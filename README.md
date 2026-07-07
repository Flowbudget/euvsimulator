# OpEnUV – Open Source Extreme Ultraviolet Lithography Simulator

**GPU-native. Modular. Apache-2.0.**  
From plasma source to CD metrology — open-source EUV lithography simulation for research and education.

```bash
pip install -e .
euv simulate                          # 32 nm L/S, NA 0.33
euv process-window --period=64 --cd=32
euv serve                              # REST API on :8000
```

## Quick Start

```bash
git clone https://github.com/Flowbudget/OpEnUV.git
cd OpEnUV
pip install -e ".[dev]"
pytest tests/ -q                      # 315+ tests, all passing
```

## Architecture

```
src/euv/
├── constants/       Physical constants + conversion helpers
├── materials/       CXRO material database (Henke f1, f2)
├── optics/          Multilayer mirrors (S-matrix TMM) + collector
├── mask3d/          RCWA 1D + 2D Fourier Modal Method + S-matrix cascade
├── aerial/          Abbe imaging + Hopkins/TCC + pupil + source shapes
├── source/          LPP Sn-plasma emission + dose model
├── resist/          CAR exposure, PEB, development, stochastics
├── opc/             OpenILT bridge (differentiable inverse lithography)
├── io/              GDSII layout I/O + rasterization + CLI
├── metro/           CD metrology + process window + SEM rendering
├── accel/           GPU acceleration layer + VRAM budget manager
├── etch/            Etch bias model (empirical / isotropic)
├── calibrate/       Wafer calibration pipeline (scipy fit)
├── api/             FastAPI REST server + web dashboard
└── pipeline.py      End-to-end simulation pipeline
```

## CLI Usage

| Command | Description |
|---------|-------------|
| `euv simulate` | Run full simulation (config file or CLI args) |
| `euv make-mask` | Generate line/space mask GDSII |
| `euv process-window` | Dose-focus Bossung plot |
| `euv materials` | List/query CXRO database |
| `euv serve` | Start REST API server |
| `euv bench` | Performance benchmark |
| `euv info` | System info |

## Python API

```python
from euv.pipeline import SimulationConfig, run_simulation

cfg = SimulationConfig(period_nm=64.0, line_width_nm=32.0, dose_mj_cm2=20.0)
result = run_simulation(cfg)
print(f"CD = {result.cd_nm:.2f} nm")
```

## Milestones

| Milestone | Status | What |
|-----------|--------|------|
| Foundation | ✅ | Project scaffold, CXRO materials, constants |
| Multilayer Optics | ✅ | S-matrix TMM, Mo/Si stack, collector |
| Mask 3D Solver (1D) | ✅ | RCWA 1D Fourier Modal Method, stable branch selection |
| Mask 3D Solver (2D) | ✅ | RCWA 2D crossed gratings (contact holes, islands) |
| Layout Import | ✅ | GDSII/OASIS I/O + rasterization |
| Aerial Image | ✅ | Abbe imaging, pupil, source shapes |
| Hopkins Accelerator | ✅ | TCC + SOCS kernels for fast OPC loops |
| High-NA Imaging | ✅ | Anamorphic 4×/8× pupil, Zernike aberrations |
| End-to-End Pipeline | ✅ | Full pipeline GDS → CD |
| Source Model | ✅ | LPP Sn plasma + dose |
| Resist Core | ✅ | Exposure, PEB, development |
| Stochastic Effects | ✅ | Shot noise, LER/LWR |
| Inverse Lithography | ✅ | Differentiable OpenILT bridge |
| Physics Benchmarks | ✅ | Energy conservation, TMM cross-validation, convergence |
| REST API + Web UI | ✅ | FastAPI + Pydantic + dashboard |
| CD Metrology | ✅ | Process window, Bossung, SEM render |
| GPU Acceleration | ✅ | VRAM budget, chunked processing |
| Etch & Calibration | ✅ | Etch bias, wafer data fitting |
| Documentation | ✅ | Sphinx docs, Jupyter tutorials |
| Docker Deployment | ✅ | Dockerfile + docker-compose |
| Public Release | 🔜 | CI, PyPI, v1.0 |

**504 tests, all passing.**

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Sponsors

Development supported by [GitHub Sponsors](https://github.com/sponsors/Flowbudget).  
OpEnUV is open source — contributions welcome.