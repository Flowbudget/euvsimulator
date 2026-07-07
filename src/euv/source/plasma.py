"""
Parametric LPP Sn-plasma source model for EUV lithography.

Models the laser-produced plasma (LPP) tin droplet source used in
ASML NXE scanners.  The source emits strongly in a narrow band around
13.5 nm (the Sn⁸⁺–Sn¹⁴⁺ unresolved transition array, UTA) with a
weaker out-of-band tail spanning DUV through IR.

Key quantities
--------------
*In-band*        — 13.5 ± 0.5 % nm  (13.35–13.65 nm, ~1.84 eV BW)
*Conversion eff* — 2–5 % of total laser power converted to in-band EUV
*Angular dist*   — Lambertian (cos θ) or narrow Gaussian
*Power target*   — ~250 W at intermediate focus (ASML NXE:3800E)

References
----------
.. [1] Mizoguchi et al. "LPP-EUV light source development for high
       volume manufacturing." Proc. SPIE 10957 (2019).
.. [2] Fomenkov et al. "Laser-produced plasma light source for EUV
       lithography." J. Phys. D: Appl. Phys. 50 (2017).
.. [3] ASML NXE:3800E specifications.  https://www.asml.com
"""

from __future__ import annotations

import dataclasses
from typing import Literal

import numpy as np
from scipy import constants
from scipy.special import erfc

from euv.constants import (
    EUV_ENERGY_EV,
    EUV_WAVELENGTH_NM,
    nm_to_eV,
)

# ──────────────────────────────────────────────────────────
# Spectral model parameters
# ──────────────────────────────────────────────────────────

_IN_BAND_CENTRE_NM: float = 13.5
"""Peak Sn UTA emission wavelength [nm]."""

_IN_BAND_HWHM_NM: float = 0.135
"""Half-width at half-maximum (±1 % of centre) [nm]."""

_IN_BAND_FWHM_NM: float = 2.0 * _IN_BAND_HWHM_NM
"""Full-width at half-maximum [nm]."""

_IN_BAND_SIGMA_EV: float = 0.92
"""Standard deviation of the in-band Gaussian in energy [eV]."""

_OOB_DUV_LAMBDA_1: float = 200.0
"""DUV tail centre wavelength [nm] — broad plasma continuum."""

_OOB_DUV_LAMBDA_2: float = 400.0
"""DUV tail secondary centre [nm]."""

_OOB_IR_LAMBDA: float = 10_600.0
"""CO₂ drive laser wavelength (10.6 μm) [nm]."""

# ──────────────────────────────────────────────────────────
# Angular distribution parameters
# ──────────────────────────────────────────────────────────

_LAMBERTIAN_NORM: float = 1.0 / constants.pi
"""Normalisation factor so that ∫ cosθ dΩ = 1 over a hemisphere."""

# ──────────────────────────────────────────────────────────
# Calibration parameters
# ──────────────────────────────────────────────────────────

_NXE_IN_BAND_POWER_W: float = 250.0
"""Nominal in-band power at intermediate focus [W] — NXE:3800E."""

_NXE_REPETITION_RATE_HZ: float = 50_000.0
"""LPP burst repetition rate [Hz]."""

_NXE_PULSE_ENERGY_MJ: float = 50.0
"""Typical drive laser pulse energy [mJ]."""


# ══════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════


@dataclasses.dataclass(frozen=True)
class LPPPlasmaSource:
    """Parametric LPP tin-plasma source model.

    Parameters
    ----------
    in_band_power_w : float
        Nominal in-band power at intermediate focus [W].
        Default matches ASML NXE specifications (~250 W).
    ce_fraction : float
        Conversion efficiency fraction (in-band / total laser power).
        Typical range: 0.02–0.05 (2–5 %).
    oob_duv_fraction : float
        Fraction of total emitted power in the DUV band
        (140–400 nm).  Fittable parameter.
    oob_ir_fraction : float
        Fraction of total emitted power at the drive-laser
        wavelength (10.6 μm).  Fittable parameter.
    angular_model : {'lambertian', 'gaussian'}
        Angular emission profile.
    gaussian_sigma_deg : float
        Standard deviation of the Gaussian angular distribution [°].
        Only used when *angular_model* = ``'gaussian'``.
    """

    in_band_power_w: float = _NXE_IN_BAND_POWER_W
    ce_fraction: float = 0.04
    oob_duv_fraction: float = 0.15
    oob_ir_fraction: float = 0.10
    angular_model: Literal["lambertian", "gaussian"] = "lambertian"
    gaussian_sigma_deg: float = 30.0

    # ── Derived properties ──────────────────────────────

    @property
    def total_power_w(self) -> float:
        """Total emitted power summed over all spectral bands [W]."""
        ib = self.in_band_power_w
        return ib / (1.0 - self.oob_duv_fraction - self.oob_ir_fraction)

    @property
    def laser_power_w(self) -> float:
        """Drive laser power incident on the tin droplet [W]."""
        return self.in_band_power_w / self.ce_fraction

    @property
    def in_band_bandwidth_nm(self) -> float:
        """In-band full width at half maximum [nm]."""
        return _IN_BAND_FWHM_NM

    @property
    def in_band_bandwidth_ev(self) -> float:
        """In-band energy bandwidth [eV]."""
        e_high = nm_to_eV(_IN_BAND_CENTRE_NM - _IN_BAND_HWHM_NM)
        e_low = nm_to_eV(_IN_BAND_CENTRE_NM + _IN_BAND_HWHM_NM)
        return e_high - e_low

    # ── Spectral emission ───────────────────────────────

    def spectral_irradiance(
        self,
        wavelength_nm: np.ndarray,
        theta_deg: float = 0.0,
    ) -> np.ndarray:
        """Spectral irradiance at a given wavelength array [W / nm].

        The model superposes three contributions:

        1. **In-band** — Gaussian centred at 13.5 nm (FWHM 0.27 nm).
        2. **DUV tail** — broad Gaussian at 200 nm plus a secondary
           component at 400 nm.
        3. **IR tail** — narrow Gaussian at 10.6 μm (CO₂ laser
           scatter + plasma IR continuum).

        Parameters
        ----------
        wavelength_nm : (N,) ndarray
            Wavelength grid [nm].
        theta_deg : float
            Observation angle from the surface normal [°].

        Returns
        -------
        irradiance : (N,) ndarray
            Spectral irradiance [W / nm] at *theta_deg*.
        """
        lam = np.asarray(wavelength_nm, dtype=np.float64)
        d_lam = np.gradient(lam) if len(lam) > 1 else np.array([1.0])

        # Angular factor
        ang = self._angular_factor(theta_deg)

        # ── In-band ─────────────────────────────────────
        ib = _gaussian(lam, _IN_BAND_CENTRE_NM, _IN_BAND_HWHM_NM / _fwhm_to_sigma())
        ib_int = np.trapezoid(ib, lam) if len(lam) > 1 else ib.sum() * d_lam[0]
        ib = (self.in_band_power_w / ib_int) * ib if ib_int > 0.0 else ib

        # ── DUV tail ────────────────────────────────────
        duv1 = _gaussian(lam, _OOB_DUV_LAMBDA_1, 80.0)
        duv2 = _gaussian(lam, _OOB_DUV_LAMBDA_2, 120.0)
        duv = 0.7 * duv1 + 0.3 * duv2
        duv_int = np.trapezoid(duv, lam) if len(lam) > 1 else duv.sum() * d_lam[0]
        duv_power = self.oob_duv_fraction * self.total_power_w
        duv = (duv_power / duv_int) * duv if duv_int > 0.0 else duv

        # ── IR tail (10.6 μm) ───────────────────────────
        ir = _gaussian(lam, _OOB_IR_LAMBDA, 500.0)
        ir_int = np.trapezoid(ir, lam) if len(lam) > 1 else ir.sum() * d_lam[0]
        ir_power = self.oob_ir_fraction * self.total_power_w
        ir = (ir_power / ir_int) * ir if ir_int > 0.0 else ir

        return ang * (ib + duv + ir)

    def in_band_spectrum(
        self,
        wavelength_nm: np.ndarray,
        theta_deg: float = 0.0,
    ) -> np.ndarray:
        """In-band-only spectral irradiance [W / nm].

        Convenience wrapper around :meth:`spectral_irradiance` that
        zeros out-of-band emission.
        """
        lam = np.asarray(wavelength_nm, dtype=np.float64)
        total = self.spectral_irradiance(lam, theta_deg)
        lo = _IN_BAND_CENTRE_NM - _IN_BAND_HWHM_NM
        hi = _IN_BAND_CENTRE_NM + _IN_BAND_HWHM_NM
        total[(lam < lo) | (lam > hi)] = 0.0
        return total

    def spectral_radiance(
        self,
        wavelength_nm: np.ndarray,
        theta_deg: float = 0.0,
    ) -> np.ndarray:
        """Spectral radiance [W / (nm · sr)].

        Irradiance divided by the angular-profile solid angle.
        """
        ang = self._angular_factor(theta_deg)
        norm = self._angular_normalisation()
        return self.spectral_irradiance(wavelength_nm, theta_deg) / (ang * norm + 1e-30)

    # ── Angular distribution ────────────────────────────

    def angular_factor(self, theta_deg: float | np.ndarray) -> float | np.ndarray:
        """Angular emission factor I(theta) = I(0) * f(theta).

        Parameters
        ----------
        theta_deg : float or ndarray
            Polar angle measured from the surface normal [degrees].

        Returns
        -------
        factor : float or ndarray
            f(theta) — dimensionless, f(0) = 1.
        """
        return self._angular_factor(theta_deg)

    def _angular_factor(self, theta_deg: float | np.ndarray) -> float | np.ndarray:
        theta = np.deg2rad(theta_deg)
        if self.angular_model == "lambertian":
            return np.cos(np.clip(theta, 0.0, np.pi / 2.0))
        elif self.angular_model == "gaussian":
            sigma = np.deg2rad(self.gaussian_sigma_deg)
            return np.exp(-0.5 * (theta / sigma) ** 2)
        else:
            raise ValueError(f"Unknown angular model: {self.angular_model}")

    def _angular_normalisation(self) -> float:
        r"""∫ f(θ) dΩ over the hemisphere.

        For Lambertian:  ∫₀^{π/2} cosθ · 2π sinθ dθ = π.
        Returns the integral value.
        """
        if self.angular_model == "lambertian":
            return constants.pi
        elif self.angular_model == "gaussian":
            sigma = np.deg2rad(self.gaussian_sigma_deg)
            # ∫₀^{π/2} exp(-θ²/(2σ²)) · 2π sinθ dθ ≈ 2πσ²  for σ ≪ π/2
            # Numerical integration is safer for arbitrary σ.
            th = np.linspace(0.0, np.pi / 2.0, 2001)
            integrand = (
                np.exp(-0.5 * (th / sigma) ** 2) * 2.0 * np.pi * np.sin(th)
            )
            return np.trapezoid(integrand, th)
        else:
            raise ValueError(f"Unknown angular model: {self.angular_model}")

    # ── Power budget ────────────────────────────────────

    def power_budget(self) -> dict[str, float]:
        """Return a summary of the source power budget.

        Returns
        -------
        budget : dict
            Keys: ``'laser_power_w'``, ``'in_band_w'``, ``'oob_duv_w'``,
            ``'oob_ir_w'``, ``'total_emitted_w'``, ``'ce_fraction'``.
        """
        return {
            "laser_power_w": self.laser_power_w,
            "in_band_w": self.in_band_power_w,
            "oob_duv_w": self.oob_duv_fraction * self.total_power_w,
            "oob_ir_w": self.oob_ir_fraction * self.total_power_w,
            "total_emitted_w": self.total_power_w,
            "ce_fraction": self.ce_fraction,
        }

    def dose_rate(
        self,
        collection_solid_angle_sr: float = 2.0 * constants.pi * (1.0 - np.cos(np.deg2rad(30.0))),
        losses: float = 0.7,
    ) -> float:
        """In-band power that reaches the wafer plane [W].

        Parameters
        ----------
        collection_solid_angle_sr : float
            Solid angle subtended by the collector mirror [sr].
            Default: 30° half-angle cone (≈0.84 sr).
        losses : float
            Cumulative loss factor through the optical train
            (collector, illuminator, projection optics, mask).
            Expressed as a fraction of power *lost* (0.7 = 70 % loss).

        Returns
        -------
        wafer_power_w : float
        """
        coll_frac = collection_solid_angle_sr / self._angular_normalisation()
        return self.in_band_power_w * coll_frac * (1.0 - losses)

    # ── Representation ──────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"in_band={self.in_band_power_w:.1f} W, "
            f"CE={self.ce_fraction:.2%}, "
            f"angular={self.angular_model})"
        )


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════


def _gaussian(
    x: np.ndarray,
    centre: float,
    sigma: float,
) -> np.ndarray:
    """Unnormalised Gaussian (peak = 1 at centre)."""
    return np.exp(-0.5 * ((x - centre) / sigma) ** 2)


def _fwhm_to_sigma() -> float:
    r"""Ratio FWHM / σ for a Gaussian: 2√(2 ln 2) ≈ 2.355."""
    return 2.0 * np.sqrt(2.0 * np.log(2.0))