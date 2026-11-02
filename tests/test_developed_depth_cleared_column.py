"""Regression guard: the depth of a fully cleared Eikonal column.

developed_depth_from_arrival reports N*dz for a fully cleared column since
2026-10 (52.5 nm for the default 50 nm film with 21 layers); before, it added
one more dz, (N + 1)*dz = 55 nm. The comment in _cd_via_full_chem that
explains why the stochastic edges use the arrival time still stated the old
value in the present tense.
"""

from __future__ import annotations

import inspect

import torch

import euvsimulator.pipeline as pipeline
from euvsimulator.resist.develop import developed_depth_from_arrival


def test_fully_cleared_column_reports_n_dz():
    n_layers, dz = 21, 50.0 / 20
    T = torch.zeros((n_layers, 1, 3), dtype=torch.float64)
    depth = developed_depth_from_arrival(T, t_develop=1.0, dz=dz)
    assert torch.allclose(depth, torch.full_like(depth, n_layers * dz))
    assert float(depth[0, 0]) == 52.5


def test_pipeline_comment_states_the_current_depth_of_a_cleared_column():
    src = inspect.getsource(pipeline._cd_via_full_chem)
    text = " ".join(line.strip().lstrip("#").strip() for line in src.splitlines())
    assert "fully cleared columns report (N + 1)*dz" not in text
    assert "52.5 nm" in text
