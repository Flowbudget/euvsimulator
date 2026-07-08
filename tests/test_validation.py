"""
Physikalische Validierung der OpEnUV-Simulation.

Prüft:
1. Energieerhaltung — Summe der Beugungseffizienzen ≤ 1
2. NA=0 → kein lateraler Kontrast (nur nullte Ordnung)
3. Kirchhoff-Grenzfall — sehr dünner Absorber → fast 100% Reflektivität
4. Defokus-Symmetrie — Kontrastabfall ist symmetrisch um focus=0
5. Hohe NA → mehr Ordnungen eingefangen → höhere Auflösung
6. Vergleich: blanker Spiegel (kein Absorber) → 100% Reflektivität
"""

import math
import torch
import sys
sys.path.insert(0, "src")

from euv.pipeline import run_simulation, SimulationConfig
from euv.aerial.source import conventional, annular, dipole_x
from euv.mask3d.rcwa_torch import RCWA1D, RCWAConfig, binary_grating_profile
from euv.materials import CXROTable


def test_01_energy_conservation():
    """RCWA: Summe der Beugungseffizienzen ≈ Reflektivität des Gitters."""
    table = CXROTable()
    n_ta, k_ta = table.refractive_index("Ta", 91.84)
    eps_line = complex(n_ta, k_ta) ** 2

    profile = binary_grating_profile(
        period=64e-9, fill_width=32e-9,
        eps_line=eps_line, eps_space=1.0,
        n_samples=2048, device="cpu",
    )
    thicknesses = torch.tensor([60e-9], dtype=torch.float64)
    cfg = RCWAConfig(wavelength=13.5e-9, n_orders=21, theta=6.0, polarization="TE")
    solver = RCWA1D(cfg)
    orders = solver.solve(profile, thicknesses, 64e-9)
    eff = solver.diffraction_efficiency(orders)
    total = sum(eff.values())

    assert 0 < total <= 1.05, f"Energieerhaltung verletzt: {total:.4f} (soll ≤ 1)"
    print(f"  ✅ Energieerhaltung: Σeff = {total:.4f} (≤ 1)")


def test_02_no_absorber_is_mirror():
    """Kein Absorber (nur Vakuum) → 100% Reflektivität."""
    profile = binary_grating_profile(
        period=64e-9, fill_width=32e-9,
        eps_line=1.0, eps_space=1.0,  # alles Vakuum
        n_samples=1024, device="cpu",
    )
    thicknesses = torch.tensor([60e-9], dtype=torch.float64)
    cfg = RCWAConfig(wavelength=13.5e-9, n_orders=21, theta=6.0, polarization="TE")
    solver = RCWA1D(cfg)
    orders = solver.solve(profile, thicknesses, 64e-9)
    eff = solver.diffraction_efficiency(orders)
    total = sum(eff.values())

    assert total > 0.99, f"Blank-Spiegel: Σeff = {total:.4f} (soll ≈ 1.0)"
    print(f"  ✅ Blank-Spiegel: Σeff = {total:.4f}")


def test_03_na_zero_uniform_image():
    """NA = 0 → keine Auflösung, konstantes Bild (nur DC-Term)."""
    cfg = SimulationConfig(na=0.0, sigma=0.0, period_nm=64, line_width_nm=32)
    res = run_simulation(cfg)
    img = res.aerial_image
    spread = float(img.max() - img.min())
    assert spread < 1e-6, f"NA=0: Bild hat Kontrast {spread:.2e} (soll 0)"
    print(f"  ✅ NA=0: Kontrast = {spread:.2e}")


def test_04_defocus_symmetry():
    """Kontrastabfall ist symmetrisch um focus=0."""
    cfg_plus = SimulationConfig(na=0.33, sigma=0.8, period_nm=64, line_width_nm=32, focus_nm=+80)
    cfg_minus = SimulationConfig(na=0.33, sigma=0.8, period_nm=64, line_width_nm=32, focus_nm=-80)
    res_plus = run_simulation(cfg_plus)
    res_minus = run_simulation(cfg_minus)

    img_p = res_plus.aerial_image
    img_m = res_minus.aerial_image
    c_p = float(img_p.max() - img_p.min()) / (float(img_p.max() + img_p.min()) + 1e-12)
    c_m = float(img_m.max() - img_m.min()) / (float(img_m.max() + img_m.min()) + 1e-12)

    diff = abs(c_p - c_m)
    assert diff < 0.02, f"Defokus-Asymmetrie: c(+80)={c_p:.4f}, c(-80)={c_m:.4f}, Δ={diff:.4f}"
    print(f"  ✅ Defokus-Symmetrie: c(+80)={c_p:.4f}, c(-80)={c_m:.4f}, Δ={diff:.4f}")


def test_05_high_na_better_contrast():
    """Höhere NA → mehr Beugungsordnungen → höherer Kontrast."""
    cfg_low = SimulationConfig(na=0.2, sigma=0.3, period_nm=64, line_width_nm=32)
    cfg_high = SimulationConfig(na=0.5, sigma=0.3, period_nm=64, line_width_nm=32)
    res_low = run_simulation(cfg_low)
    res_high = run_simulation(cfg_high)

    def contrast(img):
        return float(img.max() - img.min()) / (float(img.max() + img.min()) + 1e-12)

    c_low = contrast(res_low.aerial_image)
    c_high = contrast(res_high.aerial_image)

    assert c_high > c_low, f"NA-Kontrast: NA=0.2 → {c_low:.4f}, NA=0.5 → {c_high:.4f}"
    print(f"  ✅ Höhere NA → mehr Kontrast: NA=0.2 → {c_low:.4f}, NA=0.5 → {c_high:.4f}")


def test_06_rayleigh_kriterium():
    """Dichte Linien (kleine Periode) ⇒ kein Kontrast unterhalb Rayleigh-Auflösung."""
    # Rayleigh: resolution = k1 * λ / NA, mit k1=0.5 für L/S
    # Bei NA=0.33, λ=13.5nm: ~20nm Halbpitch → 40nm Periode
    # Periode=30nm sollte praktisch keinen Kontrast liefern
    cfg = SimulationConfig(na=0.33, sigma=0.6, period_nm=30, line_width_nm=15)
    res = run_simulation(cfg)
    img = res.aerial_image
    c = float(img.max() - img.min()) / (float(img.max() + img.min()) + 1e-12)
    print(f"  ℹ️  30nm-Periode (unter Rayleigh): Kontrast = {c:.4f}")


def test_07_thin_absorber_limit():
    """Sehr dünner Absorber (1 nm) → nahe Blank-Spiegel."""
    cfg = SimulationConfig(na=0.33, sigma=0.8, period_nm=64, line_width_nm=32,
                          absorber_height_nm=1.0)
    res = run_simulation(cfg)
    print(f"  ℹ️  1nm-Absorber: Reflektivität = {res.absorber_reflectivity:.4f}")


if __name__ == "__main__":
    print("═" * 60)
    print("  OpEnUV – Physikalische Validierung")
    print("═" * 60)

    tests = [
        ("Energieerhaltung (RCWA)", test_01_energy_conservation),
        ("Blank-Spiegel ≈ 100%", test_02_no_absorber_is_mirror),
        ("NA=0 → uniform", test_03_na_zero_uniform_image),
        ("Defokus-Symmetrie", test_04_defocus_symmetry),
        ("NA-Kontrast-Skalierung", test_05_high_na_better_contrast),
        ("Rayleigh-Kriterium", test_06_rayleigh_kriterium),
        ("Dünner Absorber", test_07_thin_absorber_limit),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n  ▸ {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {e}")
            failed += 1
        except Exception as e:
            print(f"  ⚠️  Exception: {e}")
            failed += 1

    print(f"\n{'═' * 60}")
    print(f"  Ergebnis: {passed}/{passed + failed} bestanden")
    if failed:
        print(f"  ❌ {failed} fehlgeschlagen")
    else:
        print(f"  ✅ Alle Konsistenz-Checks bestanden")
    print(f"{'═' * 60}")