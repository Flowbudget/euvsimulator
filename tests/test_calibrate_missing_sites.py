"""Missing FEM sites (NaN in the measured CD matrix) in calibrate/wafer_fit.py.

Before the fix one NaN made every objective value NaN: Nelder-Mead ran to
maxiter (nfev 3999), returned the start values with rmse NaN, and the
bootstrap kept only the replicas that happened to leave the NaN row out.
"""

from __future__ import annotations

import numpy as np
import pytest

from euvsimulator.calibrate.wafer_fit import (
    WaferCDData,
    bootstrap_fit,
    fit_resist_params,
    objective_resist,
)


def _quad_pipeline(dose: float, focus: float, a: float = 1.0, b: float = 0.0) -> float:
    """Toy Bossung: 30 nm at dose 20, slope a, curvature b, weak focus term."""
    return 30.0 + a * (dose - 20.0) + b * (dose - 20.0) ** 2 + 0.001 * focus**2


def _fem_with_one_missing_site() -> WaferCDData:
    """5 x 3 FEM from a = 1.5, b = 0.05 without noise; site (dose 16, focus 40) is NaN."""
    doses = np.array([12.0, 16.0, 20.0, 24.0, 28.0])
    foci = np.array([-40.0, 0.0, 40.0])
    cd = np.array([[_quad_pipeline(d, f, a=1.5, b=0.05) for f in foci] for d in doses])
    cd[1, 2] = np.nan
    return WaferCDData(doses, foci, cd)


def test_objective_skips_a_nan_site():
    calls = []

    def counting_pipeline(dose, focus, **params):
        calls.append((dose, focus))
        return _quad_pipeline(dose, focus, **params)

    data = _fem_with_one_missing_site()
    rmse = objective_resist(np.array([1.5, 0.05]), data, counting_pipeline, ["a", "b"])
    assert rmse == pytest.approx(0.0, abs=1e-12)
    assert len(calls) == 14
    assert (16.0, 40.0) not in calls
    # residuals 0.8, 1.2, 0, -2.8, -7.2 nm per dose row; the dose-16 row has 2 sites
    rmse_off = objective_resist(np.array([1.0, 0.0]), data, _quad_pipeline, ["a", "b"])
    assert rmse_off == pytest.approx(np.sqrt(183.84 / 14.0), rel=1e-9)


def test_fit_recovers_the_parameters_despite_a_nan_site():
    result = fit_resist_params(_fem_with_one_missing_site(), {"a": 1.0, "b": 0.0}, _quad_pipeline)
    assert result["success"]
    assert result["rmse"] < 1e-3
    assert result["fitted_params"]["a"] == pytest.approx(1.5, abs=1e-3)
    assert result["fitted_params"]["b"] == pytest.approx(0.05, abs=1e-3)


def test_bootstrap_point_estimate_lies_inside_its_interval():
    result = bootstrap_fit(
        _fem_with_one_missing_site(),
        pipeline_fn=_quad_pipeline,
        initial_params={"a": 1.0, "b": 0.0},
        n_samples=40,
        seed=0,
    )
    # before the fix: 17 / 40 valid, point estimate = start values (a = 1.0)
    # outside its own interval [1.26, 1.50]; measured after: 40 / 40, a = 1.5000
    fitted = result["fitted_on_original"]
    assert fitted["a"] == pytest.approx(1.5, abs=1e-3)
    valid = ~np.any(np.isnan(result["bootstrap_samples"]), axis=1)
    assert int(valid.sum()) >= 30
    # noise-free data: the replicas agree to ~xatol, so allow 1e-3 at the edges
    for name in ("a", "b"):
        assert result["ci_lower"][name] - 1e-3 <= fitted[name] <= result["ci_upper"][name] + 1e-3


def test_no_finite_cd_raises():
    data = WaferCDData(np.array([20.0]), np.array([0.0]), np.array([[np.nan]]))
    with pytest.raises(ValueError, match="no finite CD"):
        fit_resist_params(data, {"a": 1.0}, _quad_pipeline)


def test_inf_cd_is_rejected():
    with pytest.raises(ValueError, match="inf"):
        WaferCDData(np.array([20.0]), np.array([0.0]), np.array([[np.inf]]))
