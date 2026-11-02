"""Illumination source shapes for partially coherent EUV imaging.

Provides functions to generate 2D source intensity distributions
on the pupil grid: conventional (disk), annular, dipole, quasar
(CQuad), and custom free-form maps.

All functions return normalised (sum = 1) PyTorch float64 tensors
on the specified device.  The shape functions raise ValueError when
the requested shape covers no grid pixel (instead of returning
0/0 = NaN); custom() returns all zeros for an all-zero map.
"""

from __future__ import annotations

import math
import warnings

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
    return _normalise(mask, "conventional")


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
    if not (0.0 <= sigma_in < sigma_out):
        raise ValueError(
            f"annular() needs 0 <= sigma_in < sigma_out, got sigma_in={sigma_in}, "
            f"sigma_out={sigma_out}"
        )
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2
    mask = (r2 <= sigma_out**2) & (r2 >= sigma_in**2)
    return _normalise(mask, "annular")


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
    return _normalise(mask, "dipole_x")


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
    return _normalise(mask, "dipole_y")


def quasar(
    grid: int,
    sigma: float = 0.2,
    sigma_out: float = 0.8,
    opening_angle_deg: float | None = None,
    device: str = "cpu",
) -> torch.Tensor:
    """Quasar (CQuad) illumination — four circular poles on the diagonals.

    Each pole is a disk of radius *sigma* centred on a 45° diagonal
    (45°, 135°, 225°, 315°) at distance sigma_out - sigma from the
    origin, so it touches the outer limit *sigma_out* from inside and
    spans sigma_out - 2*sigma <= r <= sigma_out.  The centre stays dark.

    Parameters
    ----------
    grid : int
    sigma : float
        Pole radius.  Must satisfy 0 < sigma and
        sigma * (1 + sqrt(2)) < sigma_out so the four poles stay separate.
    sigma_out : float
        Outer sigma limit; the poles touch it from inside.
    opening_angle_deg : float, optional
        Deprecated and ignored.  A circular pole has no free opening angle
        (its angular full width is 2*asin(sigma / (sigma_out - sigma))).
        Passing a value emits a DeprecationWarning.  For annular-sector
        poles with an opening angle use illumination_shape="quasar" with
        sigma_inner and pole_opening_deg in the pipeline (aerial/abbe.py).
    device : str

    Returns
    -------
    source : (grid, grid) float64
    """
    if opening_angle_deg is not None:
        warnings.warn(
            "quasar(): opening_angle_deg is deprecated and ignored; the poles are "
            "disks of radius sigma touching sigma_out from inside",
            DeprecationWarning,
            stacklevel=2,
        )
    if not (sigma > 0.0 and sigma * (1.0 + math.sqrt(2.0)) < sigma_out):
        raise ValueError(
            "quasar() needs 0 < sigma and sigma * (1 + sqrt(2)) < sigma_out for four "
            f"separate poles, got sigma={sigma}, sigma_out={sigma_out}"
        )
    fx, fy = _meshgrid(grid, device)
    r2 = fx**2 + fy**2

    # pole centres on the 45° diagonals at radius sigma_out - sigma
    c = (sigma_out - sigma) / math.sqrt(2.0)
    centres = [
        (c, c),
        (-c, c),
        (-c, -c),
        (c, -c),
    ]
    mask = torch.zeros_like(fx, dtype=torch.bool)
    for cx, cy in centres:
        pole = (fx - cx) ** 2 + (fy - cy) ** 2 <= sigma**2
        mask = mask | pole
    mask = mask & (r2 <= sigma_out**2)
    return _normalise(mask, "quasar")


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
    gx, gy = torch.meshgrid(x, x, indexing="ij")
    return gx, gy


def _normalise(mask: torch.Tensor, what: str) -> torch.Tensor:
    """Turn a boolean source mask into a float64 source with sum 1.

    Raises ValueError for an empty mask instead of returning 0/0 = NaN,
    which abbe_image() would silently turn into an all-zero image.
    """
    src = mask.to(torch.float64)
    total = src.sum()
    if not total > 0:
        step = 2.0 / max(mask.shape[0] - 1, 1)
        raise ValueError(
            f"{what}(): the source covers no grid pixel (grid {mask.shape[0]}, "
            f"pixel step {step:.4g} in sigma units); increase sigma or grid"
        )
    return src / total
