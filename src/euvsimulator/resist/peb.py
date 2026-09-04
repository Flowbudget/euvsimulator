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

    Returns
    -------
    T : torch.Tensor
        Tridiagonal matrix of shape (n, n).
    """
    T = torch.zeros(n, n, device=device, dtype=dtype)
    T[0, 0] = diag_boundary
    T[0, 1] = off_diag
    for i in range(1, n - 1):
        T[i, i - 1] = off_diag
        T[i, i] = diag
        T[i, i + 1] = off_diag
    T[n - 1, n - 2] = off_diag
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
        lap[0, :] = 2.0 * (A[1, :] - A[0, :])
        lap[H - 1, :] = 2.0 * (A[H - 2, :] - A[H - 1, :])
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
        lap[:, 0] = 2.0 * (A[:, 1] - A[:, 0])
        lap[:, W - 1] = 2.0 * (A[:, W - 2] - A[:, W - 1])
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
        main_b = 1.0 + alpha  # Neumann: zero-flux at boundaries
    elif boundary == "dirichlet":
        main_b = main_diag  # Dirichlet: standard interior diag
    else:
        raise ValueError(f"Unknown boundary condition: '{boundary}'")

    T_x = _build_tridiagonal_matrix(W, main_diag, off_diag, main_b, device, dtype)
    T_y = _build_tridiagonal_matrix(H, main_diag, off_diag, main_b, device, dtype)

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


def reaction_diffusion_analytical(
    acid: torch.Tensor,
    inhibitor: torch.Tensor,
    D: float | torch.Tensor = 0.0,
    k: float | torch.Tensor = 0.1,
    t_bake: float = 10.0,
    sigma_diff: float | torch.Tensor | None = None,
    dx: float = 1.0,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Analytical PEB model — Gaussian diffusion + first-order deprotection.

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

    if sigma_diff is not None and sigma_diff > 0:
        from euvsimulator.resist.exposure import gaussian_se_blur

        A = gaussian_se_blur(A, sigma=sigma_diff, dx=dx)
    elif D > 0 and t_bake > 0:
        sigma_val = (2.0 * D * t_bake) ** 0.5
        if sigma_val > 0.1:
            from euvsimulator.resist.exposure import gaussian_se_blur

            A = gaussian_se_blur(A, sigma=sigma_val, dx=dx)

    # Deprotection: M(t) = M₀ · exp(−k · A · t)
    M_t = inhibitor * torch.exp(-k * A * t_bake)

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


def reaction_diffusion_with_quenching(
    acid: torch.Tensor,
    quencher: torch.Tensor,
    inhibitor: torch.Tensor,
    D: float | torch.Tensor,
    k: float | torch.Tensor,
    quench_rate: float,
    t_bake: float,
    sigma_diff: float | torch.Tensor | None = None,
    dx: float = 1.0,
    pag_density: float | None = None,
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

    Model, in order:

    1. The sampled per-voxel acid/quencher fields react via the
       reaction-limited closed-form kinetics (Mack, Biafore & Smith
       2011, "Stochastic Acid-Base Quenching in Chemically Amplified
       Photoresists," Proc. SPIE 7972, 797202, Eq. 15 -- free via
       lithoguru.com; see pipeline.py's acid_base_quench_rate_nm3_per_s
       comment for the rate constant's citation) BEFORE any diffusion.
       "Reaction-limited" specifically means the neutralisation is fast
       and local relative to the PEB diffusion length -- that is what
       justifies treating it as a well-mixed bimolecular reaction at
       the voxel scale in the first place, so it must act on the
       per-voxel sampled counts, not on an already spatially-averaged
       field (applying it after diffusion was tried first and found to
       destroy essentially all of the sampled molecular discreteness --
       see the comment at this function's call site below for the
       numerical finding that caught this).
    2. The post-quenching acid/quencher fields then diffuse during the
       rest of PEB (same Gaussian-blur approximation as
       :func:`reaction_diffusion_analytical`, applied to BOTH fields
       with the same sigma -- Mack et al. 2011's own baseline uses
       equal acid/base diffusivities, DA=DQ=1 nm²/s; this codebase's
       own peb_D/sigma_diff, a real EUV-cited value in its own right
       (Lavery et al. 2006 / Anderson et al. 2009, see pipeline.py
       peb_D comment), is reused for both here rather than introducing
       a second, less-representative diffusivity).
    3. That diffused, post-quenching acid level drives the SAME
       pseudo-first-order deprotection kinetics as the rest of this
       codebase, M(t) = M0 * exp(-k * h_quenched * t_bake).

    This is an approximation, not a fully coupled solve (real physics
    has quenching and deprotection proceeding concurrently, with
    quenching itself diffusion-limited at short acid/quencher diffusion
    lengths per Mack et al. 2011's own Fig. 1) -- documented as such,
    not presented as more rigorous than it is.

    Parameters
    ----------
    acid, quencher : torch.Tensor
        Sampled relative concentrations (same shape), e.g. from
        ``sample_pag_quencher_acid``.
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

    Returns
    -------
    acid_final : torch.Tensor
        Post-quenching acid concentration. Same shape as *acid*.
    quencher_final : torch.Tensor
        Post-quenching quencher concentration. Same shape as *acid*.
    inhibitor_final : torch.Tensor
        Inhibitor concentration after deprotection. Same shape.
    """
    # Reaction BEFORE diffusion, not after: "reaction-limited" kinetics
    # means the neutralisation is fast/local relative to the PEB
    # diffusion length (that is what justifies the well-mixed bimolecular
    # ODE at the voxel scale in the first place, see _reaction_limited_
    # quench's docstring). Blurring the sampled per-voxel acid/quencher
    # counts FIRST (over the full ~20nm PEB diffusion length, i.e. an
    # ensemble average across ~100+ independent voxels) and only THEN
    # applying the reaction was found to destroy essentially all of the
    # sampled molecular discreteness: since quench_rate*t_bake is large
    # enough that the reaction goes to completion for any excess down to
    # ~1e-3 (relative units), applying it to an already-averaged field
    # just reproduces the (near-zero, since PAG/quencher densities from
    # Mack et al. 2011 Table I put the mean acid signal close to the
    # quencher baseline) ENSEMBLE MEAN outcome, not a per-voxel-noisy
    # one -- verified numerically: blur-then-react gave a post-quench
    # acid field with mean/std ~1e-21 (fully degenerate, explaining the
    # exposure_stochasticity LER=LWR=0.0 finding in
    # docs/claude_code_arbeitslog.md 2026-09-03), while react-then-blur
    # on the same synthetic input gives mean=0.029, std=7.2e-4 -- a real,
    # non-degenerate signal. React first (local, per-voxel, preserving
    # the sampled discreteness), then diffuse the reacted result
    # (representing the post-neutralisation acid profile spreading
    # during the remainder of the bake).
    if pag_density is None or pag_density <= 0.0:
        raise ValueError(
            "pag_density (G0, nm^-3) is required to convert k_Q [nm^3/s] to the "
            "relative-concentration rate k_Q*G0 [1/s]; got "
            f"{pag_density!r}"
        )
    rate_rel = float(quench_rate) * float(pag_density)  # k_Q·G0 [1/s]
    A_quenched, Q_final = _reaction_limited_quench(acid, quencher, rate_rel, t_bake)

    blur_sigma = None
    if sigma_diff is not None and sigma_diff > 0:
        blur_sigma = sigma_diff
    elif D > 0 and t_bake > 0:
        sigma_val = (2.0 * D * t_bake) ** 0.5
        if sigma_val > 0.1:
            blur_sigma = sigma_val

    if blur_sigma is not None:
        from euvsimulator.resist.exposure import gaussian_se_blur

        A_quenched = gaussian_se_blur(A_quenched, sigma=blur_sigma, dx=dx)
        Q_final = gaussian_se_blur(Q_final, sigma=blur_sigma, dx=dx)

    M_t = inhibitor * torch.exp(-k * A_quenched * t_bake)

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
