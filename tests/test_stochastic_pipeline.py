"""Integration tests for stochastic pipeline (shot noise → LER/LWR)."""

import pytest
import torch

from euv.pipeline import SimulationConfig, run_simulation


def test_stochastic_disabled_by_default():
    """Default config has no LER/LWR."""
    cfg = SimulationConfig(grid=64)
    result = run_simulation(cfg)
    assert result.ler_nm == 0.0
    assert result.lwr_nm == 0.0


def test_stochastic_requires_full_chem():
    """enable_stochastic=True requires resist_model='full_chem'."""
    with pytest.raises(ValueError, match="full_chem"):
        SimulationConfig(enable_stochastic=True, resist_model="aerial_threshold")


def test_stochastic_produces_ler_lwr():
    """Stochastic pipeline returns positive LER/LWR."""
    cfg = SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=3,
        stochastic_seed=42,
        grid=128,
    )
    result = run_simulation(cfg)
    # LER/LWR should be positive (or NaN if no features)
    assert result.ler_nm >= 0 or torch.isnan(torch.tensor(result.ler_nm))
    assert result.lwr_nm >= 0 or torch.isnan(torch.tensor(result.lwr_nm))
    # With our test pattern, should get positive values
    assert result.ler_nm > 0
    assert result.lwr_nm > 0


def test_stochastic_reproducible_with_seed():
    """Same seed gives identical LER/LWR."""
    cfg1 = SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=5,
        stochastic_seed=123,
        grid=128,
    )
    cfg2 = SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=5,
        stochastic_seed=123,
        grid=128,
    )
    r1 = run_simulation(cfg1)
    r2 = run_simulation(cfg2)
    assert abs(r1.ler_nm - r2.ler_nm) < 1e-6
    assert abs(r1.lwr_nm - r2.lwr_nm) < 1e-6


def test_stochastic_different_seeds_different_results():
    """Different seeds give different LER/LWR (statistically)."""
    cfg1 = SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=10,
        stochastic_seed=1,
        grid=128,
    )
    cfg2 = SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_n_realisations=10,
        stochastic_seed=2,
        grid=128,
    )
    r1 = run_simulation(cfg1)
    r2 = run_simulation(cfg2)
    # Should differ (not exactly, but very unlikely to be identical)
    assert abs(r1.ler_nm - r2.ler_nm) > 1e-4 or abs(r1.lwr_nm - r2.lwr_nm) > 1e-4


if __name__ == "__main__":
    test_stochastic_disabled_by_default()
    print("test_stochastic_disabled_by_default PASSED")
    test_stochastic_requires_full_chem()
    print("test_stochastic_requires_full_chem PASSED")
    test_stochastic_produces_ler_lwr()
    print("test_stochastic_produces_ler_lwr PASSED")
    test_stochastic_reproducible_with_seed()
    print("test_stochastic_reproducible_with_seed PASSED")
    test_stochastic_different_seeds_different_results()
    print("test_stochastic_different_seeds_different_results PASSED")
    print("ALL TESTS PASSED")
