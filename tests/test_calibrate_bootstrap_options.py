"""bootstrap_fit(options=..., original_fit=...) in calibrate/wafer_fit.py.

Before the fix bootstrap_fit had no options parameter: every refit ran at the
hard-coded maxiter 1000 while euv calibrate fitted at --maxiter (default
500), and the CI block printed that second fit as its point estimate.
"""

from __future__ import annotations

import numpy as np

import euvsimulator.calibrate.wafer_fit as wafer_fit
from euvsimulator.calibrate.wafer_fit import WaferCDData, bootstrap_fit, fit_resist_params


def _quad_pipeline(dose: float, focus: float, a: float = 1.0, b: float = 0.0) -> float:
    return 30.0 + a * (dose - 20.0) + b * (dose - 20.0) ** 2 + 0.001 * focus**2


def _complete_fem() -> WaferCDData:
    doses = np.array([12.0, 16.0, 20.0, 24.0, 28.0])
    foci = np.array([-40.0, 0.0, 40.0])
    cd = np.array([[_quad_pipeline(d, f, a=1.5, b=0.05) for f in foci] for d in doses])
    return WaferCDData(doses, foci, cd)


def test_options_reach_the_original_fit_and_every_replica(monkeypatch):
    seen = []
    real_fit = wafer_fit.fit_resist_params

    def spy(*args, **kwargs):
        seen.append(kwargs.get("options"))
        return real_fit(*args, **kwargs)

    monkeypatch.setattr(wafer_fit, "fit_resist_params", spy)
    wafer_fit.bootstrap_fit(
        _complete_fem(),
        _quad_pipeline,
        {"a": 1.0, "b": 0.0},
        n_samples=5,
        seed=0,
        options={"maxiter": 20},
    )
    assert seen == [{"maxiter": 20}] * 6


def test_point_estimate_is_the_fit_with_the_same_options():
    """A budget of 20 iterations stops the main fit early (b ~0.03).

    The old bootstrap refitted at maxiter 1000 and reported b = 0.05 instead.
    """
    data = _complete_fem()
    main = fit_resist_params(data, {"a": 1.0, "b": 0.0}, _quad_pipeline, options={"maxiter": 20})
    assert not main["success"]
    boot = bootstrap_fit(
        data, _quad_pipeline, {"a": 1.0, "b": 0.0}, n_samples=5, seed=0, options={"maxiter": 20}
    )
    assert boot["fitted_on_original"] == main["fitted_params"]


def test_original_fit_is_reused_not_recomputed(monkeypatch):
    data = _complete_fem()
    main = fit_resist_params(data, {"a": 1.0, "b": 0.0}, _quad_pipeline, options={"maxiter": 20})
    seen = []
    real_fit = wafer_fit.fit_resist_params

    def spy(*args, **kwargs):
        seen.append(1)
        return real_fit(*args, **kwargs)

    monkeypatch.setattr(wafer_fit, "fit_resist_params", spy)
    boot = wafer_fit.bootstrap_fit(
        data,
        _quad_pipeline,
        {"a": 1.0, "b": 0.0},
        n_samples=5,
        seed=0,
        options={"maxiter": 20},
        original_fit=main,
    )
    assert boot["fitted_on_original"] is main["fitted_params"]
    assert len(seen) == 5
