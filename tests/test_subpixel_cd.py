"""Sub-pixel line width from the Eikonal arrival time (2026-09-05).

The pixel-count CD was quantised to dx (1 nm at grid 64), which turned every
CD-vs-parameter curve into a staircase and left `euv calibrate` on a flat
objective. The edge is now the linear crossing of the bottom-layer arrival
time with the development time; behind the edge T grows linearly at
1/R(M_line) per unit length, so the crossing is first-order exact
(preflight_subpixel_T.py: 64-px CD within 0.35 nm of the 256-px CD).
"""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.develop import edge_positions_from_arrival


def test_exact_crossing_on_synthetic_row():
    # cleared pixels T = 10 s, then a line whose T rises 10 s per pixel
    # (R_min = 0.1 nm/s, dx = 1 nm), symmetric on the right
    dx, t_dev = 1.0, 30.0
    T = torch.tensor([10.0, 10.0, 10.0, 25.0, 35.0, 45.0, 45.0, 35.0, 25.0, 10.0, 10.0, 10.0])
    x_l, x_r = edge_positions_from_arrival(T, t_dev, dx)
    # left: between pixel 3 (25 s, cleared) and 4 (35 s): 30 s reached half-way
    assert x_l == pytest.approx(3.5)
    # right: between pixel 8 (25 s) and 7 (35 s)
    assert x_r == pytest.approx(7.5)
    assert x_r - x_l == pytest.approx(4.0)


def test_periodic_wraparound_and_degenerate_rows():
    dx, t_dev = 1.0, 30.0
    # line straddles the periodic boundary: uncleared at [10, 11, 0, 1]
    T = torch.tensor([45.0, 35.0, 25.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 25.0, 35.0, 45.0])
    x_l, x_r = edge_positions_from_arrival(T, t_dev, dx)
    assert x_r - x_l == pytest.approx(4.0)
    # no line / no space
    assert all(math.isnan(v) for v in edge_positions_from_arrival(torch.full((8,), 5.0), t_dev, dx))
    assert all(math.isnan(v) for v in edge_positions_from_arrival(torch.full((8,), 50.0), t_dev, dx))


def test_pipeline_cd_is_smooth_and_monotone_in_dose_on_a_coarse_grid():
    """Grid 64 (dx = 1 nm): the pixel count changed in 2-nm jumps; the
    sub-pixel CD must fall monotonically with dose in sub-nm steps."""
    cds = []
    for dose in (4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6):
        r = run_simulation(SimulationConfig(resist_model="full_chem", period_nm=64.0, line_width_nm=32.0,
                                            grid=64, dose_mj_cm2=dose, peb_sigma_diff=7.0, se_blur_nm=5.0))
        cds.append(r.cd_nm)
    steps = [a - b for a, b in zip(cds[:-1], cds[1:])]
    assert all(s > 0.0 for s in steps), cds
    assert max(steps) < 1.0, cds
    assert not any(float(c).is_integer() for c in cds[1:]), f"still pixel-quantised: {cds}"


def test_coarse_grid_agrees_with_fine_grid():
    """Same physics on grid 64 and 256 must give the same line width to
    within the coarse grid's remaining discretisation error."""
    def cd(grid):
        return run_simulation(SimulationConfig(resist_model="full_chem", period_nm=64.0, line_width_nm=32.0,
                                               grid=grid, dose_mj_cm2=4.5, peb_sigma_diff=7.0, se_blur_nm=5.0)).cd_nm
    assert abs(cd(64) - cd(256)) < 0.5
