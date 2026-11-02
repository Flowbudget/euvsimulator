"""run_simulation(cfg, key=value) behaves like building a new config."""

from __future__ import annotations

import dataclasses

import pytest

from euvsimulator.pipeline import SimulationConfig, run_simulation


def _cfg(**kw) -> SimulationConfig:
    return SimulationConfig(device="cpu", grid=32, **kw)


def test_override_does_not_mutate_caller_config():
    cfg = _cfg()
    before = dataclasses.asdict(cfg)
    run_simulation(cfg, dose_mj_cm2=5.0)
    assert dataclasses.asdict(cfg) == before


def test_unknown_override_name_raises():
    cfg = _cfg()
    with pytest.raises(TypeError):
        run_simulation(cfg, dosee=5.0)
    assert not hasattr(cfg, "dosee")


def test_invalid_override_value_raises():
    with pytest.raises(ValueError):
        run_simulation(_cfg(), dose_mj_cm2=-1.0)


def test_peb_temperature_override_matches_constructor():
    # Measured 2026-10-02 (grid 32, full_chem, 1.3 mJ/cm2): CD 32.453 nm at
    # the default kinetics, 38.743 nm at 100 C. The old setattr path left
    # peb_k/peb_acid_lifetime_s at the defaults and returned 32.453.
    base = dict(resist_model="full_chem", dose_mj_cm2=1.3)
    via_kwargs = run_simulation(_cfg(**base), peb_temperature_c=100.0)
    via_ctor = run_simulation(_cfg(peb_temperature_c=100.0, **base))
    assert via_kwargs.cd_nm == via_ctor.cd_nm
    # 2026-10-03: re-measured after the periodic sampling P/G,
    # the film-bottom CD and the common thin-mask phase reference (A5):
    # 39.3563 (was 38.7425).
    assert via_kwargs.cd_nm == pytest.approx(40.6029, abs=1e-2)  # 39.3563 before 2.3.0
