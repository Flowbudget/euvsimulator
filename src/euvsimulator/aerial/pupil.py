"""Projection pupil — numerical aperture, anamorphic scaling, Zernike
aberrations, and flare.

All functions return PyTorch tensors on the specified device and
are differentiable where applicable.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import torch


def pupil_grid(
    grid: int,
    na: float = 0.33,
    mag_x: float = 4.0,
    mag_y: float = 4.0,
    device: str = "cpu",
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Normalised pupil coordinates.

    ``fx``, ``fy`` run from −1 to 1 in both axes; 1 is the largest pupil
    cut-off frequency.  For an isotropic system (``mag_x == mag_y``) the
    pupil is the unit circle, whatever the NA -- the NA only enters when the
    coordinates are mapped to physical frequencies (see
    :func:`pupil_cutoff_frequencies`).

    For an anamorphic system the cut-off seen from the mask differs per
    axis, NA/(mag·λ), so the pupil is an ellipse; the coordinates are then
    normalised to the larger cut-off NA/(min(mag_x, mag_y)·λ) and
    ``inside`` is ``(fx/sx)² + (fy/sy)² ≤ 1`` with ``s = min(mag)/mag``.
    On the wafer side the pupil of such a system is still a circle.

    Parameters
    ----------
    grid : int
        Pixel grid (grid × grid).
    na : float
        Numerical aperture (not needed for the normalised geometry).
    mag_x, mag_y : float
        Projection magnification (4× for conventional, 4×/8× for
        High-NA anamorphic).
    device : str

    Returns
    -------
    fx : (grid, grid) float64
        Normalised x-frequency (−1 to 1).
    fy : (grid, grid) float64
        Normalised y-frequency.
    inside : (grid, grid) bool
        True for points inside the pupil.
    """
    x = torch.linspace(-1.0, 1.0, grid, device=device)
    y = torch.linspace(-1.0, 1.0, grid, device=device)
    fx, fy = torch.meshgrid(x, y, indexing="ij")
    sx, sy = _anamorphic_semi_axes(mag_x, mag_y)
    inside = (fx / sx) ** 2 + (fy / sy) ** 2 <= 1.0
    return fx, fy, inside


def _anamorphic_semi_axes(mag_x: float, mag_y: float) -> Tuple[float, float]:
    """Pupil semi-axes in coordinates normalised to the larger mask-side cut-off."""
    if mag_x <= 0 or mag_y <= 0:
        raise ValueError(f"magnifications must be positive, got {mag_x}, {mag_y}")
    m = min(mag_x, mag_y)
    return m / mag_x, m / mag_y


def pupil_cutoff_frequencies(
    na: float,
    mag_x: float = 4.0,
    mag_y: float = 4.0,
    wavelength_nm: float = 13.5,
) -> Tuple[float, float]:
    """Mask-side pupil cut-off frequencies (fc_x, fc_y) in 1/nm: NA/(mag·λ)."""
    if na <= 0 or wavelength_nm <= 0:
        raise ValueError(f"na and wavelength must be positive, got {na}, {wavelength_nm}")
    _anamorphic_semi_axes(mag_x, mag_y)
    return na / (mag_x * wavelength_nm), na / (mag_y * wavelength_nm)


def defocus_pupil(
    grid: int,
    na: float = 0.33,
    defocus_nm: float = 0.0,
    wavelength_nm: float = 13.5,
    device: str = "cpu",
) -> torch.Tensor:
    """Apply defocus to a pupil function.

    Defocus is modelled as a quadratic phase term:
        W_defocus = defocus_nm * NA² * (fx² + fy²)

    Parameters
    ----------
    defocus_nm : float
        Defocus distance in nm (positive = defocus, negative = under-focus).
    wavelength_nm : float
        Exposure wavelength in nm.

    Returns
    -------
    defocus_phase : (grid, grid) complex128
        Complex phase factor to multiply with the pupil.
    """
    fx, fy, _ = pupil_grid(grid, na, device=device)
    # Quadratic phase: W = (2π/λ) * 0.5 * defocus * NA² * (fx² + fy²)
    rho_sq = fx**2 + fy**2
    phase = (2.0 * math.pi / (wavelength_nm * 1e-9)) * (defocus_nm * 1e-9) * na**2 * rho_sq / 2.0
    return torch.exp(1j * phase.to(torch.complex128))


def circular_pupil(
    grid: int,
    na: float = 0.33,
    device: str = "cpu",
) -> torch.Tensor:
    """Simple circular pupil (1 inside, 0 outside).

    Returns
    -------
    pupil : (grid, grid) float64
    """
    fx, fy, _ = pupil_grid(grid, na, device=device)
    inside = fx**2 + fy**2 <= 1.0
    return inside.to(torch.float64)


# ── Zernike polynomials ───────────────────────


def _zernike_radial(n: int, m: int, rho: torch.Tensor) -> torch.Tensor:
    """Radial Zernike polynomial R_n^m(rho).

    rho : normalized radial coordinate (0 ≤ rho ≤ 1).
    """
    R = torch.zeros_like(rho)
    for k in range((n - abs(m)) // 2 + 1):
        num = (-1) ** k * math.factorial(n - k)
        den = (
            math.factorial(k)
            * math.factorial((n + abs(m)) // 2 - k)
            * math.factorial((n - abs(m)) // 2 - k)
        )
        R = R + (num / den) * rho ** (n - 2 * k)
    return R


def zernike(
    n: int,
    m: int,
    fx: torch.Tensor,
    fy: torch.Tensor,
) -> torch.Tensor:
    """Zernike polynomial Z_n^m on a normalised pupil grid.

    Parameters
    ----------
    n : int
        Radial order (n ≥ 0).
    m : int
        Azimuthal frequency (−n ≤ m ≤ n, n−|m| even).
    fx, fy : (grid, grid) float64
        Normalised pupil coordinates.

    Returns
    -------
    Z : (grid, grid) float64
    """
    rho = torch.sqrt(fx**2 + fy**2)
    theta = torch.atan2(fy, fx)
    R = _zernike_radial(n, m, rho)
    inside = rho <= 1.0
    if m == 0:
        Z = R
    elif m > 0:
        Z = R * torch.cos(abs(m) * theta)
    else:
        Z = R * torch.sin(abs(m) * theta)
    Z[~inside] = 0.0
    return Z


def apply_aberrations(
    pupil: torch.Tensor,
    fx: torch.Tensor,
    fy: torch.Tensor,
    zernike_coeffs: List[Tuple[int, int, float]],
) -> torch.Tensor:
    """Apply Zernike wavefront aberrations to a pupil function.

    Parameters
    ----------
    pupil : (grid, grid) complex128
        Unaberrated pupil transmission (amplitude + phase).
    fx, fy : (grid, grid) float64
        Pupil coordinates.
    zernike_coeffs : list of (n, m, coeff)
        Zernike coefficients in radians RMS.

    Returns
    -------
    aberrated : (grid, grid) complex128
        Pupil with phase = original + Σ coeff · Z_n^m.
    """
    wavefront = torch.zeros_like(pupil, dtype=torch.float64)
    for n, m, coeff in zernike_coeffs:
        wavefront = wavefront + coeff * zernike(n, m, fx, fy)
    return pupil * torch.exp(1j * wavefront)


def anamorphic_pupil(
    grid: int,
    na: float = 0.55,
    mag_x: float = 4.0,
    mag_y: float = 8.0,
    device: str = "cpu",
) -> torch.Tensor:
    """High-NA anamorphic pupil (different X/Y magnification), mask side.

    Seen from the mask the cut-off is NA/(mag_x·λ) in x and NA/(mag_y·λ) in
    y, so with 4×/8× the pupil is an ellipse half as wide in y as in x (see
    :func:`pupil_grid` for the normalisation).  Before 2026-09-25 this
    returned the full square for every input.

    This is a mask-side pupil; :func:`euvsimulator.aerial.abbe.abbe_image`
    works in wafer-side coordinates (cut-off NA/λ), where the pupil of an
    anamorphic system is a circle.  The central obscuration of the EXE
    pupil is not modelled.

    Returns
    -------
    pupil : (grid, grid) float64
        Transmission (1 inside the elliptical pupil, 0 outside).
    """
    _, _, inside = pupil_grid(grid, na, mag_x, mag_y, device)
    return inside.to(torch.float64)
