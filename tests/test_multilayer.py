"""Tests for the Mo/Si multilayer stack builder."""

import math

import pytest
import torch

from euvsimulator.optics.multilayer import (
    MultilayerStack,
    default_materials,
    interdiffusion_correction,
    mo_si_stack,
)
from euvsimulator.optics.tmm import reflectivity


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
        # Si-terminated: the cap lies on Si, the bottom Mo layer on the substrate
        assert stack.symbols[1] == "Si"
        assert stack.symbols[2] == "Mo"
        assert stack.symbols[-1] == "Mo"

    def test_uncapped_stack(self):
        """No capping layer → 40 bilayers × 2 = 80 layers."""
        stack = mo_si_stack(n_bilayers=40, capping_layer=None)
        assert stack.N == 80
        assert stack.symbols[0] == "Si"

    def test_thickness_values(self):
        """Thicknesses should match the specified values."""
        stack = mo_si_stack(n_bilayers=1, d_mo_nm=3.0, d_si_nm=4.0)
        # Layering: Ru cap (2.5nm), Si (4.0nm), Mo (3.0nm) = 3 layers
        assert stack.N == 3
        assert stack.thicknesses[0].item() == pytest.approx(2.5e-9)
        assert stack.thicknesses[1].item() == pytest.approx(4.0e-9)
        assert stack.thicknesses[2].item() == pytest.approx(3.0e-9)

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

    def test_gamma_keeps_bilayer_period(self):
        """Gamma splits the fixed period d_mo_nm + d_si_nm (6.9 nm).

        Before the fix gamma=0.45 kept d_Mo = 2.8 nm and gave a 6.222 nm
        period (measured 2026-10-02).
        """
        for g in (0.35, 0.4, 0.45, 0.5):
            stack = mo_si_stack(n_bilayers=3, gamma=g, capping_layer=None)
            d = stack.thicknesses
            for i in range(3):
                # Si is the upper layer of a bilayer (Si-terminated stack)
                assert d[2 * i].item() == pytest.approx((1 - g) * 6.9e-9, rel=1e-12)
                assert d[2 * i + 1].item() == pytest.approx(g * 6.9e-9, rel=1e-12)
                assert (d[2 * i] + d[2 * i + 1]).item() == pytest.approx(6.9e-9, rel=1e-12)

    def test_gamma_matching_thicknesses_reproduces_default(self):
        """Gamma = 2.8/6.9 is the default split, so the stack is unchanged."""
        ref = mo_si_stack()
        stack = mo_si_stack(gamma=2.8 / 6.9)
        assert torch.allclose(stack.thicknesses, ref.thicknesses, rtol=0.0, atol=1e-20)

    def test_gamma_keeps_bragg_peak(self):
        """Changing gamma keeps the mirror on the 13.5 nm Bragg peak.

        Measured 2026-10-02 (50 bilayers, Ru cap, 13.5 nm, 6 deg, Si
        substrate): gamma=None R 0.647; after the fix gamma 0.35 R 0.656,
        0.45 R 0.624; before the fix 0.0005 and 0.042 (period moved).
        """
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)
        ref = mo_si_stack()
        R_ref, _ = reflectivity(ref.n_layers, ref.thicknesses, wl, theta0, te=True)
        for g in (0.35, 0.45):
            stack = mo_si_stack(gamma=g)
            R, _ = reflectivity(stack.n_layers, stack.thicknesses, wl, theta0, te=True)
            assert R.item() > 0.9 * R_ref.item(), (g, R.item(), R_ref.item())

    @pytest.mark.parametrize("g", [0.0, 1.0, -0.1, 1.2])
    def test_gamma_out_of_range_raises(self, g):
        """gamma=0 used to raise ZeroDivisionError, gamma>=1 gave d_Si <= 0."""
        with pytest.raises(ValueError, match="gamma"):
            mo_si_stack(n_bilayers=1, gamma=g)

    def test_description_reports_built_thicknesses(self):
        """The description reports the thicknesses actually built.

        It used to print d_mo_nm/d_si_nm even when gamma replaced them.
        """
        assert mo_si_stack().description.endswith("(2.8/4.1 nm) on Si")
        assert mo_si_stack(gamma=0.3).description.endswith("(2.1/4.8 nm) on Si")


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
        assert R_corr.item() < R_ideal.item(), (
            f"Interdiffused R ({R_corr:.4f}) should be < ideal R ({R_ideal:.4f})"
        )


class TestDefaultMaterials:
    """Verify the default_materials convenience function."""

    def test_returns_dict(self):
        mats = default_materials()
        assert "Mo" in mats
        assert "Si" in mats
        assert "Ru" in mats
        assert isinstance(mats["Mo"], complex)
        assert mats["Mo"].real > 0


class TestInterdiffusionPreservesPeriod:
    """interdiffusion_correction must keep the Bragg period."""

    @staticmethod
    def _stack():
        st = mo_si_stack(n_bilayers=50, capping_layer=None)
        return st.n_layers, st.thicknesses

    def test_total_thickness_unchanged(self):
        n, d = self._stack()
        for sigma in (0.1, 0.3, 0.5):
            n2, d2 = interdiffusion_correction(n, d, sigma_nm=sigma)
            assert n2.shape[0] == 2 * n.shape[0] - 1
            assert float(d2.sum()) == pytest.approx(float(d.sum()), rel=1e-12)

    def test_inserted_layer_geometry(self):
        n = torch.tensor([0.9 + 0.01j, 1.0 + 0.001j, 0.9 + 0.01j], dtype=torch.complex128)
        d = torch.tensor([2.8e-9, 4.1e-9, 2.8e-9], dtype=torch.float64)
        n2, d2 = interdiffusion_correction(n, d, sigma_nm=0.5)
        expected_d = [2.3e-9, 1.0e-9, 3.1e-9, 1.0e-9, 2.3e-9]
        assert len(d2.tolist()) == len(expected_d)
        for got, want in zip(d2.tolist(), expected_d):
            assert got == pytest.approx(want, rel=1e-12)
        assert complex(n2[1]) == pytest.approx(0.95 + 0.0055j)
        assert complex(n2[3]) == pytest.approx(0.95 + 0.0055j)

    def test_explicit_index_is_used(self):
        n = torch.tensor([0.9 + 0.01j, 1.0 + 0.001j], dtype=torch.complex128)
        d = torch.tensor([2.8e-9, 4.1e-9], dtype=torch.float64)
        n2, _ = interdiffusion_correction(n, d, sigma_nm=0.5, n_interdiffused=0.97 + 0.004j)
        assert complex(n2[1]) == pytest.approx(0.97 + 0.004j)

    def test_matches_nevot_croce(self):
        n, d = self._stack()
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)
        R_ideal, _ = reflectivity(n, d, wl, theta0, te=True)
        for sigma in (0.1, 0.3, 0.5):
            n2, d2 = interdiffusion_correction(n, d, sigma_nm=sigma)
            R_corr, _ = reflectivity(n2, d2, wl, theta0, te=True)
            R_nc, _ = reflectivity(n, d, wl, theta0, te=True, roughness_nm=sigma)
            assert R_corr.item() < R_ideal.item()
            assert abs(R_corr.item() - R_nc.item()) / R_nc.item() < 0.02
        # sigma = 0.5 nm: 0.735 -> 0.686 (vacuum spacers gave 0.014)
        assert 0.66 < R_corr.item() < 0.70

    def test_rejects_bad_sigma(self):
        n = torch.tensor([0.9 + 0.01j, 1.0 + 0.001j, 0.9 + 0.01j], dtype=torch.complex128)
        d = torch.tensor([2.8e-9, 4.1e-9, 2.8e-9], dtype=torch.float64)
        with pytest.raises(ValueError):
            interdiffusion_correction(n, d, sigma_nm=-0.1)
        with pytest.raises(ValueError):
            # the 4.1 nm middle layer cannot give up 2 * 2.1 nm
            interdiffusion_correction(n, d, sigma_nm=2.1)


class TestParabolicGrading:
    """grading_parabolic_nm: nominal period at the centre, +amplitude at top and bottom."""

    def test_profile(self):
        st = mo_si_stack(n_bilayers=11, grading_parabolic_nm=0.15, capping_layer=None)
        d_nm = (st.thicknesses * 1e9).tolist()
        periods = [d_nm[2 * i] + d_nm[2 * i + 1] for i in range(11)]
        expected = [6.9 + 0.15 * (2.0 * i / 10 - 1.0) ** 2 for i in range(11)]
        for got, want in zip(periods, expected):
            assert got == pytest.approx(want, abs=1e-9)
        assert periods[0] == pytest.approx(7.05, abs=1e-9)
        assert periods[5] == pytest.approx(6.9, abs=1e-9)
        assert periods[10] == pytest.approx(7.05, abs=1e-9)

    def test_zero_amplitude_is_nominal(self):
        st = mo_si_stack(n_bilayers=50, grading_parabolic_nm=0.0)
        assert torch.equal(st.thicknesses, mo_si_stack(n_bilayers=50).thicknesses)
        assert st.symbols[0] == "Ru"  # cap, 2.5 nm
        assert st.thicknesses[1].item() == pytest.approx(4.1e-9)  # Si on top
        assert st.thicknesses[-1].item() == pytest.approx(2.8e-9)  # Mo on the substrate

    def test_single_bilayer_is_centre(self):
        st = mo_si_stack(n_bilayers=1, grading_parabolic_nm=0.15, capping_layer=None)
        assert float(st.thicknesses.sum()) * 1e9 == pytest.approx(6.9, abs=1e-9)


class TestPeriodProperty:
    """period_nm must not include the capping layer."""

    def test_capped_and_uncapped(self):
        assert mo_si_stack().period_nm == pytest.approx(6.9)
        assert mo_si_stack(capping_layer=None).period_nm == pytest.approx(6.9)
        assert mo_si_stack(n_bilayers=3, d_mo_nm=3.0, d_si_nm=4.0).period_nm == pytest.approx(7.0)
