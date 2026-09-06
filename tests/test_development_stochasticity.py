"""Development stochasticity: the former event-based model (disabled 2026-09-04,
audit A6) and the OFF-path goldens; the derived cell-noise model that the flag
enables since 2026-09-06 is tested in tests/test_dissolution_cell_noise.py.

The event-based model (``resist/develop.py::stochastic_development``) drove
its Poisson event rate with (depth − thickness)/thickness, a quantity bounded
by one depth layer, so its pipeline output depended on ``n_develop_layers``
(LWR 1.44 nm at N=21 vs 0.17 nm at N=41 for identical physics) and its
``strength`` was a fitted, unit-less knob. The pipeline therefore refuses
``development_stochasticity=True``; the standalone function is kept as an
experimental building block and keeps its function-level tests.

Also pinned here: the OFF path is the production path and reproduces its
golden values (see test_ler_production_integration.py for their provenance).
"""

import math

import numpy as np
import pytest
import torch

from euvsimulator.constants import HC_EV_NM
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.develop import stochastic_development
from euvsimulator.resist.exposure import dose_to_acid
from euvsimulator.resist.stochastic import extract_edges, photon_deposition_shot_noise

E_PH = HC_EV_NM / 13.5
F = 6.241509074e15
DX = 0.25
THRESH = 0.3
SEED = 42

# mJ/cm² at the wafer, near dose-to-size (1.27) at TEST_SIGMA with the 2026-09-05
# acid-lifetime default
TEST_DOSE = 1.1
TEST_SIGMA = 7.0  # nm PEB blur for the regression operating point
# Regression pins, re-measured 2026-09-04 Phase 2b (exact blur, z-diffusion,
# Eikonal front, sigma_PEB 7 / 4.0 mJ/cm2); see the provenance note in
# test_ler_production_integration.py. Phase 0 values: 2.8802534977 /
# 5.6471533713; pre-Phase-0: 0.3251749642 / 0.6158645956.
GOLDEN_LARGE_N_LER = (
    3.4895922982  # 2026-09-05 acid lifetime, TEST_DOSE 1.1 (Dill-B step: 1.4022154241)
)
GOLDEN_LARGE_N_LWR = (
    6.5894303010  # 2026-09-05 acid lifetime, TEST_DOSE 1.1 (Dill-B step: 2.3954591804)
)


def _car_cfg(**kw):
    base = dict(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=1,
        stochastic_seed=SEED,
        se_blur_nm=5.0,
        dose_mj_cm2=TEST_DOSE,
        # Operating point (2026-09-04, Phase 2b): with the exact PEB blur and
        # the Eikonal development front, the then-default sigma_PEB = 19.9 nm gave
        # the 32 nm line at 64 nm pitch only in a knife-edge dose window (CD
        # 35.5 -> 14 -> 0 between 5.0 and 6.0 mJ/cm2); the stochastic machinery
        # is therefore exercised at sigma_PEB = 7 nm (smooth window, CD 31.5 nm
        # at 4.0 mJ/cm2). This is a choice of test operating point, not a
        # physics default -- the default sigma is Phase 3's subject.
        peb_sigma_diff=TEST_SIGMA,
    )
    base.update(kw)
    return SimulationConfig(**base)


def _aerial():
    cfg = SimulationConfig(
        grid=256, dose_mj_cm2=1.0, se_blur_nm=0.0, resist_model="aerial_threshold"
    )
    return run_simulation(cfg).aerial_image.clone()


def _acid_large(seed, n_tiles=4):
    """Synthetic stochastic acid map on a tiled field (function-level tests)."""
    aerial = _aerial() * 40.0
    dose_map = torch.tile(aerial.float(), (n_tiles, 1))
    rng = torch.Generator().manual_seed(seed)
    d_eff = photon_deposition_shot_noise(
        dose_map,
        5.0,
        dx_nm=DX,
        photon_energy_eV=E_PH,
        dose_to_energy_factor=F,
        rng=rng,
    )
    return dose_to_acid(d_eff, C=0.05, apply_blur=False), rng


# ── Pipeline: the switch is refused ─────────────────────────────


def test_development_stochasticity_is_accepted_since_b3():
    """Since 2026-09-06 the flag enables resist/develop.dissolution_cell_noise
    (tests/test_dissolution_cell_noise.py); it no longer raises.
    """
    cfg = SimulationConfig(
        resist_model="full_chem", enable_stochastic=True, development_stochasticity=True
    )
    assert cfg.development_stochasticity is True


def test_removed_strength_fields_are_rejected():
    with pytest.raises(TypeError):
        SimulationConfig(development_strength=15.0)
    with pytest.raises(TypeError):
        SimulationConfig(development_correlation_nm=0.5)


# ── Pipeline: OFF path unchanged ────────────────────────────────


def test_off_mode_unchanged():
    r = run_simulation(_car_cfg())
    assert r.ler_metadata["estimator"] == "large_n"
    assert abs(r.ler_nm - GOLDEN_LARGE_N_LER) <= 1e-8
    assert abs(r.lwr_nm - GOLDEN_LARGE_N_LWR) <= 1e-4


def test_legacy_off_golden_unchanged():
    r = run_simulation(_car_cfg(stochastic_ler_estimator="legacy"))
    # Re-measured 2026-09-04 Phase 2b (see the GOLDEN note above); Phase 0
    # values 0.6648028427 / 1.2965263709, pre-Phase-0 0.0860674324 / 0.1297861139.
    # 2026-09-05 acid lifetime, TEST_DOSE 1.1 (Dill-B step: 0.3398195917 / 0.5112461853)
    assert abs(r.ler_nm - 0.8785620416) <= 1e-9
    assert abs(r.lwr_nm - 1.7051756192) <= 1e-9


# ── Function-level tests of the standalone building block ───────


def test_stochastic_development_basic():
    acid, rng = _acid_large(90000, n_tiles=4)
    dev = stochastic_development(
        acid, threshold=THRESH, strength=1.0, correlation_nm=0.5, dx=DX, rng=rng
    )
    assert dev.shape == acid.shape
    assert set(torch.unique(dev).tolist()) <= {0.0, 1.0}
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
    """Strength -> large approaches the deterministic threshold."""
    acid, rng = _acid_large(90000, n_tiles=1)
    det = (acid > THRESH).float()
    dev_strong = stochastic_development(
        acid, threshold=THRESH, strength=50.0, correlation_nm=0.5, dx=DX, rng=rng
    )
    assert float((dev_strong != det).float().mean()) < 0.05


def test_different_seed_independent():
    acid1, rng1 = _acid_large(90000, n_tiles=4)
    acid2, rng2 = _acid_large(90001, n_tiles=4)
    dev1 = stochastic_development(acid1, threshold=THRESH, rng=rng1)
    dev2 = stochastic_development(acid2, threshold=THRESH, rng=rng2)
    frac = float((dev1 != dev2).float().mean())
    assert frac > 0.01


def test_no_256_periodicity():
    acid, rng = _acid_large(90000, n_tiles=16)
    dev = stochastic_development(
        acid, threshold=THRESH, strength=1.0, correlation_nm=0.5, dx=DX, rng=rng
    )
    left, right = extract_edges(dev, threshold=THRESH, dx=DX, intensity=acid)
    fin = ~(torch.isnan(left) | torch.isnan(right))
    lf = left[fin]
    xc = lf - lf.mean()
    c0 = (xc * xc).mean()
    rho256 = float((xc[:-256] * xc[256:]).mean() / c0)
    assert abs(rho256) < 0.3
