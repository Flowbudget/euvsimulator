"""Rigorous Coupled-Wave Analysis (RCWA) — 1D grating, PyTorch.

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
import warnings
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch

from euvsimulator.mask3d.geometry import line_fill_fraction

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
            raise ValueError("polarization must be TE or TM")


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
        ml_stack=None,
        roughness_nm: Optional[float] = None,
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
            (n_upper, n_lower) of substrate. Ignored when ml_stack is provided.
        ml_stack : MultilayerStack, optional
            Multilayer stack for the P1-2 order-diagonal ML reflection operator.
            When provided, the bottom boundary condition is an order-diagonal
            ML reflection operator computed via TMM (Option C).
            The grating layer is matched to a zero-thickness layer of the
            incident medium, and the TMM runs from that medium into the
            stack (top layer first, e.g. Ru).
        roughness_nm : float, optional
            RMS interface roughness [nm] for Nevot-Croce damping inside the
            ML operator: every ML interface including incident medium/top
            layer, as in the pipeline's clear-field TMM. None or 0 gives
            ideal interfaces. Only used together with ml_stack.

        Returns
        -------
        orders : (M,) complex128
            Complex reflected order amplitudes.
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

        # Rayleigh wavevectors
        k_xm = k0 * n_i[0] * math.sin(theta) - self.m * (2.0 * math.pi / period)
        Kx = torch.diag(k_xm / k0).to(torch.complex128)

        # Permittivity Toeplitz matrices: Toeplitz(ε) and Toeplitz(1/ε)
        E_eps = permittivity_toeplitz(eps_profile, self.M, use_inverse_rule=False)
        E_inv = permittivity_toeplitz(eps_profile, self.M, use_inverse_rule=True)
        I_M = torch.eye(self.M, dtype=torch.complex128, device=self.device)

        # Eigenvalue problem  d²u/dz'² = −A u  (z' = k0 z), q² = eig(A).
        #
        # TE (E_y):  A = [ε] − Kx²                                   (Moharam 1995)
        # TM (H_y):  A = [1/ε]⁻¹ (I − Kx [ε]⁻¹ Kx)                  (Li 1996, Lalanne & Morris 1996)
        #   From ∂z((1/ε)∂z H) + ∂x((1/ε)∂x H) + k0² H = 0: the product (1/ε)·∂z H
        #   has one discontinuous factor -> Laurent rule, [1/ε]; the product
        #   (1/ε)·∂x H = −i k0 E_z is continuous (E_z is tangential to the
        #   lamellar interfaces) -> inverse rule, [ε]⁻¹.
        #   Before 2026-09-04 this read A = [ε] − [ε] Kx [ε]⁻¹ Kx (Laurent rule
        #   everywhere) with the modal admittance V = [ε] W Q⁻¹ and Rayleigh
        #   admittance ε k0/kz -- a set of conventions that is self-consistent
        #   for HOMOGENEOUS layers (everything commutes; slab == TMM) but wrong
        #   for gratings: the effective-medium limit P << λ gave R_TM = 0.21
        #   instead of the exact 0.030 and did not converge in M
        # .
        Kx2 = Kx @ Kx
        if self.cfg.polarization == "TE":
            A = E_eps - Kx2
        else:
            A = torch.linalg.inv(E_inv) @ (I_M - Kx @ torch.linalg.inv(E_eps) @ Kx)

        eig_vals, W = torch.linalg.eig(A)
        q = torch.sqrt(eig_vals)
        # Branch selection (standard RCWA convention): choose the root that
        # decays or propagates forward.  Prefer Im(q) > 0 (evanescent decay);
        # when Im(q) is numerically ~0 (propagating mode), fall back to
        # Re(q) > 0.  This prevents the exp(i k0 q d) blow-up that occurs
        # when a near-real eigenvalue picks the wrong branch at high order.
        _imag_tol = 1e-10
        flip = torch.where(
            q.imag.abs() < _imag_tol,
            q.real < 0,  # near-real: pick Re(q) > 0
            q.imag < 0,  # complex: pick Im(q) > 0
        )
        q = torch.where(flip, -q, q)
        # Second tangential field of each mode (the one whose continuity,
        # together with the first, fixes the interface S-matrices):
        #   TE: H_x ∝ −(i/k0) ∂z E_y  ->  V = W Q
        #   TM: E_x ∝  (i/k0)(1/ε) ∂z H_y  ->  V = [1/ε] W Q
        if self.cfg.polarization == "TE":
            V = W @ torch.diag(q)
        else:
            V = E_inv @ W @ torch.diag(q)

        # Rayleigh "admittances" of incident and substrate media: the same
        # field ratio for a plane wave e^{i kz z} -- kz/k0 (TE, H_x/E_y) and
        # kz/(k0 ε) (TM, E_x/H_y).
        kz_inc = torch.sqrt((n_i[0] * k0) ** 2 - k_xm**2 + 0j)
        kz_sub = torch.sqrt((n_s[0] * k0) ** 2 - k_xm**2 + 0j)
        kz_inc = torch.where(kz_inc.imag < 0, -kz_inc, kz_inc)
        kz_sub = torch.where(kz_sub.imag < 0, -kz_sub, kz_sub)
        # Power carried by each reflected order relative to the incident wave
        # (same medium, so the factor is Re(kz_m)/kz_0 for TE and TM alike);
        # used by diffraction_efficiency, 0 for evanescent orders.
        self._power_factor = (kz_inc.real / kz_inc[self.M // 2].real).detach()

        if self.cfg.polarization == "TE":
            Y_inc = torch.diag(kz_inc / k0).to(torch.complex128)
            Y_sub = torch.diag(kz_sub / k0).to(torch.complex128)
        else:
            Y_inc = torch.diag(kz_inc / (k0 * n_i[0] ** 2)).to(torch.complex128)
            Y_sub = torch.diag(kz_sub / (k0 * n_s[0] ** 2)).to(torch.complex128)

        # Build top interface S-matrix: Rayleigh ↔ eigenmodes
        S_top = self._rayleigh_to_eigenmode_smatrix(Y_inc, W, V)

        # Build propagation through layer(s)
        S_layer = self._propagation_smatrix(q, thicknesses, k0)

        # Build bottom interface S-matrix: eigenmodes ↔ substrate Rayleigh
        if ml_stack is not None:
            # ── P1-2: Order-diagonal ML reflection operator (Option C) ──
            # Interface medium between the grating layer and the ML: a
            # zero-thickness layer of the incident medium (vacuum for a
            # reflective mask), whose Rayleigh admittance is Y_inc. A
            # zero-thickness homogeneous layer is transparent: without
            # roughness the orders equal those of matching directly to the
            # cap layer (max |delta r_m| 5e-16, checked 2026-10-02). With
            # roughness the TMM below also damps the incident-medium/cap
            # interface, as the pipeline's clear-field TMM does. Until
            # 2026-10-02 the cap layer was the interface medium and the ML
            # operator ignored roughness: open-frame dose +16.6 % at
            # ml_roughness_nm = 0.7 (+0.83 % with only the ML interfaces
            # damped).
            S_interface = self._eigenmode_to_rayleigh_smatrix(Y_inc, W, V)

            # Build order-diagonal ML reflection operator
            S_ML = _build_ml_reflection_operator(
                ml_stack,
                k_xm,
                k0,
                self.cfg.wavelength,
                self.cfg.polarization,
                self.device,
                n_top=n_i[0],
                roughness_nm=roughness_nm,
            )

            # Cascade: S_bot = S_interface ⨂ S_ML
            S_bot = self._redheffer_star_matrix(S_interface, S_ML)
        else:
            # Original: homogeneous substrate half-space
            S_bot = self._eigenmode_to_rayleigh_smatrix(Y_sub, W, V)

        # Cascade: total S = S_top ⨂ S_layer ⨂ S_bot
        S_total = self._redheffer_star_matrix(self._redheffer_star_matrix(S_top, S_layer), S_bot)

        # Incident: 0th order only
        inc = torch.zeros(self.M, dtype=torch.complex128, device=self.device)
        inc[self.M // 2] = 1.0

        # Reflected orders = S_total[0,0] @ inc
        reflected = S_total[0, 0] @ inc
        return reflected

    def diffraction_efficiency(
        self,
        orders: torch.Tensor,
        period: Optional[float] = None,
        n_incident: Optional[torch.Tensor] = None,
    ) -> Dict[int, float]:
        """Diffraction efficiencies per order.

        Parameters
        ----------
        orders : (M,) complex128
            Reflected order amplitudes from ``solve()``.
        period : float [m], optional
            Grating period.  Only needed when this instance has not run
            :meth:`solve` itself; otherwise the geometry of the most recent
            ``solve()`` call is used.
        n_incident : (2,) complex128, optional
            Incident medium, as in :meth:`solve` (default vacuum); only used
            together with *period*.

        Returns
        -------
        eff : dict {order: float}
            Reflected power per order relative to the incident power,
            ``|r_m|² · Re(kz_m)/kz_0`` in the incident medium; evanescent
            orders carry no power and give 0.  (Before 2026-09-25 this was
            ``|r_m|²`` alone, which is the power only for m = 0.)  Uses the
            order geometry of the most recent :meth:`solve` call.
        """
        factor = self._order_power_factor(period, n_incident)
        order_map: Dict[int, float] = {}
        for i, m_val in enumerate(self.m.tolist()):
            amp = orders[i]
            power = (amp * amp.conj()).real * factor[i]
            order_map[int(m_val)] = float(power.item())
        return order_map

    def _order_power_factor(
        self, period: Optional[float], n_incident: Optional[torch.Tensor]
    ) -> torch.Tensor:
        """Re(kz_m)/kz_0 per order: from *period* if given, else from the last solve()."""
        if period is not None:
            n_i = (
                torch.tensor([1.0 + 0.0j], dtype=torch.complex128)
                if n_incident is None
                else n_incident.to(torch.complex128)
            )
            k0 = 2.0 * math.pi / self.cfg.wavelength
            k_xm = k0 * n_i[0] * math.sin(math.radians(self.cfg.theta)) - self.m * (
                2.0 * math.pi / period
            )
            kz = torch.sqrt((n_i[0] * k0) ** 2 - k_xm**2 + 0j)
            kz = torch.where(kz.imag < 0, -kz, kz)
            return (kz.real / kz[self.M // 2].real).detach()
        if hasattr(self, "_power_factor"):
            return self._power_factor
        warnings.warn(
            "diffraction_efficiency() on a solver that has not run solve() and "
            "without `period`: returning |r_m|^2, which is the power only for m = 0",
            stacklevel=3,
        )
        return torch.ones(self.M, dtype=torch.float64, device=self.device)

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
    def _redheffer_star_matrix(S_a: torch.Tensor, S_b: torch.Tensor) -> torch.Tensor:
        """Redheffer star product for matrix-valued S-matrices.

        Port 0 of the result is port 0 of *S_a*, port 1 is port 1 of *S_b*;
        S[i, j] maps the wave INCOMING at port j to the wave OUTGOING at
        port i.  (Redheffer 1962; Li, JOSA A 13, 1024 (1996), Eq. 11):

          S₁₁ = A₁₁ + A₁₂ (I − B₁₁ A₂₂)⁻¹ B₁₁ A₂₁
          S₁₂ = A₁₂ (I − B₁₁ A₂₂)⁻¹ B₁₂
          S₂₁ = B₂₁ (I − A₂₂ B₁₁)⁻¹ A₂₁
          S₂₂ = B₂₂ + B₂₁ (I − A₂₂ B₁₁)⁻¹ A₂₂ B₁₂

        The two resolvents are NOT interchangeable for matrix blocks:
        (I − B₁₁A₂₂)⁻¹ B₁₁ = B₁₁ (I − A₂₂B₁₁)⁻¹ (push-through identity), so
        using (I − A₂₂B₁₁)⁻¹ in S₁₁ puts the factors in the wrong order.
        Before 2026-09-04 the two were swapped; that is invisible for scalar
        blocks (TMM, homogeneous layers -- everything commutes) but made the
        cascade Rayleigh → grating modes → Rayleigh over zero thickness NOT
        reduce to the plain interface (deviation 0.17 in |r| for a lossless
        test grating) and broke energy conservation by ~1 %.
        """
        M = S_a.shape[-1]
        I = torch.eye(M, dtype=torch.complex128, device=S_a.device)

        A11, A12, A21, A22 = S_a[0, 0], S_a[0, 1], S_a[1, 0], S_a[1, 1]
        B11, B12, B21, B22 = S_b[0, 0], S_b[0, 1], S_b[1, 0], S_b[1, 1]

        D_b = torch.linalg.inv(I - B11 @ A22)  # for terms that start with B11
        D_a = torch.linalg.inv(I - A22 @ B11)  # for terms that start with A22

        S = torch.zeros_like(S_a)
        S[0, 0] = A11 + A12 @ D_b @ B11 @ A21
        S[0, 1] = A12 @ D_b @ B12
        S[1, 0] = B21 @ D_a @ A21
        S[1, 1] = B22 + B21 @ D_a @ A22 @ B12
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

        Returns (efficiencies, n_orders_used).  Orders run 11, 21, 31, ...
        up to *max_orders*; if the relative change of R0 never drops below
        *target_rel*, a warning is issued and the last result is returned.
        """
        prev_r0: Optional[float] = None
        eff: Dict[int, float] = {}
        last_m = 0

        for M in range(11, max_orders + 1, 10):
            cfg = RCWAConfig(
                wavelength=self.cfg.wavelength,
                n_orders=M,
                theta=self.cfg.theta,
                polarization=self.cfg.polarization,
                device=self.cfg.device,
            )
            solver = RCWA1D(cfg)
            orders = solver.solve(
                eps_profile,
                thicknesses,
                period,
                n_incident=n_incident,
                n_substrate=n_substrate,
            )
            eff = solver.diffraction_efficiency(orders)
            r0 = eff.get(0, 0.0)

            if prev_r0 is not None and prev_r0 > 1e-12:
                rel_change = abs(r0 - prev_r0) / prev_r0
                if rel_change < target_rel:
                    return eff, M
            prev_r0 = r0
            last_m = M

        # Not converged: report the order count actually used (the former
        # `return eff, max_orders` also claimed max_orders when the step
        # never reached it) and say so.
        warnings.warn(
            f"RCWA did not converge to target_rel={target_rel} within {last_m} orders "
            "(0th order still changing); returning the last result",
            stacklevel=2,
        )
        return eff, last_m


# ──────────────────────────────────────────────
# P1-2: Order-diagonal ML reflection operator
# ──────────────────────────────────────────────


def _build_ml_reflection_operator(
    ml_stack,
    k_xm: torch.Tensor,
    k0: float,
    wavelength: float,
    polarization: str,
    device: torch.device,
    n_top: Optional[torch.Tensor] = None,
    roughness_nm: Optional[float] = None,
) -> torch.Tensor:
    """Build the order-diagonal ML reflection operator S_ML.

    For each Rayleigh order m, the complex TMM reflection coefficient
    r_m of the full ML stack is computed.  The ML is a planar stack,
    so its S-matrix is diagonal in the order basis::

        S_ML[0, 0, m, m] = r_m          (reflection, order m)
        S_ML[0, 1] = S_ML[1, 0] = 0     (no transmission)
        S_ML[1, 1] = 0                   (no reflection from below)

    The incident medium for the TMM is *n_top*, which must be the medium
    of the Rayleigh modes at the interface (RCWA1D.solve passes its
    incident medium, vacuum for a mask). Default: the ML stack's top layer
    (e.g., Ru capping layer), the convention before 2026-10-02.

    Parameters
    ----------
    ml_stack : MultilayerStack
        The multilayer stack (top -> bottom, including the cap).
    k_xm : (M,) float64
        In-plane wavevectors of each Rayleigh order.
    k0 : float
        Free-space wavevector magnitude.
    wavelength : float [m]
        Free-space wavelength.
    polarization : str
        "TE" or "TM".
    device : torch.device
    n_top : complex tensor, optional
        Incident medium of the TMM. None -> ml_stack.n_layers[0].
    roughness_nm : float, optional
        RMS interface roughness [nm] for Nevot-Croce damping of every TMM
        interface, including n_top/first layer. None or 0 -> ideal.

    Returns
    -------
    S_ML : (2, 2, M, M) complex128
        Order-diagonal ML reflection operator.
    """
    from euvsimulator.optics.tmm import reflectivity_at_kx

    M = k_xm.shape[0]
    te = polarization == "TE"

    # ML stack layers (including the cap)
    n_layers = ml_stack.n_layers  # (N,) complex128
    thicknesses = ml_stack.thicknesses  # (N,) float64 [m]

    # The incident medium of the TMM is the RCWA interface medium: n_top if
    # given (RCWA1D.solve passes its incident medium), else the top layer of
    # the ML stack (the Ru capping layer).
    n_inc = n_layers[0] if n_top is None else torch.as_tensor(n_top, dtype=torch.complex128)

    # Substrate below the ML: bulk Si (the standard EUV blank). The previous
    # expression had two identical branches that both took the LAST LAYER's
    # index -- numerically the same as Si here because the bottom layer of a
    # Mo/Si stack is Si, but logically wrong; take Si from the CXRO table at
    # the actual wavelength instead.
    from euvsimulator.constants import HC_EV_NM
    from euvsimulator.materials import CXROTable

    n_si, k_si = CXROTable().refractive_index("Si", HC_EV_NM / (wavelength * 1e9))
    n_sub = torch.tensor(complex(n_si, k_si), dtype=torch.complex128)

    S_ML = torch.zeros(2, 2, M, M, dtype=torch.complex128, device=device)

    for m in range(M):
        kx_norm = float(k_xm[m].real.item()) / k0
        # Nevot-Croce damping exp(-2 kz_a kz_b sigma^2) holds for propagating
        # waves. For an order evanescent in the incident medium kz_a kz_b is
        # negative and the factor grows like exp(2 kx^2 sigma^2) (about 1e10
        # at kx = 10.5 k0, sigma = 0.7 nm), which is not physical; such
        # orders keep ideal interfaces. Without this the image of a 64 nm
        # mask pitch drifted by 2e-4 between 51 and 101 orders (2026-10-02).
        rough_m = roughness_nm if abs(kx_norm) < float(n_inc.real) else None
        r_m = reflectivity_at_kx(
            n_layers,
            thicknesses,
            wavelength,
            kx_norm=kx_norm,
            te=te,
            n_incident=torch.tensor(
                complex(float(n_inc.real), float(n_inc.imag)), dtype=torch.complex128
            ),
            n_substrate=torch.tensor(
                complex(float(n_sub.real), float(n_sub.imag)), dtype=torch.complex128
            ),
            roughness_nm=rough_m,
        )
        # optics.tmm returns the reflection coefficient of the field whose
        # continuity its admittance formulation is built on: E_y for TE, and
        # for TM the E-field amplitude (admittance ε k0/kz = H_y/E_x). The
        # RCWA TM Rayleigh amplitudes are H_y; for the reflected (−z) wave
        # H_y = −η E_x, so r_H = −r_E. Verified 2026-09-04 on an empty
        # grating over the ML stack: with the sign, |r0|² and phase match the
        # TMM to 1e-6; without it, 0.633 vs 0.639 and −1.5° vs −12.6°.
        S_ML[0, 0, m, m] = torch.as_tensor(r_m if te else -r_m, dtype=S_ML.dtype)

    return S_ML


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

    The line is centred at ``period / 2``. Sample k sits at
    ``x_k = k * period / n_samples``, where :func:`permittivity_toeplitz`
    reads it, and a sample whose cell an edge cuts holds the area-weighted
    mixture of the two permittivities, so the duty cycle and the centre
    are exact for every ``n_samples`` (see
    :func:`~euvsimulator.mask3d.geometry.line_fill_fraction`; until 2026-10
    the closed interval ``linspace(0, period, n_samples)`` was sampled,
    ).

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
    frac = line_fill_fraction(n_samples, fill_width / period, device=device)
    return complex(eps_space) * (1.0 - frac) + complex(eps_line) * frac
