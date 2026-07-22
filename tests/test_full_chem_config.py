"""Test that full_chem resist parameters are configurable and affect internal chemistry."""

import pytest
import torch
from euv.pipeline import SimulationConfig, run_simulation


def test_full_chem_params_passed_through():
    """Verify resist params are accepted and stored in config."""
    cfg = SimulationConfig(
        resist_model="full_chem",
        dill_C=0.1,
        dill_Q=0.5,
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
    assert cfg.dill_Q == 0.5
    assert cfg.peb_k == 0.25
    assert cfg.peb_t_bake == 90.0
    assert cfg.peb_sigma_diff == 3.0
    assert cfg.mack_R_max == 200.0
    assert cfg.mack_R_min == 0.05
    assert cfg.mack_n == 8.0
    assert cfg.mack_M_th == 0.3


def test_full_chem_chemistry_affected_by_params():
    """Resist params affect internal chemistry (acid, inhib, dev_chem)."""
    from euv.aerial.abbe import aerial_from_orders
    from euv.resist.exposure import dose_to_acid
    from euv.resist.peb import reaction_diffusion_analytical
    from euv.resist.develop import threshold_development
    import math

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
    ae = aerial_from_orders(orders_complex, order_indices, period_m, na, wl_m, sigma, grid=G, se_blur_nm=0.0)
    ae_dose = ae * 20.0
    dx_nm = 64.0 / G

    # Test dill_C affects acid
    acid_low = dose_to_acid(ae_dose, C=0.01, Q=1.0, sigma_blur=0.0, dx=dx_nm, apply_blur=False)
    acid_high = dose_to_acid(ae_dose, C=0.2, Q=1.0, sigma_blur=0.0, dx=dx_nm, apply_blur=False)
    assert acid_high.mean() > acid_low.mean(), "Higher dill_C should produce more acid"

    # Test peb_k affects inhibitor
    inhib_low = torch.ones_like(acid_high)
    inhib_high = torch.ones_like(acid_high)
    _, inhib_low = reaction_diffusion_analytical(acid_high, inhib_low, k=0.1, t_bake=60.0, sigma_diff=5.0, dx=dx_nm)
    _, inhib_high = reaction_diffusion_analytical(acid_high, inhib_high, k=0.5, t_bake=60.0, sigma_diff=5.0, dx=dx_nm)
    assert inhib_high.mean() < inhib_low.mean(), "Higher peb_k should deprotect more (lower inhibitor)"

    # Test mack_M_th affects dev_chem
    dev_low = threshold_development(inhib_high, threshold=0.3)
    dev_high = threshold_development(inhib_high, threshold=0.7)
    assert dev_high.mean() > dev_low.mean(), "Higher threshold should develop more"


def test_both_paths_identical_cd():
    """Both aerial_threshold and full_chem give identical CDs (by design)."""
    cfg1 = SimulationConfig(resist_model="aerial_threshold", grid=128)
    cfg2 = SimulationConfig(resist_model="full_chem", grid=128)

    r1 = run_simulation(cfg1)
    r2 = run_simulation(cfg2)

    # CDs should be identical (within numerical precision)
    assert abs(r1.cd_nm - r2.cd_nm) < 0.01, f"CDs differ: {r1.cd_nm} vs {r2.cd_nm}"
    assert abs(r1.nils_value - r2.nils_value) < 0.01, f"NILS differ: {r1.nils_value} vs {r2.nils_value}"


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

    from euv.pipeline import SimulationConfig
    cfg = SimulationConfig(**yaml.safe_load(config_path.read_text()))
    assert cfg.dill_C == 0.1
    assert cfg.peb_k == 0.25
    assert cfg.peb_t_bake == 90.0
    assert cfg.mack_R_max == 150.0


def test_cli_resist_model_option():
    """Test that --resist-model CLI option works."""
    import subprocess
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        ["euv", "simulate", "--resist-model=full_chem", "--grid=64"],
        capture_output=True, text=True, cwd=project_root
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


if __name__ == "__main__":
    test_full_chem_params_passed_through()
    print("test_full_chem_params_passed_through PASSED")
    test_full_chem_chemistry_affected_by_params()
    print("test_full_chem_chemistry_affected_by_params PASSED")
    test_both_paths_identical_cd()
    print("test_both_paths_identical_cd PASSED")
    test_validation_rejects_invalid_params()
    print("test_validation_rejects_invalid_params PASSED")
    print("ALL TESTS PASSED")