"""Tests for the illumination source module."""

import pytest
import torch

from euv.aerial.source import (
    annular,
    conventional,
    custom,
    dipole_x,
    dipole_y,
    quasar,
)


class TestConventionalSource:
    def test_normalised(self):
        src = conventional(256, sigma=0.8)
        assert src.shape == (256, 256)
        assert src.dtype == torch.float64
        assert abs(src.sum().item() - 1.0) < 1e-10

    def test_sigma_one(self):
        """σ=1 → all pixels inside the pupil are illuminated."""
        src = conventional(256, sigma=1.0)
        assert src.sum().item() == pytest.approx(1.0, rel=1e-10)

    def test_small_sigma(self):
        """σ=0.1 → very few pixels (near the centre)."""
        src = conventional(256, sigma=0.1)
        assert src.sum().item() == pytest.approx(1.0, rel=1e-10)
        assert (src > 0).sum().item() < 256 * 256  # not all pixels


class TestAnnularSource:
    def test_normalised(self):
        src = annular(256, sigma_in=0.3, sigma_out=0.8)
        assert abs(src.sum().item() - 1.0) < 1e-10

    def test_ring_shape(self):
        """Centre should be dark (inside sigma_in)."""
        src = annular(256, sigma_in=0.4, sigma_out=0.8)
        half = 128
        # Centre pixel should be 0
        assert src[half, half].item() == 0.0


class TestDipoleSource:
    def test_dipole_x_normalised(self):
        src = dipole_x(256)
        assert abs(src.sum().item() - 1.0) < 1e-10

    def test_dipole_y_normalised(self):
        src = dipole_y(256)
        assert abs(src.sum().item() - 1.0) < 1e-10

    def test_two_poles(self):
        """X-dipole should have exactly two disconnected regions."""
        src = dipole_x(256, sigma=0.15, separation=0.5)
        nonzero = (src > 0).sum().item()
        assert nonzero > 0


class TestQuasarSource:
    def test_normalised(self):
        src = quasar(256)
        assert abs(src.sum().item() - 1.0) < 1e-10

    def test_four_poles(self):
        src = quasar(256, sigma=0.12)
        nonzero = (src > 0).sum().item()
        assert nonzero > 0


class TestCustomSource:
    def test_normalised(self):
        raw = torch.ones(64, 64)
        src = custom(raw)
        assert abs(src.sum().item() - 1.0) < 1e-10

    def test_all_zero(self):
        """All-zero input → all-zero output."""
        raw = torch.zeros(64, 64)
        src = custom(raw)
        assert src.sum().item() == 0.0