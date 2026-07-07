"""Tests for the constants module — physical and EUV constants."""

from math import isclose

from euv.constants import (
    AVOGADRO,
    BOLTZMANN,
    BOLTZMANN_EV,
    CLASSICAL_ELECTRON_RADIUS,
    DEMAGNIFICATION,
    ELECTRON_MASS,
    ELECTRON_VOLT,
    ELEMENTARY_CHARGE,
    EUV_ANGLE_DEG,
    EUV_ANGLE_RAD,
    EUV_BANDWIDTH_EV,
    EUV_ENERGY_EV,
    EUV_WAVELENGTH_M,
    EUV_WAVELENGTH_NM,
    NA_HIGH,
    NA_LOW,
    PLANCK_CONSTANT,
    PLANCK_EV,
    REDUCED_PLANCK,
    SPEED_OF_LIGHT,
    J_to_eV,
    eV_to_J,
    eV_to_nm,
    nm_to_eV,
)


class TestFundamentalConstants:
    """Verify CODATA 2018 values."""

    def test_speed_of_light(self):
        assert SPEED_OF_LIGHT == 299_792_458

    def test_planck_constant(self):
        """H = 6.62607015e-34 J·s (exact in SI 2019)."""
        assert PLANCK_CONSTANT == 6.62607015e-34

    def test_planck_ev(self):
        """H = 4.135667696e-15 eV·s."""
        assert isclose(PLANCK_EV, 4.135667696e-15, rel_tol=1e-12)

    def test_reduced_planck(self):
        """ħ = h / 2π ~ 1.054571817e-34."""
        expected = PLANCK_CONSTANT / (2 * 3.141592653589793)
        assert isclose(REDUCED_PLANCK, expected, rel_tol=1e-15)

    def test_electron_charge(self):
        """E = 1.602176634e-19 C (exact in SI 2019)."""
        assert ELEMENTARY_CHARGE == 1.602176634e-19

    def test_electron_volt(self):
        assert ELECTRON_VOLT == ELEMENTARY_CHARGE

    def test_electron_mass(self):
        assert isclose(ELECTRON_MASS, 9.1093837015e-31, rel_tol=1e-12)

    def test_avogadro(self):
        assert isclose(AVOGADRO, 6.02214076e23, rel_tol=1e-12)

    def test_boltzmann(self):
        assert isclose(BOLTZMANN, 1.380649e-23, rel_tol=1e-12)
        assert isclose(BOLTZMANN_EV, 8.617333262e-5, rel_tol=1e-10)

    def test_classical_electron_radius(self):
        assert isclose(CLASSICAL_ELECTRON_RADIUS, 2.8179403262e-15, rel_tol=1e-12)


class TestEUVConstants:
    """Verify EUV-specific parameters."""

    def test_euv_wavelength_exact(self):
        assert EUV_WAVELENGTH_NM == 13.5

    def test_euv_wavelength_m(self):
        assert EUV_WAVELENGTH_M == 13.5e-9

    def test_euv_energy(self):
        assert isclose(EUV_ENERGY_EV, 91.84, rel_tol=1e-3)

    def test_euv_bandwidth(self):
        assert EUV_BANDWIDTH_EV == 1.84

    def test_na_low(self):
        assert NA_LOW == 0.33

    def test_na_high(self):
        assert NA_HIGH == 0.55

    def test_demagnification(self):
        assert DEMAGNIFICATION == 4.0

    def test_angle_deg_to_rad(self):
        """6° should be ~0.10472 rad."""
        expected_rad = 6.0 * 3.141592653589793 / 180.0
        assert EUV_ANGLE_DEG == 6.0
        assert isclose(EUV_ANGLE_RAD, expected_rad, rel_tol=1e-12)
        assert isclose(EUV_ANGLE_RAD, 0.10471975511965977, rel_tol=1e-12)


class TestConversions:
    """Verify energy/wavelength conversion helpers."""

    def test_eV_to_J(self):
        """1 eV = 1.602176634e-19 J."""
        assert isclose(eV_to_J(1.0), 1.602176634e-19, rel_tol=1e-12)

    def test_J_to_eV(self):
        """1 J = 6.2415...e18 eV."""
        assert isclose(J_to_eV(1.0), 6.241509074460763e18, rel_tol=1e-6)

    def test_roundtrip_eV_J(self):
        for val in [1.0, 91.84, 1000.0, 0.001]:
            assert isclose(J_to_eV(eV_to_J(val)), val, rel_tol=1e-12)

    def test_nm_to_eV_known(self):
        """13.5 nm → ~91.84 eV."""
        energy = nm_to_eV(13.5)
        assert isclose(energy, 91.84, rel_tol=1e-3)

    def test_eV_to_nm_known(self):
        """91.84 eV → ~13.5 nm."""
        wl = eV_to_nm(91.84)
        assert isclose(wl, 13.5, rel_tol=1e-2)

    def test_roundtrip_nm_eV(self):
        for wl in [10.0, 13.5, 100.0, 500.0]:
            assert isclose(eV_to_nm(nm_to_eV(wl)), wl, rel_tol=1e-10)

    def test_euv_energy_wavelength_consistent(self):
        """E = hc/λ should be self-consistent at 13.5 nm."""
        wl = eV_to_nm(EUV_ENERGY_EV)
        assert isclose(wl, EUV_WAVELENGTH_NM, rel_tol=1e-2)
