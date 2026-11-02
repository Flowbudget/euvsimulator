"""run_simulation progress hook: None continues the run, False cancels it.

The hook is called as progress(done, total) before each stochastic
realisation. A hook that only reports (no return statement) returns None;
before the fix that cancelled the run at the first realisation.
"""

from __future__ import annotations

import math

import pytest

from euvsimulator.pipeline import SimulationCancelledError, SimulationConfig, run_simulation


def _cfg():
    return SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        grid=64,
        stochastic_ler_grid_y=128,
        dose_mj_cm2=1.3,
        se_blur_nm=5.0,
        device="cpu",
        stochastic_seed=1,
        stochastic_n_realisations=2,
    )


def test_report_only_progress_hook_does_not_cancel():
    calls = []
    r = run_simulation(_cfg(), progress=lambda done, total: calls.append((done, total)))
    assert calls == [(0, 2), (1, 2)]
    assert math.isfinite(r.lwr_nm)
    # the hook must not change the result
    assert r.lwr_nm == run_simulation(_cfg()).lwr_nm


@pytest.mark.parametrize("answer", [False, 0])
def test_falsy_progress_answer_still_cancels(answer):
    with pytest.raises(SimulationCancelledError, match="progress hook"):
        run_simulation(_cfg(), progress=lambda done, total: answer)
