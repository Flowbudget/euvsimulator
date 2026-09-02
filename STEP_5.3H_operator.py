#!/usr/bin/env python3
"""STEP 5.3H — READ-ONLY: Operator-Identität empirisch."""
import numpy as np
import torch
from euvsimulator.constants import HC_EV_NM
from euvsimulator.resist.exposure import gaussian_se_blur
from euvsimulator.resist.stochastic import photon_deposition_shot_noise

E_PH = HC_EV_NM / 13.5
F = 6.241509074e15


def H(img, se, dx=0.25):
    return gaussian_se_blur(img, sigma=se, dx=dx)


print("=" * 90)
print("1. LINEARITÄT + SKALENIDENTITÄT: H(dose·s) vs H(dose)·s  (Ränder, Größen)")
print("=" * 90)
for (Hsz, Wsz) in [(256, 256), (64, 64), (4096, 256), (128, 32)]:
    for se in [2.0, 5.0, 8.0]:
        dose = torch.rand(Hsz, Wsz, dtype=torch.float32) * 40.0
        s = float(torch.tensor(0.0625 * 1e-14 * F / E_PH))
        a = H(dose, se) * s
        b = H(dose * s, se)
        d = float((a - b).abs().max())
        rel = d / max(float(a.abs().max()), 1e-12)
        # Ränder getrennt: 3-Pixel-Rand vs Innenraum
        edge = float((a[:3] - b[:3]).abs().max())
        print(f"  {Hsz:5d}x{Wsz:<4d} se={se:.0f}: max|H(d·s)-H(d)·s| = {d:.3e} (rel {rel:.1e})  Rand3px: {edge:.3e}")

print()
print("=" * 90)
print("2. SE=0: neuer Pfad == alter Pfad (bitweise?)")
print("=" * 90)
dm = torch.full((256, 256), 40.0, dtype=torch.float32)
dm[:, :128] = 0.5
rng1 = torch.Generator().manual_seed(7)
d_eff_alt = photon_deposition_shot_noise(dm, 0.0, dx_nm=0.25, photon_energy_eV=E_PH,
                                         dose_to_energy_factor=F, rng=rng1)
# neuer Pfad: blur_dose = H(dose, 0) — gibt dose bitweise zurück (return image)
blur_dose = gaussian_se_blur(dm, sigma=0.0, dx=0.25)
print(f"  H(dose, 0) ist dose-Objekt (bitweise): {blur_dose is dm}  |max diff| = {float((blur_dose-dm).abs().max()):.0e}")
print(f"  alte d_eff = dose·e_dep/e_bar; neue d_eff = H(dose,0)·e_dep/e_bar = exakt gleich (gleiche Formel, blur_dose is dose)")
# RNG-Reihenfolge: gaussian_se_blur ruft keinen Generator auf
print(f"  gaussian_se_blur deterministisch (kein RNG): H(dose,5) 2x -> {float((H(dm,5.0)-H(dm,5.0)).abs().max()):.0e}")

print()
print("=" * 90)
print("3. A1 vs A2 — EPSILON-REPRODUKTION (max_abs, max_rel)")
print("=" * 90)
for (dose, se) in [(40.0, 5.0), (20.0, 5.0), (10.0, 2.0), (5.0, 8.0), (40.0, 0.0)]:
    dm = torch.full((256, 256), dose, dtype=torch.float32)
    dm[:, :128] = 0.5
    A = 0.0625 * 1e-14
    n_bar = dm * A * F / E_PH
    e_bar = H(n_bar, se)
    blur_dose = H(dm, se)
    mx_abs, mx_rel = 0.0, 0.0
    for s in range(30):
        rng = torch.Generator().manual_seed(3000 + s)
        d_eff = photon_deposition_shot_noise(dm, se, dx_nm=0.25, photon_energy_eV=E_PH,
                                             dose_to_energy_factor=F, rng=rng)
        ratio = d_eff / dm.clamp(min=1e-12)
        a1 = blur_dose * ratio
        a2 = e_bar * ratio * (E_PH / (A * F))
        mx_abs = max(mx_abs, float((a1 - a2).abs().max()))
        mx_rel = max(mx_rel, float(((a1 - a2).abs() / a2.abs().clamp(min=1e-12)).max()))
    print(f"  dose={dose:4.0f} se={se:3.0f}: max_abs={mx_abs:.3e}  max_rel={mx_rel:.3e}")

print()
print("=" * 90)
print("4. DOPPEL-BLUR-PROOF (Code-Pfad): H nur einmal auf N")
print("=" * 90)
print("  e_dep = H(N)  [1 Anwendung]")
print("  d_eff = H(dose)·e_dep/e_bar ≡ e_dep·(E_ph/(A·f))  [kein H auf e_dep]")
print("  acid = dose_to_acid(d_eff, apply_blur=False)  [Code: kein Blur]")
import inspect
from euvsimulator.resist.exposure import dose_to_acid
src = inspect.getsource(dose_to_acid)
i = src.find("if apply_blur")
print(f"  dose_to_acid-Code: {src[i:i+60].strip()!r}")
# PEB-Diffusion ist separater Operator auf acid (peb.py:282) mit peb_sigma_diff
print("  PEB: gaussian_se_blur(acid, sigma=peb_sigma_diff) — SEPARATE Größe (acid),")
print("       separater Parameter (peb_sigma_diff), keine 2. Anwendung auf N")
print("  Development: dev_corr-Kernel auf developed — 3. separate Größe")

print()
print("=" * 90)
print("5. E[d_eff] = H(dose)  vs  E[acid(d_eff)] ≠ acid(H(dose)) — Jensen erhalten")
print("=" * 90)
from euvsimulator.resist.exposure import dose_to_acid
dm = torch.full((256, 256), 40.0, dtype=torch.float32)
blur_dose = H(dm, 5.0)
acc = torch.zeros_like(dm)
for s in range(80):
    rng = torch.Generator().manual_seed(4000 + s)
    d_eff = photon_deposition_shot_noise(dm, 5.0, dx_nm=0.25, photon_energy_eV=E_PH,
                                         dose_to_energy_factor=F, rng=rng)
    ratio = d_eff / dm.clamp(min=1e-12)
    acc += dose_to_acid(blur_dose * ratio, C=0.05, Q=1.0, apply_blur=False)
E_acid = acc / 80
acid_H = dose_to_acid(blur_dose, C=0.05, Q=1.0, apply_blur=False)
rel = float(((E_acid - acid_H).abs() / acid_H.clamp(min=1e-9)).mean())
print(f"  E[d_eff] = H(dose): erfüllt (5.3F, R≈1)  —  E[acid] vs acid(H(dose)): rel.Abweichung = {rel*100:.2f}% (Jensen, erwartet ≠ 0)")
