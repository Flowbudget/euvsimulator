"""Single-source anchor: Yamamoto et al. 2011, J. Photopolym. Sci. Technol. 24(4) 405.

The default resist parameters are Yamamoto's Polymer A. The same paper
measured, on the same resist at the same PEB condition (110 °C / 60 s, 2.38 %
TMAH 30 s):

* Fig. 3 -- FTIR protection ratio P(t) during PEB after 1.4 mJ/cm² flood
  exposure at 110 °C: P(5 s) ≈ 0.60, P(10) ≈ 0.35, P(20) ≈ 0.22, P(40) ≈ 0.18,
  P(60) ≈ 0.18 (read from the figure, ±0.03 each).
* Fig. 4 -- Arrhenius plot of the deprotection rate: Kdp(110 °C) ≈ 1.4 s⁻¹.
* Fig. 5 -- RDA dissolution rate vs. flood dose, 35 % protection: threshold
  (R ≈ R_max/2) at ≈ 0.8 mJ/cm² (axis-calibrated reading, ±10 %).

History: with Table 2's PROLITH Arrhenius pair (k = 0.0723 s⁻¹, no acid
loss) the chain gave P(60 s) = 0.60 and a threshold of 2.75 mJ/cm² -- both
≈ 3.4× off -- and no acid lifetime alone could fix it (log Fortsetzung
15/20). Since 2026-09-05 the defaults carry the Fig. 3/4 rate (k·H = 0.166 s⁻¹
at 1.4 mJ/cm²) and an acid lifetime τ = 10.5 s (from the Fig. 3 plateau);
Fig. 5 was NOT used to set either, so the threshold test below is an
independent check. Since 2026-09-06 (stage A2) dill_C is the directly
measured 0.0152 cm²/mJ and the same rate is carried as k = 7.87 s⁻¹ (the
Table-2 guard test below keeps Table 2's own C = 0.08997).
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

    Returns (acid, M after PEB, dissolution rate at the film surface).
    """
    dose = torch.full((2, 2), dose_mj_cm2, dtype=torch.float64)
    acid, inhib = dill_abc_exposure(
        dose,
        A=cfg.dill_A,
        B=cfg.dill_B,
        C=cfg.dill_C,
        thickness=cfg.resist_thickness_nm * 1e-3,
        n_layers=cfg.n_develop_layers,
    )
    # surface layer (index 0) -- no absorption gradient yet. The CAR starts the
    # PEB fully protected (M0 = 1, Mack 1997 Eq. 5.33/5.34); the exposure
    # step's "inhibitor" is the remaining PAG fraction and is NOT M0 -- the
    # pipeline discards it the same way (pipeline.py, _cd_via_full_chem).
    a0 = acid[0]
    _, M = reaction_diffusion_analytical(
        a0,
        torch.ones_like(a0),
        k=cfg.peb_k,
        t_bake=cfg.peb_t_bake,
        sigma_diff=0.0,
        acid_lifetime_s=cfg.peb_acid_lifetime_s,
    )
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


def test_fig3_protection_ratio_after_peb():
    cfg = SimulationConfig()
    _, M, _ = _chain_surface(FIG3_DOSE_MJ_CM2, cfg)
    assert abs(M - FIG3_P_60S_110C) < FIG3_TOL, (
        f"P(60 s) chain = {M:.3f}, Fig. 3 ≈ {FIG3_P_60S_110C}"
    )


def test_fig5_dissolution_threshold():
    cfg = SimulationConfig()
    e_th = _threshold_dose(cfg)
    assert abs(e_th / FIG5_THRESHOLD_MJ_CM2 - 1.0) < FIG5_TOL_REL, (
        f"threshold chain = {e_th:.2f} mJ/cm², Fig. 5 ≈ {FIG5_THRESHOLD_MJ_CM2}"
    )


def test_fig3_full_curve():
    """All five read points of the 110 °C deprotection curve."""
    cfg = SimulationConfig()
    fig3 = {5.0: 0.60, 10.0: 0.35, 20.0: 0.22, 40.0: 0.18, 60.0: 0.18}
    for t, p_meas in fig3.items():
        dose = torch.full((2, 2), FIG3_DOSE_MJ_CM2, dtype=torch.float64)
        acid, _ = dill_abc_exposure(
            dose, A=cfg.dill_A, B=cfg.dill_B, C=cfg.dill_C, thickness=0.05, n_layers=2
        )
        _, M = reaction_diffusion_analytical(
            acid[0],
            torch.ones_like(acid[0]),
            k=cfg.peb_k,
            t_bake=t,
            sigma_diff=0.0,
            acid_lifetime_s=cfg.peb_acid_lifetime_s,
        )
        assert abs(float(M.mean()) - p_meas) < 0.1, (t, float(M.mean()), p_meas)


def test_chain_numbers_are_pinned():
    """Pins what the default chain does so that a drift of the default set
    (k, τ, C, Mack) shows up here first.
    """
    cfg = SimulationConfig()
    acid, M, _ = _chain_surface(FIG3_DOSE_MJ_CM2, cfg)
    assert acid == pytest.approx(1.0 - math.exp(-cfg.dill_C * FIG3_DOSE_MJ_CM2), rel=1e-6)
    assert M == pytest.approx(0.18, abs=0.02)
    assert _threshold_dose(cfg) == pytest.approx(0.75, abs=0.03)


def test_table2_arrhenius_pair_is_rejected_for_a_reason():
    """The former default (Table 2: k = 0.0723 s⁻¹, no loss) misses both
    measurements by the same factor -- kept as a guard against reverting.
    """
    cfg = SimulationConfig(dill_C=0.08997, peb_k=0.0723, peb_acid_lifetime_s=None)
    _, M, _ = _chain_surface(FIG3_DOSE_MJ_CM2, cfg)
    assert M == pytest.approx(0.60, abs=0.02)
    assert _threshold_dose(cfg) == pytest.approx(2.75, abs=0.1)
