"""make_linespace origin convention (finding r5-gds-2, 2026-10-02).

Measured before the fix: make_linespace(64, 32, 100) put the first line at
x in [-16, 16], so one rasterised 64 nm period had duty cycle 0.25 instead
of 0.5.
"""

from __future__ import annotations

import pytest

from euvsimulator.io.gds import MaskGeometry, make_contact_array, make_linespace
from euvsimulator.io.rasterize import rasterize_geometry


def test_make_linespace_origin_is_bottom_left_corner():
    polys = make_linespace(
        period_nm=64, line_width_nm=32, height_nm=100, nlines=2, origin=(5.0, 7.0)
    )
    expected0 = [[5.0, 7.0], [37.0, 7.0], [37.0, 107.0], [5.0, 107.0]]
    expected1 = [[69.0, 7.0], [101.0, 7.0], [101.0, 107.0], [69.0, 107.0]]
    assert polys[0].tolist() == expected0
    assert polys[1].tolist() == expected1


def test_make_linespace_one_period_has_the_nominal_duty_cycle():
    line = make_linespace(period_nm=64, line_width_nm=32, height_nm=100, nlines=1)[0]
    geom = MaskGeometry(polygons={(0, 0): [line]})
    grid = rasterize_geometry(geom, (0, 0), 64.0, 64.0, 64, 4)
    assert grid.mean() == pytest.approx(0.5, abs=1e-12)
    assert grid[:, :32].all() and not grid[:, 32:].any()


def test_make_linespace_matches_make_contact_array_convention():
    line = make_linespace(period_nm=64, line_width_nm=32, height_nm=100, nlines=1)[0]
    contact = make_contact_array(64, 128, 32, 100, nx=1, ny=1)[0]
    assert line.tolist() == contact.tolist()
