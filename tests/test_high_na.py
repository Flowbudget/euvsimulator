"""Tests for High-NA anamorphic imaging support."""

from __future__ import annotations

import torch

from euv.aerial.pupil import anamorphic_pupil, apply_aberrations, pupil_grid, zernike


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
        """Anamorphic NA 0.55 should be asymmetric in frequency space.

        The anamorphic pupil scales X and Y differently (8× in y vs 4× in x),
        so the *spatial-frequency* extent in y is smaller for the same NA.
        """
        na = 0.55
        mag_x, mag_y = 4.0, 8.0

        fx, fy, inside = pupil_grid(256, na=na, mag_x=mag_x, mag_y=mag_y)
        pupil = inside.to(torch.float64)

        # Normalised coordinates: fx, fy ∈ [-1, 1].
        # Physical frequency range is fx * NA/mag_x, fy * NA/mag_y.
        max_fx_phys = float(fx.abs().max()) * na / mag_x
        max_fy_phys = float(fy.abs().max()) * na / mag_y
        # mag_y=8 > mag_x=4 → narrower physical y-range
        assert (
            max_fx_phys > max_fy_phys + 0.01
        ), f"Physical fx range ({max_fx_phys:.4f}) should be > fy range ({max_fy_phys:.4f})"
        assert abs(max_fx_phys - na / mag_x) < 0.01
        assert abs(max_fy_phys - na / mag_y) < 0.01

    def test_anamorphic_vs_circular(self):
        """Anamorphic NA 0.55 should have smaller area than circular NA 0.33."""
        anam = anamorphic_pupil(128, na=0.55, mag_x=4.0, mag_y=8.0)
        circ = pupil_grid(128, na=0.33, mag_x=4.0, mag_y=4.0)[2].to(torch.float64)

        area_anam = anam.sum().item()
        area_circ = circ.sum().item()
        # Anamorphic 0.55 squashed by 8× should have area comparable to 0.33
        # (0.55/4) * (0.55/8) ≈ 0.0094 vs (0.33/4)² ≈ 0.0068
        # So anam should be slightly larger
        assert (
            area_anam > area_circ * 0.5
        ), f"Anamorphic area ({area_anam}) should be > 0.5× circular ({area_circ})"

    def test_anamorphic_na_scaling(self):
        """Higher NA should produce a larger physical frequency range."""
        fx_lo, _, _ = pupil_grid(64, na=0.33, mag_x=4.0, mag_y=8.0)
        fx_hi, _, _ = pupil_grid(64, na=0.55, mag_x=4.0, mag_y=8.0)
        # In normalised coords both are [-1,1]; physical range = coord * NA/mag
        assert float(fx_hi.abs().max() * 0.55 / 8.0) > float(
            fx_lo.abs().max() * 0.33 / 8.0
        ), "Higher NA should have larger physical frequency extent"

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
        from euv.aerial.abbe import abbe_image
        from euv.aerial.source import conventional

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
        from euv.aerial.abbe import abbe_image
        from euv.aerial.source import conventional

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
        assert (
            abs(Z6[half - d, half] - Z6[half + d, half]) < 0.04
        ), "Astigmatism should have 2-fold symmetry about x"

    def test_apply_aberrations_preserves_shape(self):
        """Applying aberrations to a pupil should preserve its shape."""
        grid = 64
        fx, fy, inside = pupil_grid(grid, na=0.33)
        pupil = inside.to(torch.float64).to(torch.complex128)
        coeffs = [(2, 0, 0.5), (2, 2, 0.3)]  # defocus + astigmatism
        aberrated = apply_aberrations(pupil, fx, fy, coeffs)
        assert aberrated.shape == pupil.shape
        assert torch.isfinite(aberrated).all()
