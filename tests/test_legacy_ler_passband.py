"""The legacy LER estimator in run_simulation applies ler_passband_nm like LWR does."""

from __future__ import annotations

import pytest

from euvsimulator.pipeline import SimulationConfig, run_simulation


def _legacy_cfg(passband):
    return SimulationConfig(
        device="cpu",
        grid=64,
        resist_model="full_chem",
        dose_mj_cm2=1.3,
        enable_stochastic=True,
        stochastic_seed=3,
        stochastic_ler_estimator="legacy",
        ler_passband_nm=passband,
    )


def test_pipeline_legacy_ler_uses_passband():
    # Measured 2026-10-02: before the fix ler_nm stayed 1.5464 with the band
    # (10, 40) while lwr_nm fell to 0.3382; with the band applied ler_nm is 0.1949.
    # Re-measured 2026-10-03 after the stochastic edges moved to the bottom-layer
    # arrival time (r3-pipeline-stochedge): 1.5393 / 0.1746 / 0.3232.
    full = run_simulation(_legacy_cfg(None))
    band = run_simulation(_legacy_cfg((10.0, 40.0)))
    # 2026-10-03:  re-measured after P/G sampling, film-bottom CD and the A5
    # thin-mask phase reference: 1.6506 / 0.2379 / 0.4288; 2.3.0 adds the
    # Si-terminated mirror: 1.5977 / 0.3019 / 0.5134.
    assert full.ler_nm == pytest.approx(1.5977, abs=1e-3)  # 1.6506 before 2.3.0
    assert band.ler_nm == pytest.approx(0.3019, abs=1e-3)  # 0.2379 before 2.3.0
    assert band.lwr_nm == pytest.approx(0.5134, abs=1e-3)  # 0.4288 before 2.3.0
    assert band.ler_nm < 0.5 * full.ler_nm
