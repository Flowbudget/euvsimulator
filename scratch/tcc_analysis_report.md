================================================================================
P1-1 INVESTIGATION: TCC FORMULA IN aerial_from_orders()
================================================================================

Date: 2026-09-01
Analyst: Hermes subagent

Files examined:
  - /Users/pi-server/Projekte/OpEnUV/src/euvsimulator/aerial/abbe.py
  - /Users/pi-server/Projekte/OpEnUV/src/euvsimulator/aerial/hopkins.py
  - /Users/pi-server/Projekte/OpEnUV/src/euvsimulator/aerial/source.py
  - /Users/pi-server/Projekte/OpEnUV/src/euvsimulator/pipeline.py
  - /Users/pi-server/Projekte/OpEnUV/tests/test_hopkins.py
  - /Users/pi-server/Projekte/OpEnUV/tests/test_reference_nils.py
  - /Users/pi-server/Projekte/OpEnUV/MASTER_CONTEXT.md

================================================================================
1. EXACT FORMULA IN THE CODE
================================================================================

File: abbe.py, lines 199-210
Reference: test_reference_nils.py, lines 29-34 (reference implementation)

  dm = abs(mi - mj)
  x = math.pi * sigma * na * dm * wavelength_m / period_m
  if abs(x) < 1e-15:
      tcc = 1.0
  else:
      tcc = 2.0 * _j1(x) / x

Mathematically:

  TCC_code(m_i, m_j) = 2·J₁(x) / x
  x = π · σ · NA · |m_i - m_j| · λ / Λ

where:
  J₁ = Bessel function of the first kind, order 1
  σ = partial coherence factor
  NA = numerical aperture
  λ = wavelength (13.5 nm)
  Λ = mask period
  m_i, m_j = diffraction order indices

The docstring claims this is the "Hopkins degree of coherence" for a
circular source.

================================================================================
2. CORRECT TCC FORMULA
================================================================================

The correct Transmission Cross Coefficient [Hopkins 1953] is:

  TCC(f', f'') = ∫∫ S(f) · P(f+f') · P*(f+f'') d²f

where:
  S(f) = source intensity distribution (in normalized pupil coordinates)
  P(f) = pupil function (1 inside NA, 0 outside)
  f, f', f'' = 2D normalized spatial frequency vectors

For conventional illumination (circular uniform source) and ideal
pupil (circular top-hat at NA):

  S(f) = 1  for |f| ≤ σ,  0 otherwise
  P(f) = 1  for |f| ≤ 1,  0 otherwise

  TCC(f_i, f_j) = ∬_{|f| ≤ σ} 𝟙_{|f+f_i| ≤ 1} · 𝟙_{|f+f_j| ≤ 1} d²f

where 𝟙 is the indicator function and fᵢ = mᵢ·λ/(Λ·NA).

GEOMETRIC INTERPRETATION: The TCC is the area of overlap of THREE
disks on the x-axis:
  - Disk 1 (source):     radius σ, center at origin
  - Disk 2 (pupil@f_i):   radius 1, center at -f_i
  - Disk 3 (pupil@f_j):   radius 1, center at -f_j

This depends on σ, f_i, and f_j INDIVIDUALLY — NOT just on their
difference |f_i - f_j| (i.e., not just on |m_i - m_j|).

================================================================================
3. IS THE BESSEL FORMULA EQUIVALENT? NO
================================================================================

The code's Bessel J₁ formula:

  TCC_code(m_i, m_j) = 2·J₁(π·σ·NA·|m_i-m_j|·λ/Λ) / (π·σ·NA·|m_i-m_j|·λ/Λ)

This is the van Cittert-Zernike (vC-Z) object-plane degree of coherence:

  μ(Δr) = 2·J₁(2π·σ·NA·Δr/λ) / (2π·σ·NA·Δr/λ)

The code's formula matches vC-Z *numerically* when the spatial separation
Δr in the object plane is Δr = dm·λ²/(2Λ). But:

  (a) This Δr has NO physical meaning as a separation in the object
      plane for the mask diffraction orders.

  (b) The vC-Z theorem describes the mutual intensity in the OBJECT
      PLANE (spatial domain). The TCC is defined in the FREQUENCY
      DOMAIN (pupil plane). They are related by a Fourier transform,
      NOT identical.

  (c) For the object-plane mutual intensity to equal the TCC, the
      pupil function must be P(f) = 1 everywhere (infinite NA,
      no pupil clipping). This is physically unrealistic.

CONCLUSION: The Bessel J₁ formula is the van Cittert-Zernike object-plane
mutual intensity, NOT the correct frequency-domain TCC. The code confuses
two different physical quantities that only coincide in the unphysical
limit of an infinite pupil.

================================================================================
4. ERROR MAGNITUDE
================================================================================

Numerical comparison (λ=13.5nm, NA=0.33, σ=0.8) computed via
501×501 grid numerical integration of the correct overlap integral:

Period=128nm (L/S=64nm), f₁=0.32:
  (0,1): Code=0.999  Correct=0.969  Error= +3.1%
  (1,-1):  Code=0.996  Correct=0.933  Error= +6.7%
  → SMALL error (orders near pupil center)

Period=64nm (L/S=32nm), f₁=0.64:
  (0,1): Code=0.996  Correct=0.831  Error= +19.8%
  (1,-1):  Code=0.985  Correct=0.555  Error= +77.3%
  → MODERATE-LARGE error (1st order at mid-pupil)

Period=48nm (L/S=24nm), f₁=0.85:
  (0,1): Code=0.993  Correct=0.724  Error= +37.2%
  (1,-1):  Code=0.973  Correct=0.197  Error=+393.1%
  → LARGE error (1st order near pupil edge)

Period=44nm (L/S=22nm), f₁=0.93:
  (0,1): Code=0.992  Correct=0.682  Error= +45.4%
  (1,-1):  Code=0.968  Correct=0.075  Error=+1195%
  → VERY LARGE error (1st order at edge)

ROOT CAUSE: The Bessel formula depends ONLY on dm = |m_i - m_j|, so it
gives the same TCC value for (0,1) and (1,-1) regardless of how close
the orders are to the pupil edge. The correct TCC is smaller when
either order is near the pupil edge because the pupil clips the source
differently for different absolute positions.

For example at period=64nm:
  TCC(0,1) correct = 0.831  (one order at center, one near edge)
  TCC(1,-1) correct = 0.555 (both orders near opposite edges)
But code gives 0.996 for BOTH.

================================================================================
5. SECOND ERROR: HARD PUPIL CUTOFF IS INCORRECT
================================================================================

The code uses a hard normal-incidence pupil cutoff (abbe.py line 144):

  max_order = int(math.floor(na * period_m / wavelength_m))

Orders with |m| > max_order are COMPLETELY discarded. This assumes
|f_m| = |m|·λ/(Λ·NA) ≤ 1 (normal incidence).

With σ > 0, off-axis illumination extends the effective NA to
NA_eff = NA·(1+σ), allowing orders with |f_m| ≤ 1+σ to contribute.

For period=64nm, σ=0.8:
  Normal-incidence max_order = 1
  Effective max_order = 2 (order 2 at f₂=1.28 can still be imaged
                           via off-axis source points)

The overlap integral shows TCC(2,2) raw area = 0.448 (vs 2.003 for
TCC(0,0)). This contribution is physically real and represents the
resolution enhancement from off-axis illumination. The code's hard
cutoff at max_order=1 discards it entirely.

================================================================================
6. RECOMMENDED FIX
================================================================================

Replace the Bessel J₁ formula with the numerical source-pupil overlap
integral. The fix for `aerial_from_orders()` should:

  1) REMOVE the hard pupil cutoff (max_order check)
  2) REMOVE the Bessel J₁ TCC formula
  3) ADD computation of the correct TCC via overlap integral

The overlap integral for each order pair (m_i, m_j):

  TCC(m_i, m_j) = Σ_f S(f) · 𝟙(|f+f_i| ≤ 1) · 𝟙(|f+f_j| ≤ 1)

where f_i = m_i · λ / (Λ · NA) and S(f) is the source from source.py.

This can be implemented efficiently as:

  a) Precompute the 2D source map S(f) using the existing source.py
     generators (conventional, annular, dipole, etc.) on the pupil
     grid from pupil_grid().

  b) For each order pair (m_i, m_j), compute f_i on the source grid,
     evaluate the pupil shifts, and sum over the grid.

  c) OR precompute a TCC lookup table for the order set, since the
     TCC only depends on (f_i, f_j, σ, source_shape) and can be
     computed once per configuration.

The fix has FOUR advantages over the current code:
  - Correct TCC for ANY source shape (not just conventional)
  - Correctly handles off-axis illumination (larger effective NA)
  - Captures pupil coupling (reduced coherence near pupil edge)
  - Works natively with the source module's output

DISADVANTAGE: Slightly more computation per image (O(M²·N_src) vs
O(M²) for the Bessel formula), but the M² term dominates for M~20
orders so the N_src overhead is modest. For very large iteration
counts, a precomputed TCC matrix avoids this entirely.

================================================================================
7. IMPACT ON EXISTING TESTS
================================================================================

The current test suite (test_reference_nils.py, test_hopkins.py)
uses the SAME Bessel formula as the reference, so the tests are
self-consistent but not physically correct. They will pass after
the fix only if the test reference is also updated.

The NILS gate (|NILS - Reference| < 0.3) will likely fail because
the correct TCC reduces interference contrast, which reduces NILS.
After the fix, the NILS values should decrease (more realistic).

The correct verification approach is to compare against a
separate Abbe summation implementation (via abbe_image()) which
computes the correct physical result by summing over source points
explicitly.

================================================================================
FILES MODIFIED: None (read-only analysis)
SCRATCH FILES: scratch/tcc_analysis.py, scratch/tcc_analysis_v2.py,
               scratch/tcc_analysis_v3.py
================================================================================