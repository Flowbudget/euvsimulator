"""GDSII import/export wrapper for EUV mask layout geometry.

Uses ``gdstk`` as the GDSII backend.  The internal representation is a
:class:`MaskGeometry` dataclass that maps ``(layer, datatype)`` pairs to
lists of polygon vertex arrays.

Typical EUV mask patterns:

- **Line/space arrays** — periodic absorber lines on a dark-field mask
- **Contact arrays** — square or circular contact holes on a clear-field mask
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    import gdstk

    _HAS_GDSTK = True
except ImportError:  # pragma: no cover
    _HAS_GDSTK = False


# ──────────────────────────────────────────────
# Internal representation
# ──────────────────────────────────────────────


@dataclass
class MaskGeometry:
    """Mask layout geometry in memory.

    Polygons are stored as a dictionary keyed by ``(layer, datatype)``,
    where each value is a list of ``(N, 2)`` numpy arrays of vertex
    coordinates in **nanometres**.

    Parameters
    ----------
    polygons : dict
        Maps ``(layer, datatype)`` tuples to lists of vertex arrays.
    cell_name : str
        Name of the source GDS cell (default: ``"TOP"``).
    """

    polygons: Dict[Tuple[int, int], List[np.ndarray]] = field(default_factory=dict)
    cell_name: str = "TOP"

    # ── convenience accessors ──────────────────

    def layers(self) -> List[Tuple[int, int]]:
        """Return sorted list of ``(layer, datatype)`` keys present."""
        return sorted(self.polygons.keys())

    @property
    def polygon_count(self) -> int:
        """Total number of polygons across all layers."""
        return sum(len(v) for v in self.polygons.values())

    def total_area_nm2(self) -> float:
        """Sum of all polygon areas in nm²."""
        total = 0.0
        for verts_list in self.polygons.values():
            for verts in verts_list:
                total += _polygon_area(verts)
        return total

    # ── GDSII export ───────────────────────────

    def to_gds(
        self,
        path: Union[str, Path],
        *,
        unit: float = 1e-9,
        precision: float = 1e-12,
    ) -> None:
        """Write the geometry to a GDSII file.

        Parameters
        ----------
        path : str | Path
            Output ``.gds`` file path.
        unit : float
            Database unit in **metres** (default ``1e-9`` → nanometre).
        precision : float
            User-unit per database-unit (default ``1e-12``).
        """
        if not _HAS_GDSTK:
            raise ImportError("gdstk is required to write GDSII files.")

        lib = gdstk.Library(unit=unit, precision=precision)
        cell = lib.new_cell(self.cell_name)

        for (layer, datatype), verts_list in self.polygons.items():
            for verts in verts_list:
                polygon = gdstk.Polygon(verts, layer=layer, datatype=datatype)
                cell.add(polygon)

        lib.write_gds(str(path))

    # ── equality helper for tests ──────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MaskGeometry):
            return NotImplemented
        if set(self.polygons.keys()) != set(other.polygons.keys()):
            return False
        for key in self.polygons:
            if len(self.polygons[key]) != len(other.polygons[key]):
                return False
            for a, b in zip(self.polygons[key], other.polygons[key]):
                if a.shape != b.shape or not np.allclose(a, b):
                    return False
        return True


# ──────────────────────────────────────────────
# GDSII reading
# ──────────────────────────────────────────────


def load_gds(
    path: Union[str, Path],
    *,
    cell_name: Optional[str] = None,
    layer_filter: Optional[Sequence[Tuple[int, int]]] = None,
    flatten: bool = True,
) -> MaskGeometry:
    """Load a GDSII file into a :class:`MaskGeometry`.

    Parameters
    ----------
    path : str | Path
        Path to the ``.gds`` file.
    cell_name : str, optional
        Name of the cell to load.  If *None*, the top-level cell with the
        most polygons is auto-selected.
    layer_filter : sequence of (layer, datatype), optional
        If provided, only polygons matching one of these pairs are kept.
    flatten : bool
        If *True* (default), flatten all cell references into a single cell.

    Returns
    -------
    MaskGeometry
    """
    if not _HAS_GDSTK:
        raise ImportError("gdstk is required to read GDSII files.")

    lib = gdstk.read_gds(str(path))
    cells = lib.cells

    if not cells:
        raise ValueError(f"No cells found in GDSII file: {path}")

    # Resolve target cell
    if cell_name is not None:
        target = [c for c in cells if c.name == cell_name]
        if not target:
            raise ValueError(f"Cell '{cell_name}' not found in {path}")
        target_cell = target[0]
    else:
        top_level = lib.top_level()
        if len(top_level) == 1:
            target_cell = top_level[0]
        else:
            # Pick the cell with the most polygons (direct or via refs)
            target_cell = max(
                cells,
                key=lambda c: len(c.get_polygons() if flatten else c.polygons),
            )

    # Collect polygons
    raw_polygons = target_cell.get_polygons() if flatten else target_cell.polygons

    geometry: Dict[Tuple[int, int], List[np.ndarray]] = {}
    for poly in raw_polygons:
        key = (poly.layer, poly.datatype)
        if layer_filter is not None and key not in layer_filter:
            continue
        verts = np.asarray(poly.points, dtype=np.float64)
        geometry.setdefault(key, []).append(verts)

    return MaskGeometry(polygons=geometry, cell_name=target_cell.name)


# ──────────────────────────────────────────────
# EUV mask pattern generators
# ──────────────────────────────────────────────


def make_linespace(
    period_nm: float,
    line_width_nm: float,
    height_nm: float,
    nlines: int = 1,
    *,
    layer: int = 0,
    datatype: int = 0,
    origin: Tuple[float, float] = (0.0, 0.0),
) -> List[np.ndarray]:
    """Create a periodic line/space array.

    Each line is a rectangle of width ``line_width_nm`` and height
    ``height_nm``, repeated every ``period_nm``.

    Parameters
    ----------
    period_nm : float
        Centre-to-centre pitch in nm.
    line_width_nm : float
        Line width in nm.
    height_nm : float
        Line height (y-direction) in nm.
    nlines : int
        Number of lines (default 1).
    layer : int
        GDS layer number (default 0).
    datatype : int
        GDS datatype (default 0).
    origin : (float, float)
        Bottom-left corner of the first line (default ``(0, 0)``).

    Returns
    -------
    list of (N, 2) ndarray
        Polygon vertex arrays (one per line).
    """
    x0, y0 = origin
    half_w = line_width_nm / 2.0
    polygons: List[np.ndarray] = []

    for i in range(nlines):
        cx = x0 + i * period_nm
        left = cx - half_w
        right = cx + half_w
        top = y0 + height_nm
        verts = np.array(
            [
                [left, y0],
                [right, y0],
                [right, top],
                [left, top],
            ],
            dtype=np.float64,
        )
        polygons.append(verts)

    return polygons


def make_contact_array(
    period_x_nm: float,
    period_y_nm: float,
    contact_width_nm: float,
    contact_height_nm: float,
    nx: int = 1,
    ny: int = 1,
    *,
    layer: int = 1,
    datatype: int = 0,
    origin: Tuple[float, float] = (0.0, 0.0),
) -> List[np.ndarray]:
    """Create a rectangular array of contact holes.

    Each contact is a rectangle centred at each grid point.  On an EUV
    clear-field mask, contacts are typically openings (absorber removed),
    so the polygon represents the opening in the absorber layer.

    Parameters
    ----------
    period_x_nm, period_y_nm : float
        Centre-to-centre pitch in the x / y direction [nm].
    contact_width_nm, contact_height_nm : float
        Contact opening size in x / y [nm].
    nx, ny : int
        Number of contacts in x / y (default 1 each).
    layer : int
        GDS layer number (default 1).
    datatype : int
        GDS datatype (default 0).
    origin : (float, float)
        Bottom-left corner of the first contact (default ``(0, 0)``).

    Returns
    -------
    list of (N, 2) ndarray
        Polygon vertex arrays (one per contact).
    """
    x0, y0 = origin
    half_w = contact_width_nm / 2.0
    half_h = contact_height_nm / 2.0
    polygons: List[np.ndarray] = []

    for iy in range(ny):
        cy = y0 + iy * period_y_nm + half_h
        for ix in range(nx):
            cx = x0 + ix * period_x_nm + half_w
            left = cx - half_w
            right = cx + half_w
            bottom = cy - half_h
            top = cy + half_h
            verts = np.array(
                [
                    [left, bottom],
                    [right, bottom],
                    [right, top],
                    [left, top],
                ],
                dtype=np.float64,
            )
            polygons.append(verts)

    return polygons


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _polygon_area(verts: np.ndarray) -> float:
    """Signed area of a polygon using the shoelace formula."""
    x = verts[:, 0]
    y = verts[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))
