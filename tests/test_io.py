"""Tests for the GDSII layout I/O module."""

import pytest

from euv.io import MaskGeometry
from euv.io.gds import make_linespace


class TestMakeLineSpace:
    def test_shape(self):
        """make_linespace should return a list of polygon arrays."""
        polys = make_linespace(period_nm=64, line_width_nm=32, height_nm=1000, nlines=5)
        assert len(polys) == 5

    def test_polygon_count(self):
        """5 lines should produce 5 polygons."""
        polys = make_linespace(period_nm=64, line_width_nm=32, height_nm=1000, nlines=5)
        assert len(polys) == 5

    def test_line_width(self):
        """Each polygon should have 4 vertices, correct width."""
        polys = make_linespace(period_nm=64, line_width_nm=32, height_nm=1000, nlines=3)
        for poly in polys:
            assert poly.shape == (4, 2)
            width = poly[:, 0].max() - poly[:, 0].min()
            assert width == pytest.approx(32.0, abs=1.0)

    def test_export_gds(self):
        try:
            import gdstk  # noqa: F401
        except ImportError:
            pytest.skip("gdstk not installed")
        polys = make_linespace(period_nm=64, line_width_nm=32, height_nm=1000, nlines=5)
        geom = MaskGeometry()
        geom.polygons[(0, 0)] = polys
        geom.to_gds("/tmp/test_export.gds")
        import pathlib

        assert pathlib.Path("/tmp/test_export.gds").exists()


class TestMaskGeometry:
    def test_empty(self):
        geom = MaskGeometry()
        assert len(geom.polygons) == 0

    def test_add_polygons(self):
        polys = make_linespace(period_nm=64, line_width_nm=32, height_nm=1000, nlines=3)
        geom = MaskGeometry()
        geom.polygons[(0, 0)] = polys
        assert len(geom.polygons[(0, 0)]) == 3
