"""load_gds and to_gds unit handling (finding r5-gds-1, 2026-10-02).

Measured before the fix: a 32 nm x 2 um line written with a 1 um user unit
was read by load_gds as 0.032 x 2.0 (area 0.064 instead of 64000 nm^2), and
to_gds(unit=1e-6) wrote a 32 nm line as 32 um.
"""

from __future__ import annotations

import numpy as np
import pytest

from euvsimulator.io.gds import MaskGeometry, load_gds, make_linespace

gdstk = pytest.importorskip("gdstk")


def test_load_gds_converts_micrometre_user_unit_to_nm(tmp_path):
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    cell = lib.new_cell("TOP")
    cell.add(gdstk.rectangle((0, 0), (0.032, 2.0)))
    path = tmp_path / "um.gds"
    lib.write_gds(str(path))

    geom = load_gds(path)
    verts = geom.polygons[(0, 0)][0]
    xs = sorted(set(verts[:, 0].tolist()))
    ys = sorted(set(verts[:, 1].tolist()))
    assert xs == pytest.approx([0.0, 32.0], abs=1e-9)
    assert ys == pytest.approx([0.0, 2000.0], abs=1e-9)
    assert geom.total_area_nm2() == pytest.approx(64000.0, rel=1e-9)


def test_load_gds_scales_flattened_references(tmp_path):
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    sub = lib.new_cell("SUB")
    sub.add(gdstk.rectangle((0, 0), (0.032, 2.0)))
    top = lib.new_cell("TOP")
    top.add(gdstk.Reference(sub, (0.064, 0)))
    top.add(gdstk.Reference(sub, (0.128, 0)))
    path = tmp_path / "umref.gds"
    lib.write_gds(str(path))

    geom = load_gds(path)
    assert geom.cell_name == "TOP"
    lefts = sorted(float(v[:, 0].min()) for v in geom.polygons[(0, 0)])
    assert lefts == pytest.approx([64.0, 128.0], abs=1e-9)
    assert geom.total_area_nm2() == pytest.approx(2 * 64000.0, rel=1e-9)


def test_nm_round_trip_is_unchanged(tmp_path):
    polys = make_linespace(period_nm=64, line_width_nm=32, height_nm=1000, nlines=3)
    geom = MaskGeometry(polygons={(0, 0): polys})
    path = tmp_path / "nm.gds"
    geom.to_gds(path)
    back = load_gds(path)
    assert len(back.polygons[(0, 0)]) == 3
    for a, b in zip(polys, back.polygons[(0, 0)]):
        assert np.array_equal(a, b)


def test_to_gds_micrometre_unit_writes_converted_coordinates(tmp_path):
    rect = np.array([[0.0, 0.0], [32.0, 0.0], [32.0, 2000.0], [0.0, 2000.0]])
    geom = MaskGeometry(polygons={(0, 0): [rect]})
    path = tmp_path / "um_out.gds"
    geom.to_gds(path, unit=1e-6, precision=1e-9)

    raw = gdstk.read_gds(str(path))
    assert raw.unit == pytest.approx(1e-6)
    pts = raw.cells[0].polygons[0].points
    assert float(pts[:, 0].max()) == pytest.approx(0.032, abs=1e-12)
    assert float(pts[:, 1].max()) == pytest.approx(2.0, abs=1e-12)

    back = load_gds(path)
    assert back.total_area_nm2() == pytest.approx(64000.0, rel=1e-9)
