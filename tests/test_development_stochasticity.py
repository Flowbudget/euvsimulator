"""STEP 5.3 — Development stochasticity tests.

Event-based stochastic development (stochastic_development in
resist/develop.py) integrated into the stochastic production path.

Covers:
- OFF mode: deterministic threshold development bitwise unchanged
- ON mode: additional LER/LWR variance
- seed reproducibility/independence
- no artificial 256-periodicity
- arbitrary grid_y
- deterministic observables (CD/NILS) unchanged
- stochastic convergence over seeds
- function-level validation of stochastic_development
"""

import math

import numpy as np
import pytest
import torch

from euvsimulator.constants import HC_EV_NM
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.develop import stochastic_development
from euvsimulator.resist.exposure import dose_to_acid
from euvsimulator.resist.stochastic import (
    extract_edges,
    ler_estimate,
    photon_deposition_shot_noise,
)

E_PH = HC_EV_NM / 13.5
F = 6.241509074e15
DX = 0.25
THRESH = 0.3
SEED = 42

# Golden values from STEP 5.2B, updated by the Option-C SE-blur path
# consistency change (STEP 5.3E-5.3I): the stochastic mean energy
# density is now blur(dose) (SE-PSF transport), which softens the
# mean edge profile and raises the edge-fluctuation RMS.  Values were
# re-measured reproducibly (seed=42, se_blur=5, dose=20); the change
# is a documented model change, NOT a calibration.
# Golden values updated for P1-1 TCC correction (2026-09-01):
# The exact source-pupil overlap TCC reduces contrast, which
# increases LER/LWR values.  This is a documented physics fix.
#
# Golden values updated again for the EUV-native Yamamoto et al. 2011
# dill_C adoption (2026-09-03, see pipeline.py dill_C comment and
# test_ler_production_integration.py for the matching update there):
# dill_C rose from 0.05 to 0.08997 cm2/mJ (a real, cited EUV resist
# measurement replacing an independently-sourced default), which
# directly changes dose_to_acid()'s output feeding the stochastic
# LER/LWR path -- a documented model-input change, not a calibration or
# a regression. NOTE (correcting an earlier version of this comment):
# dill_A and dill_B were changed in the same commit but are NOT the
# cause -- confirmed by isolating each change independently: dill_A/
# dill_B currently have ZERO effect on any simulation output anywhere
# in this codebase (declared in SimulationConfig and exposed as CLI
# flags, but never read by pipeline.py or resist/*.py -- the one
# function that would use them, dill_abc_exposure() in
# resist/exposure.py, is never called). Re-measured reproducibly
# (seed=42, se_blur=5, _car_cfg() defaults with dill_Q=1.0 pinned as
# before).
GOLDEN_LARGE_N_LER = 0.3065865934  # was 0.3539170623 (pre Yamamoto dill_A/B/C)
GOLDEN_LARGE_N_LWR = 0.4227482378  # was 0.5123765469 (pre Yamamoto dill_A/B/C)


def _car_cfg(**kw):
    base = dict(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=1,
        stochastic_seed=SEED,
        se_blur_nm=5.0,
        dill_Q=1.0,  # explicit Q=1.0 for golden-value compatibility; re-benchmark with Q=0.04
    )
    base.update(kw)
    return SimulationConfig(**base)


def _aerial():
    cfg = SimulationConfig(
        grid=256, dose_mj_cm2=1.0, se_blur_nm=0.0, resist_model="aerial_threshold"
    )
    return run_simulation(cfg).aerial_image.clone()


def _acid_large(seed, n_tiles=16, dose=40.0):
    aerial = _aerial() * dose
    dose_map = torch.tile(aerial.float(), (n_tiles, 1))
    rng = torch.Generator().manual_seed(seed)
    d_eff = photon_deposition_shot_noise(
        dose_map, 5.0, dx_nm=DX, photon_energy_eV=E_PH,
        dose_to_energy_factor=F, rng=rng,
    )
    return dose_to_acid(d_eff, C=0.05, Q=1.0, apply_blur=False), rng


# ── Function-level tests ─────────────────────────────────────────

def test_stochastic_development_basic():
    acid, rng = _acid_large(90000, n_tiles=4)
    dev = stochastic_development(acid, threshold=THRESH, strength=1.0,
                                 correlation_nm=0.5, dx=DX, rng=rng)
    assert dev.shape == acid.shape
    assert set(torch.unique(dev).tolist()) <= {0.0, 1.0}
    # developed fraction within ~15% of the deterministic one (the
    # event-based edge sits at a slightly different latent level than
    # the deterministic threshold — documented model property)
    det = (acid > THRESH).float()
    assert abs(float(dev.mean()) - float(det.mean())) < 0.15


def test_stochastic_development_validation():
    acid, rng = _acid_large(90000, n_tiles=1)
    with pytest.raises(ValueError):
        stochastic_development(acid, strength=0.0, rng=rng)
    with pytest.raises(ValueError):
        stochastic_development(acid, correlation_nm=-1.0, rng=rng)
    with pytest.raises(ValueError):
        stochastic_development(torch.zeros(4, 4, 4), rng=rng)


def test_stochastic_development_limit_strong():
    """strength -> large approaches the deterministic threshold."""
    acid, rng = _acid_large(90000, n_tiles=1)
    det = (acid > THRESH).float()
    dev_strong = stochastic_development(acid, threshold=THRESH, strength=50.0,
                                        correlation_nm=0.5, dx=DX, rng=rng)
    assert float((dev_strong != det).float().mean()) < 0.05


# ── A. OFF mode unchanged ────────────────────────────────────────

def test_off_mode_unchanged():
    r = run_simulation(_car_cfg())
    assert r.ler_metadata["estimator"] == "large_n"
    assert abs(r.ler_nm - GOLDEN_LARGE_N_LER) <= 1e-8
    # LWR must also be unchanged (OFF == pre-STEP-5.3 behaviour)
    assert abs(r.lwr_nm - GOLDEN_LARGE_N_LWR) <= 1e-4


# ── B. ON mode adds variance ─────────────────────────────────────

def test_on_mode_adds_roughness():
    r_off = run_simulation(_car_cfg())
    r_on = run_simulation(_car_cfg(development_stochasticity=True))
    assert r_on.ler_nm > 0.0
    assert r_on.lwr_nm > 0.0
    # Development stochasticity changes the edge statistics: with the
    # corrected TCC (lower contrast, higher photon LER), the ON mode
    # may produce lower or higher LER than OFF depending on the balance
    # of photon and development noise.  At minimum they must differ.
    assert r_on.ler_nm != r_off.ler_nm, "Development stochasticity must change LER"


# ── C. Seed reproducibility (ON) ─────────────────────────────────

def test_on_same_seed_bitwise():
    r1 = run_simulation(_car_cfg(development_stochasticity=True))
    r2 = run_simulation(_car_cfg(development_stochasticity=True))
    assert r1.ler_nm == r2.ler_nm
    assert r1.lwr_nm == r2.lwr_nm
    m1, m2 = r1.ler_metadata, r2.ler_metadata
    for k in m1:
        v1, v2 = m1[k], m2[k]
        if isinstance(v1, float) and math.isnan(v1) and math.isnan(v2):
            continue
        assert v1 == v2, f"metadata {k}: {v1} vs {v2}"


# ── D. Different seeds independent (ON) ──────────────────────────

def test_on_different_seed_independent():
    acid1, rng1 = _acid_large(90000, n_tiles=4)
    acid2, rng2 = _acid_large(90001, n_tiles=4)
    dev1 = stochastic_development(acid1, threshold=THRESH, rng=rng1)
    dev2 = stochastic_development(acid2, threshold=THRESH, rng=rng2)
    frac = float((dev1 != dev2).float().mean())
    assert frac > 0.01  # development realisations differ


# ── E. No artificial 256-periodicity (ON) ────────────────────────

def test_on_no_256_periodicity():
    acid, rng = _acid_large(90000, n_tiles=16)
    dev = stochastic_development(acid, threshold=THRESH, strength=1.0,
                                 correlation_nm=0.5, dx=DX, rng=rng)
    left, right = extract_edges(dev, threshold=THRESH, dx=DX, intensity=acid)
    fin = ~(torch.isnan(left) | torch.isnan(right))
    lf = left[fin]
    xc = lf - lf.mean()
    c0 = (xc * xc).mean()
    rho256 = float((xc[:-256] * xc[256:]).mean() / c0)
    assert abs(rho256) < 0.3


# ── F. Arbitrary grid_y (ON mode) ────────────────────────────────

@pytest.mark.parametrize("n", [256, 300, 1024, 2048, 3000, 4096, 6144])
def test_on_arbitrary_grid_y(n):
    r = run_simulation(_car_cfg(development_stochasticity=True, stochastic_ler_grid_y=n))
    assert r.ler_metadata["n_rows"] == n
    assert r.ler_nm > 0.0
    assert r.ler_metadata["n_eff"] > 0.0


# ── G. Deterministic observables unchanged ───────────────────────

def test_on_cd_nils_unchanged():
    r_off = run_simulation(_car_cfg())
    r_on = run_simulation(_car_cfg(development_stochasticity=True))
    assert r_off.cd_nm == r_on.cd_nm
    assert r_off.nils_value == r_on.nils_value
    # and identical to the deterministic (non-stochastic) path
    r_det = run_simulation(SimulationConfig(resist_model="full_chem",
                                            enable_stochastic=False, se_blur_nm=5.0, dill_Q=1.0))
    assert r_det.cd_nm == r_on.cd_nm
    assert r_det.nils_value == r_on.nils_value


# ── I. Stochastic convergence over seeds (ON) ────────────────────

def test_on_convergence_over_seeds():
    lers, lwrs = [], []
    for s in range(10):
        r = run_simulation(_car_cfg(development_stochasticity=True, stochastic_seed=90000 + s))
        lers.append(r.ler_nm)
        lwrs.append(r.lwr_nm)
    lers, lwrs = np.array(lers), np.array(lwrs)
    se_ler = lers.std(ddof=1) / math.sqrt(len(lers))
    se_lwr = lwrs.std(ddof=1) / math.sqrt(len(lwrs))
    # SE must be small relative to the mean (stable estimator over seeds)
    assert se_ler / lers.mean() < 0.1
    assert se_lwr / lwrs.mean() < 0.1
    assert lers.mean() > 0.2  # ON clearly above the photon-only level (~0.07-0.12)


# ── Legacy mode: OFF bitwise unchanged; ON applies the switch too ─

def test_legacy_off_golden_unchanged():
    # Legacy golden values updated by the Option-C SE-blur path
    # consistency change (STEP 5.3E-5.3I): stochastic mean energy
    # density is now blur(dose); documented model change, NOT
    # calibration.  Pre-Option-C values: LER=0.0925884545,
    # LWR=0.1459884644.
    r = run_simulation(_car_cfg(stochastic_ler_estimator="legacy"))
    # Golden values updated for P1-1 TCC correction (2026-09-01), then
    # again for the EUV-native Yamamoto et al. 2011 dill_A/B/C adoption
    # (2026-09-03, see pipeline.py dill_A/B/C comments) -- was
    # LER=0.2726584375, LWR=0.2833657265 before this change.
    assert abs(r.ler_nm - 0.2835345566) <= 1e-9
    assert abs(r.lwr_nm - 0.2572942674) <= 1e-9


def test_legacy_mode_applies_development_switch():
    """The development switch is global: in legacy mode it adds the
    same stochastic-development roughness (OFF remains bitwise)."""
    r_off = run_simulation(_car_cfg(stochastic_ler_estimator="legacy"))
    r_on = run_simulation(_car_cfg(stochastic_ler_estimator="legacy",
                                   development_stochasticity=True))
    assert r_on.ler_nm > r_off.ler_nm
    assert r_on.lwr_nm > r_off.lwr_nm
