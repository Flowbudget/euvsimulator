"""Tests for the mask geometry builder module."""

import pytest
import torch

from euvsimulator.mask3d.geometry import (
    MaskLayer,
    MaskStack,
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
        assert len(mask.absorber_layers) == 2  # Ta absorber (top) + Ru cap (under it)
        assert mask.absorber_layers[0].material == "Ta"
        assert mask.absorber_layers[0].etched is True
        assert mask.absorber_layers[1].material == "Ru"
        assert mask.absorber_layers[1].etched is False
        assert mask.multilayer_bilayers == 40
        assert mask.period_nm == 64.0
        assert mask.line_width_nm == 32.0

    def test_total_absorber_thickness(self):
        mask = standard_euv_mask(absorber_thickness_nm=50.0, capping_thickness_nm=3.0)
        # Only the etched 50 nm absorber counts; the blanket 3 nm cap does not.
        assert mask.total_absorber_thickness_nm == pytest.approx(50.0)

    def test_custom_absorber(self):
        mask = standard_euv_mask(absorber="Ni", absorber_thickness_nm=40.0)
        assert mask.absorber_layers[0].material == "Ni"


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
        assert eps_mo.real < eps_sub.real < eps_si.real, (
            f"eps_sub.real={eps_sub.real:.4f} outside [{eps_mo.real:.4f}, {eps_si.real:.4f}]"
        )


class TestCappingLayerNotInGrating:
    """The blanket Ru cap must not enter the absorber grating."""

    def test_standard_mask_grating_is_absorber_only(self):
        mask = standard_euv_mask()  # 60 nm Ta absorber + 2.5 nm Ru cap
        eps, d, _ = build_permittivity_profile(mask, n_samples=1024)
        # Grating height is the 60 nm absorber, not 62.5 nm (absorber + cap).
        assert d.item() == pytest.approx(60.0e-9, rel=1e-12)
        assert mask.total_absorber_thickness_nm == pytest.approx(60.0)
        ta_eps = complex(mask.absorber_layers[0].nk) ** 2
        assert eps[512].item() == pytest.approx(ta_eps, rel=1e-12)  # line centre
        assert eps[0].item() == pytest.approx(1.0 + 0.0j)  # space = vacuum

    def test_cap_does_not_change_profile(self):
        """standard_euv_mask gives the same grating as the pipeline's Ta-only stack."""
        mask = standard_euv_mask()
        ta = mask.absorber_layers[0]
        ta_only = MaskStack(
            absorber_layers=[MaskLayer(material="Ta", thickness_nm=60.0, nk=ta.nk, etched=True)],
            period_nm=mask.period_nm,
            line_width_nm=mask.line_width_nm,
        )
        eps_a, d_a, _ = build_permittivity_profile(mask, n_samples=1024)
        eps_b, d_b, _ = build_permittivity_profile(ta_only, n_samples=1024)
        assert torch.equal(eps_a, eps_b)
        assert torch.equal(d_a, d_b)

    def test_no_etched_layer_raises(self):
        stack = MaskStack(
            absorber_layers=[MaskLayer(material="Ru", thickness_nm=2.5, nk=0.89 + 0.017j)]
        )
        with pytest.raises(ValueError, match="etched=True"):
            build_permittivity_profile(stack, n_samples=64)

    def test_mixed_etched_materials_raise(self):
        stack = MaskStack(
            absorber_layers=[
                MaskLayer(material="TaBO", thickness_nm=2.0, nk=0.95 + 0.03j, etched=True),
                MaskLayer(material="Ta", thickness_nm=60.0, nk=0.94 + 0.04j, etched=True),
            ]
        )
        with pytest.raises(ValueError, match="different"):
            build_permittivity_profile(stack, n_samples=64)
