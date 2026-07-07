"""
Spectral weighting and dose-evaluation tools for EUV lithography.

Provides functions for computing in-band efficiency fractions,
photon flux at the wafer plane, and dose-to-wafer mapping in
photons / nm².

References
----------
.. [1] ITRS 2015 — Lithography roadmap.
.. [2] H. J. Levinson, "Principles of Lithography," SPIE Press.
"""

from __future__ import annotations

import numpy as np

from euv.constants import (
    EUV_ENERGY_EV,
    EUV_WAVELENGTH_NM,
    PLANCK_EV,
    SPEED_OF_LIGHT,
    nm_to_eV,
)
from euv.source.plasma import LPPPlasmaSource


# ──────────────────────────────────────────────────────────
# In-band efficiency
# ──────────────────────────────────────────────────────────


def in_band_efficiency(
    source: LPPPlasmaSource | None = None,
    wavelength_nm: np.ndarray | None = None,
    bandwidth_nm: float = 0.27,
) -> float:
    """Fraction of total emitted power that falls inside the EUV band.

    Evaluates the integral of *spectral_irradiance* over the
    bandwidth window divided by the integral over all wavelengths.

    Parameters
    ----------
    source : LPPPlasmaSource or None
        Source model.  If ``None``, a default :class:`LPPPlasmaSource`
        is used.
    wavelength_nm : (N,) ndarray or None
        Wavelength grid [nm].  Should cover from ~1 nm to beyond
        11 μm for an accurate ratio.  If ``None`` a default grid
        spanning 1 nm to 12 μm is generated.
    bandwidth_nm : float
        Half-width of the in-band window centred at 13.5 nm [nm].
        Default 0.27 nm (±1 %).

    Returns
    -------
    efficiency : float
        In-band / total power ratio (0.0–1.0).
    """
    if source is None:
        source = LPPPlasmaSource()

    if wavelength_nm is None:
        # Logarithmically-spaced grid covering 1 nm → 12 μm
        wavelength_nm = np.logspace(0, 4.08, 5000)

    lam = np.asarray(wavelength_nm, dtype=np.float64)
    spectrum = source.spectral_irradiance(lam, theta_deg=0.0)

    lo = EUV_WAVELENGTH_NM - bandwidth_nm
    hi = EUV_WAVELENGTH_NM + bandwidth_nm
    in_band_mask = (lam >= lo) & (lam <= hi)

    total_power = np.trapezoid(spectrum, lam)
    in_band_power = np.trapezoid(spectrum[in_band_mask], lam[in_band_mask])

    if total_power <= 0.0:
        return 0.0
    return in_band_power / total_power


# ──────────────────────────────────────────────────────────
# Photon flux
# ──────────────────────────────────────────────────────────


def photons_per_nm2(
    power_w: float,
    area_nm2: float = 1.0,
    wavelength_nm: float = EUV_WAVELENGTH_NM,
) -> float:
    r"""Photon flux density [photons / (nm² · s)].

    .. math::

        \frac{N}{A \cdot t} = \frac{P \cdot \lambda}{A \cdot h c}

    Parameters
    ----------
    power_w : float
        Optical power at the plane of interest [W].
    area_nm2 : float
        Area over which the power is distributed [nm²].
        Default 1 nm² — returns flux per unit area.
    wavelength_nm : float
        Photon wavelength [nm].  Default 13.5 nm.

    Returns
    -------
    flux : float
        Photon flux [photons / (nm² · s)].
    """
    lam_m = wavelength_nm * 1.0e-9
    energy_per_photon_J = (PLANCK_EV * SPEED_OF_LIGHT) / lam_m
    # Convert eV to J
    e_J = energy_per_photon_J * 1.602176634e-19
    photons_per_second = power_w / e_J if e_J > 0.0 else 0.0
    return photons_per_second / area_nm2


# ──────────────────────────────────────────────────────────
# Dose-to-wafer mapping
# ──────────────────────────────────────────────────────────


def dose_to_wafer(
    source: LPPPlasmaSource | None = None,
    collection_solid_angle_sr: float | None = None,
    losses: float = 0.7,
    exposure_area_nm2: float = 26e6 * 33e6,  # 26 mm × 33 mm field
    exposure_time_s: float | None = None,
    scan_velocity_mm_s: float = 500.0,
    slit_width_mm: float = 3.0,
) -> dict[str, float]:
    """Map source power to wafer-plane dose quantities.

    Computes the in-band power reaching the wafer after collection
    and optical-train losses, then derives photon flux and dose for
    a given exposure area and scan.

    Parameters
    ----------
    source : LPPPlasmaSource or None
    collection_solid_angle_sr : float or None
        Collector solid angle [sr].  If ``None``, uses the default
        from :meth:`LPPPlasmaSource.dose_rate` (30° half-angle cone).
    losses : float
        Fraction of power lost through the optical train (default 0.7).
    exposure_area_nm2 : float
        Wafer-plane exposure field area [nm²].
        Default 26 mm × 33 mm = 8.58e14 nm².
    exposure_time_s : float or None
        Exposure time per field [s].  If ``None``, derived from
        *scan_velocity_mm_s* and *slit_width_mm*.
    scan_velocity_mm_s : float
        Wafer-stage scan velocity [mm / s].  Default 500 mm/s.
    slit_width_mm : float
        Scanning-slit width in the scan direction [mm].  Default 3 mm.

    Returns
    -------
    dose : dict
        Keys:

        - ``'wafer_power_mw'`` — in-band power at wafer [mW].
        - ``'exposure_time_s'`` — time per field [s].
        - ``'dose_mj_cm2'`` — energy density [mJ / cm²].
        - ``'photon_flux_per_nm2_s'`` — photon flux [/ (nm² · s)].
        - ``'photons_per_nm2'`` — total photons per nm² per field.
        - ``'source_power_w'`` — in-band power at source [W].
        - ``'collection_solid_angle_sr'``.
    """
    if source is None:
        source = LPPPlasmaSource()

    # Wafer power after collection + optics
    wafer_power_w = source.dose_rate(
        collection_solid_angle_sr=collection_solid_angle_sr
        if collection_solid_angle_sr is not None
        else 2.0 * np.pi * (1.0 - np.cos(np.deg2rad(30.0))),
        losses=losses,
    )

    # Exposure time
    if exposure_time_s is None:
        exposure_time_s = slit_width_mm / scan_velocity_mm_s

    # Area
    area_cm2 = exposure_area_nm2 * 1.0e-14  # nm² → cm²

    # Dose
    energy_J = wafer_power_w * exposure_time_s
    dose_mj_cm2 = (energy_J * 1.0e3) / area_cm2 if area_cm2 > 0.0 else 0.0

    # Photon flux
    flux = photons_per_nm2(
        power_w=wafer_power_w,
        area_nm2=exposure_area_nm2,
        wavelength_nm=EUV_WAVELENGTH_NM,
    )
    total_photons = flux * exposure_time_s * exposure_area_nm2

    return {
        "wafer_power_mw": wafer_power_w * 1.0e3,
        "exposure_time_s": exposure_time_s,
        "dose_mj_cm2": dose_mj_cm2,
        "photon_flux_per_nm2_s": flux,
        "photons_per_nm2": flux * exposure_time_s,
        "source_power_w": source.in_band_power_w,
        "collection_solid_angle_sr": collection_solid_angle_sr or 0.842,
    }