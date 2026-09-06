# euvsimulator

**An open-source EUV lithography simulator whose every physical default has a named source.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![Version 2.1.0](https://img.shields.io/badge/version-2.1.0-blue.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-940%20passing%20locally-brightgreen.svg)](tests/)
[![Type-checked](https://img.shields.io/badge/mypy-clean-brightgreen.svg)](pyproject.toml)

euvsimulator models the EUV imaging and resist chain at 13.5 nm — multilayer mirror, mask
diffraction, partially coherent imaging, chemically amplified resist, development, and the
stochastics behind line-edge roughness — in Python and PyTorch, on a laptop.

What sets it apart is not the number of modules but the bookkeeping: each default of the resist
chain is either measured in a cited paper, derived from a cited measurement, or explicitly
labelled as a calibration or an assumption. Two named resists serve as anchors, and the distance
between simulation and measurement is documented rather than tuned away.
See [docs/physics.md](docs/physics.md) for the chain, the sources and the open questions.

## What it is — and what it is not

- **It is** a transparent, tested physics chain for studying how exposure, bake, development and
  noise interact, with the provenance of every number one click away.
- **It is not** a predictive tool for production resists. At the NXE1716 anchor the printing dose
  comes out 1.7–1.9× above the measurement (an inconsistency inside the source data) and the
  roughness is bracketed between 0.7× and 2.4× by a blur nobody has measured for that resist; at
  the MET-2D anchor the simulated roughness is 4.3 nm 3σ against 6.7 nm measured with SEM bias.
  Two physics questions that no freely available measurement decides change results by a factor
  of two; `euv calibrate --bands` reports them as bands.

## Quick start

```bash
pip install git+https://github.com/Flowbudget/euvsimulator.git
```

```bash
euv simulate --period 64 --cd 32 --dose 1.3 --resist-model full_chem   # default resist
euv process-window --period 64 --cd 32                                   # Bossung, DoF, EL
euv calibrate wafer.csv --period 44 --cd 22 --bands                      # fit your own FEM
euv serve                                                                # web dashboard
```

```python
from euvsimulator.pipeline import SimulationConfig, run_simulation

cfg = SimulationConfig(period_nm=64, line_width_nm=32, dose_mj_cm2=1.3, resist_model="full_chem")
result = run_simulation(cfg)
print(f"CD {result.cd_nm:.1f} nm, NILS {result.nils_value:.2f}")
```

The default resist is a 2011 research resist (Yamamoto et al.) and prints at about
1.3 mJ/cm² at 64 nm pitch — far more sensitive than a production resist. Use the presets in
`euvsimulator.presets` (NXE1716, MET-2D) or calibrate to your own data.

## What is inside

| Stage | Model | Notes |
|---|---|---|
| Materials | CXRO atomic scattering factors, Z = 1–92 | absorption of a resist computed from its composition |
| Multilayer mirror | S-matrix transfer-matrix method, Névot–Croce roughness | verified against Fresnel and energy-conservation limits |
| Mask | thin-mask Fourier series; RCWA 1D/2D optional | no flare, no mask roughness |
| Imaging | Abbe/Hopkins partially coherent, NA 0.33 and high-NA anamorphic | conventional, annular, dipole and quasar sources incl. scanner-style sector poles |
| Exposure | Dill ABC with depth attenuation; photon shot noise with secondary-electron spread; PAG counting | acid yield per absorbed photon checked against measurements |
| Post-exposure bake | diffuse–quench–deprotect with measured kinetics at 80–140 °C; concurrent reaction-diffusion (NIST law) optional | validated on the NIST bilayer diffusion lengths |
| Development | Mack rate, Eikonal first-arrival front, sub-pixel CD; dissolution-cell noise optional | roughness metrology passband and SEM-bias bookkeeping |
| Metrology | CD, NILS, process window, LER/LWR with correlation-aware statistics | |
| Calibration | fit to wafer FEM data, bootstrap CIs, structural uncertainty bands | |

Six executable notebooks in [`notebooks/`](notebooks/) walk through the chain.

## Validation status

Numerics are checked against exact solutions and conservation laws. The physics is anchored to
primary measurements: Yamamoto 2011 (deprotection kinetics at seven temperatures, dissolution
threshold), Kang/NIST 2009 (bilayer diffusion lengths), LBNL film quantum yields, Thackeray 2010
(blur decomposition), Vesters 2017/2019 (NXE1716 dissolution curves and 22 nm lines on an
NXE3300B), Anderson & Naulleau 2008 (MET-2D blur, dose and LER). What the chain reproduces, and
where it does not, is tabulated in [docs/physics.md](docs/physics.md) §6; the detailed record is
[docs/claude_code_arbeitslog.md](docs/claude_code_arbeitslog.md).

## Known limitations

- Not validated for production resists; see above.
- Undecided physics (factor 2): the acid-loss law in patterns (`peb_model`) and the size of the
  dissolving unit (`dissolution_cell_nm`). Experimental options are off by default and listed in
  the `SimulationConfig` docstring.
- Optics: 1D gratings, no flare, no mask roughness, defocus only. The plasma-source module is a
  parametric power-budget estimate and is not connected to the imaging chain.
- Compute: the stochastic chain at 2048 rows and grid 256 needs about 1.8 GB and minutes per
  realisation; the concurrent PEB costs ~6× more. Developed and tested on an Apple M1 with 8 GB.
- CI has not run since 2026-08-31 (account limit); all verification is local (macOS, Python 3.14).

## Documentation

- [docs/physics.md](docs/physics.md) — the chain, every default with source and status, anchors, open questions
- [CHANGELOG.md](CHANGELOG.md) — release notes; [docs/analyse_2026-09-05_stand_und_plan.md](docs/analyse_2026-09-05_stand_und_plan.md) — plan and roadmap
- Sphinx sources in [`docs/`](docs/) (`pip install sphinx sphinx-rtd-theme && cd docs && make html`)

## Citation

```bibtex
@software{euvsimulator2026,
  author  = {Flowbudget},
  title   = {euvsimulator: Open Source EUV Lithography Simulator},
  version = {2.1.0},
  year    = {2026},
  url     = {https://github.com/Flowbudget/euvsimulator},
  license = {Apache-2.0}
}
```

## License and third-party material

Apache 2.0 — see [LICENSE](LICENSE). All runtime dependencies are OSI-licensed (numpy, scipy,
torch, matplotlib, fastapi, uvicorn, pydantic, typer, httpx, gdstk); the optional dashboard loads
Chart.js (MIT) from a CDN. CXRO scattering-factor tables are redistributed unmodified with
attribution; anchor data are digitised numbers with their citations. See [NOTICE](NOTICE).

## Contributing and support

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Physics changes
follow the project rule: predict first, measure, then change the code, and keep the source of
every number.

euvsimulator is developed and tested on a single laptop. If it saves you time, you can support
the work:

[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsor-ea4aaa?logo=github&logoColor=white)](https://github.com/sponsors/Flowbudget)
[![Donate via PayPal](https://img.shields.io/badge/PayPal-Donate-00457C?logo=paypal&logoColor=white)](https://www.paypal.com/donate/?business=Gofter%40web.de&currency_code=EUR)

PayPal donations go to **Gofter@web.de**.
