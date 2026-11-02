# Changelog

All notable changes to euvsimulator are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [2.3.0] - 2026-10-30

### Fixed (2026-10-30)
- `optics.multilayer`: the Mo/Si bilayer was built Mo-then-Si, so the Ru cap sat on Mo. The
  published stacks are Si-terminated (Yan et al., JVST B 25, 1859, 2007; van Setten et al.,
  SPIE 7545, 754503, 2010), and the cap belongs on that Si. With the cap on Si the roughness-free
  TMM at 13.5 nm, 6 deg, 50 bilayers gives a clear-field reflectivity of 0.73216 instead of
  0.64697; the absorber reflectivity drops from 0.0129 to 0.011247 and the duty-weighted mask
  mean rises from 0.3299 to 0.3717. Every golden that depends on the mask was re-measured: default
  CD 26.7034 -> 27.2926 nm, NILS 4.5018 -> 4.8309, legacy LER/LWR 0.9779/1.5564 -> 0.9459/1.7067
  nm, large-N LER/LWR 3.3562/6.3593 -> 3.7996/7.3268 nm, n_eff 45.28 -> 37.03, l_int 11.38 ->
  13.95 nm. `NXE1716_DOSE_SCALE_CALIBRATION` was re-bisected on the new mirror: 1.6572 -> 1.70648
  (prints CD 22.0 nm at 11.0 mJ/cm2 again); the uncalibrated dose-to-size moves from 18.03 to
  18.78 mJ/cm2. Notebooks and docs recomputed. The phase of the multilayer reflection coefficient
  moves from 0.56 + 0.58j to 0.208 - 0.830j; only differences of it are physical.
- `data/cxro/Si.csv` came from a CXRO release whose Si K-edge rows fell (1838.8, 1839.0, 1838.9),
  which a wavelength grid cannot tolerate. Replaced with the 2026-08-11 release (1838.80, 1839.00,
  1843.45) and `materials.py` now raises `ValueError` when a loaded table has a falling energy.
  f1 at 91.5391 eV moves from 0.306962 to 0.307208. Be, Er, Nb and Y also changed in that release
  and are *not* adopted; `scripts/download_cxro.py` records why.
- `resist.stochastic`: `residue_island_fraction()` reports the share of rows that carry resist
  that is detached from the main line, as `ler_metadata["island_row_fraction"]`. Diagnostic only;
  edges, CD and LER are untouched (B3.1).
- `pipeline`: a `pag_density_per_nm3` other than the default 0.2 with the default `peb_k` now warns
  that only the neutralisation scales with G0, not the deprotection (B3.2).

### Removed
- Two machine-facing schema files. They described an MCP server with three
  tools and an agent endpoint, neither of which exists in this repository, and their schemas
  had drifted from the real parameters (illumination `quadrupole`, resist model `stochastic`, the
  removed `Q` output field, "48 wheel configurations" for what is 3 operating systems × 4 Python
  versions, "534 tests", and a URL that returns 404). Git keeps both files in the history.

### Changed
- `llms.txt` rewritten, every claim checked against the working tree: no
  "physics-accurate" claim, no reference to the non-existent `docs/cli.rst`, no `euv notebook`
  command, the real `SimulationConfig` defaults and `SimulationResult` fields, development named
  as an Eikonal front plus a vertical-column model (was "level-set" and "PEB (ADI solver)"),
  `etch` and `opc` marked as present but not wired into the pipeline or CLI, test counts carrying
  their date, and an explicit list of interfaces that do not exist.
- CI: the per-cell notebook timeout is 2400 s (was 900 s) and the notebook job is skipped for
  tags. The v2.2.1 tag run timed out after 900 s in notebook 05's `dill_C` loop while the
  identical commit passed on `main`, where notebook 05 took 994 s in total; hosted-runner speed
  varies by more than 2× on that cell, and the limit is a hang guard, not a performance budget. A
  tag commit has already run this job on `main`, so repeating it occupies about 30 minutes of
  runner time and verifies nothing new.

### Fixed
- `mask3d.geometry`: `standard_euv_mask` listed the Ru capping layer first and as etched, and
  `build_permittivity_profile` took the line permittivity from the last layer but the height from
  all layers, so the default mask became a 62.5 nm Ta grating (the 2.5 nm cap counted as Ta in
  the lines and as vacuum in the spaces). The cap is now the blanket bottom layer
  (`etched=False`, order `[absorber, cap]`), only etched layers form the grating (60 nm),
  `total_absorber_thickness_nm` counts etched layers only, and `build_permittivity_profile`
  raises `ValueError` for a stack without etched layers or with etched layers of different
  refractive index. Model the cap in the multilayer stack (`mo_si_stack(capping_layer=...)` as
  `ml_stack`), as `run_simulation` does. The pipeline is unchanged (it passes a Ta-only stack).
  The module docstring names the real functions.
- `resist.develop.developed_depth_from_arrival` (Eikonal path, the default development model)
  reported a fully cleared column as (N+1)*dz, while its docstring and the column model give
  N*dz; the depth jumped by one dz when the last layer cleared, and the stochastic LER/LWR
  sub-pixel edge interpolation used a different "cleared" plateau than the column model. Now
  N*dz. Deterministic CD and NILS are unchanged. The stochastic edges come from the arrival
  time since the 2026-10 changes, so this plateau no longer moves the stochastic regression pins;
  those were re-measured once after all 2026-10 fixes (see Tests).
- `resist.develop` docstrings: `M_th` is the inflection point of the Mack rate curve, not the
  point where R = (R_max + R_min)/2 (n = 5, M_th = 0.5, R_max = 100: R(M_th) = 41.98 instead of
  50.05 nm/s). Documentation only.
- The `--resist-preset` help text said "CAR (5nm)" while `RESIST_PRESETS["CAR"]` is
  `DEFAULT_SE_BLUR_NM` = 2.5 nm, as `test_se_blur_default` asserts; the `pipeline` module
  docstring repeated the same stale 5.0. The help now also states that `nonCAR` and `HighNA` are
  unsourced placeholders.
- aerial_from_orders sampled the period at linspace(-P/2, P/2, G): pitch P/(G-1) and the last
  sample a copy of the first, while the pipeline, nils() and the resist chain use dx = P/G and
  treat the G samples as one period. Every length taken from the image was low by (G-1)/G, and a
  line moved across the array boundary changed CD and NILS (G = 64: 24.72 against 25.29 nm). The
  samples now sit at x_k = -P/2 + k P/G; the crossing loops of nils() and
  _cd_via_aerial_threshold include the pair (G-1, 0); the CSV export and the GUI plot use the
  pitch P/n. Default benchmark (aerial_threshold, grid 256): CD 27.62 -> 27.67 nm, NILS
  4.9685 -> 5.0330; CD from grid 256 to 2048 now changes by 0.002 nm (was 0.042). full_chem at
  64/32 nm, 1.1 mJ/cm2, SE blur 5 nm, PEB sigma 7 nm: CD 37.81 -> 38.05 nm; NXE1716 calibrated
  preset 22.00 -> 22.23 nm (inside its 0.3 nm test band, calibration factor not refitted).
  LER/LWR regression pins re-derived: seed 42 now draws a different noise realisation, the
  large-N LER mean over seeds 1, 2, 3, 42 is 3.65 nm before and after. The NILS reference test
  now blurs with the exact Gaussian MTF (its 3-sigma convolve2d was 0.04-0.06 off at 10 nm);
  tolerance 2e-3. The bias had also hidden most of a first-order full_chem CD error of about
  one pixel (grid 64 / 256: 35.44 / 34.69 nm, limit about 34.44 nm); the grid-64 against
  grid-256 test bound is 1.0 nm (was 0.5) until that is fixed.
- _compute_tcc_matrix: a source that holds no point of the 256-point integration grid
  (0 < sigma < ~0.011 for a conventional source) took the coherent shortcut TCC = 1 for every
  order pair, so an order outside the pupil that the (1 + sigma) order cutoff admits entered the
  image at full strength (64 nm pitch, duty 0.35, NA 0.33: Imax 1.131 instead of 1.482 for a 1/0
  grating at sigma 0.005). The shortcut now applies the pupil, TCC(i, j) = P(f_i) P(f_j);
  sigma = 0 is bit-identical.
- Legacy quasar source (illumination_shape "quasar" without sigma_inner): the pole test
  rotated the coordinates by 30 degrees, so the four poles sat at 15/105/195/285 degrees instead
  of on the diagonals (45/135/225/315 degrees) like aerial.source.quasar and the scanner-style
  sector branch. TCC(0,+1) at 36 nm pitch, NA 0.33, sigma 0.8 is now 0.382 (was 0.283). Other
  source shapes are unchanged.
- aerial.source.quasar() put its four pole centres at (+-0.5 sigma, +-0.5 sigma) with pole radius
  sigma, so the poles overlapped each other and the origin and merged into one blob of radius 0.34
  (default sigma 0.2); sigma_out only clipped and opening_angle_deg was never read. The poles are
  now disks of radius sigma centred on the 45 deg diagonals at radius sigma_out - sigma: four
  separate poles, dark centre, lit radius 0.40 to 0.80 at the defaults. sigma <= 0 or
  sigma * (1 + sqrt(2)) >= sigma_out raises ValueError; opening_angle_deg is deprecated and
  ignored (DeprecationWarning). Not used by run_simulation, whose quasar is built in aerial/abbe.py.
- aerial.source: conventional(), annular(), dipole_x(), dipole_y() and quasar() divided by an
  unguarded sum, so a shape covering no grid pixel (sigma 0 or below the grid step on an even
  grid, annular with sigma_in >= sigma_out) returned an all-NaN source, which abbe_image() turned
  into an all-zero image without notice. They now raise ValueError, and annular() checks
  0 <= sigma_in < sigma_out. Non-empty sources are bitwise unchanged.
- `mask3d.rcwa2d`: the eigenproblem read `Kx² + Ky² − ε`, which with the propagator
  `exp(i k₀ q d)` made every propagating mode evanescent (a vacuum layer reflected 100 %, Ta
  1.074). Now `ε − Kx² − Ky²`, as in the 1D TE solver; a y-invariant grating reproduces the 1D
  result exactly and a homogeneous slab the Airy formula to 1e-10. The branch choice of `q` now
  follows the 1D rule (numerically real → Re(q) > 0); the old rule lost 5.5e-4 of the power at
  normal incidence. The module is documented as a scalar approximation. Not used by the pipeline.
- `diffraction_efficiency` (1D and 2D) returned `|r_m|²`, which is the power only for m = 0; it
  now weights each order by Re(kz_m)/kz_0, so evanescent orders give 0 and a lossless grating on
  a mirror sums to 1 (was 3.58 TE, 1.74 TM). R0 and the pipeline are unchanged; notebook 06 shows
  corrected non-zero orders. Solvers cast thicknesses to float64 (float32 cost ~1e-6 in R).
- RCWA convergence drivers warn when `target_rel` is not reached and return the order count
  actually used (they returned `max_orders` even when the step never reached it).
- `aerial.pupil.anamorphic_pupil` returned the full square for every input; it is now the
  mask-side ellipse (4×/8×: half the extent in y). Isotropic pupils are bit-identical to before.
  New helper `pupil_cutoff_frequencies`. Not used by the pipeline.
- `metro.process_window` / `pw_metrics`: DoF and EL are the contiguous in-spec run through the
  best point; an out-of-spec gap no longer counts (a test fixture reported 80 nm DoF across a
  gap). Exact ties for the best point in `pw_metrics` go to the largest window. Smooth Bossung
  data give identical results.
- `source.spectrum.dose_to_wafer`: in scan mode the dose is P / (field width · scan speed); the
  slit energy was spread over the whole 26 × 33 mm field, 11× too low. New parameter
  `field_width_mm`. `in_band_efficiency` defaults to the documented ±1 % window (0.135 nm, was
  0.27 nm = ±2 %). The line-width docstrings of the source model are corrected (line FWHM
  0.135 nm, 98 % inside the 2 % band). The source module stays a toy model outside the pipeline.
- source.plasma.LPPPlasmaSource.dose_rate collected Omega/pi of the in-band power (Omega over the
  hemisphere integral for the Gaussian profile), which ignores the angular weighting: 0.268
  instead of sin^2(30 deg) = 0.25 for the default 30 deg cone, and 2.0 (Gaussian, sigma 30 deg:
  4.0) for the full hemisphere, more power than emitted. It now integrates the angular profile
  over the cone; the default wafer power drops by 6.7 % (20.10 to 18.75 W), and dose_to_wafer
  with it. Solid angles outside [0, 2*pi] raise ValueError. angular_factor is symmetric in theta
  (Lambertian gave 1.0 for every negative angle). Not used by the pipeline.
- `resist.stochastic.rms_scaling_check` thresholded the rescaled Poisson count with a fixed
  value, i.e. asked "at least one acid in this pixel", and ignored `photon_energy_eV` and
  `dose_to_energy_factor`; it returned exponents of +0.5 to +2.6. It now blurs (`se_blur_nm`,
  default 2.5) and thresholds at a fixed fraction of the deterministic maximum, as notebook 05
  does, and gives -0.53 ... -0.56 in the small-noise regime.
- `resist.exposure.dose_to_acid` clips negative doses (a dose of -5 gave acid -0.65).
- `calibrate_on_synthetic` takes `initial_params`; the default start stays target ± 5 %.
- docker-compose publishes the API on 127.0.0.1 only (the API has no authentication, see
  SECURITY.md), and the CXRO data volume now targets the installed package, which is where
  `materials.py` reads; the former target `/app/euvsimulator/data` had no effect. Not tested in a
  container.
- MPS is not used (float64/complex128), RCWA 2D is scalar, NILS gate tolerances.

- `aerial.hopkins.compare_hopkins_abbe` passed an uncentred spectrum to two functions that
  expect a centred one; Hopkins and Abbe then differed by 47 % for a dipole source. Centred:
  1.6 % (dipole), 0.7 % (conventional). The former strict-xfail test is a normal test again.
- `aerial.abbe.abbe_image` used the pupil array as given, which is only right when the pupil
  radius in FFT pixels equals G/2 (pixel = λ/(2 NA)); otherwise one branch cut a square out of the
  pupil and the other applied the unit circle at the wrong scale. The pupil is now resampled to
  its FFT-grid radius (aberration phases kept); bit-identical at pixel = λ/(2 NA).
- `opc.openilt_bridge`: the forward pass ignored the pixel size (fixed 64 nm per pixel: no optical
  filtering at all) and `optimize()` returned sigmoid(p), which tests then passed through a second
  sigmoid. New `pixel_nm`, `na`, `sigma`, `wavelength_nm`, `resist_from_mask()`, and a warning when
  the pupil spans less than one FFT pixel; `optimize()` documents its continuous [0, 1] return.
- `calibrate`/`reaction-diffusion`/`peb temperature` tests: bootstrap on seeded synthetic data
  with known truth (was unseeded random data, 0-6 of 10 runs converged); the reaction-diffusion
  PDE is checked against NIST's own model with NIST's full Table 1 (within 7 %) and at second
  order in time against an RK4 reference; the PEB-temperature test compares like with like (kT
  under NIST's law: factor 2.0 between two resists, was tau against 1/kT).
- NIST 2009 Table 1 does list k_Q = 1.6 ± 1.0 nm³/s (docs/physics.md, pipeline comment and test
  said or implied otherwise); the chain's 1.2 lies inside that range.
- `test_pipeline`: NILS measured at dose-to-size (1.314 mJ/cm², CD 32.0 nm, NILS 2.27; 1.348 / 2.37
  before the 2026-10 sampling and phase-reference fixes) instead of
  a 50.6 nm line; first-order grid convergence; the TE/TM intensity averaging is checked inside
  the pipeline.
- NXE1716 calibrated preset: the factor on `peb_k` was the dose ratio 19.67/11.0 = 1.788, which
  assumes the dose-to-size scales as 1/k; the preset printed 20.35 nm instead of 22 nm at the
  measured 11.0 mJ/cm². `NXE1716_DOSE_SCALE_CALIBRATION` is now the directly calibrated 1.7392
  (CD 22.000 nm at 11.0); the dose ratio stays available as `NXE1716_DOSE_GAP`. Combining
  `calibrated_dose_scale` with `explicit_quencher` raises ValueError: the neutralisation does not
  scale with k (the analytical quencher variant printed at 15.0 instead of 11.0). The GUI label
  shows the factor (×1.66 after the 2026-10 recalibration).
- `scripts/gen_notebooks.py` removed. It rewrote notebooks 04-06 unconditionally from a state
  several revisions old (e.g. 0.04 instead of 0.2 acids per incident photon in notebook 05) and
  called `rms_scaling_check(dx=...)`, a keyword that no longer exists; running it would have
  replaced the maintained notebooks. Git keeps it in the history.
- run_simulation(cfg, key=value) applied the overrides with setattr on the caller's cfg: the
  caller's object kept them, __post_init__ did not run (dose_mj_cm2=-1.0 was accepted;
  peb_temperature_c=100 left peb_k at 10.947 and the acid lifetime at 7.54 s instead of 4.647
  and 16.33 s), and a misspelled name was stored silently. The overrides now go through
  dataclasses.replace like the constructor path; an unknown name raises TypeError.
- run_simulation built the Mo/Si multilayer without energy_eV, so the Mo, Si and Ru n,k were
  always taken at 91.84 eV while substrate and absorber used hc/wavelength_nm. At 13.0 nm the
  clear-field reflectivity was 0.3562 instead of 0.1508 (14.0 nm: 0.0902 instead of 0.1301). At
  the default 13.5 nm the energy moves by 1.5e-4 eV: R_clear +1.6e-6, default CD +5.4e-6 nm.
- The legacy LER estimator ignored ler_passband_nm while LWR and the large_n estimator applied
  it, so LER could exceed LWR (grid 64, seed 3, band 10-40 nm: LER 1.5464 nm, LWR 0.3382 nm).
  extract_ler now takes passband_nm (default None, unchanged); with the band LER is 0.1949 nm.
- `pipeline`: stochastic runs on a GPU crashed at the first realisation. `_noisy_depth_map` drew
  its tile seeds and the development-noise seed with `torch.randint(..., device="cpu")` from the
  run's generator, which lives on the simulation device, and PyTorch rejects a CUDA generator
  there. With the defaults (grid 256, `stochastic_ler_grid_y` 4096: four tiles) every
  `enable_stochastic=True` run with `device="auto"` on a CUDA machine failed. The seeds are now
  drawn on the generator's device and moved to the CPU; CPU results are bit-identical.
- `stochastic_seed=None` is documented as random but repeated the same noise on every run: a
  fresh `torch.Generator` starts from a fixed default seed (two unseeded runs gave LWR 1.8585 nm
  both times). Unseeded runs now seed the generator from the operating system
  (`Generator.seed()`), so they are independent samples and not reproducible; runs with an
  explicit seed are unchanged.
- A `run_simulation` progress hook that returned `None` (one that only reports) cancelled the run
  with `SimulationCancelledError` at the first realisation. `None` now continues; `False` (or any
  other falsy value) still cancels. `ProgressHook` is typed `Callable[[int, int], Optional[bool]]`.
- SimulationConfig rejects an unknown resist_model with ValueError. Any string other than
  "full_chem" (e.g. "full-chem", also via euv simulate --resist-model) silently ran the
  aerial-threshold model and returned LER = LWR = 0.
- presets.met2d_config rejects a blur_metric other than "contact" or "corner" with
  ValueError; every other value (e.g. "Contact") silently selected the corner blur
  (sigma 14.78 nm instead of 10.11 nm).
- peb_sigma_diff together with peb_model="reaction_diffusion" now warns. The concurrent PEB
  has no single blur and ignores the value; the MET-2D preset's measured 10.1 nm became
  sqrt(2 * 4.2 * 90) = 27.5 nm from peb_D and peb_t_bake without notice. The field comment
  and the GUI help now say "analytical PEB model only".
- absorber_taper_deg / mask_undercut_nm raise NotImplementedError on the default thin-mask
  path too. The check sat inside the use_rcwa branch, so the thin mask accepted any value
  without effect, although the API, notebook 06 and the 2.0.0 entry below said otherwise.
- aerial_threshold: a period in which nothing develops (threshold above the whole image, low
  dose) reports CD = pitch instead of 0, as full_chem does; CD = 0 stays reserved for a fully
  cleared period. CD(dose) is now monotone at the low-dose end (64/32 nm, grid 128: 64.0,
  57.4, 50.6 nm at 4.1, 4.3, 5 mJ/cm2; was 0.0, 57.4, 50.6). NILS is unchanged. The tests
  test_dose_1_ok and test_dose_1e_12_ok now expect 64 nm.
- resist.stochastic.photon_deposition_shot_noise, resist.exposure.sample_pag_quencher_acid and
  resist.develop.stochastic_development: called without a seed or generator, they created a
  fresh torch.Generator, whose default seed is the fixed value 67280421310721, so every such
  call drew the same noise (two calls gave bit-identical results although the docstrings said
  random or non-reproducible). The fresh generator is now seeded with Generator.seed(). Calls
  with a seed or an explicit generator are unchanged; run_simulation always passes its own
  generator to these functions.
- photon_deposition_shot_noise docstring: the mean of D_eff is the SE-blurred dose blur(dose),
  not dose; the docstring called it unbiased. The code is unchanged.
- Removed the private resist.stochastic._generate_photon_shot_noise. It had no caller, ignored
  its acid argument, returned a mean of QE squared instead of the acid concentration, and its
  docstring claimed that poisson_shot_noise used it.
- metro.sem_render.add_edge_roughness: lwr_nm was not the width roughness. Each contour point got
  independent noise N(0, ler²) + 0.5·N(0, lwr²), so at the defaults (2.0 and 2.0 nm; straight
  32 nm line, 2000 points per edge) the edges had σ 2.21 and 2.24 nm and the width σ 3.23 nm.
  Points at the same position along the long axis now share a placement draw and a width draw:
  each edge has σ = ler_nm and the width σ = lwr_nm (2.01, 2.02 and 2.04 nm). lwr_nm above
  2·ler_nm and negative values raise ValueError; rng_seed uses a local generator instead of
  resetting the global torch RNG. Not used by the pipeline.
- `metro.cd`: `extract_cd_1d`, `extract_cd_2d` and `extract_multiple_lines` paired the edges by
  list index, so a profile that began inside a feature (a line cut by the left border) returned
  the neighbouring space (44 nm for a 20 nm line at 64 nm pitch), and `extract_cd_2d` a left edge
  right of the right edge; `mode="space"` had the mirror bug. A feature cut by the border is now
  skipped. Not used by the pipeline.
- `metro.cd.extract_multiple_lines` cut the middle row into stripes of `pitch_px`, so a line on
  a stripe edge was cut apart and the space was reported instead (12 px lines centred on the
  stripe edges gave [28, 28, 28, 28] px). It now measures every complete line on the whole row
  and returns one value per line ([12, 12, 12] px); `pitch_px` < 1 raises ValueError.
- `metro.cd.compute_nils` returned the signed image log-slope in 1/nm while its docstring
  promised the NILS. The default output is unchanged and now documented as the log-slope; the
  new argument `cd_nm` returns the Mack NILS CD · |dI/dx| / I (3.137 at CD 32 nm where the
  log-slope is 0.098 1/nm). An edge outside the profile returns 0.0, and near the ends the
  difference step stays inside the profile (the clamped sample had lowered the slope, by 25 %
  at 0.5 nm from the end of a linear ramp).
- `metro.cd.extract_contour` sorted all boundary pixels, including holes and other features, by
  angle around the centroid, which is a polygon only for star-shaped features (an L shape came
  back with IoU 0.40), and the pixel-centre points shrank every feature by one pixel per axis in
  `render_sem`. It now traces the outer boundary of the first feature along the pixel edges, and
  `render_sem` gives that feature back pixel for pixel. Holes and further features are not
  returned.
- mo_si_stack(gamma=...) and SimulationConfig.ml_gamma kept d_mo_nm and set the period to
  d_mo_nm / gamma, so changing the Mo fraction also moved the Bragg peak (13.5 nm, 6°, 50
  bilayers: Γ 0.45 gave period 6.222 nm and R 0.042, Γ 0.35 gave 8.0 nm and R 0.0005, against
  R 0.647 at 6.9 nm). Γ now splits the fixed period d_mo_nm + d_si_nm (Γ 0.45: 3.105/3.795 nm),
  values outside 0 < Γ < 1 raise ValueError, and MultilayerStack.description reports the
  thicknesses actually built (it printed the unadjusted d_mo_nm/d_si_nm). Runs with
  ml_gamma=None (the default) are unchanged.
- Docker: neither image could be built. Both Dockerfiles installed every dependency and the
  package itself through the PyTorch CPU index (--index-url replaces PyPI, and that index answers
  403 for scipy, fastapi, typer, gdstk, matplotlib and wheel), and the builder stage ran
  pip install . without src/, which pyproject.toml needs (packages.find where=["src"]). torch now
  comes alone from the CPU index, everything else from PyPI, and src/ is copied into the
  builder; the unused copy of src/ in the runtime stage is gone. tests/test_docker.py checks both
  points. CI still builds no image, and on arm64 hosts gdstk has no wheel and needs a C++ build.
- `scripts/download_cxro.py` wrote to `<repo>/data/cxro`, a directory nothing reads, so the
  advice in the loader's FileNotFoundError and in the API's 404 ("Run python
  scripts/download_cxro.py first") could not fix a missing table. It now writes to
  `euvsimulator.materials.DATA_DIR` (`src/euvsimulator/data/cxro` in a source checkout).
  `scripts/download_cxro.sh` wrote raw `.nff` files to the non-existent `src/euv/data/henke`; it
  is now a wrapper around the Python script.
  The unused placeholder `data/.gitkeep` is removed.
- docs/api/modules.rst: all 26 automodule directives named the package euv, which does not
  exist; they now name euvsimulator.*, and tests/test_docs_api_modules.py checks every target.
- docs/conf.py: the source path pointed one directory above the repository (Sphinx runs conf.py
  from docs/), and release said 1.0.3; it now uses <repo>/src and euvsimulator.__version__.
- README: the docs build command was cd docs && make html, but there is no docs/Makefile; it is
  now sphinx-build -b html docs docs/_build/html.
- `optics.multilayer.interdiffusion_correction` inserted a vacuum layer (n = 1) of thickness sigma
  at every interface without taking it from the neighbours and applied no damping, so every
  period grew by sigma and the mirror was detuned (50 Mo/Si bilayers, 13.5 nm, 6 deg, sigma =
  0.5 nm: R 0.735 -> 0.014). It now inserts a 2 sigma layer with the mean index of its neighbours
  (or `n_interdiffused`), carved out of both neighbours: the period is kept and R is 0.686, within
  1 % of the Nevot-Croce value 0.681. Not used by the pipeline.
- `mo_si_stack(grading_parabolic_nm=A)` (`SimulationConfig.ml_grading_parabolic_nm`) added
  `A * (1 - cos(pi z))`, a one-sided ramp from 0 at the top to 2A at the bottom; the docstring
  promised the nominal period at the centre and +A at top and bottom. It now adds
  `A * (2z - 1)**2`. The default 0.0 is unchanged; runs with a non-zero value change.
- `MultilayerStack.period_nm` summed the first two layers, i.e. Ru + Mo = 5.3 nm for the default
  capped stack; it now sums the bottom bilayer (6.9 nm).
- REST API: an explicit `null` for a non-nullable config field (e.g. `grid`, `na`, `absorber_material`, `dose_mj_cm2`) in `/simulate`, `/jobs` or `/estimate` is now a 422 validation error instead of an HTTP 500 (`TypeError`); `null` stays valid for the `Optional` fields such as `sigma_inner` or `ler_passband_nm`.
- REST API: an `absorber_material` or `ml_capping` element without CXRO data (e.g. a typo such as `Xx` or `ta`) is now reported by the physics check as a 422 (and listed by `/estimate`) instead of failing inside `/simulate` with an HTTP 500 (`KeyError`); a cap of `none` or zero thickness is not looked up and stays valid.
- `aerial_from_orders`: defocus ignored the source point. The paraxial defocus phase was attached
  to each diffraction order with its on-axis value phi_m = -pi*z*m^2*lambda/Lambda^2, which is
  exact only for a coherent on-axis source. Order m under source point s passes the pupil at
  s + f_m, so the phase now sits inside the TCC integral (`_compute_tcc_matrix(..., focus_nm=)`).
  Checked against an independent NumPy Abbe sum (`tests/test_defocus_abbe_reference.py`): with
  the old code, conventional sigma 0.8 at 64 nm pitch and 100 nm defocus had contrast 0.479
  instead of 0.581, and the 0.62/0.90 90 deg dipole at 36 nm pitch and 50 nm defocus had 0.056
  instead of 0.768. In focus nothing changes (bit-identical TCC; default CD 27.62 nm, NILS
  4.9685). Through focus the numbers change: default configuration at -50/+50 nm CD
  26.77/26.73 -> 25.84/25.83 nm, at +100 nm CD 0 -> 14.18 nm; with `use_rcwa=True` the NILS peak
  at +25 nm (5.40) flattens to 4.73 against 4.68 in focus. Bossung, DoF/EL and best-focus
  results from earlier versions (notebooks 04 and 06) have to be recomputed.
- full_chem sub-pixel CD: the edge now comes from the arrival time at the film bottom
  (T[-2], z = film thickness), the criterion the developed-pixel map uses. It came from
  T[-1], one layer below the film, so the CD was too wide by an amount that grew with the
  layer spacing (default resist, 1.0 mJ/cm2, grid 256: 42.293 -> 41.925 nm at 21 layers,
  42.616 -> 41.675 nm at 11 layers; 1.3 mJ/cm2: 31.876 -> 31.779 nm). Between 21 and 41
  layers the CD now moves by 0.05 nm (was 0.16 nm), and it agrees with the stochastic chain's
  depth-map width to 0.02 nm (was 0.35 nm). NILS, LER and LWR are unchanged.
  NXE1716 calibrated preset at 11.0 mJ/cm2: 22.000 -> 21.770 nm
  (the calibration constant 1.7392 is not re-fitted here).
- Thin mask: the absorber and the space reflectance now refer to one plane, the absorber top
  (the space reflectance gets the vacuum round trip exp(2ikd cos θ) of the absorber height). Until
  now they referred to planes 60 nm apart and arg(a/b) was 179.0° instead of −123.5° for the
  default Ta mask. Results change: default CD 27.67 → 26.70 nm, NILS 5.0330 → 4.5018; a thin mask
  with this absorber now shifts best focus by itself (+10 nm at 64 nm pitch, notebook 06). The
  RCWA path already used one plane and is bit-identical; its empty-grating order now equals the
  thin-mask space reflectance.
- NXE1716 dose calibration re-fitted after the sampling, film-bottom and phase-reference fixes:
  `NXE1716_DOSE_SCALE_CALIBRATION` 1.7392 → 1.6572; the uncalibrated chain prints 22 nm at
  18.70 mJ/cm² instead of 19.67 (`NXE1716_DOSE_GAP` 1.79 → 1.70; explicit quencher 18.73).
- `peb_model="reaction_diffusion"` without `peb_temperature_c` used the analytical-law rate
  10.947 with the trapping-law `k_trap`; it now defaults to the trapping-law pair (8.929, 0.2076,
  Yamamoto Fig. 3). An explicitly given `peb_k` is never rewritten; the structural bands derive
  the reaction-diffusion corner's rate from the base's own law (GUI/REST bands included).
- `SimulationResult.absorber_reflectivity` is the absorber's own reflectivity |r_abs|² (0.0129
  for the default mask) instead of the duty-weighted mask mean (0.33), which is now the new field
  `mask_mean_reflectivity`. GUI, CLI JSON and REST carry both.
- `run_simulation` no longer sets torch's global default dtype to float64; every tensor that
  relied on it has an explicit dtype. Caller code creating tensors on MPS after a simulation
  failed with "MPS framework doesn't support float64".
- Input validation: `SimulationConfig` rejects invalid optics and geometry (wavelength, NA,
  sigma, period, line width, grid, odd RCWA order count); the CLI reports it as a message, the REST
  API as 422. Reversed or degenerate process-window and bands ranges are rejected. `euv calibrate`
  gives readable CSV errors, treats an empty `cd_nm` as a site without measurement and rejects
  parameters it cannot fit; the bands use every fitted parameter.
- RCWA: the absorber line is centred like the thin-mask line, and the grating profile is sampled
  where the FFT reads it (edge cells get their area fraction). The tiled sampled-molecule chain
  draws halo molecules from the neighbouring tile's own sample.
- `ler_lwr_estimate` blurs each noisy acid realisation and takes sub-pixel edges (the same defect
  as `rms_scaling_check`); `extract_cd` handles uniform rows and offers a periodic search;
  `abbe_image` documents `period_m` as the pixel pitch and filters by default;
  `compare_hopkins_abbe` compares at the TCC pixel only; `mo_si_stack(substrate=...)` sets the
  substrate index; `euv process-window` warns when DoF or EL is not resolved; the REST API and GUI
  accept `dipole_x`; full_chem-only options are marked in CLI, field help and GUI.
- Documentation re-measured after these fixes (README, llms.txt, physics.md,
  quickstart, tutorials, help texts); numbers that could not be re-measured are marked "measured
  before the 2026-10 fixes". All six notebooks re-executed; their summaries quote the new outputs.

### Tests
- Tests that could not fail now test something: the `or` in the process-window equality, the
  empty `pass` tests in `test_hopkins` (annular with sigma_inner = 0; an analytic circle-overlap
  reference for the TCC), four stochastic scaling tests without an effective assert, the
  never-negative dose test, a "within measured band" test that lowered the band edge by 20 %,
  RCWA/TMM comparisons whose tolerance exceeded R itself, and a uniform-layer test against a
  different geometry. The Hopkins/Abbe dipole mismatch (47 %) was the centring error B1.7; the
  comparison is a normal test again with a 2 % bound instead of passing a 50 % bound. `test_cxro_loader.py` (byte-identical to
  `test_materials.py`) removed. Each changed test states the measured values in its docstring.
- Regression pins re-measured after the sampling, film-bottom and phase-reference fixes (default
  CD/NILS, stochastic LER/LWR and their metadata, legacy passband, temperature override); earlier
  values are kept in comments. Tests for `ler_lwr_estimate` and the stochastic fixtures now cross
  an edge (they used `indexing="ij"` and asserted only types).

## [2.2.1] — 2026-09-11

Maintenance release: corrected notebooks, a safer server default, the NILS fix and
cross-platform CI (Linux, macOS, Windows; Python 3.10–3.13). No change to the physics.

### Changed
- README badges are live: CI status (GitHub workflow badge; the pipeline runs the tests on Linux,
  macOS and Windows with Python 3.10–3.13 plus ruff and mypy), latest release, required Python and
  licence. They replace the static "version 2.1.0", "940 tests passing locally" and "mypy clean"
  badges, two of which had gone stale.
- `euv serve` binds to 127.0.0.1 by default (was 0.0.0.0): the server has no authentication and
  should not listen on the network unasked. `--host 0.0.0.0` restores network access; the Docker
  image is unchanged (it starts uvicorn with its own host setting).
- Notebooks 01–06 re-checked against the current defaults and re-executed; several sections showed
  results that did not support their text. 02: the SE-blur sweep was flat because the threshold
  model ignores `se_blur_nm`; the blur is now applied to the image (NILS 4.97 → 3.59 → 1.45 at
  0 / 5 / 10 nm), and the resolution statement follows the computed NILS (< 2 between 20 and 16 nm
  half-pitch). 03 and 05: exposure at the dose-to-size of the default resist (1.3 mJ/cm², was 4 with
  a stale "prints near 5.7" comment), the chain's own PEB blur, the correct photon budget (13.6
  incident, ≈ 2.7 absorbed per nm² at 20 mJ/cm²), no removed Q factor; 05's dill_C sweep stays
  inside the printing window (was 8 of 8 points without an edge). 05's standalone shot-noise
  demonstration was broken (LER 0, fit exponent NaN); rebuilt with a dark line, 0.2 acids per
  incident photon and a fixed relative threshold, it fits a dose exponent of −0.55 (Poisson: −0.5)
  and LWR/LER = 1.37–1.43 (√2 = 1.41), and 03's
  broken copy of it is removed. 04: the dose sweep brackets the dose-to-size, the focus sweep no
  longer cuts off the DoF, the NA comparison works (it was all-NaN, see `dose_matrix` below), the
  SE-blur effect is computed with the full chemistry (EL 22.8 % → 10.0 % from 0 to 10 nm) and MEEF
  with the full chemistry (1.28; the threshold model gives 0.50). 06: the RCWA demonstration uses the
  pipeline's mask set-up (4× mask period, mirror operator; it used a bare substrate and the wafer
  pitch, so its efficiencies were ~1000× too small), the taper cell that did not model a taper is
  replaced by the pipeline's rejection, and best focus is compared for thin mask (0 nm) and RCWA
  (+25 nm). 01: σ = 0.5 is no longer called coherent.
- Releases: only the gated "Create Release" job in ci.yml (after the full test matrix) creates the
  GitHub release; release.yml is manual. Both used to fire on a tag and raced.

### Fixed
- `metro.dose_matrix` called the callback with keywords and turned every exception into NaN, so a
  callback named `(dose, focus)` gave an all-NaN matrix without a warning (notebook 04 reported
  DoF = EL = 0 for its whole NA and SE-blur sweeps). It now calls positionally and lets errors
  surface; two tests added.
- full_chem reported a NILS (0.47 at 64 nm pitch) when nothing developed (CD = pitch), read off the
  wrap-around pixels; it is now NaN because there is no printed edge (test added).
- API/GUI: absorber taper and undercut (not implemented, the pipeline raises) are rejected with a
  clear 422 message instead of a server error; the field catalogue called them "RCWA path".
- Windows: the CLI reads YAML/JSON configs as UTF-8 (the platform default is cp1252).
- SECURITY.md and the Code of Conduct pointed to mailboxes of the old project name on a foreign
  domain; reports now go through GitHub's private vulnerability reporting.

### Added
- Documented limitation: the `aerial_threshold` model's threshold follows the image mean, so it
  underestimates MEEF by about half (0.50 vs 1.02 with a fixed threshold, 1.28 in the full
  chemistry at 64/32 nm). README and docs/physics.md say to use `full_chem` for mask comparisons.
- `docs/campaign_2026-09-07/`: exploratory parameter campaign (256 configurations over optics, PEB
  kinetics, development and stochastics) with scripts, raw data and the pattern-search report — all
  patterns map onto known laws (edge-dose invariance, lumped-parameter development model to 8 %,
  Gaussian correlation length, blur-limited exposure latitude vanishing at blur/pitch ≈ 0.3).
- docs/physics.md §7: the two measurements that would decide the acid-loss law, and Kang 2010's
  activation energies as the only free temperature series for trapping and diffusion.
- Repository public since 2026-09-11 (old history purged by GitHub Support, ticket #4734231).

## [2.2.0] — 2026-09-06

Browser GUI rebuilt in four stages; no physics change (the pipeline only gained an optional
progress/cancel hook). See the stage notes below.

### Added — browser GUI, stages 3 and 4 (jobs, process window, bands, estimate)
- Background jobs (`api/jobs.py`): `POST /jobs` starts a simulation, a process window or the
  structural bands in a worker thread; `GET /jobs/{id}` reports progress, message, partial
  results (the growing CD matrix) and the final result; `DELETE /jobs/{id}` cancels
  cooperatively (before the next stochastic realisation / grid cell / bands corner);
  `GET /jobs/{id}/export.csv` exports profiles, the Bossung matrix or the band corners.
- `run_simulation(cfg, progress=...)`: optional hook called before each stochastic
  realisation; returning `False` raises `SimulationCancelledError`. Same hook on
  `calibrate.bands.structural_bands(progress=...)`. No physics change.
- `POST /estimate`: peak-memory estimate of a configuration from a model fitted to eleven
  measurements on the reference machine (`api/estimate.py`, ±30 %, test-guarded) — shown live in the GUI
  instead of any size limit.
- GUI: task selector (Simulation / Process window / Uncertainty bands), progress bar with
  message and elapsed time, cancel button, live memory estimate and live physics check under
  the Run button, LER/LWR tiles with n_eff, correlation length, passband and 95 % CI in the
  notes, Bossung table with in-spec colouring and best cell (rendered while the job runs),
  bands table with dose-to-size and 3σ-LWR bands, CSV/JSON export links.

### Added — browser GUI, stage 2 (presets and guidance)
- `GET /presets`: named starting configurations with provenance text and the full
  `SimulationConfig` each resolves to — the documented default resist, the NXE1716 anchor as a
  prediction (dose-to-size 19.7 vs measured 11.0 mJ/cm²), the same anchor with the ×1.79 dose
  calibration labelled as a calibration, and the MET-2D / XP 5271 anchor.
- `GET /fields`: every `SimulationConfig` field with type, default, group, label, unit, help and
  choices (`api/fields.py`); `tests/test_api_fields.py` asserts catalogue, generated request
  model and dataclass never drift apart.
- `POST /simulate` now takes `{preset, config}` where `config` is any subset of the flat
  `SimulationConfig` fields (generated pydantic model, unknown names rejected); the response
  carries the fully resolved config and provenance notes. LER/LWR (1σ) are reported when photon
  shot noise is enabled, with the no-SEM-bias caveat. Physical constraints only, no cosmetic
  limits on grid, rows, seeds or realisations.
- GUI: the parameter form is generated from the catalogue — six main parameters open, the
  other 58 in collapsed groups (optics, mask, multilayer, exposure, PEB, development,
  stochastics, numerics), preset selector with "where these numbers come from", reset to
  preset, model-dependent fields hidden, only the overrides are sent; result notes explain
  CD = 0 / CD = pitch and the roughness statistics.

### Changed — browser GUI, stage 1 (clean-up)
- One page instead of two (`/`; the old `/simulate` page redirects there); the leftover
  old project name is gone.
- No external assets: the profile plot is inline SVG, Chart.js and its CDN load are removed
  (NOTICE/README updated). The page works offline.
- `POST /simulate` is a sync endpoint, so FastAPI runs the pipeline in its threadpool and the
  server stays responsive during long runs.
- API schema: every field maps onto a `pipeline.SimulationConfig` field (resist thickness,
  development time, inner σ and pole opening are now forwarded instead of silently ignored);
  fields the pipeline never read (`reduction_ratio`, `zernike_coeffs`, `outer_sigma`, `layout`,
  `gds_path`, `resist_type`, `acid_diffusion_length_nm`) are removed; defaults mirror the
  pipeline (pitch 64, CD 32, absorber 60 nm, 50 bilayers); bounds are physical only
  (0 < NA < 1, CD < pitch, inner σ < outer σ). The pipeline device is no longer pinned to CPU.
- The threshold line in the plot is the intensity the CD was extracted at
  (`raw.threshold_intensity`), not 0.5 × max.
- GUI sliders are conveniences; number fields accept any physically valid value.

## [2.1.0] — 2026-09-06

### Added — calibration with structural uncertainty bands
- **`euv calibrate --bands`** (`calibrate/bands.py`): after fitting a wafer FEM, the calibrated chain
  is evaluated at the corners of the two structural choices no free measurement decides — the PEB
  acid-loss law (`"analytical"` vs `"reaction_diffusion"`) and the dissolution-unit size (1 and
  4.3 nm) — and reports dose-to-size and 3σ LWR as bands instead of single numbers. Simulated LWR
  carries no SEM bias; the bootstrap CIs of the fitted parameters remain the statistical band.
  Runtime ~3–5 min at grid 128 on the reference machine.
- `calibrate.DEFAULT_BOUNDS` is the single source of the default fit bounds (contains the defaults;
  test-guarded). No physics change.

## [2.0.0] — 2026-09-06

**Release summary.** This version closes the physics work of September 2026: every default of the
resist chain now has a named source, a derivation, or an explicit calibration/assumption label
(`docs/physics.md`); the aerial image is clear-field-normalised; the exposure, PEB, development and
roughness models were rebuilt against primary measurements (Yamamoto 2011, Kang/NIST 2009/2010,
LBNL film quantum yields, Thackeray 2010, Anderson/Naulleau 2008, Vesters 2017/2019, Lorusso/Mack
2018); two named-resist anchors and their documented distance to the measurements replace the
former unqualified "validated" claims. Defaults changed (Dill B/C, deprotection rate, acid lifetime,
diffusivity, SE blur, quench rate), so results differ from 1.x — that is the point of the release.
Experimental options (off by default, documented as such): `development_stochasticity`,
`development_model="eikonal3d"`, `peb_model="reaction_diffusion"`, `exposure_stochasticity`,
`ler_passband_nm`, `peb_temperature_c`. Known limitations: README "Known limitations" and
`docs/physics.md` §7. Full local test suite: 935 tests; CI could not run (GitHub billing limit).
The entries below are the detailed log of the release in reverse chronological order.

### Verified (2026-09-06)
- The sampled exposure chain already carries the photon-to-acid multiplicity: acid counts in blocks
  larger than the SE blur are compound-Poisson with Var/E = 1 + m (measured 1.91 vs 2.0 for m = 1.0
  acids per absorbed photon; 0.96 vs 1.0 without photon noise). Pinned in `tests/test_acid_multiplicity.py`;
  the plan's item 3.3 ("multiplicity missing") is withdrawn.

### Added (physics, 2026-09-06) — concurrent reaction-diffusion PEB
- **`peb_model="reaction_diffusion"`** (`resist/peb.reaction_diffusion_pde`): the PEB as the coupled
  system of Kang et al. (NIST) 2009, Eqs. 1–3 — diffusion of acid and base, acid trapping by
  deprotected sites (k_trap·h·φ), neutralisation and deprotection all concurrent (operator splitting,
  exact Gaussian diffusion per step). Validated with zero free parameters on the NIST bilayer
  diffusion lengths (76/56/36/23 nm for four quencher layouts, `tests/test_reaction_diffusion_pde.py`);
  the chain's previous diffuse-then-quench form with first-order acid loss gives 25/12/6/2 nm there.
  The same Yamamoto Fig. 3 flood curves are fitted equally well by both laws (per-temperature
  parameters of the NIST law in the anchor data; `peb_temperature_c` selects them for this model).
  Default stays `"analytical"` (goldens); the concurrent model costs ~6× per PEB.
- **Quench-rate default 15 → 1.2 nm³/s**: Mack 2011's 15 and Osaka 2025's 12.6 are model assumptions;
  the NIST bilayer cases with quencher in the receiving layer are reproduced only for k_Q ≈ 1.0–1.5.
  Consequence: neutralisation during a 60 s PEB is incomplete (k_Q·G0·t ≈ 1.8), and the B2 two-curve
  quencher fit (which assumed complete neutralisation) needs re-evaluation.
- Also: `peb_k_trap_per_s` (0.2076 at 110 °C from the Fig. 3 refit), `peb_D_quencher`.
- **NXE1716 quencher fit through the concurrent PEB** (`presets.NXE1716_QUENCHER_FIT_PDE`,
  `nxe1716_config(explicit_quencher=True, peb_model="reaction_diffusion")`, `presets.flood_rate_pde`):
  Q/PAG = 0.36 (0.13 with the analytical PEB), Mack n 13–14 instead of at the fit bound, rms 0.04/0.07 —
  the NIST law makes the two-curve fit physically consistent. The dose-to-size of the 22 nm lines stays
  1.7× above the measurement (19.0 vs 11.0 mJ/cm² at grid 128) whichever PEB law is used.

### Changed (physics, 2026-09-06) — PEB temperature model
- **All seven Fig. 3 curves of Yamamoto 2011 (80–140 °C) digitised** and fitted with the chain's own
  deprotection law (`data/anchors/yamamoto2011_fig3_polymerA.json`, `resist/kinetics.py`): k and the
  acid lifetime τ per temperature, log-linear in 1/T in between. Findings: two Arrhenius regions as the
  paper states (103 kJ/mol below 110 °C, 38 kJ/mol above — the kcal reading of Table 1 is confirmed,
  resolving the unit question); **τ(90 °C) = 35 s** against 38 s measured by
  Kang/NIST 2009 on a different EUV resist.
- **Defaults refined from the full 110 °C curve:** `peb_k` 7.87 → 10.95 s⁻¹, `peb_acid_lifetime_s`
  10.5 → 7.54 s (same product, Fig. 3/5 anchors unchanged; default PEB blur 9.4 → 7.9 nm; preflight:
  dose-to-size −4 % at 44 nm pitch, photon LWR −6 %). New `peb_temperature_c` (config) and
  `--peb-temperature` (CLI) select the measured kinetics at any PEB temperature in 80–140 °C.
- Consequence recorded for the NXE1716 anchor: with the sourced 90 °C lifetime (35–38 s) the free-
  diffusion blur √(2·D·t_eff) would be 15–16 nm and the lines would not print at 11 mJ/cm² — the
  quencher-controlled effective diffusion (NIST: 36 → 14 nm with quencher) is not captured by a
  subtractive quencher; open.

### Added (numerics and metrology, 2026-09-06)
- **`development_model="eikonal3d"`**: the fast-sweeping Eikonal solver can couple the rows through a
  third (y) Godunov term (Zhao 2005, d = 3; Jacobi in y, Gauss–Seidel in z/x, periodic in y). Invariants
  tested: uniform rate exact, y-uniform fields bit-identical to the per-row solver, y-varying fields never
  later than per-row, exact tiling invariance with cell noise (coupling reach ≤ n_iter rows < halo).
  Finding at the MET-2D anchor with cell noise: the coupling does not lower the LER (5.14 vs 5.04 nm 3σ),
  it shortens the correlation and softens the cell-size dependence (a⁻⁰·⁵ instead of a⁻¹), at 8–9× the
  cost. Default stays `"eikonal"`.
- **`ler_passband_nm`**: metrology passband (p_min, p_max) applied to edge and width profiles before the
  roughness statistics (`resist/stochastic.bandlimit_along_rows`). Measurements are band-limited
  (Anderson & Naulleau 2008: 10–834 nm; imec biased CD-SEM protocol, Vesters 2019: 5.38 nm y-pixels →
  ≈ 10.8–5500 nm); the simulated field is not, and the dissolution-cell noise puts most of its power at
  periods of a few nm. The anchor presets carry their source's band; the default (None) keeps the full
  band and all goldens. In-band anchor results: MET-2D 4.3 nm 3σ with dissolution
  noise (2.0 photons + PAG) vs 6.7 measured SEM-biased; NXE1716 13.2 nm vs 6.7 (5.1–5.7 bias-corrected) —
  the thin-film / 22 nm half-pitch anchor stays over-predicted, dominated by the 110 °C-derived blur.

### Added (physics, 2026-09-06) — development noise
- **`development_stochasticity=True` now enables a derived dissolution-noise model**
  (`resist/develop.dissolution_cell_noise`) instead of raising: each dissolution cell of edge
  `dissolution_cell_nm` (4.3 nm, Thackeray 2010 polymer radius of gyration) contains
  `blocked_site_density_per_nm3 · a³` polymer sites (1.63 nm⁻³ from the default composition,
  35 % protection); the blocked count fluctuates by Poisson statistics (Mack 2010, *LER and the
  ultimate limits of lithography*, Eq. 36) and the cell dissolves at the Mack rate of its own
  protection, which roughens the front (Mack 2010, JM3 9, 041202, KPZ class). No fitted knob.
  Quenched per cell, anchored to absolute indices, bit-identical under any y-tiling or row
  chunking; nothing is drawn when the option is off (all goldens unchanged). Stochastic chain
  only; the deterministic chain stays the mean field. Non-Eikonal development with the option
  raises `NotImplementedError`.
- **Result at the anchors:** MET-2D (XP 5271, 50 nm 1:1, dose calibrated) LER 3σ rises from
  0.73 (photons) / 1.97 (+ PAG counting) to **4.96 nm** with the dissolution noise, against 6.7 nm
  measured (SEM-biased, Anderson & Naulleau 2008) — the missing "intrinsic" floor is largely the
  counting statistics of the dissolving polymer. Caveat measured, not assumed: the result scales
  roughly with 1/cell size (2.15 nm → 10.2 nm 3σ), so the dissolution-unit size is a physical
  parameter of this model; and the per-row Eikonal solver has no y-coupling, so the added roughness
  is cell-scale white along y (n_eff 120–350).
- Tests: `tests/test_dissolution_cell_noise.py` (density from composition, Poisson scatter by
  inversion, quenched/reproducible/cell-constant, absolute-row anchoring, bit-exact tiling
  invariance, deterministic chain unaffected, validation).

### Added (validation anchors, 2026-09-06)
- **Explicit quencher for NXE1716** (`presets.NXE1716_QUENCHER_FIT`, `nxe1716_config(explicit_quencher=True)`,
  `presets.flood_rate_quenched`): the NXE1717 curve (half the quencher) was digitised too; a joint fit with
  shared deprotection rate and a 2:1 quencher ratio through the chain's own neutralisation step gives a
  relative quencher loading of 0.13–0.15 (Q ≈ 0.03 nm⁻³), rms 0.03/0.06 in log10 R. Finding: neither the
  dose-to-size (19.7 → 19.7) nor the LWR at matched dose (10.9 → 11.1 nm 3σ) depends on it — a subtractive
  quencher is cancelled alike in flood and pattern. Structural result: for a symmetric
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

### Added (validation anchor, 2026-09-06)
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

### Changed (physics, 2026-09-06)
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

### Changed (physics, 2026-09-06)
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
  xfail until it is decided which parameter moves. No default changed.

### Changed (physics, 2026-09-05)
- **Default acid diffusivity 3.3 → 4.2 nm²/s (Kang et al. 2010, measured).** The old value was
  back-calculated so that D·60 s gave Anderson 2009's 19.9 nm blur; with the acid lifetime the
  diffusion time is the effective lifetime (10.5 s), so that reasoning no longer applied and the
  implicit default blur had already become 8.3 nm. 4.2 ± 0.3 nm²/s is the FT-IR bilayer value for
  P(HOSt-co-tBA) at 90 °C (Kang, Macromolecules 43, 4275, Table 2); the resulting default blur
  σ = 9.4 nm lies inside the 7.5–12 nm band of directly measured blur lengths of named EUV CARs
  (LBNL resist PSF, Langner 2010, Thackeray 2010) without being fitted to it. Pre-registered
  preflight: dose-to-size +0.6 % (64 nm pitch) / +3 % (44 nm); photon LWR
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
  alone could rescue it. The two former
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
  Measured consequences: absorbed photon fraction
  5.2 % → 19.9 %, dose-to-size +14–20 %, photon-shot-noise LWR at dose-to-size down by ≈ 2.5–3.5×
  (P = 44 nm: ≈ 10.6 → ≈ 4 nm). All stochastic regression goldens re-derived. The default is pinned
  to the derivation by `tests/test_absorption_coefficient.py`.
- `tests/test_stochastic_consistency.py`: the large-number-limit invariant now compares the
  sampled-molecule chain with the mean-field chain field-to-field (same tiles, same edge
  extractor) instead of against `cd_nm`, which since the sub-pixel CD uses a different edge
  estimator (arrival-time crossing) than the realisations (depth-map crossing); the two differ
  by up to ~1 px on their own and that difference was being tested by accident.

### Fixed (physics
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
  Eikonal front raised the working set of the noisy exposure → PEB → development
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
- **One chemistry for both chains.** The deterministic full_chem chain and the
  sampled-molecule chain (`exposure_stochasticity=True`) run the same PEB step: acid and
  quencher diffuse, then neutralise (Mack 2011 closed form, k_Q·G0), then deprotect. The
  deterministic result is now the large-number limit of the stochastic one
  (`tests/test_stochastic_consistency.py`). Previously the deterministic chain had no quencher and
  the stochastic chain evaluated the reaction per grid voxel, where it was effectively inert.
  New `ler_metadata["stochastic_cd_nm"]`.
- **RCWA.** Three errors in the 1D solver's mode coupling, found through conservation
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
  `process-window`: 7 of 8 commands were untested).
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
- Repository layout: third-party reference PDFs/HTML removed from version control.

### Documentation
- Vesters cross-check: with the fully sourced default set, the dose-scaled
  photon-shot-noise LWR at 22 nm half-pitch is 1.2–1.7× above the biased CD-SEM values of two
  NXE resists (was 3–4× before the exact-blur rework). Documented as a plausibility check, not a validation.
- **Known limitations**, documented rather than hidden: photon shot noise is computed on
  incident rather than absorbed photons; the dose convention is not clear-field-normalised;
  the PEB diffusion length is not sourced for the validation regime; the quencher is
  effectively inert in the stochastic path; `development_stochasticity` depends on the
  numerical layer count; the RCWA TM factorisation uses the Laurent rule, not Li's rule.

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