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

| Module | Status | Phase |
|--------|--------|-------|
| Materials DB | ✅ Done | P1 |
| TMM Multilayer | ⏳ WIP | P2 |
| RCWA 1D | ❌ | P3 |
| GDSII I/O | ❌ | P4 |
| Aerial Image | ❌ | P5 |
| End-to-End | ❌ | P6 |
| Plasma Source | ❌ | P7 |
| Resist | ❌ | P8 |
| REST API | ❌ | P10 |
| 1st OSS Release | ❌ | P10 |

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Sponsors

Development supported by [GitHub Sponsors](https://github.com/sponsors/Flowbudget).  
OpEnUV is open source — contributions welcome.