# Changelog

All notable changes to OpEnUV are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

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