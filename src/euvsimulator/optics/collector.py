"""Grazing-incidence collector mirror geometry.

In EUV lithography, the plasma source emits isotropically.  A collector
mirror (nested Wolter-type or ellipsoidal shells) gathers the in-band
13.5 nm radiation and delivers it to the illumination optics.

This module provides geometric utilities for the simplest collector
model: a **mono-ellipsoid** grazing-incidence mirror.

References
----------
V. Banine et al., "Free electron laser and EUV sources", EUV Lithography
(SPIE Press, 2018).
ASML NXE collector design (public literature).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import torch


@dataclass
class CollectorGeometry:
    """Geometrical parameters of an ellipsoidal grazing-incidence collector.

    An ellipsoid with focal points *f₁* (plasma source) and *f₂*
    (intermediate focus, IF) reflects rays that pass through *f₁* to
    *f₂* at grazing incidence.

    Parameters
    ----------
    semi_major : float  [m]
        Ellipsoid semi-major axis a.
    semi_minor : float  [m]
        Ellipsoid semi-minor axis b.
    focal_distance : float  [m]
        Distance between the two foci: 2c = 2 sqrt(a² − b²).
    grazing_angle_deg : float
        Nominal grazing angle at the mirror centre [°].
    collection_half_angle_deg : float
        Half-angle subtended by the collector from the source [°].
    reflectivity : float
        Assumed in-band reflectivity at the coating (default: 0.7 ≈ 70 %
        for Mo/Si at grazing incidence).
    """

    semi_major: float
    semi_minor: float
    focal_distance: float
    grazing_angle_deg: float
    collection_half_angle_deg: float = 90.0
    reflectivity: float = 0.7

    @property
    def eccentricity(self) -> float:
        """Ellipsoid eccentricity e = c / a."""
        return self.focal_distance / (2.0 * self.semi_major)

    def collection_efficiency(self) -> float:
        """Fraction of isotropic source emission collected (geometric only).

        For a collector subtending a half-angle *θ*, the solid angle
        fraction is::

            η_geom = 2π (1 − cos θ) / 4π  =  (1 − cos θ) / 2

        For the full 2π sr (θ = 90°), this is 0.5 (50 %).
        """
        theta = math.radians(self.collection_half_angle_deg)
        return (1.0 - math.cos(theta)) / 2.0

    def effective_collection(self) -> float:
        """Geometric collection × mirror reflectivity."""
        return self.collection_efficiency() * self.reflectivity


# ──────────────────────────────────────────────
# Standard ASML-like collector parameters
# ──────────────────────────────────────────────


def nxe_collector() -> CollectorGeometry:
    """Approximate ASML NXE collector geometry (literature-based).

    The NXE:3400C uses nested Wolter-type shells.  This single-ellipsoid
    approximation is an educational simplification.

    References
    ----------
    SPIE vol. 8679, "EUV collector mirror design and performance" (2013).
    """
    # Source-to-IF distance ≈ 1.5 m
    c = 0.75  # half focal distance [m]
    a = 1.0  # semi-major axis [m]
    b = math.sqrt(a**2 - c**2)  # semi-minor axis
    return CollectorGeometry(
        semi_major=a,
        semi_minor=b,
        focal_distance=2.0 * c,
        grazing_angle_deg=15.0,
        collection_half_angle_deg=90.0,
        reflectivity=0.65,
    )


# ──────────────────────────────────────────────
# Ray-trace utilities
# ──────────────────────────────────────────────


def ellipsoid_intersection(
    source: Tuple[float, float, float],
    direction: Tuple[float, float, float],
    a: float,
    b: float,
    c: float,
) -> torch.Tensor | None:
    """Intersect a ray from *source* in *direction* with an ellipsoid.

    The ellipsoid is centred at the origin with the major axis along z::

        x²/b² + y²/b² + (z − z₀)²/a² = 1

    where z₀ is the ellipsoid centre offset associated with the focal
    points at (±c, 0, 0).

    This is a simplified utility intended for geometric validation,
    not for production raytracing.

    Parameters
    ----------
    source : (3,) tuple of float
        Ray origin [m].
    direction : (3,) tuple of float
        Unit direction vector.
    a : float
        Semi-major axis along z [m].
    b : float
        Semi-minor axis (same for x and y, spheroid) [m].
    c : float
        Half focal distance [m].

    Returns
    -------
    hit_point : (3,) tensor or None
        Intersection point in [m], or None if no forward intersection
        exists.
    """
    # Quadratic coefficients: (d · Q · d) t² + 2 (s · Q · d) t + (s · Q · s − 1) = 0
    # Q = diag(1/b², 1/b², 1/a²)  (ellipsoid at origin, foci at ±c on z)
    s = torch.tensor(source, dtype=torch.float64)
    d = torch.tensor(direction, dtype=torch.float64)
    d = d / d.norm()

    inv_b2 = 1.0 / (b * b)
    inv_a2 = 1.0 / (a * a)
    Q = torch.diag(torch.tensor([inv_b2, inv_b2, inv_a2], dtype=torch.float64))

    A = (d @ Q @ d).item()
    B = 2.0 * (s @ Q @ d).item()
    C = (s @ Q @ s).item() - 1.0

    disc = B * B - 4.0 * A * C
    if disc < 0:
        return None

    t1 = (-B + math.sqrt(disc)) / (2.0 * A)
    t2 = (-B - math.sqrt(disc)) / (2.0 * A)

    # Pick the smallest positive t (forward ray)
    t = None
    for ti in (t1, t2):
        if ti > 1e-12:
            if t is None or ti < t:
                t = ti

    if t is None:
        return None

    return s + t * d
