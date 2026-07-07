"""Rasterise GDSII polygon geometry onto a binary permittivity grid for RCWA input.

The core function :func:`rasterize_geometry` samples a mask layer's polygons
onto a uniform Cartesian grid, returning a 2D binary array where 1 indicates
the absorber (patterned) phase and 0 the background (vacuum).

Manhattan (rectilinear) polygons are handled exactly through scanline
point-in-polygon testing.

Use :func:`area_conservation_error` to quantify the fidelity of the
rasterisation against the analytical polygon area.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from euv.io.gds import MaskGeometry

# ──────────────────────────────────────────────
# Core rasteriser
# ──────────────────────────────────────────────


def rasterize_geometry(
    geometry: MaskGeometry,
    layer_key: Tuple[int, int],
    extent_x_nm: float,
    extent_y_nm: float,
    nx: int,
    ny: int,
    *,
    origin: Tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """Rasterise a single layer region onto a binary grid.

    Each grid cell is set to 1 (absorber) if its centre point lies inside
    any polygon of the specified ``layer_key``, and 0 otherwise.

    Parameters
    ----------
    geometry : MaskGeometry
        The loaded mask geometry.
    layer_key : (int, int)
        ``(layer, datatype)`` pair identifying the region to rasterize.
    extent_x_nm, extent_y_nm : float
        Physical extent of the simulation domain in x / y [nm].
    nx, ny : int
        Number of grid points along x / y.
    origin : (float, float)
        Bottom-left corner of the simulation domain [nm] (default ``(0, 0)``).

    Returns
    -------
    grid : (ny, nx) ndarray of bool
        Binary mask.  ``True`` = absorber (pattern layer present).
    """
    if layer_key not in geometry.polygons:
        return np.zeros((ny, nx), dtype=bool)

    x0, y0 = origin
    # Place grid points at pixel centres (not edges) to avoid boundary
    # artifacts with the ray-casting point-in-polygon test.
    dx = extent_x_nm / nx
    dy = extent_y_nm / ny
    x_centres = np.linspace(x0 + dx / 2, x0 + extent_x_nm - dx / 2, nx)
    y_centres = np.linspace(y0 + dy / 2, y0 + extent_y_nm - dy / 2, ny)
    xx, yy = np.meshgrid(x_centres, y_centres, indexing="xy")

    grid = np.zeros((ny, nx), dtype=bool)

    for verts in geometry.polygons[layer_key]:
        inside = _points_in_convex_polygon(xx, yy, verts)
        grid |= inside

    return grid


# ──────────────────────────────────────────────
# Area conservation
# ──────────────────────────────────────────────


def area_conservation_error(
    geometry: MaskGeometry,
    layer_key: Tuple[int, int],
    raster: np.ndarray,
    pixel_area_nm2: float,
) -> float:
    """Compute the relative area error of a rasterised pattern.

    .. math::

       \\varepsilon_\\text{area} =
           \\frac{|A_\\text{exact} - A_\\text{raster}|}{A_\\text{exact}}

    where :math:`A_\\text{exact}` is the total polygon area from the
    shoelace formula and :math:`A_\\text{raster}` is the number of on
    pixels times ``pixel_area_nm2``.

    Parameters
    ----------
    geometry : MaskGeometry
    layer_key : (int, int)
        Layer/datatype to measure.
    raster : (ny, nx) ndarray of bool
        Rasterised binary mask (output of :func:`rasterize_geometry`).
    pixel_area_nm2 : float
        Area of a single raster pixel in nm².

    Returns
    -------
    float
        Relative area error (0 = perfect conservation).
    """
    if layer_key not in geometry.polygons:
        exact_area = 0.0
    else:
        exact_area = sum(_polygon_area(v) for v in geometry.polygons[layer_key])

    if exact_area == 0.0:
        return 0.0 if np.count_nonzero(raster) == 0 else float("inf")

    raster_area_nm2 = float(np.count_nonzero(raster)) * pixel_area_nm2
    return abs(exact_area - raster_area_nm2) / exact_area


# ──────────────────────────────────────────────
# Point-in-polygon (Manhattan / rectilinear)
# ──────────────────────────────────────────────


def _points_in_convex_polygon(
    x: np.ndarray,
    y: np.ndarray,
    verts: np.ndarray,
) -> np.ndarray:
    """Test which of the given grid points lie inside a convex polygon.

    Uses the winding-number / crossing-number method.  Works correctly
    for Manhattan (rectilinear) polygons and any convex polygon.

    Parameters
    ----------
    x, y : (M, N) ndarray
        Meshgrid coordinates.
    verts : (P, 2) ndarray
        Polygon vertices in CCW or CW order (closed or open).

    Returns
    -------
    (M, N) bool ndarray
    """
    # Ensure closed polygon
    if not np.allclose(verts[0], verts[-1]):
        verts = np.concatenate([verts, verts[:1]], axis=0)

    inside = np.zeros_like(x, dtype=bool)
    n = verts.shape[0] - 1

    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[i + 1]

        # Skip horizontal edges (y1 == y2) — they don't cross a horizontal ray
        if y1 == y2:
            continue

        # Ray casting: edge straddles the test point's y
        mask = (y1 > y) != (y2 > y)
        # Compute x-intersection of the edge with the horizontal line at y
        x_intersect = x1 + (x2 - x1) * (y - y1) / (y2 - y1)
        inside ^= mask & (x < x_intersect)

    return inside


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _polygon_area(verts: np.ndarray) -> float:
    """Signed area of a polygon via the shoelace formula."""
    x = verts[:, 0]
    y = verts[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))
