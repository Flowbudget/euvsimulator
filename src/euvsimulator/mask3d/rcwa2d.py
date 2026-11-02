"""Rigorous Coupled-Wave Analysis (RCWA) — 2D grating, PyTorch.

Fourier Modal Method (FMM) for crossed gratings (2D-periodic) with
numerically stable scattering-matrix (S-matrix) cascade.

Theory
------
For a 2D grating periodic in *x* and *y*, the fields are expanded
in 2D Fourier series.  Each homogeneous-in-*z* layer satisfies the
2D eigenvalue problem::

    A W = W q²   where A = ε − Kx² − Ky²

This is a *scalar* formulation (one field component, no polarisation
coupling).  It is exact for structures that are invariant in *y* at
φ = 0, where it reduces to the 1D TE solver, and an approximation
otherwise.  Before 2026-09-25 the operator read ``Kx² + Ky² − ε``; with
the propagator ``exp(i k₀ q d)`` that turned every propagating mode into
an evanescent one, so even a vacuum layer reflected 100 %.

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
import warnings
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch

from euvsimulator.mask3d.geometry import line_fill_fraction

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
        # float32 thicknesses cost ~1e-6 relative accuracy in R (phase k0 q d)
        thicknesses = thicknesses.to(torch.float64)
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

        # Eigenvalue problem (scalar 2D, same convention as the 1D TE solver):
        # A = E - Kx² - Ky², q = sqrt(eig(A)) is kz/k0 of each mode.
        Kx2 = Kx @ Kx
        Ky2 = Ky @ Ky
        A = E - Kx2 - Ky2

        eig_vals, W = torch.linalg.eig(A)
        q = torch.sqrt(eig_vals)
        # Branch selection as in the 1D solver: Im(q) > 0 (decay), and for a
        # numerically real q (|Im| < 1e-10) Re(q) > 0 (forward propagation).
        # The former rule `Im(q) < 0 -> flip` sent degenerate propagating modes
        # backwards whenever round-off gave them Im(q) ~ -1e-17 (normal
        # incidence): a lossless grating on a mirror returned sum R = 0.99945.
        flip = torch.where(q.imag.abs() < 1e-10, q.real < 0, q.imag < 0)
        q = torch.where(flip, -q, q)
        V = W @ torch.diag(q)  # modal admittance

        # Rayleigh admittances
        kz_inc_sq = (n_i[0] * k0) ** 2 - k_xmn**2 - k_ymn**2
        kz_sub_sq = (n_s[0] * k0) ** 2 - k_xmn**2 - k_ymn**2
        kz_inc = torch.sqrt(kz_inc_sq + 0j)
        kz_sub = torch.sqrt(kz_sub_sq + 0j)
        kz_inc = torch.where(kz_inc.imag < 0, -kz_inc, kz_inc)
        kz_sub = torch.where(kz_sub.imag < 0, -kz_sub, kz_sub)
        # Power carried by each reflected order relative to the incident wave;
        # used by diffraction_efficiency (0 for evanescent orders).
        self._power_factor = (kz_inc.real / kz_inc[self.P // 2].real).detach()

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
        inc[P // 2] = 1.0

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
            Reflected power per order relative to the incident power,
            ``|r_mn|² · Re(kz_mn)/kz_00`` in the incident medium; evanescent
            orders carry no power and give 0.  Uses the order geometry of the
            most recent :meth:`solve` call.
        """
        if hasattr(self, "_power_factor"):
            factor = self._power_factor
        else:
            warnings.warn(
                "diffraction_efficiency() on a solver that has not run solve(): "
                "returning |r_mn|^2, which is the power only for (0, 0)",
                stacklevel=2,
            )
            factor = torch.ones(self.P, dtype=torch.float64, device=self.device)
        mg, ng = torch.meshgrid(self.m_vals, self.n_vals, indexing="ij")
        m_all = mg.reshape(-1)
        n_all = ng.reshape(-1)

        eff: Dict[Tuple[int, int], float] = {}
        for idx in range(self.P):
            m_val = int(m_all[idx].item())
            n_val = int(n_all[idx].item())
            amp = orders[idx]
            power = (amp * amp.conj()).real * factor[idx]
            eff[(m_val, n_val)] = float(power.item())
        return eff

    # ── S-matrix operations ────────────────────

    @staticmethod
    def _redheffer_star(S_a: torch.Tensor, S_b: torch.Tensor) -> torch.Tensor:
        """Redheffer star product for matrix S-matrices."""
        P = S_a.shape[-1]
        I = torch.eye(P, dtype=torch.complex128, device=S_a.device)

        A11, A12, A21, A22 = S_a[0, 0], S_a[0, 1], S_a[1, 0], S_a[1, 1]
        B11, B12, B21, B22 = S_b[0, 0], S_b[0, 1], S_b[1, 0], S_b[1, 1]

        # Resolvent ordering matters for matrix blocks (push-through
        # identity); same correction as rcwa_torch.RCWA1D._redheffer_star_matrix
        # (2026-09-04) -- see its docstring.
        D_b = torch.linalg.inv(I - B11 @ A22)  # terms starting with B11
        D_a = torch.linalg.inv(I - A22 @ B11)  # terms starting with A22

        S = torch.zeros_like(S_a)
        S[0, 0] = A11 + A12 @ D_b @ B11 @ A21
        S[0, 1] = A12 @ D_b @ B12
        S[1, 0] = B21 @ D_a @ A21
        S[1, 1] = B22 + B21 @ D_a @ A22 @ B12
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
        last_m = 0

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
            last_m = M

        # Not converged: report the order count actually used (the former
        # `return eff, max_orders` also claimed max_orders when the step
        # never reached it) and say so.
        warnings.warn(
            f"RCWA did not converge to target_rel={target_rel} within {last_m} orders "
            "((0, 0) order still changing); returning the last result",
            stacklevel=2,
        )
        return eff, last_m


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

    The island is centred at ``(period_x / 2, period_y / 2)``. Sample
    (i, j) sits at ``(i * period_x / n_samples_x, j * period_y / n_samples_y)``,
    where :func:`permittivity_toeplitz_2d` reads it, and a sample whose cell
    an edge cuts holds the area-weighted mixture (the product of the two
    :func:`~euvsimulator.mask3d.geometry.line_fill_fraction` profiles), so
    the island area and centre are exact for every sample count. Until
    2026-10 the closed intervals ``linspace(0, period, n)`` were sampled.

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
    # Island centred in the period; covered fraction of each sample cell
    fx = line_fill_fraction(n_samples_x, width_x / period_x, device=device)
    fy = line_fill_fraction(n_samples_y, width_y / period_y, device=device)
    frac = fx[:, None] * fy[None, :]
    return complex(eps_background) * (1.0 - frac) + complex(eps_island) * frac


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

    The hole is centred at ``(period_x / 2, period_y / 2)``. Sample (i, j)
    sits at ``(i * period_x / n_samples_x, j * period_y / n_samples_y)``,
    where :func:`permittivity_toeplitz_2d` reads it, and belongs to the
    hole when that point lies inside the circle (binary raster: the area
    is quantised to the sample cells, the centre is exact). Until 2026-10
    the closed intervals ``linspace(0, period, n)`` were sampled, which
    shifted the hole by half a sample and shrank it by ``(n - 1) / n``.

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
    # Offsets from the centre P/2 = sample n/2, exact and symmetric in float64
    x = (torch.arange(n_samples_x, dtype=torch.float64, device=device) - 0.5 * n_samples_x) * (
        period_x / n_samples_x
    )
    y = (torch.arange(n_samples_y, dtype=torch.float64, device=device) - 0.5 * n_samples_y) * (
        period_y / n_samples_y
    )
    X, Y = torch.meshgrid(x, y, indexing="ij")
    mask = X**2 + Y**2 <= radius**2

    eps = torch.full(
        (n_samples_x, n_samples_y), eps_background, dtype=torch.complex128, device=device
    )
    eps[mask] = torch.tensor(complex(eps_hole), dtype=eps.dtype, device=eps.device)
    return eps
