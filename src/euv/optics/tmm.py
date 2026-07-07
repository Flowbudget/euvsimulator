"""Transfer-Matrix Method (TMM) for multilayer thin-film reflectivity.

Uses the **scattering matrix (S-matrix) / Redheffer star product**
formulation for numerical stability with many layers and lossy media.
All public functions accept PyTorch tensors and are fully differentiable
via torch.autograd.

Theory
------
For a multilayer stack, each interface and each layer is represented by
a 2×2 scattering matrix that relates incoming to outgoing waves.  The
total stack S-matrix is built by combining layer-by-layer via the
Redheffer star product, which is numerically stable because it never
mixes exponentially growing and decaying eigenmodes (unlike the
classical T-matrix formulation).

Layer propagation S-matrix::

    S_layer = |  0           e^{i k_z d}  |
              | e^{i k_z d}      0         |

Interface S-matrix (between medium *a* and *b*)::

    r_ab = (η_a − η_b) / (η_a + η_b)
    t_ab = 2 η_a / (η_a + η_b)

    S_iface = | r_ab   t_ba |
              | t_ab   r_ba |

where *η* is the layer admittance (k_z/k₀ for TE, n² k₀/k_z for TM),
*k_z* = k₀ √(n² − n₀² sin²θ₀), and *d* is the physical thickness.

References
----------
H. A. Macleod, *Thin-Film Optical Filters*, 4th ed., CRC Press (2010).
L. Li, "Formulation and comparison of two recursive matrix algorithms
for modeling layered diffraction gratings", J. Opt. Soc. Am. A 13(5),
1024–1035 (1996).
"""

from __future__ import annotations

import math
from typing import Tuple

import torch

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _kz(
    n_layer: torch.Tensor,
    k0: torch.Tensor,
    n0_sin2_value: torch.Tensor,
) -> torch.Tensor:
    """z-component of the wavevector in a layer.

    k_z = k₀ · √(n² − n₀² sin²θ₀)

    The branch is chosen so that Im(k_z) ≥ 0 (wave decays propagating
    into an absorbing medium).

    Parameters
    ----------
    n_layer : (...,) complex128
    k0 : (...,) float64
    n0_sin2_value : (...,) float64
        n₀² sin²θ₀ (real scalar per wavelength/angle).

    Returns
    -------
    kz : (...,) complex128
    """
    n2 = n_layer * n_layer
    radicand = n2 - n0_sin2_value.to(torch.complex128)
    kz = k0.to(torch.complex128) * torch.sqrt(radicand)
    # Enforce Im(kz) >= 0 (decaying branch for lossy media)
    kz = torch.where(kz.imag < 0, -kz, kz)
    return kz


def _admittance(
    n: torch.Tensor,
    kz: torch.Tensor,
    k0: torch.Tensor,
    te: bool,
) -> torch.Tensor:
    """Layer admittance η.

    TE:  η = k_z / k₀
    TM:  η = n² · k₀ / k_z
    """
    if te:
        return kz / k0.to(torch.complex128)
    else:
        n2 = n * n
        return n2.to(torch.complex128) * k0.to(torch.complex128) / kz


# ──────────────────────────────────────────────
# S-matrix building blocks
# ──────────────────────────────────────────────


def _interface_smatrix(eta_a: torch.Tensor, eta_b: torch.Tensor) -> torch.Tensor:
    """Scattering matrix for an interface between media *a* and *b*.

    S = [[r_ab,  t_ba],
         [t_ab,  r_ba]]

    Shape: (..., 2, 2)
    """
    denom = eta_a + eta_b
    r_ab = (eta_a - eta_b) / denom
    t_ab = 2.0 * eta_a / denom
    # From side b: r_ba = (η_b − η_a) / (η_a + η_b) = −r_ab
    r_ba = (eta_b - eta_a) / denom
    t_ba = 2.0 * eta_b / denom

    S = torch.zeros(*eta_a.shape, 2, 2, dtype=torch.complex128, device=eta_a.device)
    S[..., 0, 0] = r_ab
    S[..., 0, 1] = t_ba
    S[..., 1, 0] = t_ab
    S[..., 1, 1] = r_ba
    return S


def _layer_smatrix(kz: torch.Tensor, d: torch.Tensor) -> torch.Tensor:
    """Scattering matrix for propagation through a homogeneous layer.

    S = [[0,         exp(i kz d)],
         [exp(i kz d),  0       ]]

    Shape: (..., 2, 2)
    """
    phase = torch.exp(1j * kz * d.to(torch.complex128))
    S = torch.zeros(*kz.shape, 2, 2, dtype=torch.complex128, device=kz.device)
    S[..., 0, 1] = phase
    S[..., 1, 0] = phase
    return S


def _redheffer_star(S_a: torch.Tensor, S_b: torch.Tensor) -> torch.Tensor:
    """Redheffer star product: combine two adjacent S-matrices.

    Both S_a and S_b are (W, 2, 2) where each 2×2 has scalar elements
    (no mode coupling — scalar TE/TM formulation).

    Stable formulation (Li 1996) — all operations are scalar:
      D₁ = 1 / (1 − a₂₂ b₁₁)
      D₂ = 1 / (1 − b₁₁ a₂₂)
      s₁₁ = a₁₁ + a₁₂ · D₁ · b₁₁ · a₂₁
      s₁₂ = a₁₂ · D₁ · b₁₂
      s₂₁ = b₂₁ · D₂ · a₂₁
      s₂₂ = b₂₂ + b₂₁ · D₂ · a₂₂ · b₁₂

    Shapes: all (W, 2, 2), returns (W, 2, 2)
    """
    a11 = S_a[..., 0, 0]  # (W,)
    a12 = S_a[..., 0, 1]
    a21 = S_a[..., 1, 0]
    a22 = S_a[..., 1, 1]

    b11 = S_b[..., 0, 0]
    b12 = S_b[..., 0, 1]
    b21 = S_b[..., 1, 0]
    b22 = S_b[..., 1, 1]

    D1 = 1.0 / (1.0 - a22 * b11)
    D2 = 1.0 / (1.0 - b11 * a22)

    S = torch.zeros_like(S_a)
    S[..., 0, 0] = a11 + a12 * D1 * b11 * a21
    S[..., 0, 1] = a12 * D1 * b12
    S[..., 1, 0] = b21 * D2 * a21
    S[..., 1, 1] = b22 + b21 * D2 * a22 * b12
    return S


# ──────────────────────────────────────────────
# Core computation
# ──────────────────────────────────────────────


def stack_smatrix(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelengths_m: torch.Tensor,
    theta0: torch.Tensor,
    n_incident: torch.Tensor,
    n_substrate: torch.Tensor,
    te: bool = True,
) -> torch.Tensor:
    """Total scattering matrix for a multilayer stack.

    Parameters
    ----------
    n_layers : (N,) complex128
        Refractive index of each layer (top → bottom).
    thicknesses : (N,) float64 [m]
        Physical thickness of each layer.
    wavelengths_m : (W,) float64 [m]
        Wavelength grid.
    theta0 : float or () tensor [rad]
        Angle of incidence in the incident medium.
    n_incident : complex128
        Incident medium index (vacuum: 1.0).
    n_substrate : complex128
        Substrate index.
    te : bool
        True → TE,  False → TM.

    Returns
    -------
    S_total : (W, 2, 2) complex128
        Total S-matrix of the stack (incident side port 0, substrate port 1).
    """
    N = n_layers.shape[0]
    W = wavelengths_m.shape[0]

    n_inc = n_incident.expand(W).to(torch.complex128)
    n_sub = n_substrate.expand(W).to(torch.complex128)

    n_b = n_layers.unsqueeze(0).expand(W, N).contiguous().to(torch.complex128)
    d_b = thicknesses.unsqueeze(0).expand(W, N).contiguous()
    theta0_b = torch.as_tensor(theta0, dtype=torch.float64).expand(W)

    k0 = 2.0 * math.pi / wavelengths_m  # (W,)
    sin_theta0 = torch.sin(theta0_b)
    n0_sin2 = ((n_inc * sin_theta0) ** 2).real  # (W,) — real for vacuum incident

    # k_z and admittance for each layer
    kz_all = torch.zeros(W, N, dtype=torch.complex128, device=n_layers.device)
    eta_all = torch.zeros(W, N, dtype=torch.complex128, device=n_layers.device)
    for j in range(N):
        kz_all[:, j] = _kz(n_b[:, j], k0, n0_sin2)
        eta_all[:, j] = _admittance(n_b[:, j], kz_all[:, j], k0, te)

    # Start with the top interface: incident medium → first layer
    eta_inc = _admittance(n_inc, _kz(n_inc, k0, n0_sin2), k0, te)
    S_total = _interface_smatrix(eta_inc, eta_all[:, 0])  # (W, 2, 2)

    # Iterate: layer propagation + next interface, layer by layer
    for j in range(N):
        # Layer propagation S-matrix
        S_layer = _layer_smatrix(kz_all[:, j], d_b[:, j])  # (W, 2, 2)
        S_total = _redheffer_star(S_total, S_layer)

        # Interface to the next layer (or substrate)
        if j < N - 1:
            S_iface = _interface_smatrix(eta_all[:, j], eta_all[:, j + 1])
        else:
            S_iface = _interface_smatrix(
                eta_all[:, j], _admittance(n_sub, _kz(n_sub, k0, n0_sin2), k0, te)
            )
        S_total = _redheffer_star(S_total, S_iface)

    return S_total


def reflectivity(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelengths_m: torch.Tensor,
    theta0: torch.Tensor,
    n_incident: torch.Tensor = torch.tensor(1.0 + 0.0j),
    n_substrate: torch.Tensor = torch.tensor(1.0 + 0.0j),
    te: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Intensity reflectivity and complex reflection coefficient.

    Parameters
    ----------
    n_layers : (N,) complex128
    thicknesses : (N,) float64 [m]
    wavelengths_m : (W,) float64 [m]
    theta0 : float or () tensor [rad]
    n_incident : complex128, optional
    n_substrate : complex128, optional
    te : bool, optional (default: True → TE)

    Returns
    -------
    R : (W,) float64
        Intensity reflectivity [0, 1].
    r : (W,) complex128
        Complex reflection coefficient.
    """
    S = stack_smatrix(
        n_layers,
        thicknesses,
        wavelengths_m,
        theta0,
        n_incident,
        n_substrate,
        te=te,
    )
    # Reflection coefficient r = S₁₁ (port 0 → port 0 = reflected wave)
    r = S[..., 0, 0]
    R = (r * r.conj()).real
    return R, r


# ──────────────────────────────────────────────
# Convenience wrappers
# ──────────────────────────────────────────────


def reflectivity_at_wavelength(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelength_m: float,
    theta0: float = 0.0,
    n_incident: torch.Tensor = torch.tensor(1.0 + 0.0j),
    n_substrate: torch.Tensor = torch.tensor(1.0 + 0.0j),
    te: bool = True,
) -> float:
    """Single-wavelength reflectivity (scalar wrapper)."""
    wl = torch.tensor([wavelength_m], dtype=torch.float64)
    R, _ = reflectivity(n_layers, thicknesses, wl, theta0, n_incident, n_substrate, te=te)
    return float(R.item())


def reflectivity_scan(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    wavelength_range: Tuple[float, float, int],
    theta0: float = 0.0,
    n_incident: torch.Tensor = torch.tensor(1.0 + 0.0j),
    n_substrate: torch.Tensor = torch.tensor(1.0 + 0.0j),
    te: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Wavelength-scan reflectivity.

    Returns (wavelengths, R) both 1D tensors.
    """
    npts = wavelength_range[2]
    wl = torch.linspace(wavelength_range[0], wavelength_range[1], npts)
    R, _ = reflectivity(n_layers, thicknesses, wl, theta0, n_incident, n_substrate, te=te)
    return wl, R
