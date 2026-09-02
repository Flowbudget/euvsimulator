# euvsimulator — Agent Integration Guide

**Target audience:** Autonomous AI agents, coding assistants, and agent frameworks.

This document describes the actual current state of the working tree. Every claim has been verified against the repository. The scientific status is based on the P0–P8 audit series (2026-09-02).

---

## 1. Installation

```bash
cd euvsimulator
pip install -e ".[dev]"   # includes pytest, ruff, mypy, jupyter

# Verify installation
pytest tests/ -x -q       # 789 tests passing (baseline)
```

**Requirements:** Python 3.10+, PyTorch, NumPy, SciPy. GPU optional (MPS on Apple Silicon, CUDA where available).

---

## 2. Python API — Core Entry Points

### 2.1 Single Simulation
```python
from euvsimulator.pipeline import SimulationConfig, run_simulation

cfg = SimulationConfig(
    period_nm=64.0,
    line_width_nm=32.0,
    dose_mj_cm2=20.0,
    na=0.33,
    sigma=0.8,
    illumination_shape="conventional",  # "conventional" | "annular" | "dipole" | "dipole_x" | "dipole_y" | "quasar"
    resist_model="aerial_threshold",    # "aerial_threshold" | "full_chem"
    grid=256,
    focus_nm=0.0,
)

result = run_simulation(cfg)

# Key outputs
print(f"CD: {result.cd_nm:.2f} nm")
print(f"NILS: {result.nils_value:.3f}")
```

When `resist_model="full_chem"` is used, Dill A/B/C, PEB, and Mack development
parameters are applied. When `enable_stochastic=True` is also set, photon shot
noise and LER/LWR extraction are additionally enabled:

```python
cfg = SimulationConfig(
    resist_model="full_chem",
    enable_stochastic=True,
    stochastic_n_realisations=10,
    dill_A=0.5, dill_B=0.2, dill_C=0.05,
    peb_D=5.0, peb_k=0.3, peb_t_bake=60.0,
    mack_R_max=100.0, mack_R_min=0.1, mack_n=5.0, mack_M_th=0.5,
)

result = run_simulation(cfg)
print(f"CD: {result.cd_nm:.2f} nm")
print(f"LER: {result.ler_nm:.3f} nm")
print(f"LWR: {result.lwr_nm:.3f} nm")
if result.resist_profile is not None:
    print(f"Resist profile: {result.resist_profile.shape}")
```

### 2.2 Resist Presets

`RESIST_PRESETS` contains only typical secondary-electron blur lengths:

```python
from euvsimulator.pipeline import RESIST_PRESETS

# RESIST_PRESETS = {"CAR": 5.0, "nonCAR": 2.5, "HighNA": 3.0}
# Each value is se_blur_nm in nm.
cfg = SimulationConfig(period_nm=64, line_width_nm=32, dose_mj_cm2=20,
                       se_blur_nm=RESIST_PRESETS["CAR"])
```

See the CLI (`euv simulate --help`) for full Dill, PEB, Mack, and stochastic
parameter names and defaults.

### 2.3 Process Window (via CLI)

```bash
euv process-window \
  --period 64 --cd 32 --dose-start 10 --dose-end 40 --dose-steps 7 \
  --focus-start -50 --focus-end 50 --focus-steps 7 \
  --output pw_results.json --output-plot pw_heatmap.png --output-csv pw.csv \
  --tolerance 0.1
```

A post-processing helper is available in `euvsimulator.metro.process_window`:

```python
from euvsimulator.metro.process_window import process_window
import numpy as np

# Pre-compute a CD matrix via a dose×focus sweep (e.g. using the CLI
# or a manual loop over SimulationConfig), then analyse it:
cd_matrix = np.array([[30.0, 28.5, 27.0], ...])  # shape (n_focus, n_dose)
doses = [10.0, 15.0, 20.0, 30.0, 40.0]
focuses = [-50.0, -25.0, 0.0, 25.0, 50.0]

result = process_window(
    cd_matrix=cd_matrix,
    doses=doses,
    focuses=focuses,
    target_cd=32.0,
    tolerance=0.1,
)
# result: dict with keys 'dof_nm', 'el_pct', 'best_dose', 'best_focus'
```

### 2.4 Calibration (Wafer CD → Resist Parameters)

```python
from euvsimulator.calibrate import WaferCDData, fit_resist_params, bootstrap_fit
import numpy as np

# FEM CD data: shape (n_dose, n_focus)
data = WaferCDData(
    dose_values=np.array([10, 15, 20, 30]),
    focus_values=np.array([-50, -25, 0, 25, 50]),
    cd_matrix_nm=...,  # measured CD values
)
result = fit_resist_params(
    data,
    initial_params={"dill_C": 0.05, "mack_n": 5.0},
    pipeline_fn=lambda dose, focus, **kw: ...,
    bounds={"dill_C": (0.01, 0.5)},
)
# result: {"fitted_params": {...}, "rmse": ..., "success": True}
```

---

## 3. CLI Commands

```bash
euv --help
```

| Command | Description |
|---------|-------------|
| `simulate` | Run a single simulation (all resist and mask parameters) |
| `process-window` | Bossung plot over dose × focus, CD heatmap, DoF/EL |
| `calibrate` | Fit resist parameters to measured wafer CD data |
| `make-mask` | Generate a line/space test mask as GDSII |
| `serve` | Start the REST API server |
| `materials` | Query the CXRO material database |
| `bench` | Run a performance benchmark |
| `version`, `info` | Version and system information |

All commands accept config files via `--config`.

---

## 4. Jupyter Notebooks

Six notebooks in `notebooks/`:

| Notebook | Focus |
|----------|-------|
| `01_aerial_image.ipynb` | Aerial image formation, pupil, coherence, TCC |
| `02_nils_cd.ipynb` | NILS analysis, CD extraction, SE blur effects |
| `03_resist_chain.ipynb` | Dill ABC, PEB, development, parameter sweeps |
| `04_process_window.ipynb` | Bossung curves, CD heatmaps, DoF/EL, CSV export |
| `05_stochastics.ipynb` | Shot noise, LER/LWR extraction, verification gates |
| `06_mask3d.ipynb` | RCWA 1D/2D, mask 3D effects, Fourier orders |

---

## 5. Physics Validation

Any PR changing physics must pass:

1. **Full test suite:** `pytest tests/ -x -q` — 789 tests passing (baseline)
2. **NILS Gate:** `|euvsimulator - Reference| < 0.3` for sinusoidal grating
3. **Notebook Execution:** All 6 notebooks execute without error

Reference model: `scripts/reference_model.py` (pure NumPy/SciPy, no euvsimulator imports).

---

## 6. Scientific Status

| Layer | Status | Detail |
|-------|--------|--------|
| **Hopkins/TCC optics** | ✅ Internally mathematically validated | Bitwise match with independent numpy reference (12/12 cases) |
| **TMM (Mo/Si ML, Ta absorber)** | ✅ Internally validated | Fresnel limits confirmed, phase propagates (Δφ≈179°, 15% CD impact) |
| **Aerial image** | ✅ Grid-convergent, always non-negative | Sub-pixel CD extraction monotonic, 0.04 nm span 64→1024 |
| **Aerial-threshold resist** | ✅ Implemented, grid-convergent | `resist_model="aerial_threshold"` |
| **Full-chem resist** | ✅ Implemented (Dill, PEB, Mack) | `resist_model="full_chem"` with Dill A/B/C, PEB kinetics, Mack development |
| **Stochastic/LER/LWR** | ✅ Implemented | `enable_stochastic=True`, photon shot noise, LER/LWR extraction |
| **Wafer calibration** | ✅ Implemented | `calibrate` module: `WaferCDData`, `fit_resist_params`, `bootstrap_fit` |
| **Dose** | ⚠️ Model parameter (mJ/cm²) | No absolute photon-flux→resist-energy calibration; dose scales aerial image |
| **CD** | ⚠️ Optical threshold CD | Not an experimentally validated wafer CD |
| **NILS** | ⚠️ Optical metric | Same aerial-image threshold as CD; not a resist-performance metric |
| **Mask model** | ⚠️ Thin-mask / scalar | 3D mask effects available via optional RCWA (`--use-rcwa`) |
| **External quantitative validation** | ❌ Unvalidated | No public reference with identical parameters (PROLITH/Dr.LiTHO N/A) |

**Classification:** Internally mathematically validated, physically simplified, externally quantitatively unvalidated.

**Standard result (aerial_threshold, grid=256):** CD=27.62 nm, NILS=4.97 — optical threshold-CD of the implemented model, not a wafer-validated value.

**Threshold normalization:** The implementation uses `mean(aerial)`, not `max(aerial)` (the docstring at pipeline.py:247 contains an outdated reference to "max").

---

## 7. Contribution Workflow

```bash
git checkout -b feat/your-change
# Make changes, then:
pip install -e ".[dev]"
pytest tests/ -x -q
git add .
git commit -m "feat(scope): description"
git push origin feat/your-change
# Open PR at https://github.com/Flowbudget/OpEnUV/pulls
```

**PR Requirements:**
- Tests pass
- Conventional commit messages

---

## 8. Project Structure

```
src/euvsimulator/
├── source/         LPP Sn-plasma emission
├── materials/      CXRO f1/f2 database
├── optics/         Multilayer TMM
├── mask3d/         RCWA 1D/2D
├── aerial/         Abbe/Hopkins imaging
├── resist/         Dill ABC, PEB, development, stochastic
├── metro/          CD metrology, process window
├── calibrate/      Wafer fitting + bootstrap uncertainty
├── pipeline.py     End-to-end orchestration
├── io/             CLI, GDSII, rasterization
├── api/            FastAPI REST server (optional)
└── accel/          GPU acceleration device selection

tests/              789 tests (unit + integration)
notebooks/          6 verified notebooks
scripts/            gen_notebooks.py, validate_nils.py
```

---

## 9. Contact & Community

- **Issues:** https://github.com/Flowbudget/OpEnUV/issues
- **Discussions:** https://github.com/Flowbudget/OpEnUV/discussions
- **Security:** See SECURITY.md

---

## 10. License

Apache-2.0 — permissive, allows commercial use, modification, distribution.