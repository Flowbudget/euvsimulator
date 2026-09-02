"""
Mathematical analysis: Bessel J1 TCC vs correct source-pupil overlap integral.

The correct TCC [Hopkins 1953] is:
    TCC(f', f'') = ∫∫ S(f) · P(f+f') · P*(f+f'') d²f

For a 1D grating with orders m_i, m_j:
    f'_x = m_i * λ / (Λ * NA)   (normalized pupil coordinate)
    f''_x = m_j * λ / (Λ * NA)

The code's approximation:
    TCC ≈ 2·J₁(x)/x,  x = π · σ · NA · |m_i - m_j| · λ / Λ

We'll compute BOTH numerically and compare.
"""
import math
import numpy as np
from scipy.special import j1

# ============================================================
# PARAMETERS (typical EUV line/space)
# ============================================================
LAMBDA = 13.5e-9  # m
NA = 0.33
SIGMA = 0.8

def code_tcc(mi, mj, sigma=SIGMA, na=NA, period_m=None, wavelength_m=LAMBDA):
    """The Bessel J1 formula as used in aerial_from_orders."""
    dm = abs(mi - mj)
    x = math.pi * sigma * na * dm * wavelength_m / period_m
    if abs(x) < 1e-15:
        return 1.0
    return 2.0 * j1(x) / x


def correct_tcc_2d(mi, mj, sigma=SIGMA, na=NA, period_m=None, wavelength_m=LAMBDA,
                   grid_2d=401):
    """
    Compute the correct TCC as the source-pupil overlap integral
    for a 1D grating (orders on x-axis).
    
    TCC(mi, mj) = ∫∫_{|f|≤σ} 𝟙_{|f+(f'_x,0)|≤1} · 𝟙_{|f+(f''_x,0)|≤1} d²f
    
    Returns: overlap area (not normalized)
    """
    # Normalized pupil coordinates for the two orders
    f_i = mi * wavelength_m / (period_m * na)
    f_j = mj * wavelength_m / (period_m * na)
    
    # Source radius in normalized coordinates
    src_r = sigma
    
    # Integration grid in source coordinates
    half_grid = grid_2d // 2
    lin = np.linspace(-1.2, 1.2, grid_2d)  # slightly beyond pupil edge
    fx, fy = np.meshgrid(lin, lin)
    
    # Source indicator: |f| ≤ sigma
    in_source = (fx**2 + fy**2) <= src_r**2
    
    # Pupil indicators for the shifted pupils
    in_pupil_i = ((fx + f_i)**2 + fy**2) <= 1.0
    in_pupil_j = ((fx + f_j)**2 + fy**2) <= 1.0
    
    # Overlap of all three: source ∩ pupil_i ∩ pupil_j
    overlap = in_source & in_pupil_i & in_pupil_j
    
    # Area element
    dA = (2 * 1.2 / grid_2d) ** 2
    
    area = overlap.sum() * dA
    return area


def normalized_correct_tcc(mi, mj, **kwargs):
    """
    Correct TCC normalized so that TCC(m, m) = 1.
    """
    num = correct_tcc_2d(mi, mj, **kwargs)
    denom = correct_tcc_2d(mi, mi, **kwargs)
    if denom < 1e-30:
        return 0.0
    return num / denom


# ============================================================
# MAIN COMPARISON
# ============================================================
print("=" * 80)
print("TCC ANALYSIS: Bessel J1 formula vs Correct Source-Pupil Overlap Integral")
print("=" * 80)
print(f"λ = {LAMBDA*1e9:.1f} nm, NA = {NA}, σ = {SIGMA}")
print()

# Test cases: common line/space periods for EUV
periods_nm = [128, 64, 48, 44, 32, 22]
line_spacings = [64, 32, 24, 22, 16, 11]  # L/S half-pitch

for period_nm, half_pitch in zip(periods_nm, line_spacings):
    period_m = period_nm * 1e-9
    
    # Orders that fit within the pupil
    max_order = int(math.floor(NA * period_nm / LAMBDA * 1e9))
    print(f"\n{'─' * 70}")
    print(f"Period = {period_nm} nm (L/S = {half_pitch} nm), max_order = {max_order}")
    print(f"{'─' * 70}")
    
    # Check: position of ±1st order in pupil
    f1 = 1.0 * LAMBDA / (period_m * NA)
    print(f"  1st order position in pupil: f₁ = {f1:.4f} (pupil edge at 1.0)")
    
    # Compare TCC for several (mi, mj) pairs
    pairs = [
        (0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2),
        (0, -1), (1, -1),
    ]
    
    print(f"  {'mi':>4} {'mj':>4} {'dm':>4}  {'Code TCC':>10} {'Correct TCC':>12} {'Error':>10} {'f_i':>8} {'f_j':>8}")
    
    for mi, mj in pairs:
        # Check if orders are within pupil
        if abs(mi) > max_order or abs(mj) > max_order:
            continue
        
        dm = abs(mi - mj)
        c_tcc = code_tcc(mi, mj, period_m=period_m)
        corr_tcc = normalized_correct_tcc(mi, mj, period_m=period_m)
        
        f_i = mi * LAMBDA / (period_m * NA)
        f_j = mj * LAMBDA / (period_m * NA)
        
        if corr_tcc > 1e-15:
            error = (c_tcc - corr_tcc) / corr_tcc * 100
        else:
            error = 0.0 if abs(c_tcc) < 1e-15 else float('inf')
        
        print(f"  {mi:>4} {mj:>4} {dm:>4}  {c_tcc:>10.6f} {corr_tcc:>12.8f} {error:>+9.3f}%  {f_i:>8.4f} {f_j:>8.4f}")

# ============================================================
# DETAILED ANALYSIS FOR A SPECIFIC CASE
# ============================================================
print(f"\n\n{'=' * 80}")
print("DETAILED ANALYSIS: Period = 64 nm (L/S = 32 nm)")
print(f"{'=' * 80}")
period_m = 64e-9

f1 = LAMBDA / (period_m * NA)  # 1st order position
print(f"\n1st order f₁ = λ/(Λ·NA) = {f1:.6f}")

# Show how the TCC depends on source radius
print(f"\nFor the (0, 1) pair (dm=1):")
print("  Code TCC = 2*J₁(π·σ·NA·dm·λ/Λ)/(π·σ·NA·dm·λ/Λ)")
x = math.pi * SIGMA * NA * 1 * LAMBDA / period_m
print(f"  x = {x:.6f}")
print(f"  Code TCC = {2*j1(x)/x:.8f}")
print(f"  Normalized correct TCC = {normalized_correct_tcc(0, 1, period_m=period_m):.8f}")

print(f"\nFor the (0, 2) pair (dm=2):")
x2 = math.pi * SIGMA * NA * 2 * LAMBDA / period_m
print(f"  x = {x2:.6f}")
print(f"  Code TCC = {2*j1(x2)/x2:.8f}")
print(f"  Normalized correct TCC = {normalized_correct_tcc(0, 2, period_m=period_m):.8f}")

# ============================================================
# EXAMINE THE VAN CITTERT-ZERNIKE CONNECTION
# ============================================================
print(f"\n\n{'=' * 80}")
print("VAN CITTERT-ZERNIKE CONNECTION")
print(f"{'=' * 80}")

# The vC-Z degree of coherence for a circular source:
# μ(Δr) = 2*J₁(2π·σ·NA·Δr/λ) / (2π·σ·NA·Δr/λ)
# 
# The code's formula:
# TCC_code = 2*J₁(π·σ·NA·dm·λ/Λ) / (π·σ·NA·dm·λ/Λ)
#
# The code argument: x_code = π · σ · NA · dm · λ / Λ
# The vC-Z argument: x_vCZ = 2π · σ · NA · Δr / λ
#
# For these to match, we need: Δr = dm · λ² / (2 · Λ · NA²) ?
# This is not a physically meaningful separation distance.

# Let's compute the code TCC vs vC-Z for the actual order separation
print("\nComparison for period=64nm (32nm L/S):")
period_m = 64e-9
dm_values = [0, 1, 2, 3, 4]
for dm in dm_values:
    x_code = math.pi * SIGMA * NA * dm * LAMBDA / period_m
    tcc_code = 1.0 if dm == 0 else 2*j1(x_code)/x_code
    
    # vC-Z: what Δr would give the same x_code?
    # x_code = π · σ · NA · dm · λ / Λ
    # x_vCZ = 2π · σ · NA · Δr / λ
    # Equate: π · σ · NA · dm · λ / Λ = 2π · σ · NA · Δr / λ
    # => Δr = dm · λ² / (2 · Λ)
    delta_r = dm * LAMBDA**2 / (2 * period_m)
    x_vcz = 2*math.pi * SIGMA * NA * delta_r / LAMBDA
    mu_vcz = 1.0 if dm == 0 else 2*j1(x_vcz)/x_vcz
    
    print(f"  dm={dm}: code TCC={tcc_code:.8f}, vC-Z at Δr={delta_r*1e9:.6f}nm: μ={mu_vcz:.8f}, match={abs(tcc_code-mu_vcz)<1e-12}")

# ============================================================  
# WHAT THE CORRECT TCC SHOULD BE (FULL OVERLAP)
# ============================================================
print(f"\n\n{'=' * 80}")
print("CONCLUSION: Does the Bessel J1 formula capture the correct TCC?")
print(f"{'=' * 80}")

# Test the non-symmetric behavior: correct TCC depends on f_i, f_j individually
print(f"\nKey test: correct TCC depends on ABSOLUTE positions, not just difference")
print("(0,1) vs (-1,0): same dm but different absolute positions")

period_m = 64e-9
tcc_01 = normalized_correct_tcc(0, 1, period_m=period_m)
tcc_neg1_0 = normalized_correct_tcc(-1, 0, period_m=period_m)
print(f"  TCC(0,1)   = {tcc_01:.8f}  (f'=0, f''=f₁)")
print(f"  TCC(-1,0)  = {tcc_neg1_0:.8f}  (f'=-f₁, f''=0)")
print(f"  Same dm=1, but correct TCC differs: |Δ| = {abs(tcc_01 - tcc_neg1_0):.8f}")

print(f"\nCode TCC for dm=1                             = {code_tcc(0, 1, period_m=period_m):.8f}")
print(f"Code TCC symmetric (same for any mi,mj with dm=1) = {code_tcc(-1, 0, period_m=period_m):.8f}")

# Test for more extreme case: near pupil edge
print(f"\n\nNear-pupil-edge test (period=44nm):")
period_m = 44e-9
f1 = LAMBDA / (period_m * NA)
print(f"  f₁ = {f1:.4f}")
tcc_01_44 = normalized_correct_tcc(0, 1, period_m=period_m)
tcc_neg1_0_44 = normalized_correct_tcc(-1, 0, period_m=period_m)
code_tcc_44 = code_tcc(0, 1, period_m=period_m)
print(f"  TCC(0,1) correct = {tcc_01_44:.8f}")
print(f"  TCC(-1,0) correct = {tcc_neg1_0_44:.8f}")
print(f"  TCC code          = {code_tcc_44:.8f}")
print(f"  Error (0,1):  |code-correct|/correct = {abs(code_tcc_44-tcc_01_44)/tcc_01_44*100 if tcc_01_44>0 else float('inf'):.2f}%")
print(f"  Error (-1,0): |code-correct|/correct = {abs(code_tcc_44-tcc_neg1_0_44)/tcc_neg1_0_44*100 if tcc_neg1_0_44>0 else float('inf'):.2f}%")

# ============================================================
# SUMMARY TABLE
# ============================================================
print(f"\n\n{'=' * 80}")
print("SUMMARY TABLE: (0,1) pair across periods")
print(f"{'=' * 80}")
print(f"  {'Period(nm)':>12} {'f₁':>8} {'Code TCC':>10} {'Correct(0,1)':>14} {'Correct(-1,0)':>14} {'Error(0,1)%':>12}")
for period_nm in [128, 64, 48, 44, 40, 36, 32]:
    period_m = period_nm * 1e-9
    f1 = LAMBDA / (period_m * NA)
    if f1 > 1.01:
        continue
    tcc_code = code_tcc(0, 1, period_m=period_m)
    tcc_c01 = normalized_correct_tcc(0, 1, period_m=period_m)
    tcc_cn10 = normalized_correct_tcc(-1, 0, period_m=period_m)
    err = abs(tcc_code - tcc_c01) / tcc_c01 * 100
    print(f"  {period_nm:>12} {f1:>8.4f} {tcc_code:>10.6f} {tcc_c01:>14.8f} {tcc_cn10:>14.8f} {err:>11.3f}%")