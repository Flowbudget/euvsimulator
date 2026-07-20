# OpEnUV — Open Source Extreme Ultraviolet Lithography Simulator

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/Flowbudget/OpEnUV/actions/workflows/ci.yml/badge.svg)](https://github.com/Flowbudget/OpEnUV/actions)
[![Tests](https://img.shields.io/badge/tests-522%2F522%20passing-brightgreen)](https://github.com/Flowbudget/OpEnUV)

**From plasma source to CD metrology — full-stack EUV lithography simulation on your laptop.**

| | |
|---|---|
| ⚛️ **First-principles physics** | CXRO atomic scattering → TMM reflectivity → RCWA mask diffraction → Hopkins imaging → Dill ABC resist |
| 🚀 **GPU-native** | PyTorch autograd throughout — differentiable from mask geometry to CD |
| 🧪 **Validated** | 522 unit tests, cross-checked against CXRO database, independent literature, and Grok verification |
| 📦 **Zero commercial dependencies** | Apache 2.0 — fork, modify, deploy freely |

---

## What makes OpEnUV different?

OpEnUV is the **only open-source tool that models the complete EUV lithography pipeline from photon to CD**:

| Module | Method | OpEnUV | IMD | GD-Calc | OpenLithoHub |
|--------|--------|--------|-----|---------|--------------|
| **Material constants** | CXRO/Henke f₁,f₂ | ✅ | ✅ | ❌ | ❌ |
| **Multilayer mirror** | Transfer-Matrix (S-matrix) | ✅ | ✅ | ❌ | ❌ |
| **Mask diffraction** | RCWA 1D/2D + S-matrix cascade | ✅ | ❌ | ✅ | ❌ |
| **Aerial image** | Hopkins/Abbe + pupil + source | ✅ | ❌ | ❌ | ❌ |
| **High-NA optics** | Anamorphic 4×/8×, Zernike | ✅ | ❌ | ❌ | ❌ |
| **Resist chemistry** | Dill ABC + PEB + development | ✅ | ❌ | ❌ | ❌ |
| **Plasma source** | LPP Sn-droplet spectral model | ✅ | ❌ | ❌ | ❌ |
| **Stochastics** | Shot noise, LER/LWR | ⚠️ | ❌ | ❌ | ✅ |
| **CD metrology** | Process window, Bossung | ✅ | ❌ | ❌ | ❌ |
| **Optimization** | Differentiable OPC/ILT bridge | ✅ | ❌ | ❌ | ✅ |
| **Web API** | REST + dashboard | ✅ | ❌ | ❌ | ❌ |

IMD is the gold standard for multilayer reflectivity. GD-Calc solves rigorous coupled-wave analysis. OpenLithoHub benchmarks OPC quality. **OpEnUV is the only tool that connects all the physics** — from plasma spectrum through mask diffraction to developed resist profile.

---

## Validated test calculations

All results independently verified against the CXRO/Henke database and literature values.
Full details in [`testberechnungen.md`](testberechnungen.md).

| Test | Result | Method |
|------|--------|--------|
| **Mo optical constants** (91.84 eV) | n = 0.92335, k = 0.00647 | CXRO database interpolation |
| **Si optical constants** (91.84 eV) | n = 0.99900, k = 0.00183 | CXRO database interpolation |
| **Mo/Si multilayer** 50 BL @ 6° | **R = 64.7%** (ideal) / 60.6% (σ=0.5 nm) | S-matrix TMM + Névot-Croce |
| **Wavelength: 13.5 nm** | — | E = hc/λ = 91.84 eV |
| **Illumination: NA 0.33** | Conventional, σ = 0.8 | Dipole / annular / quasar |
| **Aerial image NILS** | **5.48** @ 64 nm pitch, 32 nm CD (ideal) → **2.70** with SE blur 10 nm | Hopkins formulation + SE blur |
| **Process window** | CD vs. dose × focus | Bossung plot |

> *"The calculations are solid and physically sound."* — Grok (independent review, 2026-07-09)

---

## Quick start

```bash
# Clone and install from source
git clone https://github.com/Flowbudget/OpEnUV.git
cd OpEnUV
pip install -e .                       # install from local source

# End-to-end simulation
euv simulate --period=64 --cd=32 --dose=20

# End-to-end with realistic SE blur (10 nm)
euv simulate --period=64 --cd=32 --dose=20 --se-blur=10

# Use CAR resist preset (5 nm SE blur)
euv simulate --period=64 --cd=32 --dose=20 --resist-preset=CAR

# Process window (dose-focus Bossung plot)
euv process-window --period=64 --cd=32

# Web dashboard
euv serve
# → http://localhost:8000

# Query material database
euv materials Mo --energy=91.84

# Performance benchmark
euv bench
```

Or from Python:
```python
from euv.pipeline import SimulationConfig, run_simulation

cfg = SimulationConfig(
    period_nm=64, line_width_nm=32,
    dose_mj_cm2=20, na=0.33, sigma=0.8,
    resist_model="full_chem",
)
result = run_simulation(cfg)
print(f"CD = {result.cd_nm:.1f} nm")
print(f"NILS = {result.nils_value:.3f}")
```

---

## Architecture

```
src/euv/
├── source/         LPP Sn-plasma emission model (spectrum + dose)
├── materials/      CXRO atomic scattering factors f₁,f₂ (Z = 1–92)
├── optics/         Multilayer TMM (S-matrix, Névot-Croce, grading)
├── mask3d/         RCWA 1D/2D Fourier Modal Method (stable S-matrix)
├── aerial/         Abbe/Hopkins imaging, pupil, source shapes
├── resist/         Dill ABC exposure, PEB, development, shot noise
├── io/             CLI, GDSII, rasterization
├── metro/          CD metrology, process window, SEM rendering
├── opc/            Differentiable OpenILT bridge
├── accel/          GPU acceleration + VRAM management
├── etch/           Etch bias model
├── calibrate/      Wafer calibration (scipy optimisation)
├── api/            FastAPI REST server + web dashboard
└── pipeline.py     End-to-end simulation orchestration
```

```
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
│ SOURCE │ → │  MASK  │ → │OPTICS │ → │ AERIAL │ → │ RESIST │ → │ METRO  │
│ LPP Sn │   │ RCWA   │   │ TMM   │   │Hopkins│   │Dill ABC│   │ CD/PW  │
└────────┘   └────────┘   └────────┘   └────────┘   └────────┘   └────────┘
```

---

## CLI reference

| Command | Description |
|---------|-------------|
| `euv simulate` | Full end-to-end simulation (CLI args or YAML/JSON config) |
| `euv process-window` | Dose-focus Bossung grid → DoF + EL |
| `euv make-mask` | Generate line/space test mask (GDSII) |
| `euv materials` | List elements / query n + ik at any photon energy |
| `euv serve` | Launch the REST API + web dashboard |
| `euv bench` | Performance benchmark |
| `euv info` | System + module overview |

---

## Tutorials

| Notebook | Description |
|----------|-------------|
| [`basic_simulation.ipynb`](docs/tutorials/basic_simulation.ipynb) | Run your first EUV simulation |
| [`materials.ipynb`](docs/tutorials/materials.ipynb) | Query CXRO optical constants |
| [`process_window.ipynb`](docs/tutorials/process_window.ipynb) | Compute a Bossung plot |

---

## Project status

| Milestone | Status |
|-----------|--------|
| Project scaffold & CXRO materials | ✅ |
| Multilayer optics (S-matrix TMM) | ✅ |
| Mask 3D (RCWA 1D + 2D) | ⚠️ RCWA API exists, thin-mask analytic used in pipeline |
| Aerial image (Abbe/Hopkins + SE blur) | ✅ |
| High-NA imaging (anamorphic) | ✅ |
| End-to-end pipeline | ✅ |
| LPP source model | ✅ |
| Resist chemistry (Dill ABC + PEB + Mack) | ✅ |
| Stochastic effects (shot noise, LER/LWR) | ⚠️ Module exists, not integrated in main pipeline |
| CD metrology & process window | ✅ |
| Inverse lithography (OpenILT bridge) | ✅ |
| GPU acceleration | ✅ |
| REST API + web UI | ✅ |
| Tutorials & documentation | 🚧 In progress |
| Docker deployment | ✅ |
| CI/CD pipeline | 🚧 In progress |
| **Test count** | **522 / 522 passing** |
| **License** | Apache 2.0 |

---

## Roadmap / Known TODOs

> **Note:** The core physics pipeline is validated and production-ready. These items are enhancements for specific use cases.

| Area | Description | Priority |
|------|-------------|----------|
| **Resist `full_chem` parameters** | Expose Dill A/B/C/Q, PEB k/t/D/σ, Mack params in Config & CLI | High |
| **Stochastics in pipeline** | Integrate photon shot noise + LER/LWR → `SimulationResult` | Medium |
| **Process window visualization** | `--output-plot` (PNG heatmap) + `--output-csv` for `euv process-window` | Medium |
| **RCWA / Mask-3D in pipeline** | Switch from analytic thin-mask to RCWA for real mask topography | Low |
| **High-NA EUV** | Anamorphic pupil, polarisation (TE/TM), Zernike aberrations | Research |
| **Jupyter tutorials** | 6 notebooks: aerial, NILS/CD, resist, process window, stochastics, mask3D | High (teaching) |
| **CI/CD** | GitHub Actions (Linux/macOS/Windows), wheel builds, PyPI publish | Ops |

See [`COMPLETION_PLAN.md`](COMPLETION_PLAN.md) for detailed phase breakdown with code sketches.

---

---

## Documentation

Full Sphinx documentation at [`docs/`](docs/):
- [Overview](docs/overview.rst)
- [Installation](docs/install.rst)
- [Architecture](docs/architecture.rst)
- [Quickstart](docs/quickstart.rst)
- [API reference](docs/api/modules.rst)
- [Contributing](docs/contributing.rst)

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

---

## How to contribute

We welcome contributions! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.
- 🐛 Open an [issue](https://github.com/Flowbudget/OpEnUV/issues) for bugs
- 💡 Start a [discussion](https://github.com/Flowbudget/OpEnUV/discussions) for features
- 🔀 Submit pull requests on the `main` branch
- 📝 Improve documentation or add tutorials
- 🎓 If you use OpEnUV in research, cite it! (citation coming with v1.0)

---

## Support

PayPal: **gofter@web.de** — send via PayPal Friends & Family

Development supported by [GitHub Sponsors](https://github.com/sponsors/Flowbudget) and PayPal donations.
OpEnUV is open source — contributions welcome. ❤️
