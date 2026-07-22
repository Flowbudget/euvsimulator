"""Tests for the calibration pipeline (euv.calibrate.wafer_fit)."""

from __future__ import annotations

import numpy as np
import pytest

from euv.calibrate.wafer_fit import (
    WaferCDData,
    bootstrap_fit,
    calibrate_on_synthetic,
    fit_resist_params,
    objective_resist,
)

# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────


def _simple_pipeline(
    dose: float,
    focus: float,
    R_max: float = 100.0,
    R_min: float = 0.1,
    n: float = 5.0,
    M_th: float = 0.5,
) -> float:
    """A simple, deterministic pipeline surrogate for testing.

    Models CD as a function of dose and focus with a parabolic focus
    dependence and a power-law dose dependence — similar to a Bossung
    curve but purely analytical.
    """
    # Focus dependence: parabolic with minimum at focus=0
    focus_term = (focus / 50.0) ** 2
    # Dose dependence: CD decreases with dose (power law)
    dose_term = 50.0 * (dose / 20.0) ** (-0.3)
    # R_max modulates overall magnitude
    scale = R_max / 100.0
    # n modulates the focus sensitivity
    focus_scale = 5.0 / max(n, 0.1)
    # M_th adds a constant offset to the CD (increased contribution)
    cd = scale * (dose_term + focus_scale * focus_term * 20.0 + R_min * 10.0) + M_th * 20.0
    return max(cd, 5.0)


# ──────────────────────────────────────────────────────────
# WaferCDData
# ──────────────────────────────────────────────────────────


class TestWaferCDData:
    def test_create_and_access_fields(self):
        """Create a WaferCDData and access its fields."""
        doses = np.linspace(12, 28, 5)
        foci = np.linspace(-60, 60, 5)
        cd = np.random.rand(5, 5) * 30 + 20
        data = WaferCDData(doses, foci, cd)
        assert len(data.dose_values) == 5
        assert len(data.focus_values) == 5
        assert data.cd_matrix_nm.shape == (5, 5)

    def test_shape_mismatch_raises(self):
        """Mismatched matrix shape raises ValueError."""
        doses = np.linspace(12, 28, 5)
        foci = np.linspace(-60, 60, 5)
        cd = np.random.rand(5, 4)  # wrong shape
        with pytest.raises(ValueError, match="does not match"):
            WaferCDData(doses, foci, cd)

    def test_flatten(self):
        """Flatten returns (N, 2) and (N,) arrays with correct length."""
        doses = np.array([12.0, 20.0])
        foci = np.array([-30.0, 0.0, 30.0])
        cd = np.array([[25.0, 22.0, 25.0], [20.0, 18.0, 20.0]])
        data = WaferCDData(doses, foci, cd)
        x, y = data.flatten()
        assert x.shape == (6, 2)
        assert y.shape == (6,)
        # Check a specific value
        assert y[0] == 25.0
        assert x[0, 0] == 12.0
        assert x[0, 1] == -30.0

    def test_properties(self):
        """n_dose and n_focus properties are correct."""
        data = WaferCDData(
            dose_values=np.array([10, 20, 30]),
            focus_values=np.array([-40, 0, 40]),
            cd_matrix_nm=np.random.rand(3, 3),
        )
        assert data.n_dose == 3
        assert data.n_focus == 3


# ──────────────────────────────────────────────────────────
# Objective
# ──────────────────────────────────────────────────────────


class TestObjectiveResist:
    def test_rmse_is_zero_for_perfect_match(self):
        """RMSE = 0 when the pipeline reproduces the data exactly."""
        doses = np.array([20.0])
        foci = np.array([0.0])
        cd_target = np.array([[30.0]])  # 30 nm CD
        data = WaferCDData(doses, foci, cd_target)

        # Create a pipeline that returns exactly 30.0 for these inputs
        def perfect_pipeline(dose, focus, **params):
            return 30.0

        rmse = objective_resist(
            params=np.array([100.0]),  # not used by perfect_pipeline
            data=data,
            pipeline_fn=perfect_pipeline,
            param_names=["R_max"],
        )
        assert rmse == 0.0, f"Expected 0 RMSE, got {rmse}"

    def test_rmse_positive_for_mismatch(self):
        """RMSE > 0 when pipeline and data differ."""
        doses = np.array([20.0])
        foci = np.array([0.0])
        cd_target = np.array([[30.0]])
        data = WaferCDData(doses, foci, cd_target)

        def off_pipeline(dose, focus, **params):
            return 35.0  # 5 nm off

        rmse = objective_resist(
            params=np.array([100.0]),
            data=data,
            pipeline_fn=off_pipeline,
            param_names=["R_max"],
        )
        assert rmse == pytest.approx(5.0, abs=1e-10)

    def test_rmse_for_multiple_points(self):
        """RMSE for known differences is computed correctly."""
        doses = np.array([10.0, 20.0])
        foci = np.array([0.0])
        cd_target = np.array([[20.0], [30.0]])
        data = WaferCDData(doses, foci, cd_target)

        def half_pipeline(dose, focus, **params):
            return 0.0  # returns 0 everywhere

        rmse = objective_resist(
            params=np.array([100.0]),
            data=data,
            pipeline_fn=half_pipeline,
            param_names=["R_max"],
        )
        # residuals = [0-20, 0-30] = [-20, -30]
        # MSE = (400 + 900) / 2 = 650
        # RMSE = sqrt(650) ≈ 25.495
        expected = np.sqrt((20.0**2 + 30.0**2) / 2.0)
        assert rmse == pytest.approx(expected, abs=1e-10)


# ──────────────────────────────────────────────────────────
# Fit resist params
# ──────────────────────────────────────────────────────────


class TestFitResistParams:
    def test_returns_dict_with_expected_keys(self):
        """fit_resist_params returns a dict with expected keys."""
        doses = np.array([20.0])
        foci = np.array([0.0])
        cd = np.array([[30.0]])
        data = WaferCDData(doses, foci, cd)

        # Use a pipeline that ignores params and returns constant
        def const_pipeline(dose, focus, **params):
            return 30.0

        result = fit_resist_params(
            data,
            initial_params={"R_max": 100.0},
            pipeline_fn=const_pipeline,
        )
        expected_keys = {"fitted_params", "rmse", "success", "message", "n_iter", "nfev"}
        assert expected_keys.issubset(result.keys()), (
            f"Missing keys: {expected_keys - set(result.keys())}"
        )

    def test_fits_simple_pipeline(self):
        """Fitting works on a simple analytical pipeline."""
        doses = np.array([15.0, 20.0, 25.0])
        foci = np.array([-30.0, 0.0, 30.0])
        true_params = {"R_max": 120.0, "R_min": 0.2, "n": 4.0, "M_th": 0.4}

        # Generate synthetic data
        cd_sim = np.zeros((3, 3), dtype=float)
        for i, d in enumerate(doses):
            for j, f in enumerate(foci):
                cd_sim[i, j] = _simple_pipeline(d, f, **true_params)

        data = WaferCDData(doses, foci, cd_sim)

        result = fit_resist_params(
            data,
            initial_params={"R_max": 100.0, "R_min": 0.1, "n": 5.0, "M_th": 0.5},
            pipeline_fn=_simple_pipeline,
        )
        assert result["success"]
        assert result["rmse"] < 5.0, f"RMSE too high: {result['rmse']}"

    def test_fitted_params_dict(self):
        """fitted_params is a dict with the correct keys."""
        doses = np.array([20.0])
        foci = np.array([0.0])
        cd = np.array([[30.0]])
        data = WaferCDData(doses, foci, cd)

        def const_pipeline(dose, focus, **params):
            return 30.0

        result = fit_resist_params(
            data,
            initial_params={"R_max": 100.0, "n": 5.0},
            pipeline_fn=const_pipeline,
        )
        fitted = result["fitted_params"]
        assert "R_max" in fitted
        assert "n" in fitted


# ──────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────


class TestBootstrapFit:
    def test_returns_expected_keys(self):
        """bootstrap_fit returns dict with expected keys."""
        doses = np.linspace(12, 28, 4)
        foci = np.linspace(-60, 60, 4)
        cd = np.random.rand(4, 4) * 30 + 20
        data = WaferCDData(doses, foci, cd)

        result = bootstrap_fit(
            data,
            pipeline_fn=_simple_pipeline,
            initial_params={"R_max": 100.0, "R_min": 0.1},
            n_samples=10,
            seed=42,
        )
        expected_keys = {
            "param_names",
            "fitted_on_original",
            "bootstrap_samples",
            "ci_lower",
            "ci_upper",
            "ci_level",
        }
        assert expected_keys.issubset(result.keys())

    def test_ci_level_is_95(self):
        """Default ci_level is 95."""
        doses = np.linspace(12, 28, 3)
        foci = np.linspace(-60, 60, 3)
        cd = np.random.rand(3, 3) * 30 + 20
        data = WaferCDData(doses, foci, cd)

        result = bootstrap_fit(
            data,
            pipeline_fn=_simple_pipeline,
            initial_params={"R_max": 100.0},
            n_samples=5,
            seed=42,
        )
        assert result["ci_level"] == 95.0

    def test_bootstrap_samples_shape(self):
        """bootstrap_samples has shape (n_samples, n_params)."""
        doses = np.linspace(12, 28, 3)
        foci = np.linspace(-60, 60, 3)
        cd = np.random.rand(3, 3) * 30 + 20
        data = WaferCDData(doses, foci, cd)

        result = bootstrap_fit(
            data,
            pipeline_fn=_simple_pipeline,
            initial_params={"R_max": 100.0, "R_min": 0.1},
            n_samples=10,
            seed=42,
        )
        assert result["bootstrap_samples"].shape == (10, 2)


# ──────────────────────────────────────────────────────────
# Synthetic calibration
# ──────────────────────────────────────────────────────────


class TestCalibrateOnSynthetic:
    def test_recovers_target_params_within_twenty_percent(self):
        """Calibration recovers target parameters within 20% relative error."""
        target = {"R_max": 100.0, "R_min": 0.1, "n": 5.0, "M_th": 0.5}
        result = calibrate_on_synthetic(
            target_params=target,
            pipeline_fn=_simple_pipeline,
            noise_std=0.5,  # low noise for recovery test
            seed=42,
        )
        for key in target:
            rel_err = result["relative_error"][key]
            assert rel_err < 0.20, (
                f"Relative error for {key} = {rel_err:.4f} "
                f"(target={target[key]}, fitted={result['fitted_params'][key]:.2f})"
            )

    def test_returns_expected_keys(self):
        """calibrate_on_synthetic returns dict with expected keys."""
        target = {"R_max": 100.0, "R_min": 0.1}
        result = calibrate_on_synthetic(
            target_params=target,
            pipeline_fn=_simple_pipeline,
            noise_std=1.0,
            seed=42,
        )
        expected_keys = {
            "target_params",
            "fitted_params",
            "relative_error",
            "rmse",
            "noise_std_used",
            "n_dose",
            "n_focus",
        }
        assert expected_keys.issubset(result.keys())

    def test_custom_grid(self):
        """Custom dose/focus grids are used correctly."""
        target = {"R_max": 100.0, "R_min": 0.1}
        doses = np.array([15.0, 25.0])
        foci = np.array([-30.0, 30.0])
        result = calibrate_on_synthetic(
            target_params=target,
            pipeline_fn=_simple_pipeline,
            noise_std=0.0,
            dose_values=doses,
            focus_values=foci,
            seed=42,
        )
        assert result["n_dose"] == 2
        assert result["n_focus"] == 2
