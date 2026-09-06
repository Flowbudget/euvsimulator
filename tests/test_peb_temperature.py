"""PEB temperature model from Yamamoto 2011 Fig. 3 (plan stage C1, log Fortsetzung 37)."""

from __future__ import annotations

import json
import math
from importlib import resources

import numpy as np
import pytest

from euvsimulator.pipeline import SimulationConfig
from euvsimulator.resist.kinetics import yamamoto_polymer_a_kinetics


def _anchor():
    with (
        resources.files("euvsimulator.data.anchors")
        .joinpath("yamamoto2011_fig3_polymerA.json")
        .open() as f
    ):
        return json.load(f)


def test_measured_temperatures_are_reproduced_and_k_is_monotonic():
    d = _anchor()["chain_fits"]["per_temperature"]
    ks = []
    for T, v in d.items():
        k, tau = yamamoto_polymer_a_kinetics(float(T))
        assert k == pytest.approx(v["k_per_s_at_C_0.0152"], rel=1e-9)
        assert tau == pytest.approx(v["tau_s"], rel=1e-9)
        ks.append((float(T), k))
    ks.sort()
    assert all(
        b[1] > a[1] for a, b in zip(ks, ks[1:]) if b[0] != 130.0
    )  # 130 C sits below 120 C in the data


def test_tau_at_90_c_agrees_with_nist_on_a_different_resist():
    """Yamamoto Polymer A: tau(90 C) = 35 s from Fig. 3; Kang/NIST 2009 (JSR EUV
    resist, FT-IR kinetics, PEB 90 C): kT = 0.026 1/s -> 38 s. Two resists,
    two methods, within 15 %.
    """
    _, tau = yamamoto_polymer_a_kinetics(90.0)
    assert tau == pytest.approx(1.0 / 0.026, rel=0.15)


def test_chain_law_reproduces_all_seven_curves():
    d = _anchor()
    H0 = 1.0 - math.exp(-0.0152 * d["dose_mj_cm2"])
    for T, curve in d["curves_t_s_P"].items():
        k, tau = yamamoto_polymer_a_kinetics(float(T))
        pts = np.array([p for p in curve if p[0] >= 1.0])
        model = np.exp(-k * H0 * tau * (1.0 - np.exp(-pts[:, 0] / tau)))
        rms = float(np.sqrt(np.mean((model - pts[:, 1]) ** 2)))
        assert rms <= 0.03, (T, rms)


def test_config_temperature_overrides_k_and_tau_and_warns_when_clamped():
    c = SimulationConfig(peb_temperature_c=110.0)
    assert c.peb_k == pytest.approx(10.947, abs=0.01)
    assert c.peb_acid_lifetime_s == pytest.approx(7.54, abs=0.01)
    assert SimulationConfig().peb_temperature_c is None
    with pytest.warns(UserWarning, match="outside the measured"):
        c2 = SimulationConfig(peb_temperature_c=150.0)
    assert c2.peb_k == pytest.approx(SimulationConfig(peb_temperature_c=140.0).peb_k)
    # k*H0 is preserved when C differs
    a = SimulationConfig(peb_temperature_c=90.0)
    b = SimulationConfig(peb_temperature_c=90.0, dill_C=0.03)
    h = lambda C: 1.0 - math.exp(-C * 1.4)  # noqa: E731
    assert a.peb_k * h(0.0152) == pytest.approx(b.peb_k * h(0.03), rel=1e-9)
