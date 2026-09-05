"""io/rasterize.py had no tests (audit 2026-09-04, E7)."""

from __future__ import annotations

import numpy as np
import pytest

from euvsimulator.io.gds import MaskGeometry
from euvsimulator.io.rasterize import area_conservation_error, rasterize_geometry


def _geom():
    # one 32 x 100 nm rectangle at x in [16, 48) on layer (1, 0)
    rect = np.array([[16.0, 0.0], [48.0, 0.0], [48.0, 100.0], [16.0, 100.0]])
    return MaskGeometry(polygons={(1, 0): [rect]})


def test_pixel_aligned_rectangle_is_exact():
    g = _geom()
    grid = rasterize_geometry(g, (1, 0), extent_x_nm=64.0, extent_y_nm=100.0, nx=64, ny=10)
    assert grid.shape == (10, 64)
    assert grid.dtype == bool
    # cell centres at 0.5, 1.5, ...: inside for 16 <= x < 48 -> columns 16..47
    assert grid[:, 16:48].all() and not grid[:, :16].any() and not grid[:, 48:].any()
    err = area_conservation_error(g, (1, 0), grid, pixel_area_nm2=1.0 * 10.0)
    assert err == pytest.approx(0.0, abs=1e-12)


def test_area_error_bounded_by_one_pixel_row_per_edge():
    g = _geom()
    # dx = 64/48 nm: the 32-nm line is 24 px exactly; still exact
    grid = rasterize_geometry(g, (1, 0), extent_x_nm=64.0, extent_y_nm=100.0, nx=48, ny=5)
    err = area_conservation_error(g, (1, 0), grid, pixel_area_nm2=(64.0 / 48) * 20.0)
    assert err == pytest.approx(0.0, abs=1e-12)
    # dx = 64/50 = 1.28 nm: edges fall inside pixels -> error below one pixel per edge
    grid = rasterize_geometry(g, (1, 0), extent_x_nm=64.0, extent_y_nm=100.0, nx=50, ny=5)
    err = area_conservation_error(g, (1, 0), grid, pixel_area_nm2=1.28 * 20.0)
    assert err < 2 * 1.28 / 32.0


def test_origin_shift_moves_the_pattern():
    g = _geom()
    a = rasterize_geometry(g, (1, 0), 64.0, 100.0, 64, 4)
    b = rasterize_geometry(g, (1, 0), 64.0, 100.0, 64, 4, origin=(8.0, 0.0))
    assert np.array_equal(np.roll(a, -8, axis=1)[:, :56], b[:, :56])


def test_missing_layer_is_an_empty_mask():
    """A layer absent from the GDS is an empty absorber layer (documented
    behaviour in rasterize_geometry), not an error.
    """
    g = _geom()
    grid = rasterize_geometry(g, (7, 0), 64.0, 100.0, 64, 4)
    assert grid.shape == (4, 64) and grid.dtype == bool and not grid.any()
