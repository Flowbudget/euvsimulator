"""
Optical constants for EUV lithography (13.5 nm, 91.84 eV).

All refractive indices are *n* + i*k (complex) at 13.5 nm (91.84 eV).
Values from CXRO/Henke atomic scattering factors (f₁, f₂):

    n = 1 - (r₀ λ² / 2π) · N · f₁
    k = (r₀ λ² / 2π) · N · f₂

where r₀ = 2.81794e-15 m (classical electron radius).

References
----------
• B.L. Henke, E.M. Gullikson, J.C. Davis, Atomic Data and Nuclear
  Data Tables 54(2), 181–342 (1993). — doi:10.1006/adnd.1993.1013
• CXRO X-Ray Database: https://henke.lbl.gov/optical_constants/
• ELitho implementation (MIT) — takahashi-edalab/elitho

All CXRO/Henke data is in the public domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

EUV_WAVELENGTH_NM: float = 13.5  # 91.84 eV
"""Primary EUV wavelength for lithography (13.5 nm, 2 % in-band window)."""

EUV_ENERGY_EV: float = 91.84
"""Photon energy corresponding to 13.5 nm."""

EUV_BANDWIDTH_EV: float = 1.84
"""2 % in-band window at 13.5 nm (90.84–92.68 eV)."""

NA_LOW: float = 0.33
"""Numerical aperture for current-generation EUV scanners (NXE:3400C)."""

NA_HIGH: float = 0.55
"""Numerical aperture for High-NA EUV scanners (EXE:5000)."""


@dataclass(frozen=True)
class Material:
    """Optical properties of a material at 13.5 nm.

    Parameters
    ----------
    name : str
        Chemical symbol or common name.
    n : float
        Real part of refractive index at 13.5 nm.
    k : float
        Imaginary part (extinction coefficient) at 13.5 nm.
    density : float
        Mass density in g/cm³.
    description : str, optional
        Additional notes (source, layer role).
    """

    name: str
    n: float
    k: float
    density: float
    description: str = ""


# fmt: off
# --- EUV optical constants table (13.5 nm, CXRO/Henke + ELitho validated) ---

MATERIALS: Dict[str, Material] = {
    "Mo":  Material("Mo",  0.9238,  0.00637, 10.28, "Molybdenum — spacer in Mo/Si multilayer mirrors"),
    "Si":  Material("Si",  0.9990,  0.00183,  2.33, "Silicon — absorber in Mo/Si multilayer mirrors"),
    "Ru":  Material("Ru",  0.8863,  0.01710, 12.37, "Ruthenium — capping layer protector"),
    "Ta":  Material("Ta",  0.9424,  0.03860, 16.65, "Tantalum — primary absorber material"),
    "TaN": Material("TaN", 0.9440,  0.04000, 14.30, "Tantalum nitride — absorber (alternative)"),
    "TaBN":Material("TaBN",0.9450,  0.03950, 13.80, "Tantalum boron nitride — absorber"),
    "Sn":  Material("Sn",  0.8870,  0.03140,  7.31, "Tin — LPP plasma source material"),
    "SiO2":Material("SiO2",0.9800,  0.01000,  2.65, "Silicon dioxide — buffer/capping"),
    "C":   Material("C",   0.9602,  0.00676,  2.25, "Carbon — contaminant film"),
    "Cr":  Material("Cr",  0.9320,  0.01610,  7.19, "Chromium — hardmask"),
    "Au":  Material("Au",  0.8640,  0.04140, 19.32, "Gold — calibration reference"),
    "Ni":  Material("Ni",  0.9216,  0.02612,  8.91, "Nickel — EUV detector coating"),
    "Al":  Material("Al",  0.9620,  0.00443,  2.70, "Aluminium — window material"),
}
# fmt: on


def refractive_index(element: str) -> Tuple[float, float]:
    """Return (n, k) for a given element at 13.5 nm.

    Parameters
    ----------
    element : str
        Chemical symbol (case-sensitive, e.g. 'Mo', 'Si').

    Returns
    -------
    n, k : float
        Real and imaginary parts of refractive index.

    Raises
    ------
    KeyError
        If the element is not in the database.
    """
    mat = MATERIALS[element]
    return mat.n, mat.k


def multilayer_permittivity(
    layer_materials: list[str],
    layer_thicknesses_nm: list[float],
    wavelength_nm: float = EUV_WAVELENGTH_NM,
) -> np.ndarray:
    """Build a 1-D permittivity profile through a multilayer stack.

    Parameters
    ----------
    layer_materials : list of str
        Material names from top to bottom.
    layer_thicknesses_nm : list of float
        Thickness of each layer in nm.
    wavelength_nm : float, optional
        Wavelength used for refractive index lookup. Default 13.5 nm.

    Returns
    -------
    permittivity : ndarray of shape (N_layers,)
        Complex permittivity ε = (n + ik)² for each layer.
    """
    eps = []
    for mat, thick in zip(layer_materials, layer_thicknesses_nm):
        n, k = refractive_index(mat)
        eps.append(complex(n, k) ** 2)
    return np.array(eps)


# ---------------------------------------------------------------------------
# CXRO/Henke query helper
# ---------------------------------------------------------------------------

CXRO_URL: str = (
    "https://henke.lbl.gov/optical_constants/"
    "getdb.pl?name={element}&low_eV={low}&high_eV={high}&num={num}"
)
"""Base URL for the CXRO/Henke atomic scattering factor database."""


def cxro_url(element: str, low_eV: float = 10.0, high_eV: float = 30000.0, num: int = 1000) -> str:
    """Generate a URL to download CXRO/Henke data for an element.

    Parameters
    ----------
    element : str
        Atomic symbol (e.g. 'Mo').
    low_eV, high_eV : float
        Energy range in eV.
    num : int
        Number of energy points.

    Returns
    -------
    url : str
        HTTPS URL for the F1/F2 query.
    """
    return CXRO_URL.format(element=element, low=low_eV, high=high_eV, num=num) + "&flag=1"