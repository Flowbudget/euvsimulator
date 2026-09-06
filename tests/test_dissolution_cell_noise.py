"""Development noise from the counting statistics of blocked polymer units
per dissolution cell (resist/develop.dissolution_cell_noise; plan stage B3,
log Fortsetzung 32/33). Sources: Mack 2010 JM3 9, 041202 (KPZ roughening of
a dissolution front with cell-wise rate noise) and Mack 2010 "LER and the
ultimate limits of lithography", Eq. 36 (Poisson term of the blocked sites).
"""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.pipeline import (
    DEFAULT_BLOCKED_SITE_DENSITY_PER_NM3,
    SimulationConfig,
    run_simulation,
)
from euvsimulator.resist.develop import MackModel, dissolution_cell_noise

MACK = MackModel(R_max=100.0, R_min=0.01, n=5.0, M_th=0.4)


def _uniform(M, N=4, H=64, W=64):
    return torch.full((N, H, W), M, dtype=torch.float64)


def test_default_density_follows_the_composition():
    assert DEFAULT_BLOCKED_SITE_DENSITY_PER_NM3 == pytest.approx(0.35 * 4.66, abs=0.02)
    assert SimulationConfig().blocked_site_density_per_nm3 == DEFAULT_BLOCKED_SITE_DENSITY_PER_NM3


def test_cell_protection_scatter_matches_the_poisson_count():
    """M_cell = M + xi*sqrt(M/(n0 a^3)): the implied rate multiplier equals
    R(M_cell)/R(M); check by inverting on a uniform field with a linear law.
    """
    lin = MackModel(R_max=1.0, R_min=0.0, n=1.0001, M_th=0.0)  # ~ R = 1 - M
    M, n0, a = 0.5, 1.63, 4.3
    field = _uniform(M, N=2, H=256, W=256)
    mult = dissolution_cell_noise(
        field,
        lin,
        blocked_density_per_nm3=n0,
        cell_nm=a,
        dx=a,
        dz=a,
        row_index=torch.arange(256),
        seed=7,
    )
    m_cell = 1.0 - mult * (1.0 - M)  # invert R = 1 - M
    sd = float(m_cell.std())
    assert sd == pytest.approx(math.sqrt(M / (n0 * a**3)), rel=0.08)
    assert float(m_cell.mean()) == pytest.approx(M, abs=0.005)


def test_noise_is_quenched_per_cell_and_reproducible():
    field = _uniform(0.5, N=4, H=40, W=40)
    kw = dict(blocked_density_per_nm3=1.63, cell_nm=4.0, dx=1.0, dz=1.0, row_index=torch.arange(40))
    a = dissolution_cell_noise(field, MACK, seed=3, **kw)
    b = dissolution_cell_noise(field, MACK, seed=3, **kw)
    c = dissolution_cell_noise(field, MACK, seed=4, **kw)
    assert torch.equal(a, b) and not torch.equal(a, c)
    # constant inside a 4x4x4 cell, different between cells
    assert torch.allclose(a[:4, :4, :4], a[0, 0, 0])
    assert not torch.allclose(a[:4, :4, :4], a[:4, 4:8, :4])


def test_field_is_anchored_to_absolute_rows():
    """The rows [16, 48) computed alone must equal the same rows of the full field."""
    field = _uniform(0.5, N=4, H=64, W=32)
    kw = dict(blocked_density_per_nm3=1.63, cell_nm=4.0, dx=1.0, dz=1.0, seed=11)
    full = dissolution_cell_noise(field, MACK, row_index=torch.arange(64), **kw)
    part = dissolution_cell_noise(field[:, 16:48], MACK, row_index=torch.arange(16, 48), **kw)
    assert torch.equal(full[:, 16:48], part)


def _stoch(rows, tile_rows, **kw):
    import euvsimulator.pipeline as P

    cfg = SimulationConfig(
        resist_model="full_chem",
        period_nm=44.0,
        line_width_nm=22.0,
        grid=128,
        se_blur_nm=5.0,
        dose_mj_cm2=1.55,
        enable_stochastic=True,
        stochastic_n_realisations=1,
        stochastic_seed=5,
        stochastic_ler_grid_y=rows,
        development_stochasticity=True,
        **kw,
    )
    orig = P._noisy_depth_map
    captured = {}

    def wrapped(*a, **k):
        k["tile_rows"] = tile_rows
        d = orig(*a, **k)
        captured["depth"] = d
        return d

    P._noisy_depth_map = wrapped
    try:
        r = run_simulation(cfg)
    finally:
        P._noisy_depth_map = orig
    return r, captured["depth"]


def test_development_noise_is_tiling_invariant_and_changes_the_result():
    r1, d1 = _stoch(1300, 10**6)
    r2, d2 = _stoch(1300, 512)
    assert torch.allclose(d1, d2, atol=1e-9, rtol=0.0), float((d1 - d2).abs().max())
    assert math.isclose(r1.lwr_nm, r2.lwr_nm, rel_tol=1e-9, abs_tol=1e-9)
    # and the option does something: the depth map differs from the noise-free chain
    cfg_off = SimulationConfig(
        resist_model="full_chem",
        period_nm=44.0,
        line_width_nm=22.0,
        grid=128,
        se_blur_nm=5.0,
        dose_mj_cm2=1.55,
        enable_stochastic=True,
        stochastic_n_realisations=1,
        stochastic_seed=5,
        stochastic_ler_grid_y=1300,
    )
    r0 = run_simulation(cfg_off)
    assert r0.lwr_nm != r1.lwr_nm


def test_deterministic_chain_ignores_the_option():
    a = run_simulation(SimulationConfig(resist_model="full_chem", grid=128, dose_mj_cm2=1.3))
    b = run_simulation(
        SimulationConfig(
            resist_model="full_chem", grid=128, dose_mj_cm2=1.3, development_stochasticity=True
        )
    )
    assert a.cd_nm == b.cd_nm


def test_invalid_parameters_are_rejected():
    with pytest.raises(ValueError):
        SimulationConfig(blocked_site_density_per_nm3=0.0)
    with pytest.raises(ValueError):
        SimulationConfig(dissolution_cell_nm=-1.0)
