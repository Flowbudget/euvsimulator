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
├── optics/          Multilayer mirrors (TMM) + pupil shapes
├── mask3d/          RCWA / Waveguide solver for mask-3D effects
├── aerial/          Abbe/Hopkins partially coherent imaging
├── source/          LPP tin-plasma source model
├── resist/          Stochastic resist simulation (CAR/MOR)
├── io/              GDSII import/export + CLI
├── api/             FastAPI REST server
└── data/            CXRO material constants (auto-downloaded)
```

## Status

| Module | Status | Milestone |
|--------|--------|-----------|
| Material Database | ✅ Done | Foundation |
| Multilayer Optics | ✅ Done | Optics Core |
| Mask 3D Solver | ❌ | EM Simulation |
| Layout I/O | ❌ | Layout Import |
| Aerial Image | ❌ | Aerial Image |
| Full Pipeline | ❌ | End-to-End |
| Plasma Source | ❌ | Source Model |
| Resist Model | ❌ | Resist Core |
| Resist Stochastics | ❌ | Stochastic Effects |
| REST API | ❌ | REST API |
| First OSS Release | ❌ | Public Release |

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Sponsors

Development supported by [GitHub Sponsors](https://github.com/sponsors/Flowbudget).  
OpEnUV is open source — contributions welcome.