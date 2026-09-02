"""Tests for the TMM multilayer mirror module."""

import math

import pytest
import torch

from euvsimulator.optics.tmm import (
    reflectivity,
    reflectivity_at_wavelength,
    reflectivity_scan,
)


class TestTMMSingleInterface:
    """Verify TMM on a single interface (Fresnel equations)."""

    def test_normal_incidence_glass(self):
        """A single interface at normal incidence should match Fresnel.

        Air (n=1) → glass (n=1.5): R = ((1-1.5)/(1+1.5))² ≈ 0.04
        """
        n_layers = torch.tensor([1.5 + 0.0j], dtype=torch.complex128)
        d = torch.tensor([1e-9], dtype=torch.float64)
        wl = torch.tensor([500e-9], dtype=torch.float64)
        theta0 = 0.0

        R_te, r_te = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=True,
        )
        R_tm, r_tm = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=False,
        )

        expected_R = ((1.0 - 1.5) / (1.0 + 1.5)) ** 2
        assert R_te.item() == pytest.approx(expected_R, abs=1e-4)
        assert R_tm.item() == pytest.approx(expected_R, abs=1e-4)
        assert r_te[0].real.item() < 0  # π phase shift on reflection

    def test_normal_incidence_silicon(self):
        """Si substrate at normal incidence with thin layer."""
        n_si = 0.999 + 0.0018j
        n_layers = torch.tensor([n_si], dtype=torch.complex128)
        d = torch.tensor([1e-12], dtype=torch.float64)
        R, _ = reflectivity(
            n_layers,
            d,
            torch.tensor([13.5e-9]),
            0.0,
            n_substrate=torch.tensor(n_si),
            te=True,
        )
        assert 0.0 <= R.item() <= 0.1


class TestTMMMoSiMultilayer:
    """Verify Mo/Si multilayer peak reflectivity at 13.5 nm."""

    def test_peak_reflectivity(self):
        """Mo/Si 40-bilayer mirror: ~70% peak at 13.5 nm, 6°, TE."""
        n_layers = torch.tensor([0.9238 + 0.00637j, 0.999 + 0.00183j] * 40, dtype=torch.complex128)
        d = torch.tensor([2.8e-9, 4.1e-9] * 40, dtype=torch.float64)
        R, _ = reflectivity(
            n_layers,
            d,
            torch.tensor([13.5e-9], dtype=torch.float64),
            math.radians(6.0),
            n_substrate=torch.tensor(0.999 + 0.00183j),
            te=True,
        )
        assert 0.60 <= R.item() <= 0.80, f"R={R.item():.4f}"

    def test_reflectivity_scan_shape(self):
        """Wavelength scan returns correct-length arrays."""
        n_layers = torch.tensor([0.9238 + 0.00637j, 0.999 + 0.00183j] * 10, dtype=torch.complex128)
        d = torch.tensor([2.8e-9, 4.1e-9] * 10, dtype=torch.float64)

        wl, R = reflectivity_scan(
            n_layers,
            d,
            wavelength_range=(13.0e-9, 14.0e-9, 21),
            theta0=math.radians(6.0),
            n_substrate=torch.tensor(0.999 + 0.00183j),
        )

        assert wl.shape == (21,)
        assert R.shape == (21,)
        assert torch.all(R >= 0)
        assert torch.all(R <= 1)

    def test_peak_near_13_5nm(self):
        """The reflectivity peak should be near 13.5 nm."""
        n_layers = torch.tensor([0.9238 + 0.00637j, 0.999 + 0.00183j] * 40, dtype=torch.complex128)
        d = torch.tensor([2.8e-9, 4.1e-9] * 40, dtype=torch.float64)

        wl, R = reflectivity_scan(
            n_layers,
            d,
            wavelength_range=(13.0e-9, 14.0e-9, 51),
            theta0=math.radians(6.0),
            n_substrate=torch.tensor(0.999 + 0.00183j),
        )

        peak_idx = torch.argmax(R)
        peak_wl = wl[peak_idx].item() * 1e9
        assert 13.3 <= peak_wl <= 13.7, f"Peak at {peak_wl:.3f} nm, expected near 13.5 nm"


class TestTMMPolarization:
    """Polarisation-dependent reflectivity."""

    def test_te_vs_tm(self):
        """TE reflectivity should be >= TM at oblique incidence."""
        n_layers = torch.tensor([1.5 + 0.0j], dtype=torch.complex128)
        d = torch.tensor([1e-9], dtype=torch.float64)
        wl = torch.tensor([500e-9], dtype=torch.float64)
        theta0 = math.radians(45.0)

        R_te, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=True,
        )
        R_tm, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=False,
        )

        assert R_te.item() >= R_tm.item(), (
            f"TE ({R_te:.4f}) should be >= TM ({R_tm:.4f}) at oblique incidence"
        )


class TestTMMDifferentiability:
    """Gradient checking for PyTorch autograd."""

    def test_thickness_gradient(self):
        """Reflectivity should be differentiable w.r.t. layer thickness."""
        n = torch.tensor([1.5 + 0.0j], dtype=torch.complex128, requires_grad=False)
        d = torch.tensor([200e-9], dtype=torch.float64, requires_grad=True)
        R, _ = reflectivity(
            n,
            d,
            torch.tensor([500e-9]),
            0.0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=True,
        )
        grad = torch.autograd.grad(R.sum(), d, create_graph=False)[0]
        assert grad is not None
        assert torch.isfinite(grad).all(), "Gradient contains NaN or inf"


class TestTMMConvenience:
    """Scalar convenience wrappers."""

    def test_reflectivity_at_wavelength(self):
        """reflectivity_at_wavelength returns a scalar float matching Fresnel."""
        n_layers = torch.tensor([1.5 + 0.0j], dtype=torch.complex128)
        d = torch.tensor([1e-9], dtype=torch.float64)
        R = reflectivity_at_wavelength(
            n_layers,
            d,
            500e-9,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=True,
        )
        assert isinstance(R, float)
        expected = ((1.0 - 1.5) / (1.0 + 1.5)) ** 2
        assert R == pytest.approx(expected, abs=1e-4)


class TestTMMn0Sin2:
    """P1-2 validation: TMM n0_sin2 extension for evanescent orders."""

    def test_theta_vs_n0_sin2_equivalent(self):
        """TMM with theta0 should equal TMM with n0_sin2 = sin^2(theta0)."""
        n_layers = torch.tensor([1.5 + 0.0j], dtype=torch.complex128)
        d = torch.tensor([1e-9], dtype=torch.float64)
        wl = torch.tensor([500e-9], dtype=torch.float64)
        theta0 = torch.tensor([math.radians(30.0)], dtype=torch.float64)

        R_theta, r_theta = reflectivity(
            n_layers, d, wl, theta0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=True,
        )
        n0_sin2 = torch.tensor([math.sin(math.radians(30.0)) ** 2], dtype=torch.float64)
        R_n0, r_n0 = reflectivity(
            n_layers, d, wl, theta0=None,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=True,
            n0_sin2=n0_sin2,
        )
        assert abs(R_theta.item() - R_n0.item()) < 1e-12
        assert abs(r_theta.item() - r_n0.item()) < 1e-12

    def test_theta_vs_n0_sin2_tm(self):
        """Same equivalence check for TM polarization."""
        n_layers = torch.tensor([1.5 + 0.0j], dtype=torch.complex128)
        d = torch.tensor([1e-9], dtype=torch.float64)
        wl = torch.tensor([500e-9], dtype=torch.float64)
        theta0 = torch.tensor([math.radians(30.0)], dtype=torch.float64)

        R_theta, r_theta = reflectivity(
            n_layers, d, wl, theta0,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=False,
        )
        n0_sin2 = torch.tensor([math.sin(math.radians(30.0)) ** 2], dtype=torch.float64)
        R_n0, r_n0 = reflectivity(
            n_layers, d, wl, theta0=None,
            n_substrate=torch.tensor(1.5 + 0.0j),
            te=False,
            n0_sin2=n0_sin2,
        )
        assert abs(R_theta.item() - R_n0.item()) < 1e-12

    def test_evanescent_no_nan(self):
        """TMM with n0_sin2 > 1 must not produce NaN for passive media."""
        n_layers = torch.tensor([0.94 + 0.03j], dtype=torch.complex128)
        d = torch.tensor([50e-9], dtype=torch.float64)
        wl = torch.tensor([13.5e-9], dtype=torch.float64)

        for n0_sin2_val in [1.05, 1.2, 1.5, 2.0, 5.0]:
            n0_sin2 = torch.tensor([n0_sin2_val], dtype=torch.float64)
            R, r = reflectivity(
                n_layers, d, wl, theta0=None,
                n_substrate=torch.tensor(0.94 + 0.03j),
                te=True,
                n0_sin2=n0_sin2,
            )
            assert not torch.isnan(R).any(), f"NaN at n0_sin2={n0_sin2_val}"
            assert not torch.isnan(r).any(), f"NaN at n0_sin2={n0_sin2_val}"
            assert not torch.isinf(R).any(), f"Inf at n0_sin2={n0_sin2_val}"

    def test_evanescent_reflectivity_bounded(self):
        """|r| must be <= 1 for passive media, even with n0_sin2 > 1."""
        n_layers = torch.tensor([0.94 + 0.03j], dtype=torch.complex128)
        d = torch.tensor([50e-9], dtype=torch.float64)
        wl = torch.tensor([13.5e-9], dtype=torch.float64)

        for n0_sin2_val in [0.5, 0.8, 0.95, 1.0, 1.05, 1.2, 1.5, 2.0]:
            n0_sin2 = torch.tensor([n0_sin2_val], dtype=torch.float64)
            R, r = reflectivity(
                n_layers, d, wl, theta0=None,
                n_substrate=torch.tensor(0.94 + 0.03j),
                te=True,
                n0_sin2=n0_sin2,
            )
            assert abs(r.item()) <= 1.0 + 1e-10, (
                f"|r| = {abs(r.item()):.6f} > 1 at n0_sin2={n0_sin2_val}"
            )
