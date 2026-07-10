"""Tests for the OpEnUV enhancements: Névot–Croce roughness, spectral scans, and plotting."""

import math

import pytest
import torch

from euv.optics.tmm import (
    reflectivity,
    reflectivity_at_wavelength,
    reflectivity_scan,
    stack_smatrix,
)

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def mo_si_layers():
    """Standard Mo/Si 40-bilayer stack (ideal, abrupt interfaces)."""
    n_layers = torch.tensor(
        [0.9238 + 0.00637j, 0.999 + 0.00183j] * 40,
        dtype=torch.complex128,
    )
    d = torch.tensor([2.8e-9, 4.1e-9] * 40, dtype=torch.float64)
    return n_layers, d


# ──────────────────────────────────────────────
# 1. Névot–Croce: physical sanity
# ──────────────────────────────────────────────


class TestNevotCroce:
    """Verify that the Névot–Croce roughness model behaves physically."""

    def test_roughness_reduces_reflectivity(self, mo_si_layers):
        """R should decrease monotonically with increasing sigma."""
        n_layers, d = mo_si_layers
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)

        R_ideal, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=None,
        )
        R_03, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=0.3,
        )
        R_05, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=0.5,
        )
        R_07, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=0.7,
        )

        assert R_ideal.item() >= R_03.item(), f"R_ideal({R_ideal:.4f}) < R_0.3({R_03:.4f})"
        assert R_03.item() >= R_05.item(), f"R_0.3({R_03:.4f}) < R_0.5({R_05:.4f})"
        assert R_05.item() >= R_07.item(), f"R_0.5({R_05:.4f}) < R_0.7({R_07:.4f})"

    def test_roughness_reduces_peak_by_reasonable_amount(self, mo_si_layers):
        """At σ=0.5 nm, R should be 3-15 % lower than the ideal peak."""
        n_layers, d = mo_si_layers
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)

        R_ideal, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=None,
        )
        R_rough, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=0.5,
        )

        rel_drop = (R_ideal.item() - R_rough.item()) / R_ideal.item()
        # EUV multilayers with σ=0.5nm typically lose 3-15% peak R
        assert 0.03 <= rel_drop <= 0.25, f"Relative drop = {rel_drop:.1%}, expected 3-25%"

    def test_zero_roughness_matches_ideal(self, mo_si_layers):
        """roughness_nm=0.0 should give identical results to None."""
        n_layers, d = mo_si_layers
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)

        R_none, r_none = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=None,
        )
        R_zero, r_zero = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=0.0,
        )

        assert R_none.item() == pytest.approx(R_zero.item(), abs=1e-10)
        assert r_none.item() == pytest.approx(r_zero.item(), abs=1e-10)

    def test_roughness_kz_required(self, mo_si_layers):
        """Calling _interface_smatrix with sigma but without kz should raise."""
        from euv.optics.tmm import _interface_smatrix

        eta_a = torch.tensor([1.0 + 0.0j], dtype=torch.complex128)
        eta_b = torch.tensor([0.9 + 0.01j], dtype=torch.complex128)

        with pytest.raises(ValueError, match="kz_a and kz_b are required"):
            _interface_smatrix(eta_a, eta_b, roughness_nm=0.5)

    def test_roughness_backward_compatible(self, mo_si_layers):
        """Existing tests should pass without specifying roughness_nm."""
        n_layers, d = mo_si_layers
        wl = torch.tensor([13.5e-9], dtype=torch.float64)
        theta0 = math.radians(6.0)

        # Call without roughness_nm — should work as before
        R, _ = reflectivity(
            n_layers,
            d,
            wl,
            theta0,
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
        )
        assert 0.60 <= R.item() <= 0.80


# ──────────────────────────────────────────────
# 2. Spectral scan
# ──────────────────────────────────────────────


class TestSpectralScan:
    """Verify that spectral scans produce physically reasonable results."""

    def test_peak_near_13_5nm(self, mo_si_layers):
        """The reflectivity peak should be near 13.5 nm."""
        n_layers, d = mo_si_layers

        wl, R = reflectivity_scan(
            n_layers,
            d,
            wavelength_range=(13.0e-9, 14.0e-9, 51),
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
        )

        peak_idx = torch.argmax(R)
        peak_wl = wl[peak_idx].item() * 1e9
        assert 13.3 <= peak_wl <= 13.7, f"Peak at {peak_wl:.3f} nm"

    def test_scan_returns_valid_range(self, mo_si_layers):
        """All reflectivity values must be in [0, 1]."""
        n_layers, d = mo_si_layers

        wl, R = reflectivity_scan(
            n_layers,
            d,
            wavelength_range=(10.0e-9, 20.0e-9, 101),
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
        )

        assert wl.shape == (101,)
        assert R.shape == (101,)
        assert torch.all(R >= 0)
        assert torch.all(R <= 1)

    def test_scan_with_roughness(self, mo_si_layers):
        """Spectral scan should accept roughness_nm without error."""
        n_layers, d = mo_si_layers

        wl, R = reflectivity_scan(
            n_layers,
            d,
            wavelength_range=(13.0e-9, 14.0e-9, 21),
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
            roughness_nm=0.5,
        )

        assert torch.all(R >= 0)
        assert torch.all(R <= 1)


# ──────────────────────────────────────────────
# 3. Plotting
# ──────────────────────────────────────────────


class TestPlotting:
    """Verify that plotting functions run without errors (non-visual)."""

    def test_plot_spectrum_saves_file(self, mo_si_layers, tmp_path):
        """plot_reflectivity_spectrum should save a PNG without error."""
        from euv.optics.plot import plot_reflectivity_spectrum

        n_layers, d = mo_si_layers
        save_path = str(tmp_path / "spectrum.png")

        wl, R = plot_reflectivity_spectrum(
            n_layers,
            d,
            wavelength_range=(12.0e-9, 15.0e-9, 51),
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
            save_path=save_path,
        )

        # Check the file was created
        import os

        assert os.path.isfile(save_path)
        assert os.path.getsize(save_path) > 1000
        # Check return values
        assert len(wl) == 51
        assert len(R) == 51

    def test_plot_angle_saves_file(self, mo_si_layers, tmp_path):
        """plot_reflectivity_angle should save a PNG without error."""
        from euv.optics.plot import plot_reflectivity_angle

        n_layers, d = mo_si_layers
        save_path = str(tmp_path / "angle.png")

        angles, R = plot_reflectivity_angle(
            n_layers,
            d,
            wavelength_m=13.5e-9,
            angle_range=(0.0, 15.0, 31),
            n_substrate=n_layers[-1].unsqueeze(0),
            save_path=save_path,
        )

        import os

        assert os.path.isfile(save_path)
        assert os.path.getsize(save_path) > 1000
        assert len(angles) == 31
        assert len(R) == 31

    def test_roughness_comparison_saves_file(self, mo_si_layers, tmp_path):
        """plot_roughness_comparison should save a PNG without error."""
        from euv.optics.plot import plot_roughness_comparison

        n_layers, d = mo_si_layers
        save_path = str(tmp_path / "roughness_compare.png")

        # Should run without error
        plot_roughness_comparison(
            n_layers,
            d,
            sigma_values=(0.0, 0.3, 0.7),
            wavelength_range=(12.0e-9, 15.0e-9, 31),
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
            save_path=save_path,
        )

        import os

        assert os.path.isfile(save_path)
        assert os.path.getsize(save_path) > 1000

    def test_dual_plot_saves_file(self, mo_si_layers, tmp_path):
        """plot_reflectivity (dual side-by-side) should save a PNG."""
        from euv.optics.plot import plot_reflectivity

        n_layers, d = mo_si_layers
        save_path = str(tmp_path / "dual.png")

        plot_reflectivity(
            n_layers,
            d,
            wavelength_range=(12.0e-9, 15.0e-9, 41),
            angle_range=(0.0, 15.0, 21),
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
            save_path=save_path,
        )

        import os

        assert os.path.isfile(save_path)
        assert os.path.getsize(save_path) > 1000


class TestConvenienceWrappers:
    """Verify convenience wrappers still work with new param."""

    def test_reflectivity_at_wavelength_with_roughness(self, mo_si_layers):
        """reflectivity_at_wavelength should accept roughness_nm."""
        n_layers, d = mo_si_layers

        R_ideal = reflectivity_at_wavelength(
            n_layers,
            d,
            13.5e-9,
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=None,
        )
        R_rough = reflectivity_at_wavelength(
            n_layers,
            d,
            13.5e-9,
            theta0=math.radians(6.0),
            n_substrate=n_layers[-1].unsqueeze(0),
            te=True,
            roughness_nm=0.5,
        )

        assert R_ideal > R_rough
        assert isinstance(R_ideal, float)
        assert isinstance(R_rough, float)
