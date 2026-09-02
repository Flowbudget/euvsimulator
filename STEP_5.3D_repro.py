#!/usr/bin/env python3
"""STEP 5.3D — READ-ONLY: SE-Blur-Konsistenz, Reproduktionstest, Uniform-Test."""
import numpy as np
import torch
from euvsimulator.constants import HC_EV_NM
from euvsimulator.resist.exposure import dose_to_acid, gaussian_se_blur
from euvsimulator.resist.stochastic import photon_deposition_shot_noise

E_PH = HC_EV_NM / 13.5
F = 6.241509074e15
DX = 0.25
THR = 0.3


def run_case(dose, se, C, Q, n_seeds=40, seed0=1000):
    H, W = 256, 256
    dose_edge = torch.full((H, W), 0.5, dtype=torch.float32)
    dose_edge[:, :W // 2] = dose
    # deterministisch
    acid_det = dose_to_acid(gaussian_se_blur(dose_edge, sigma=se, dx=DX), C=C, Q=Q, apply_blur=False)
    # stochastisch (Mittel ueber Seeds)
    acc = torch.zeros_like(dose_edge)
    acc_ratio = 0.0
    for s in range(n_seeds):
        rng = torch.Generator().manual_seed(seed0 + s)
        d_eff = photon_deposition_shot_noise(dose_edge, se, dx_nm=DX, photon_energy_eV=E_PH,
                                             dose_to_energy_factor=F, rng=rng)
        acc += dose_to_acid(d_eff, C=C, Q=Q, apply_blur=False)
        # E[d_eff]/dose in heller Region (Spalte 10) und Kante (128)
        acc_ratio += float(d_eff[128, 10].mean()) / dose
    acid_stoch = acc / n_seeds
    ratio = acc_ratio / n_seeds

    def profile(a):
        row = a[128].numpy()
        return row

    def edge_and_slope(a):
        row = a[128].numpy()
        over = (row > THR)
        idx = np.argmax(~over) if (~over).any() else len(row)
        # subpixel via interpolation
        i = idx
        if 0 < i < len(row):
            x0, x1 = row[i - 1], row[i]
            pos = (i - 1) + (THR - x0) / (x1 - x0) if x1 != x0 else float(i)
        else:
            pos = float(i)
        # Transition-Width 10/50/90%
        hi = row > 0.9 * row.max() if row.max() > 0 else np.zeros_like(row, dtype=bool)
        lo = row < 0.1 * row.max()
        x_hi = np.argmax(hi) if hi.any() else len(row)
        x_lo = np.argmax(lo) if lo.any() else len(row)
        t10, t90 = min(x_hi, x_lo), max(x_hi, x_lo)
        x50 = np.argmax(row >= 0.5 * row.max()) if (row >= 0.5 * row.max()).any() else len(row)
        # max lokale Steigung (Spalten)
        slope = float(np.abs(np.diff(row)).max())
        return pos, (t90 - t10), float(x50), slope

    p_det, w_det, x50_det, s_det = edge_and_slope(acid_det)
    p_sto, w_sto, x50_sto, s_sto = edge_and_slope(acid_stoch)
    # uniforme Regionen (mittlere Energiedichte)
    acid_det_unif = dose_to_acid(gaussian_se_blur(torch.full((256, 256), dose, dtype=torch.float32), sigma=se, dx=DX), C=C, Q=Q, apply_blur=False)
    return dict(p_det=p_det, p_sto=p_sto, w_det=w_det, w_sto=w_sto, x50_det=x50_det,
                x50_sto=x50_sto, s_det=s_det, s_sto=s_sto, ratio=ratio,
                acid_ratio=float((acid_stoch[128, 10] / acid_det[128, 10]).mean()))


if __name__ == "__main__":
    print("=" * 100)
    print("B. REPRODUKTIONSTEST (dose=40, se=5, C=0.05, Q=1.0, 40 Seeds)")
    print("=" * 100)
    r = run_case(40, 5.0, 0.05, 1.0)
    for k, v in r.items():
        print(f"  {k:12s} = {v:.4f}" if isinstance(v, float) else f"  {k:12s} = {v}")
    print()
    print("C. ROBUSTHEITSMATRIX (x_det, x_stoch, Δx, Transition det/stoch, Slope-Ratio)")
    print(f"  {'dose':>5} {'se':>4} {'C':>6} {'Q':>5} | {'x_det':>8} {'x_sto':>8} {'Δx':>7} | {'Tdet':>5} {'Tsto':>5} | {'slopeR':>7} | {'E[d_eff]/d':>10}")
    for dose in [40, 20, 10, 5]:
        for se in [0, 2, 5, 8]:
            r = run_case(dose, se, 0.05, 1.0)
            print(f"  {dose:5.0f} {se:4.0f} {0.05:6.3f} {1.0:5.2f} | {r['p_det']:8.2f} {r['p_sto']:8.2f} {r['p_det']-r['p_sto']:7.2f} | {r['w_det']:5.0f} {r['w_sto']:5.0f} | {r['s_det']/max(r['s_sto'],1e-9):7.1f} | {r['ratio']:10.4f}")
    for C in [0.025, 0.10]:
        r = run_case(40, 5.0, C, 1.0)
        print(f"  {40:5.0f} {5:4.0f} {C:6.3f} {1.0:5.2f} | {r['p_det']:8.2f} {r['p_sto']:8.2f} {r['p_det']-r['p_sto']:7.2f} | {r['w_det']:5.0f} {r['w_sto']:5.0f} | {r['s_det']/max(r['s_sto'],1e-9):7.1f} | {r['ratio']:10.4f}")
    print()
    print("D. UNIFORM-DOSE TEST (E[d_eff]/dose in heller Region; acid_stoch/acid_det)")
    print(f"  {'dose':>5} {'se':>4} | {'E[d_eff]/dose':>14} {'acid_sto/det':>12}")
    for dose in [40, 20, 10, 5]:
        for se in [2, 5]:
            r = run_case(dose, se, 0.05, 1.0)
            print(f"  {dose:5.0f} {se:4.0f} | {r['ratio']:14.6f} {r['acid_ratio']:12.6f}")
