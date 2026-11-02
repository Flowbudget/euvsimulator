"""Regression guard: the RCWA mask line must sit where the thin-mask line sits.

build_permittivity_profile puts the absorber at P/2 of the mask cell. Until
2026-10 the pipeline imaged the RCWA orders without a shift, so the dark line
came out at x = +-P/2 -- across column 0 of the image grid and across its
duplicated endpoint sample -- while the thin-mask line sits at x = 0. The
non-periodic edge extraction then returned columns 0 and W-1 on every
RCWA + full_chem + enable_stochastic run (LER = LWR = 0, stochastic CD about
the pitch), and RCWA CD/NILS carried a 0.6-1.1 px placement bias.
"""

import math

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.stochastic import extract_edges, extract_ler, extract_lwr

G = 64


def _rcwa(**kw):
    base = dict(grid=G, device="cpu", use_rcwa=True, n_rcwa_orders=11)
    base.update(kw)
    return run_simulation(SimulationConfig(**base))


@pytest.mark.parametrize("estimator", ["legacy", "large_n"])
def test_rcwa_full_chem_stochastic_edges_are_measured(estimator):
    """LER/LWR of an RCWA stochastic run must be finite and positive, and the
    stochastic line width must be the line, not the pitch. Before the fix
    (grid 64, seed 7): LER = LWR = 0.0000 and stochastic_cd_nm = 63.0 nm.
    """
    r = _rcwa(
        resist_model="full_chem",
        dose_mj_cm2=1.3,
        enable_stochastic=True,
        stochastic_seed=7,
        stochastic_ler_estimator=estimator,
        stochastic_ler_grid_y=256,
    )
    assert 0.0 < r.cd_nm < 64.0
    assert math.isfinite(r.ler_nm) and r.ler_nm > 0.1
    assert math.isfinite(r.lwr_nm) and r.lwr_nm > 0.1
    if estimator == "large_n":
        assert r.ler_metadata["stochastic_cd_nm"] == pytest.approx(r.cd_nm, abs=2.0)


@pytest.mark.parametrize("resist_model", ["aerial_threshold", "full_chem"])
def test_rcwa_line_is_centred_like_the_thin_mask_line(resist_model):
    """The RCWA dark line lies inside the array, with the duplicated endpoint
    sample (x = +-P/2) in the space, as on the thin-mask path.
    """
    kw = dict(dose_mj_cm2=1.3) if resist_model == "full_chem" else {}
    for use_rcwa in (False, True):
        r = run_simulation(
            SimulationConfig(
                grid=G,
                device="cpu",
                use_rcwa=use_rcwa,
                n_rcwa_orders=11,
                resist_model=resist_model,
                **kw,
            )
        )
        row = r.aerial_image[G // 2]
        lo, hi = float(row.min()), float(row.max())
        assert G // 4 <= int(row.argmin()) < 3 * G // 4, f"use_rcwa={use_rcwa}"
        assert float(row[0]) > 0.5 * (lo + hi), f"use_rcwa={use_rcwa}"
        if resist_model == "full_chem":
            dev = r.resist_profile[G // 2]
            assert float(dev[0]) == 1.0 and float(dev[G // 2]) == 0.0


def _line_field(H=64, W=48, seed=3):
    """Developed field (1 = developed) with one rough line per row, centred."""
    g = torch.Generator().manual_seed(seed)
    cols = torch.arange(W, dtype=torch.float64)
    left = 16.0 + 1.5 * torch.randn(H, 1, generator=g, dtype=torch.float64)
    right = 32.0 + 1.5 * torch.randn(H, 1, generator=g, dtype=torch.float64)
    # continuous field: > 0.5 in the space, < 0.5 in the line (linear ramps)
    field = 0.5 + 0.25 * torch.maximum(left - cols, cols - right)
    return field.clamp(0.0, 1.0)


def test_extract_edges_is_periodic():
    """A line that straddles column 0 gives the same widths and the same
    LER/LWR as the same line centred in the array. Before the fix the first
    and last undeveloped pixels were columns 0 and W-1 for every row.
    """
    field = _line_field()
    W = field.shape[1]
    shift = W // 2
    wrapped = torch.roll(field, shift, dims=1)
    for intensity in (False, True):
        l0, r0 = extract_edges(field, 0.5, 1.0, field if intensity else None)
        l1, r1 = extract_edges(wrapped, 0.5, 1.0, wrapped if intensity else None)
        torch.testing.assert_close(r1 - l1, r0 - l0, rtol=0.0, atol=1e-9)
        # positions are unwrapped: same line, translated by the roll
        torch.testing.assert_close(torch.remainder(l1 - shift, W), l0, rtol=0.0, atol=1e-9)
        a = extract_ler(field, 0.5, 1.0, intensity=field if intensity else None)
        b = extract_ler(wrapped, 0.5, 1.0, intensity=wrapped if intensity else None)
        assert b == pytest.approx(a, abs=1e-9) and a > 0.5
        a = extract_lwr(field, 0.5, 1.0, intensity=field if intensity else None)
        b = extract_lwr(wrapped, 0.5, 1.0, intensity=wrapped if intensity else None)
        assert b == pytest.approx(a, abs=1e-9) and a > 0.5


def test_extract_edges_unchanged_when_column_zero_is_space():
    """No roll when the rows already start in the space (legacy layout)."""
    field = _line_field()
    l0, r0 = extract_edges(field, 0.5, 2.0, field)
    assert float(l0.min()) > 2.0 * 10 and float(r0.max()) < 2.0 * 40
