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

Development models provided:

1. **Threshold development** — the resist is considered developed where
   the inhibitor concentration falls below a critical threshold M_cd.
   This yields a binary developed image (screening only).

2. **Eikonal development front** (``eikonal_development``) — the
   physical model: the dissolution front is an isotropic wave with local
   speed R(M); its first-arrival time obeys |∇T| = 1/R with T = 0 on the
   top surface and is solved by fast sweeping (Zhao 2005). Lateral
   dissolution, undercut and sidewall angle are represented.

3. **Vertical-column model** (``surface_advancement_level_set``) — each
   column developed independently from the top, T = Σ dz/R. No lateral
   dissolution. Fast approximation and the reference the Eikonal solver
   reduces to without lateral rate variation.

4. ``stochastic_development`` — an EXPERIMENTAL event-based dissolution-
   noise model with a dimensionless event-rate parameter and no
   literature source. Not used by the pipeline (disabled 2026-09-04,
   see pipeline.SimulationConfig.development_stochasticity).

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

import math
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
    """Event-based stochastic development (EXPERIMENTAL, not in the pipeline).

    Status (2026-09-04): kept as a standalone building block only. Its
    ``strength`` is a unit-less event-rate knob without a literature source,
    and when it was driven by the pipeline's depth overshoot its output
    depended on the numerical layer count; the pipeline therefore refuses
    ``development_stochasticity=True`` (audit A6).

    Model
    -----
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
        raise ValueError(f"development correlation_nm must be >= 0, got {correlation_nm}")

    drive = torch.clamp((latent - threshold) / max(threshold, 1e-12), min=0.0)
    rate = strength * drive

    if rng is None:
        rng = torch.Generator(device=latent.device)
    n_events = torch.poisson(rate, generator=rng)

    if correlation_nm > 0:
        from euvsimulator.resist.exposure import gaussian_se_blur

        e_dev = gaussian_se_blur(n_events.to(latent.dtype), sigma=correlation_nm, dx=dx)
    else:
        e_dev = n_events.to(latent.dtype)

    return (e_dev >= 0.5).to(latent.dtype)


# ──────────────────────────────────────────────
# Eikonal development front (fast sweeping)
# ──────────────────────────────────────────────


def eikonal_arrival_time(
    rate_3d: torch.Tensor,
    dx: float,
    dz: float,
    n_iter: int = 6,
    tol: float = 1e-6,
) -> torch.Tensor:
    """Arrival time T(x, z) of the development front, |∇T| = 1/R(x, z).

    The dissolution front is a wave propagating with the local, isotropic
    speed R(M(x, z)) (Mack's rate): its first-arrival time obeys the Eikonal
    equation |∇T| = 1/R with T = 0 on the resist top surface, the same
    equation a level-set / fast-marching development simulator solves. It is
    solved here with the fast-sweeping method (H. Zhao, "A fast sweeping
    method for Eikonal equations", Math. Comp. 74, 603-627, 2005): Godunov
    upwind discretisation, Gauss-Seidel sweeps in the four (z, x) sweep
    directions, vectorised over the un-modelled y direction (tensor rows).
    First-order accurate in the grid spacing.

    Boundary conditions: T = 0 at z = 0 (top surface, in contact with the
    developer everywhere -- a ghost node above layer 0); periodic in x (the
    grid is one period); no condition at the bottom (the substrate is not
    dissolved -- the front simply stops).

    Parameters
    ----------
    rate_3d : torch.Tensor
        Development rate R [nm/s] per voxel, shape ``(N, H, W)`` = (depth
        layers top → bottom, rows, columns). Layer k occupies
        z ∈ [k·dz, (k+1)·dz].
    dx, dz : float
        Lateral and vertical grid spacing [nm].
    n_iter : int
        Maximum number of full 4-direction sweep iterations. Two iterations
        suffice for monotone rate fields; convex/re-entrant fronts need more.
    tol : float
        Stop when the maximum change of T between iterations is below this
        value [s].

    Returns
    -------
    T : torch.Tensor
        Arrival time [s] at the BOTTOM face of every layer, shape
        ``(N, H, W)``. T[k] ≤ T[k+1] along a column is not enforced -- a
        lateral front can arrive at a deeper voxel earlier than the column
        above it (undercut), which is the point of solving the Eikonal
        equation rather than integrating dz / R down each column.
    """
    if rate_3d.ndim != 3:
        raise ValueError(f"rate_3d must be (N, H, W), got shape {tuple(rate_3d.shape)}")
    if dx <= 0 or dz <= 0:
        raise ValueError("dx and dz must be > 0")
    N, H, W = rate_3d.shape
    slowness = 1.0 / rate_3d.clamp(min=1e-30)
    big = torch.tensor(1e30, dtype=rate_3d.dtype, device=rate_3d.device)
    T = torch.full((N + 1, H, W), 1e30, dtype=rate_3d.dtype, device=rate_3d.device)
    T[0] = 0.0  # ghost row: top surface

    inv_hz2 = 1.0 / dz**2
    inv_hx2 = 1.0 / dx**2
    A2 = inv_hz2 + inv_hx2

    def godunov(t_old, a, b, f):
        # Solve (T-a)^2/hz^2 + (T-b)^2/hx^2 = f^2 for T > max(a, b), else the
        # one-dimensional update from the smaller neighbour.
        t1 = a + f * dz
        t2 = b + f * dx
        B2 = -2.0 * (a * inv_hz2 + b * inv_hx2)
        C2 = a * a * inv_hz2 + b * b * inv_hx2 - f * f
        disc = (B2 * B2 - 4.0 * A2 * C2).clamp(min=0.0)
        t3 = (-B2 + torch.sqrt(disc)) / (2.0 * A2)
        t_new = torch.where(t3 > torch.maximum(a, b), t3, torch.minimum(t1, t2))
        return torch.minimum(t_old, t_new)

    for _ in range(n_iter):
        T_prev = T.clone()
        for z_dir in (1, -1):
            z_range = range(1, N + 1) if z_dir == 1 else range(N, 0, -1)
            for x_dir in (1, -1):
                x_range = range(W) if x_dir == 1 else range(W - 1, -1, -1)
                for k in z_range:
                    up = T[k - 1]
                    down = T[k + 1] if k + 1 <= N else big.expand_as(up)
                    a = torch.minimum(up, down)
                    Tk = T[k]
                    fk = slowness[k - 1]
                    for i in x_range:
                        b = torch.minimum(Tk[:, (i - 1) % W], Tk[:, (i + 1) % W])
                        Tk[:, i] = godunov(Tk[:, i], a[:, i], b, fk[:, i])
        if float((T - T_prev).abs().max()) < tol:
            break
    return T[1:]


def developed_depth_from_arrival(
    T: torch.Tensor,
    t_develop: float,
    dz: float,
) -> torch.Tensor:
    """Developed depth per (y, x) column from the arrival-time field.

    A column counts as developed down to the deepest layer whose bottom face
    the front has reached within *t_develop*; the partially developed next
    layer is added by linear interpolation of T between the two bounding
    faces (same continuous-depth semantics as
    :func:`surface_advancement_level_set`, which the LER/LWR sub-pixel edge
    extraction relies on). Where the front has reached the bottom of the
    film with time to spare, the depth is reported as (N + 1)·dz − (one
    layer of overshoot) exactly like the column model, so both models feed
    the same "fully cleared" test in the pipeline.
    """
    N, H, W = T.shape
    reached = T <= t_develop
    # Layers are reached top-down along a column unless a lateral front
    # arrives from below; count the leading run of reached layers so that a
    # column is "cleared through" only if every layer is reached.
    not_reached = (~reached).to(torch.int64)
    first_not = torch.where(
        not_reached.any(dim=0),
        torch.argmax(not_reached, dim=0),
        torch.full((H, W), N, dtype=torch.int64, device=T.device),
    )
    n_clear = first_not  # number of consecutive cleared layers from the top
    depth = n_clear.to(T.dtype) * dz
    idx_next = n_clear.clamp(max=N - 1)
    T_next = torch.gather(T, 0, idx_next.unsqueeze(0)).squeeze(0)
    T_prev = torch.where(
        n_clear > 0,
        torch.gather(T, 0, (n_clear - 1).clamp(min=0).unsqueeze(0)).squeeze(0),
        torch.zeros_like(T_next),
    )
    frac = ((t_develop - T_prev) / (T_next - T_prev).clamp(min=1e-30)).clamp(0.0, 1.0)
    partial = torch.where(n_clear < N, frac * dz, torch.zeros_like(frac))
    # Fully cleared columns: report one extra dz of overshoot, matching the
    # column model's convention (see surface_advancement_level_set).
    overshoot = torch.where(n_clear >= N, torch.full_like(frac, dz), torch.zeros_like(frac))
    return depth + partial + overshoot


def eikonal_development(
    inhibitor_3d: torch.Tensor,
    mack: MackModel,
    dx: float,
    dz: float,
    t_develop: float,
    n_iter: int = 6,
    return_arrival: bool = False,
    chunk_rows: int = 2048,
) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
    """Developed depth map [nm] from a 2D (x, z) Eikonal development front.

    With ``return_arrival=True`` the arrival-time field ``T`` (shape
    ``(N, H, W)``, seconds) is returned as well; its bottom layer is what
    :func:`edge_positions_from_arrival` uses for a sub-pixel line width.

    Replaces the vertical-column time-of-flight of
    :func:`surface_advancement_level_set` (which cannot represent lateral
    dissolution, undercut or sidewall angle) by the first-arrival time of an
    isotropic front with local speed R(M) -- see :func:`eikonal_arrival_time`.
    Returns the same continuous depth field (shape ``(H, W)``) so the
    pipeline's CD/LER/LWR extraction is unchanged.
    """
    # Rows (y) are independent 2D (x, z) problems: solve them in chunks so the
    # solver's working set (~12x the field, measured 2026-09-05) stays bounded
    # for the 61440-row LER fields. Bitwise identical to one call.
    N, H, W = inhibitor_3d.shape
    if H > chunk_rows:
        depths, arrivals = [], []
        for y0 in range(0, H, chunk_rows):
            out = eikonal_development(
                inhibitor_3d[:, y0 : y0 + chunk_rows],
                mack,
                dx=dx,
                dz=dz,
                t_develop=t_develop,
                n_iter=n_iter,
                return_arrival=return_arrival,
                chunk_rows=chunk_rows,
            )
            if return_arrival:
                depths.append(out[0])
                arrivals.append(out[1])
            else:
                depths.append(out)
        depth = torch.cat(depths, dim=0)
        return (depth, torch.cat(arrivals, dim=1)) if return_arrival else depth
    R = mack.rate(inhibitor_3d)
    T = eikonal_arrival_time(R, dx=dx, dz=dz, n_iter=n_iter)
    depth = developed_depth_from_arrival(T, t_develop, dz)
    if return_arrival:
        return depth, T
    return depth


def edge_positions_from_arrival(
    T_row: torch.Tensor,
    t_develop: float,
    dx: float,
) -> tuple[float, float]:
    """Sub-pixel left/right edge [nm] of the longest undeveloped run in one
    row of the bottom-layer arrival-time field.

    A pixel is cleared when the front reached the film bottom within
    *t_develop*. Between the last cleared pixel (T_a ≤ t_develop) and the
    first uncleared one (T_b > t_develop) the front has travelled a fraction
    (t_develop − T_a)/(T_b − T_a) of the pixel: T is linear in x behind the
    edge (the lateral front moves at the local rate, ≈ R_min in the
    unexposed line), so the crossing is first-order exact. Verified
    2026-09-05 against a 4× finer grid (preflight_subpixel_T.py: 64-px CD
    within 0.35 nm of the 256-px CD, monotone in dose; interpolating the
    developed-depth map instead gave a 0.8 nm sawtooth). Periodic in x.

    Returns ``(nan, nan)`` when no pixel is uncleared (no line) or none is
    cleared (space not open).
    """
    if T_row.ndim != 1:
        raise ValueError(f"expected a 1D row, got shape {tuple(T_row.shape)}")
    W = T_row.shape[0]
    cleared = T_row <= t_develop
    if not cleared.any() or cleared.all():
        return float("nan"), float("nan")
    # longest run of uncleared pixels (periodic): rotate so that the row
    # starts with a cleared pixel, then take the longest 0-run
    start = int(torch.nonzero(cleared).flatten()[0])
    rolled = torch.roll(~cleared, -start)
    best_len, best_i0 = 0, 0
    i = 0
    while i < W:
        if bool(rolled[i]):
            j = i
            while j < W and bool(rolled[j]):
                j += 1
            if j - i > best_len:
                best_len, best_i0 = j - i, i
            i = j
        else:
            i += 1
    i0 = (best_i0 + start) % W  # first uncleared pixel
    i1 = (best_i0 + best_len - 1 + start) % W  # last uncleared pixel
    Ta, Tb = float(T_row[(i0 - 1) % W]), float(T_row[i0])
    Ta2, Tb2 = float(T_row[(i1 + 1) % W]), float(T_row[i1])

    def _frac(t_clear: float, t_line: float) -> float:
        # fraction of the pixel the front entered; an unreachable pixel
        # (T = inf, only possible with R = 0) puts the edge on the pixel face
        if not math.isfinite(t_line):
            return 0.5
        return (t_develop - t_clear) / (t_line - t_clear) if t_line > t_clear else 1.0

    frac_l = _frac(Ta, Tb)
    frac_r = _frac(Ta2, Tb2)
    x_left = ((i0 - 1) + frac_l) * dx
    x_right = ((i1 + 1) - frac_r) * dx
    if x_right < x_left:  # run wraps around the periodic boundary
        x_right += W * dx
    return x_left, x_right


# ──────────────────────────────────────────────
# Surface-advancement (vertical column) development
# ──────────────────────────────────────────────


def surface_advancement_level_set(
    inhibitor_3d: torch.Tensor,
    mack: MackModel,
    dx: float = 1.0,
    dz: float = 1.0,
    t_develop: float = 30.0,
) -> torch.Tensor:
    """Vertical-column ("time-of-flight") development model.

    Each (x, y) column is developed independently from the top down: the
    time to reach the bottom face of layer k is T_k = Σ_{j≤k} dz / R(M_j).
    The front position at *t_develop* is the deepest face with T ≤ t,
    plus a linear interpolation into the next layer.

    LIMITATION -- this is NOT a level-set / fast-marching solution despite
    the historical name: there is no lateral dissolution, so undercut,
    sidewall angle and the erosion of a line from an already-cleared
    neighbouring space cannot occur. Use :func:`eikonal_development`
    (isotropic front, |∇T| = 1/R) for the physical model; this function
    is kept as the fast, well-tested column approximation and as the
    reference the Eikonal solver must reduce to when the rate has no
    lateral variation (tests/test_eikonal_development.py).

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
    t_develop : float
        Development time [s].

    Returns
    -------
    depth_map : torch.Tensor
        Developed depth at each (y, x) position [nm from the top surface],
        shape ``(H, W)``; continuous (sub-layer interpolation), with up to
        one dz of overshoot for fully cleared columns (see the note in the
        body). A former ``t_develop=None`` mode returning an all-ones 3D
        mask was dead, defective code and was removed 2026-09-04.
    """
    N, H, W = inhibitor_3d.shape

    # compute rate at each voxel
    R = mack.rate(inhibitor_3d)  # (N, H, W) [nm/s]

    # time to clear each layer = dz / R [s]
    dt_layer = dz / (R + 1e-30)  # (N, H, W)

    # cumulative time to reach each depth
    cum_time = torch.cumsum(dt_layer, dim=0)  # (N, H, W)

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
