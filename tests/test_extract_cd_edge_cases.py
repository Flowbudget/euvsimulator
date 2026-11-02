"""Regression guard: resist.develop.extract_cd and _find_runs.

Three defects, none on the pipeline path:
- a uniform row was classified by comparing the BINARISED value with the
  user threshold, so a fully cleared depth row (52.5 nm everywhere) read with
  threshold 50 returned the full width instead of 0;
- _find_runs took run starts from 1 -> 0 steps whatever the target, so it
  was only correct for target=0 ([(3, 0)] for [0, 1, 1, 0] and target 1);
- the longest run was searched on the linear row only, so on one period of a
  periodic pattern a line crossing the array boundary was split and only its
  longer half measured. ``periodic=True`` now searches the periodic row; the
  default stays the linear search that the existing tests pin.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.develop import _find_runs, extract_cd


def test_uniform_row_uses_the_binarised_value_not_the_threshold():
    cleared = torch.full((64,), 52.5)  # developed depth [nm], film 50 nm
    assert extract_cd(cleared, threshold=50.0) == 0.0
    uncleared = torch.full((64,), 10.0)
    assert extract_cd(uncleared, threshold=50.0, dx=0.5) == 32.0
    assert extract_cd(torch.ones(64)) == 0.0
    assert extract_cd(torch.zeros(64)) == 64.0


@pytest.mark.parametrize(
    ("row", "target", "runs"),
    [
        ([0, 1, 1, 0], 1, [(1, 2)]),
        ([0, 1, 1, 0], 0, [(0, 0), (3, 3)]),
        ([1, 1, 0, 1, 0, 0], 1, [(0, 1), (3, 3)]),
        ([1, 1, 0, 1, 0, 0], 0, [(2, 2), (4, 5)]),
        ([1, 1, 1], 1, [(0, 2)]),
        ([1, 1, 1], 0, []),
    ],
)
def test_find_runs_for_both_targets(row, target, runs):
    assert _find_runs(torch.tensor(row, dtype=torch.float32), target=target) == runs


def test_periodic_search_measures_a_line_across_the_boundary():
    dev = torch.ones(64)
    dev[:10] = 0.0
    dev[-10:] = 0.0  # one 20 px line wrapping the boundary
    assert extract_cd(dev, dx=1.0) == 10.0  # linear search (default): longer half
    cd, left, right = extract_cd(dev, dx=1.0, periodic=True, return_edges=True)
    assert cd == 20.0
    assert (left, right) == (54.0, 10.0)  # wrapped: right edge left of the left edge
    # a line inside the row is measured identically by both searches
    inner = torch.ones(64)
    inner[20:44] = 0.0
    assert extract_cd(inner, periodic=True, return_edges=True) == extract_cd(
        inner, return_edges=True
    )
    # periodic: a row without an undeveloped pixel is 0, a row without a developed one W
    assert extract_cd(torch.ones(64), periodic=True) == 0.0
    assert extract_cd(torch.zeros(64), periodic=True, dx=2.0) == 128.0
