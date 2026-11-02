"""The sub-pixel full_chem CD uses the arrival time at the film bottom
(plan pipeline-1, step 6).

eikonal_arrival_time returns T[k] at z = (k + 1) * dz; with N layer nodes
and dz = thickness / (N - 1) the film bottom is T[-2]. Until 2026-10 the
pipeline used T[-1] (one dz below the film): at dose 1.0, grid 256 the CD
read 42.616 / 42.293 / 42.130 nm for 11 / 21 / 41 layers, against
41.675 / 41.925 / 41.976 nm at the film bottom and a cleared-pixel count of
41.5 / 42.0 nm (11 / 21 layers).
"""

import pytest
import torch

import euvsimulator.pipeline as P
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.develop import MackModel, eikonal_development


def test_develop_depth_returns_the_film_bottom_arrival():
    cfg = SimulationConfig(resist_model="full_chem")
    inhib = torch.full((5, 2, 16), 0.95, dtype=torch.float64)
    inhib[:, :, :8] = 0.05
    mack = MackModel(R_max=cfg.mack_R_max, R_min=cfg.mack_R_min, n=cfg.mack_n, M_th=cfg.mack_M_th)
    _, arrival = P._develop_depth(inhib, mack, 1.0, 2.5, cfg, return_arrival=True)
    _, T = eikonal_development(
        inhib, mack, dx=1.0, dz=2.5, t_develop=cfg.develop_time_s, return_arrival=True
    )
    assert torch.equal(arrival, T[-2])
    assert not torch.equal(arrival, T[-1])


@pytest.mark.parametrize("layers", [11, 21])
def test_subpixel_cd_agrees_with_the_cleared_pixel_count(layers):
    cfg = SimulationConfig(
        resist_model="full_chem", dose_mj_cm2=1.0, grid=256, device="cpu", n_develop_layers=layers
    )
    r = run_simulation(cfg)
    dx = cfg.period_nm / cfg.grid
    row = r.resist_profile[cfg.grid // 2]
    pixel_cd = float((row == 0).sum()) * dx
    assert abs(r.cd_nm - pixel_cd) <= dx, (r.cd_nm, pixel_cd)


def test_subpixel_cd_converges_with_the_layer_count():
    cds = [
        run_simulation(
            SimulationConfig(
                resist_model="full_chem",
                dose_mj_cm2=1.0,
                grid=256,
                device="cpu",
                n_develop_layers=n,
            )
        ).cd_nm
        for n in (21, 41)
    ]
    assert abs(cds[0] - cds[1]) < 0.1, cds
