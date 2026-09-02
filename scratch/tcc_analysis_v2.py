"""
TCC analysis v2: correct comparison of Bessel J1 vs source-pupil overlap integral.
"""
import math
import numpy as np
from scipy.special import j1

LAMBDA = 13.5e-9
NA = 0.33
SIGMA = 0.8


def code_tcc(mi, mj, sigma=SIGMA, na=NA, period_m=None):
    """Bessel J1 formula as used in aerial_from_orders."""
    dm = abs(mi - mj)
    x = math.pi * sigma * na * dm * LAMBDA / period_m
    if abs(x) < 1e-15:
        return 1.0
    return 2.0 * j1(x) / x


def tcc_overlap_raw(mi, mj, period_m=None, grid_2d=501):
    """
    Compute the raw TCC overlap integral:
    TCC(mi, mj) = ∫∫_{|f|≤σ, |f+fi|≤1, |f+fj|≤1} d²f

    Returns the raw AREA (not normalized).
    """
    fi = mi * LAMBDA / (period_m * NA)
    fj = mj * LAMBDA / (period_m * NA)

    src_r = SIGMA
    extent = max(1.2, abs(fi) + 1.2, abs(fj) + 1.2)

    lin = np.linspace(-extent, extent, grid_2d)
    fx, fy = np.meshgrid(lin, lin)

    in_source = (fx**2 + fy**2) <= src_r**2
    in_pupil_i = ((fx + fi)**2 + fy**2) <= 1.0
    in_pupil_j = ((fx + fj)**2 + fy**2) <= 1.0

    overlap = in_source & in_pupil_i & in_pupil_j
    dA = (2 * extent / grid_2d) ** 2
    return float(overlap.sum() * dA)


def hopkins_tcc(mi, mj, period_m=None):
    """
    Compute the correctly normalized Hopkins TCC as defined by:
    μ(mi, mj) = TCC(mi, mj) / sqrt(TCC(mi,mi) * TCC(mj,mj))
    
    This is the degree of coherence normalized by the geometric mean
    of the diagonal elements, matching the coherence factor used in
    the code's I(x) = ΣᵢΣⱼ rᵢ rⱼ* TCC(i,j) exp(...).
    """
    t = tcc_overlap_raw(mi, mj, period_m=period_m)
    ti = tcc_overlap_raw(mi, mi, period_m=period_m)
    tj = tcc_overlap_raw(mj, mj, period_m=period_m)
    denom = math.sqrt(max(ti, 1e-30) * max(tj, 1e-30))
    return t / denom if denom > 1e-30 else 0.0


print("=" * 80)
print("TCC ANALYSIS: Bessel J1 formula vs Correct Hopkins Overlap Integral")
print("=" * 80)
print(f"λ = {LAMBDA*1e9:.1f} nm, NA = {NA}, σ = {SIGMA}")
print()

test_cases = [
    (128, 0.3196),
    (64,  0.6392),
    (48,  0.8523),
    (44,  0.9298),
]

print(f"{'Period':>8} {'f₁':>8} {'Pair':>10} {'Code TCC':>10} {'Hopkins TCC':>12} {'Raw Overlap':>12} {'Diag(i,i)':>12} {'Diag(j,j)':>12} {'Error':>10}")
print(f"{'─'*8} {'─'*8} {'─'*10} {'─'*10} {'─'*12} {'─'*12} {'─'*12} {'─'*12} {'─'*10}")
for period_nm, f1 in test_cases:
    period_m = period_nm * 1e-9
    
    for mi, mj in [(0, 1), (0, 2), (1, -1)]:
        dm = abs(mi - mj)
        code_val = code_tcc(mi, mj, period_m=period_m)
        hopkins_val = hopkins_tcc(mi, mj, period_m=period_m)
        
        raw = tcc_overlap_raw(mi, mj, period_m=period_m)
        diag_i = tcc_overlap_raw(mi, mi, period_m=period_m)
        diag_j = tcc_overlap_raw(mj, mj, period_m=period_m)
        
        if hopkins_val > 1e-15:
            err = (code_val - hopkins_val) / hopkins_val * 100
        else:
            err = float('inf')
        
        fi = mi * LAMBDA / (period_m * NA)
        fj = mj * LAMBDA / (period_m * NA)
        
        print(f"  {period_nm:>6}  {f1:>8.4f} ({mi:>2},{mj:>2}) "
              f"{code_val:>10.6f} {hopkins_val:>12.8f} "
              f"{raw:>12.8f} {diag_i:>12.8f} {diag_j:>12.8f} {err:>+9.3f}%")

print(f"\n{'='*80}")
print("KEY SYMMETRY CHECK: Hopkins TCC depends on ABSOLUTE positions, not just dm")
print(f"{'='*80}")

period_m = 64e-9
f1 = LAMBDA / (period_m * NA)
print(f"\nPeriod=64nm: f₁ = {f1:.4f}")
pairs = [(0,1), (1,0), (-1,0), (0,-1), (1,-1), (-1,1), (1,2), (0,3)]
print(f"  {'Pair':>8} {'dm':>4} {'Code TCC':>10} {'Hopkins TCC':>12} {'Raw':>12} {'Diag_i':>10} {'Diag_j':>10}")
for mi, mj in pairs:
    dm = abs(mi-mj)
    c = code_tcc(mi, mj, period_m=period_m)
    h = hopkins_tcc(mi, mj, period_m=period_m)
    r = tcc_overlap_raw(mi, mj, period_m=period_m)
    di = tcc_overlap_raw(mi, mi, period_m=period_m)
    dj = tcc_overlap_raw(mj, mj, period_m=period_m)
    print(f"  ({mi:>2},{mj:>2})  {dm:>4} {c:>10.6f} {h:>12.8f} {r:>12.8f} {di:>10.6f} {dj:>10.6f}")

print(f"\n{'='*80}")
print("FULL TCC TABLE for period=64nm")
print(f"{'='*80}")
period_m = 64e-9
orders = [-2, -1, 0, 1, 2]
max_o = int(NA * period_m / LAMBDA)
print(f"Max order in pupil: {max_o}")
print(f"\nCode TCC (Bessel J1):")
print(f"  {'':>4}", end="")
for mj in orders:
    print(f" {mj:>4}", end="")
print()
for mi in orders:
    print(f" {mi:>4}", end="")
    for mj in orders:
        if abs(mi) > max_o or abs(mj) > max_o:
            print(f" {'X':>4}", end="")
        else:
            print(f" {code_tcc(mi, mj, period_m=period_m):>7.4f}"[:4], end="")
    print()

print(f"\nHopkins TCC (correct overlap integral, normalized):")
print(f"  {'':>4}", end="")
for mj in orders:
    print(f" {mj:>4}", end="")
print()
for mi in orders:
    print(f" {mi:>4}", end="")
    for mj in orders:
        if abs(mi) > max_o or abs(mj) > max_o:
            print(f" {'X':>4}", end="")
        else:
            val = hopkins_tcc(mi, mj, period_m=period_m)
            print(f" {val:>7.4f}"[:4], end="")
    print()

print(f"\nRaw Overlap Area (μm² in normalized coords):")
print(f"  {'':>4}", end="")
for mj in orders:
    print(f" {mj:>4}", end="")
print()
for mi in orders:
    print(f" {mi:>4}", end="")
    for mj in orders:
        if abs(mi) > max_o or abs(mj) > max_o:
            print(f" {'X':>4}", end="")
        else:
            r = tcc_overlap_raw(mi, mj, period_m=period_m)
            print(f" {r:>7.4f}"[:4], end="")
    print()


print(f"\n{'='*80}")
print("THEORETICAL ANALYSIS")
print(f"{'='*80}")
print(r"""
Correct TCC (Hopkins 1953):
    TCC(f', f'') = ∫∫ S(f) P(f+f') P*(f+f'') d²f

For conventional illumination (circular source of radius σ, 
top-hat pupil of radius 1):
    S(f) = 1 for |f| ≤ σ, 0 otherwise
    P(f) = 1 for |f| ≤ 1, 0 otherwise

TCC is the overlap area of THREE circles:
    Circle 1: source, radius σ, center O
    Circle 2: pupil shifted by -f', radius 1, center -f'
    Circle 3: pupil shifted by -f'', radius 1, center -f''

For 1D mask orders on the x-axis at f_i = m_i·λ/(Λ·NA), f_j = m_j·λ/(Λ·NA),
all three centers lie on the x-axis. The overlap area depends on σ, f_i, f_j.

The Bessel formula 2J₁(x)/x with x = π·σ·NA·|mi-mj|·λ/Λ
is the van Cittert-Zernike object-plane degree of coherence. It is
NOT the frequency-domain TCC.

The vC-Z coherence equals TCC ONLY if the pupil is infinite (P=1 everywhere).
In realistic EUV systems the pupil clips orders, coupling source coherence
and pupil filtering in a way the Bessel formula cannot capture.
""")

print(f"\n{'='*80}")
print("ERROR SUMMARY")
print(f"{'='*80}")
print(f"\n{'Period(nm)':>10} {'L/S(nm)':>10} {'f₁':>8} {'Code(0,1)':>10} {'Hopkins(0,1)':>14} {'Error%':>10}")
for period_nm in [128, 64, 48, 44, 40, 36]:
    period_m = period_nm * 1e-9
    f1 = LAMBDA / (period_m * NA)
    if f1 > 1.01:
        break
    code_val = code_tcc(0, 1, period_m=period_m)
    hopkins_val = hopkins_tcc(0, 1, period_m=period_m)
    err = (code_val - hopkins_val) / hopkins_val * 100
    hp = period_nm / 2
    print(f"  {period_nm:>8} {hp:>8}  {f1:>8.4f} {code_val:>10.6f} {hopkins_val:>14.8f} {err:>+9.3f}%")