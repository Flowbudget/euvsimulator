"""Fundamental physical constants and EUV-specific parameters.

All values are in SI units unless otherwise noted.  EUV lithography operates
at 13.5 nm (in-band: 13.35–13.65 nm) corresponding to a photon energy of
91.84 eV.

References
----------
CODATA 2018 — https://physics.nist.gov/cuu/Constants/
CXRO — https://henke.lbl.gov/optical_constants/
"""

from __future__ import annotations

# ──────────────────────────────────────────────
# Fundamental physical constants
# ──────────────────────────────────────────────

SPEED_OF_LIGHT: float = 2.99792458e8
"""Speed of light in vacuum [m/s]."""

PLANCK_CONSTANT: float = 6.62607015e-34
"""Planck constant [J·s]."""

PLANCK_EV: float = 4.135667696e-15
"""Planck constant [eV·s]."""

REDUCED_PLANCK: float = PLANCK_CONSTANT / (2.0 * 3.14159265358979323846)
"""Reduced Planck constant ħ = h / 2π [J·s]."""

ELEMENTARY_CHARGE: float = 1.602176634e-19
"""Elementary charge [C]."""

ELECTRON_MASS: float = 9.1093837015e-31
"""Electron rest mass [kg]."""

ELECTRON_VOLT: float = ELEMENTARY_CHARGE
"""1 eV in Joules [J]."""

AVOGADRO: float = 6.02214076e23
"""Avogadro number [mol⁻¹]."""

BOLTZMANN: float = 1.380649e-23
"""Boltzmann constant [J/K]."""

BOLTZMANN_EV: float = 8.617333262e-5
"""Boltzmann constant [eV/K]."""

CLASSICAL_ELECTRON_RADIUS: float = 2.8179403262e-15
"""Classical electron radius r₀ = e² / (4πε₀ mₑ c²) [m]."""

FINE_STRUCTURE: float = 7.2973525693e-3
"""Fine-structure constant α (dimensionless)."""

# ──────────────────────────────────────────────
# EUV lithography parameters
# ──────────────────────────────────────────────

EUV_WAVELENGTH_NM: float = 13.5
"""Primary EUV lithography wavelength [nm] — 91.84 eV."""

EUV_WAVELENGTH_M: float = EUV_WAVELENGTH_NM * 1e-9
"""Primary EUV wavelength in [m]."""

EUV_ENERGY_EV: float = 91.84
"""Photon energy at 13.5 nm [eV] — h·c/λ."""

EUV_BANDWIDTH_EV: float = 1.84
"""2 % in-band mirror bandwidth at 13.5 nm (90.84–92.68 eV) [eV]."""

EUV_ANGLE_DEG: float = 6.0
"""Chief-ray angle of incidence at the mask [°] — NXE scanner."""

EUV_ANGLE_RAD: float = 6.0 * 3.141592653589793 / 180.0
"""Chief-ray angle of incidence at the mask [rad]."""

NA_LOW: float = 0.33
"""Numerical aperture for current-generation EUV scanners (NXE:3400C)."""

NA_HIGH: float = 0.55
"""Numerical aperture for High-NA EUV scanners (EXE:5000)."""

DEMAGNIFICATION: float = 4.0
"""Projection optics demagnification factor (4×)."""

# ──────────────────────────────────────────────
# Convenience conversion helpers
# ──────────────────────────────────────────────


def eV_to_J(energy_eV: float) -> float:
    """Convert electron-volts to Joules."""
    return energy_eV * ELECTRON_VOLT


def J_to_eV(energy_J: float) -> float:
    """Convert Joules to electron-volts."""
    return energy_J / ELECTRON_VOLT


def nm_to_eV(wavelength_nm: float) -> float:
    """Convert wavelength [nm] to photon energy [eV] via E = hc/λ."""
    return (PLANCK_EV * SPEED_OF_LIGHT) / (wavelength_nm * 1e-9)


def eV_to_nm(energy_eV: float) -> float:
    """Convert photon energy [eV] to wavelength [nm]."""
    return (PLANCK_EV * SPEED_OF_LIGHT) / energy_eV * 1e9
