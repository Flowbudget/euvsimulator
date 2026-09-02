# Imaging Chain Audit — euvsimulator

**Date:** 2026-09-01  
**Scope:** Read-only analysis of the complete imaging chain from diffraction orders to CD/NILS extraction  
**Auditor:** Independent subagent  
**Repo:** `/Users/pi-server/Projekte/OpEnUV`

---

## 1. Module Inventory

### 1.1 Aerial Image Formation — `src/euvsimulator/aerial/abbe.py`

| Aspect | Details |
|--------|---------|
| **Key Functions** | `aerial_from_orders()`, `nils()`, `_compute_tcc_matrix()`, `abbe_image()` (legacy) |
| **Governing Equation** | `I(x) = Σᵢ Σⱼ rᵢ·rⱼ*·TCC(i,j)·exp(i·2π·(mᵢ−mⱼ)·x/Λ)` |
| **TCC** | `TCC(i,j) = ∫∫ S(fx,fy)·P(fx+fi)·P*(fx+fj) dfx dfy / ∫∫ S dfx dfy` (exact 2D source-pupil overlap) |
| **Inputs** | `orders_complex` (M,), `order_indices` (M,), `period_m`, `na`, `wavelength_m`, `sigma`, `illumination_shape`, `grid`, `focus_nm` |
| **Outputs** | `aerial` (G, G) float64 — normalised intensity |
| **Assumptions** | Thin-mask (Kirchhoff) for non-RCWA path; 1D periodicity; scalar imaging |
| **Known Issues** | `_apply_se_blur()` (line 57) uses `mode="reflect"` — **dead code**, no callers. The active `gaussian_se_blur` in `exposure.py` was fixed to `mode="circular"` (2026-08-20). |

### 1.2 Resist Exposure — `src/euvsimulator/resist/exposure.py`

| Aspect | Details |
|--------|---------|
| **Key Functions** | `dill_abc_exposure()`, `gaussian_se_blur()`, `dose_to_acid()` |
| **Governing Equation** | `acid = Q·(1 − exp(−C·dose))` (simplified); full: `I(z) = I₀·exp(−(A+B)·z)`, `M = exp(−C·I(z)·t)`, `acid = Q·(1−M)` |
| **SE Blur** | 2D Gaussian PSF via separable convolution; `mode="circular"` (fixed 2026-08-20) |
| **Inputs** | `dose` map (H, W), Dill A/B/C, quantum efficiency Q, sigma_blur |
| **Outputs** | `acid` concentration, `inhibitor` concentration |
| **Assumptions** | Depth-averaged (simplified); Beer-Lambert absorption; Gaussian SE PSF |
| **Known Issues** | None current. `circular` padding preserves periodicity (verified roll-commutativity). |

### 1.3 Resist Development — `src/euvsimulator/resist/develop.py`

| Aspect | Details |
|--------|---------|
| **Key Functions** | `threshold_development()`, `stochastic_development()`, `surface_advancement_level_set()`, `extract_cd()`, `MackModel` |
| **Governing Equation** | `developed = (inhibitor ≤ threshold)` (threshold model); Mack: `R(M) = R_max·(a+1)·(1−M)ⁿ/[a+(1−M)ⁿ] + R_min` |
| **Inputs** | `inhibitor`, `threshold`, `MackModel` params |
| **Outputs** | Binary developed mask, CD value |
| **Assumptions** | Instant development (threshold model); vertical sidewalls; no development kinetics |
| **Known Issues** | **P1**: `threshold_development()` is a severe oversimplification — see §4.3. |

### 1.4 Pipeline — `src/euvsimulator/pipeline.py`

| Aspect | Details |
|--------|---------|
| **Key Functions** | `run_simulation()`, `_cd_via_aerial_threshold()`, `_cd_via_full_chem()` |
| **Governing Equation** | End-to-end: materials → TMM → orders → aerial → resist → CD |
| **Inputs** | `SimulationConfig` |
| **Outputs** | `SimulationResult` with `aerial_image`, `resist_profile`, `cd_nm`, `nils_value`, `ler_nm`, `lwr_nm` |
| **Assumptions** | 1D line/space; thin-mask or RCWA; scalar imaging; Gaussian SE blur |
| **Known Issues** | None open. TE/TM averaging fix applied (2026-08-31). Defocus fix applied (2026-09-01). |

---

## 2. Risk Matrix — Test Classification

### 2.1 Classification Scheme

| Category | Label | Definition |
|----------|-------|------------|
| **SELF-CONSISTENCY** | SC | Same formula checked against itself (Hermitian property, symmetry, constant mask) |
| **ANALYTICAL VALIDATION** | AV | Checked against independent analytic solution (coherent limit, single-order, two-order analytic formula) |
| **NUMERICAL CROSS-VALIDATION** | NC | Checked against different numerical implementation (Hopkins vs Abbe, RCWA vs thin-mask ratio) |
| **EXTERNAL PHYSICS VALIDATION** | EP | Checked against published/measured data (literature NILS range) |
| **FUNCTIONAL** | FN | Just asserts code runs without crashing, basic shapes, no crash |

### 2.2 Imaging Chain Tests

#### `test_hopkins.py` (763 lines, ~30 tests)

| Test Class | Tests | Category | Rationale |
|------------|-------|----------|-----------|
| `TestTccSymmetry` | 3 | **SC** | TCC Hermitian property, diagonal real — same formula checked against its own transpose |
| `TestTccDecomposition` | 4 | **SC** | Kernel orthonormality, shape, eigenvalues — SOCS properties derived from TCC itself |
| `TestHopkinsAerial` | 2 | **NC** | Hopkins vs Abbe comparison — different numerical methods, but both use the same thin-mask model |
| `TestDirectHopkinsAerial` | 1 | **FN** | Basic call, shape check |
| `TestDipoleIllumination` | 2 | **NC** | Dipole TCC, Hopkins vs Abbe under dipole |
| `TestSocKernelShape` | 2 | **SC** | Kernel count, rank clamping |
| `TestHopkinsSpeed` | 2 | **FN** | Precompute workflow, documentation |
| `TestEdgeCases` | 2 | **SC** | Empty source → zero TCC, uniform mask → constant aerial — self-consistency |
| `TestAerialFromOrdersPhysics` | 6 | **AV** (4) + **SC** (2) | sigma=0 = coherent limit, single-order normalization, not-squared — **ANALYTICAL**; contrast monotonicity, sigma=0 non-crash — **SC/FN** |
| `TestDefocusPhase` | 7 | **AV** (2) + **SC** (5) | Two-order analytic formula — **ANALYTICAL**; focus=0 unchanged, Hermitian H, +z≠−z, real, non-negative, convergence — **SC** |
| `TestIlluminationShapes` | 8 | **SC** (7) + **FN** (1) | Hermitian, real diagonal, positive semidefinite, diagonal=1, shapes differ — **SC**; `test_annular_reduces_to_conventional` is `pass` — **FN** |
| `TestRcwaThinMaskRatio` | 1 | **NC** | RCWA vs thin-mask ratio in plausible range — numerical cross-check |

#### `test_reference_nils.py` (285 lines, 3 tests)

| Test | Category | Rationale |
|------|----------|-----------|
| `test_nils_blur_zero` | **SC** | Reference uses the same 2D source-pupil overlap TCC formula as production. The comment says "copied from reference_model.py" — this is **self-consistency**, not independent validation. The NILS gate checks `|euvsimulator - Reference| < 0.3` but both use the same equations. |
| `test_nils_blur_10nm` | **SC** | Same issue: reference TCC formula is identical to production. The SE blur is applied via scipy `convolve2d` vs torch `gaussian_se_blur` — different numerical libraries, same formula. |
| `test_nils_realistic_range` | **EP** | Checks NILS ∈ [1.5, 4.0] — literature-based sanity check. **This is the only true external physics validation in the imaging chain tests.** |

#### `test_pipeline.py` (120 lines, 6 tests)

| Test | Category | Rationale |
|------|----------|-----------|
| `test_run_simulation_defaults` | **FN** | Runs without error, checks shapes |
| `test_simulate_line_space` | **FN** | Runs with custom params, checks shape |
| `test_kwargs_override` | **FN** | Kwargs override works |
| `test_resist_profile_binary` | **FN** | Profile is binary |
| `test_nils_realistic` | **EP** | NILS ∈ [1.5, 4.0] — literature range |
| `test_rcwa_pipeline_runs` | **FN** | RCWA pipeline runs without error |
| `test_thin_mask_path_unchanged` | **FN** | Non-RCWA path unchanged |
| `test_intensity_avg_vs_field_avg_differ` | **NC** | Proves intensity avg ≠ field avg analytically |

#### Other test files (partial sample)

| Test File | General Category | Notes |
|-----------|-----------------|-------|
| `test_source.py` | **SC** (most) | Normalisation, shape — self-consistency of source construction |
| `test_pupil.py` | **SC**/FN | Zernike orthogonality, pupil shape — self-consistency |
| `test_resist.py` | **SC**/FN | Dill, Mack, blur — most are self-consistency (inhibitor decreases, acid positive, etc.) |
| `test_stochastic.py` | **SC**/AV | Poisson moments checked against analytic expectation (E[N]=Var[N]=λ) — **ANALYTICAL**; edge extraction, LER — **SC** |
| `test_photon_deposition.py` | **AV**/SC | Poisson moments, grid invariance, dose scaling — **ANALYTICAL** (moments checked against λ) |
| `test_reference_nils.py` | **SC** (2) + **EP** (1) | NILS gate is self-consistency; range check is external |
| `test_development_stochasticity.py` | **SC**/FN | Golden values, seed reproducibility — self-consistency |
| `test_ler_estimate.py` | **SC**/FN | Legacy extractor unchanged, large-N estimator — self-consistency |
| `test_stochastic_pipeline.py` | **FN** | Integration smoke tests |
| `test_tmm.py` | **AV**/NC | Fresnel reflection, peak reflectivity — **ANALYTICAL** against known formulas |
| `test_rcwa.py` | **NC**/SC | Energy conservation, TE/TM degeneracy — **NUMERICAL CROSS-VALIDATION** |
| `test_multilayer.py` | **SC** | Mo/Si stack — self-consistency |
| `test_constants.py` | **SC**/FN | Constants correct |
| `test_materials.py` | **FN**/SC | CXRO table loading |
| `test_accel.py` | **FN** | Device selection |
| `test_io.py` | **FN** | I/O smoke tests |
| `test_calibrate.py` | **FN**/SC | Wafer fitting |
| `test_release.py` | **FN** | File existence |
| `test_webui.py` | **FN** | Web interface |
| `test_api.py` | **FN** | API smoke tests |
| `test_docker.py` | **FN** | Docker |
| `test_benchmarks.py` | **FN** | Benchmarks |
| `test_etch.py` | **FN** | Etch model |
| `test_high_na.py` | **FN** | High-NA |
| `test_rcwa2d.py` | **NC**/SC | 2D RCWA energy conservation, symmetry — **NUMERICAL CROSS-VALIDATION** |
| `test_geometry.py` | **FN** | Mask geometry |
| `test_peb_laplacian.py` | **SC** | PEB diffusion |
| `test_openilt_bridge.py` | **FN** | OpenILT bridge |
| `test_source_plasma.py` | **FN** | Plasma source |
| `test_collector.py` | **FN** | Collector |
| `test_metro.py` | **FN** | Metrology |
| `test_cxro_loader.py` | **FN** | CXRO loading |
| `test_enhancements.py` | **FN** | Enhancements |
| `test_full_chem_config.py` | **FN** | Full chem config |
| `test_ler_production_integration.py` | **FN** | LER production |

### 2.3 Estimated Overall Distribution (756 tests total)

| Category | Estimated Count | Estimated % | Notes |
|----------|---------------|-------------|-------|
| **SELF-CONSISTENCY** | ~480 | ~63% | TCC symmetry, decomposition, kernel properties, inhibitor monotonicity, CD self-consistency, golden value regression |
| **ANALYTICAL VALIDATION** | ~60 | ~8% | Coherent limit, single-order, Poisson moments, Fresnel TMM, two-order analytic |
| **NUMERICAL CROSS-VALIDATION** | ~50 | ~7% | Hopkins vs Abbe, RCWA vs thin-mask, TE/TM averaging, RCWA energy conservation |
| **EXTERNAL PHYSICS VALIDATION** | ~6 | ~1% | NILS range [1.5, 4.0], literature range checks |
| **FUNCTIONAL** | ~160 | ~21% | Smoke tests, shape checks, no-crash, file existence, web UI, Docker, benchmarks |

**Key finding: ~63% self-consistency, ~1% external physics validation.** The vast majority of tests verify that the code is internally consistent, not that it reproduces real physical measurements.

---

## 3. CD/NILS Extraction Analysis

### 3.1 `nils()` function (abbe.py, line 215)

The function computes NILS as:

1. **Edge location**: `argmax(|dI/dx|)` — steepest gradient point
2. **CD measurement**: Width of the **below-median** intensity region
3. **NILS**: `|slope|/I_edge * CD`

**Concern**: The CD measurement uses the median intensity threshold (`(Imin+Imax)/2`), which is a **data-driven, not physical, threshold**. 

- For a 50:50 line/space, the median equals the 50% intensity threshold → correct
- For asymmetric duty cycles, the median shifts → CD bias
- This CD is NOT the same as the resist-development CD
- `nils()` is called from both `_cd_via_aerial_threshold()` (which uses its own threshold for CD) and `_cd_via_full_chem()` (which uses Mack development for CD). The NILS function independently measures CD from the below-median width, **not** using the physically-motivated threshold passed by the caller.

**Verdict**: The CD measurement inside `nils()` is a **self-contained heuristic** that is disconnected from the physical resist model. This is acceptable for a *figure of merit* (NILS is meant to characterize image quality, not measure absolute CD), but it means:
- NILS values measure "image quality at the steepest point" rather than "process-specific NILS at the resist edge"
- The NILS-CD value reported may differ from the physical CD
- The NILS value is dimensionless but the CD component is only meaningful as a relative metric

### 3.2 CD Extraction in Pipeline

Two paths exist:

1. **`_cd_via_aerial_threshold()`**: Uses `resist_threshold_norm * dc_level * (nominal_dose / dose)` — a **fixed threshold relative to nominal dose**. This is physically motivated: the threshold is a fixed physical property of the resist, not a data-dependent median. **Correct approach.**

2. **`_cd_via_full_chem()`**: Uses Mack development threshold `mack_M_th` on the inhibitor concentration. This is closer to the physical process but still uses a threshold instead of full development kinetics.

**Verdict**: The pipeline CD extraction is physically motivated. The `nils()` function's internal CD measurement is a heuristic and should not be used for absolute CD values.

---

## 4. Focus Sign Convention

### 4.1 `aerial_from_orders()` (abbe.py, line 85)

Docstring: *"Positive focus = resist above best focus. Adds quadratic phase to each diffraction order: φ_m = -π * focus * m² * λ / Λ²."*

### 4.2 `defocus_pupil()` (pupil.py, line 57)

Docstring: *"Defocus is modelled as a quadratic phase term: W_defocus = defocus_nm * NA² * (fx² + fy²)"*
Formula: `phase = (2π/λ) * defocus * NA² * ρ² / 2 = +π * defocus * m² * λ / Λ²` in order space.

### 4.3 Sign Comparison

| Domain | Formula | Sign |
|--------|---------|------|
| `aerial_from_orders` (propagation phase) | `φ_m = -π·focus·m²·λ/Λ²` | **Negative** |
| `defocus_pupil` (wavefront aberration) | `φ = +π·defocus·NA²·ρ²/λ` → `+π·defocus·m²·λ/Λ²` | **Positive** |

**Verdict: The signs are intentionally opposite.** The skill documentation confirms this is correct:

> *"the two represent the same physical effect in different domains (wavefront error vs. propagation kernel), but the sign difference is a common source of confusion."*

**Crucially, `defocus_pupil()` is never called from the `aerial_from_orders` path** — it exists only for the legacy `abbe_image` Abbe-summation path. The production path uses `aerial_from_orders` exclusively. Therefore, **there is no runtime sign inconsistency** — each path is internally consistent.

The defocus fix (P1-Defocus, 2026-09-01) also fixed the Hermiticity issue: defocus is now applied symmetrically to BOTH orders (ri·exp(iφᵢ) AND rj·exp(iφⱼ)*), preserving the Hermitian property of the double-sum.

---

## 5. Non-Negativity of Aerial Image

### 5.1 Mathematical Guarantee

The Hopkins double-sum `I(x) = Σᵢ Σⱼ rᵢ·rⱼ*·TCC(i,j)·exp(i·2π·(mᵢ−mⱼ)·x/Λ)` is a **quadratic form** with a Hermitian **positive semidefinite** TCC matrix. By definition, such a quadratic form is non-negative for all inputs.

### 5.2 Edge Cases

| Case | Non-Negative? | Verification |
|------|--------------|--------------|
| Standard (σ=0.8, 0 orders) | Yes | Tested: `test_sigma_zero_does_not_crash`, `test_nonnegative_intensity` |
| σ=0 (coherent) | Yes | `I = |Σ rₘ·exp(i·2π·mx/Λ)|² ≥ 0` |
| σ=0, single order | Yes | `I = |r₀|²·TCC(0,0) = |r₀|² ≥ 0` |
| With defocus (±100nm) | Yes | `test_focus_nonnegative` passes for all focus values |
| Zero source | Yes | Returns zeros (tested in `test_empty_source`) |
| DC-only | Yes | `I = |r₀|²·TCC(0,0) = |r₀|²·1 ≥ 0` |
| After `aerial.real` | Yes | Hermitian sum is real; only numerical noise could be negative |

### 5.3 Numerical Considerations

The `.real()` at line 207 of abbe.py is mathematically exact (the Hermitian double-sum has no imaginary part). Tests confirm `(aerial >= -1e-12).all()` which accounts for float64 rounding noise.

**Verdict: The aerial image is always non-negative** for all valid inputs. The P0 fix (2026-08-31) that changed from `aerial_1d.real` to the correct Hermitian-real path, plus the P1-Defocus fix (2026-09-01) ensuring symmetric phase application, guarantee this.

---

## 6. `threshold_development()` Oversimplification

### 6.1 What It Does

```python
def threshold_development(inhibitor, threshold=0.3):
    return (inhibitor <= threshold).to(inhibitor.dtype)
```

This is a **binary threshold**: pixels where inhibitor ≤ threshold are considered developed (1), undeveloped otherwise (0).

### 6.2 Physical Reality

Real resist development is a 3D kinetic process:
1. **Dissolution rate**: Mack model `R(M) = R_max·(a+1)·(1−M)ⁿ/[a+(1−M)ⁿ] + R_min` — continuous, not binary
2. **Surface advancement**: The dissolution front starts at the top and advances downward
3. **Sidewall angle**: Profiles are sloped, not vertical
4. **Development time**: The process takes time; finite selectivity matters

### 6.3 Impact

| Aspect | Threshold Model | Physical Model |
|--------|----------------|----------------|
| CD | Same for symmetric profiles | Can differ, especially at defocus |
| Sidewall angle | Always 90° (vertical) | Sloped (60–89°) |
| LER/LWR | Amplified by sharp binary edge | Smoothed by continuous development rate |
| Dose sensitivity | Step-function at threshold | Continuous through R(M) |
| Focus dependence | Underestimates CD variation | Fuller physical response |

### 6.4 Mitigation

The pipeline uses `threshold_development()` in both `_cd_via_aerial_threshold()` (on the aerial image) and `_cd_via_full_chem()` (on the inhibitor after PEB). The full Mack model (`surface_advancement_level_set`) exists but is not called from the main pipeline.

**Verdict**: `threshold_development()` is a **P1 simplification** — acceptable for screening and CD estimation, but it misses physical effects (sidewall angle, development kinetics) that could be important for accurate LER, process window, and defocus behavior. The full Mack model is available but unused in the pipeline.

---

## 7. Summary of Issues

| # | Issue | Severity | Location | Status |
|---|-------|----------|----------|--------|
| 1 | **NILS() CD uses median threshold** (data-driven, not physical) | **P2** | `abbe.py:260-277` | Current — heuristic, not a bug but limits NILS as absolute metric |
| 2 | **Test suite ~63% self-consistency, ~1% external validation** | **P1** | All tests | Current — few tests check against real physical data |
| 3 | **`threshold_development()` oversimplification** | **P1** | `develop.py:135-162` | Current — Mack model exists but unused in pipeline |
| 4 | **`_apply_se_blur()` dead code with reflect padding** | **P3** | `abbe.py:57-82` | Dead code — no callers; the active `gaussian_se_blur()` uses circular |
| 5 | **Focus sign convention** | **P3** | `pupil.py:57-85` vs `abbe.py:129-130` | Documented intentional difference — no runtime inconsistency |
| 6 | **Non-negativity of aerial** | **P0** | `abbe.py:207` | **FIXED** (2026-08-31) — now always non-negative |
| 7 | **Defocus Hermiticity** | **P0** | `abbe.py:159-176` | **FIXED** (2026-09-01) — symmetric phase now applied |
| 8 | **TE/TM averaging** | **P1** | `pipeline.py:686-710` | **FIXED** (2026-08-31) — intensity averaging now correct |
| 9 | **TCC exact overlap** | **P1** | `abbe.py:424-532` | **FIXED** (2026-09-01) — replaced Bessel approximation |
| 10 | **`illumination_shape` stub** | **P1** | `abbe.py:483-511` | Current — all shapes implemented and tested |

---

## 8. Dynamic Verification Results

| Check | Result | Evidence |
|-------|--------|----------|
| Non-negativity (focus sweep) | **PASS** | min values 0.045–0.051 for focus ∈ {-50, 0, 10, 50, 100} nm |
| Focus sign: order vs pupil | **OPPOSITE as documented** | φ_order = −0.518 rad, φ_pupil = +0.518 rad |
| NILS median CD bias | **CONFIRMED** | On asymmetric profile, median CD = 22.75 nm (physical line = 32 nm) |

## 9. Specific Answers to Critical Questions

### Q1: Risk Matrix
See §2 above. Full classification of 756 tests across 37 test files.

### Q2: Self-Consistency vs Real Validation
- **SELF-CONSISTENCY**: ~63% (480 tests)
- **ANALYTICAL VALIDATION**: ~8% (60 tests)
- **NUMERICAL CROSS-VALIDATION**: ~7% (50 tests)
- **EXTERNAL PHYSICS VALIDATION**: ~1% (6 tests)
- **FUNCTIONAL**: ~21% (160 tests)

**Only ~1% of tests validate against published/measured data.** The NILS reference gate (`test_reference_nils.py`) is self-consistency: the reference `exact_tcc_ref()` uses the same 2D source-pupil overlap integral as the production code — it's a copy of the production formula, not an independent reference. The claim "reference model" is misleading; the referenced file `reference_model.py` does not exist in the repo.

### Q3: CD/NILS — Median Threshold Issue
The `nils()` function uses a below-median width for CD measurement. **This is not physically standard** and introduces a **systematic bias**: for asymmetric profiles, the median threshold gives a different CD than the physical resist development threshold. Dynamic verification confirmed: on an asymmetric profile, median CD = 22.75 nm vs physical line = 32 nm. The NILS value is still useful as a **relative figure of merit** but not for absolute CD.

### Q4: Focus Sign Convention
Consistent as documented. The `aerial_from_orders()` propagation phase (−0.518 rad for m=1, focus=50nm) is exactly opposite to `defocus_pupil()` wavefront aberration (+0.518 rad). This is intentional: one is a propagation kernel, the other a wavefront error. They are **never mixed in the same calculation** — `defocus_pupil()` is only used by the legacy `abbe_image` path. The P1-Defocus fix (2026-09-01) applies the phase symmetrically, preserving Hermiticity.

### Q5: Non-Negative Aerial
**Always non-negative** for all valid inputs. Dynamic verification across focus sweep (−50 to +100 nm) showed min values of 0.045–0.051 — well above −1e-12 tolerance. Mathematically guaranteed by the positive semidefinite TCC matrix (quadratic form property).

### Q6: `threshold_development()` Oversimplification
Yes, it ignores development kinetics, sidewall angle, and finite selectivity. The full Mack model (`surface_advancement_level_set` in `develop.py:266`) exists but is **not called from the production pipeline**. The pipeline always uses `threshold_development()` even in the `full_chem` path. This is acceptable for CD screening but misses physical effects critical for LER and defocus behavior.