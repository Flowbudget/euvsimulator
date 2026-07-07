"""Tests for the CXRO/Henke material database loader."""

import math
from pathlib import Path

import numpy as np
import pytest

from euv.materials import CXROTable, Material, get_cxro_table


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def table() -> CXROTable:
    """Shared CXRO table — loads CSVs once per module."""
    return CXROTable()


# ──────────────────────────────────────────────
# Test: CXRO data presence
# ──────────────────────────────────────────────


class TestCXRODataPresence:
    """Verify CXRO data is downloaded and accessible."""

    def test_cxro_directory_exists(self):
        """data/cxro/ must exist with CSVs."""
        data_dir = (
            Path(__file__).resolve().parent.parent / "data" / "cxro"
        )
        assert data_dir.is_dir(), (
            f"CXRO data directory not found at {data_dir}. "
            "Run ``python scripts/download_cxro.py`` first."
        )

    def test_all_92_elements_available(self, table):
        """All Z=1..92 elements should have CSVs."""
        elements = table.list_elements()
        assert len(elements) >= 90, (
            f"Expected ~92 elements, got {len(elements)}"
        )
        for core in ["Mo", "Si", "Ru", "Ta", "Sn"]:
            assert core in elements, f"Missing core element {core}"

    def test_core_elements_have_f1f2_data(self, table):
        """Core EUV materials should have valid f1,f2 at 91.84 eV."""
        for elem in ["Mo", "Si", "Ru"]:
            f1, f2 = table.get_f1f2(elem, 91.84)
            assert np.isfinite(f1), f"{elem}: f1={f1} not finite"
            assert np.isfinite(f2), f"{elem}: f2={f2} not finite"
            assert f2 > 0, f"{elem}: f2={f2} must be > 0"


class TestCXRORefractiveIndex:
    """Verify refractive index computation from CXRO data."""

    @pytest.mark.parametrize(
        "elem, expected_n_range, expected_k_range",
        [
            ("Mo", (0.90, 0.95), (0.005, 0.01)),
            ("Si", (0.99, 1.01), (0.001, 0.003)),
            ("Ru", (0.87, 0.90), (0.015, 0.02)),
            ("Ta", (0.93, 0.96), (0.03, 0.05)),
            ("Sn", (0.93, 0.96), (0.04, 0.10)),
        ],
    )
    def test_refractive_index_13_5nm(
        self, table, elem, expected_n_range, expected_k_range
    ):
        """n,k at 13.5 nm should match known reference ranges."""
        n, k = table.refractive_index(elem, 91.84)

        n_lo, n_hi = expected_n_range
        assert n_lo <= n <= n_hi, (
            f"{elem} @ 91.84 eV: n={n:.6f} ∉ [{n_lo}, {n_hi}]"
        )

        k_lo, k_hi = expected_k_range
        assert k_lo <= k <= k_hi, (
            f"{elem} @ 91.84 eV: k={k:.6f} ∉ [{k_lo}, {k_hi}]"
        )

    def test_refractive_index_monotonic_f2(self, table):
        """f2 should be > 0 for all elements at EUV energy."""
        for elem in ["Mo", "Si", "Ru", "Ta", "Sn", "C", "Au", "Ni"]:
            _, k = table.refractive_index(elem, 91.84)
            assert k > 0, f"{elem}: k={k} (must be positive at EUV)"
            assert k < 1, f"{elem}: k={k} (unrealistically large)"

    def test_refractive_index_near_unity_for_light(self, table):
        """Light elements (Be, C) have n close to 1 at EUV."""
        for elem in ["Be", "C", "B"]:
            n, k = table.refractive_index(elem, 91.84)
            assert 0.95 <= n <= 1.0, f"{elem}: n={n} outside [0.95, 1.0]"


class TestCXROErrors:
    """Verify error handling."""

    def test_missing_element(self, table):
        """Non-existent elements should raise KeyError."""
        with pytest.raises(KeyError, match="Unknown element"):
            table.refractive_index("Xz")

    def test_out_of_energy_range(self, table):
        """Energy outside CXRO table range should raise."""
        with pytest.raises(ValueError, match="outside CXRO range"):
            table.get_f1f2("Mo", 1e6)  # 1 MeV — far above 30 keV max

    def test_singleton_is_cxro_table(self):
        """get_cxro_table() should return a CXROTable."""
        singleton = get_cxro_table()
        assert isinstance(singleton, CXROTable)


class TestMaterialDataclass:
    """Verify the Material dataclass properties."""

    def test_material_basic(self):
        m = Material(symbol="Mo", energy_eV=91.84, n=0.9238, k=0.00637, density=10.28)
        assert m.symbol == "Mo"
        assert m.energy_eV == 91.84
        assert m.n == 0.9238
        assert m.k == 0.00637
        assert m.density == 10.28

    def test_wavelength_property(self):
        m = Material(symbol="Si", energy_eV=91.84, n=0.999, k=0.00183, density=2.33)
        assert m.wavelength_nm == pytest.approx(13.5, rel=1e-2)

    def test_epsilon(self):
        m = Material(symbol="Mo", energy_eV=91.84, n=0.9238, k=0.00637, density=10.28)
        expected = complex(0.9238, 0.00637) ** 2
        assert m.epsilon == expected

    def test_delta(self):
        m = Material(symbol="Si", energy_eV=91.84, n=0.999, k=0.00183, density=2.33)
        assert m.delta == pytest.approx(0.001, abs=1e-6)

    def test_absorption_length(self):
        """SiO2: k~0.010 → absorption length ~ 107 nm at 13.5 nm."""
        m = Material(symbol="SiO2", energy_eV=91.84, n=0.98, k=0.010, density=2.65)
        expected = 13.5 / (4 * math.pi * 0.010)
        assert m.absorption_length_nm == pytest.approx(expected, rel=1e-3)

    def test_get_material_from_table(self, table):
        """CXROTable.get_material() should build a Material with valid n,k."""
        m = table.get_material("Si", 91.84)
        assert isinstance(m, Material)
        assert m.symbol == "Si"
        assert 0.99 < m.n < 1.01
        assert 0.0 < m.k < 0.005
        assert m.density > 0