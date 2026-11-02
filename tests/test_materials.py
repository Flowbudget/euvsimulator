"""Tests for the CXRO/Henke material database loader."""

import math
from pathlib import Path

import numpy as np
import pytest

from euvsimulator.materials import CXROTable, Material, get_cxro_table

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
        from euvsimulator.materials import CXROTable

        data_dir = CXROTable()._data_dir
        assert data_dir.is_dir(), (
            f"CXRO data directory not found at {data_dir}. "
            "Run ``python scripts/download_cxro.py`` first."
        )

    def test_all_92_elements_available(self, table):
        """All Z=1..92 elements should have CSVs."""
        elements = table.list_elements()
        assert len(elements) >= 90, f"Expected ~92 elements, got {len(elements)}"
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
    def test_refractive_index_13_5nm(self, table, elem, expected_n_range, expected_k_range):
        """n,k at 13.5 nm should match known reference ranges."""
        n, k = table.refractive_index(elem, 91.84)

        n_lo, n_hi = expected_n_range
        assert n_lo <= n <= n_hi, f"{elem} @ 91.84 eV: n={n:.6f} ∉ [{n_lo}, {n_hi}]"

        k_lo, k_hi = expected_k_range
        assert k_lo <= k <= k_hi, f"{elem} @ 91.84 eV: k={k:.6f} ∉ [{k_lo}, {k_hi}]"

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


def test_energy_below_first_f1_point_raises(table):
    """Below the first tabulated f1 point CXRO has no f1; this used to give n = NaN.

    Measured before the fix (2026-10-02): get_f1f2("Si", 20.0) -> (nan, 0.9648),
    refractive_index("Si", 20.0) -> (nan, 0.0831), Mo at 15 eV and Si at 28.9 eV
    likewise. The first tabulated f1 point is 29.3 eV for Si and 19.2 eV for Mo.
    """
    for symbol, energy in [("Si", 20.0), ("Si", 29.2989), ("Mo", 15.0)]:
        with pytest.raises(ValueError, match="below the tabulated f1 range"):
            table.get_f1f2(symbol, energy)
        with pytest.raises(ValueError, match="below the tabulated f1 range"):
            table.refractive_index(symbol, energy)


def test_f1_unchanged_from_first_tabulated_point_on(table):
    """At and above the first f1 point the values are finite and as before the fix."""
    f1, f2 = table.get_f1f2("Si", 29.3)  # CSV row 29.3,3.83398,0.371742 (CXRO 2026-08)
    assert f1 == pytest.approx(3.83398, rel=1e-12)
    assert f2 == pytest.approx(0.371742, rel=1e-9)
    assert table.get_f1f2("Mo", 19.2) == pytest.approx((5.20954, 8.31758), rel=1e-12)
    n, k = table.refractive_index("Si", 29.5)
    # was 0.8487083495280365 / 0.014732206966129473 (CXRO 2026-03)
    assert n == pytest.approx(0.8487010581360201, rel=1e-12)
    assert k == pytest.approx(0.014731929907635848, rel=1e-12)


def test_get_f2_covers_the_whole_table(table):
    """get_f2 needs no f1, so it keeps working below the first f1 point."""
    # was 0.9648037510340106 (CXRO 2026-03)
    assert table.get_f2("Si", 20.0) == pytest.approx(0.9647863954504623, rel=1e-12)
    assert table.get_f2("Si", 91.84) == table.get_f1f2("Si", 91.84)[1]
    with pytest.raises(ValueError, match="outside CXRO range"):
        table.get_f2("Mo", 1e6)


def test_bromine_uses_the_liquid_density(table):
    """Br was stored as 3.12e-3 g/cm3 (gas scale) although labelled liquid.

    Measured before the fix (2026-10-02): refractive_index("Br", 91.84) =
    (0.99999352, 5.876e-6). With 3.12 g/cm3 delta and k are 1000x larger.
    """
    assert table._element_info("Br")[2] == pytest.approx(3.12)
    n, k = table.refractive_index("Br", 91.84)
    assert (n, k) == table.refractive_index("Br", 91.84, density_g_cm3=3.12)
    assert 1.0 - n == pytest.approx(6.4764e-3, rel=1e-4)
    assert k == pytest.approx(5.8756e-3, rel=1e-4)


# ──────────────────────────────────────────────
# A26: Si K edge and table ordering
# ──────────────────────────────────────────────

_CXRO_DIR = Path(CXROTable()._data_dir)


def test_every_cxro_table_has_non_decreasing_energies():
    """np.interp silently mis-interpolates a falling energy column."""
    for csv_path in sorted(_CXRO_DIR.glob("*.csv")):
        energies = np.loadtxt(csv_path, delimiter=",", skiprows=1, usecols=0)
        assert np.all(np.diff(energies) >= 0), csv_path.name


def test_si_k_edge_matches_cxro_2026_08_release(table):
    """Si.csv is the CXRO release of 2026-08-11 (si.nff rows 579-581).

    The release before it had 1838.8, 1839.0, 1838.9 eV at the K edge, with
    the 1838.9 eV row out of order.
    """
    assert table.get_f1f2("Si", 1838.80) == pytest.approx((2.81266, 0.366838), rel=1e-12)
    assert table.get_f1f2("Si", 1839.0) == pytest.approx((2.81448, 4.15734), rel=1e-12)
    assert table.get_f1f2("Si", 1843.45) == pytest.approx((7.44375, 4.14337), rel=1e-12)


def test_loader_rejects_a_falling_energy(tmp_path):
    (tmp_path / "Xx.csv").write_text(
        "energy_eV,f1,f2\n1838.8,2.82,0.367\n1839.0,2.82,2.27\n1838.9,7.97,4.16\n"
    )
    with pytest.raises(ValueError, match="not sorted by energy"):
        CXROTable(data_dir=tmp_path).get_f2("Xx", 1838.85)
