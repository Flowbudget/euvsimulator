# OpEnUV – Open Source Extreme Ultraviolet Lithography Simulator

**GPU-native. Modular. Apache-2.0.**  
From plasma source to CD metrology — open-source EUV lithography simulation for research and education.

```bash
pip install euv
euv simulate --config mask.yaml
euv serve                          # REST API on :8000
```

## Quick Start

```bash
git clone https://github.com/Flowbudget/OpEnUV.git
cd OpEnUV
pip install -e ".[dev]"
python scripts/download_cxro.py   # download atomic scattering factors
pytest tests/                       # run tests (-v for verbose)
```

## Architecture

```
src/euv/
├── constants/       Physical constants + conversion helpers
├── materials/       CXRO material database (Henke f1, f2)
├── optics/          Multilayer mirrors (S-matrix TMM) + collector
├── mask3d/          RCWA 1D Fourier Modal Method + S-matrix cascade
├── aerial/          Abbe partially coherent imaging + pupil + source shapes
├── source/          LPP Sn-plasma emission + dose model
├── resist/          CAR exposure, PEB, development simulation
├── io/              GDSII layout I/O + rasterization
├── api/             FastAPI REST server
└── data/            CXRO material constants (auto-downloaded)
```

## Status

| Module | Status | Milestone |
|--------|--------|-----------|
| Material Database | ✅ Done | Foundation |
| Multilayer Optics | ✅ Done | Optics Core |
| Mask 3D Solver | ✅ Done | EM Simulation |
| Layout I/O | ✅ Done | Layout Import |
| Aerial Image | ✅ Done | Aerial Image |
| Full Pipeline | ❌ | End-to-End |
| Plasma Source | ✅ Done | Source Model |
| Resist Model | ✅ Done | Resist Core |
| Resist Stochastics | ❌ | Stochastic Effects |
| REST API | ❌ | REST API |
| First OSS Release | ❌ | Public Release |

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Sponsors

Development supported by [GitHub Sponsors](https://github.com/sponsors/Flowbudget).  
OpEnUV is open source — contributions welcome.