"""Development model — Mack dissolution, surface advancement, CD extraction.

Theory
------
The development step converts the deprotected (latent) resist image into a
physical 3D profile by selective dissolution of deprotected regions.

The **Mack (enhanced) model** describes the development rate *R* as a
function of the normalised inhibitor concentration *M*:

    R(M) = R_max · (a + 1)(1 − M)ⁿ / [a + (1 − M)ⁿ] + R_min

    a = (n + 1) / (n − 1) · (1 − M_th)ⁿ

where:
    R_max  — maximum development rate for fully exposed resist [nm/s]
    R_min  — minimum development rate for unexposed resist [nm/s]
    n      — dissolution selectivity (contrast, typically 2–15)
    M_th   — threshold inhibitor concentration where R = (R_max + R_min)/2

Two development extraction methods are provided:

1. **Threshold development** — the resist is considered developed where
   the inhibitor concentration falls below a critical threshold M_cd.
   This yields a binary developed image.

2. **Surface-advancement / level-set development** — the dissolution
   front advances from the top surface according to the local rate
   R(M), solved via a fast-marching / level-set approach.  CD is then
   extracted at the resist-substrate interface.

CD extraction uses the developed profile to find left/right edge
positions at a given height (typically the substrate), from which
the critical dimension is computed.

All operations use PyTorch and are differentiable where possible.

References
----------
C.A. Mack, "Development of positive photoresist", TECHCON '83 (1983).
C.A. Mack, "New model for resist development", Proc. SPIE 5383,
    209–220 (2004).
"""

from __future__ import annotations

import torch
from typing import Tuple, Optional


# ──────────────────────────────────────────────
# Mack model for dissolution rate
# ──────────────────────────────────────────────


class MackModel:
    """Mack (enhanced) dissolution-rate model.

    Parameters
    ----------
    R_max : float
        Maximum development rate for fully exposed resist [nm/s].
        Typical range: 50–500 nm/s.  Default 100.0.
    R_min : float
        Minimum development rate for unexposed resist [nm/s].
        Typical range: 0.01–1.0 nm/s.  Default 0.1.
    n : float
        Dissolution selectivity (contrast).  Typical range: 2–15.
        Default 5.0.
    M_th : float
        Threshold inhibitor concentration (Mack a-parameter).
        Typical range: 0.3–0.7.  Default 0.5.
    """

    def __init__(
        self,
        R_max: float = 100.0,
        R_min: float = 0.1,
        n: float = 5.0,
        M_th: float = 0.5,
    ) -> None:
        self.R_max = R_max
        self.R_min = R_min
        self.n = n
        self.M_th = M_th

        # Mack 'a' parameter
        # a = (n + 1) / (n - 1) * (1 - M_th)^n
        eps = 1e-12
        self.a = (n + 1.0) / max(n - 1.0, eps) * (1.0 - M_th) ** n

    def rate(self, M: torch.Tensor) -> torch.Tensor:
        """Compute dissolution rate *R(M)*.

        Parameters
        ----------
        M : torch.Tensor
            Normalised inhibitor concentration [0, 1].  Any shape.

        Returns
        -------
        R : torch.Tensor
            Development rate [nm/s].  Same shape as *M*.
        """
        # Clamp M to avoid numerical issues
        M = torch.clamp(M, 0.0, 1.0)

        one_minus_M = 1.0 - M
        one_minus_M_n = one_minus_M**self.n

        # R(M) = R_max * (a + 1) * (1 - M)^n / [a + (1 - M)^n] + R_min
        denom = self.a + one_minus_M_n
        rate = self.R_max * (self.a + 1.0) * one_minus_M_n / (denom + 1e-30)
        rate = rate + self.R_min

        return rate

    def contrast(self) -> float:
        """Compute the contrast parameter γ = n · (1 − M_th) / (1 + a)."""
        return self.n * (1.0 - self.M_th) / (1.0 + self.a)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"R_max={self.R_max}, R_min={self.R_min}, "
            f"n={self.n}, M_th={self.M_th}, a={self.a:.4f})"
        )


# ──────────────────────────────────────────────
# Threshold development
# ──────────────────────────────────────────────


def threshold_development(
    inhibitor: torch.Tensor,
    threshold: float = 0.3,
) -> torch.Tensor:
    """Binary threshold development of the latent image.

    Pixels where *inhibitor* ≤ *threshold* are considered fully
    developed (1), and pixels where *inhibitor* > *threshold* are
    considered undeveloped (0).

    This is a simple, fast model suitable for quasi-3D or screening
    studies.  For more accurate profiles, use
    :func:`surface_advancement_level_set`.

    Parameters
    ----------
    inhibitor : torch.Tensor
        Normalised inhibitor concentration [0, 1].  Any shape.
    threshold : float
        Development threshold.  Default 0.3.

    Returns
    -------
    developed : torch.Tensor
        Binary mask: 1 = developed (dissolved), 0 = undeveloped.
        Same shape as *inhibitor*.
    """
    return (inhibitor <= threshold).to(inhibitor.dtype)


# ──────────────────────────────────────────────
# Surface-advancement / level-set development
# ──────────────────────────────────────────────


def surface_advancement_level_set(
    inhibitor_3d: torch.Tensor,
    mack: MackModel,
    dx: float = 1.0,
    dz: float = 1.0,
    t_develop: float | None = None,
    n_time_steps: int = 50,
) -> torch.Tensor:
    """3D level-set-like surface advancement during development.

    The dissolution front starts at the top of the resist and advances
    downward according to the local rate *R(M)*.  This is modelled
    via a **ray-tracing / time-of-flight** approximation:

        T(x, y) = Σ_k dz / R(M(k, x, y))

    where *k* indexes the depth layer.  The front position at time
    *t_develop* is the deepest layer where the cumulative development
    time ≤ *t_develop*.

    This is a fast approximation to a full level-set (fast marching)
    solution, suitable for moderate resist thicknesses.

    Parameters
    ----------
    inhibitor_3d : torch.Tensor
        3D inhibitor concentration.  Shape ``(N, H, W)`` where *N* is
        the number of depth layers (top to bottom).
    mack : MackModel
        Mack dissolution-rate model.
    dx : float
        Lateral grid spacing [nm].  Default 1.0.
    dz : float
        Vertical grid spacing [nm].  Default 1.0.
    t_develop : float, optional
        Development time [s].  If ``None``, the full 3D profile is
        computed (time at each depth).
    n_time_steps : int
        Number of time-steps for the surface advancement when
        *t_develop* is given.  Default 50.

    Returns
    -------
    profile : torch.Tensor
        Developed profile.  If *t_develop* is ``None``: 3D float tensor
        of shape ``(N, H, W)`` with values in [0, 1] representing
        whether each voxel is developed (0 = undeveloped, 1 =
        developed).  If *t_develop* is given: 2D tensor ``(H, W)``
        representing the developed depth at each (x, y) position [nm
        from top surface].
    """
    N, H, W = inhibitor_3d.shape

    # compute rate at each voxel
    R = mack.rate(inhibitor_3d)  # (N, H, W) [nm/s]

    # time to clear each layer = dz / R [s]
    dt_layer = dz / (R + 1e-30)  # (N, H, W)

    # cumulative time to reach each depth
    cum_time = torch.cumsum(dt_layer, dim=0)  # (N, H, W)

    if t_develop is None:
        # return the full 3D developed mask
        # compare cum_time to a range of times
        t_vals = torch.linspace(0, cum_time.max().item(), n_time_steps)
        # for simplicity, return mask at each depth
        # binary: 1 where the front has passed
        profile_3d = torch.zeros_like(cum_time)
        for k in range(N):
            front_passed = cum_time[k] <= cum_time[-1]  # full clearing
            profile_3d[k] = (cum_time[k] <= cum_time[-1].max()).float()
        # simpler: developed depth = number of cleared layers
        # build mask voxel-by-voxel
        profile_3d = torch.zeros_like(inhibitor_3d)
        for k in range(N):
            for i in range(H):
                for j in range(W):
                    profile_3d[k, i, j] = (
                        1.0 if cum_time[k, i, j] <= t_vals[-1]
                        else 0.0
                    )
        return profile_3d
    else:
        # developed depth: deepest layer where cum_time <= t_develop
        # use binary search / argmax
        developed_mask = cum_time <= t_develop  # (N, H, W) bool
        # depth = (last True index + 1) * dz
        # if no layer is cleared, depth = 0
        depth_map = torch.zeros((H, W), device=inhibitor_3d.device)
        for i in range(H):
            for j in range(W):
                cleared = torch.where(developed_mask[:, i, j])[0]
                if len(cleared) > 0:
                    depth_map[i, j] = (cleared[-1].item() + 1) * dz
        return depth_map


# ──────────────────────────────────────────────
# CD extraction
# ──────────────────────────────────────────────


def extract_cd(
    developed: torch.Tensor,
    row: int | None = None,
    threshold: float = 0.5,
    dx: float = 1.0,
    return_edges: bool = False,
) -> float | Tuple[float, float, float]:
    """Extract critical dimension (CD) from a developed profile.

    The CD is the width of the region where the developed image is
    at or above *threshold* (positive-tone: developed = 1 =
    dissolved, so the *un*-developed region is the remaining CD).

    For a **positive-tone** resist where *developed* = 1 means
    dissolved, the CD = width of the *zero* (undeveloped) region.

    Parameters
    ----------
    developed : torch.Tensor
        Developed profile.  2D ``(H, W)`` binary mask (float or bool),
        or 1D ``(W,)`` line-cut.
    row : int, optional
        Row index for CD extraction.  If ``None`` and *developed* is
        2D, uses the middle row.
    threshold : float
        Classification threshold.  Default 0.5.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.

    Returns
    -------
    cd : float
        Critical dimension [nm].
    left_edge : float, optional
        Left edge position [nm] — only if *return_edges* is ``True``.
    right_edge : float, optional
        Right edge position [nm] — only if *return_edges* is ``True``.
    """
    if developed.ndim == 2:
        if row is None:
            row = developed.shape[0] // 2
        line = developed[row, :]
    else:
        line = developed

    # binarise
    binary = (line > threshold).float()

    # positive tone: develop = 1 means dissolved, so CD = width
    # of undeveloped (binary == 0) region.
    # Find transitions: 0 → 1 and 1 → 0
    diffs = torch.diff(binary)
    rising = torch.where(diffs > 0.5)[0]  # 0 → 1 (into developed)
    falling = torch.where(diffs < -0.5)[0]  # 1 → 0 (into undeveloped)

    # For a feature (CD bar), undeveloped region is binary == 0.
    # If the pattern starts and ends with undeveloped regions,
    # we want the first undeveloped run.
    # Simple approach: width of all undeveloped segments
    # Find runs where binary == 0
    if len(rising) == 0 and len(falling) == 0:
        # uniform
        cd_nm = 0.0 if binary[0] > threshold else binary.shape[0] * dx
        if return_edges:
            return cd_nm, 0.0, cd_nm
        return cd_nm

    # Measure the largest undeveloped segment
    runs = _find_runs(binary, target=0)
    if len(runs) == 0:
        cd_nm = 0.0
        left_edge, right_edge = 0.0, 0.0
    else:
        # largest run by length
        longest = max(runs, key=lambda r: r[1] - r[0])
        lidx, ridx = longest
        cd_nm = (ridx - lidx + 1) * dx
        left_edge = lidx * dx
        right_edge = (ridx + 1) * dx

    if return_edges:
        return cd_nm, left_edge, right_edge
    return cd_nm


# ──────────────────────────────────────────────
# Helper: find consecutive runs of a target value
# ──────────────────────────────────────────────


def _find_runs(x: torch.Tensor, target: int = 0) -> list:
    """Find intervals where ``x == target``.

    Returns list of (start_idx, end_idx) inclusive.
    """
    padded = torch.cat(
        [torch.tensor([1 - target], device=x.device), x, torch.tensor([1 - target], device=x.device)]
    )
    diffs = torch.diff(padded.float())
    starts = torch.where(diffs < -0.5)[0]
    ends = torch.where(diffs > 0.5)[0] - 1
    return [(s.item(), e.item()) for s, e in zip(starts, ends)]