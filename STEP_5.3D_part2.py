#!/usr/bin/env python3
"""STEP 5.3D — Teil 2: Q-Sensitivität, Wrap, Silent-Cases, Dead-Config."""
import numpy as np
import torch

from euvsimulator.pipeline import SimulationConfig, run_simulation


def car_cfg(**kw):
    base = dict(resist_model="full_chem", enable_stochastic=True,
                stochastic_n_realisations=1, stochastic_seed=42, se_blur_nm=5.0)
    base.update(kw)
    return SimulationConfig(**base)


print("G. DILL-Q SENSITIVITY (Referenz: dose=40, se=5, C=0.05, 3 Seeds Mittel)")
for Q in [0.01, 0.04, 0.1, 0.5, 1.0]:
    cds, lers, lwrs = [], [], []
    for s in range(3):
        r = run_simulation(car_cfg(dill_Q=Q, stochastic_seed=90000 + s))
        cds.append(r.cd_nm); lers.append(r.ler_nm); lwrs.append(r.lwr_nm)
    print(f"  Q={Q:5.2f}: CD={np.mean(cds):7.2f} nm  NILS={r.nils_value:6.2f}  "
          f"LER={np.mean(lers):.4f} nm  LWR={np.mean(lwrs):.4f} nm")

print()
print("E. WRAP-TEST (Kante 40|0.5, det-Pfad, dx=0.25; Kante nahe Rand vs Mitte)")
for se in [2, 5, 8]:
    for shift in [32, 128]:  # Kante bei Spalte shift (Rand vs Mitte)
        H, W = 256, 256
        dm = torch.full((H, W), 0.5, dtype=torch.float32)
        dm[:, :shift] = 40.0
        from euvsimulator.resist.exposure import gaussian_se_blur, dose_to_acid
        acid = dose_to_acid(gaussian_se_blur(dm, sigma=se, dx=0.25), C=0.05, Q=1.0, apply_blur=False)
        row = acid[128].numpy()
        over = row > 0.3
        idx = np.argmax(~over) if (~over).any() else len(row)
        print(f"  se={se} Kante@Spalte {shift:3d}: det-Kante bei Spalte {idx:5.1f} (nm {idx*0.25:6.2f})  "
              f"acid@Kante={row[max(idx-1,0)]:.3f}")

print()
print("H. SILENT-CASE AUDIT")
cases = [
    ("se_blur=-5", dict(se_blur_nm=-5.0)),
    ("dose=0", dict(dose_mj_cm2=0.0)),
    ("Q→0.001", dict(dill_Q=0.001)),
    ("peb_sigma_diff=-1", dict(peb_sigma_diff=-1.0)),
    ("na=1.5", dict(na=1.5)),
    ("period=-64", dict(period_nm=-64.0)),
    ("line_width=0", dict(line_width_nm=0.0)),
    ("wavelength=0", dict(wavelength_nm=0.0)),
    ("grid=0", dict(grid=0)),
]
for name, kw in cases:
    try:
        cfg = SimulationConfig(**kw)
        try:
            r = run_simulation(cfg)
            status = f"RUNS: CD={r.cd_nm:.2f}" if r.cd_nm == r.cd_nm else "RUNS: CD=NaN"
        except Exception as e:
            status = f"Runtime-Error: {type(e).__name__}"
        print(f"  {name:20s}: Config akzeptiert, {status}")
    except Exception as e:
        print(f"  {name:20s}: Config-Error: {type(e).__name__}: {e}")

print()
print("I. DEAD-CONFIG VERIFIKATION (Parameterextreme -> Observable unveraendert?)")
pairs = [
    ("dill_A", 0.5, 9.0, "cd_nm"),
    ("dill_B", 0.2, 9.0, "cd_nm"),
    ("peb_D", 5.0, 500.0, "cd_nm"),
    ("stochastic_quantum_efficiency", 0.04, 0.9, "ler_nm"),
    ("mack_R_max", 100.0, 5000.0, "cd_nm"),
    ("mack_n", 5.0, 20.0, "cd_nm"),
]
for name, v0, v1, obs in pairs:
    try:
        r0 = run_simulation(car_cfg(**{name: v0}))
        r1 = run_simulation(car_cfg(**{name: v1}))
        a, b = getattr(r0, obs), getattr(r1, obs)
        same = (a == b) or (abs(a - b) < 1e-9)
        print(f"  {name:35s}: {v0:>7} -> {v1:>7} | {obs}: {a:.6f} vs {b:.6f} | {'UNVERAENDERT (DEAD)' if same else 'WIRKT'}")
    except Exception as e:
        print(f"  {name:35s}: Fehler {type(e).__name__}: {e}")
