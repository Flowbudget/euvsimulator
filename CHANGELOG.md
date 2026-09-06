# Changelog

All notable changes to euvsimulator are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added (validation anchors, 2026-09-06, plan stage B2)
- **Explicit quencher for NXE1716** (`presets.NXE1716_QUENCHER_FIT`, `nxe1716_config(explicit_quencher=True)`,
  `presets.flood_rate_quenched`): the NXE1717 curve (half the quencher) was digitised too; a joint fit with
  shared deprotection rate and a 2:1 quencher ratio through the chain's own neutralisation step gives a
  relative quencher loading of 0.13–0.15 (Q ≈ 0.03 nm⁻³), rms 0.03/0.06 in log10 R. Finding: neither the
  dose-to-size (19.7 → 19.7) nor the LWR at matched dose (10.9 → 11.1 nm 3σ) depends on it — a subtractive
  quencher is cancelled alike in flood and pattern. Structural result (log Fortsetzung 29): for a symmetric
  1:1 image the edge sits at the mean intensity (0.318 of open frame here), so the printing dose is the flood
  through-dose divided by 0.318; imec's 11.0 mJ/cm² would need the film to clear at 3.5 mJ/cm² where the DRM
  curve gives 0.02 nm/s. The two Vesters experiments (PAB 110 vs 90 °C, SiO₂ vs AL412 underlayer) are
  incompatible by ~2× in dose under any symmetric image model; the calibration stays declared.
- **MET-2D / XP 5271 anchor** (`presets.met2d_config`, `data/anchors/met2d_xp5271.json`): C and FQY (LBNL),
  B and Mack (Sekiguchi 2011 Table 6), measured deprotection blur, E-size and LER (Anderson & Naulleau 2008,
  OSTI 950847) for one commercial resist from four groups; blur set directly from the measurement
  (23.8 nm width → σ 10.1). With the dose scale calibrated to E-size 12.5, the photon-shot-noise LER at
  50 nm 1:1 is **0.74 nm 3σ vs measured 6.7** — the chain's photon-only noise model accounts for ≤ 15 % of
  the measured LER at 80 nm film / 13 mJ/cm², consistent with Anderson's "intrinsic LER floor". Together
  with NXE1716 (photon LWR 1.6× too high at 35 nm film / 22 nm HP) this falsifies "photon shot noise only"
  as the LWR model: a dose-independent floor (polymer, development, SEM bias) is missing.
- New tests: `tests/test_met2d_anchor.py`, two-curve quencher regression in `tests/test_nxe1716_anchor.py`.

### Added (validation anchor, 2026-09-06, plan stage B1)
- **NXE1716 anchor** (`euvsimulator.presets.nxe1716_config`, data in `data/anchors/vesters2017_nxe1716.json`):
  Vesters 2017 DRM contrast curve digitised (25 fit points, 16 markers, axis-calibrated) and the thesis
  patterning row (22 nm lines / 44 nm pitch, NXE3300B dipole 90X, D2S 11.0 mJ/cm², LWR 6.7 nm 3σ biased).
  The chain reproduces the flood curve (rms 0.04 in log10 R) with Mack plateaus from the data and (k, n)
  fitted at fixed M_th (degenerate triple, documented).
- **Scanner-style multipole sources**: `sigma_inner` and `pole_opening_deg` on `SimulationConfig` /
  `aerial_from_orders` give annular-sector dipole/quasar poles (imec "dipole 90X 0.62/0.90"); legacy
  fixed-geometry poles unchanged when `sigma_inner` is None. At 44 nm pitch, NA 0.33 every dipole point is
  two-beam (TCC(0,±1) = 0.5 exactly); conventional σ 0.8 gives 0.47.
- **Result, reported as found:** without a free parameter the chain prints at 19.7 mJ/cm² instead of 11.0
  (1.79×; blur and develop time explain ≤ 2 mJ/cm² of it, open discrepancy). With the dose scale calibrated
  (declared, `calibrated_dose_scale=True`) the photon-shot-noise LWR is 10.9 nm 3σ with the default PEB
  blur (9.4 nm, τ from 110 °C) and 4.8 nm with a 5 nm blur, vs measured 6.7 (SEM-biased): the anchor brackets
  the measurement and, without a measured blur for this resist at 90 °C, neither validates nor falsifies the
  noise model (±1.6×). With molecular noise 19 nm. No parameter was tuned to the LWR. Candidate causes logged
  (quencher contrast, unknown α, τ at 90 °C, sampler variance).

### Changed (physics, 2026-09-06, plan stage A3)
- **Default secondary-electron blur 0 → 2.5 nm** (`DEFAULT_SE_BLUR_NM`): Thackeray et al. 2010 (JPST
  23(5) 631, Eq. 8) EUV-specific blur term inside their measured 11.5 nm total; models give 2.1–3.3
  (Mack 2011). No direct measurement of the SE blur alone exists; documented as such. Chain total
  blur is now 9.4 (acid) ⊕ 2.5 = 9.7 nm (no radius-of-gyration term). Preset `CAR` 5 → 2.5,
  `nonCAR`/`HighNA` marked unsourced; CLI `--se-blur` defaults follow (simulate, process window,
  calibrate), the unsourced "5–10 realistic" help text is gone.
- **Finding:** with `se_blur_nm = 0` the stochastic full_chem chain was physically broken, not
  "ideal": white per-pixel Poisson noise on a 0.17 nm grid (0.007 photons/pixel) saturates the
  Dill law on single-photon spikes and the line does not print (LWR = 0). A `UserWarning` now fires
  for `enable_stochastic` with zero blur; `se_blur_nm < 0` is rejected. The aerial_threshold model
  never applied the SE blur and still does not (it thresholds the aerial image directly).

### Changed (physics, 2026-09-06, plan stage A2)
- **Default Dill C 0.08997 → 0.0152 cm²/mJ; default deprotection rate k 1.4 → 7.87 s⁻¹.** The old C
  was a PROLITH fit (Yamamoto 2011 / Sekiguchi 2011) that lumps PEB kinetics into the exposure
  parameter (it even changes with quencher loading, Sekiguchi IEEJ 2013) and implied 6 acids per
  absorbed photon against measured 1.4–2.1. Direct measurements in this model's convention,
  acid = G0·(1 − e^{−C·E}) with incident E, give 0.010–0.05: LBNL base titration (OSTI 1004159,
  Table 3; MET-2D 0.0152 — the same resist Sekiguchi fits at 0.090) and PSI/ARCNL bleaching
  (Fallica et al. 2017, SPIE 10143, seven EUV CARs 0.010–0.021). Yamamoto's Fig. 3/4 fix only the
  rate k·H = 0.166 s⁻¹ at 1.4 mJ/cm², so k is re-derived from the same data; Fig. 3/5 anchors are
  kept (P(60 s) 0.177, threshold 0.764 mJ/cm²). Effect: dose-to-size +2.7 % (P = 64) / +2.9 %
  (P = 44), photon-shot-noise LWR at dose-to-size unchanged within ±3 %; stochastic goldens
  re-derived. Acids per absorbed photon now 1.0 (surface) / 1.24 LBNL-style vs their 1.39.
- CLI defaults (`--dill-C`, `--peb-k`, calibrate initial guess) follow. `Kazazis et al. 2017` in the
  pipeline comments is Fallica et al. 2017 (same paper, wrong first author).

### Added (diagnostics, 2026-09-05)
- **`pipeline.acids_per_absorbed_photon(cfg)`** – film quantum yield implied by the configured
  Dill C, PAG density G0 and absorption coefficient (C·G0 / (N_ph·α), low-dose limit). Measured
  values are 1.4–2.1 acids per absorbed photon (Brainard/LBNL, OSTI 1004159, Table 3: EUV-2D
  2.08/1.94, MET-2D 1.39, XP-5496 1.45) and ≈2 (Kozawa, JPST 28(4) 501). The defaults imply
  **6.0** – C (PROLITH fit, Yamamoto/Sekiguchi) and G0 (Mack 2011) are not mutually consistent.
  `tests/test_acid_yield.py` pins today's value and carries the band test [1.3, 3.0] as a strict
  xfail until plan stage A2 decides which parameter moves. No default changed.

### Changed (physics, 2026-09-05)
- **Default acid diffusivity 3.3 → 4.2 nm²/s (Kang et al. 2010, measured).** The old value was
  back-calculated so that D·60 s gave Anderson 2009's 19.9 nm blur; with the acid lifetime the
  diffusion time is the effective lifetime (10.5 s), so that reasoning no longer applied and the
  implicit default blur had already become 8.3 nm. 4.2 ± 0.3 nm²/s is the FT-IR bilayer value for
  P(HOSt-co-tBA) at 90 °C (Kang, Macromolecules 43, 4275, Table 2); the resulting default blur
  σ = 9.4 nm lies inside the 7.5–12 nm band of directly measured blur lengths of named EUV CARs
  (LBNL resist PSF, Langner 2010, Thackeray 2010) without being fitted to it. Pre-registered
  preflight (log Fortsetzung 22): dose-to-size +0.6 % (64 nm pitch) / +3 % (44 nm); photon LWR
  +14 % at 44 nm, no rise at 64 nm. Caveat kept in the field comment: measured at 90 °C, the
  default PEB is 110 °C, and Kang's Arrhenius extrapolation is too uncertain to use.
- **Acid lifetime in the PEB, and the deprotection rate read from the source's own kinetics.**
  New `SimulationConfig.peb_acid_lifetime_s` (CLI `--peb-acid-lifetime`; `None`/0 = no loss): a
  first-order acid loss H(t) = H0·e^{−t/τ} (Yamamoto et al. 2011 Eq. 1 "τ", Kang et al. 2010
  "trapping") enters the closed-form PEB through the effective time τ(1 − e^{−t/τ})
  (`resist.peb.effective_reaction_time`) -- exact for the deprotection and the D·t diffusion
  length, the same approximation for the neutralisation. Defaults: `peb_k = 1.4 s⁻¹` (Kdp at
  110 °C from Yamamoto's Fig. 4 Arrhenius plot) and `peb_acid_lifetime_s = 10.5` (from the Fig. 3
  plateau). With these the chain reproduces Fig. 3 at all five read points (≤ 0.08) and, without
  any adjustment to it, the independent Fig. 5 dissolution threshold (0.75 vs ≈ 0.8 mJ/cm²);
  Table 2's PROLITH Arrhenius pair (0.0723 s⁻¹, no loss) missed both by ≈ 3.4× and no lifetime
  alone could rescue it (pre-registered preflight, log Fortsetzung 20). The two former
  `xfail(strict)` anchor tests are now real tests. Consequence: the default resist is a very
  sensitive 2011 research resist -- dose-to-size ≈ 1.3 mJ/cm² at 64 nm pitch (σ_PEB 7 nm) --
  which is a property of the source, not a target; the stochastic regression operating point
  moved to 1.1 mJ/cm² and all goldens were re-derived.
- `tests/test_stochastic_consistency.py`: two bounds that were numbers of the old operating point
  (field deviation < 0.1 px at ρ = 2000; sparse/dense LWR ratio ≤ 20) replaced by invariants
  (deviation falls ≥ 5× per two decades of density; the sparse ratio has a floor only, because
  at several nm of LWR the Mack threshold and the lateral front can only amplify roughness).
- `tests/test_quencher_sekiguchi.py`: the neutralisation closed form (`peb._reaction_limited_quench`,
  second order) is checked against Sekiguchi's (IEEJ 2013) effective Dill C versus quencher loading:
  one rate fitted on the 0.5 row reproduces the 0.05/0.10 rows within 5 % and the 0.75 row within
  30 % (known deviation), while complete neutralisation (A = H0 − q) is clearly worse. The rate
  itself is not transferable to the PEB and is not asserted.
- **Default Dill B is now computed from the resist composition (4.44 µm⁻¹), no longer Yamamoto's
  Table-2 value (1.06 µm⁻¹).** `materials.linear_absorption_coefficient_per_um(composition, density)`
  evaluates α = 4πβ/λ from the CXRO f₂ tables; for PHS with 35 % tBOC protection at 1.20 g/cm³ this
  gives 4.44 µm⁻¹ (PHS 4.0–4.2, PMMA 5.2, polystyrene 2.95). A value of 1.06 µm⁻¹ is below even
  oxygen-free polystyrene and cannot describe a PHS film; three independent measurements agree with
  the computed range (Sekiguchi 2011: 4.32/5.21 for MET-1K/2D; Fallica 2016: 4–5; Kang 2010).
  Measured consequences (pre-registered preflight, log Fortsetzung 19): absorbed photon fraction
  5.2 % → 19.9 %, dose-to-size +14–20 %, photon-shot-noise LWR at dose-to-size down by ≈ 2.5–3.5×
  (P = 44 nm: ≈ 10.6 → ≈ 4 nm). All stochastic regression goldens re-derived. The default is pinned
  to the derivation by `tests/test_absorption_coefficient.py`.
- `tests/test_stochastic_consistency.py`: the large-number-limit invariant now compares the
  sampled-molecule chain with the mean-field chain field-to-field (same tiles, same edge
  extractor) instead of against `cd_nm`, which since the sub-pixel CD uses a different edge
  estimator (arrival-time crossing) than the realisations (depth-map crossing); the two differ
  by up to ~1 px on their own and that difference was being tested by accident.

### Fixed (physics — Phase 0 of the 2026-09-04 audit, see `docs/audit_2026-09-04_vollpruefung.md`)
- **Exposure-dose convention.** `dose_mj_cm2` is now the wafer dose in a clear area (Mack 1997):
  the aerial image is divided by the multilayer's clear-field reflectivity (|r_ML|² ≈ 0.647 for
  the default stack), so an open frame delivers exactly the nominal dose. Previously the resist
  saw 0.647 × the nominal dose and every dose-to-size comparison with the literature was off by
  that factor. New result field `clear_field_reflectivity`.
- **Photon shot noise on absorbed photons.** The stochastic path now samples the absorbed
  fraction 1 − exp(−(A+B)·t) of the incident photons (5.2 % for the default film) instead of all
  of them; photon-shot-noise LWR was under-estimated 4.4× (linear) to 7.9× (measured).
- **`dill_B` was silently ignored** (`B, H, W = dose.shape` shadowed the parameter); the
  absorption coefficient was A + 1.0 µm⁻¹ regardless of configuration.
- **RCWA order labels off by one** (floor division) and **RCWA run at wafer instead of mask
  scale** (±1 orders hit the mirror outside its Bragg acceptance, 10.8× order asymmetry instead of
  the physical ≈1.2×). New `mask_demagnification` (default 4×).
- **Quench rate units:** k_Q [nm³/s] is converted to k_Q·G0 [1/s] for relative concentrations
  (Mack 2011: 3 s⁻¹, not 15).
- `absorber_taper_deg` / `mask_undercut_nm` now raise `NotImplementedError` instead of being
  silently ignored.
- **`euv calibrate` simulated the wrong line width.** The CSV loader's loop variable `cd`
  shadowed the `--cd` option, so every fit used the *last measured CD* as the nominal line
  width (found by a synthetic-FEM smoke test: the fit returned σ = 1 nm / RMSE 6.6 nm for data
  generated at σ = 7 nm). Wiring is now covered by `tests/test_cli_calibrate.py`.
- `bootstrap_fit` no longer warns "Only n / n runs succeeded" when all runs succeeded.
- **Sub-pixel line width (Eikonal model).** `cd_nm` was the count of undeveloped pixels × dx,
  i.e. quantised to 1 nm at grid 64 and 0.5 nm at grid 128; every CD-vs-dose or -vs-parameter
  curve was a staircase and the calibration objective was flat over whole parameter ranges.
  The edge is now the linear crossing of the bottom-layer arrival time with the development
  time (`resist.develop.edge_positions_from_arrival`): behind the edge the arrival time grows
  linearly at 1/R(M) per unit length, so the crossing is first-order exact. Verified against a
  4× finer grid (within 0.35 nm, monotone in dose; interpolating the developed-depth map
  instead gave a 0.8 nm sawtooth and was rejected). The column model keeps the pixel count.
  Tests: `tests/test_subpixel_cd.py`.
- **Stochastic chain no longer needs the whole 3D stack in memory.** The z-diffusion and the
  Eikonal front (Phase 2b) raised the working set of the noisy exposure → PEB → development
  chain to ~10× the `(n_layers, H, W)` field (measured), which OOM-killed the 61440-row large-N
  LER tests on an 8 GB machine. The chain now runs in y-tiles with a halo of one row more than
  the 4σ blur radius (`pipeline._noisy_depth_map`); every step is pointwise, per column, per row
  or that truncated circular convolution, so the result is the untiled one to FFT rounding
  (`tests/test_stochastic_chunking.py`). Sampled molecules are drawn per tile from generators
  seeded once from the run's RNG, so a realisation does not depend on the grouping. Fields of
  ≤ 1024 rows are a single tile drawn directly from the run RNG (unchanged results). The Eikonal
  solver, the z-blur and the FFT blur additionally process rows/layers in slices (bitwise
  identical).
- `tests/test_stochastic_consistency.py`: the "no roughness at ρ = 2000" check (passed by
  0.0002 nm) is replaced by the physical invariant LWR ∝ ρ^(−1/2) with the photon sampler off
  (measured ×150 over four decades, √10⁴ = 100); the sparse-vs-dense ordering with photon noise
  on is dropped (a +3 % effect below the estimator scatter at n_eff ≈ 9).
- **One chemistry for both chains (Phase 1).** The deterministic full_chem chain and the
  sampled-molecule chain (`exposure_stochasticity=True`) run the same PEB step: acid and
  quencher diffuse, then neutralise (Mack 2011 closed form, k_Q·G0), then deprotect. The
  deterministic result is now the large-number limit of the stochastic one
  (`tests/test_stochastic_consistency.py`). Previously the deterministic chain had no quencher and
  the stochastic chain evaluated the reaction per grid voxel, where it was effectively inert.
  New `ler_metadata["stochastic_cd_nm"]`.
- **RCWA (Phase 2a).** Three errors in the 1D solver's mode coupling, found through conservation
  laws: (1) the Redheffer star product had its two resolvents swapped (invisible for scalar/
  homogeneous cases, wrong for grating modes -- cascading two interfaces through the mode basis did
  not reduce to the direct interface); (2) the TM branch used the Laurent rule with inverted
  admittances (effective-medium limit gave R = 0.21 instead of 0.030 and did not converge); (3) the
  multilayer operator fed the E-field TM reflection coefficient to H-field amplitudes (sign). Now
  pinned by `tests/test_rcwa_physics.py`: slab == TMM, Fresnel limit, effective-medium limit,
  energy conservation R+T = 1 (2e-6) for TE and TM, multilayer operator magnitude and phase. Same
  star-product fix in `rcwa2d.py`. Effect on the EUV Ta grating is small (≈1 % in mean intensity).
- `quencher_density_per_nm3` default 0.05 → 0.0: the Dill/PEB/Mack parameters are Yamamoto
  2011's PROLITH set, which has no quencher; loading Mack 2011's base on top moved dose-to-size
  from 6.6 to 21.2 mJ/cm² with no source for the combination. Set it explicitly for a
  self-consistent parameter set.

- **Gaussian blur kernel was clamped to the image size** (`resist.exposure.gaussian_se_blur`): a PEB
  blur wider than one pitch was truncated at ~1σ and renormalised -- for the default σ = 19.9 nm
  on the 256-px grid the modulation transfer at the pitch frequency was 0.12 instead of the exact
  0.018 (6.9×; 1.7× at 14 nm, 1.09× at 10 nm). Every full_chem result with σ_PEB ≳ 7 nm (44 nm
  pitch) / ≳ 11 nm (64 nm pitch) was affected. Now an exact periodic (FFT) convolution for any
  kernel size, 4σ truncation; `tests/test_blur.py` pins the analytic MTF.
- `resist.peb.reaction_diffusion_adi`: zero-flux boundary rows in conservative flux form on both
  half-steps (mass created before: +0.14..+1.6 %); `tests/test_peb_numerics.py`.
- PEB diffusion is isotropic: the unified PEB step also diffuses along z (face-symmetric mirror
  boundaries, column total conserved); previously lateral only.
- `full_chem` NILS is now measured at the edge the chemistry prints (CD·|dI/dx|/I at the image
  level of the developed boundary); previously it used the aerial_threshold model's
  reference-dose level, which has no meaning for the chemistry chain and returned 0 whenever that
  level missed the image. NaN when no line prints. `resist_threshold_norm` no longer affects
  full_chem results at all.
- `metro.pw_metrics` returned grid-index counts under the physical keys `dof_nm`/`el_pct`; it now
  takes the `doses`/`focuses` grids and reports NaN for the physical values without them (index
  counts are available as `dof_steps`/`el_steps`).
- `resist.develop.surface_advancement_level_set`: `t_develop` is required; the `t_develop=None`
  mode (returned an all-ones mask) was dead, defective code. Docstring now states plainly that
  this is a vertical-column model without lateral dissolution.
- `mask3d.rcwa_torch._build_ml_reflection_operator`: substrate index taken from CXRO Si at the
  actual wavelength instead of the last ML layer.

### Added
- `resist.develop.eikonal_development` / `eikonal_arrival_time`: 2D (x, z) development front from
  the Eikonal equation |∇T| = 1/R(M) (fast sweeping, Zhao 2005), validated against exact
  solutions (`tests/test_eikonal_development.py`). **Pipeline default** via
  `SimulationConfig.development_model = "eikonal"` (CLI `--development-model`); `"column"` keeps
  the former vertical time-of-flight approximation. With lateral dissolution the default
  Yamamoto-2011 resist parameters print the 32 nm line at 64 nm pitch only in a knife-edge dose
  window at the default 19.9 nm PEB blur -- the column model had kept such lines alive
  artificially. At 44 nm pitch the 22 nm line prints with σ_PEB ≤ 7 nm at a dose-to-size of
  ≈ 4.5–4.9 mJ/cm² (a first coarse scan with 2.5 mJ/cm² steps had missed this window; corrected
  the same day). The stochastic regression tests run at an explicit operating point
  (σ_PEB = 7 nm, 4.0 mJ/cm²).
- Docstrings of `etch.bias` (coefficients are empirical, no source), `source.plasma` (illustrative,
  not connected to the pipeline) and `aerial.abbe` (numerical TCC overlap, scalar thin-mask) now
  state their status.
- `euv calibrate --period/--cd/--grid/--se-blur`: the simulated geometry must match the measured
  FEM; it was hard-wired to 64/32 nm regardless of the data.
- `tests/test_cli_commands.py`: smoke tests for `version`, `info`, `materials`, `make-mask`,
  `process-window` (audit item E7: 7 of 8 commands were untested).
- `tests/test_yamamoto_anchor.py`: the default resist parameters (Yamamoto et al. 2011, Table 2)
  are checked against the same paper's own measurements on the same resist (Fig. 3 FTIR
  protection ratio, Fig. 5 dissolution-rate threshold). In the standard Mack forms the chain
  deprotects ≈ 3.4× too little (P(60 s) 0.60 vs ≈ 0.18; threshold 2.75 vs ≈ 0.8 mJ/cm²). Encoded as
  `xfail(strict=True)` with the reason, plus a pin of the current numbers. Consequence documented
  in `SimulationConfig`: the shape parameters are sourced, the absolute dose scale of the default
  resist is not a validated quantity in either direction. No acid-loss knob was added (no
  published value).

### Removed
- `development_stochasticity=True` (raises `NotImplementedError`), `development_strength`,
  `development_correlation_nm`: the event-based development-noise model depended on the
  numerical layer count (LWR 1.44 nm at 21 layers vs 0.17 nm at 41) and used a fitted, unit-less
  event-rate knob. `resist.develop.stochastic_development` remains as an experimental function.
- `dill_Q` (config field, CLI `--dill-Q`, calibration parameter): it double-counted the PAG
  quantum efficiency, which lives inside Dill C (Mack 2013, Eqs. 8/10), and capped the acid yield
  at 0.5. The acid yield is now 1 − exp(−C·E). `SimulationConfig(dill_Q=...)` raises.
- `resist_threshold`, `mask_sidewall_roughness_nm`: accepted but never read.
- `resist.exposure.dose_to_acid(Q=...)`: the surviving copy of the removed `dill_Q` prefactor
  (default 0.04, capping the yield below 1) in the 2D helper used by tests and screening
  scripts; the yield is 1 − exp(−C·E) there too now.

### Changed
- Lint clean (`ruff check` + `ruff format --check`, the CI lint job): 35 files reformatted,
  over-long parameter comments in `SimulationConfig` and CLI help strings rewrapped (text
  unchanged), a dead `__main__` block referencing a removed test deleted. The CI lint job had
  been failing since 2026-09-02 (unnoticed: GitHub Actions has not run since 2026-08-31,
  spending limit).
- `_noisy_depth_map`: rows are distributed evenly over floor(H / tile_rows) tiles so that every
  tile is at least one halo long (a short remainder tile would have misaligned the interior
  slice); `edge_positions_from_arrival` puts the edge on the pixel face if the neighbouring
  arrival time is infinite (R = 0).
- Repository layout: 110+ historical audit/session reports moved out of the repository root
  (recoverable from git history; index in `docs/history/README.md`); third-party reference
  PDFs/HTML removed from version control; `testberechnungen.md` moved to `docs/`.

### Documentation
- Vesters cross-check (log Fortsetzung 23): with the fully sourced default set, the dose-scaled
  photon-shot-noise LWR at 22 nm half-pitch is 1.2–1.7× above the biased CD-SEM values of two
  NXE resists (was 3–4× before Phase 2b). Documented as a plausibility check, not a validation.
- `docs/audit_2026-09-04_vollpruefung.md`: full scientific audit of the code base. Records
  several **open physics defects** that are not yet fixed (photon shot noise computed on
  incident instead of absorbed photons; undocumented dose convention — aerial image is not
  clear-field-normalised; PEB diffusion length not sourced for the validation regime;
  quencher effectively inert in the stochastic path; `development_stochasticity` depends on
  the numerical layer count; RCWA TM factorisation is the Laurent rule, not Li's rule).
  No physics or code was changed in this release; see the report for evidence and a
  proposed order of correction.

## [1.0.0] — 2026-07-07

### Added
- **Multilayer optics** — S-matrix TMM for Mo/Si Bragg mirrors, collector.
- **Mask 3D solver (1D)** — RCWA Fourier Modal Method, stable eigenmode branch selection (50+ orders).
- **Mask 3D solver (2D)** — Crossed-grating RCWA for contact holes, islands, SRAM.
- **Aerial image** — Abbe source-point summation, Hopkins/TCC accelerator with SOCS kernels.
- **High-NA imaging** — Anamorphic 4×/8× pupil, Zernike aberrations, defocus.
- **Plasma source** — Parametric LPP Sn spectrum (in-band + out-of-band), dose model.
- **Photoresist** — Dill exposure, PEB reaction-diffusion, Mack development, stochastic LER/LWR.
- **Inverse lithography** — Differentiable forward model bridge for OpenILT.
- **CD metrology** — Sub-pixel CD extraction, process window / Bossung, SEM rendering.
- **GPU acceleration** — VRAM budget, chunked Abbe, mixed precision.
- **Etch bias & calibration** — Empirical etch model, scipy wafer-data fitting.
- **Layout I/O** — GDSII / OASIS via gdstk, rasterization.
- **REST API + Web UI** — FastAPI service + browser dashboard (GitHub-dark theme).
- **CLI** — 7 commands: simulate, make-mask, process-window, materials, serve, bench, info.
- **Docker deployment** — Multi-stage Dockerfile, docker-compose (API + CLI).
- **Sphinx documentation** — API reference, Jupyter tutorials.
- **CI** — GitHub Actions (lint + test matrix 3.10–3.12).
- **504 tests, all passing.** Physics benchmarks (energy conservation, RCWA↔TMM cross-validation, Fourier convergence).

### Known limitations
- Scalar 2D RCWA omits TE↔TM cross-coupling (zeroth-order values accurate).
- RCWA1D uses one permittivity profile per layer (multi-material Toeplitz planned).
- Rust rigorous engine and CNN M3D surrogate on roadmap.

## v0.1.0 (2026-07-07)

Initial public release of the Open Source EUV Lithography Simulator.

### Physics engines
- **Multilayer optics** — S-matrix transfer-matrix method (TMM) for Mo/Si
  Bragg mirrors, collector geometry, interdiffusion correction.
- **Mask 3D solver (1D)** — Rigorous Coupled-Wave Analysis via the Fourier
  Modal Method with a numerically stable S-matrix cascade and correct
  eigenmode branch selection (stable to 50+ Fourier orders).
- **Mask 3D solver (2D)** — RCWA for crossed gratings: contact holes,
  rectangular islands, SRAM-like patterns.
- **Aerial image** — Abbe source-point summation (physically honest with
  mask-3D) plus the Hopkins/TCC accelerator with SOCS kernel decomposition
  for fast OPC loops.
- **High-NA imaging** — anamorphic 4×/8× pupil, Zernike aberrations, defocus.
- **Plasma source** — parametric LPP tin-plasma spectrum (in-band + out-of-band)
  and dose model.
- **Photoresist** — Dill exposure kinetics with secondary-electron blur,
  post-exposure-bake reaction-diffusion, Mack development, and a stochastic
  LER/LWR overlay.
- **Inverse lithography** — differentiable forward model bridge for OpenILT.

### Tooling
- **CD metrology** — sub-pixel CD extraction, NILS, process window / Bossung,
  SEM-style rendering.
- **GPU acceleration** — device selection, VRAM budget manager, chunked Abbe.
- **Etch bias & calibration** — empirical etch bias, scipy-based wafer fitting.
- **Layout I/O** — GDSII/OASIS import/export via gdstk, rasterization.
- **REST API + Web UI** — FastAPI service with a browser dashboard.
- **CLI** — `euv simulate`, `make-mask`, `process-window`, `materials`,
  `serve`, `bench`, `info`.

### Verification
- **504 tests, all passing.**
- Physics benchmarks: energy conservation, RCWA↔TMM cross-validation,
  Fourier-order convergence, Fresnel-limit checks, normal-incidence symmetry.

### Deployment
- Docker + docker-compose (API and CLI images, CPU-only PyTorch).
- Sphinx documentation and Jupyter tutorials.

### License
- Apache-2.0.

### Known limitations
- The scalar 2D RCWA omits TE↔TM cross-coupling, so 2D efficiency sums are
  not strictly energy-conserving (zeroth-order values are accurate). Full
  vector 2D RCWA is planned.
- RCWA1D applies one permittivity profile to all layers; true
  alternating-material stacks (per-layer Toeplitz) are a planned enhancement.
- A Rust rigorous-solver backend and a CNN M3D surrogate are on the roadmap
  for production-scale runtimes.