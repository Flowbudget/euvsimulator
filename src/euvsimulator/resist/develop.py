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
209-220 (2004).
"""

from __future__ import annotations

from typing import Tuple

import torch

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


def stochastic_development(
    latent: torch.Tensor,
    threshold: float = 0.3,
    strength: float = 1.0,
    correlation_nm: float = 0.5,
    dx: float = 1.0,
    rng: torch.Generator | None = None,
) -> torch.Tensor:
    """Event-based stochastic development (STEP 5.3).

    Physical model
    --------------
    The dissolution of a resist is a discrete stochastic process:
    molecular aggregates dissolve when the local driving force
    (over-threshold latent concentration) overcomes the activation
    barrier.  The model has three ingredients:

    1. Local driving force (normalised, non-negative):

           drive(x) = max(0, (latent(x) - threshold) / threshold)

    2. Dissolution events are drawn per pixel from a Poisson
       distribution with mean rate:

           rate(x) = strength * drive(x)

       ``strength`` is dimensionless: the mean number of dissolution
       events per pixel at full driving force (drive = 1).

    3. Events are spread over a short correlation length
       ``correlation_nm`` (molecular aggregate size, Gaussian kernel,
       same separable convolution machinery as the SE blur), giving a
       spatially coherent dissolution density ``e_dev``.  A pixel is
       developed when ``e_dev >= 0.5``.

    The coherent spreading suppresses isolated holes inside the
    developed region (a dissolution aggregate removes a connected
    cluster, not isolated pixels), which keeps the edge extraction
    well-defined.  In the limit ``strength -> infinity`` the model
    reduces to the deterministic threshold development.

    Parameters
    ----------
    latent : torch.Tensor
        Continuous latent image driving development (e.g. acid or
        deprotected concentration).  2D ``(H, W)``.
    threshold : float
        Development threshold on *latent*.  Default 0.3.
    strength : float
        Dimensionless development strength: mean dissolution events
        per pixel at drive = 1.  Larger -> sharper development,
        smaller stochastic contribution.  Default 1.0.
    correlation_nm : float
        Spatial correlation length of dissolution aggregates [nm].
        Default 0.5 (molecular scale).  ``<= 0`` disables spreading.
    dx : float
        Pixel spacing [nm].  Default 1.0.
    rng : torch.Generator, optional
        RNG for the Poisson draw.  When None, a fresh CPU generator
        is created (non-reproducible).  Reproducible runs must pass
        a seeded generator.

    Returns
    -------
    developed : torch.Tensor
        Binary mask: 1 = developed (dissolved), 0 = undeveloped.
        Same shape as *latent*.
    """
    if latent.ndim != 2:
        raise ValueError(f"Expected 2D tensor, got {latent.ndim}D")
    if strength <= 0:
        raise ValueError(f"development strength must be > 0, got {strength}")
    if correlation_nm < 0:
        raise ValueError(
            f"development correlation_nm must be >= 0, got {correlation_nm}"
        )

    drive = torch.clamp((latent - threshold) / max(threshold, 1e-12), min=0.0)
    rate = strength * drive

    if rng is None:
        rng = torch.Generator(device=latent.device)
    n_events = torch.poisson(rate, generator=rng)

    if correlation_nm > 0:
        from euvsimulator.resist.exposure import gaussian_se_blur

        e_dev = gaussian_se_blur(
            n_events.to(latent.dtype), sigma=correlation_nm, dx=dx
        )
    else:
        e_dev = n_events.to(latent.dtype)

    return (e_dev >= 0.5).to(latent.dtype)


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
        # Vectorized: use broadcasting to compare all voxels at once
        profile_3d = (cum_time <= t_vals[-1]).float()
        return profile_3d
    else:
        # Developed depth: fully-cleared layers, PLUS a linearly-interpolated
        # partial clearing into the next (boundary) layer using the time
        # remaining after the last fully-cleared layer and that boundary
        # layer's own local rate. Without this interpolation, depth is a
        # staircase quantised to multiples of dz (only N possible output
        # values) -- fine for a quick deterministic CD estimate, but it
        # silently discards any variation smaller than one dz step, which
        # matters when this function is used per-realisation with a noisy
        # inhibitor field (photon-shot-noise-driven LER/LWR): the noise is
        # typically much finer than dz, so the un-interpolated version was
        # measuring near-zero LER regardless of the actual noise (found and
        # fixed 2026-09-03 while wiring the stochastic LER/LWR path to this
        # same chain -- see docs/claude_code_arbeitslog.md).
        developed_mask = cum_time <= t_develop  # (N, H, W) bool
        has_true = developed_mask.any(dim=0)  # (H, W) bool
        rev_mask = developed_mask.flip(dims=(0,)).to(torch.int64)
        first_true = rev_mask.argmax(dim=0)  # (H, W), index into the reversed array
        last_cleared_idx = N - 1 - first_true  # (H, W) int64; meaningless where ~has_true

        zeros_hw = torch.zeros((H, W), device=inhibitor_3d.device, dtype=cum_time.dtype)

        # Time already spent clearing layers 0..last_cleared_idx (0 if none cleared).
        gather_idx = last_cleared_idx.clamp(min=0)
        cum_time_at_last = torch.gather(cum_time, 0, gather_idx.unsqueeze(0)).squeeze(0)
        time_spent = torch.where(has_true, cum_time_at_last, zeros_hw)

        # Boundary layer to partially clear into: the layer right after the
        # last fully-cleared one, or layer 0 if none is fully cleared yet.
        # Clamped to N-1 so a front already at the last layer stays there.
        next_idx = torch.where(
            has_true, (last_cleared_idx + 1).clamp(max=N - 1), torch.zeros_like(last_cleared_idx)
        )
        R_next = torch.gather(R, 0, next_idx.unsqueeze(0)).squeeze(0)  # (H, W) [nm/s]

        t_remain = (t_develop - time_spent).clamp(min=0.0)
        partial_depth = (t_remain * R_next).clamp(min=0.0, max=dz)
        # No boundary layer left to partially clear into once every layer
        # (0..N-1) is already fully cleared.
        fully_cleared_all = has_true & (last_cleared_idx >= N - 1)
        partial_depth = torch.where(fully_cleared_all, torch.zeros_like(partial_depth), partial_depth)

        base_depth = torch.where(has_true, (last_cleared_idx.to(cum_time.dtype) + 1.0) * dz, zeros_hw)
        depth_map = base_depth + partial_depth
        # NOT clamped to (N-1)*dz (the modelled film thickness): a pixel
        # whose front reaches the last layer WITH time to spare naturally
        # reports up to one extra dz of "overshoot" (base_depth can reach
        # N*dz when fully_cleared_all). This is deliberate, not an
        # oversight -- it is the only signal callers have for "how much
        # margin this pixel cleared with," which
        # resist/develop.py:stochastic_development()'s drive formula
        # ((latent-threshold)/threshold) needs to produce any nonzero
        # event rate at all for a fully-clearing pixel. Clamping this away
        # was tried and found to make development_stochasticity=True
        # degenerate (zero drive everywhere a pixel fully clears) --
        # see docs/claude_code_arbeitslog.md, 2026-09-03. Callers that
        # want a strict "did this fully clear the real film" binary
        # should compare with `>=` against the true thickness ((N-1)*dz),
        # not rely on this field never exceeding it.
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
        [
            torch.tensor([1 - target], device=x.device),
            x,
            torch.tensor([1 - target], device=x.device),
        ]
    )
    diffs = torch.diff(padded.float())
    starts = torch.where(diffs < -0.5)[0]
    ends = torch.where(diffs > 0.5)[0] - 1
    return [(s.item(), e.item()) for s, e in zip(starts, ends)]
