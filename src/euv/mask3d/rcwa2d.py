"""Rigorous Coupled-Wave Analysis (RCWA) — 2D grating, PyTorch.

Fourier Modal Method (FMM) for crossed gratings (2D-periodic) with
numerically stable scattering-matrix (S-matrix) cascade.

Theory
------
For a 2D grating periodic in *x* and *y*, the fields are expanded
in 2D Fourier series.  Each homogeneous-in-*z* layer satisfies the
2D eigenvalue problem::

    A W = W q²   where A = Kx² + Ky² − ε

with :math:`Kx = \\operatorname{diag}(k_{xmn}/k₀)` and
:math:`Ky = \\operatorname{diag}(k_{ymn}/k₀)` being the normalised
wavevector matrices, and *ε* the block-Toeplitz permittivity matrix.

The S-matrix cascade is the same Redheffer-star product used in the
1D solver, extended to :math:`(2M_x+1)(2M_y+1)` modes.

References:
----------
M. G. Moharam et al., J. Opt. Soc. Am. A 12(5), 1077–1086 (1995).
L. Li, J. Opt. Soc. Am. A 13(9), 1870–1876 (1996).

Note:
----
The 2D solver is computationally expensive.  A 21×21 harmonic set
produces matrices of size 441 × 441 — the eigenvalue decomposition
scales as O((Mx·My)³).  Start with 5×5 or 7×7 orders and increase
only as needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch

# ──────────────────────────────────────────────
# 2D Configuration
# ──────────────────────────────────────────────


@dataclass
class RCWA2DConfig:
    """Configuration for a 2D RCWA simulation.

    Parameters
    ----------
    wavelength : float
        Free-space wavelength [m] (default: 13.5e-9).
    n_orders_x : int
        Fourier orders in x (odd, default: 7).
    n_orders_y : int
        Fourier orders in y (odd, default: 7).
    theta : float
        Polar angle of incidence [deg] (default: 6.0).
    phi : float
        Azimuthal angle [deg] (default: 0.0).
    device : str
        PyTorch device (default: ``"cpu"``).
    """

    wavelength: float = 13.5e-9
    n_orders_x: int = 7
    n_orders_y: int = 7
    theta: float = 6.0
    phi: float = 0.0
    device: str = "cpu"

    def __post_init__(self) -> None:
        if self.n_orders_x % 2 == 0:
            raise ValueError(f"n_orders_x must be odd, got {self.n_orders_x}")
        if self.n_orders_y % 2 == 0:
            raise ValueError(f"n_orders_y must be odd, got {self.n_orders_y}")

    @property
    def n_modes(self) -> int:
        """Total number of Fourier modes."""
        return self.n_orders_x * self.n_orders_y


# ──────────────────────────────────────────────
# 2D Permittivity Fourier coefficients
# ──────────────────────────────────────────────


def permittivity_toeplitz_2d(
    eps_profile: torch.Tensor,
    n_orders_x: int,
    n_orders_y: int,
) -> torch.Tensor:
    """Build the block-Toeplitz permittivity matrix for a 2D grating.

    The 2D permittivity profile :math:`\\varepsilon(x,y)` is sampled on
    an :math:`(N_x, N_y)` grid.  A 2D FFT gives the Fourier coefficients
    :math:`\\varepsilon_{mn}`, from which the block-Toeplitz matrix is
    assembled.

    Parameters
    ----------
    eps_profile : (Nx, Ny) complex128
        2D sampled permittivity over one period.
    n_orders_x, n_orders_y : int
        Number of Fourier orders in each direction (odd).

    Returns
    -------
    E : (P, P) complex128
        Block-Toeplitz matrix where P = n_orders_x * n_orders_y.
    """
    Px, Py = n_orders_x, n_orders_y
    P = Px * Py

    Nx, Ny = eps_profile.shape

    # 2D FFT → Fourier coefficients
    eps_fft = torch.fft.fft2(eps_profile) / (Nx * Ny)
    eps_fft = torch.fft.fftshift(eps_fft)

    cx, cy = Nx // 2, Ny // 2

    # For a 2D grating, the Toeplitz structure is:
    # The Fourier coefficient at (p,q) in the matrix is ε at
    # (m_i - m_j, n_i - n_j) where (m,n) are the harmonic indices.
    # We build this as a block matrix with Py × Py blocks,
    # each of size Px × Px.

    # Create index arrays for all modes: (m_idx, n_idx) pairs
    mx_half = Px // 2
    my_half = Py // 2
    m_vals = torch.arange(-mx_half, mx_half + 1, device=eps_profile.device)
    n_vals = torch.arange(-my_half, my_half + 1, device=eps_profile.device)

    # Grid of all (m, n) pairs, flattened
    mg, ng = torch.meshgrid(m_vals, n_vals, indexing="ij")
    m_all = mg.reshape(-1)  # (P,)
    n_all = ng.reshape(-1)

    # Difference indices for Toeplitz: E[i,j] = ε(m_i - m_j, n_i - n_j)
    dm = m_all.view(-1, 1) - m_all.view(1, -1)  # (P, P)
    dn = n_all.view(-1, 1) - n_all.view(1, -1)

    # Map to FFT array indices
    idx = (cx + dm.to(torch.long)) % Nx
    idy = (cy + dn.to(torch.long)) % Ny

    # Gather Fourier coefficients
    E = eps_fft[idx, idy]
    return E.to(torch.complex128)


# ──────────────────────────────────────────────
# 2D RCWA solver
# ──────────────────────────────────────────────


class RCWA2D:
    """2D RCWA solver with S-matrix cascade.

    Solves the 2D Fourier Modal Method for crossed gratings periodic
    in both *x* and *y*.

    Parameters
    ----------
    cfg : RCWA2DConfig
    """

    def __init__(self, cfg: RCWA2DConfig) -> None:
        self.cfg = cfg
        self.device = torch.device(cfg.device)
        self.Px = cfg.n_orders_x
        self.Py = cfg.n_orders_y
        self.P = cfg.n_modes

        # Harmonic indices
        mx_half = self.Px // 2
        my_half = self.Py // 2
        self.m_vals = torch.arange(-mx_half, mx_half + 1, dtype=torch.float64, device=self.device)
        self.n_vals = torch.arange(-my_half, my_half + 1, dtype=torch.float64, device=self.device)

    # ── Public API ─────────────────────────────

    def solve(
        self,
        eps_profile_2d: torch.Tensor,
        thicknesses: torch.Tensor,
        period_x: float,
        period_y: float,
        n_incident: Optional[torch.Tensor] = None,
        n_substrate: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Run the 2D RCWA simulation.

        Parameters
        ----------
        eps_profile_2d : (Nx, Ny) complex128
            2D sampled permittivity over one period.
        thicknesses : (Nlayers,) float64 [m]
            Layer thicknesses.
        period_x, period_y : float [m]
            Grating periods.
        n_incident : (2,) complex128, optional
            Refractive index of incident medium.
        n_substrate : (2,) complex128, optional
            Refractive index of substrate.

        Returns
        -------
        orders : (P,) complex128
            Complex reflected order amplitudes (flattened 2D).
        """
        if n_incident is None:
            n_incident = torch.tensor([1.0 + 0.0j, 1.0 + 0.0j], dtype=torch.complex128)
        if n_substrate is None:
            n_substrate = n_incident.clone()

        n_i = n_incident.to(torch.complex128)
        n_s = n_substrate.to(torch.complex128)
        k0 = 2.0 * math.pi / self.cfg.wavelength
        theta = math.radians(self.cfg.theta)
        phi = math.radians(self.cfg.phi)

        # Wavevector components of the incident plane wave
        k_inc_x = k0 * n_i[0] * math.sin(theta) * math.cos(phi)
        k_inc_y = k0 * n_i[0] * math.sin(theta) * math.sin(phi)

        # Flattened harmonic indices
        mg, ng = torch.meshgrid(self.m_vals, self.n_vals, indexing="ij")
        m_all = mg.reshape(-1)  # (P,)
        n_all = ng.reshape(-1)

        # Rayleigh wavevectors
        k_xmn = k_inc_x - m_all * (2.0 * math.pi / period_x)
        k_ymn = k_inc_y - n_all * (2.0 * math.pi / period_y)

        Kx = torch.diag(k_xmn / k0).to(torch.complex128)
        Ky = torch.diag(k_ymn / k0).to(torch.complex128)

        # Permittivity Toeplitz matrix
        E = permittivity_toeplitz_2d(eps_profile_2d, self.Px, self.Py)

        # Eigenvalue problem: A = Kx² + Ky² - E  (scalar 2D)
        Kx2 = Kx @ Kx
        Ky2 = Ky @ Ky
        A = Kx2 + Ky2 - E

        eig_vals, W = torch.linalg.eig(A)
        q = torch.sqrt(eig_vals)
        q = torch.where(q.imag < 0, -q, q)  # Im(q) >= 0
        V = W @ torch.diag(q)  # modal admittance

        # Rayleigh admittances
        kz_inc_sq = (n_i[0] * k0) ** 2 - k_xmn**2 - k_ymn**2
        kz_sub_sq = (n_s[0] * k0) ** 2 - k_xmn**2 - k_ymn**2
        kz_inc = torch.sqrt(kz_inc_sq + 0j)
        kz_sub = torch.sqrt(kz_sub_sq + 0j)
        kz_inc = torch.where(kz_inc.imag < 0, -kz_inc, kz_inc)
        kz_sub = torch.where(kz_sub.imag < 0, -kz_sub, kz_sub)

        Y_inc = torch.diag(kz_inc / k0).to(torch.complex128)
        Y_sub = torch.diag(kz_sub / k0).to(torch.complex128)

        # Build and cascade S-matrices
        P = self.P
        I = torch.eye(P, dtype=torch.complex128, device=self.device)

        # Top interface: incident → eigenmode
        YW = Y_inc @ W
        A_iface = V + YW
        B_iface = YW - V
        A_inv = torch.linalg.inv(A_iface)

        S_top = torch.zeros(2, 2, P, P, dtype=torch.complex128, device=self.device)
        S_top[0, 0] = 2.0 * W @ A_inv @ Y_inc - I
        S_top[0, 1] = 2.0 * W @ A_inv @ V
        S_top[1, 0] = 2.0 * A_inv @ Y_inc
        S_top[1, 1] = -A_inv @ B_iface

        # Layer propagation
        S_layer = torch.zeros(2, 2, P, P, dtype=torch.complex128, device=self.device)
        S_layer[0, 1] = I
        S_layer[1, 0] = I

        for idx in range(thicknesses.shape[0]):
            d = thicknesses[idx]
            phase = torch.exp(1j * k0 * q * d)
            X = torch.diag(phase)

            S_this = torch.zeros(2, 2, P, P, dtype=torch.complex128, device=self.device)
            S_this[0, 1] = X
            S_this[1, 0] = X

            S_layer = self._redheffer_star(S_layer, S_this)

        # Bottom interface: eigenmode → substrate
        YW_sub = Y_sub @ W
        A_sub = V + YW_sub
        B_sub = YW_sub - V
        A_sub_inv = torch.linalg.inv(A_sub)

        S_bot = torch.zeros(2, 2, P, P, dtype=torch.complex128, device=self.device)
        S_bot[0, 0] = -A_sub_inv @ B_sub
        S_bot[0, 1] = 2.0 * A_sub_inv @ Y_sub
        S_bot[1, 0] = 2.0 * W @ A_sub_inv @ V
        S_bot[1, 1] = 2.0 * W @ A_sub_inv @ Y_sub - I

        # Cascade: S_total = S_top ⨂ S_layer ⨂ S_bot
        S_total = self._redheffer_star(self._redheffer_star(S_top, S_layer), S_bot)

        # Incident: (m=0, n=0) only
        inc = torch.zeros(P, dtype=torch.complex128, device=self.device)
        inc[P // 2] = 1.0 + 0.0j

        reflected = S_total[0, 0] @ inc
        return reflected

    def diffraction_efficiency(self, orders: torch.Tensor) -> Dict[Tuple[int, int], float]:
        """Diffraction efficiencies per 2D order.

        Parameters
        ----------
        orders : (P,) complex128
            Reflected order amplitudes from ``solve()``.

        Returns
        -------
        eff : dict {(m, n): float}
        """
        mg, ng = torch.meshgrid(self.m_vals, self.n_vals, indexing="ij")
        m_all = mg.reshape(-1)
        n_all = ng.reshape(-1)

        eff: Dict[Tuple[int, int], float] = {}
        for idx in range(self.P):
            m_val = int(m_all[idx].item())
            n_val = int(n_all[idx].item())
            amp = orders[idx]
            eff[(m_val, n_val)] = float((amp * amp.conj()).real.item())
        return eff

    # ── S-matrix operations ────────────────────

    @staticmethod
    def _redheffer_star(S_a: torch.Tensor, S_b: torch.Tensor) -> torch.Tensor:
        """Redheffer star product for matrix S-matrices."""
        P = S_a.shape[-1]
        I = torch.eye(P, dtype=torch.complex128, device=S_a.device)

        A11, A12, A21, A22 = S_a[0, 0], S_a[0, 1], S_a[1, 0], S_a[1, 1]
        B11, B12, B21, B22 = S_b[0, 0], S_b[0, 1], S_b[1, 0], S_b[1, 1]

        D1 = torch.linalg.inv(I - A22 @ B11)
        D2 = torch.linalg.inv(I - B11 @ A22)

        S = torch.zeros_like(S_a)
        S[0, 0] = A11 + A12 @ D1 @ B11 @ A21
        S[0, 1] = A12 @ D1 @ B12
        S[1, 0] = B21 @ D2 @ A21
        S[1, 1] = B22 + B21 @ D2 @ A22 @ B12
        return S

    # ── Convergence driver ─────────────────────

    def solve_with_convergence(
        self,
        eps_profile_2d: torch.Tensor,
        thicknesses: torch.Tensor,
        period_x: float,
        period_y: float,
        target_rel: float = 1e-3,
        max_orders: int = 15,
        n_incident: Optional[torch.Tensor] = None,
        n_substrate: Optional[torch.Tensor] = None,
    ) -> Tuple[Dict[Tuple[int, int], float], int]:
        """Increase orders until zeroth-order (0,0) stabilises.

        Parameters
        ----------
        eps_profile_2d : (Nx, Ny) complex128
        thicknesses : (Nlayers,) float64 [m]
        period_x, period_y : float [m]
        target_rel : float
            Relative convergence criterion.  Default 1e-3.
        max_orders : int
            Maximum orders in each direction.  Default 15.

        Returns
        -------
        efficiencies, n_orders_used
        """
        prev_r00: Optional[float] = None
        eff: Dict[Tuple[int, int], float] = {}

        for M in range(5, max_orders + 1, 2):
            cfg = RCWA2DConfig(
                wavelength=self.cfg.wavelength,
                n_orders_x=M,
                n_orders_y=M,
                theta=self.cfg.theta,
                phi=self.cfg.phi,
                device=self.cfg.device,
            )
            solver = RCWA2D(cfg)
            orders = solver.solve(
                eps_profile_2d,
                thicknesses,
                period_x,
                period_y,
                n_incident=n_incident,
                n_substrate=n_substrate,
            )
            eff = solver.diffraction_efficiency(orders)
            r00 = eff.get((0, 0), 0.0)

            if prev_r00 is not None and prev_r00 > 1e-12:
                rel_change = abs(r00 - prev_r00) / prev_r00
                if rel_change < target_rel:
                    return eff, M
            prev_r00 = r00

        return eff, max_orders


# ──────────────────────────────────────────────
# Convenience: rectangular island / contact hole
# ──────────────────────────────────────────────


def rectangular_island_profile(
    period_x: float,
    period_y: float,
    width_x: float,
    width_y: float,
    eps_island: complex,
    eps_background: complex,
    n_samples_x: int = 256,
    n_samples_y: int = 256,
    device: str = "cpu",
) -> torch.Tensor:
    """Create a 2D permittivity profile for a rectangular island.

    Parameters
    ----------
    period_x, period_y : float [m]
        Period in x and y.
    width_x, width_y : float [m]
        Width of the rectangular island.
    eps_island : complex
        Island permittivity.
    eps_background : complex
        Background permittivity.
    n_samples_x, n_samples_y : int
        Spatial samples.

    Returns
    -------
    eps_profile : (n_samples_x, n_samples_y) complex128
    """
    x = torch.linspace(0, period_x, n_samples_x, device=device)
    y = torch.linspace(0, period_y, n_samples_y, device=device)
    X, Y = torch.meshgrid(x, y, indexing="ij")

    # Island centred in the period
    cx, cy = period_x / 2.0, period_y / 2.0
    hx, hy = width_x / 2.0, width_y / 2.0
    mask = (X >= cx - hx) & (X <= cx + hx) & (Y >= cy - hy) & (Y <= cy + hy)

    eps = torch.full(
        (n_samples_x, n_samples_y), eps_background, dtype=torch.complex128, device=device
    )
    eps[mask] = complex(eps_island)
    return eps


def contact_hole_profile(
    period_x: float,
    period_y: float,
    radius: float,
    eps_hole: complex,
    eps_background: complex,
    n_samples_x: int = 256,
    n_samples_y: int = 256,
    device: str = "cpu",
) -> torch.Tensor:
    """Create a 2D permittivity profile for a circular contact hole.

    Parameters
    ----------
    period_x, period_y : float [m]
    radius : float [m]
        Contact hole radius.
    eps_hole : complex
        Hole permittivity.
    eps_background : complex
        Background (absorber) permittivity.

    Returns
    -------
    eps_profile : (n_samples_x, n_samples_y) complex128
    """
    x = torch.linspace(0, period_x, n_samples_x, device=device)
    y = torch.linspace(0, period_y, n_samples_y, device=device)
    X, Y = torch.meshgrid(x, y, indexing="ij")

    cx, cy = period_x / 2.0, period_y / 2.0
    r_sq = (X - cx) ** 2 + (Y - cy) ** 2
    mask = r_sq <= radius**2

    eps = torch.full(
        (n_samples_x, n_samples_y), eps_background, dtype=torch.complex128, device=device
    )
    eps[mask] = complex(eps_hole)
    return eps
