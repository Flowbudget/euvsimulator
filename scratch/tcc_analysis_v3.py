"""
TCC analysis v3: investigate the hard pupil cutoff and effective NA
"""
import math
import numpy as np
from scipy.special import j1

LAMBDA = 13.5e-9
NA = 0.33
SIGMA = 0.8

def tcc_overlap_raw(mi, mj, period_m=None, grid_2d=501):
    fi = mi * LAMBDA / (period_m * NA)
    fj = mj * LAMBDA / (period_m * NA)
    src_r = SIGMA
    extent = max(1.5, abs(fi) + 1.5, abs(fj) + 1.5)
    lin = np.linspace(-extent, extent, grid_2d)
    fx, fy = np.meshgrid(lin, lin)
    in_source = (fx**2 + fy**2) <= src_r**2
    in_pupil_i = ((fx + fi)**2 + fy**2) <= 1.0
    in_pupil_j = ((fx + fj)**2 + fy**2) <= 1.0
    overlap = in_source & in_pupil_i & in_pupil_j
    dA = (2 * extent / grid_2d) ** 2
    return float(overlap.sum() * dA)

# Check: which orders CAN contribute with off-axis illumination?
print("=" * 80)
print("EFFECTIVE NA ANALYSIS")
print("=" * 80)
print()
print("With conventional illumination σ = 0.8, the source extends")
print("from f = -0.8 to f = +0.8 in normalized pupil coordinates.")
print("An order at f_m can be imaged if there exists some source point")
print("f such that |f| ≤ σ AND |f + f_m| ≤ 1.")
print()
print("Condition: |f_m| - σ ≤ 1  →  |f_m| ≤ 1 + σ")
print(f"Effective max |f| = 1 + σ = {1+SIGMA:.2f}")
print(f"Normal-incidence max |f| = 1.0")
print()

for period_nm in [128, 64, 48, 44]:
    period_m = period_nm * 1e-9
    max_order_normal = int(1.0 * period_m * NA / LAMBDA)
    max_order_effective = int((1+SIGMA) * period_m * NA / LAMBDA)
    
    print(f"Period = {period_nm} nm:")
    for mi in range(0, 5):
        fi = mi * LAMBDA / (period_m * NA)
        can_image_normal = fi <= 1.0
        can_image_oa = fi <= 1.0 + SIGMA
        diag_raw = tcc_overlap_raw(mi, mi, period_m=period_m) if fi <= 1.0 + SIGMA else 0.0
        
        print(f"  Order {mi}: f_{mi} = {fi:.4f}  "
              f"| within NA? {'YES' if can_image_normal else 'NO '}  "
              f"| OA-assisted? {'YES' if can_image_oa else 'NO '}  "
              f"| TCC({mi},{mi}) raw = {diag_raw:.4f}")
    
    print(f"  Code's max_order = {max_order_normal}")
    print(f"  Effective max_order (σ=0.8) = {max_order_effective}")
    print()

# Show: what the code currently includes vs what it should include
print("=" * 80)
print("CORRECT MAX ORDER FOR period=64nm")
print("=" * 80)
period_m = 64e-9
print(f"\nNormal-incidence max_order = int(NA·Λ/λ) = int({NA*period_m/LAMBDA:.3f}) = {int(NA*period_m/LAMBDA)}")
print(f"Effective max_order (σ=0.8) = int((1+σ)·NA·Λ/λ) = int({(1+SIGMA)*NA*period_m/LAMBDA:.3f}) = {int((1+SIGMA)*NA*period_m/LAMBDA)}")

print(f"\nAll possible order pairs with non-zero TCC (period=64nm, σ=0.8):")
f1 = LAMBDA / (period_m * NA)
print(f"\nf₁ = {f1:.4f}")
nonzero_pairs = []
for mi in range(-3, 4):
    for mj in range(-3, 4):
        raw = tcc_overlap_raw(mi, mj, period_m=period_m)
        if raw > 1e-8:
            nonzero_pairs.append((mi, mj, raw))

for mi, mj, raw in sorted(nonzero_pairs):
    fi = mi * LAMBDA / (period_m * NA)
    fj = mj * LAMBDA / (period_m * NA)
    diag_i = tcc_overlap_raw(mi, mi, period_m=period_m)
    diag_j = tcc_overlap_raw(mj, mj, period_m=period_m)
    normalized = raw / math.sqrt(max(diag_i, 1e-30) * max(diag_j, 1e-30))
    code = j1(math.pi * SIGMA * NA * abs(mi-mj) * LAMBDA / period_m) * 2 / (math.pi * SIGMA * NA * abs(mi-mj) * LAMBDA / period_m) if mi != mj else 1.0
    print(f"  ({mi:>2},{mj:>2})  dm={abs(mi-mj):>2}  | "
          f"fi={fi:>7.4f}  fj={fj:>7.4f}  | "
          f"raw={raw:.4f}  TCC={normalized:.4f}  "
          f"code_TCC={code:.4f}  "
          f"in_code? {'YES' if abs(mi)<=int(NA*period_m/LAMBDA) and abs(mj)<=int(NA*period_m/LAMBDA) else 'NO '}")