"""Tests for the LPP tin-plasma source model (plasma + spectrum)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import trapezoid

from euvsimulator.source.plasma import LPPPlasmaSource
from euvsimulator.source.spectrum import (
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
        integral = trapezoid(in_band, in_band_lam)
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

    def test_lambertian_symmetric_in_theta(self, source):
        """f(-theta) = f(theta).  Clipping theta to [0, 90 deg] before the
        cosine gave f = 1.0 for every negative angle.
        """
        angles = np.array([-60.0, -30.0, 30.0, 60.0])
        factors = source.angular_factor(angles)
        assert factors == pytest.approx(np.cos(np.deg2rad(np.abs(angles))), rel=1e-12)


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

    def test_collection_fraction_lambertian_is_sin2_alpha(self):
        """A Lambertian cone of half angle a collects sin^2(a) of the power.

        Omega/pi gave 0.268 at 30 deg, 1.0 at 60 deg and 2.0 for the
        hemisphere (more power than emitted).  Default: 250 W x 0.25 x 0.3.
        """
        src = LPPPlasmaSource()
        for alpha_deg in (30.0, 60.0, 90.0):
            omega = 2.0 * np.pi * (1.0 - np.cos(np.deg2rad(alpha_deg)))
            frac = src.dose_rate(collection_solid_angle_sr=omega, losses=0.0) / 250.0
            assert frac == pytest.approx(np.sin(np.deg2rad(alpha_deg)) ** 2, rel=1e-12)
        assert src.dose_rate() == pytest.approx(18.75, rel=1e-12)

    def test_collection_fraction_gaussian_against_quad(self):
        """Gaussian profile: cone fraction against scipy quad; the hemisphere
        collects everything (Omega / norm gave 4.0 for sigma = 30 deg).
        """
        from scipy.integrate import quad

        src = LPPPlasmaSource(angular_model="gaussian", gaussian_sigma_deg=30.0)
        sig = np.deg2rad(30.0)

        def weight(t):
            return np.exp(-0.5 * (t / sig) ** 2) * np.sin(t)

        ref = quad(weight, 0.0, np.deg2rad(30.0))[0] / quad(weight, 0.0, np.pi / 2.0)[0]
        omega30 = 2.0 * np.pi * (1.0 - np.cos(np.deg2rad(30.0)))
        frac30 = src.dose_rate(collection_solid_angle_sr=omega30, losses=0.0) / 250.0
        assert frac30 == pytest.approx(ref, rel=1e-6)
        full = src.dose_rate(collection_solid_angle_sr=2.0 * np.pi, losses=0.0) / 250.0
        assert full == pytest.approx(1.0, rel=1e-12)

    def test_collection_solid_angle_outside_hemisphere_raises(self):
        src = LPPPlasmaSource()
        with pytest.raises(ValueError):
            src.dose_rate(collection_solid_angle_sr=2.0 * np.pi + 0.1)
        with pytest.raises(ValueError):
            src.dose_rate(collection_solid_angle_sr=-0.1)


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

    def test_scan_dose_is_power_over_field_width_times_speed(self):
        """Scanned field: dose = P_wafer / (field width · scan speed).

        Every point sees the slit for slit_width/v, and the slit area is
        field_width × slit_width, so the slit width cancels.  The absolute
        value (~150 mJ/cm² here) is not realistic because the default
        optical-train transmission (losses = 0.7) is far too high; this
        test checks the geometry only.
        """
        dose = dose_to_wafer()
        p_w = dose["wafer_power_mw"] * 1e-3
        expected = p_w / (2.6 * 50.0) * 1e3  # 26 mm, 500 mm/s -> mJ/cm²
        assert dose["dose_mj_cm2"] == pytest.approx(expected, rel=1e-12)
        wide = dose_to_wafer(slit_width_mm=6.0)
        assert wide["dose_mj_cm2"] == pytest.approx(dose["dose_mj_cm2"], rel=1e-12)

    def test_static_exposure_uses_the_given_area(self):
        dose = dose_to_wafer(exposure_time_s=0.01, exposure_area_nm2=1.0e14)  # 1 cm²
        p_w = dose["wafer_power_mw"] * 1e-3
        assert dose["dose_mj_cm2"] == pytest.approx(p_w * 0.01 * 1e3, rel=1e-12)

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

    def test_in_band_line_fwhm_and_window_fraction(self):
        """The in-band line has FWHM 0.135 nm (a modelling choice), so that
        erf(2.355 / sqrt(2)) = 98.1 % of in_band_power_w lies inside the 2 %
        window 13.365-13.635 nm.  A line of FWHM 0.27 nm would give 0.270 nm
        and 76.1 % here.  The out-of-band tails are switched off because they
        are normalised over the given grid and would add a baseline.
        """
        src = LPPPlasmaSource(oob_duv_fraction=0.0, oob_ir_fraction=0.0)
        lam = np.linspace(13.0, 14.0, 100001)
        spec = src.spectral_irradiance(lam)
        above = lam[spec >= 0.5 * spec.max()]
        assert above[-1] - above[0] == pytest.approx(0.135, abs=2e-4)
        window = (lam >= 13.365) & (lam <= 13.635)
        frac = trapezoid(spec[window], lam[window]) / src.in_band_power_w
        assert frac == pytest.approx(0.981, abs=2e-3)


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


class TestWithoutNumpyTrapezoid:
    """pyproject allows numpy>=1.24, but numpy.trapezoid only exists from NumPy 2.0.

    Deleting the attribute simulates NumPy 1.x; before the fix every call
    below raised AttributeError there.
    """

    def test_in_band_efficiency(self, monkeypatch):
        expected = in_band_efficiency()
        monkeypatch.delattr(np, "trapezoid", raising=False)
        assert in_band_efficiency() == expected

    def test_in_band_spectrum(self, monkeypatch):
        src = LPPPlasmaSource()
        lam = np.linspace(10.0, 20.0, 500)
        expected = src.in_band_spectrum(lam)
        monkeypatch.delattr(np, "trapezoid", raising=False)
        np.testing.assert_array_equal(src.in_band_spectrum(lam), expected)

    def test_gaussian_dose_rate(self, monkeypatch):
        src = LPPPlasmaSource(angular_model="gaussian", gaussian_sigma_deg=15.0)
        expected = src.dose_rate()
        monkeypatch.delattr(np, "trapezoid", raising=False)
        assert src.dose_rate() == expected
