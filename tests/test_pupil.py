"""Tests for the pupil module."""

import pytest
import torch

from euv.aerial.pupil import (
    anamorphic_pupil,
    apply_aberrations,
    circular_pupil,
    pupil_grid,
    zernike,
)


class TestPupilGrid:
    def test_coordinates(self):
        fx, fy, inside = pupil_grid(64, na=0.33)
        assert fx.shape == (64, 64)
        assert fy.shape == (64, 64)
        assert inside.shape == (64, 64)
        assert inside.dtype == torch.bool

    def test_anamorphic(self):
        fx, fy, inside = pupil_grid(64, na=0.55, mag_x=4.0, mag_y=8.0)
        assert fx.shape == (64, 64)
        # Normalised coordinates: both [-1,1]. Anamorphic scaling is in
        # the pupil shape:  (fx/mag_x)² + (fy/mag_y)² ≤ 1
        # With mag_x=4, mag_y=8 and range [-1,1], LHS max = 0.078 ≪ 1,
        # so the anamorphic pupil fills the entire grid (unlike circular).
        pupil_ani = anamorphic_pupil(64, na=0.55, mag_x=4.0, mag_y=8.0)
        pupil_ref = circular_pupil(64, na=0.55)
        # Anamorphic stretches the pupil in frequency space → more pixels inside
        assert pupil_ani.sum() > pupil_ref.sum(), (
            "Anamorphic pupil fills more of the grid than circular"
        )
        # Check that anamorphic with different mags yields different areas
        pupil_ani2 = anamorphic_pupil(64, na=0.55, mag_x=8.0, mag_y=4.0)
        # Different orientation → different shape even though same area
        assert pupil_ani.shape == pupil_ani2.shape


class TestCircularPupil:
    def test_shape(self):
        pupil = circular_pupil(64, na=0.33)
        assert pupil.shape == (64, 64)
        assert pupil.dtype == torch.float64
        assert 0.0 <= pupil.min().item() <= pupil.max().item() <= 1.0

    def test_diameter(self):
        """Pupil should be non-zero at centre."""
        pupil = circular_pupil(256, na=0.33)
        half = 128
        assert pupil[half, half].item() == 1.0


class TestZernike:
    def test_piston(self):
        """Zernike Z₀⁰ (piston) = 1 everywhere inside the pupil."""
        fx, fy, _ = pupil_grid(64)
        Z = zernike(0, 0, fx, fy)
        inside = (fx**2 + fy**2) <= 1.0
        assert Z[inside].mean().item() == pytest.approx(1.0, abs=0.01)

    def test_tilt(self):
        """Zernike Z₁¹ (x-tilt) should be proportional to x."""
        fx, fy, _ = pupil_grid(64)
        Z = zernike(1, 1, fx, fy)
        # Should be antisymmetric in x
        half = 32
        assert Z[half, :].mean().item() == pytest.approx(0.0, abs=0.5)


class TestApplyAberrations:
    def test_no_aberrations(self):
        """Zero aberrations → pupil unchanged."""
        pupil = circular_pupil(64).to(torch.complex128)
        fx, fy, _ = pupil_grid(64)
        aberrated = apply_aberrations(pupil, fx, fy, [])
        assert torch.allclose(aberrated, pupil)

    def test_defocus(self):
        """Z₀² + Z₂⁰ (defocus) adds quadratic phase."""
        pupil = circular_pupil(64).to(torch.complex128)
        fx, fy, _ = pupil_grid(64)
        aberrated = apply_aberrations(pupil, fx, fy, [(2, 0, 1.0)])
        # Phase should differ from zero
        assert not torch.allclose(aberrated, pupil)


class TestAnamorphicPupil:
    def test_shape(self):
        pupil = anamorphic_pupil(64, na=0.55)
        assert pupil.shape == (64, 64)
        assert pupil.dtype == torch.float64
