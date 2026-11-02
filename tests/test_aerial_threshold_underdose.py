"""aerial_threshold: an underexposed period reports CD = pitch, a fully
cleared one CD = 0 (plan pipeline-1, step 5).

Until 2026-10 both cases returned 0, so CD(dose) at 64/32 nm, grid 128 read
0.0 (dose 4.1) -> 57.4 (4.3) -> 50.6 (5) -> 27.6 (20): not monotone.
"""

from euvsimulator.pipeline import SimulationConfig, run_simulation


def _run(dose):
    return run_simulation(SimulationConfig(dose_mj_cm2=dose, grid=128, device="cpu"))


def test_underexposed_period_reports_the_pitch():
    r = _run(1.0)
    assert float(r.resist_profile.sum()) == 0.0  # nothing developed
    assert r.cd_nm == 64.0


def test_fully_cleared_period_still_reports_zero():
    r = _run(500.0)
    assert float(r.resist_profile.mean()) == 1.0  # everything developed
    assert r.cd_nm == 0.0


def test_cd_is_monotone_in_dose_at_the_low_dose_end():
    cds = [_run(d).cd_nm for d in (1.0, 4.1, 4.3, 5.0, 10.0, 20.0)]
    assert all(a >= b for a, b in zip(cds, cds[1:])), cds
    assert cds[0] == 64.0 and 0.0 < cds[-1] < 64.0
