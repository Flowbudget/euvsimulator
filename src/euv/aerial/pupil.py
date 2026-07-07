"""
Projection pupil — numerical aperture, anamorphic scaling, Zernike
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

    Parameters
    ----------
    grid : int
        Pixel grid (grid × grid).
    na : float
        Numerical aperture.
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
        True for points inside the pupil: fx² + fy² ≤ 1.
    """
    x = torch.linspace(-na / mag_x, na / mag_x, grid, device=device)
    y = torch.linspace(-na / mag_y, na / mag_y, grid, device=device)
    fx, fy = torch.meshgrid(x, y, indexing="ij")
    inside = fx**2 + fy**2 <= na**2
    return fx, fy, inside


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
    _, _, inside = pupil_grid(grid, na, device=device)
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
    """High-NA anamorphic pupil (different X/Y magnification).

    Returns
    -------
    pupil : (grid, grid) float64
        Transmission (1 inside the stretched pupil, 0 outside).
    """
    fx, fy, inside = pupil_grid(grid, na, mag_x, mag_y, device)
    return inside.to(torch.float64)