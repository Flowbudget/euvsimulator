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
        from euv.resist.exposure import gaussian_se_blur

        A = gaussian_se_blur(A, sigma=sigma_diff, dx=dx)
    elif D > 0 and t_bake > 0:
        sigma_val = (2.0 * D * t_bake) ** 0.5
        if sigma_val > 0.1:
            from euv.resist.exposure import gaussian_se_blur

            A = gaussian_se_blur(A, sigma=sigma_val, dx=dx)

    # Deprotection: M(t) = M₀ · exp(−k · A · t)
    M_t = inhibitor * torch.exp(-k * A * t_bake)

    return A, M_t


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
