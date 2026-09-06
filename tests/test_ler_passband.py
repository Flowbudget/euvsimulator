"""Metrology passband for LER/LWR (plan stage B3.5, log Fortsetzung 36)."""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig
from euvsimulator.presets import met2d_config, nxe1716_config
from euvsimulator.resist.stochastic import bandlimit_along_rows


def _sine(period_nm, n=4096, dx=0.25, amp=1.0):
    y = torch.arange(n, dtype=torch.float64) * dx
    return amp * torch.sin(2 * math.pi * y / period_nm)


def test_band_keeps_inside_and_removes_outside_periods():
    dx = 0.25
    inside = _sine(64.0, dx=dx)  # 64 nm period: inside (10, 834)
    outside = _sine(4.0, dx=dx)  # 4 nm period: cell-scale, outside
    x = inside + outside
    f = bandlimit_along_rows(x, dx, (10.0, 834.0))
    assert float(f.std()) == pytest.approx(float(inside.std()), rel=0.02)
    assert float((f - inside).abs().max()) < 0.05
    assert bandlimit_along_rows(outside, dx, (10.0, 834.0)).abs().max() < 1e-6


def test_none_is_identity_and_mean_is_removed():
    x = _sine(50.0) + 3.0
    assert torch.equal(bandlimit_along_rows(x, 0.25, None), x)
    f = bandlimit_along_rows(x, 0.25, (10.0, 834.0))
    assert abs(float(f.mean())) < 1e-9


def test_config_validation_and_anchor_bands():
    with pytest.raises(ValueError):
        SimulationConfig(ler_passband_nm=(100.0, 10.0))
    assert SimulationConfig().ler_passband_nm is None
    assert met2d_config().ler_passband_nm == (10.0, 834.0)
    assert nxe1716_config().ler_passband_nm == (10.8, 5500.0)
