"""
Rigorous Coupled-Wave Analysis (RCWA) — 1D grating, PyTorch.

Fourier Modal Method (FMM) with numerically stable scattering-matrix
(S-matrix) cascade.  All core functions support autograd.

Theory
------
For a 1D grating periodic in *x*, the fields are expanded in Fourier
orders.  Each homogeneous-in-*z* layer satisfies the eigenvalue
problem::

    A W = W q²   where A = E − Kx²   (TE polarisation)

The eigenvectors *W* diagonalise the permittivity Toeplitz matrix *E*,
and the eigenvalues *q²* give the propagation constants.  Interface
S-matrices connect the Rayleigh order basis to the eigenmode basis
using the continuity of tangential E and H.

References
----------
M. G. Moharam et al., J. Opt. Soc. Am. A 12(5), 1077–1086 (1995).
L. Li, J. Opt. Soc. Am. A 13(9), 1870–1876 (1996).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────


@dataclass
class RCWAConfig:
    """Configuration for a 1D RCWA simulation.

    Parameters
    ----------
    wavelength : float
        Free-space wavelength [m] (default: 13.5e-9).
    n_orders : int
        Number of Fourier orders (odd, default: 21).
    theta : float
        Polar angle of incidence [deg] (default: 6.0).
    polarization : str
        ``"TE"`` or ``"TM"`` (default: ``"TE"``).
    device : str
        PyTorch device (default: ``"cpu"``).
    """
    wavelength: float = 13.5e-9
    n_orders: int = 21
    theta: float = 6.0
    polarization: str = "TE"
    device: str = "cpu"

    def __post_init__(self) -> None:
        if self.n_orders % 2 == 0:
            raise ValueError(f"n_orders must be odd, got {self.n_orders}")
        self.polarization = self.polarization.upper()
        if self.polarization not in ("TE", "TM"):
            raise ValueError(f"polarization must be TE or TM")


# ──────────────────────────────────────────────
# Toeplitz permittivity matrix
# ──────────────────────────────────────────────


def permittivity_toeplitz(
    eps_profile: torch.Tensor,
    n_orders: int,
    use_inverse_rule: bool = False,
) -> torch.Tensor:
    """Toeplitz permittivity matrix from a 1D profile (Li's rules).

    Parameters
    ----------
    eps_profile : (Nx,) complex128
    n_orders : int (odd)
    use_inverse_rule : bool
        True → build [1/ε] Toeplitz (needed for TM).

    Returns
    -------
    E : (M, M) complex128
    """
    M = n_orders
    Nx = eps_profile.shape[0]
    if use_inverse_rule:
        eps_profile = 1.0 / eps_profile
    eps_fft = torch.fft.fft(eps_profile) / Nx
    eps_fft = torch.fft.fftshift(eps_fft)
    center = Nx // 2
    idx = torch.arange(M, device=eps_profile.device)
    diff = idx.view(-1, 1) - idx.view(1, -1)
    E = eps_fft[center + diff]
    return E.to(torch.complex128)


# ──────────────────────────────────────────────
# RCWA solver
# ──────────────────────────────────────────────


class RCWA1D:
    """1D RCWA solver with S-matrix cascade.

    Parameters
    ----------
    cfg : RCWAConfig
    """

    def __init__(self, cfg: RCWAConfig) -> None:
        self.cfg = cfg
        self.device = torch.device(cfg.device)
        self.M = cfg.n_orders
        half = self.M // 2
        self.m = torch.arange(-half, half + 1, dtype=torch.float64, device=self.device)

    # ── Public API ─────────────────────────────

    def solve(
        self,
        eps_profile: torch.Tensor,
        thicknesses: torch.Tensor,
        period: float,
        n_incident: Optional[torch.Tensor] = None,
        n_substrate: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Run the RCWA simulation.

        Parameters
        ----------
        eps_profile : (Nx,) complex128
            Permittivity over one period.
        thicknesses : (Nlayers,) float64 [m]
            Layer thicknesses (single layer for binary grating).
        period : float [m]
            Grating period.
        n_incident : (2,) complex128, optional
            (n_upper, n_lower) of incident medium.
        n_substrate : (2,) complex128, optional
            (n_upper, n_lower) of substrate.

        Returns
        -------
        orders : (M,) complex128
            Complex reflected order amplitudes.
        """
        if n_incident is None:
            n_incident = torch.tensor([1.0+0.0j, 1.0+0.0j], dtype=torch.complex128)
        if n_substrate is None:
            n_substrate = n_incident.clone()

        n_i = n_incident.to(torch.complex128)
        n_s = n_substrate.to(torch.complex128)
        k0 = 2.0 * math.pi / self.cfg.wavelength
        theta = math.radians(self.cfg.theta)

        # Rayleigh wavevectors
        k_xm = k0 * n_i[0] * math.sin(theta) - self.m * (2.0 * math.pi / period)
        Kx = torch.diag(k_xm / k0).to(torch.complex128)

        # Permittivity Toeplitz matrix
        use_inv = self.cfg.polarization == "TM"
        E = permittivity_toeplitz(eps_profile, self.M, use_inverse_rule=use_inv)

        # Eigenvalue problem: A = E - Kx²  (TE)
        Kx2 = Kx @ Kx
        if self.cfg.polarization == "TE":
            A = E - Kx2
        else:
            E_inv = torch.linalg.inv(E)
            A = E - Kx @ E_inv @ Kx  # Li's TM rule

        eig_vals, W = torch.linalg.eig(A)
        q = torch.sqrt(eig_vals)
        q = torch.where(q.imag < 0, -q, q)  # Im(q) >= 0
        V = W @ torch.diag(q)  # modal admittance (TE)

        # Rayleigh admittances of incident and substrate media
        kz_inc = torch.sqrt(
            (n_i[0] * k0) ** 2 - k_xm**2 + 0j
        )
        kz_sub = torch.sqrt(
            (n_s[0] * k0) ** 2 - k_xm**2 + 0j
        )
        kz_inc = torch.where(kz_inc.imag < 0, -kz_inc, kz_inc)
        kz_sub = torch.where(kz_sub.imag < 0, -kz_sub, kz_sub)

        if self.cfg.polarization == "TE":
            Y_inc = torch.diag(kz_inc / k0).to(torch.complex128)
            Y_sub = torch.diag(kz_sub / k0).to(torch.complex128)
        else:
            Y_inc = torch.diag(n_i[0]**2 * k0 / kz_inc).to(torch.complex128)
            Y_sub = torch.diag(n_s[0]**2 * k0 / kz_sub).to(torch.complex128)

        # Build top interface S-matrix: Rayleigh ↔ eigenmodes
        S_top = self._rayleigh_to_eigenmode_smatrix(Y_inc, W, V)

        # Build propagation through layer(s)
        S_layer = self._propagation_smatrix(q, thicknesses, k0)

        # Build bottom interface S-matrix: eigenmodes ↔ substrate Rayleigh
        S_bot = self._eigenmode_to_rayleigh_smatrix(Y_sub, W, V)

        # Cascade: total S = S_top ⨂ S_layer ⨂ S_bot
        S_total = self._redheffer_star_matrix(
            self._redheffer_star_matrix(S_top, S_layer), S_bot
        )

        # Incident: 0th order only
        inc = torch.zeros(self.M, dtype=torch.complex128, device=self.device)
        inc[self.M // 2] = 1.0 + 0.0j

        # Reflected orders = S_total[0,0] @ inc
        reflected = S_total[0, 0] @ inc
        return reflected

    def diffraction_efficiency(
        self, orders: torch.Tensor
    ) -> Dict[int, float]:
        """Diffraction efficiencies per order.

        Parameters
        ----------
        orders : (M,) complex128
            Reflected order amplitudes from ``solve()``.

        Returns
        -------
        eff : dict {order: float}
        """
        order_map: Dict[int, float] = {}
        for i, m_val in enumerate(self.m.tolist()):
            amp = orders[i]
            order_map[int(m_val)] = float((amp * amp.conj()).real.item())
        return order_map

    # ── S-matrix building blocks ───────────────

    def _rayleigh_to_eigenmode_smatrix(
        self, Y_R: torch.Tensor, W: torch.Tensor, V: torch.Tensor
    ) -> torch.Tensor:
        """Interface: Rayleigh basis → eigenmode basis.

        S₁₁ = 2W A⁻¹ Y_R − I    (reflected Rayleigh)
        S₁₂ = 2W A⁻¹ V          (incoming eigenmode → Rayleigh)
        S₂₁ = A⁻¹ 2 Y_R         (incident Rayleigh → eigenmode)
        S₂₂ = −A⁻¹ B            (reflected eigenmode → eigenmode)

        where A = V + Y_R W, B = Y_R W − V.
        """
        M = self.M
        I = torch.eye(M, dtype=torch.complex128, device=self.device)
        YW = Y_R @ W
        A = V + YW
        B = YW - V
        A_inv = torch.linalg.inv(A)

        S = torch.zeros(2, 2, M, M, dtype=torch.complex128, device=self.device)
        S[0, 0] = 2.0 * W @ A_inv @ Y_R - I
        S[0, 1] = 2.0 * W @ A_inv @ V
        S[1, 0] = 2.0 * A_inv @ Y_R
        S[1, 1] = -A_inv @ B
        return S

    def _eigenmode_to_rayleigh_smatrix(
        self, Y_R: torch.Tensor, W: torch.Tensor, V: torch.Tensor
    ) -> torch.Tensor:
        """Interface: eigenmode basis → Rayleigh basis (substrate side).

        This is the same as ``_rayleigh_to_eigenmode_smatrix`` but with
        port roles swapped: port 0 = eigenmode, port 1 = Rayleigh.
        """
        M = self.M
        I = torch.eye(M, dtype=torch.complex128, device=self.device)
        YW = Y_R @ W
        A = V + YW
        B = YW - V
        A_inv = torch.linalg.inv(A)

        S = torch.zeros(2, 2, M, M, dtype=torch.complex128, device=self.device)
        # Port 0 = eigenmode (top), Port 1 = Rayleigh (bottom)
        # S₁₁: eigenmode → eigenmode (reflected back into layer)
        # S₁₂: bottom Rayleigh → eigenmode
        # S₂₁: eigenmode → bottom Rayleigh
        # S₂₂: bottom Rayleigh → Rayleigh
        S[0, 0] = -A_inv @ B
        S[0, 1] = 2.0 * A_inv @ Y_R
        S[1, 0] = 2.0 * W @ A_inv @ V
        S[1, 1] = 2.0 * W @ A_inv @ Y_R - I
        return S

    def _propagation_smatrix(
        self, q: torch.Tensor, thicknesses: torch.Tensor, k0: float
    ) -> torch.Tensor:
        """Propagation through grating layer(s).

        For each layer, the S-matrix in the eigenmode basis is:
        S = [[0, X], [X, 0]] where X = diag(exp(-i k₀ q d)).

        Multiple layers are cascaded via Redheffer star.
        """
        M = self.M
        S_total = torch.zeros(2, 2, M, M, dtype=torch.complex128, device=self.device)
        S_total[0, 1] = torch.eye(M, dtype=torch.complex128, device=self.device)
        S_total[1, 0] = torch.eye(M, dtype=torch.complex128, device=self.device)

        for idx in range(thicknesses.shape[0]):
            d = thicknesses[idx]
            phase = torch.exp(1j * k0 * q * d)
            X = torch.diag(phase)

            S_layer = torch.zeros(2, 2, M, M, dtype=torch.complex128, device=self.device)
            S_layer[0, 1] = X
            S_layer[1, 0] = X

            S_total = self._redheffer_star_matrix(S_total, S_layer)

        return S_total

    # ── Redheffer star product ─────────────────

    @staticmethod
    def _redheffer_star_matrix(
        S_a: torch.Tensor, S_b: torch.Tensor
    ) -> torch.Tensor:
        """Redheffer star product for matrix-valued S-matrices.

        Stable formulation (Li 1996):
          D₁ = (I − A₂₂ B₁₁)^{-1}
          D₂ = (I − B₁₁ A₂₂)^{-1}
        """
        M = S_a.shape[-1]
        I = torch.eye(M, dtype=torch.complex128, device=S_a.device)

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
        eps_profile: torch.Tensor,
        thicknesses: torch.Tensor,
        period: float,
        target_rel: float = 1e-3,
        max_orders: int = 101,
        n_incident: Optional[torch.Tensor] = None,
        n_substrate: Optional[torch.Tensor] = None,
    ) -> Tuple[Dict[int, float], int]:
        """Increase Fourier orders until zeroth order stabilises.

        Returns (efficiencies, n_orders_used).
        """
        prev_r0: Optional[float] = None
        eff: Dict[int, float] = {}

        for M in range(11, max_orders + 1, 10):
            cfg = RCWAConfig(
                wavelength=self.cfg.wavelength, n_orders=M,
                theta=self.cfg.theta, polarization=self.cfg.polarization,
                device=self.cfg.device,
            )
            solver = RCWA1D(cfg)
            orders = solver.solve(
                eps_profile, thicknesses, period,
                n_incident=n_incident, n_substrate=n_substrate,
            )
            eff = solver.diffraction_efficiency(orders)
            r0 = eff.get(0, 0.0)

            if prev_r0 is not None and prev_r0 > 1e-12:
                rel_change = abs(r0 - prev_r0) / prev_r0
                if rel_change < target_rel:
                    return eff, M
            prev_r0 = r0

        return eff, max_orders


# ──────────────────────────────────────────────
# Convenience: binary grating profile
# ──────────────────────────────────────────────


def binary_grating_profile(
    period: float,
    fill_width: float,
    eps_line: complex,
    eps_space: complex,
    n_samples: int = 1024,
    device: str = "cpu",
) -> torch.Tensor:
    """Binary (rectangular) grating permittivity profile.

    Parameters
    ----------
    period : float [m]
    fill_width : float [m]
        Width of the line (high-ε region).
    eps_line : complex
        Line permittivity.
    eps_space : complex
        Space permittivity.
    n_samples : int
        Spatial samples (default: 1024).
    device : str

    Returns
    -------
    eps_profile : (n_samples,) complex128
    """
    x = torch.linspace(0, period, n_samples, device=device)
    half = fill_width / 2.0
    mask = (x >= period / 2 - half) & (x <= period / 2 + half)
    eps = torch.full_like(x, eps_space, dtype=torch.complex128)
    eps[mask] = complex(eps_line)
    return eps