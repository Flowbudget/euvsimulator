"""Material database — CXRO/Henke atomic scattering factors and refractive indices.

Loads the CXRO f₁, f₂ tables (``data/cxro/*.csv``) for all 92 elements and
computes complex refractive indices at arbitrary photon energies.

Theory
------
The refractive index is *n* + i*k:

    n = 1 — δ            where  δ = (r₀ λ² / 2π) · N · f₁
    k = (r₀ λ² / 2π) · N · f₂

with:
    r₀ — classical electron radius
    λ — photon wavelength [m]
    N — atomic number density [atoms/m³] = ρ · N_A / A
    f₁, f₂ — atomic scattering factors (CXRO/Henke)

References
----------
B.L. Henke, E.M. Gullikson, J.C. Davis, Atomic Data and Nuclear Data Tables
54(2), 181–342 (1993).  https://doi.org/10.1006/adnd.1993.1013
CXRO database: https://henke.lbl.gov/optical_constants/
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from euv.constants import (
    AVOGADRO,
    CLASSICAL_ELECTRON_RADIUS,
    EUV_ENERGY_EV,
)

# ──────────────────────────────────────────────
# Path resolution
# ──────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cxro"
"""Directory containing ``<Element>.csv`` for Z = 1–92."""


# ──────────────────────────────────────────────
# Element metadata (Z, symbol, atomic mass, density)
# ──────────────────────────────────────────────

# fmt: off
_ELEMENT_TABLE: Dict[str, Tuple[int, float, float]] = {
    # symbol: (Z, atomic_mass_g_mol, density_g_cm3)
    "H":  ( 1,  1.008,    0.0899e-3),  # gas @ STP
    "He": ( 2,  4.0026,   0.1785e-3),
    "Li": ( 3,  6.94,     0.534),
    "Be": ( 4,  9.0122,   1.848),
    "B":  ( 5, 10.81,     2.37),
    "C":  ( 6, 12.011,    2.25),      # graphite
    "N":  ( 7, 14.007,    1.251e-3),  # gas
    "O":  ( 8, 15.999,    1.429e-3),  # gas
    "F":  ( 9, 18.998,    1.696e-3),  # gas
    "Ne": (10, 20.180,    0.8999e-3), # gas
    "Na": (11, 22.990,    0.971),
    "Mg": (12, 24.305,    1.738),
    "Al": (13, 26.982,    2.70),
    "Si": (14, 28.085,    2.33),
    "P":  (15, 30.974,    1.82),
    "S":  (16, 32.06,     2.07),
    "Cl": (17, 35.45,     3.12e-3),   # gas
    "Ar": (18, 39.948,    1.784e-3),  # gas
    "K":  (19, 39.098,    0.862),
    "Ca": (20, 40.078,    1.54),
    "Sc": (21, 44.956,    2.99),
    "Ti": (22, 47.867,    4.506),
    "V":  (23, 50.942,    5.96),
    "Cr": (24, 51.996,    7.19),
    "Mn": (25, 54.938,    7.21),
    "Fe": (26, 55.845,    7.874),
    "Co": (27, 58.933,    8.86),
    "Ni": (28, 58.693,    8.912),
    "Cu": (29, 63.546,    8.96),
    "Zn": (30, 65.38,     7.134),
    "Ga": (31, 69.723,    5.904),
    "Ge": (32, 72.630,    5.323),
    "As": (33, 74.922,    5.776),
    "Se": (34, 78.971,    4.809),
    "Br": (35, 79.904,    3.12e-3),   # liquid density used as proxy
    "Kr": (36, 83.798,    3.749e-3),  # gas
    "Rb": (37, 85.468,    1.532),
    "Sr": (38, 87.62,     2.64),
    "Y":  (39, 88.906,    4.472),
    "Zr": (40, 91.224,    6.506),
    "Nb": (41, 92.906,    8.57),
    "Mo": (42, 95.95,    10.28),
    "Tc": (43, 98.0,     11.5),       # synthetic, estimate
    "Ru": (44, 101.07,   12.37),
    "Rh": (45, 102.91,   12.41),
    "Pd": (46, 106.42,   12.02),
    "Ag": (47, 107.87,   10.501),
    "Cd": (48, 112.41,    8.69),
    "In": (49, 114.82,    7.31),
    "Sn": (50, 118.71,    7.287),
    "Sb": (51, 121.76,    6.685),
    "Te": (52, 127.60,    6.232),
    "I":  (53, 126.90,    4.93),
    "Xe": (54, 131.29,    5.894e-3),  # gas
    "Cs": (55, 132.91,    1.873),
    "Ba": (56, 137.33,    3.594),
    "La": (57, 138.91,    6.145),
    "Ce": (58, 140.12,    6.77),
    "Pr": (59, 140.91,    6.773),
    "Nd": (60, 144.24,    7.007),
    "Pm": (61, 145.0,     7.26),      # estimate
    "Sm": (62, 150.36,    7.52),
    "Eu": (63, 151.96,    5.243),
    "Gd": (64, 157.25,    7.895),
    "Tb": (65, 158.93,    8.229),
    "Dy": (66, 162.50,    8.55),
    "Ho": (67, 164.93,    8.795),
    "Er": (68, 167.26,    9.066),
    "Tm": (69, 168.93,    9.321),
    "Yb": (70, 173.05,    6.965),
    "Lu": (71, 174.97,    9.84),
    "Hf": (72, 178.49,   13.31),
    "Ta": (73, 180.95,   16.654),
    "W":  (74, 183.84,   19.25),
    "Re": (75, 186.21,   21.02),
    "Os": (76, 190.23,   22.61),
    "Ir": (77, 192.22,   22.56),
    "Pt": (78, 195.08,   21.46),
    "Au": (79, 196.97,   19.32),
    "Hg": (80, 200.59,   13.5336),    # liquid
    "Tl": (81, 204.38,   11.85),
    "Pb": (82, 207.2,    11.342),
    "Bi": (83, 208.98,    9.79),
    "Po": (84, 209.0,     9.20),      # estimate
    "At": (85, 210.0,     7.0),       # estimate
    "Rn": (86, 222.0,     9.73e-3),   # gas estimate
    "Fr": (87, 223.0,     2.48),      # estimate
    "Ra": (88, 226.0,     5.5),       # estimate
    "Ac": (89, 227.0,    10.07),
    "Th": (90, 232.04,   11.72),
    "Pa": (91, 231.04,   15.37),
    "U":  (92, 238.03,   18.95),
}
# fmt: on


# ──────────────────────────────────────────────
# Material record
# ──────────────────────────────────────────────


@dataclass
class Material:
    """Optical properties of an element or compound at a given photon energy.

    Parameters
    ----------
    symbol : str
        Chemical symbol or compound identifier.
    energy_eV : float
        Photon energy [eV].
    n : float
        Real part of refractive index.
    k : float
        Imaginary part (extinction coefficient).
    density : float
        Mass density [g/cm³].
    """

    symbol: str
    energy_eV: float
    n: float
    k: float
    density: float

    @property
    def wavelength_nm(self) -> float:
        """Wavelength [nm] corresponding to the photon energy."""
        from euv.constants import eV_to_nm

        return eV_to_nm(self.energy_eV)

    @property
    def epsilon(self) -> complex:
        """Complex permittivity ε = (n + ik)² (dimensionless)."""
        return complex(self.n, self.k) ** 2

    @property
    def delta(self) -> float:
        """Refractive index decrement δ = 1 — n."""
        return 1.0 - self.n

    @property
    def absorption_length_nm(self) -> float:
        """1/e absorption length [nm] = λ / (4π k)."""
        if self.k <= 0:
            return float("inf")
        return self.wavelength_nm / (4.0 * math.pi * self.k)


# ──────────────────────────────────────────────
# CXRO data loader
# ──────────────────────────────────────────────


class CXROTable:
    """In-memory representation of the CXRO f₁, f₂ scattering factors.

    Lazy-loads CSV data on first access.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing ``<Element>.csv`` files.
    """

    def __init__(self, data_dir: str | Path = DATA_DIR) -> None:
        self._data_dir = Path(data_dir)
        self._tables: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    def _load(self, symbol: str) -> None:
        """Load f₁, f₂ data for *symbol* from CSV."""
        csv_path = self._data_dir / f"{symbol}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(
                f"CXRO table not found: {csv_path}. "
                f"Run ``python scripts/download_cxro.py`` first."
            )

        energies: List[float] = []
        f1_vals: List[Optional[float]] = []
        f2_vals: List[float] = []

        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) < 3:
                    continue
                try:
                    energy = float(row[0])
                except (ValueError, IndexError):
                    continue
                # f1 = None (empty) means -9999 in the raw data
                f1 = float(row[1]) if row[1].strip() else None
                f2 = float(row[2]) if row[2].strip() else None
                if f2 is None:
                    continue
                energies.append(energy)
                f1_vals.append(f1)
                f2_vals.append(f2)

        if not energies:
            raise ValueError(f"No valid data in {csv_path}")

        self._tables[symbol] = (
            np.array(energies, dtype=np.float64),
            np.array(f1_vals, dtype=np.float64),
            np.array(f2_vals, dtype=np.float64),
        )

    def has_element(self, symbol: str) -> bool:
        """Check if CXRO data exists for this element."""
        return (self._data_dir / f"{symbol}.csv").exists()

    def get_f1f2(self, symbol: str, energy_eV: float) -> Tuple[float, float]:
        """Interpolate f₁, f₂ at a given photon energy.

        Parameters
        ----------
        symbol : str
            Chemical symbol (e.g. ``'Mo'``, ``'Si'``).
        energy_eV : float
            Photon energy in eV.

        Returns
        -------
        f1, f2 : float
            Atomic scattering factors at *energy_eV*.

        Raises
        ------
        KeyError
            If the element is not loaded.
        ValueError
            If *energy_eV* is outside the CXRO table range.
        """
        if symbol not in self._tables:
            self._load(symbol)

        energies, f1_raw, f2_raw = self._tables[symbol]

        if energy_eV < energies[0] or energy_eV > energies[-1]:
            raise ValueError(
                f"Energy {energy_eV:.1f} eV outside CXRO range for {symbol} "
                f"[{energies[0]:.1f}, {energies[-1]:.1f}] eV"
            )

        # Linear interpolation (log-log for better accuracy)
        log_e = np.log(energies)
        log_e_target = np.log(energy_eV)

        # f1 — only interpolate where f1 is not -9999 (NaN)
        valid = ~np.isnan(f1_raw) & ~np.isinf(f1_raw)
        if valid.sum() < 2:
            # Fall back to f2-based Kramers–Kronig or just use nearest
            f1 = float(np.interp(energy_eV, energies[valid], f1_raw[valid]))
        else:
            f1 = float(np.interp(energy_eV, energies, f1_raw))

        # f2 — log-log interpolation
        log_f2 = np.log(np.maximum(f2_raw, 1e-30))
        f2 = float(np.exp(np.interp(log_e_target, log_e, log_f2)))

        return f1, f2

    def refractive_index(
        self,
        symbol: str,
        energy_eV: float = EUV_ENERGY_EV,
        density_g_cm3: float | None = None,
    ) -> Tuple[float, float]:
        """Compute refractive index *n* + i*k from CXRO data.

        Parameters
        ----------
        symbol : str
            Chemical symbol.
        energy_eV : float
            Photon energy [eV].
        density_g_cm3 : float, optional
            Material density in g/cm³.  Uses standard density from the
            element table if omitted.

        Returns
        -------
        n, k : float
            Real and imaginary parts of refractive index.
        """
        if density_g_cm3 is None:
            _, _, density_g_cm3 = self._element_info(symbol)

        f1, f2 = self.get_f1f2(symbol, energy_eV)

        # Atomic number density N [atoms/m³] = ρ · N_A / A
        _, atomic_mass, _ = self._element_info(symbol)
        N = density_g_cm3 * 1e3 * AVOGADRO / (atomic_mass * 1e-3)  # atoms/m³

        # Wavelength [m] from energy
        from euv.constants import PLANCK_EV, SPEED_OF_LIGHT

        lam = PLANCK_EV * SPEED_OF_LIGHT / energy_eV  # [m]

        # Pre-factor
        prefactor = CLASSICAL_ELECTRON_RADIUS * lam**2 / (2.0 * math.pi)

        delta = prefactor * N * f1
        k = prefactor * N * f2

        n = 1.0 - delta
        return n, max(k, 0.0)  # k must be non-negative

    def get_material(self, symbol: str, energy_eV: float = EUV_ENERGY_EV) -> Material:
        """Build a ``Material`` instance from CXRO data.

        Parameters
        ----------
        symbol : str
            Chemical symbol.
        energy_eV : float
            Photon energy [eV].

        Returns
        -------
        Material
            Optical properties at the requested energy.
        """
        z, _, density = self._element_info(symbol)
        n, k = self.refractive_index(symbol, energy_eV)
        return Material(
            symbol=symbol,
            energy_eV=energy_eV,
            n=n,
            k=k,
            density=density,
        )

    def list_elements(self) -> List[str]:
        """Return all symbols for which CXRO data is available."""
        elements = []
        for fname in sorted(os.listdir(self._data_dir)):
            if fname.endswith(".csv"):
                elements.append(fname[:-4])
        return elements

    @staticmethod
    def _element_info(symbol: str) -> Tuple[int, float, float]:
        """Return (Z, atomic_mass_g_mol, density_g_cm3) for *symbol*."""
        try:
            return _ELEMENT_TABLE[symbol]
        except KeyError:
            raise KeyError(f"Unknown element '{symbol}'. " f"CXRO loader covers Z = 1–92.")


# ──────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────

_DEFAULT_TABLE: CXROTable | None = None


def get_cxro_table() -> CXROTable:
    """Get or create the default CXRO table singleton."""
    global _DEFAULT_TABLE
    if _DEFAULT_TABLE is None:
        _DEFAULT_TABLE = CXROTable()
    return _DEFAULT_TABLE
