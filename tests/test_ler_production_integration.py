"""STEP 5.2B — LER production integration tests.

Validates the large-N LER estimator integration into the stochastic
production path (pipeline.py):

- legacy mode reproduces the previous production behavior exactly
- default large-N mode uses stochastic_ler_grid_y=4096
- configurable field sizes (2048/4096/6144), no artificial upper bound
- deterministic block/blur equivalence (max|diff| = 0)
- stochastic non-periodicity, seed determinism/independence
- N_eff >= 30, 2048→4096 convergence <= 1 %
- subsampling/correlation controls, same-N BC control, valid shift test
- edge="both" equivalence with legacy extract_ler
- deterministic observables unchanged, dose scaling consistent
- full metadata population
"""

import math

import numpy as np
import pytest
import torch

from euvsimulator.constants import HC_EV_NM
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.exposure import dose_to_acid, gaussian_se_blur
from euvsimulator.resist.stochastic import (
    extract_edges,
    extract_ler,
    ler_estimate,
    photon_deposition_shot_noise,
)

E_PH = HC_EV_NM / 13.5
F = 6.241509074e15
DX = 0.25
THRESH = 0.3
SEED = 42

# Golden values measured on the immutable release + STEP 5.1 estimator
# (se_blur_nm=5.0, dill_C=0.05, dill_Q=1.0, dose=20 mJ/cm², seed=42,
#  stochastic_n_realisations=1).
# Golden values updated by the Option-C SE-blur path consistency
# change (STEP 5.3E-5.3I): stochastic mean energy density is now
# blur(dose) (SE-PSF transport); documented model change, NOT
# calibration.  Pre-Option-C: legacy LER=0.0925884545/LWR=0.1459884644,
# large_n LER=0.1205059215.
GOLDEN_LEGACY_LER = 0.1495450884
GOLDEN_LEGACY_LWR = 0.2358894646
GOLDEN_LARGE_N_LER = 0.1925484836
GOLDEN_N_EFF = 60.6448
GOLDEN_L_INT_NM = 8.494581
GOLDEN_RHO_TRUNC = 102


def _car_cfg(**kw):
    base = dict(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=1,
        stochastic_seed=SEED,
        se_blur_nm=5.0,
    )
    base.update(kw)
    return SimulationConfig(**base)


def _aerial():
    cfg = SimulationConfig(
        grid=256, dose_mj_cm2=1.0, se_blur_nm=0.0, resist_model="aerial_threshold"
    )
    return run_simulation(cfg).aerial_image.clone()


def _make_acid_large(dose_map, seed, n_real=1):
    """Pipeline-equivalent stochastic acid on a large field."""
    out = []
    rng = torch.Generator().manual_seed(seed)
    for _ in range(n_real):
        d_eff = photon_deposition_shot_noise(
            dose_map, 5.0, dx_nm=DX, photon_energy_eV=E_PH,
            dose_to_energy_factor=F, rng=rng,
        )
        out.append(dose_to_acid(d_eff, C=0.05, Q=1.0, apply_blur=False))
    return out


# ── 1. Legacy extraction unchanged ──────────────────────────────

def test_legacy_extract_ler_unchanged():
    """extract_ler still returns the legacy RMS observable."""
    aerial = _aerial() * 40.0
    acid = _make_acid_large(torch.tile(aerial.float(), (8, 1)), 90000)[0]
    dev = (acid > THRESH).float()
    leg = extract_ler(dev, threshold=THRESH, dx=DX, intensity=acid)
    assert leg > 0.0
    # identical observable as ler_estimate(..., edge="both") on the same field
    est = ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both")
    assert abs(est.ler_nm - leg) <= 1e-6 * leg


# ── 2. Legacy production mode reproduces previous behavior ──────

def test_legacy_mode_reproduces_previous_production():
    """estimator='legacy' must reproduce the exact previous production LER."""
    r1 = run_simulation(_car_cfg(stochastic_ler_estimator="legacy", stochastic_ler_grid_y=2048))
    r2 = run_simulation(_car_cfg(stochastic_ler_estimator="legacy", stochastic_ler_grid_y=4096))
    # grid_y must be ignored in legacy mode (no mixing)
    assert r1.ler_metadata is None
    assert r2.ler_metadata is None
    assert abs(r1.ler_nm - GOLDEN_LEGACY_LER) <= 1e-9
    assert abs(r2.ler_nm - r1.ler_nm) == 0.0
    assert abs(r2.lwr_nm - GOLDEN_LEGACY_LWR) <= 1e-9


# ── 3/4. Default large-N mode and field size ────────────────────

def test_default_large_n_mode():
    """Default uses estimator='large_n' and stochastic_ler_grid_y=4096."""
    cfg = _car_cfg()
    assert cfg.stochastic_ler_estimator == "large_n"
    assert cfg.stochastic_ler_grid_y == 4096
    r = run_simulation(cfg)
    m = r.ler_metadata
    assert m is not None
    assert m["estimator"] == "large_n"
    assert m["n_rows"] == 4096
    assert r.ler_nm > 0.0
    # golden reproducibility
    assert abs(r.ler_nm - GOLDEN_LARGE_N_LER) <= 1e-8
    assert abs(m["n_eff"] - GOLDEN_N_EFF) <= 0.5
    assert abs(m["l_int_nm"] - GOLDEN_L_INT_NM) <= 0.2
    assert m["rho_truncation"] == GOLDEN_RHO_TRUNC


def test_field_size_4096():
    r = run_simulation(_car_cfg())
    assert r.ler_metadata["n_rows"] == 4096


# ── 5/6. Configurable field sizes ───────────────────────────────

def test_field_size_2048():
    r = run_simulation(_car_cfg(stochastic_ler_grid_y=2048))
    assert r.ler_metadata["n_rows"] == 2048


def test_field_size_6144():
    r = run_simulation(_car_cfg(stochastic_ler_grid_y=6144))
    assert r.ler_metadata["n_rows"] == 6144


# ── 7. No artificial upper limit ────────────────────────────────

def test_no_artificial_upper_limit():
    """grid_y=0 and invalid estimator fail transparently; no clamping."""
    with pytest.raises(ValueError):
        SimulationConfig(stochastic_ler_grid_y=0)
    with pytest.raises(ValueError):
        SimulationConfig(stochastic_ler_estimator="bogus")


# ── 7b. Arbitrary N (STEP 5.2C: no 256-multiple requirement) ───

@pytest.mark.parametrize("n", [256, 300, 1024, 2048, 3000, 4096, 6144, 61440])
def test_arbitrary_n_rows(n):
    """Any positive grid_y must produce exactly n_rows == N (no clamping,
    no padding, no fallback to 256)."""
    r = run_simulation(_car_cfg(stochastic_ler_grid_y=n))
    m = r.ler_metadata
    assert m["n_rows"] == n
    assert r.ler_nm > 0.0
    assert m["n_eff"] > 0.0


# ── 7c. Aerial y-invariance guard (STEP 5.2C) ───────────────────

def test_aerial_y_invariance():
    """The arbitrary-N Y-extension is only justified while the aerial
    field is exactly y-invariant (every row bitwise identical).

    If a true 2D mask/RCWA field (not y-invariant) is introduced later,
    this assumption must be re-evaluated.
    """
    cfg = SimulationConfig(
        grid=256, dose_mj_cm2=1.0, se_blur_nm=0.0, resist_model="aerial_threshold"
    )
    aerial = run_simulation(cfg).aerial_image
    diff = (aerial[1:] - aerial[:-1]).abs().max()
    assert float(diff) == 0.0


# ── 8/9. Deterministic block and blur equivalence ───────────────

def test_deterministic_block_equivalence():
    aerial = _aerial()
    big = torch.tile(aerial, (8, 1))
    assert big.shape == (2048, 256)
    voxel_area = DX * DX * 1e-14
    nb = (aerial * 40.0).double() * voxel_area * F / E_PH
    nb_big = (big * 40.0).double() * voxel_area * F / E_PH
    eb = gaussian_se_blur(nb, sigma=5.0, dx=DX)
    eb_big = gaussian_se_blur(nb_big, sigma=5.0, dx=DX)
    for i in range(8):
        block = eb_big[i * 256:(i + 1) * 256, :]
        assert float((block - eb).abs().max()) == 0.0


# ── 10. Stochastic non-periodicity ──────────────────────────────

def test_stochastic_non_periodicity():
    aerial = _aerial() * 40.0
    dose_map = torch.tile(aerial.float(), (16, 1))
    acid = _make_acid_large(dose_map, 90000)[0]
    dev = (acid > THRESH).float()
    left, right = extract_edges(dev, threshold=THRESH, dx=DX, intensity=acid)
    fin = ~(torch.isnan(left) | torch.isnan(right))
    lf = left[fin]
    xc = lf - lf.mean()
    c0 = (xc * xc).mean()
    rho256 = float((xc[:-256] * xc[256:]).mean() / c0)
    # no artificial periodicity at the tile period
    assert abs(rho256) < 0.3


# ── 11/12. Seed determinism and independence ────────────────────

def test_same_seed_determinism():
    r1 = run_simulation(_car_cfg())
    r2 = run_simulation(_car_cfg())
    assert r1.ler_nm == r2.ler_nm
    assert r1.lwr_nm == r2.lwr_nm
    m1, m2 = r1.ler_metadata, r2.ler_metadata
    assert m1.keys() == m2.keys()
    for k in m1:
        v1, v2 = m1[k], m2[k]
        if isinstance(v1, float) and math.isnan(v1) and math.isnan(v2):
            continue  # NaN == NaN is False; both NaN is identical
        assert v1 == v2, f"metadata {k} differs: {v1} vs {v2}"


def test_different_seed_independence():
    aerial = _aerial() * 40.0
    dose_map = torch.tile(aerial.float(), (8, 1))
    rng1 = torch.Generator().manual_seed(90000)
    rng2 = torch.Generator().manual_seed(90001)
    e1 = torch.poisson(
        dose_map.double() * DX * DX * 1e-14 * F / E_PH, generator=rng1
    )
    e2 = torch.poisson(
        dose_map.double() * DX * DX * 1e-14 * F / E_PH, generator=rng2
    )
    frac = float((e1 != e2).float().mean())
    assert frac > 0.05  # statistically different realizations


# ── 12b. Stochastic integrity at arbitrary N=3000 (STEP 5.2C) ──

def test_stochastic_integrity_3000():
    """N=3000 (non-256-multiple): same-seed bitwise, different-seed
    independent, no artificial 256-periodicity, no repeated noise blocks."""
    # same seed -> bitwise identical production run
    r1 = run_simulation(_car_cfg(stochastic_ler_grid_y=3000))
    r2 = run_simulation(_car_cfg(stochastic_ler_grid_y=3000))
    assert r1.ler_nm == r2.ler_nm
    assert r1.lwr_nm == r2.lwr_nm
    assert r1.ler_metadata["n_rows"] == 3000

    # different seed -> independent realizations (Poisson diff-rate)
    aerial = _aerial() * 40.0
    dose_map = torch.tile(aerial.float(), (12, 1))[:3000]
    n_bar = dose_map.double() * DX * DX * 1e-14 * F / E_PH
    e1 = torch.poisson(n_bar, generator=torch.Generator().manual_seed(90000))
    e2 = torch.poisson(n_bar, generator=torch.Generator().manual_seed(90001))
    assert float((e1 != e2).float().mean()) > 0.05

    # no artificial 256-periodicity in the edge positions
    rng = torch.Generator().manual_seed(90000)
    d_eff = photon_deposition_shot_noise(
        dose_map, 5.0, dx_nm=DX, photon_energy_eV=E_PH, dose_to_energy_factor=F, rng=rng
    )
    acid = dose_to_acid(d_eff, C=0.05, Q=1.0, apply_blur=False)
    dev = (acid > THRESH).float()
    left, right = extract_edges(dev, threshold=THRESH, dx=DX, intensity=acid)
    fin = ~(torch.isnan(left) | torch.isnan(right))
    lf = left[fin]
    xc = lf - lf.mean()
    c0 = (xc * xc).mean()
    rho256 = float((xc[:-256] * xc[256:]).mean() / c0)
    assert abs(rho256) < 0.3

    # no repeated identical noise blocks: the continuous acid field of
    # rows 0-255 and 256-511 must differ almost everywhere (the binarized
    # dev field is insensitive — only pixels at the edge flip with noise)
    frac = float((acid[0:256] != acid[256:512]).float().mean())
    assert frac > 0.5


# ── 13. N_eff >= 30 ─────────────────────────────────────────────

def test_neff_ge_30():
    r = run_simulation(_car_cfg())
    assert r.ler_metadata["n_eff"] >= 30.0


# ── 14. 2048→4096 convergence ───────────────────────────────────

def test_convergence_2048_to_4096():
    aerial = _aerial() * 40.0
    seeds = range(90000, 90010)
    vals = {}
    for n, tiles in ((2048, 8), (4096, 16)):
        dose_map = torch.tile(aerial.float(), (tiles, 1))
        lers = []
        for s in seeds:
            acid = _make_acid_large(dose_map, s)[0]
            dev = (acid > THRESH).float()
            lers.append(
                ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both").ler_nm
            )
        vals[n] = np.mean(lers)
    rel = abs(vals[4096] - vals[2048]) / vals[2048] * 100
    assert rel <= 1.0


# ── 15. Subsampling control ─────────────────────────────────────

def test_subsampling_control():
    """Subsampled (spacing > L_int) rows must yield the same mean LER
    as the full sample, averaged over independent seeds (a single-field
    comparison is dominated by estimation noise at N_eff~2)."""
    aerial = _aerial() * 40.0
    seeds = range(90000, 90010)
    full_vals, sub_vals = [], []
    for s in seeds:
        dose_map = torch.tile(aerial.float(), (16, 1))
        acid = _make_acid_large(dose_map, s)[0]
        dev = (acid > THRESH).float()
        full_vals.append(
            ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both").ler_nm
        )
        sub_vals.append(
            ler_estimate(dev[::64], threshold=THRESH, dx=DX, intensity=acid[::64], edge="both").ler_nm
        )
    full_vals, sub_vals = np.array(full_vals), np.array(sub_vals)
    rel = abs(sub_vals.mean() - full_vals.mean()) / full_vals.mean() * 100
    assert rel <= 1.0


# ── 16. Correlation control ─────────────────────────────────────

def test_correlation_control():
    aerial = _aerial() * 40.0
    dose_map = torch.tile(aerial.float(), (16, 1))
    acid = _make_acid_large(dose_map, 90000)[0]
    dev = (acid > THRESH).float()
    ln = ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both", estimator="large_n")
    cc = ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both", estimator="corr_corrected")
    rel = abs(cc.ler_nm - ln.ler_nm) / ln.ler_nm * 100
    assert rel <= 3.0


# ── 17. Same-N BC control ───────────────────────────────────────

def test_same_n_bc_control():
    aerial = _aerial() * 40.0
    seeds = range(90000, 90010)
    v_ref, v_large = [], []
    for s in seeds:
        # reference: 256-row field
        acid_ref = _make_acid_large((aerial * 40.0).float(), s)[0]
        dev_ref = (acid_ref > THRESH).float()
        v_ref.append(
            ler_estimate(dev_ref, threshold=THRESH, dx=DX, intensity=acid_ref, edge="both").ler_nm
        )
        # large field, first 256 rows only (same N)
        dose_map = torch.tile((aerial * 40.0).float(), (16, 1))
        acid_large = _make_acid_large(dose_map, s)[0]
        dev_large = (acid_large > THRESH).float()
        v_large.append(
            ler_estimate(dev_large[:256], threshold=THRESH, dx=DX,
                         intensity=acid_large[:256], edge="both").ler_nm
        )
    v_ref, v_large = np.array(v_ref), np.array(v_large)
    d = v_large - v_ref
    t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    assert abs(t) <= 2.0


# ── 18. Valid shift test (0/8 nm, geometrically valid) ──────────

def test_valid_shift_08():
    """Shift invariance for the geometrically valid 0/8 nm range.

    STEP 3.10 established (N=500): global Δ=+0.38 % (t=1.09) — small,
    non-significant.  A 10-seed t-test is noise-dominated (per-seed
    differences are ~0.001 nm); 30 seeds bring t close to the
    established value."""
    aerial = _aerial() * 40.0
    aer8 = torch.roll(aerial, int(8 / DX), dims=1)
    seeds = range(90000, 90030)
    v0, v8 = [], []
    for s in seeds:
        d0 = torch.tile(aerial.float(), (16, 1))
        d8 = torch.tile(aer8.float(), (16, 1))
        a0 = _make_acid_large(d0, s)[0]
        a8 = _make_acid_large(d8, s)[0]
        dev0 = (a0 > THRESH).float()
        dev8 = (a8 > THRESH).float()
        v0.append(ler_estimate(dev0, threshold=THRESH, dx=DX, intensity=a0, edge="both").ler_nm)
        v8.append(ler_estimate(dev8, threshold=THRESH, dx=DX, intensity=a8, edge="both").ler_nm)
    v0, v8 = np.array(v0), np.array(v8)
    d = v8 - v0
    t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    assert abs(t) <= 2.0


# ── 19. Edge semantics ──────────────────────────────────────────

def test_edge_both_equivalence():
    aerial = _aerial() * 40.0
    acid = _make_acid_large(torch.tile(aerial.float(), (8, 1)), 90000)[0]
    dev = (acid > THRESH).float()
    leg = extract_ler(dev, threshold=THRESH, dx=DX, intensity=acid)  # edge="both" default
    est = ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both")
    assert abs(est.ler_nm - leg) <= 1e-6 * leg


# ── 20. Deterministic observables unchanged ─────────────────────

def test_deterministic_observables_unchanged():
    r_no = run_simulation(SimulationConfig(resist_model="full_chem", enable_stochastic=False, se_blur_nm=5.0))
    r_st = run_simulation(_car_cfg())
    assert r_no.cd_nm == r_st.cd_nm
    assert r_no.nils_value == r_st.nils_value


def test_deterministic_observables_unchanged_3000():
    """CD/NILS invariance also holds for arbitrary N=3000."""
    r_no = run_simulation(SimulationConfig(resist_model="full_chem", enable_stochastic=False, se_blur_nm=5.0))
    r_st = run_simulation(_car_cfg(stochastic_ler_grid_y=3000))
    assert r_no.cd_nm == r_st.cd_nm
    assert r_no.nils_value == r_st.nils_value


# ── 21. Dose scaling consistent with legacy ─────────────────────

def test_dose_scaling_consistent():
    aerial = _aerial()
    seeds = (90000, 90001, 90002)
    doses = (20.0, 40.0, 80.0)

    def slope_large():
        logd, logl = [], []
        for dose in doses:
            dm = torch.tile((aerial * dose).float(), (16, 1))
            lers = []
            for s in seeds:
                acid = _make_acid_large(dm, s)[0]
                dev = (acid > THRESH).float()
                lers.append(ler_estimate(dev, threshold=THRESH, dx=DX, intensity=acid, edge="both").ler_nm)
            logd.append(math.log(dose))
            logl.append(math.log(np.mean(lers)))
        return np.polyfit(logd, logl, 1)[0]

    s_ln = slope_large()
    # Large-N slope as a plausibility/regression test: the established
    # pipeline range is -0.75 ± 0.05 (STEP 5.1, shot-noise-only would be
    # -0.5; Dill chain steepens it).  The legacy N=256 slope is NOT a
    # scientific reference (dose-dependent N_eff bias distorts it).
    assert -0.85 <= s_ln <= -0.65


# ── 22. Metadata ────────────────────────────────────────────────

def test_metadata_populated():
    r = run_simulation(_car_cfg())
    m = r.ler_metadata
    assert m is not None
    for key in ("ler_nm", "n_rows", "n_eff", "l_int_px", "l_int_nm",
                "uncertainty_nm", "ci95_low_nm", "ci95_high_nm", "seed_count",
                "estimator", "rho_truncation", "disclaimer"):
        assert key in m, f"missing metadata key {key}"
    assert m["n_rows"] == 4096
    assert m["n_eff"] > 0.0
    assert m["l_int_nm"] > 0.0
    assert m["seed_count"] == 1
    assert m["estimator"] == "large_n"
    assert "experimentally validated" not in m["disclaimer"].lower() or "kein experimentell validierter" in m["disclaimer"]
    assert len(m["disclaimer"]) > 10