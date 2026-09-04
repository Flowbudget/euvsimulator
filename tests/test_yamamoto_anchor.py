"""Single-source anchor: Yamamoto et al. 2011, J. Photopolym. Sci. Technol. 24(4) 405.

The default resist parameters (dill_B/C, peb_k, mack_*) are Table 2 of that
paper ("Calculation parameters of Polymer A on PROLITH").  The same paper
measured, on the same resist at the same PEB condition (110 °C / 60 s, 2.38 %
TMAH 30 s):

* Fig. 3 -- FTIR protection ratio P(t) during PEB after 1.4 mJ/cm² flood
  exposure: P(60 s, 110 °C) ≈ 0.18 (plateau 0.17; read from the figure,
  ±0.03).
* Fig. 5 -- RDA dissolution rate vs. flood dose, 35 % protection: R = 0.1 nm/s
  up to 0.65 mJ/cm², 1.5 nm/s at 0.75, ≈ 60 nm/s from 0.84 mJ/cm²
  (axis-calibrated reading, ±10 % in dose).

Implemented in the standard Mack forms this chain uses, Table 2 gives
P(60 s) = 0.60 and a dissolution threshold of ≈ 2.7 mJ/cm² -- the same factor
≈ 3.4 in k·C from two independent figures.  The paper's own kinetics (its
Eq. 1) has an acid-loss term and a reaction order that Table 2 does not carry
and for which no values are published.

These tests are therefore ``xfail(strict=True)``: they encode the primary
measurements as the falsification target, fail today for a documented
reason, and will start FAILING-AS-UNEXPECTED-PASS the moment a model change
makes the chain reproduce its own source -- at which point the caveat in
pipeline.py must be revisited.  The last test pins the chain's current
numbers so a silent drift of the default set shows up.
"""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig
from euvsimulator.resist.develop import MackModel
from euvsimulator.resist.exposure import dill_abc_exposure
from euvsimulator.resist.peb import reaction_diffusion_analytical

# Readings from the paper (figure-derived, see module docstring)
FIG3_DOSE_MJ_CM2 = 1.4
FIG3_P_60S_110C = 0.18
FIG3_TOL = 0.06  # generous: covers the ±0.03 reading twice

FIG5_THRESHOLD_MJ_CM2 = 0.80  # dose at R ≈ R_max/2 for the 35 % curve
FIG5_TOL_REL = 0.30


def _chain_surface(dose_mj_cm2: float, cfg: SimulationConfig) -> tuple[float, float, float]:
    """Flood exposure -> PEB (no diffusion needed for a uniform field) -> Mack rate.

    Returns (acid, M after PEB, dissolution rate at the film surface)."""
    dose = torch.full((2, 2), dose_mj_cm2, dtype=torch.float64)
    acid, inhib = dill_abc_exposure(
        dose, A=cfg.dill_A, B=cfg.dill_B, C=cfg.dill_C,
        thickness=cfg.resist_thickness_nm * 1e-3, n_layers=cfg.n_develop_layers,
    )
    # surface layer (index 0) -- no absorption gradient yet. The CAR starts the
    # PEB fully protected (M0 = 1, Mack 1997 Eq. 5.33/5.34); the exposure
    # step's "inhibitor" is the remaining PAG fraction and is NOT M0 -- the
    # pipeline discards it the same way (pipeline.py, _cd_via_full_chem).
    a0 = acid[0]
    _, M = reaction_diffusion_analytical(a0, torch.ones_like(a0), k=cfg.peb_k, t_bake=cfg.peb_t_bake, sigma_diff=0.0)
    mack = MackModel(R_max=cfg.mack_R_max, R_min=cfg.mack_R_min, M_th=cfg.mack_M_th, n=cfg.mack_n)
    R = mack.rate(M)
    return float(a0.mean()), float(M.mean()), float(R.mean())


def _threshold_dose(cfg: SimulationConfig) -> float:
    """Bisect the flood dose at which the surface rate reaches R_max/2."""
    target = 0.5 * cfg.mack_R_max
    lo, hi = 0.05, 50.0
    assert _chain_surface(lo, cfg)[2] < target < _chain_surface(hi, cfg)[2]
    for _ in range(40):
        mid = math.sqrt(lo * hi)
        if _chain_surface(mid, cfg)[2] < target:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


@pytest.mark.xfail(
    strict=True,
    reason="Yamamoto 2011 Table 2 in standard Mack form deprotects ~3.4x too little "
    "(P(60 s) = 0.60 vs Fig. 3 ≈ 0.18); the source's acid-loss/order terms are unpublished",
)
def test_fig3_protection_ratio_after_peb():
    cfg = SimulationConfig()
    _, M, _ = _chain_surface(FIG3_DOSE_MJ_CM2, cfg)
    assert abs(M - FIG3_P_60S_110C) < FIG3_TOL, f"P(60 s) chain = {M:.3f}, Fig. 3 ≈ {FIG3_P_60S_110C}"


@pytest.mark.xfail(
    strict=True,
    reason="chain dissolution threshold ≈ 2.7 mJ/cm² vs Fig. 5 ≈ 0.8 mJ/cm² (same factor as Fig. 3)",
)
def test_fig5_dissolution_threshold():
    cfg = SimulationConfig()
    e_th = _threshold_dose(cfg)
    assert abs(e_th / FIG5_THRESHOLD_MJ_CM2 - 1.0) < FIG5_TOL_REL, (
        f"threshold chain = {e_th:.2f} mJ/cm², Fig. 5 ≈ {FIG5_THRESHOLD_MJ_CM2}"
    )


def test_chain_numbers_are_pinned():
    """Pins what the default chain currently does, so that the factor documented
    in pipeline.py (≈ 3.4) cannot drift silently."""
    cfg = SimulationConfig()
    acid, M, _ = _chain_surface(FIG3_DOSE_MJ_CM2, cfg)
    assert acid == pytest.approx(1.0 - math.exp(-cfg.dill_C * FIG3_DOSE_MJ_CM2), rel=1e-6)
    assert M == pytest.approx(0.598, abs=0.005)
    e_th = _threshold_dose(cfg)
    assert e_th == pytest.approx(2.7, abs=0.1)
    # the two independent figure readings imply the same shortfall in k*C
    factor_fig3 = -math.log(FIG3_P_60S_110C) / -math.log(M)
    factor_fig5 = e_th / FIG5_THRESHOLD_MJ_CM2
    assert 2.5 < factor_fig3 < 4.5
    assert 2.5 < factor_fig5 < 4.5
