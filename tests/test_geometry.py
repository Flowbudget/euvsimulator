"""Tests for the mask geometry builder module."""

import pytest
import torch

from euv.mask3d.geometry import (
    MaskLayer,
    build_permittivity_profile,
    standard_euv_mask,
)


class TestMaskLayer:
    """Verify the MaskLayer dataclass."""

    def test_basic(self):
        layer = MaskLayer(material="Ta", thickness_nm=60.0, nk=0.94 + 0.04j, etched=True)
        assert layer.material == "Ta"
        assert layer.thickness_nm == 60.0
        assert layer.etched is True


class TestMaskStack:
    """Verify the MaskStack dataclass."""

    def test_standard_mask_has_layers(self):
        mask = standard_euv_mask()
        assert len(mask.absorber_layers) == 2  # Ru cap + Ta absorber
        assert mask.absorber_layers[0].material == "Ru"
        assert mask.absorber_layers[1].material == "Ta"
        assert mask.multilayer_bilayers == 40
        assert mask.period_nm == 64.0
        assert mask.line_width_nm == 32.0

    def test_total_absorber_thickness(self):
        mask = standard_euv_mask(absorber_thickness_nm=50.0, capping_thickness_nm=3.0)
        assert mask.total_absorber_thickness_nm == pytest.approx(53.0)

    def test_custom_absorber(self):
        mask = standard_euv_mask(absorber="Ni", absorber_thickness_nm=40.0)
        assert mask.absorber_layers[1].material == "Ni"


class TestBuildPermittivity:
    """Verify permittivity profile building."""

    def test_profile_shape(self):
        mask = standard_euv_mask()
        eps, d, eps_sub = build_permittivity_profile(mask, n_samples=512)
        assert eps.shape == (512,)
        assert eps.dtype == torch.complex128
        assert d.shape == (1,)
        assert d.dtype == torch.float64
        assert eps_sub.dtype == torch.complex128

    def test_line_and_space_values(self):
        """Line region should differ from space (vacuum)."""
        mask = standard_euv_mask()
        eps, _, _ = build_permittivity_profile(mask, n_samples=4096)
        # Some values should not be 1.0+0j (the vacuum permittivity)
        assert torch.any(eps.real != 1.0), "All eps = vacuum (no line present)"

    def test_substrate_permittivity_values(self):
        """Substrate permittivity should be between Si and Mo values."""
        mask = standard_euv_mask()
        _, _, eps_sub = build_permittivity_profile(mask)
        # eps_sub is weighted average of Mo and Si
        # Mo: (0.9238-0.00637j)² ≈ 0.8527-0.0118j
        # Si: (0.999-0.00183j)² ≈ 0.9980-0.00366j
        # Weighted average with 2.8/4.1 ratio
        eps_mo = complex(0.9238 + 0.00637j) ** 2
        eps_si = complex(0.999 + 0.00183j) ** 2
        assert (
            eps_mo.real < eps_sub.real < eps_si.real
        ), f"eps_sub.real={eps_sub.real:.4f} outside [{eps_mo.real:.4f}, {eps_si.real:.4f}]"
