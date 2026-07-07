"""Tests for the Mo/Si multilayer stack builder."""

import math

import pytest
import torch

from euv.optics.multilayer import (
    MultilayerStack,
    default_materials,
    interdiffusion_correction,
    mo_si_stack,
)
from euv.optics.tmm import reflectivity


class TestMultilayerStack:
    """Verify the MultilayerStack dataclass."""

    def test_properties(self):
        stack = MultilayerStack(
            n_layers=torch.tensor([1.0 + 0.0j], dtype=torch.complex128),
            thicknesses=torch.tensor([10e-9], dtype=torch.float64),
            symbols=["Vac"],
            description="test",
        )
        assert stack.N == 1
        assert stack.total_thickness_m == 10e-9


class TestMoSiStack:
    """Verify the Mo/Si stack builder."""

    def test_default_stack_shape(self):
        """Default 50-bilayer Mo/Si stack should have correct layer count:
        50 bilayers × 2 + 1 capping layer = 101 layers.
        """
        stack = mo_si_stack(n_bilayers=50)
        expected_layers = 50 * 2 + 1  # Mo/Si bilayers + Ru cap
        assert stack.N == expected_layers, f"Expected {expected_layers} layers, got {stack.N}"
        assert stack.symbols[0] == "Ru"
        assert stack.symbols[1] == "Mo"
        assert stack.symbols[2] == "Si"

    def test_uncapped_stack(self):
        """No capping layer → 40 bilayers × 2 = 80 layers."""
        stack = mo_si_stack(n_bilayers=40, capping_layer=None)
        assert stack.N == 80
        assert stack.symbols[0] == "Mo"

    def test_thickness_values(self):
        """Thicknesses should match the specified values."""
        stack = mo_si_stack(n_bilayers=1, d_mo_nm=3.0, d_si_nm=4.0)
        # Layering: Ru cap (2.5nm), Mo (3.0nm), Si (4.0nm) = 3 layers
        assert stack.N == 3
        assert stack.thicknesses[0].item() == pytest.approx(2.5e-9)
        assert stack.thicknesses[1].item() == pytest.approx(3.0e-9)
        assert stack.thicknesses[2].item() == pytest.approx(4.0e-9)

    def test_refractive_indices_are_complex(self):
        """Refractive indices should be complex128."""
        stack = mo_si_stack(n_bilayers=5)
        assert stack.n_layers.dtype == torch.complex128
        # All n should have positive real part
        assert torch.all(stack.n_layers.real > 0)

    def test_peak_reflectivity_via_builder(self):
        """Mo/Si stack built via mo_si_stack should show ~70% peak."""
        stack = mo_si_stack(n_bilayers=40)
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)

        R, _ = reflectivity(
            stack.n_layers,
            stack.thicknesses,
            wl,
            theta0,
            te=True,
        )
        assert 0.60 <= R.item() <= 0.80


class TestInterdiffusion:
    """Verify interdiffusion correction."""

    def test_adds_layers(self):
        """Interdiffusion correction should insert layers at interfaces."""
        n = torch.tensor(
            [0.9 + 0.01j, 1.0 + 0.001j, 0.9 + 0.01j, 1.0 + 0.001j],
            dtype=torch.complex128,
        )
        d = torch.tensor([2.8e-9, 4.1e-9, 2.8e-9, 4.1e-9], dtype=torch.float64)

        n_corr, d_corr = interdiffusion_correction(n, d, sigma_nm=0.5)

        # 4 layers → 3 interfaces → 7 layers
        assert n_corr.shape[0] == 7
        assert d_corr.shape[0] == 7

    def test_reduces_reflectivity(self):
        """Interdiffusion correction should reduce peak reflectivity."""
        d_mo = 2.8e-9
        d_si = 4.1e-9
        n_bilayers = 40

        n_list = []
        d_list = []
        for _ in range(n_bilayers):
            n_list.append(0.9238 + 0.00637j)
            d_list.append(d_mo)
            n_list.append(0.999 + 0.00183j)
            d_list.append(d_si)

        n_ideal = torch.tensor(n_list, dtype=torch.complex128)
        d_ideal = torch.tensor(d_list, dtype=torch.float64)

        n_corr, d_corr = interdiffusion_correction(n_ideal, d_ideal, sigma_nm=0.5)

        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)

        R_ideal, _ = reflectivity(n_ideal, d_ideal, wl, theta0, te=True)
        R_corr, _ = reflectivity(n_corr, d_corr, wl, theta0, te=True)

        # Interdiffusion should reduce reflectivity (Debye-Waller damping)
        assert (
            R_corr.item() < R_ideal.item()
        ), f"Interdiffused R ({R_corr:.4f}) should be < ideal R ({R_ideal:.4f})"


class TestDefaultMaterials:
    """Verify the default_materials convenience function."""

    def test_returns_dict(self):
        mats = default_materials()
        assert "Mo" in mats
        assert "Si" in mats
        assert "Ru" in mats
        assert isinstance(mats["Mo"], complex)
        assert mats["Mo"].real > 0
