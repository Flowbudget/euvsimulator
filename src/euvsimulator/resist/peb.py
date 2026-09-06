"""Post-exposure bake (PEB) — reaction-diffusion of photoacid.

Theory
------
During the PEB, photoacid generated during exposure diffuses through
the resist and catalyses deprotection (cleavage of acid-labile protecting
groups in a chemically amplified resist).  The two governing processes are:

1. **Acid diffusion** (Fickian)::

    ∂[H⁺]/∂t = ∇·(D · ∇[H⁺])

   where *D* is the acid diffusivity [nm²/s].  In the general case the
   diffusivity can depend on temperature, degree of deprotection, or local
   free volume.

2. **Deprotection kinetics**::

    ∂M/∂t = −k · [H⁺] · M

   where *M* is the normalised inhibitor concentration (1 = full, 0 =
   none) and *k* is the deprotection rate constant [s⁻¹ M⁻¹].

For the finite-difference solver we use an **Alternating Direction
Implicit (ADI)** scheme via pre-built tridiagonal systems and
``torch.linalg.solve``, which is unconditionally stable for the 2D
diffusion equation and second-order accurate in space.

An analytical approximation is also provided for cases where diffusion
can be neglected (or replaced by the SE-blur from exposure).

All operations use PyTorch and are differentiable.

References
----------
E. Reichmanis, L.F. Thompson, "Polymer materials for microlithography",
    Chem. Rev. 89(6), 1273–1289 (1989).
M.D. Stewart et al., "Comparison of analytical and finite-difference
    models for post-exposure bake in chemically amplified resists",
    Proc. SPIE 6153, 61534B (2006).
"""

from __future__ import annotations

import math
from typing import Tuple

import torch

# ──────────────────────────────────────────────
# Reaction-diffusion — ADI solver (2D)
# ──────────────────────────────────────────────


def _build_tridiagonal_matrix(
    n: int,
    diag: float,
    off_diag: float,
    diag_boundary: float,
    device: torch.device,
    dtype: torch.dtype,
    off_boundary: float | None = None,
) -> torch.Tensor:
    """Build a tridiagonal matrix of size n×n.

    Parameters
    ----------
    n : int
        Matrix dimension.
    diag : float
        Interior diagonal value.
    off_diag : float
        Sub/super diagonal value.
    diag_boundary : float
        Diagonal value at rows 0 and n-1 (boundary).
    device : torch.device
        Tensor device.
    dtype : torch.dtype
        Tensor dtype.
    off_boundary : float, optional
        Off-diagonal value in the boundary rows (default: *off_diag*). The
        zero-flux condition in flux (finite-volume) form is the row
        (1 + α) A_0 − α A_1, i.e. ``diag_boundary = 1 + α`` with the interior
        off-diagonal: the discrete diffusion operator then has zero column
        sums and conserves mass. Before 2026-09-04 the explicit half-step
        used the mirror form 2(A_1 − A_0) (column sum −1) against this
        implicit flux form; the mismatch created mass in a zero-flux problem
        (+0.14 % at α = 2.5, +1.6 % at α = 10 after ten steps -- audit C1).

    Returns
    -------
    T : torch.Tensor
        Tridiagonal matrix of shape (n, n).
    """
    ob = off_diag if off_boundary is None else off_boundary
    T = torch.zeros(n, n, device=device, dtype=dtype)
    T[0, 0] = diag_boundary
    T[0, 1] = ob
    for i in range(1, n - 1):
        T[i, i - 1] = off_diag
        T[i, i] = diag
        T[i, i + 1] = off_diag
    T[n - 1, n - 2] = ob
    T[n - 1, n - 1] = diag_boundary
    return T


def _laplacian_y_explicit(A: torch.Tensor, boundary: str) -> torch.Tensor:
    """Compute ∂²A/∂y² using central differences (explicit, full grid)."""
    H = A.shape[0]
    lap = torch.zeros_like(A)
    # interior
    lap[1:-1, :] = A[2:, :] - 2.0 * A[1:-1, :] + A[:-2, :]
    # boundaries
    if boundary == "neumann":
        # Flux (finite-volume) form: the boundary cell exchanges with ONE
        # neighbour only, so the discrete operator has zero column sums and
        # the scheme conserves mass. The mirror form 2(A1 - A0) does not
        # (column sum -1), and mixing it with the implicit flux-form row
        # created mass (audit C1, fixed 2026-09-04).
        lap[0, :] = A[1, :] - A[0, :]
        lap[H - 1, :] = A[H - 2, :] - A[H - 1, :]
    else:  # dirichlet
        lap[0, :] = -2.0 * A[0, :]
        lap[H - 1, :] = -2.0 * A[H - 1, :]
    return lap


def _laplacian_x_explicit(A: torch.Tensor, boundary: str) -> torch.Tensor:
    """Compute ∂²A/∂x² using central differences (explicit, full grid)."""
    W = A.shape[1]
    lap = torch.zeros_like(A)
    lap[:, 1:-1] = A[:, 2:] - 2.0 * A[:, 1:-1] + A[:, :-2]
    if boundary == "neumann":
        lap[:, 0] = A[:, 1] - A[:, 0]  # flux form, see _laplacian_y_explicit
        lap[:, W - 1] = A[:, W - 2] - A[:, W - 1]
    else:  # dirichlet
        lap[:, 0] = -2.0 * A[:, 0]
        lap[:, W - 1] = -2.0 * A[:, W - 1]
    return lap


def reaction_diffusion_adi(
    acid: torch.Tensor,
    inhibitor: torch.Tensor,
    D: float | torch.Tensor = 5.0,
    k: float | torch.Tensor = 0.1,
    dt: float = 1.0,
    n_steps: int = 10,
    dx: float = 1.0,
    boundary: str = "neumann",
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Solve the 2D reaction-diffusion PEB equations with ADI.

    Governing equations (in 2D)::

        ∂A/∂t = D · (∂²A/∂x² + ∂²A/∂y²)
        ∂M/∂t = −k · A · M

    where *A* = [H⁺] is the photoacid concentration, *M* is the
    normalised inhibitor (PAC) concentration, and *k* is the deprotection
    rate constant.  Diffusion is solved with an ADI (Peaceman–Rachford)
    scheme; the reaction term is integrated analytically between
    diffusion half-steps.

    Parameters
    ----------
    acid : torch.Tensor
        Photoacid concentration [a.u.].  Shape ``(H, W)``.
    inhibitor : torch.Tensor
        Normalised inhibitor concentration [0, 1].  Shape ``(H, W)``.
    D : float or torch.Tensor
        Acid diffusivity [nm²/s].  Default 5.0.
    k : float or torch.Tensor
        Deprotection rate constant [s⁻¹].  Default 0.1.
    dt : float
        Time step [s].  Default 1.0.
    n_steps : int
        Number of time steps.  Default 10.
    dx : float
        Grid spacing [nm].  Default 1.0.
    boundary : str
        Boundary condition: ``'neumann'`` (zero-flux, default) or
        ``'dirichlet'`` (zero-concentration).

    Returns
    -------
    acid_final : torch.Tensor
        Photoacid after PEB.  Same shape as *acid*.
    inhibitor_final : torch.Tensor
        Inhibitor concentration after PEB.  Same shape as *inhibitor*.
    """
    A = acid.clone()
    M = inhibitor.clone()
    H, W = A.shape
    device, dtype = A.device, A.dtype

    # ADI coefficients (Crank–Nicolson split)
    alpha = D * dt / (2.0 * dx**2)

    # Pre-build tridiagonal system matrices
    # (1 + 2α) on diagonal, -α on off-diagonals
    main_diag = 1.0 + 2.0 * alpha
    off_diag = -alpha

    if boundary == "neumann":
        # Zero flux in finite-volume (flux) form: (1 + α) A_0 − α A_1 -- the
        # boundary cell exchanges with one neighbour only, zero column sums,
        # mass conserved; the explicit half-step uses the same form.
        main_b, off_b = 1.0 + alpha, off_diag
    elif boundary == "dirichlet":
        main_b, off_b = main_diag, off_diag  # ghost = 0: standard interior row
    else:
        raise ValueError(f"Unknown boundary condition: '{boundary}'")

    T_x = _build_tridiagonal_matrix(
        W, main_diag, off_diag, main_b, device, dtype, off_boundary=off_b
    )
    T_y = _build_tridiagonal_matrix(
        H, main_diag, off_diag, main_b, device, dtype, off_boundary=off_b
    )

    for _ in range(n_steps):
        # --- half-step 1: implicit in x, explicit in y ---
        # RHS = (I + α·∂²/∂y²) A
        lap_y = _laplacian_y_explicit(A, boundary)
        R = A + alpha * lap_y  # (H, W)
        # Solve T_x · A_new[i,:]^T = R[i,:]^T for each row i
        # T_x @ A_new[i,:] = R[i,:]  →  A_new = solve(T_x, R.T).T
        # Using torch.linalg.solve instead of inverse for numerical stability
        A = torch.linalg.solve(T_x, R.T).T  # (H, W)

        # --- reaction half-step ---
        M = M * torch.exp(-k * A * (dt / 2.0))

        # --- half-step 2: implicit in y, explicit in x ---
        lap_x = _laplacian_x_explicit(A, boundary)
        R = A + alpha * lap_x  # (H, W)
        # T_y · A_new[:,j] = R[:,j] for each column j
        A = torch.linalg.solve(T_y, R)  # (H, W)

        # --- reaction half-step ---
        M = M * torch.exp(-k * A * (dt / 2.0))

    return A, M


# ──────────────────────────────────────────────
# Analytical reaction-diffusion (diffusion via
# Gaussian blur + first-order deprotection)
# ──────────────────────────────────────────────


def effective_reaction_time(t_bake: float, acid_lifetime_s: float | None) -> float:
    """Time-integral of the acid that survives a first-order loss.

    With acid decaying as H(t) = H0·exp(−t/τ) during the bake (Yamamoto et al.
    2011, Eq. 1: "τ, the average acid lifetime"; Kang et al. 2010: trapping),
    the deprotection integrates ∫H dt = H0·τ·(1 − exp(−t/τ)), so every
    closed form of the kind exp(−k·H0·t) stays exact with t replaced by this
    effective time. ``None`` (or a non-positive value) means no loss.
    """
    if acid_lifetime_s is None or acid_lifetime_s <= 0.0:
        return float(t_bake)
    return float(acid_lifetime_s) * (1.0 - math.exp(-float(t_bake) / float(acid_lifetime_s)))


def reaction_diffusion_analytical(
    acid: torch.Tensor,
    inhibitor: torch.Tensor,
    D: float | torch.Tensor = 0.0,
    k: float | torch.Tensor = 0.1,
    t_bake: float = 10.0,
    sigma_diff: float | torch.Tensor | None = None,
    dx: float = 1.0,
    acid_lifetime_s: float | None = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Analytical PEB model — Gaussian diffusion + first-order deprotection.

    ``acid_lifetime_s`` (τ, optional): first-order acid loss during the bake;
    deprotection and the D·t diffusion length then use the effective time
    τ·(1 − e^{−t/τ}) (:func:`effective_reaction_time`).

    When acid diffusivity is negligible (or already captured by SE blur
    from the exposure step), the PEB is approximated by:

        M(t) = M₀ · exp(−k · [H⁺] · t)

    If *sigma_diff* (the diffusion length) is non-zero, the acid map is
    first blurred with a Gaussian of that sigma (representing the acid
    diffusion length L_d = sqrt(2·D·t)).

    Parameters
    ----------
    acid : torch.Tensor
        Photoacid concentration [a.u.].  Shape ``(H, W)``.
    inhibitor : torch.Tensor
        Initial normalised inhibitor concentration [0, 1].
        Shape ``(H, W)``.
    D : float or torch.Tensor
        Acid diffusivity [nm²/s].  Default 0.0 (no diffusion).
    k : float or torch.Tensor
        Deprotection rate constant [s⁻¹].  Default 0.1.
    t_bake : float
        Bake time [s].  Default 10.0.
    sigma_diff : float or torch.Tensor, optional
        Diffusion length [nm] = ``sqrt(2·D·t)``.  If given, overrides
        *D* and *t_bake*.
    dx : float
        Grid spacing [nm/pixel].  Default 1.0.

    Returns
    -------
    acid_final : torch.Tensor
        Photoacid after PEB (modified by diffusion if applicable).
        Same shape as *acid*.
    inhibitor_final : torch.Tensor
        Inhibitor concentration after PEB.  Same shape as *inhibitor*.
    """
    A = acid.clone()
    t_eff = effective_reaction_time(t_bake, acid_lifetime_s)

    if sigma_diff is not None and sigma_diff > 0:
        from euvsimulator.resist.exposure import gaussian_se_blur

        A = gaussian_se_blur(A, sigma=sigma_diff, dx=dx)
    elif D > 0 and t_eff > 0:
        sigma_val = (2.0 * D * t_eff) ** 0.5
        if sigma_val > 0.1:
            from euvsimulator.resist.exposure import gaussian_se_blur

            A = gaussian_se_blur(A, sigma=sigma_val, dx=dx)

    # Deprotection: M(t) = M₀ · exp(−k · A · t_eff)
    M_t = inhibitor * torch.exp(-k * A * t_eff)

    return A, M_t


def _reaction_limited_quench(
    h0: torch.Tensor, q0: torch.Tensor, rate: float, t: float
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Closed-form reaction-limited acid-base neutralisation, both signs.

    Solves dh/dt = dq/dt = -rate*h*q (bimolecular, irreversible; h and q
    are RELATIVE concentrations, i.e. normalised to initial PAG density
    G0, matching Mack et al. 2011's h=H/G0, q=Q/G0 convention -- see
    reaction_diffusion_with_quenching's docstring for the full
    derivation and citation). h - q is conserved (= delta0 = h0 - q0),
    so the closed form only needs the MINOR species (whichever starts
    smaller, since it is driven to zero):

        minor(t) = minor0 * delta * exp(-delta*rate*t)
                   / (major0 - minor0 * exp(-delta*rate*t))

    with delta = major0 - minor0 >= 0 by construction, so the exponent
    is always <= 0 and this never overflows (the naive single-formula
    version does, for the acid-limited case, since it needs
    exp(-delta0*rate*t) with delta0 that can be very negative). The
    delta=0 (h0==q0) case is handled separately via the standard
    second-order-kinetics limit, minor(t) = minor0/(1+minor0*rate*t).
    """
    delta = h0 - q0
    acid_excess = delta >= 0
    major0 = torch.where(acid_excess, h0, q0)
    minor0 = torch.where(acid_excess, q0, h0)
    d = delta.abs()

    is_degenerate = d < 1e-12
    d_safe = torch.where(is_degenerate, torch.ones_like(d), d)
    exp_term = torch.exp(-d_safe * rate * t)
    minor_general = minor0 * d_safe * exp_term / torch.clamp(major0 - minor0 * exp_term, min=1e-30)
    minor_degenerate = minor0 / (1.0 + minor0 * rate * t)
    minor_final = torch.where(is_degenerate, minor_degenerate, minor_general)

    # Reconstruct the major species from the minor one via h - q = delta,
    # i.e. major = minor + d (using the UNSIGNED d, not the signed delta
    # -- using signed delta here was an earlier bug: in the acid_excess
    # =False branch it made q_final go negative and get clamped to 0
    # instead of correctly approaching q0-h0; caught by a standalone
    # symmetry test, see docs/claude_code_arbeitslog.md 2026-09-03).
    q_final = torch.where(acid_excess, minor_final, minor_final + d)
    h_final = torch.where(acid_excess, minor_final + d, minor_final)
    return torch.clamp(h_final, min=0.0), torch.clamp(q_final, min=0.0)


def reaction_diffusion_pde(
    acid: torch.Tensor,
    quencher: torch.Tensor | float,
    inhibitor: torch.Tensor,
    *,
    D: float,
    k: float,
    k_trap: float,
    quench_rate: float,
    t_bake: float,
    dx: float,
    pag_density: float,
    dz: float | None = None,
    D_quencher: float | None = None,
    dt: float | None = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """PEB as the coupled reaction-diffusion system of Kang et al. (NIST) 2009.

    Kang, Prabhu, Wu, Lin, Choi, Chandhok, Younkin, Yueh, Proc. SPIE 7273,
    72733U (2009), Eqs. (1)-(3), in this chain's relative concentrations
    h = H/G0, q = Q/G0 and remaining protection M = 1 - phi:

        dphi/dt = k * h * (1 - phi)                 (deprotection, k = k_P*G0)
        dh/dt   = D grad^2 h - k_trap * h * phi - (k_Q*G0) * h * q
        dq/dt   = D_Q grad^2 q - (k_Q*G0) * h * q

    Diffusion, acid trapping BY DEPROTECTED SITES, neutralisation and
    deprotection proceed concurrently. This differs from
    :func:`reaction_diffusion_with_quenching` in two ways that matter for
    patterns: acid diffusing into a base-rich or still-protected region is
    consumed there (the NIST bilayer shows a 36 -> 14 nm reduction of the
    diffusion length by the quencher), and the acid loss is not first-order
    in time but proportional to the local deprotection (the same flood data
    are fitted equally well by both laws, log Fortsetzung 38).

    Numerics: operator splitting per step ``dt`` -- exact Gaussian diffusion
    (lateral FFT blur, sigma = sqrt(2 D dt); z blur when ``dz`` is given),
    then the local reactions with an exact second-order neutralisation step
    (:func:`_reaction_limited_quench`) followed by the trapping and
    deprotection updates. ``dt`` defaults to the largest step whose
    diffusion sigma is >= 3 grid cells, capped at t_bake / 20.

    Returns (h, q, M) after the bake.
    """
    from euvsimulator.resist.exposure import gaussian_se_blur

    if pag_density is None or pag_density <= 0.0:
        raise ValueError("pag_density (G0, nm^-3) is required")
    rate_rel = float(quench_rate) * float(pag_density)  # k_Q*G0 [1/s]
    D_q = D if D_quencher is None else D_quencher
    if dt is None:
        d_max = max(D, D_q, 1e-30)
        dt = min(t_bake / 20.0, (3.0 * dx) ** 2 / (2.0 * d_max)) if d_max > 0 else t_bake / 20.0
    n_steps = max(1, int(math.ceil(t_bake / dt)))
    dt = t_bake / n_steps

    h = acid.clone()
    q = (
        torch.full_like(h, float(quencher))
        if not isinstance(quencher, torch.Tensor)
        else quencher.clone()
    )
    M = inhibitor.clone()
    three_d = dz is not None and h.ndim == 3 and h.shape[0] > 1

    def diffuse(f, Dv):
        if Dv <= 0:
            return f
        sig = (2.0 * Dv * dt) ** 0.5
        f = gaussian_se_blur(f, sigma=sig, dx=dx)
        if three_d:
            f = _gaussian_blur_z(f, sigma_nm=float(sig), dz=dz)
        return f

    for _ in range(n_steps):
        h = diffuse(h, D)
        if rate_rel > 0:
            q = diffuse(q, D_q)
            h, q = _reaction_limited_quench(h, q, rate_rel, dt)
        phi = 1.0 - M
        h = h * torch.exp(-k_trap * phi * dt)
        M = M * torch.exp(-k * h * dt)
    return h, q, M


def _gaussian_blur_z(field: torch.Tensor, sigma_nm: float, dz: float) -> torch.Tensor:
    """Gaussian blur along the first (depth) axis of an ``(N, H, W)`` tensor.

    Mirror (Neumann) boundaries: the film's top and bottom surfaces are
    no-flux boundaries for the acid, so the profile is reflected there. The
    kernel is truncated at 3σ and renormalised; for σ larger than the film
    this tends to the depth average, as it should. The column total (Σ over
    z) is conserved exactly by the face-symmetric padding (see body).
    """
    N = field.shape[0]
    s_px = sigma_nm / dz
    if s_px < 1e-12:
        return field
    r = int(3.0 * s_px + 0.5)
    if r < 1:
        return field
    x = torch.arange(-r, r + 1, dtype=field.dtype, device=field.device)
    k = torch.exp(-0.5 * (x / s_px) ** 2)
    k = k / k.sum()
    # Symmetric (face-mirror) padding along z, repeated if r >= N (thin films):
    # ghost −k = f_{k−1}, i.e. the no-flux boundary lies on the face between
    # sample 0 and its ghost. Only this padding conserves the column total
    # exactly for a symmetric kernel ("reflect" padding, which mirrors about
    # the boundary SAMPLE, leaks Σ_j f_j k(j) − f_0 Σ_k k(k)); it is the
    # finite-volume counterpart of the ADI solver's flux-form Neumann rows.
    padded = field
    left, right = r, r
    while left > 0 or right > 0:
        n_now = padded.shape[0]
        pl, pr = min(left, n_now), min(right, n_now)
        parts = []
        if pl > 0:
            parts.append(padded[:pl].flip(0))
        parts.append(padded)
        if pr > 0:
            parts.append(padded[-pr:].flip(0))
        padded = torch.cat(parts, dim=0)
        left, right = left - pl, right - pr
    # Convolve along z: (H*W, 1, N_pad) -> conv1d, in row chunks so the
    # permuted copy and the conv output never hold the whole field twice
    # (memory bound for the 61440-row LER fields, 2026-09-05; columns are
    # independent, so the result is bitwise identical to one call).
    H, W = field.shape[1], field.shape[2]
    kk = k.view(1, 1, -1)
    rows_per_chunk = max(1, (1 << 22) // max(1, W * padded.shape[0]))
    outs = []
    for y0 in range(0, H, rows_per_chunk):
        p = padded[:, y0 : y0 + rows_per_chunk]
        h = p.shape[1]
        v = p.permute(1, 2, 0).reshape(-1, 1, padded.shape[0])
        o = torch.nn.functional.conv1d(v, kk)
        outs.append(o.reshape(h, W, -1).permute(2, 0, 1)[:N])
    return torch.cat(outs, dim=1)


def reaction_diffusion_with_quenching(
    acid: torch.Tensor,
    quencher: torch.Tensor | float,
    inhibitor: torch.Tensor,
    D: float | torch.Tensor,
    k: float | torch.Tensor,
    quench_rate: float,
    t_bake: float,
    sigma_diff: float | torch.Tensor | None = None,
    dx: float = 1.0,
    pag_density: float | None = None,
    dz: float | None = None,
    acid_lifetime_s: float | None = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """PEB with explicit acid-base quenching, for the sampled-PAG/quencher path.

    Extends :func:`reaction_diffusion_analytical` with the acid-quencher
    neutralisation reaction that resist/exposure.py's
    ``sample_pag_quencher_acid`` makes physically meaningful (a
    deterministic mean-field acid concentration has no quencher-count
    counterpart to neutralise against; this function is the PEB step
    that actually consumes the ``quencher`` field that function
    produces, so it does not become a second dead/unused parameter --
    see the pipeline.py note on the dill_A/B and mack_R_max/R_min/n
    "ARCHITECTURE GAP" findings earlier this session for why that
    matters here specifically).

    Used by BOTH the mean-field (deterministic) chain and the sampled-
    molecule (exposure_stochasticity) chain, so that the deterministic
    result is the large-number limit of the stochastic one (pinned by
    tests/test_stochastic_consistency.py). Operator splitting, in order:

    1. Acid and quencher DIFFUSE over the PEB diffusion length (Gaussian
       blur of both fields with the same sigma -- Mack, Biafore & Smith
       2011, Proc. SPIE 7972, 797202, baseline D_A = D_Q; this codebase's
       peb_D / sigma_diff is used for both).
    2. The diffused fields then react via the reaction-limited closed-form
       bimolecular kinetics (same paper, Eq. 15) with rate k_Q·G0 over
       t_bake. Molecules "meet" through diffusion, not inside a grid cell:
       evaluating the reaction on the raw per-voxel sample (the order used
       before 2026-09-04) made the quencher effectively inert at this
       codebase's resolution -- a 0.17×0.17×2.5 nm³ voxel holds 0.014
       molecules, so an acid and a base only "met" when both Poisson draws
       landed in the same cell (p ≈ 0.004; measured: 0.3 % of the acid
       removed at q0/h0 = 0.25/0.16, where the mean field would remove all
       of it). For equal diffusivities and complete reaction the result is
       exactly max(blur(h0) − blur(q0), 0), since diffusion is linear and
       the reaction conserves h − q; the closed form additionally handles
       incomplete reaction near h ≈ q. The molecular discreteness survives
       as the fluctuation of the diffused fields -- the counting statistics
       of the molecules inside a diffusion volume, which is the physical
       noise source.
       (The earlier "react first" choice had been adopted because
       blur-then-react collapsed the signal to ~1e-21 -- that collapse was
       the correct mean-field consequence of the THEN-inconsistent
       parameters: acid capped at Q = 0.5 and a 0.647× dose scale put the
       mean acid below the quencher level; both are fixed, see
       docs/claude_code_arbeitslog.md "Fortsetzung 11".)
    3. The post-quenching acid drives the pseudo-first-order deprotection,
       M(t) = M0 · exp(−k · h_quenched · t_bake).

    Approximation, not a fully coupled reaction-diffusion solve: real
    quenching and deprotection proceed concurrently and the reaction can
    be diffusion-limited at short diffusion lengths (Mack et al. 2011,
    Fig. 1). With sigma ≈ 20 nm and k_Q·G0·t_bake = 180 the reaction-
    limited, post-mixing closed form is the appropriate limit.

    Parameters
    ----------
    acid : torch.Tensor
        Relative acid concentration (mean field or sampled), shape (N, H, W).
    quencher : torch.Tensor or float
        Relative quencher concentration: a tensor of the same shape (sampled
        chain) or a float for a UNIFORM loading (mean-field chain). A float
        avoids allocating and blurring a full field -- the blur of a constant
        is the constant -- which matters for the large Y-tiled stochastic
        fields (21 × 61440 × 256 doubles = 2.6 GB per copy); q = 0 skips the
        reaction entirely.
    inhibitor : torch.Tensor
        Initial normalised inhibitor concentration [0, 1]. Same shape.
    D, sigma_diff, dx : see :func:`reaction_diffusion_analytical`.
    k : float or torch.Tensor
        Deprotection rate constant [s⁻¹], same role as elsewhere in
        this codebase.
    quench_rate : float
        Bimolecular acid-base quenching rate constant k_Q [nm³/s] (Mack,
        Biafore & Smith 2011, Proc. SPIE 7972, Table I: 15 nm³/s). It acts
        on NUMBER densities, dH/dt = −k_Q·H·Q. This function works with
        RELATIVE concentrations h = H/G0, q = Q/G0, for which the same
        kinetics read dh/dt = −(k_Q·G0)·h·q -- Mack et al. 2011 state the
        baseline value explicitly as "k_Q·G0 = 3 s⁻¹". The conversion
        therefore needs *pag_density* (G0); passing k_Q unconverted (the
        behaviour before 2026-09-04) made the reaction G0⁻¹ = 5× too fast
        (docs/audit_2026-09-04_vollpruefung.md, A4).
    t_bake : float
        Bake time [s].
    pag_density : float
        Initial PAG number density G0 [nm⁻³] used to normalise *acid* and
        *quencher*. Required (no default): the rate conversion is
        meaningless without it.
    dz : float, optional
        Layer spacing [nm] of a 3D ``(N, H, W)`` input. When given, the
        diffusion is ISOTROPIC: the same Gaussian is applied along z
        (mirror/Neumann boundaries at the top and bottom surfaces -- no acid
        flux out of the film). Without it (or for 2D input) the diffusion is
        lateral only, as before 2026-09-04; that left the Beer-Lambert depth
        profile of the acid untouched while smearing it 20 nm laterally,
        which is inconsistent for a 50 nm film (measured effect on dose-to-
        size: −0.03 % at α = 1.06 µm⁻¹, −2.8 % at α = 8 µm⁻¹).

    acid_lifetime_s : float, optional
        Average acid lifetime τ [s] (Yamamoto et al. 2011 Eq. 1); ``None`` =
        no acid loss (behaviour before 2026-09-05).

    Returns
    -------
    acid_final : torch.Tensor
        Post-quenching acid concentration. Same shape as *acid*.
    quencher_final : torch.Tensor or float
        Post-quenching quencher concentration (same shape as *acid*), or the
        float 0.0 when no base was loaded.
    inhibitor_final : torch.Tensor
        Inhibitor concentration after deprotection. Same shape.
    """
    if pag_density is None or pag_density <= 0.0:
        raise ValueError(
            "pag_density (G0, nm^-3) is required to convert k_Q [nm^3/s] to the "
            "relative-concentration rate k_Q*G0 [1/s]; got "
            f"{pag_density!r}"
        )
    rate_rel = float(quench_rate) * float(pag_density)  # k_Q·G0 [1/s]

    # First-order acid loss (lifetime τ): closed forms below run on the
    # effective time τ(1 − e^{−t/τ}) -- exact for the deprotection and the
    # D·t diffusion length; for the neutralisation it is the same
    # approximation (acid and base react only while the acid is alive).
    t_eff = effective_reaction_time(t_bake, acid_lifetime_s)

    blur_sigma = None
    if sigma_diff is not None and sigma_diff > 0:
        blur_sigma = sigma_diff
    elif D > 0 and t_eff > 0:
        sigma_val = (2.0 * D * t_eff) ** 0.5
        if sigma_val > 0.1:
            blur_sigma = sigma_val

    # 1. Diffuse both species (see docstring for why this comes first).
    h = acid
    if blur_sigma is not None:
        from euvsimulator.resist.exposure import gaussian_se_blur

        h = gaussian_se_blur(h, sigma=blur_sigma, dx=dx)
        if dz is not None and h.ndim == 3 and h.shape[0] > 1:
            h = _gaussian_blur_z(h, sigma_nm=float(blur_sigma), dz=dz)

    uniform_q = not isinstance(quencher, torch.Tensor)
    if uniform_q and float(quencher) == 0.0:
        # No base loaded: the neutralisation is a no-op; do not allocate.
        A_quenched, Q_final = h, 0.0
    else:
        if uniform_q:
            q = torch.full_like(h, float(quencher))  # blur of a constant == constant
        else:
            q = quencher
            if blur_sigma is not None:
                q = gaussian_se_blur(q, sigma=blur_sigma, dx=dx)
                if dz is not None and q.ndim == 3 and q.shape[0] > 1:
                    q = _gaussian_blur_z(q, sigma_nm=float(blur_sigma), dz=dz)
        # 2. React (reaction-limited closed form on the mixed fields).
        A_quenched, Q_final = _reaction_limited_quench(h, q, rate_rel, t_eff)

    # 3. Deprotect (effective time, see above).
    M_t = inhibitor * torch.exp(-k * A_quenched * t_eff)

    return A_quenched, Q_final, M_t


# ──────────────────────────────────────────────
# Deprotection front propagation (finite difference)
# ──────────────────────────────────────────────


def deprotection_fd(
    inhibitor: torch.Tensor,
    acid: torch.Tensor,
    k: float | torch.Tensor = 0.1,
    dt: float = 1.0,
    n_steps: int = 10,
) -> torch.Tensor:
    """Finite-difference deprotection (no diffusion).

    Integrates::

        ∂M/∂t = −k · [H⁺] · M

    with a simple forward Euler scheme.

    Parameters
    ----------
    inhibitor : torch.Tensor
        Initial normalised inhibitor concentration.  Shape ``(H, W)``.
    acid : torch.Tensor
        Photoacid concentration.  Shape ``(H, W)``.
    k : float or torch.Tensor
        Rate constant [s⁻¹].  Default 0.1.
    dt : float
        Time step [s].  Default 1.0.
    n_steps : int
        Number of time steps.  Default 10.

    Returns
    -------
    M : torch.Tensor
        Inhibitor after *n_steps* × *dt* seconds.  Same shape as input.
    """
    M = inhibitor.clone()
    for _ in range(n_steps):
        M = M - k * acid * M * dt
        M = torch.clamp(M, 0.0, 1.0)
    return M


# ──────────────────────────────────────────────
# Analytical deprotection
# ──────────────────────────────────────────────


def deprotection_analytical(
    inhibitor: torch.Tensor,
    acid: torch.Tensor,
    k: float | torch.Tensor = 0.1,
    t: float = 10.0,
) -> torch.Tensor:
    """Analytical deprotection: M(t) = M₀ · exp(−k · [H⁺] · t).

    Exact solution of the first-order deprotection kinetics when the
    acid concentration is constant (no depletion).

    Parameters
    ----------
    inhibitor : torch.Tensor
        Initial normalised inhibitor [0, 1].  Shape ``(H, W)``.
    acid : torch.Tensor
        Photoacid concentration.  Shape ``(H, W)``.
    k : float or torch.Tensor
        Rate constant [s⁻¹].  Default 0.1.
    t : float
        Bake time [s].  Default 10.0.

    Returns
    -------
    M_final : torch.Tensor
        Inhibitor after time *t*.
    """
    return inhibitor * torch.exp(-k * acid * t)
