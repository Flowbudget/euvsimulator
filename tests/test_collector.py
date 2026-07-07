"""Tests for the collector geometry module."""

import math

import pytest

from euv.optics.collector import (
    CollectorGeometry,
    ellipsoid_intersection,
    nxe_collector,
)


class TestCollectorGeometry:
    """Verify collector geometry calculations."""

    def test_eccentricity(self):
        """Ellipsoid with a=1, b=0.8 should have known eccentricity.

        e = c/a where c = sqrt(a² - b²).
        """
        a, b = 1.0, 0.8
        c = math.sqrt(a**2 - b**2)
        col = CollectorGeometry(
            semi_major=a,
            semi_minor=b,
            focal_distance=2.0 * c,
            grazing_angle_deg=15.0,
        )
        expected_e = c / a
        assert col.eccentricity == pytest.approx(expected_e, rel=1e-6)

    def test_collection_efficiency_full(self):
        """Full 2π sr (θ=90°) → 50% geometric efficiency."""
        col = CollectorGeometry(
            semi_major=1.0,
            semi_minor=1.0,
            focal_distance=0.5,
            grazing_angle_deg=15.0,
            collection_half_angle_deg=90.0,
            reflectivity=0.7,
        )
        assert col.collection_efficiency() == pytest.approx(0.5, rel=1e-3)
        assert col.effective_collection() == pytest.approx(0.35, rel=1e-3)

    def test_collection_efficiency_hemisphere(self):
        """θ=180° → 100% geometric efficiency."""
        col = CollectorGeometry(
            semi_major=1.0,
            semi_minor=1.0,
            focal_distance=0.5,
            grazing_angle_deg=15.0,
            collection_half_angle_deg=180.0,
            reflectivity=0.7,
        )
        assert col.collection_efficiency() == pytest.approx(1.0, rel=1e-3)

    def test_nxe_collector(self):
        """NXE collector should have plausible values."""
        col = nxe_collector()
        assert col.semi_major > 0
        assert col.semi_minor > 0
        assert col.focal_distance > 0
        assert 10.0 <= col.grazing_angle_deg <= 30.0


class TestEllipsoidIntersection:
    """Verify the ray-ellipsoid intersection utility."""

    def test_forward_intersection(self):
        """A ray from (-c, 0, 0) along +z should hit the ellipsoid.

        Standard ellipsoid: foci at (±c, 0, 0).
        """
        a = 1.0
        b = 0.8
        c = math.sqrt(a**2 - b**2)

        # Source at one focus, pointing roughly toward the other focus
        hit = ellipsoid_intersection(
            source=(-c, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),  # along z
            a=a,
            b=b,
            c=c,
        )
        assert hit is not None
        # The intersection should be on the ellipsoid surface
        inv_b2 = 1.0 / (b * b)
        inv_a2 = 1.0 / (a * a)
        val = hit[0] ** 2 * inv_b2 + hit[1] ** 2 * inv_b2 + hit[2] ** 2 * inv_a2
        assert val.item() == pytest.approx(1.0, abs=1e-6)

    def test_miss(self):
        """A ray pointing away from the ellipsoid should miss."""
        hit = ellipsoid_intersection(
            source=(0.0, 2.0, 0.0),  # far from surface
            direction=(0.0, 1.0, 0.0),  # pointing further away
            a=1.0,
            b=1.0,
            c=0.0,
        )
        assert hit is None

    def test_no_intersection(self):
        """Ray that never hits the ellipsoid (discriminant < 0)."""
        hit = ellipsoid_intersection(
            source=(10.0, 0.0, 0.0),
            direction=(0.0, 1.0, 0.0),
            a=1.0,
            b=1.0,
            c=0.0,
        )
        assert hit is None
