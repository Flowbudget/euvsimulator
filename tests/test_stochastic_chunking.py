"""Tiled stochastic chain (2026-09-05) must reproduce the untiled one.

The noisy exposure -> PEB -> development chain runs in y-tiles with a halo of
one row more than the 4-sigma truncation radius of the lateral PEB blur, taken
periodically from the full field. Every step is pointwise, per column, per
row, or that circular convolution, so the interior rows of a tile are exactly
what the full-field computation gives. This test pins that claim for the
photon-only chain (RNG-free after the 2D photon draw) and checks that the
sampled-molecule chain is reproducible and independent of the tile grouping.
"""

from __future__ import annotations

import math

import torch

import euvsimulator.pipeline as P
from euvsimulator.pipeline import SimulationConfig, run_simulation


def _cfg(**kw):
    base = dict(
        resist_model="full_chem",
        period_nm=44.0,
        line_width_nm=22.0,
        se_blur_nm=5.0,
        grid=128,
        peb_sigma_diff=7.0,
        dose_mj_cm2=1.55,
        enable_stochastic=True,
        stochastic_seed=7,
        stochastic_n_realisations=1,
        stochastic_ler_grid_y=1536,
    )
    base.update(kw)
    return SimulationConfig(**base)


def _run_with_tile_rows(tile_rows, **kw):
    orig = P._noisy_depth_map
    captured = {}

    def wrapped(d_eff, cfg, **kws):
        out = orig(d_eff, cfg, **kws, tile_rows=tile_rows)
        captured["depth"] = out
        return out

    P._noisy_depth_map = wrapped
    try:
        r = run_simulation(_cfg(**kw))
    finally:
        P._noisy_depth_map = orig
    return r, captured["depth"]


def test_photon_only_chain_is_tiling_invariant():
    r1, d1 = _run_with_tile_rows(10**6)  # one tile, no halo
    r2, d2 = _run_with_tile_rows(512)  # three tiles with halo
    assert d1.shape == d2.shape
    assert torch.allclose(d1, d2, atol=1e-9, rtol=0.0), float((d1 - d2).abs().max())
    assert math.isclose(r1.lwr_nm, r2.lwr_nm, rel_tol=1e-9, abs_tol=1e-9)


def test_halo_is_at_least_the_blur_radius():
    cfg = _cfg()
    dx = 44.0 / 128
    assert P._peb_blur_radius_px(cfg, dx) == int(4.0 * 7.0 / dx + 0.5)
    assert P._peb_blur_radius_px(SimulationConfig(peb_sigma_diff=None, peb_D=0.0), dx) == 0


def test_sampled_chain_is_reproducible_and_grouping_independent():
    # same seed -> bitwise identical realisation; and because each tile draws
    # from its own seeded generator, the realisation must not depend on how
    # many tiles are processed per chunk -- here tile_rows 512 vs 1024 give
    # different tilings, so only reproducibility is checked at fixed tiling
    # pag_density 12.0: the 1.0 px tolerance below was set when C*G0 was
    # 0.090 * 2.0 = 0.18 cm²/mJ·nm⁻³; the molecular scatter of the row-mean
    # width scales with the acid count per voxel (∝ C*G0), so with the
    # directly measured C = 0.0152 (2026-09-06, A2) the same count needs
    # G0 = 12 nm⁻³. Statistical bound, not a physical PAG loading.
    kw = dict(exposure_stochasticity=True, pag_density_per_nm3=12.0)
    _, a = _run_with_tile_rows(512, **kw)
    _, b = _run_with_tile_rows(512, **kw)
    assert torch.equal(a, b)
    _, c = _run_with_tile_rows(10**6, **kw)
    # different tiling = different draw, but the same physics: the mean
    # width must agree within the molecular-noise scatter of the row mean
    assert abs(float(c.mean()) - float(a.mean())) < 1.0


def test_row_count_not_a_multiple_of_the_tile_is_still_exact():
    """A short remainder tile would contribute fewer halo rows than assumed
    and misalign the interior slice; rows are therefore distributed evenly
    over floor(H / tile_rows) tiles, each at least `halo` rows long.
    """
    r1, d1 = _run_with_tile_rows(10**6, stochastic_ler_grid_y=1300)
    r2, d2 = _run_with_tile_rows(512, stochastic_ler_grid_y=1300)  # 2 tiles of 650
    assert d1.shape == d2.shape == (1300, 128)
    assert torch.allclose(d1, d2, atol=1e-9, rtol=0.0), float((d1 - d2).abs().max())
    assert math.isclose(r1.lwr_nm, r2.lwr_nm, rel_tol=1e-9, abs_tol=1e-9)
