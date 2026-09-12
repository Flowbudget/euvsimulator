# euvsimulator — Agent Integration Guide

**Target audience:** autonomous agents, coding assistants and agent frameworks.

Every claim below was checked against the working tree of version 2.2.1 on 2026-09-12. Numbers
that go stale quickly (test counts, timings) are marked with that date.

## 1. Interfaces that exist

| Interface | Entry point | Status |
|---|---|---|
| Python API | `euvsimulator.pipeline.run_simulation` | supported |
| CLI | `euv` (Typer) | supported |
| REST API + browser GUI | `euv serve` (FastAPI, binds 127.0.0.1) | supported, no authentication |
| MCP server | — | **does not exist** |
| A2A agent endpoint | — | **does not exist** |
| Hosted docs site | — | **does not exist**, docs live in the repository |

Versions 2.1–2.2.0 shipped `mcp/server.json` and `.well-known/agent-card.json` describing an MCP
server and an A2A endpoint. No code ever backed them, and their schemas had drifted from the real
parameters. Both files were removed in 2.2.1. If you are an agent looking for a tool endpoint:
call the CLI, the Python API, or the local REST API instead.

## 2. Installation

```bash
pip install -e ".[dev]"    # pytest, ruff, mypy, jupyter
pytest -q                  # 989 tests collected (2026-09-12)
```

Python 3.10 to 3.13. PyTorch, NumPy, SciPy. GPU optional (MPS on Apple Silicon, CUDA elsewhere).

## 3. Python API

```python
from euvsimulator.pipeline import SimulationConfig, run_simulation

cfg = SimulationConfig(
    period_nm=64.0,            # wafer scale; the mask carries 4x larger features
    line_width_nm=32.0,
    dose_mj_cm2=1.3,           # dose-to-size of the default resist at 64/32
    na=0.33,
    sigma=0.8,
    illumination_shape="conventional",  # annular | dipole | dipole_x | dipole_y | quasar
    resist_model="full_chem",  # or "aerial_threshold" (default)
    grid=256,
    focus_nm=0.0,
)
result = run_simulation(cfg)
```

`SimulationResult` fields: `cd_nm`, `nils_value`, `ler_nm`, `lwr_nm`, `aerial_image`,
`resist_profile`, `absorber_reflectivity`, `clear_field_reflectivity`, `ler_metadata`.

Defaults worth knowing: `se_blur_nm=2.5` (Thackeray 2010), `dill_A=0.0`, `dill_B=4.44`,
`dill_C=0.0152`, `use_rcwa=False` (thin mask), `enable_stochastic=False`,
`stochastic_n_realisations=1`. `RESIST_PRESETS` holds SE-blur values only:
CAR 2.5, nonCAR 2.5, HighNA 3.0 nm; the latter two are unsourced placeholders.

Stochastic runs add shot noise and roughness:

```python
cfg = SimulationConfig(period_nm=64.0, line_width_nm=32.0, dose_mj_cm2=1.3,
                       resist_model="full_chem", enable_stochastic=True,
                       stochastic_n_realisations=10, stochastic_seed=42, se_blur_nm=5.0)
```

Named measurement anchors are in `euvsimulator.presets`: `nxe1716_config()`, `met2d_config()`,
`load_nxe1716_anchor()`, `load_met2d_anchor()`. The anchor data sits in
`src/euvsimulator/data/anchors/`.

A simulation can be cancelled and reports progress; see `SimulationCancelledError` and the
progress hook in `pipeline.py`.

## 4. CLI

| Command | Purpose |
|---|---|
| `simulate` | one end-to-end simulation |
| `process-window` | Bossung plot over dose × focus, CD heatmap, DoF and EL |
| `calibrate` | fit resist parameters to measured wafer CD data (`--bands` for uncertainty) |
| `make-mask` | line/space test mask as GDSII |
| `serve` | browser GUI and REST API |
| `materials` | query the CXRO database |
| `bench` | performance benchmark |
| `version`, `info` | version and system information |

There is no `euv notebook` command; open the notebooks with Jupyter directly.

## 5. Post-processing and calibration helpers

```python
from euvsimulator.metro.process_window import process_window, dose_matrix
# process_window(cd_matrix, doses, focuses, target_cd=32.0, tolerance=0.1)
#   -> {"dof_nm", "el_pct", "best_dose", "best_focus", ...}

from euvsimulator.calibrate import WaferCDData, fit_resist_params, bootstrap_fit
# WaferCDData(dose_values, focus_values, cd_matrix_nm)
# fit_resist_params(data, initial_params, pipeline_fn, bounds=None, method="Nelder-Mead")
```

`dose_matrix` calls `pipeline_fn(dose, focus)` positionally and does not swallow exceptions.

## 6. Notebooks

Six notebooks in `notebooks/`, all executed in CI on pushes to `main` and on pull requests
(skipped for tags, whose commit has already run on `main`).

| Notebook | Focus |
|---|---|
| `01_aerial_image.ipynb` | aerial image formation, pupil, coherence |
| `02_nils_cd.ipynb` | NILS, CD extraction, SE-blur effect |
| `03_resist_chain.ipynb` | Dill ABC, PEB, development, photon budget |
| `04_process_window.ipynb` | Bossung, DoF/EL, NA comparison, MEEF |
| `05_stochastics.ipynb` | shot noise, LER/LWR, dose scaling |
| `06_mask3d.ipynb` | RCWA orders, convergence, best focus |

## 7. What a physics change must pass

1. `pytest -q` — the full suite, including goldens held to 1e-4 nm.
2. The NILS gate in `tests/test_reference_nils.py`: the difference to an inlined NumPy/SciPy
   Hopkins reference (no euvsimulator imports) must stay below 0.3.
3. All six notebooks execute without error.
4. `ruff check .` and `mypy src`.

Before changing physics, measure the change with a monkey patch against a falsifiable prediction
written down in advance. `docs/physics.md` records every default with its source and status.

## 8. Scientific status

| Layer | Status |
|---|---|
| Hopkins/TCC optics | internally validated against an independent NumPy reference |
| Mo/Si multilayer TMM | internally validated, Fresnel limits and phase confirmed |
| Aerial image, threshold resist | implemented, grid-convergent |
| Full chemistry (Dill, PEB, Mack) | implemented, defaults sourced |
| Stochastics, LER/LWR | implemented |
| Wafer calibration | implemented, with uncertainty bands |
| External quantitative validation | **open**: at the NXE1716 anchor the printing dose is 1.7–1.9× the measurement; at MET-2D the roughness is 4.3 nm 3σ against 6.7 nm measured |

Known model weakness: the `aerial_threshold` model normalises the threshold to the image mean
(`resist_threshold_norm × mean(aerial) × 20/dose`), so its MEEF is 0.50 where the full chemistry
gives 1.28. Use `resist_model="full_chem"` for mask-error sensitivity. See README, known
limitations.

## 9. Repository layout

```
src/euvsimulator/
  source/      LPP Sn-plasma power budget (parametric, not wired into imaging)
  materials/   CXRO f1/f2 database
  optics/      multilayer TMM
  mask3d/      RCWA 1D/2D
  aerial/      Abbe/Hopkins imaging
  resist/      Dill ABC, SE blur, PEB kinetics, development, stochastics
  metro/       CD metrology, process window
  calibrate/   wafer fitting, bootstrap, bands
  io/          CLI, GDSII, rasterisation
  api/         FastAPI REST server and browser GUI
  accel/       device selection, VRAM budget, chunking
  etch/, opc/  etch bias and an ILT bridge; not wired into the pipeline or CLI
  pipeline.py  end-to-end orchestration, SimulationConfig, SimulationResult
  presets.py   named anchors: nxe1716_config(), met2d_config()
  constants.py physical constants; materials.py thin material helpers
tests/         989 tests (2026-09-12)
notebooks/     6 notebooks
```

## 10. Contributing

```bash
git checkout -b feat/your-change
pytest -q && ruff check . && mypy src
git commit -m "feat(scope): description"   # conventional commits
```

Issues and Discussions are open; security reports go through GitHub private vulnerability
reporting, see `SECURITY.md`. Licence Apache-2.0.
