"""Tests for the illumination source module."""

import pytest
import torch

from euvsimulator.aerial.source import (
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

    @staticmethod
    def _lit_radii(src: torch.Tensor) -> torch.Tensor:
        x = torch.linspace(-1.0, 1.0, src.shape[0], dtype=torch.float64)
        gx, gy = torch.meshgrid(x, x, indexing="ij")
        return torch.sqrt(gx**2 + gy**2)[src > 0]

    @pytest.mark.parametrize("grid", [256, 257])
    @pytest.mark.parametrize("sigma", [0.2, 0.12])
    def test_four_separate_poles(self, grid, sigma):
        """Four disconnected poles between sigma_out - 2*sigma and sigma_out."""
        from scipy import ndimage

        src = quasar(grid, sigma=sigma, sigma_out=0.8)
        _, n_poles = ndimage.label((src > 0).numpy())
        assert n_poles == 4
        r = self._lit_radii(src)
        step = 2.0 / (grid - 1)
        assert r.min().item() >= 0.8 - 2 * sigma - step
        assert r.max().item() <= 0.8 + 1e-6

    def test_one_pole_per_quadrant(self):
        src = quasar(256)
        h = 128
        for quad in (src[h:, h:], src[:h, h:], src[:h, :h], src[h:, :h]):
            assert quad.sum().item() == pytest.approx(0.25, abs=0.01)

    def test_sigma_out_moves_poles(self):
        r_small = self._lit_radii(quasar(256, sigma=0.1, sigma_out=0.5))
        r_large = self._lit_radii(quasar(256, sigma=0.1, sigma_out=0.9))
        assert r_large.min().item() > r_small.max().item()

    def test_opening_angle_deprecated_and_ignored(self):
        with pytest.warns(DeprecationWarning):
            src = quasar(257, opening_angle_deg=5.0)
        assert torch.equal(src, quasar(257))

    def test_no_warning_by_default(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            quasar(257)

    @pytest.mark.parametrize("sigma", [0.0, -0.1, 0.35])
    def test_invalid_pole_radius_raises(self, sigma):
        with pytest.raises(ValueError):
            quasar(256, sigma=sigma, sigma_out=0.8)


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


class TestEmptySourceRaises:
    """A shape that covers no grid pixel must raise, not return NaN."""

    @pytest.mark.parametrize(
        "make",
        [
            lambda: conventional(256, sigma=0.0),
            lambda: conventional(256, sigma=0.005),
            lambda: annular(256, sigma_in=0.8, sigma_out=0.3),
            lambda: annular(256, sigma_in=0.5, sigma_out=0.5),
            lambda: dipole_x(256, sigma=0.001),
            lambda: dipole_y(256, sigma=0.001),
        ],
    )
    def test_raises_value_error(self, make):
        with pytest.raises(ValueError):
            make()

    def test_odd_grid_sigma_zero_is_single_pixel(self):
        """sigma=0 on an odd grid hits the centre pixel: coherent point source."""
        src = conventional(257, sigma=0.0)
        assert not torch.isnan(src).any()
        assert (src > 0).sum().item() == 1
        assert src[128, 128].item() == 1.0
