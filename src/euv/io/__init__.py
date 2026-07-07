"""
Layout I/O — GDSII import/export and rasterization for EUV mask patterns.

Provides
--------
- :class:`MaskGeometry` — internal representation of mask layout geometry
- :func:`load_gds` — load GDSII files into a :class:`MaskGeometry`
- :func:`make_linespace` — create line/space array patterns
- :func:`make_contact_array` — create contact hole array patterns
- :func:`rasterize_geometry` — convert polygon geometry to a binary permittivity grid
- :func:`area_conservation_error` — compute area error of a rasterized pattern
"""

from __future__ import annotations

from euv.io.gds import (
    MaskGeometry,
    load_gds,
    make_linespace,
    make_contact_array,
)
from euv.io.rasterize import (
    rasterize_geometry,
    area_conservation_error,
)

__all__ = [
    "MaskGeometry",
    "load_gds",
    "make_linespace",
    "make_contact_array",
    "rasterize_geometry",
    "area_conservation_error",
]