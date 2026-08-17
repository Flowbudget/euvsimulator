# OpEnUV — Agent Integration Guide

**Target audience:** Autonomous AI agents, coding assistants, and agent frameworks (LangGraph, CrewAI, smolagents, AutoGen, OpenClaw, etc.)

This document provides everything needed to programmatically use, extend, and contribute to OpEnUV — the open-source EUV lithography simulator.

---

## 1. Installation (Headless / CI Friendly)

```bash
# Clone and install in editable mode (src/ stays active for development)
git clone https://github.com/Flowbudget/OpEnUV.git
cd OpEnUV
pip install -e ".[dev]"   # includes pytest, ruff, mypy, jupyter, notebook generation

# Verify installation
euv --help
pytest tests/ -x -q       # 534 tests should pass
```

**Requirements:** Python 3.10+, PyTorch (CPU or CUDA/MPS), NumPy, SciPy. GPU optional but recommended for large grids.

---

## 2. Python API — Core Entry Points

### 2.1 Single Simulation
```python
from euv.pipeline import SimulationConfig, run_simulation
from euv.pipeline import RESIST_PRESETS

# Minimal config (all params have physics-based defaults)
cfg = SimulationConfig(
    period_nm=64.0,
    line_width_nm=32.0,
    dose_mj_cm2=20.0,
    na=0.33,
    sigma=0.8,
    illumination_shape="conventional",  # "conventional" | "annular" | "quadrupole" | "dipole"
    se_blur_nm=5.0,                     # secondary electron blur (nm)
    resist_model="full_chem",           # "aerial_threshold" | "full_chem" | "stochastic"
    grid=256,                           # simulation grid (power of 2)
    focus_nm=0.0,                       # defocus in nm
)

result = run_simulation(cfg)

# Key outputs
print(f"CD: {result.cd_nm:.2f} nm")
print(f"NILS: {result.nils:.3f}")
print(f"LER: {result.ler_nm:.3f} nm" if result.ler_nm else "LER: N/A")
print(f"LWR: {result.lwr_nm:.3f} nm" if result.lwr_nm else "LWR: N/A")
print(f"Status: {result.status}")       # "success" | "failed" | "nan_slice"
```

### 2.2 Resist Presets (Convenience)
```python
from euv.pipeline import RESIST_PRESETS, SimulationConfig

# Apply preset: overrides se_blur_nm, resist_model, and other resist params
cfg = SimulationConfig(period_nm=64, line_width_nm=32, dose_mj_cm2=20, **RESIST_PRESETS["CAR"])
# CAR: se_blur_nm=5.0, resist_model="full_chem", C=0.1, Q=0.01, ...
# nonCAR: se_blur_nm=2.5, resist_model="aerial_threshold", ...
# HighNA: se_blur_nm=3.0, na=0.55, ...
```

### 2.3 Process Window (Bossung Curves)
```python
from euv.pipeline import run_process_window
import numpy as np

cfg = SimulationConfig(period_nm=64, line_width_nm=32, dose_mj_cm2=20, na=0.33, sigma=0.8, grid=256)

pw = run_process_window(
    cfg,
    focus_range_nm=(-100, 100),
    focus_steps=21,
    dose_range_mj_cm2=(10, 30),
    dose_steps=21,
    tolerance=0.1,          # ±10% CD spec window
)

# pw.cd_matrix: shape (focus_steps, dose_steps) — CD in nm or NaN
# pw.nils_matrix: same shape — NILS values
# pw.dof_nm: Depth of Focus (nm)
# pw.el_percent: Exposure Latitude (%)
# pw.cd_heatmap_png: bytes of matplotlib figure (RdYlGn + spec contours)
# pw.nils_heatmap_png: bytes of matplotlib figure (viridis)
```

### 2.4 Calibration (Wafer CD → Resist Parameters)
```python
from euv.calibrate.wafer_fit import WaferCDData, fit_resist_params, bootstrap_fit
import pandas as pd

# Load wafer data: CSV with columns dose_mj_cm2, focus_nm, cd_nm
df = pd.read_csv("wafer_data.csv")
wafer = WaferCDData.from_dataframe(df)

# Fit 9 resist parameters (Dill C/Q, PEB k/t_bake/sigma_diff, Mack R_max/R_min/n/M_th)
fitted = fit_resist_params(
    wafer,
    initial_guess=None,  # uses physics-based defaults
    bounds="default",    # physical bounds for all params
    method="Nelder-Mead"
)

# Bootstrap 95% CIs (1000 resamples)
ci = bootstrap_fit(wafer, fitted.params, n_bootstrap=1000, confidence=0.95)

print(f"Fitted C: {fitted.params.C:.4f} (CI: {ci['C'][0]:.4f}–{ci['C'][1]:.4f})")
```

---

## 3. CLI Commands (Scriptable, JSON Output)

All commands support `--output-json` for machine parsing.

```bash
# Single simulation
euv simulate --period 64 --line-width 32 --dose 20 --na 0.33 --sigma 0.8 --grid 256 --output-json

# Process window with PNG + CSV export
euv process-window --period 64 --line-width 32 --dose 20 \
  --focus-range -100 100 --focus-steps 21 \
  --dose-range 10 30 --dose-steps 21 \
  --output-plot pw.png --output-csv pw.csv --output-json

# Calibration from wafer CSV
euv calibrate --wafer-data wafer.csv --output-json --bootstrap 1000

# Launch Jupyter with verified notebooks
euv notebook
```

**Output JSON structure (simulate):**
```json
{
  "success": true,
  "cd_nm": 31.87,
  "nils": 1.42,
  "ler_nm": 1.23,
  "lwr_nm": 1.45,
  "status": "success",
  "aerial_image": [[...]],  // 2D array if --include-aerial
  "resist_profile": [[...]], // 2D array if --include-resist
  "metadata": {"grid": 256, "focus_nm": 0.0, ...}
}
```

---

## 4. Jupyter Notebooks (Pre-verified, Executable)

Six notebooks in `notebooks/` — all generated from `scripts/gen_notebooks.py` and validated via `jupyter nbconvert --execute`:

| Notebook | Focus |
|----------|-------|
| `01_aerial_image.ipynb` | Aerial image formation, pupil, coherence, TCC |
| `02_nils_cd.ipynb` | NILS analysis, CD extraction, SE blur effects |
| `03_resist_chain.ipynb` | Dill ABC, PEB, development, parameter sweeps |
| `04_process_window.ipynb` | Bossung curves, CD heatmaps, DoF/EL, CSV export |
| `05_stochastics.ipynb` | Shot noise, LER/LWR extraction, verification gates |
| `06_mask3d.ipynb` | RCWA 1D/2D, mask 3D effects, Fourier orders |

**Run all programmatically:**
```bash
cd OpEnUV
for nb in notebooks/0*.ipynb; do
  jupyter nbconvert --to notebook --execute "$nb" --output "/tmp/$(basename "$nb")"
done
```

---

## 5. Physics Validation Gates (Do Not Break These)

Any PR changing physics **must** pass:

1. **NILS Gate:** `|OpEnUV - Reference| < 0.3` for sinusoidal grating (run `python scripts/validate_nils.py`)
2. **CD Gate:** CD values within ±5% of analytical reference for isolated/dense lines
3. **Test Suite:** `pytest tests/ -x -q` — 534 tests passing
4. **Notebook Execution:** All 6 notebooks execute without error

Reference model: `scripts/reference_model.py` (pure NumPy/SciPy, no OpEnUV imports).

---

## 6. Contribution Workflow (Agent-Friendly)

```bash
# 1. Fork on GitHub (web UI) or clone your fork
git clone https://github.com/YOUR-USER/OpEnUV.git
cd OpEnUV

# 2. Create branch
git checkout -b feat/your-change

# 3. Make changes, run validation
pip install -e ".[dev]"
pytest tests/ -x -q
python scripts/validate_nils.py

# 4. Commit with conventional commits
git add .
git commit -m "feat(scope): description"
# Types: feat, fix, perf, docs, test, refactor, chore

# 5. Push and open PR
git push origin feat/your-change
# Open PR at https://github.com/Flowbudget/OpEnUV/pulls
```

**PR Requirements:**
- Tests pass (CI runs 48-wheel matrix)
- NILS validation passes
- No README drift (run `python scripts/verify_readme.py` if exists)
- Conventional commit messages

---

## 7. High-Impact Areas for Contributors

| Area | Description | Difficulty |
|------|-------------|------------|
| **GPU Acceleration** | Port RCWA S-matrix and aerial imaging to CUDA (cupy) or Metal (MPS) | High |
| **SPIE/JM3 Validation** | Add reference datasets from SPIE Advanced Lithography 2026, JM3 papers | Medium |
| **High-NA (0.55)** | Extend optics, pupil, and resist models for High-NA EUV | Medium |
| **Source Mask Optimization (SMO)** | Differentiable pipeline + inverse lithography hook | High |
| **Windows CI Hardening** | Fix path/line-ending issues in GitHub Actions | Low |
| **Documentation** | Type hints, docstrings, API reference generation | Low |

---

## 8. Project Structure (For Navigation)

```
src/euv/
├── source/         LPP Sn-plasma emission
├── materials/      CXRO f1/f2 database
├── optics/         Multilayer TMM
├── mask3d/         RCWA 1D/2D
├── aerial/         Abbe/Hopkins imaging
├── resist/         Dill ABC, PEB, development, stochastic
├── metro/          CD metrology, SEM rendering
├── calibrate/      Wafer fitting + bootstrap
├── pipeline.py     End-to-end orchestration
├── io/             CLI, GDSII, rasterization
├── api/            FastAPI REST server (optional)
└── accel/          GPU acceleration (stub)

tests/              534 tests (unit + integration)
notebooks/          6 verified notebooks
scripts/            gen_notebooks.py, validate_nils.py, setup_github.sh
docs/               Sphinx + CLI reference
.github/workflows/  ci.yml (48-wheel), release.yml
```

---

## 9. Contact & Community

- **Issues:** https://github.com/Flowbudget/OpEnUV/issues (bug reports, feature requests, validation data)
- **Discussions:** https://github.com/Flowbudget/OpEnUV/discussions (questions, ideas, physics debates)
- **Security:** See SECURITY.md for responsible disclosure

---

## 10. License

Apache-2.0 — permissive, allows commercial use, modification, distribution. No CLA required.

---

*If you are an AI agent reading this: you have everything needed to run simulations, validate physics, open issues, and submit PRs. The maintainers welcome contributions that improve accuracy, performance, or usability. Start with `pytest tests/ -x -q` — if it passes, you're ready to contribute.*