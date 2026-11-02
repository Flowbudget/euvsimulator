"""Dose-to-size bisection of calibrate/bands.py (fast: run_simulation is stubbed).

Before the fix 9 linear steps over 0.3-60 mJ/cm2 resolved only +-0.058
mJ/cm2: +9.2 % at the trapping law's 0.5416 and -1.1 % at the analytical
law's 1.3054 (grid 64, measured 2026-10-02), and a crossing below dose_lo
returned dose_lo + 0.057 instead of NaN.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import euvsimulator.calibrate.bands as bands_mod


def _stub(monkeypatch, d2s: float, target: float = 32.0) -> list:
    """CD = target * d2s / dose: falls with dose and crosses target at d2s."""
    doses: list = []

    def fake_run_simulation(cfg):
        doses.append(cfg.dose_mj_cm2)
        return SimpleNamespace(cd_nm=target * d2s / cfg.dose_mj_cm2)

    monkeypatch.setattr(bands_mod, "run_simulation", fake_run_simulation)
    return doses


def _make(dose_mj_cm2):
    return SimpleNamespace(dose_mj_cm2=dose_mj_cm2)


@pytest.mark.parametrize("d2s", [0.5416, 1.3054, 30.0])
def test_dose_to_size_is_resolved_to_rtol(monkeypatch, d2s):
    doses = _stub(monkeypatch, d2s)
    got = bands_mod._dose_to_size(_make, 32.0, 0.3, 60.0)
    assert got == pytest.approx(d2s, rel=5e-4)
    assert len(doses) <= 16


def test_crossing_below_dose_lo_gives_nan(monkeypatch):
    _stub(monkeypatch, 0.5416)
    assert math.isnan(bands_mod._dose_to_size(_make, 32.0, 2.0, 60.0))


def test_not_printing_at_dose_hi_gives_nan(monkeypatch):
    _stub(monkeypatch, 80.0)
    assert math.isnan(bands_mod._dose_to_size(_make, 32.0, 0.3, 60.0))


def test_invalid_bracket_raises(monkeypatch):
    _stub(monkeypatch, 1.3)
    with pytest.raises(ValueError, match="dose_lo < dose_hi"):
        bands_mod._dose_to_size(_make, 32.0, 60.0, 0.3)
