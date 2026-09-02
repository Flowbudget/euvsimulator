#!/usr/bin/env python3
"""STEP 5.3F — READ-ONLY: A1≡A2-Äquivalenz, Varianz/Kovarianz vs Theorie."""
import numpy as np
import torch
from euvsimulator.constants import HC_EV_NM
from euvsimulator.resist.exposure import gaussian_se_blur
from euvsimulator.resist.stochastic import photon_deposition_shot_noise

E_PH = HC_EV_NM / 13.5
F = 6.241509074e15


def build(dose, se, dx, seed0=2000, n_seeds=60, edge=True):
    H, W = 256, 256
    dm = torch.full((H, W), dose, dtype=torch.float32)
    if edge:
        dm[:, : W // 2] = 0.5
    A = dx * dx * 1e-14
    n_bar = dm * A * F / E_PH
    blur_dose = gaussian_se_blur(dm, sigma=se, dx=dx)
    e_bar = gaussian_se_blur(n_bar, sigma=se, dx=dx)
    a1 = torch.zeros_like(dm)
    a2 = torch.zeros_like(dm)
    diff = 0.0
    for s in range(n_seeds):
        rng = torch.Generator().manual_seed(seed0 + s)
        d_eff = photon_deposition_shot_noise(dm, se, dx_nm=dx, photon_energy_eV=E_PH,
                                             dose_to_energy_factor=F, rng=rng)
        # d_eff = dose*e_dep/e_bar  ->  e_dep/e_bar = d_eff/dose
        ratio = d_eff / dm.clamp(min=1e-12)
        d1 = blur_dose * ratio           # A1
        # A2: e_dep * E_ph/(A*f)  mit e_dep = e_bar*ratio
        d2 = e_bar * ratio * (E_PH / (A * F))
        a1 += d1
        a2 += d2
        diff = max(diff, float((d1 - d2).abs().max()))
    a1 /= n_seeds
    a2 /= n_seeds
    return a1, a2, diff, dm, blur_dose, e_bar


def cov_row(field, r):
    """Kovarianz entlang x in Zeile 128 (Spaltenpaare im Abstand r)."""
    row = field[128]
    x = row - row.mean()
    n = len(row) - r
    return float((x[:n] * x[r:]).mean())


print("=" * 90)
print("1. A1 vs A2 — ALGEBRAISCHE IDENTITÄT (max|diff| über 60 Seeds)")
print("=" * 90)
for (dose, se) in [(40, 5.0), (20, 5.0), (10, 2.0), (5, 8.0)]:
    a1, a2, diff, *_ = build(dose, se, 0.25)
    rel = diff / max(float(a1.abs().max()), 1e-12)
    print(f"  dose={dose:3.0f} se={se:3.0f}: max|A1-A2| = {diff:.3e}  (relativ {rel:.2e})")

print()
print("=" * 90)
print("2. FIRST MOMENT: R(x) = E[d_eff]/blur(dose)  (homogen + Kante)")
print("=" * 90)
for (dose, se) in [(40, 5.0), (20, 5.0), (10, 5.0)]:
    a1, a2, _, dm, blur_dose, e_bar = build(dose, se, 0.25)
    R_hom = float((a1 / blur_dose.clamp(min=1e-12))[128, 60].mean())
    # Kante: Mittel über Spalten 100-150 (Übergangszone), gewichtet
    zone = slice(100, 160)
    R_zone = float((a1[128, zone] / blur_dose[128, zone].clamp(min=1e-12)).mean())
    print(f"  dose={dose:3.0f} se={se:3.0f}: R(homogen)={R_hom:.4f}  R(Kantenzone)={R_zone:.4f}")

print()
print("=" * 90)
print("3. SECOND MOMENT: Var[d_eff] vs Theorie (E_ph/(A*f))²·Σh²·n_bar")
print("=" * 90)
for (dose, se) in [(40, 5.0), (20, 5.0), (10, 5.0)]:
    a1, a2, _, dm, blur_dose, e_bar = build(dose, se, 0.25, n_seeds=120)
    # Empirische Varianz (homogene Region, Spalten 20-100)
    rng = torch.Generator().manual_seed(2000)
    n_bar = dm * 0.0625 * 1e-14 * F / E_PH
    A = 0.0625 * 1e-14
    d_effs = []
    for s in range(120):
        rng = torch.Generator().manual_seed(2000 + s)
        d_eff = photon_deposition_shot_noise(dm, se, dx_nm=0.25, photon_energy_eV=E_PH,
                                             dose_to_energy_factor=F, rng=rng)
        d_effs.append(d_eff[128, 20:100])
    d_effs = torch.stack(d_effs)
    var_emp = float(d_effs.var(dim=0).mean())
    # Theorie: (E_ph/(A*f))² * Σh²*n_bar  (homogen: Σh²*n_bar an Spalte 60)
    # Σh² der diskreten 2D-Faltung: aus dem Kernel ableiten
    # numerisch: Var[d_eff] = (E_ph/(A*f))² * Σ_j h_j² * n_bar_j
    # nutze: rel.Var = Var/dose² = Σh²/n_bar -> Σh² = rel.Var*n_bar messen
    rel_var = var_emp / dose**2
    n_bar_h = float(n_bar[128, 60])
    sh2_emp = rel_var * n_bar_h
    # theoretisches Σh² für separierbaren 2D-Gauß σ_px: (Σh_x²)²
    sigma_px = se / 0.25
    x = torch.arange(-int(3 * sigma_px), int(3 * sigma_px) + 1, dtype=torch.float64)
    k1 = torch.exp(-0.5 * (x / sigma_px) ** 2)
    k1 = k1 / k1.sum()
    sh2_theory = float((k1**2).sum() ** 2)
    print(f"  dose={dose:3.0f} se={se:3.0f}: rel.Var={rel_var:.6f}  Σh²(emp)={sh2_emp:.3e}  Σh²(theorie)={sh2_theory:.3e}  Verhältnis={sh2_emp/sh2_theory:.3f}")

print()
print("=" * 90)
print("4. KOVARIANZ: Cov(r) vs exp(-r²/(4σ²))  (√2σ-Korrelationslänge)")
print("=" * 90)
for se in [2.0, 5.0]:
    a1, a2, _, dm, blur_dose, e_bar = build(40, se, 0.25, n_seeds=120)
    rng = torch.Generator().manual_seed(2000)
    d_effs = []
    for s in range(120):
        rng = torch.Generator().manual_seed(2000 + s)
        d_eff = photon_deposition_shot_noise(dm, se, dx_nm=0.25, photon_energy_eV=E_PH,
                                             dose_to_energy_factor=F, rng=rng)
        d_effs.append(d_eff[128, 20:100])
    d_effs = torch.stack(d_effs)  # (120, 80)
    x = d_effs - d_effs.mean(dim=0, keepdim=True)
    c0 = float((x * x).mean())
    sigma_px = se / 0.25
    print(f"  se={se} (σ_px={sigma_px:.0f}): r=1: {float((x[:, :-1]*x[:, 1:]).mean())/c0:.4f} "
          f"(theorie exp(-1/(4σ²))={np.exp(-1/(4*sigma_px**2)):.4f})")
    for r_px in [sigma_px, np.sqrt(2)*sigma_px, 2*sigma_px]:
        rr = int(r_px)
        emp = float((x[:, :-rr]*x[:, rr:]).mean())/c0
        th = np.exp(-(rr**2)/(4*sigma_px**2))
        print(f"    r={rr:3d} px: emp={emp:.4f}  theorie(√2σ)={th:.4f}")

print()
print("=" * 90)
print("5. SE-SKALIERUNG + DOSIS: Kantenposition det vs A1 (Mittel)")
print("=" * 90)
def edge_pos(a):
    row = a[128].numpy()
    under = np.argmax(row < 0.3) if (row < 0.3).any() else len(row)
    i = under
    if 0 < i < len(row):
        x0, x1 = row[i-1], row[i]
        return (i-1) + (0.3 - x1)/(x0 - x1) if x1 != x0 else float(i)
    return float('nan')
from euvsimulator.resist.exposure import dose_to_acid
for se in [2.0, 5.0, 8.0]:
    for dose in [10.0, 20.0, 40.0]:
        a1, a2, _, dm, blur_dose, e_bar = build(dose, se, 0.25, n_seeds=60)
        acid_det = dose_to_acid(blur_dose, C=0.05, Q=1.0, apply_blur=False)
        acid_a1 = dose_to_acid(a1, C=0.05, Q=1.0, apply_blur=False)
        p_det, p_a1 = edge_pos(acid_det), edge_pos(acid_a1)
        print(f"  dose={dose:3.0f} se={se:3.0f}: x_det={p_det:7.2f}  x_A1={p_a1:7.2f}  Δ={p_det-p_a1:+.3f} nm")

print()
print("=" * 90)
print("6. GRID-INVARIANZ der relativen Varianz (dx=0.25 vs 0.5)")
print("=" * 90)
for dx in [0.25, 0.5]:
    dm = torch.full((256, 256), 40.0, dtype=torch.float32)
    rng = torch.Generator().manual_seed(2000)
    d_effs = []
    for s in range(120):
        rng = torch.Generator().manual_seed(2000 + s)
        d_eff = photon_deposition_shot_noise(dm, 5.0, dx_nm=dx, photon_energy_eV=E_PH,
                                             dose_to_energy_factor=F, rng=rng)
        d_effs.append(d_eff[128, 20:100])
    d_effs = torch.stack(d_effs)
    var = float(d_effs.var(dim=0).mean())
    print(f"  dx={dx}: rel.Var = {var/1600:.6f}")
