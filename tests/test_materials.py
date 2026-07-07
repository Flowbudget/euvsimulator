"""Tests for the optics module — materials database."""

import numpy as np
import pytest

from euv.optics import (
    MATERIALS,
    refractive_index,
    multilayer_permittivity,
    EUV_WAVELENGTH_NM,
)


class TestMaterials:
    """Verify refractive indices and constants."""

    def test_material_count(self):
        """At least the core EUV materials exist."""
        core = {"Mo", "Si", "Ru", "Ta", "Sn"}
        assert core.issubset(MATERIALS.keys()), f"Missing: {core - MATERIALS.keys()}"

    def test_refractive_index_keyerror(self):
        """Unknown material raises KeyError."""
        with pytest.raises(KeyError):
            refractive_index("Unobtainium")

    @pytest.mark.parametrize(
        "element, expected_n_low, expected_n_high",
        [
            ("Mo", 0.92, 0.93),
            ("Si", 0.99, 1.00),
            ("Ru", 0.88, 0.89),
            ("Ta", 0.94, 0.95),
            ("Sn", 0.88, 0.89),
        ],
    )
    def test_refractive_n_bounds(self, element, expected_n_low, expected_n_high):
        """Real part n should be within expected range for EUV materials."""
        n, k = refractive_index(element)
        assert expected_n_low <= n <= expected_n_high, (
            f"{element}: n={n} outside [{expected_n_low}, {expected_n_high}]"
        )

    @pytest.mark.parametrize(
        "element, expected_k_low, expected_k_high",
        [
            ("Mo", 0.005, 0.008),
            ("Si", 0.001, 0.003),
            ("Ru", 0.015, 0.020),
            ("Ta", 0.035, 0.042),
            ("Sn", 0.028, 0.035),
        ],
    )
    def test_refractive_k_bounds(self, element, expected_k_low, expected_k_high):
        """Imaginary part k should be within expected range for EUV materials."""
        n, k = refractive_index(element)
        assert expected_k_low <= k <= expected_k_high, (
            f"{element}: k={k} outside [{expected_k_low}, {expected_k_high}]"
        )

    def test_multilayer_permittivity(self):
        """Mo/Si bilayer permittivity should be reasonable."""
        eps_array = multilayer_permittivity(
            ["Mo", "Si"],
            [2.8, 4.2],  # typical Mo/Si pair thicknesses
        )
        assert eps_array.shape == (2,)
        assert np.all(np.abs(eps_array) > 0)

    def test_refractive_indices_complex_pair(self):
        """Each material should have n>0 and k>0 at EUV wavelength."""
        for name, mat in MATERIALS.items():
            assert mat.n > 0, f"{name}: n={mat.n} (should be >0)"
            assert mat.k >= 0, f"{name}: k={mat.k} (should be >=0)"

    def test_euv_wavelength(self):
        """EUV wavelength constant should be exactly 13.5 nm."""
        assert EUV_WAVELENGTH_NM == 13.5
