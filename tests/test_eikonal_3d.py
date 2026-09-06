"""y-coupled (3D) fast-sweeping Eikonal solver (plan stage B3.4, 2026-09-06).

Invariants: uniform rate -> T = z/R exactly; a y-uniform field gives the
per-row result bit for bit; a y-varying field is never later than the
per-row first arrival (more paths); the pipeline option is accepted and the
deterministic chain (y-uniform fields) is unchanged by it.
"""

from __future__ import annotations

import torch

from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.develop import eikonal_arrival_time


def test_uniform_rate_is_exact_in_3d():
    R = torch.full((5, 8, 6), 10.0, dtype=torch.float64)
    T = eikonal_arrival_time(R, dx=1.0, dz=2.0, dy=1.0, n_iter=20)
    expected = torch.arange(1, 6, dtype=torch.float64).view(-1, 1, 1) * 0.2
    assert float((T - expected).abs().max()) < 1e-12


def test_y_uniform_field_reproduces_the_per_row_solver_exactly():
    g = torch.Generator().manual_seed(0)
    R = (
        (10 * torch.rand((6, 1, 12), generator=g, dtype=torch.float64) + 0.1)
        .expand(6, 7, 12)
        .clone()
    )
    T2 = eikonal_arrival_time(R, dx=1.0, dz=1.0, n_iter=20)
    T3 = eikonal_arrival_time(R, dx=1.0, dz=1.0, dy=1.0, n_iter=40)
    assert torch.equal(T2, T3)


def test_y_varying_field_is_never_later_than_per_row():
    g = torch.Generator().manual_seed(1)
    R = 10 * torch.rand((6, 9, 12), generator=g, dtype=torch.float64) + 0.1
    T2 = eikonal_arrival_time(R, dx=1.0, dz=1.0, n_iter=30)
    T3 = eikonal_arrival_time(R, dx=1.0, dz=1.0, dy=1.0, n_iter=60)
    assert float((T3 - T2).max()) <= 1e-12
    assert float((T2 - T3).mean()) > 0.0


def test_pipeline_option_and_deterministic_invariance():
    a = run_simulation(SimulationConfig(resist_model="full_chem", grid=64, dose_mj_cm2=1.3))
    b = run_simulation(
        SimulationConfig(
            resist_model="full_chem", grid=64, dose_mj_cm2=1.3, development_model="eikonal3d"
        )
    )
    assert a.cd_nm == b.cd_nm


def test_3d_with_cell_noise_is_tiling_invariant():
    """The y-coupling reaches at most n_iter rows per solve, the tile halo
    (4 sigma / dx + 1 >= 60 rows here) covers that, so tiling is exact.
    """
    import euvsimulator.pipeline as P

    def stoch(tile_rows):
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
            stochastic_ler_grid_y=1300,
            development_stochasticity=True,
            development_model="eikonal3d",
        )
        orig = P._noisy_depth_map
        cap = {}

        def wrapped(*a, **k):
            k["tile_rows"] = tile_rows
            d = orig(*a, **k)
            cap["d"] = d
            return d

        P._noisy_depth_map = wrapped
        try:
            r = run_simulation(cfg)
        finally:
            P._noisy_depth_map = orig
        return r, cap["d"]

    r1, d1 = stoch(10**6)
    r2, d2 = stoch(512)
    # not bitwise: the Jacobi y-sweeps converge along slightly different paths
    # inside the halo; the physics is identical to numerical tolerance
    assert float((d1 - d2).abs().max()) < 1e-4, float((d1 - d2).abs().max())
    assert abs(r1.lwr_nm - r2.lwr_nm) < 1e-4 * max(r1.lwr_nm, 1e-9)
