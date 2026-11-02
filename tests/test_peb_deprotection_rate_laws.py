"""Regression guard: each PEB law gets its own deprotection rate k.

Yamamoto 2011 Fig. 3 (Polymer A, 110 C, 1.4 mJ/cm2 flood) was fitted once
with each acid-loss law (data/anchors/yamamoto2011_fig3_polymerA.json):

* ``"analytical"`` (first-order acid lifetime): k*H0 = 0.2305 1/s,
  tau = 7.54 s, i.e. k = 10.947 1/s at C = 0.0152;
* ``"reaction_diffusion"`` (Kang/NIST trapping): k*H0 = 0.188 1/s,
  k_trap = 0.2076 1/s, i.e. k = 8.929 1/s.

Until 2026-10 ``SimulationConfig(peb_model="reaction_diffusion")`` kept the
analytical k next to the NIST-law k_trap, a pair that does not reproduce the
flood curve (P(60 s) 0.139 instead of 0.178), and the structural bands ran
their reaction_diffusion corner with whatever k the base carried. A first fix
scaled k by 8.929/10.947 unconditionally; a base that was already
reaction_diffusion (``api.tasks.bands_task``) then got 7.283, and an explicit
peb_k was rewritten when it happened to equal the default.
"""

from __future__ import annotations

import dataclasses
import math
import warnings
from types import SimpleNamespace

import numpy as np
import pytest

import euvsimulator.calibrate.bands as bands_mod
from euvsimulator.api.fields import resolve_config
from euvsimulator.api.tasks import bands_task
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.kinetics import (
    yamamoto_polymer_a_kinetics,
    yamamoto_polymer_a_kinetics_nist_law,
)

RD = "reaction_diffusion"
K_ANALYTICAL = 10.947  # 0.2305 / H0
K_NIST = 8.929  # 0.188 / H0, H0 = 1 - exp(-0.0152 * 1.4)
K_TRAP = 0.2076
RATIO = K_NIST / K_ANALYTICAL


def _flood_p_nist(k: float, k_trap: float, h0: float, t: float = 60.0, n: int = 3000) -> float:
    """Protection P(t) under dP/dt = -k h P, dh/dt = -k_trap h (1 - P) (RK4)."""

    def f(y: np.ndarray) -> np.ndarray:
        p, h = y
        return np.array([-k * h * p, -k_trap * h * (1.0 - p)])

    y = np.array([1.0, h0])
    dt = t / n
    for _ in range(n):
        k1 = f(y)
        k2 = f(y + 0.5 * dt * k1)
        k3 = f(y + 0.5 * dt * k2)
        k4 = f(y + dt * k3)
        y = y + dt / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(y[0])


# ── SimulationConfig ──────────────────────────────────────────────────────


def test_reaction_diffusion_default_is_the_nist_law_pair():
    cfg = SimulationConfig(peb_model=RD)
    assert cfg.peb_k == pytest.approx(K_NIST, abs=1e-3)
    assert cfg.peb_k_trap_per_s == K_TRAP
    k_fit, k_trap_fit = yamamoto_polymer_a_kinetics_nist_law(110.0)
    assert cfg.peb_k == pytest.approx(k_fit, rel=1e-4)
    assert cfg.peb_k_trap_per_s == pytest.approx(k_trap_fit, rel=1e-9)
    at_110 = SimulationConfig(peb_model=RD, peb_temperature_c=110.0)
    assert cfg.peb_k == pytest.approx(at_110.peb_k, rel=1e-4)
    assert cfg.peb_k_trap_per_s == pytest.approx(at_110.peb_k_trap_per_s, rel=1e-9)


def test_both_default_pairs_reproduce_the_same_flood_curve():
    """The point of the pairing: both laws' defaults give Fig. 3's plateau.

    Measured: analytical 0.1759, reaction_diffusion 0.178 (was 0.139).
    """
    a = SimulationConfig()
    r = SimulationConfig(peb_model=RD)
    h0 = 1.0 - math.exp(-a.dill_C * 1.4)
    tau = a.peb_acid_lifetime_s
    assert tau is not None
    p_analytical = math.exp(-a.peb_k * h0 * tau * (1.0 - math.exp(-60.0 / tau)))
    p_rd = _flood_p_nist(r.peb_k, r.peb_k_trap_per_s, h0)
    assert p_analytical == pytest.approx(0.176, abs=0.005)
    assert abs(p_rd - p_analytical) < 0.005


def test_derived_configs_take_the_new_laws_default():
    """A default peb_k follows the law in derived configurations too.

    dataclasses.replace, run_simulation(cfg, peb_model=...) and the GUI's
    preset + overrides (api.fields.resolve_config) pass the resolved peb_k on.
    """
    to_rd = dataclasses.replace(SimulationConfig(), peb_model=RD)
    assert to_rd.peb_k == pytest.approx(K_NIST, abs=1e-3)
    back = dataclasses.replace(SimulationConfig(peb_model=RD), peb_model="analytical")
    assert back.peb_k == K_ANALYTICAL
    assert resolve_config(None, {"peb_model": RD}).peb_k == pytest.approx(K_NIST, abs=1e-3)
    assert resolve_config(None, {}).peb_k == K_ANALYTICAL


def test_an_explicit_peb_k_is_never_rewritten():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k in (K_ANALYTICAL, K_NIST, 5.0, 20.0):
            for law in ("analytical", RD):
                assert SimulationConfig(peb_model=law, peb_k=k).peb_k == k
        assert dataclasses.replace(SimulationConfig(peb_k=5.0), peb_model=RD).peb_k == 5.0
        explicit_rd = SimulationConfig(peb_model=RD, peb_k=5.0)
        assert dataclasses.replace(explicit_rd, peb_model="analytical").peb_k == 5.0
        assert resolve_config(None, {"peb_model": RD, "peb_k": K_ANALYTICAL}).peb_k == K_ANALYTICAL


def test_reaction_diffusion_with_the_analytical_law_k_warns():
    with pytest.warns(UserWarning, match="analytical law's fit"):
        SimulationConfig(peb_model=RD, peb_k=K_ANALYTICAL)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        SimulationConfig(peb_model=RD)
        SimulationConfig(peb_model=RD, peb_k=5.0)
        SimulationConfig(peb_k=K_ANALYTICAL)
        # temperature mode replaces k by that temperature's fit of the chosen law
        SimulationConfig(peb_model=RD, peb_k=K_ANALYTICAL, peb_temperature_c=110.0)


def test_default_analytical_chain_is_unchanged():
    """Default aerial_threshold golden: CD 27.2926 nm, NILS 4.8309 (2026-10-30).

    2026-10-03; 27.6683 / 5.0330 before the common thin-mask phase reference A5.
    """
    cfg = SimulationConfig()
    assert cfg.peb_model == "analytical"
    assert cfg.peb_k == K_ANALYTICAL
    assert cfg.peb_k_trap_per_s == K_TRAP
    assert cfg.peb_acid_lifetime_s == 7.54
    assert cfg == SimulationConfig(peb_k=K_ANALYTICAL)
    r = run_simulation(SimulationConfig())
    assert round(r.cd_nm, 4) == 27.2926
    assert round(r.nils_value, 4) == 4.8309
    # the default-marked k and a plain 10.947 run the same numbers
    chem = dict(resist_model="full_chem", grid=32, dose_mj_cm2=1.3, device="cpu")
    a = run_simulation(SimulationConfig(**chem))
    b = run_simulation(SimulationConfig(peb_k=K_ANALYTICAL, **chem))
    assert a.cd_nm == b.cd_nm
    assert a.nils_value == b.nils_value


# ── structural bands ──────────────────────────────────────────────────────


class _Job:
    cancel_requested = False

    def report(self, *args, **kwargs) -> None:
        pass


def _record(monkeypatch) -> list:
    """Stub run_simulation: CD = 32 / dose (dose-to-size 1.0), LWR 1 nm."""
    calls: list = []

    def fake_run_simulation(cfg):
        calls.append(cfg)
        return SimpleNamespace(cd_nm=32.0 / cfg.dose_mj_cm2, lwr_nm=1.0)

    monkeypatch.setattr(bands_mod, "run_simulation", fake_run_simulation)
    return calls


def _only(calls: list, law: str) -> tuple:
    """The one (peb_k, peb_k_trap_per_s) every run of ``law`` used."""
    pairs = {(c.peb_k, c.peb_k_trap_per_s) for c in calls if c.peb_model == law}
    assert len(pairs) == 1, (law, pairs)
    return pairs.pop()


def _run_bands_task(cfg: SimulationConfig) -> dict:
    task = bands_task(cfg, "default", rows=64, seeds=[1], dose_lo=0.3, dose_hi=60.0)
    return task(_Job())


@pytest.mark.parametrize("law", ["analytical", RD])
def test_bands_task_corner_k_for_a_default_config_of_either_law(monkeypatch, law):
    calls = _record(monkeypatch)
    out = _run_bands_task(SimulationConfig(resist_model="full_chem", grid=32, peb_model=law))
    k_rd, k_trap_rd = _only(calls, RD)
    assert k_rd == pytest.approx(K_NIST, abs=1e-3)  # was 10.947, rejected fix 7.283
    assert k_trap_rd == K_TRAP
    assert _only(calls, "analytical") == (K_ANALYTICAL, K_TRAP)
    # the LWR corners run the analytical law at its dose-to-size
    assert all(c.peb_model == "analytical" for c in calls if c.enable_stochastic)
    assert out["dose_to_size_mj_cm2"]["analytical"] == pytest.approx(1.0, rel=1e-3)
    assert out["peb_k_per_law"]["analytical"] == K_ANALYTICAL
    assert out["peb_k_per_law"][RD] == pytest.approx(K_NIST, abs=1e-3)


def test_bands_task_carries_an_explicit_k_across_the_laws(monkeypatch):
    calls = _record(monkeypatch)
    _run_bands_task(SimulationConfig(resist_model="full_chem", grid=32, peb_k=5.0))
    assert _only(calls, "analytical")[0] == 5.0
    assert _only(calls, RD)[0] == pytest.approx(5.0 * RATIO, rel=1e-12)

    calls.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rd_cfg = SimulationConfig(resist_model="full_chem", grid=32, peb_model=RD, peb_k=4.0)
    _run_bands_task(rd_cfg)
    assert _only(calls, RD)[0] == 4.0
    assert _only(calls, "analytical")[0] == pytest.approx(4.0 / RATIO, rel=1e-12)


def test_bands_task_with_a_peb_temperature_uses_that_temperatures_fits(monkeypatch):
    calls = _record(monkeypatch)
    _run_bands_task(SimulationConfig(resist_model="full_chem", grid=32, peb_temperature_c=90.0))
    k_nist_90, k_trap_90 = yamamoto_polymer_a_kinetics_nist_law(90.0)
    k_an_90, _ = yamamoto_polymer_a_kinetics(90.0)
    k_rd, k_trap_rd = _only(calls, RD)
    assert k_rd == pytest.approx(k_nist_90, rel=1e-12)
    assert k_trap_rd == pytest.approx(k_trap_90, rel=1e-12)
    assert _only(calls, "analytical")[0] == pytest.approx(k_an_90, rel=1e-12)


def test_structural_bands_on_a_calibrated_cli_base(monkeypatch):
    """The base of `euv calibrate --bands` carries a k fitted under the analytical law.

    It is the fixed geometry plus the fitted parameters, without a peb_model key.
    """
    calls = _record(monkeypatch)
    base = dict(period_nm=64.0, line_width_nm=32.0, se_blur_nm=2.5, peb_k=12.0)
    out = bands_mod.structural_bands(base, target_cd_nm=32.0, grid=32, rows=64, seeds=(1,))
    assert _only(calls, "analytical")[0] == 12.0
    assert _only(calls, RD)[0] == pytest.approx(12.0 * RATIO, rel=1e-12)
    assert out["peb_k_per_law"][RD] == pytest.approx(12.0 * RATIO, rel=1e-12)

    calls.clear()
    bands_mod.structural_bands(
        dict(period_nm=64.0, line_width_nm=32.0), target_cd_nm=32.0, grid=32, rows=64, seeds=(1,)
    )
    assert _only(calls, RD)[0] == pytest.approx(K_NIST, abs=1e-3)
    assert _only(calls, "analytical")[0] == K_ANALYTICAL
