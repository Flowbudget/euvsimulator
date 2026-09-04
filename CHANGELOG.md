# Changelog

All notable changes to euvsimulator are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
  solutions (`tests/test_eikonal_development.py`). Not yet the pipeline default.
- Docstrings of `etch.bias` (coefficients are empirical, no source), `source.plasma` (illustrative,
  not connected to the pipeline) and `aerial.abbe` (numerical TCC overlap, scalar thin-mask) now
  state their status.

### Removed
- `development_stochasticity=True` (raises `NotImplementedError`), `development_strength`,
  `development_correlation_nm`: the event-based development-noise model depended on the
  numerical layer count (LWR 1.44 nm at 21 layers vs 0.17 nm at 41) and used a fitted, unit-less
  event-rate knob. `resist.develop.stochastic_development` remains as an experimental function.
- `dill_Q` (config field, CLI `--dill-Q`, calibration parameter): it double-counted the PAG
  quantum efficiency, which lives inside Dill C (Mack 2013, Eqs. 8/10), and capped the acid yield
  at 0.5. The acid yield is now 1 − exp(−C·E). `SimulationConfig(dill_Q=...)` raises.
- `resist_threshold`, `mask_sidewall_roughness_nm`: accepted but never read.

### Changed
- Repository layout: 110+ historical audit/session reports moved out of the repository root
  (recoverable from git history; index in `docs/history/README.md`); third-party reference
  PDFs/HTML removed from version control; `testberechnungen.md` moved to `docs/`.

### Documentation
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