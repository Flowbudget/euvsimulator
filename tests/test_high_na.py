"""Tests for High-NA anamorphic imaging support."""

from __future__ import annotations

import pytest
import torch

from euvsimulator.aerial.pupil import (
    anamorphic_pupil,
    apply_aberrations,
    pupil_cutoff_frequencies,
    pupil_grid,
    zernike,
)


class TestAnamorphicPupil:
    """Test suite for the High-NA anamorphic pupil."""

    def test_anamorphic_pupil_basic(self):
        """Anamorphic pupil should be non-zero in the stretched region."""
        pupil = anamorphic_pupil(128, na=0.55, mag_x=4.0, mag_y=8.0)
        assert pupil.shape == (128, 128)
        assert pupil.dtype == torch.float64
        assert pupil.max() > 0.5  # some transmission
        assert pupil.min() >= 0.0

    def test_anamorphic_asymmetry(self):
        """Mask-side extent in y is mag_x/mag_y = 1/2 of the extent in x."""
        pupil = anamorphic_pupil(257, na=0.55, mag_x=4.0, mag_y=8.0)
        fx, fy, _ = pupil_grid(257, na=0.55, mag_x=4.0, mag_y=8.0)
        inside = pupil > 0.5
        half_x = float(fx[inside].abs().max())
        half_y = float(fy[inside].abs().max())
        assert half_x == pytest.approx(1.0, abs=1e-12)
        assert half_y == pytest.approx(0.5, abs=2.0 / 256)

    def test_anamorphic_vs_circular(self):
        """Same NA and grid: the 4x/8x pupil covers half the area of the 4x/4x one."""
        anam = anamorphic_pupil(256, na=0.55, mag_x=4.0, mag_y=8.0)
        circ = pupil_grid(256, na=0.55, mag_x=4.0, mag_y=4.0)[2].to(torch.float64)
        assert (anam.sum() / circ.sum()).item() == pytest.approx(0.5, rel=0.02)

    def test_anamorphic_na_scaling(self):
        """Mask-side cut-off NA/(mag·λ): scales with NA, ratio x/y = mag_y/mag_x."""
        lo = pupil_cutoff_frequencies(0.33, 4.0, 8.0)
        hi = pupil_cutoff_frequencies(0.55, 4.0, 8.0)
        assert hi[0] / lo[0] == pytest.approx(0.55 / 0.33, rel=1e-12)
        assert hi[0] / hi[1] == pytest.approx(2.0, rel=1e-12)
        assert hi[0] == pytest.approx(0.55 / (4.0 * 13.5), rel=1e-12)

    def test_anamorphic_device(self):
        """Pupil on CPU should work."""
        pupil = anamorphic_pupil(64, na=0.55, mag_x=4.0, mag_y=8.0)
        assert pupil.device.type == "cpu"

    def test_anamorphic_preserves_power(self):
        """Pupil should be 1 inside, 0 outside."""
        pupil = anamorphic_pupil(64, na=0.55, mag_x=4.0, mag_y=8.0)
        assert torch.all(pupil[pupil > 0.5] == 1.0)
        assert torch.all(pupil[pupil <= 0.5] == 0.0)


class TestHighNAAerialImage:
    """Test High-NA imaging through the Abbe module."""

    def test_high_na_pupil_integration(self):
        """High-NA pupil should work with Abbe imaging."""
        from euvsimulator.aerial.abbe import abbe_image
        from euvsimulator.aerial.source import conventional

        grid = 64
        mask = torch.zeros(grid, grid, dtype=torch.complex128)
        mask[:, 20:44] = 1.0  # simple line/space
        mask_fft = torch.fft.fftshift(torch.fft.fft2(mask))

        source = conventional(grid, sigma=0.6)
        fx, fy, inside = pupil_grid(grid, na=0.33)
        pupil = inside.to(torch.float64).to(torch.complex128)

        image_low = abbe_image(mask_fft, source, fx, fy, pupil, na=0.33)

        # High-NA
        pupil_high = anamorphic_pupil(grid, na=0.55, mag_x=4.0, mag_y=8.0)
        pupil_high = pupil_high.to(torch.complex128)
        image_high = abbe_image(mask_fft, source, fx, fy, pupil_high, na=0.55)

        assert image_low.shape == image_high.shape == (grid, grid)
        assert image_high.max() > 0.0, "High-NA image should have signal"

    def test_high_na_low_na_difference(self):
        """Abbe with different pupil masks should produce different images.

        The pupil acts as a frequency filter — blocking part of the pupil
        changes the resulting aerial image.
        """
        from euvsimulator.aerial.abbe import abbe_image
        from euvsimulator.aerial.source import conventional

        grid = 64
        mask = torch.zeros(grid, grid, dtype=torch.complex128)
        mask[:, 22:42] = 1.0
        mask_fft = torch.fft.fftshift(torch.fft.fft2(mask))

        source = conventional(grid, sigma=0.8)
        fx, fy, inside = pupil_grid(grid, na=0.33, mag_x=4.0, mag_y=4.0)
        pupil_full = inside.to(torch.float64).to(torch.complex128)

        # All-pass pupil
        img_full = abbe_image(mask_fft, source, fx, fy, pupil_full, na=0.33)

        # Half-pupil: block the right half
        pupil_half = pupil_full.clone()
        pupil_half[:, grid // 2 :] = 0.0
        img_half = abbe_image(mask_fft, source, fx, fy, pupil_half, na=0.33)

        diff = (img_full - img_half).abs().mean().item()
        assert diff > 0.001, f"Different pupil masks should give different images: diff={diff:.6f}"


class TestZernikeHighNA:
    """Test Zernike aberrations in the High-NA context."""

    def test_zernike_anamorphic_grid(self):
        """Zernike polynomials should work on an anamorphic grid."""
        fx, fy, _ = pupil_grid(64, na=0.55, mag_x=4.0, mag_y=8.0)
        Z5 = zernike(2, 0, fx, fy)  # defocus
        assert Z5.shape == (64, 64)
        assert torch.isfinite(Z5).all()

    def test_zernike_astigmatism(self):
        """Zernike astigmatism (Z6) should have 2-fold symmetry."""
        fx, fy, _ = pupil_grid(64, na=0.33)
        Z6 = zernike(2, 2, fx, fy)  # astigmatism
        # Z(2,2) = x² - y² → should be equal at symmetric x-coordinates
        half = 32
        # Check at radius 0.5 (normalised coordinate)
        d = 16
        assert abs(Z6[half - d, half] - Z6[half + d, half]) < 0.04, (
            "Astigmatism should have 2-fold symmetry about x"
        )

    def test_apply_aberrations_preserves_shape(self):
        """Applying aberrations to a pupil should preserve its shape."""
        grid = 64
        fx, fy, inside = pupil_grid(grid, na=0.33)
        pupil = inside.to(torch.float64).to(torch.complex128)
        coeffs = [(2, 0, 0.5), (2, 2, 0.3)]  # defocus + astigmatism
        aberrated = apply_aberrations(pupil, fx, fy, coeffs)
        assert aberrated.shape == pupil.shape
        assert torch.isfinite(aberrated).all()
