"""Regression guard: the tiled sampled-molecule chain must be one consistent realisation.

_noisy_depth_map processes the exposure_stochasticity chain in y-tiles with
a halo, and samples the PAG/quencher molecules of a whole tile every time the
tile is needed: as its own interior and as the halo of both neighbours. The
halo rows are only correct if every one of those calls returns the same
molecules. Each tile used to draw from one generator that was seeded once,
so every call advanced it and returned a new draw; the rows within one PEB
halo of every seam were then blurred against molecules that the neighbouring
tile's output never saw.
"""

from __future__ import annotations

import pytest
import torch

import euvsimulator.pipeline as P
from euvsimulator.pipeline import SimulationConfig, run_simulation

TILE_ROWS = 512
ROWS = 1536  # three tiles of 512 rows


def _cfg():
    return SimulationConfig(
        resist_model="full_chem",
        period_nm=44.0,
        line_width_nm=22.0,
        se_blur_nm=5.0,
        grid=64,
        peb_sigma_diff=7.0,
        dose_mj_cm2=1.55,
        enable_stochastic=True,
        stochastic_seed=7,
        stochastic_n_realisations=1,
        stochastic_ler_grid_y=ROWS,
        exposure_stochasticity=True,
        pag_density_per_nm3=12.0,
        device="cpu",
    )


def _run(monkeypatch, tile_rows, sampler):
    """Run the chain with a given tiling and sampler; return depth and the
    acid/quencher stacks that reached the sampled-chain PEB step.
    """
    captured = {}
    peb_in = []
    orig_ndm = P._noisy_depth_map
    orig_peb = P._peb_step

    def ndm(d_eff, cfg, **kw):
        out = orig_ndm(d_eff, cfg, **kw, tile_rows=tile_rows)
        captured["depth"] = out
        return out

    def peb(acid_3d, quencher_arg, *args, **kwargs):
        if isinstance(quencher_arg, torch.Tensor):  # sampled chain only
            peb_in.append((acid_3d.clone(), quencher_arg.clone()))
        return orig_peb(acid_3d, quencher_arg, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(P, "_noisy_depth_map", ndm)
        m.setattr(P, "_peb_step", peb)
        m.setattr(P, "sample_pag_quencher_acid", sampler)
        run_simulation(_cfg())
    return captured["depth"], peb_in


@pytest.fixture(scope="module")
def tiled():
    """One tiled run, recording every sampler call."""
    calls = []
    orig = P.sample_pag_quencher_acid

    def sampler(dose_z, **kw):
        acid, quencher = orig(dose_z, **kw)
        calls.append((dose_z.clone(), acid.clone(), quencher.clone()))
        return acid, quencher

    mp = pytest.MonkeyPatch()
    try:
        depth, peb_in = _run(mp, TILE_ROWS, sampler)
    finally:
        mp.undo()
    return depth, peb_in, calls


def test_every_call_for_a_tile_returns_the_same_molecules(tiled):
    _, _, calls = tiled
    groups = []  # [dose slice, [(acid, quencher), ...]] per tile
    for dose_z, acid, quencher in calls:
        for g in groups:
            if g[0].shape == dose_z.shape and torch.equal(g[0], dose_z):
                g[1].append((acid, quencher))
                break
        else:
            groups.append((dose_z, [(acid, quencher)]))
    assert len(groups) == ROWS // TILE_ROWS
    for _, draws in groups:
        assert len(draws) == 3  # interior, previous tile's halo, next tile's halo
        for acid, quencher in draws[1:]:
            assert torch.equal(acid, draws[0][0])
            assert torch.equal(quencher, draws[0][1])


def test_halo_rows_are_the_neighbours_interior_rows(tiled):
    _, peb_in, _ = tiled
    n_tiles = ROWS // TILE_ROWS
    assert len(peb_in) == n_tiles
    halo = (peb_in[0][0].shape[1] - TILE_ROWS) // 2
    assert halo > 0
    for t in range(n_tiles):
        nxt = (t + 1) % n_tiles
        for k in (0, 1):  # acid, quencher
            cur, following = peb_in[t][k], peb_in[nxt][k]
            # next halo of tile t == first interior rows of tile t+1
            assert torch.equal(cur[:, halo + TILE_ROWS :], following[:, halo : 2 * halo])
            # previous halo of tile t+1 == last interior rows of tile t
            assert torch.equal(following[:, :halo], cur[:, TILE_ROWS : TILE_ROWS + halo])


def test_tiled_chain_equals_one_field_of_the_same_molecules(tiled, monkeypatch):
    """The tiled depth map must equal the untiled chain run on the very
    molecules the tiles hold (same exactness as the photon-only chain in
    tests/test_stochastic_chunking.py).
    """
    depth_tiled, peb_in, _ = tiled
    halo = (peb_in[0][0].shape[1] - TILE_ROWS) // 2
    acid = torch.cat([a[:, halo : halo + TILE_ROWS] for a, _ in peb_in], dim=1)
    quencher = torch.cat([q[:, halo : halo + TILE_ROWS] for _, q in peb_in], dim=1)

    def inject(dose_z, **kw):
        assert dose_z.shape[1] == ROWS
        return acid.clone(), quencher.clone()

    depth_single, _ = _run(monkeypatch, 10**6, inject)
    assert depth_single.shape == depth_tiled.shape == (ROWS, 64)
    err = (depth_single - depth_tiled).abs().max().item()
    assert err < 1e-9, err
