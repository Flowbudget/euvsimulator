"""Test that full_chem resist parameters are configurable and affect internal chemistry."""

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig, run_simulation


def test_full_chem_params_passed_through():
    """Verify resist params are accepted and stored in config."""
    cfg = SimulationConfig(
        resist_model="full_chem",
        dill_C=0.1,
        peb_k=0.25,
        peb_t_bake=90.0,
        peb_sigma_diff=3.0,
        mack_R_max=200.0,
        mack_R_min=0.05,
        mack_n=8.0,
        mack_M_th=0.3,
        grid=128,
    )
    assert cfg.dill_C == 0.1
    assert cfg.peb_k == 0.25
    assert cfg.peb_t_bake == 90.0
    assert cfg.peb_sigma_diff == 3.0
    assert cfg.mack_R_max == 200.0
    assert cfg.mack_R_min == 0.05
    assert cfg.mack_n == 8.0
    assert cfg.mack_M_th == 0.3


def test_full_chem_chemistry_affected_by_params():
    """Resist params affect the helper chemistry (acid, inhib, dev_chem).

    These helpers (dose_to_acid, reaction_diffusion_analytical,
    threshold_development) are the analytic building blocks; the pipeline's
    full_chem path uses dill_abc_exposure, its own PEB and the Mack front.
    """
    import math

    from euvsimulator.aerial.abbe import aerial_from_orders
    from euvsimulator.resist.develop import threshold_development
    from euvsimulator.resist.exposure import dose_to_acid
    from euvsimulator.resist.peb import reaction_diffusion_analytical

    # Build aerial image
    G = 128
    period_m = 64e-9
    na = 0.33
    wl_m = 13.5e-9
    sigma = 0.8
    r_space = 0.7 + 0j
    r_abs = 0.05 + 0j
    duty = 0.5
    c0 = r_abs * duty + r_space * (1 - duty)
    oi = [-1, 0, 1]
    amps = []
    for m in oi:
        if m == 0:
            amps.append(c0)
        else:
            amps.append((r_abs - r_space) * math.sin(math.pi * m * duty) / (math.pi * m))

    orders_complex = torch.tensor(amps, dtype=torch.complex128)
    order_indices = torch.tensor(oi)
    ae = aerial_from_orders(orders_complex, order_indices, period_m, na, wl_m, sigma, grid=G)
    ae_dose = ae * 40.0  # Use higher dose to ensure acid is well above threshold
    dx_nm = 64.0 / G

    # Test dill_C affects acid
    acid_low = dose_to_acid(ae_dose, C=0.01, sigma_blur=0.0, dx=dx_nm, apply_blur=False)
    acid_high = dose_to_acid(ae_dose, C=0.2, sigma_blur=0.0, dx=dx_nm, apply_blur=False)
    assert acid_high.mean() > acid_low.mean(), "Higher dill_C should produce more acid"

    # Test peb_k affects inhibitor
    inhib_low = torch.ones_like(acid_high)
    inhib_high = torch.ones_like(acid_high)
    _, inhib_low = reaction_diffusion_analytical(
        acid_high, inhib_low, k=0.1, t_bake=60.0, sigma_diff=5.0, dx=dx_nm
    )
    _, inhib_high = reaction_diffusion_analytical(
        acid_high, inhib_high, k=0.5, t_bake=60.0, sigma_diff=5.0, dx=dx_nm
    )
    assert inhib_high.mean() < inhib_low.mean(), (
        "Higher peb_k should deprotect more (lower inhibitor)"
    )

    # Threshold affects the developed fraction.  The thresholds must lie inside
    # the inhibitor range: after this PEB the inhibitor is <= 0.002, so the
    # former fixed 0.1 / 0.9 both developed every pixel and ">=" held trivially.
    # explicit dtype: other test modules change torch's default dtype at import
    q = torch.tensor([0.25, 0.75], dtype=torch.float64)
    lo_t, hi_t = torch.quantile(inhib_low.flatten().to(torch.float64), q).tolist()
    dev_low = threshold_development(inhib_low, threshold=lo_t)
    dev_high = threshold_development(inhib_low, threshold=hi_t)
    assert dev_high.mean() > dev_low.mean(), "Higher threshold should develop more"


def test_both_paths_produce_reasonable_cd():
    """Both aerial_threshold and full_chem give reasonable CDs (different by design).

    The aerial_threshold path uses a threshold on the aerial image.
    The full_chem path uses the depth-resolved, time-integrated Mack
    development front (dill_abc_exposure + MackModel via
    surface_advancement_level_set, wired in 2026-09-03).

    Note (2026-09-03): with the real, EUV-native, cited defaults now in
    SimulationConfig (dill_A/B/C/Q from Yamamoto et al. 2011 and Mack et
    al. 2011; see pipeline.py's dill_A/B and mack_R_max comments), plain
    defaults already produce a realistic, non-degenerate CD -- no more
    hand-tuned override values are needed to route around the old
    CD=64.0/0.0 degeneracy (that degeneracy is fixed, not worked around;
    see pipeline.py's "RESOLVED" note above mack_R_max/mack_R_min).
    """
    cfg1 = SimulationConfig(resist_model="aerial_threshold", grid=128)
    # full_chem at a printable operating point (2026-09-04: wafer-dose
    # convention, acid yield saturating at 1, Eikonal development front). At
    # the aerial_threshold model's reference dose of 20 mJ/cm² the resist is
    # fully cleared (CD = 0) -- physics, not a failure -- and at the default
    # then-default 19.9 nm PEB blur the 32 nm line existed only in a knife-edge dose window,
    # so the test uses sigma_PEB = 7 nm / 4.0 mJ/cm² like the stochastic
    # regression tests (see test_ler_production_integration._car_cfg).
    cfg2 = SimulationConfig(resist_model="full_chem", grid=128, dose_mj_cm2=1.1, peb_sigma_diff=7.0)

    r1 = run_simulation(cfg1)
    r2 = run_simulation(cfg2)

    # Both should give positive, non-zero CDs
    assert r1.cd_nm > 0, f"aerial_threshold CD should be positive: {r1.cd_nm}"
    assert r2.cd_nm > 0, f"full_chem CD should be positive: {r2.cd_nm}"
    # Both should be in reasonable range for the nominal 32 nm line
    assert 5 < r1.cd_nm < 50, f"aerial_threshold CD out of range: {r1.cd_nm}"
    assert 5 < r2.cd_nm < 50, f"full_chem CD out of range: {r2.cd_nm}"


def test_config_file_with_resist_params(tmp_path):
    """Test loading resist params from YAML config file."""
    import yaml

    config = {
        "resist_model": "full_chem",
        "dill_C": 0.1,
        "peb_k": 0.25,
        "peb_t_bake": 90.0,
        "mack_R_max": 150.0,
        "grid": 128,
    }
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(yaml.dump(config))

    from euvsimulator.pipeline import SimulationConfig

    cfg = SimulationConfig(**yaml.safe_load(config_path.read_text(encoding="utf-8")))
    assert cfg.dill_C == 0.1
    assert cfg.peb_k == 0.25
    assert cfg.peb_t_bake == 90.0
    assert cfg.mack_R_max == 150.0


def test_cli_resist_model_option():
    """Test that --resist-model CLI option works."""
    import os
    import subprocess

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Resolve the console script from the interpreter's own environment: the
    # venv bin directory is not necessarily on PATH when pytest is started as
    # a virtual environment -m pytest.
    import shutil
    import sys

    cli = shutil.which("euv") or os.path.join(os.path.dirname(sys.executable), "euv")
    result = subprocess.run(
        [cli, "simulate", "--resist-model=full_chem", "--grid=64"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "cd_nm" in result.stdout


def test_validation_rejects_invalid_params():
    """SimulationConfig validation rejects invalid resist params."""
    # dill_C must be > 0
    try:
        SimulationConfig(dill_C=-1)
        pytest.fail("Should have raised ValueError for dill_C <= 0")
    except ValueError:
        pass

    # peb_k must be > 0
    try:
        SimulationConfig(peb_k=0)
        pytest.fail("Should have raised ValueError for peb_k <= 0")
    except ValueError:
        pass

    # mack_n must be > 1
    try:
        SimulationConfig(mack_n=1)
        pytest.fail("Should have raised ValueError for mack_n <= 1")
    except ValueError:
        pass

    # mack_M_th must be in (0, 1)
    try:
        SimulationConfig(mack_M_th=1.5)
        pytest.fail("Should have raised ValueError for mack_M_th not in (0,1)")
    except ValueError:
        pass

    # mack_R_max must be > mack_R_min
    try:
        SimulationConfig(mack_R_max=0.05, mack_R_min=0.1)
        pytest.fail("Should have raised ValueError for mack_R_max <= mack_R_min")
    except ValueError:
        pass


def test_dill_q_no_longer_exists():
    """Regression against re-introducing a separate acid-yield factor.

    2026-09-04: the former ``dill_Q`` multiplied the Dill acid yield,
    acid = Q·(1 − e^{−C·E}), capping it at 0.5. In Mack's EUV exposure
    model (2013, Eqs. 8/10) the PAG quantum efficiency is a factor inside
    C, and the yield saturates at 1; the PROLITH-fitted dill_C already
    contains it. A separate Q double-counted φ_PAG and acted as a hidden
    calibration knob. The config must reject it outright rather than
    silently accept and ignore it.
    """
    with pytest.raises(TypeError):
        SimulationConfig(dill_Q=0.5)
    assert not hasattr(SimulationConfig(), "dill_Q")


def test_acid_yield_saturates_at_one():
    """Acid = 1 − exp(−C·E) -> 1 for E -> ∞ (Mack 2013 Eq. 10); a
    prefactor < 1 would show up as a lower plateau.
    """
    from euvsimulator.resist.exposure import dill_abc_exposure

    dose = torch.full((2, 2), 1e6, dtype=torch.float64)
    acid, inhib = dill_abc_exposure(dose, A=0.0, B=1.06, C=0.09, thickness=0.05, n_layers=2)
    assert float(acid.min()) == pytest.approx(1.0, abs=1e-9)
    assert float(inhib.max()) == pytest.approx(0.0, abs=1e-9)


def test_full_chem_nils_is_measured_at_the_printed_edge():
    """NILS of the chemistry chain refers to the edge the resist prints, not
    to the aerial_threshold model's reference-dose level (which returned 0
    whenever that level missed the image, e.g. at 4 mJ/cm²).
    """
    r = run_simulation(
        SimulationConfig(
            resist_model="full_chem", dose_mj_cm2=1.1, se_blur_nm=5.0, peb_sigma_diff=7.0, grid=128
        )
    )
    assert r.cd_nm > 0
    assert 0.5 < r.nils_value < 10.0
    cleared = run_simulation(
        SimulationConfig(resist_model="full_chem", dose_mj_cm2=20.0, se_blur_nm=5.0, grid=128)
    )
    assert cleared.cd_nm == 0.0
    assert cleared.nils_value != cleared.nils_value  # NaN: no printed edge


def test_full_chem_reports_no_nils_when_nothing_develops():
    """CD = pitch (whole row undeveloped) has no printed edge, so NILS must be NaN,
    not a value read off the wrap-around pixels (campaign 2026-09-07).
    """
    import math

    from euvsimulator.pipeline import SimulationConfig, run_simulation

    r = run_simulation(SimulationConfig(grid=32, resist_model="full_chem", dose_mj_cm2=0.05))
    assert r.cd_nm == 64.0
    assert math.isnan(r.nils_value)
    r2 = run_simulation(SimulationConfig(grid=32, resist_model="full_chem", dose_mj_cm2=1.3))
    assert 0.0 < r2.cd_nm < 64.0 and r2.nils_value > 0.0


def test_longest_run_periodic_joins_a_line_across_the_boundary():
    """An undeveloped (0) run may straddle column 0 of a periodic row (RCWA
    path: absorber at P/2 of the mask cell). It must be found whole, not
    split into two halves (2026-10-02).
    """
    from euvsimulator.pipeline import _find_runs_1d, _longest_run_periodic

    row = torch.ones(16)
    row[:3] = 0.0
    row[12:] = 0.0  # one 7-pixel line: columns 12..15 and 0..2
    assert max(_find_runs_1d(row, target=0), key=lambda r: r[1] - r[0]) == (12, 15)
    assert _longest_run_periodic(row, target=0) == (12, 2, 7)
    centred = torch.ones(16)
    centred[5:9] = 0.0
    assert _longest_run_periodic(centred, target=0) == (5, 8, 4)
    assert _longest_run_periodic(torch.ones(16), target=0) is None
    assert _longest_run_periodic(torch.zeros(16), target=0) == (0, 15, 16)


@pytest.mark.parametrize("development_model", ["column", "eikonal"])
def test_rcwa_full_chem_measures_the_line_across_the_boundary(monkeypatch, development_model):
    """RCWA path: the column-model CD must be the whole line and the NILS
    threshold must lie at the printed edges, not inside the line. Before
    2026-10-02 the line crossed column 0 and was split in two (grid 128,
    n_rcwa_orders 11, dose 1.3): column CD 25.0 instead of 42.5 nm, eikonal
    NILS 4.26 instead of 4.60. Since 2026-10 the RCWA line is
    centred like the thin-mask line.
    """
    import euvsimulator.pipeline as pipeline_module

    seen = {}
    real_nils = pipeline_module.nils

    def spy(aerial, line_center, line_width_px, dx_nm, threshold=None):
        seen["row"] = aerial[line_center].detach().clone()
        seen["thr"] = float(threshold)
        return real_nils(aerial, line_center, line_width_px, dx_nm, threshold=threshold)

    monkeypatch.setattr(pipeline_module, "nils", spy)
    G = 64
    r = run_simulation(
        SimulationConfig(
            grid=G,
            device="cpu",
            resist_model="full_chem",
            use_rcwa=True,
            n_rcwa_orders=11,
            dose_mj_cm2=1.3,
            development_model=development_model,
        )
    )
    dev = r.resist_profile[G // 2]
    edges = [k for k in range(G) if float(dev[k]) != float(dev[(k + 1) % G])]
    assert len(edges) == 2  # exactly one printed line per period
    assert float(dev[0]) == 1.0  # centred, as on the thin-mask path (A42)
    if development_model == "column":
        assert r.cd_nm == pytest.approx(int((dev < 0.5).sum()) * 64.0 / G)
    row, thr = seen["row"], seen["thr"]
    for k in edges:  # printed edge between pixel k and pixel k+1
        lo, hi = sorted((float(row[k]), float(row[(k + 1) % G])))
        assert lo <= thr <= hi
