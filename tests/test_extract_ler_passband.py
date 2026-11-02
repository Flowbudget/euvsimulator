"""extract_ler applies a metrology passband like extract_lwr and ler_estimate do."""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.resist.stochastic import extract_ler, ler_estimate

DX = 0.25  # nm per pixel
H = 1024  # rows: 256 nm, a whole number of 64 nm and 4 nm periods
W = 256


def _two_edge_field() -> torch.Tensor:
    """Signed-distance field whose 0-crossings are the given edges exactly.

    Each edge carries a 64 nm sine (amplitude 0.5 nm, inside 10-834 nm) and a
    4 nm sine (amplitude 0.3 nm, outside the band).
    """
    y = torch.arange(H, dtype=torch.float64) * DX
    x = torch.arange(W, dtype=torch.float64) * DX

    def s(period, amp, phase=0.0):
        return amp * torch.sin(2 * math.pi * y / period + phase)

    left = 20.0 + s(64.0, 0.5) + s(4.0, 0.3)
    right = 44.0 + s(64.0, 0.5, 1.0) + s(4.0, 0.3, 2.0)
    return torch.maximum(left[:, None] - x[None, :], x[None, :] - right[:, None])


def test_extract_ler_passband_removes_out_of_band_roughness():
    f = _two_edge_field()
    full = extract_ler(f, threshold=0.0, dx=DX, intensity=f)
    band = extract_ler(f, threshold=0.0, dx=DX, intensity=f, passband_nm=(10.0, 834.0))
    assert full == pytest.approx(math.sqrt(0.5**2 / 2 + 0.3**2 / 2), rel=1e-6)
    assert band == pytest.approx(0.5 / math.sqrt(2), rel=1e-6)
    assert extract_ler(f, threshold=0.0, dx=DX, intensity=f, passband_nm=None) == full


def test_extract_ler_passband_matches_ler_estimate():
    f = _two_edge_field()
    pb = (10.0, 834.0)
    legacy = extract_ler(f, threshold=0.0, dx=DX, intensity=f, passband_nm=pb)
    large_n = ler_estimate(f, threshold=0.0, dx=DX, intensity=f, passband_nm=pb).ler_nm
    assert legacy == pytest.approx(large_n, rel=1e-6)
