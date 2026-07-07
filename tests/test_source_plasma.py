"""Tests for the LPP tin-plasma source model (plasma + spectrum)."""

from __future__ import annotations

import numpy as np
import pytest

from euv.source.plasma import LPPPlasmaSource
from euv.source.spectrum import (
    dose_to_wafer,
    in_band_efficiency,
    photons_per_nm2,
)

# ══════════════════════════════════════════════════════════
# LPPPlasmaSource — construction & defaults
# ══════════════════════════════════════════════════════════


class TestLPPPlasmaSourceDefaults:
    """Verify factory defaults match NXE-class specifications."""

    def test_default_power(self):
        src = LPPPlasmaSource()
        assert src.in_band_power_w == pytest.approx(250.0, rel=1e-3)

    def test_default_ce(self):
        src = LPPPlasmaSource()
        assert src.ce_fraction == pytest.approx(0.04)

    def test_default_angular_model(self):
        src = LPPPlasmaSource()
        assert src.angular_model == "lambertian"

    def test_total_power_greater_than_in_band(self):
        src = LPPPlasmaSource()
        assert src.total_power_w > src.in_band_power_w

    def test_laser_power(self):
        """Laser power = in-band / CE."""
        src = LPPPlasmaSource(in_band_power_w=100.0, ce_fraction=0.02)
        assert src.laser_power_w == pytest.approx(5000.0)


class TestLPPPlasmaSourceCustom:
    """Verify custom parameter overrides."""

    def test_custom_power(self):
        src = LPPPlasmaSource(in_band_power_w=300.0)
        assert src.in_band_power_w == 300.0

    def test_gaussian_angular(self):
        src = LPPPlasmaSource(angular_model="gaussian", gaussian_sigma_deg=20.0)
        assert src.angular_model == "gaussian"
        # Normal incidence → factor = 1
        assert src.angular_factor(0.0) == pytest.approx(1.0)

    def test_custom_oob(self):
        src = LPPPlasmaSource(oob_duv_fraction=0.3, oob_ir_fraction=0.2)
        assert src.total_power_w == pytest.approx(500.0, rel=1e-3)  # 250 / (1 - 0.5)


# ══════════════════════════════════════════════════════════
# Spectral emission
# ══════════════════════════════════════════════════════════


class TestSpectralEmission:
    """Check shape, normalisation, and basic physics of the spectrum."""

    @pytest.fixture
    def source(self):
        return LPPPlasmaSource()

    @pytest.fixture
    def lam(self):
        return np.linspace(1.0, 100.0, 2000)

    def test_spectral_irradiance_shape(self, source, lam):
        spec = source.spectral_irradiance(lam)
        assert spec.shape == lam.shape
        assert np.all(spec >= 0.0)

    def test_in_band_peak_at_13_5_nm(self, source):
        """Spectral irradiance should peak near 13.5 nm."""
        lam = np.linspace(13.0, 14.0, 500)
        spec = source.spectral_irradiance(lam)
        peak_idx = np.argmax(spec)
        assert lam[peak_idx] == pytest.approx(13.5, abs=0.05)

    def test_in_band_power_integrates(self, source):
        """Integrated in-band irradiance over full grid ≈ in_band_power."""
        lam = np.linspace(1.0, 100.0, 5000)
        spec = source.spectral_irradiance(lam)
        lo, hi = 13.35, 13.65
        in_band = spec[(lam >= lo) & (lam <= hi)]
        in_band_lam = lam[(lam >= lo) & (lam <= hi)]
        integral = np.trapezoid(in_band, in_band_lam)
        assert integral == pytest.approx(source.in_band_power_w, rel=0.15)

    def test_zero_power_spectrum(self):
        """Source with zero in-band power should produce zero spectrum."""
        src = LPPPlasmaSource(in_band_power_w=0.0)
        lam = np.linspace(1.0, 100.0, 500)
        spec = src.spectral_irradiance(lam)
        assert np.all(spec == 0.0)

    def test_spectral_radiance_finite(self, source, lam):
        """Radiance should be finite everywhere."""
        rad = source.spectral_radiance(lam)
        assert not np.any(np.isinf(rad))
        assert not np.any(np.isnan(rad))


# ══════════════════════════════════════════════════════════
# Angular distribution
# ══════════════════════════════════════════════════════════


class TestAngularDistribution:
    @pytest.fixture
    def source(self):
        return LPPPlasmaSource()

    def test_lambertian_normal(self, source):
        """cos(0) = 1."""
        assert source.angular_factor(0.0) == pytest.approx(1.0)

    def test_lambertian_45deg(self, source):
        """cos(45°) ≈ 0.707."""
        assert source.angular_factor(45.0) == pytest.approx(np.cos(np.pi / 4), rel=1e-6)

    def test_lambertian_90deg(self, source):
        """cos(90°) = 0."""
        assert source.angular_factor(90.0) == pytest.approx(0.0, abs=1e-15)

    def test_gaussian_off_axis(self):
        """Gaussian factor should decrease monotonically with angle."""
        src = LPPPlasmaSource(angular_model="gaussian", gaussian_sigma_deg=30.0)
        f0 = src.angular_factor(0.0)
        f30 = src.angular_factor(30.0)
        f60 = src.angular_factor(60.0)
        assert f0 > f30 > f60

    def test_angular_factor_array(self, source):
        """Factor should work with ndarray input."""
        angles = np.array([0.0, 30.0, 60.0, 90.0])
        factors = source.angular_factor(angles)
        assert factors.shape == angles.shape
        assert np.all(np.isfinite(factors))


# ══════════════════════════════════════════════════════════
# Power budget
# ══════════════════════════════════════════════════════════


class TestPowerBudget:
    def test_budget_self_consistent(self):
        """Sum of in-band + OOB should equal total emitted."""
        src = LPPPlasmaSource()
        b = src.power_budget()
        allocated = b["in_band_w"] + b["oob_duv_w"] + b["oob_ir_w"]
        assert allocated == pytest.approx(b["total_emitted_w"], rel=1e-10)

    def test_budget_keys(self):
        src = LPPPlasmaSource()
        b = src.power_budget()
        for key in ("laser_power_w", "in_band_w", "ce_fraction"):
            assert key in b

    def test_dose_rate_positive(self):
        src = LPPPlasmaSource()
        dr = src.dose_rate()
        assert dr > 0.0
        # Should be less than in-band power (collection + losses)
        assert dr < src.in_band_power_w


# ══════════════════════════════════════════════════════════
# Spectrum module
# ══════════════════════════════════════════════════════════


class TestInBandEfficiency:
    def test_range(self):
        """Efficiency should be in [0, 1]."""
        src = LPPPlasmaSource()
        eff = in_band_efficiency(src)
        assert 0.0 <= eff <= 1.0

    def test_typical_value(self):
        """Default source has ~75 % spectral efficiency (250 W in-band of
        333.3 W total, since OOB is 25 % of budget).
        """
        src = LPPPlasmaSource()
        eff = in_band_efficiency(src)
        assert 0.60 <= eff <= 0.85, f"Efficiency {eff:.4f} outside expected range"

    def test_no_source(self):
        """Calling without a source uses defaults."""
        eff = in_band_efficiency()
        assert 0.0 <= eff <= 1.0


class TestPhotonsPerNm2:
    def test_positive(self):
        flux = photons_per_nm2(power_w=250.0)
        assert flux > 0.0

    def test_zero_power(self):
        flux = photons_per_nm2(power_w=0.0)
        assert flux == 0.0

    def test_wavelength_scaling(self):
        """Shorter wavelength → higher photon energy → fewer photons per watt."""
        f1 = photons_per_nm2(power_w=1.0, wavelength_nm=10.0)
        f2 = photons_per_nm2(power_w=1.0, wavelength_nm=20.0)
        assert f2 > f1  # lower energy → more photons


class TestDoseToWafer:
    def test_returns_dict(self):
        dose = dose_to_wafer()
        assert isinstance(dose, dict)

    def test_keys_present(self):
        dose = dose_to_wafer()
        for key in (
            "wafer_power_mw",
            "exposure_time_s",
            "dose_mj_cm2",
            "photon_flux_per_nm2_s",
            "photons_per_nm2",
        ):
            assert key in dose, f"Missing key: {key}"

    def test_wafer_power_positive(self):
        dose = dose_to_wafer()
        assert dose["wafer_power_mw"] > 0.0

    def test_dose_positive(self):
        dose = dose_to_wafer()
        assert dose["dose_mj_cm2"] > 0.0

    def test_plausible_dose_range(self):
        """A sensible scan should give a dose in the 10–100 mJ/cm² range."""
        dose = dose_to_wafer()
        d = dose["dose_mj_cm2"]
        assert 1.0 <= d <= 200.0, f"Dose {d:.2f} mJ/cm² outside expected range."

    def test_photons_per_nm2_finite(self):
        dose = dose_to_wafer()
        ppn = dose["photons_per_nm2"]
        assert ppn > 0.0
        assert np.isfinite(ppn)


# ══════════════════════════════════════════════════════════
# Bandwidth properties
# ══════════════════════════════════════════════════════════


class TestBandwidth:
    def test_in_band_bandwidth_nm(self):
        src = LPPPlasmaSource()
        bw_nm = src.in_band_bandwidth_nm
        assert bw_nm == pytest.approx(0.27, abs=0.02)

    def test_in_band_bandwidth_ev(self):
        src = LPPPlasmaSource()
        bw_ev = src.in_band_bandwidth_ev
        # ≈ 1.84 eV for the ±1% band
        assert bw_ev == pytest.approx(1.84, rel=0.1)


# ══════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_single_wavelength(self):
        """spectral_irradiance should handle a single-element array."""
        src = LPPPlasmaSource()
        spec = src.spectral_irradiance(np.array([13.5]))
        assert spec.size == 1
        assert spec[0] >= 0.0

    def test_negative_wavelength(self):
        """Negative wavelength should produce zero emission."""
        src = LPPPlasmaSource()
        lam = np.linspace(-10.0, 10.0, 100)
        spec = src.spectral_irradiance(lam)
        assert np.all(spec >= 0.0)

    def test_in_band_spectrum_zeros_out_of_band(self):
        src = LPPPlasmaSource()
        lam = np.linspace(10.0, 20.0, 500)
        ib = src.in_band_spectrum(lam)
        lo, hi = 13.35, 13.65
        outside = (lam < lo) | (lam > hi)
        assert np.all(ib[outside] == 0.0), "Out-of-band values should be zero"

    def test_high_ce_source(self):
        """Source with 100% CE → laser power = in-band power."""
        src = LPPPlasmaSource(ce_fraction=1.0)
        assert src.laser_power_w == pytest.approx(src.in_band_power_w)
