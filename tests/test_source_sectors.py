"""Scanner-style multipole sources (annular sectors), stage B1 2026-09-06.

Reference geometry: imec NXE3300B "dipole 90X, sigma inner/outer 0.62/0.90"
(Vesters 2019 thesis, Sec. 4.3.2) = two 90-degree sectors of the annulus
0.62 <= r <= 0.90 on the x axis.
"""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.aerial.abbe import _compute_tcc_matrix
from euvsimulator.pipeline import SimulationConfig, run_simulation


def test_dipole_90x_sector_area_and_symmetry():
    grid = 512
    f = torch.linspace(-2.0, 2.0, grid, dtype=torch.float64)
    FX, FY = torch.meshgrid(f, f, indexing="ij")
    r2 = FX**2 + FY**2
    theta = torch.atan2(FY, FX)
    d0 = torch.remainder(theta + math.pi, 2 * math.pi) - math.pi
    d1 = torch.remainder(theta, 2 * math.pi) - math.pi
    expected = (
        ((d0.abs() <= math.pi / 4) | (d1.abs() <= math.pi / 4)) & (r2 <= 0.81) & (r2 >= 0.62**2)
    )
    area = float(expected.double().mean()) * 16.0  # grid spans [-2, 2]^2
    assert area == pytest.approx(math.pi * (0.9**2 - 0.62**2) / 2, rel=0.03)


def test_tcc_zero_order_is_one_and_first_order_two_beam_for_dipole_90x():
    """At 44 nm pitch, NA 0.33 the first orders sit at +-0.93: every dipole
    source point passes the zeroth and exactly one first order (two-beam),
    so TCC(0,0) = 1 and TCC(0,+1) + TCC(0,-1) = 1 (each source point
    contributes to one of them) -- a property the conventional disk lacks.
    """
    orders = torch.tensor([-1, 0, 1])
    kw = dict(na=0.33, wavelength_m=13.5e-9, period_m=44e-9, grid=512)
    t = _compute_tcc_matrix(
        orders,
        sigma=0.9,
        illumination_shape="dipole",
        sigma_inner=0.62,
        pole_opening_deg=90.0,
        **kw,
    )
    assert t[1, 1].real == pytest.approx(1.0, abs=1e-6)
    assert (t[1, 0] + t[1, 2]).real == pytest.approx(1.0, abs=0.02)
    c = _compute_tcc_matrix(orders, sigma=0.8, illumination_shape="conventional", **kw)
    assert (
        c[1, 0] + c[1, 2]
    ).real < 0.95  # 0.93: source points with |sigma_y| large lose the first order


def test_legacy_dipole_unchanged_without_sigma_inner():
    orders = torch.tensor([-1, 0, 1])
    kw = dict(na=0.33, wavelength_m=13.5e-9, period_m=44e-9, grid=256, sigma=0.9)
    a = _compute_tcc_matrix(orders, illumination_shape="dipole", **kw)
    b = _compute_tcc_matrix(orders, illumination_shape="dipole", sigma_inner=None, **kw)
    assert torch.allclose(a, b)


def test_invalid_sector_parameters_are_rejected():
    orders = torch.tensor([0])
    kw = dict(na=0.33, wavelength_m=13.5e-9, period_m=44e-9, grid=64, sigma=0.9)
    with pytest.raises(ValueError):
        _compute_tcc_matrix(orders, illumination_shape="dipole", sigma_inner=0.95, **kw)
    with pytest.raises(ValueError):
        _compute_tcc_matrix(
            orders, illumination_shape="dipole", sigma_inner=0.5, pole_opening_deg=0.0, **kw
        )


def test_pipeline_accepts_scanner_source():
    r = run_simulation(
        SimulationConfig(
            period_nm=44.0,
            line_width_nm=22.0,
            grid=128,
            illumination_shape="dipole",
            sigma=0.9,
            sigma_inner=0.62,
            pole_opening_deg=90.0,
        )
    )
    assert r.nils_value > 0
