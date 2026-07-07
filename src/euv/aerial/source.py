"""
Illumination source shapes for partially coherent EUV imaging.

Provides functions to generate 2D source intensity distributions
on the pupil grid: conventional (disk), annular, dipole, quasar
(CQuad), and custom free-form maps.

All functions return normalised (sum = 1) PyTorch float64 tensors
on the specified device.
"""

from __future__ import annotations

import math

import torch


def conventional(
    grid: int,
    sigma: float = 0.8,
    device: str = "cpu",
) -> torch.Tensor:
    """Conventional (filled-disk) illumination.

    Parameters
    ----------
    grid : int
        Pixel grid size (grid × grid).
    sigma : float
        Partial coherence factor σ = NA_illum / NA_proj (0 < σ ≤ 1).
    device : str

    Returns
    -------
    source : (grid, grid) float64
    """
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2
    mask = r2 <= sigma**2
    src = mask.to(torch.float64)
    return src / src.sum()


def annular(
    grid: int,
    sigma_in: float = 0.3,
    sigma_out: float = 0.8,
    device: str = "cpu",
) -> torch.Tensor:
    """Annular illumination (ring).

    Parameters
    ----------
    grid : int
    sigma_in : float
        Inner sigma (0 ≤ sigma_in < sigma_out).
    sigma_out : float
        Outer sigma (sigma_in < sigma_out ≤ 1).
    device : str

    Returns
    -------
    source : (grid, grid) float64
    """
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2
    mask = (r2 <= sigma_out**2) & (r2 >= sigma_in**2)
    src = mask.to(torch.float64)
    return src / src.sum()


def dipole_x(
    grid: int,
    sigma: float = 0.2,
    sigma_out: float = 0.8,
    separation: float = 0.6,
    device: str = "cpu",
) -> torch.Tensor:
    """X-dipole illumination (two poles on the x-axis).

    Parameters
    ----------
    grid : int
    sigma : float
        Radius of each pole.
    sigma_out : float
        Outer sigma limit.
    separation : float
        Pole centre-to-centre distance in σ units.
    device : str

    Returns
    -------
    source : (grid, grid) float64
    """
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2
    half = separation / 2.0
    pole_r = (fx - half) ** 2 + fy**2 <= sigma**2
    pole_l = (fx + half) ** 2 + fy**2 <= sigma**2
    mask = (pole_r | pole_l) & (r2 <= sigma_out**2)
    src = mask.to(torch.float64)
    return src / src.sum()


def dipole_y(
    grid: int,
    sigma: float = 0.2,
    sigma_out: float = 0.8,
    separation: float = 0.6,
    device: str = "cpu",
) -> torch.Tensor:
    """Y-dipole illumination (two poles on the y-axis)."""
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2
    half = separation / 2.0
    pole_u = fx**2 + (fy - half) ** 2 <= sigma**2
    pole_d = fx**2 + (fy + half) ** 2 <= sigma**2
    mask = (pole_u | pole_d) & (r2 <= sigma_out**2)
    src = mask.to(torch.float64)
    return src / src.sum()


def quasar(
    grid: int,
    sigma: float = 0.2,
    sigma_out: float = 0.8,
    opening_angle_deg: float = 30.0,
    device: str = "cpu",
) -> torch.Tensor:
    """Quasar (CQuad) illumination — four poles at 45°.

    Parameters
    ----------
    grid : int
    sigma : float
        Pole radius.
    sigma_out : float
        Outer sigma limit.
    opening_angle_deg : float
        Angular width of each pole [°].
    device : str

    Returns
    -------
    source : (grid, grid) float64
    """
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2
    r = torch.sqrt(fx**2 + fy**2)

    centres = [
        (0.5, 0.5),
        (-0.5, 0.5),
        (-0.5, -0.5),
        (0.5, -0.5),
    ]
    mask = torch.zeros_like(fx, dtype=torch.bool)
    for cx, cy in centres:
        pole = (fx - cx * sigma) ** 2 + (fy - cy * sigma) ** 2 <= sigma**2
        mask = mask | pole
    mask = mask & (r2 <= sigma_out**2)
    src = mask.to(torch.float64)
    return src / src.sum()


def custom(
    intensity_map: torch.Tensor,
    device: str = "cpu",
) -> torch.Tensor:
    """Custom free-form source from a 2D intensity map.

    Parameters
    ----------
    intensity_map : (grid, grid) float64
        Non-negative intensity values (will be normalised).

    Returns
    -------
    source : (grid, grid) float64
    """
    src = intensity_map.to(torch.float64).clamp(min=0.0)
    total = src.sum()
    if total > 0:
        src = src / total
    return src


# ── Internal ──────────────────────────────────


def _meshgrid(grid: int, device: str) -> tuple[torch.Tensor, torch.Tensor]:
    """Normalised frequency coordinates in [-1, 1]."""
    x = torch.linspace(-1.0, 1.0, grid, device=device)
    return torch.meshgrid(x, x, indexing="ij")