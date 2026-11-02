"""The stochastic edge extractor uses the same edge definition as cd_nm.

For the Eikonal development models the deterministic CD is the crossing of
the bottom-layer arrival time T with develop_time_s
(edge_positions_from_arrival). Until 2026-10-02 the stochastic realisations
interpolated the developed-depth map instead, whose fully cleared columns
then reported (N + 1)*dz = 55 nm for the 50 nm film (N*dz = 52.5 nm since
2026-10), so the edge depended only on
the first uncleared pixel: -0.78 px against cd_nm at 1.1 mJ/cm2 and grid 128,
+0.27 px at grid 64. With the photon sampler replaced by its expectation
value the stochastic chain is the deterministic chain, so its mean line
width must equal cd_nm.
"""

import math

import pytest

import euvsimulator.pipeline as P
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.exposure import gaussian_se_blur


@pytest.fixture
def photon_noise_off(monkeypatch):
    """Replace the photon sampler by its expectation value."""

    def mean_field(dose, se_blur_nm, dx_nm=1.0, **kw):
        return gaussian_se_blur(dose, sigma=se_blur_nm, dx=dx_nm) if se_blur_nm > 0 else dose

    monkeypatch.setattr(P, "photon_deposition_shot_noise", mean_field)


@pytest.mark.parametrize("grid", [64, 128])
def test_mean_field_stochastic_cd_equals_deterministic_cd(photon_noise_off, grid):
    common = dict(resist_model="full_chem", grid=grid, dose_mj_cm2=1.1)
    det = run_simulation(SimulationConfig(**common))
    sto = run_simulation(
        SimulationConfig(
            **common,
            enable_stochastic=True,
            stochastic_n_realisations=1,
            stochastic_seed=1,
            stochastic_ler_grid_y=256,
        )
    )
    dx = 64.0 / grid
    s_cd = sto.ler_metadata["stochastic_cd_nm"]
    assert math.isfinite(s_cd)
    assert abs(s_cd - det.cd_nm) < 0.02 * dx, (s_cd, det.cd_nm)


def test_noisy_depth_map_reports_arrival_only_for_eikonal(photon_noise_off):
    """arrival_out receives the (H, W) bottom-layer arrival field for the
    Eikonal model and None for the column model; the return value stays the
    depth map in both cases.
    """
    seen = {}
    orig = P._noisy_depth_map

    def wrapped(d_eff, cfg, **kw):
        out = orig(d_eff, cfg, **kw)
        seen[cfg.development_model] = (out, kw["arrival_out"][0])
        return out

    P._noisy_depth_map = wrapped
    try:
        for model in ("eikonal", "column"):
            run_simulation(
                SimulationConfig(
                    resist_model="full_chem",
                    grid=64,
                    dose_mj_cm2=1.1,
                    development_model=model,
                    enable_stochastic=True,
                    stochastic_n_realisations=1,
                    stochastic_seed=1,
                    stochastic_ler_grid_y=128,
                )
            )
    finally:
        P._noisy_depth_map = orig
    depth_e, arr_e = seen["eikonal"]
    depth_c, arr_c = seen["column"]
    assert arr_e is not None and arr_e.shape == depth_e.shape == (128, 64)
    assert arr_c is None and depth_c.shape == (128, 64)
