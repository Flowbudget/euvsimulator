"""Eikonal development front (resist/develop.py::eikonal_arrival_time).

The dissolution front is an isotropic wave with local speed R(M); its
first-arrival time obeys |∇T| = 1/R with T = 0 on the top surface. These
tests check the solver against exact solutions and its reduction to the
column model, with no calibrated numbers.
"""

import math

import pytest
import torch

from euvsimulator.resist.develop import (
    MackModel,
    developed_depth_from_arrival,
    eikonal_arrival_time,
    eikonal_development,
    surface_advancement_level_set,
)

torch.set_default_dtype(torch.float64)
N, H, W, DX, DZ = 21, 3, 64, 0.17, 2.5
Z = (torch.arange(N, dtype=torch.float64) + 1) * DZ  # bottom face of each layer


def test_homogeneous_rate_is_exact():
    R = torch.full((N, H, W), 50.0)
    T = eikonal_arrival_time(R, DX, DZ)
    assert torch.allclose(T[:, 0, 0], Z / 50.0, rtol=1e-12, atol=0.0)


def test_two_layer_rate_is_exact():
    R = torch.full((N, H, W), 50.0)
    R[10:] = 5.0
    T = eikonal_arrival_time(R, DX, DZ)
    exact = torch.where(Z <= 10 * DZ, Z / 50.0, 10 * DZ / 50.0 + (Z - 10 * DZ) / 5.0)
    assert torch.allclose(T[:, 0, 0], exact, rtol=1e-12, atol=0.0)


def test_point_source_circular_front_first_order():
    """Only one surface column is open: the front expands as a circle
    T = sqrt(x^2 + z^2)/R. Godunov upwind is first order: mean relative error
    of order dx/r; the Manhattan metric (a wrong scheme) would give up to 41 %."""
    R = torch.full((N, H, W), 10.0)
    R[0] = 1e-12
    R[0, :, W // 2] = 10.0
    T = eikonal_arrival_time(R, DX, DZ, n_iter=30)
    xs = (torch.arange(W) - W // 2) * DX
    Zg, Xg = torch.meshgrid(Z, xs, indexing="ij")
    exact = torch.sqrt(Xg**2 + Zg**2) / 10.0
    inner = (Xg.abs() < 4.0) & (Zg > 3 * DZ)
    rel = ((T[:, 0, :] - exact).abs() / exact)[inner]
    assert float(rel.mean()) < 0.03
    assert float(rel.max()) < 0.2


def test_lateral_front_never_slower_than_column_model():
    torch.manual_seed(0)
    R = torch.rand(N, H, W) * 50 + 1.0
    T = eikonal_arrival_time(R, DX, DZ)
    T_col = torch.cumsum(DZ / R, dim=0)
    assert bool((T <= T_col + 1e-9).all())
    assert float((T_col / T).mean()) > 1.0  # lateral paths help somewhere


def test_reduces_to_column_model_without_lateral_contrast():
    """With no lateral rate variation the fastest path is straight down."""
    R = (torch.rand(N, 1, 1) * 50 + 1.0).expand(N, H, W).clone()
    T = eikonal_arrival_time(R, DX, DZ)
    T_col = torch.cumsum(DZ / R, dim=0)
    assert torch.allclose(T, T_col, rtol=1e-10, atol=0.0)


def test_depth_map_matches_column_model_without_lateral_contrast():
    mack = MackModel(R_max=68.6, R_min=0.1, n=18.2, M_th=0.39)
    M = torch.linspace(0.0, 1.0, N).view(N, 1, 1).expand(N, H, W).clone()
    d_col = surface_advancement_level_set(M, mack, dx=DX, dz=DZ, t_develop=30.0)
    d_eik = eikonal_development(M, mack, dx=DX, dz=DZ, t_develop=30.0)
    assert torch.allclose(d_col, d_eik, atol=1e-9)


def test_undercut_is_represented():
    """A slow cap layer over a fast layer: the column model needs the cap
    time everywhere, the Eikonal front enters through one opening and runs
    underneath -- columns away from the opening get developed below the cap
    while the column model has them untouched."""
    R = torch.full((N, H, W), 1e-3)
    R[0, :, W // 2] = 1e3  # one opening in the slow cap
    R[1:] = 1e3            # fast layer underneath
    T = eikonal_arrival_time(R, DX, DZ, n_iter=10)
    far = W // 2 + 20
    t_far_eik = float(T[5, 0, far])
    t_far_col = float(torch.cumsum(DZ / R, dim=0)[5, 0, far])
    assert t_far_eik < 0.05 * t_far_col


def test_input_validation():
    with pytest.raises(ValueError):
        eikonal_arrival_time(torch.ones(4, 4), 1.0, 1.0)
    with pytest.raises(ValueError):
        eikonal_arrival_time(torch.ones(2, 4, 4), 0.0, 1.0)


def test_developed_depth_interpolates_and_overshoots_like_column_model():
    T = torch.zeros(4, 1, 1)
    T[:, 0, 0] = torch.tensor([1.0, 2.0, 3.0, 4.0])
    d = developed_depth_from_arrival(T, t_develop=2.5, dz=2.0)
    assert float(d) == pytest.approx(2 * 2.0 + 0.5 * 2.0)  # two layers + half of the third
    d_full = developed_depth_from_arrival(T, t_develop=10.0, dz=2.0)
    assert float(d_full) == pytest.approx(4 * 2.0 + 2.0)  # all layers + one dz overshoot


def test_row_chunking_is_bitwise_identical():
    """Rows are independent (x, z) problems; chunking over y (memory bound
    for the 61440-row LER fields, 2026-09-05) must not change a single bit."""
    torch.manual_seed(0)
    inhib = 1.0 - torch.rand(5, 37, 16, dtype=torch.float64) * 0.5
    mack = MackModel(R_max=68.6, R_min=0.1, M_th=0.39, n=18.2)
    a, Ta = eikonal_development(inhib, mack, dx=0.25, dz=2.5, t_develop=30.0, return_arrival=True, chunk_rows=10**9)
    b, Tb = eikonal_development(inhib, mack, dx=0.25, dz=2.5, t_develop=30.0, return_arrival=True, chunk_rows=10)
    assert torch.equal(a, b) and torch.equal(Ta, Tb)
    assert Ta.shape == inhib.shape
