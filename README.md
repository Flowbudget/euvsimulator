1|# euvsimulator — Open Source Extreme Ultraviolet Lithography Simulator
2|
3|[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
4|[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
5|[![CI](https://github.com/Flowbudget/euvsimulator/actions/workflows/ci.yml/badge.svg)](https://github.com/Flowbudget/euvsimulator/actions)
6|[![Tests](https://img.shields.io/badge/tests-880%2B%20passing-brightgreen)](https://github.com/Flowbudget/euvsimulator)
7|[![Release](https://img.shields.io/github/v/release/Flowbudget/euvsimulator?include_prereleases&sort=semver)](https://github.com/Flowbudget/euvsimulator/releases)
8|9|
10|**From plasma source to CD metrology — full-stack EUV lithography simulation on your laptop.**
11|
12|| | |
13||---|---|
14|| ⚛️ **First-principles physics** | CXRO atomic scattering → TMM reflectivity → RCWA mask diffraction → Hopkins imaging → Dill ABC resist |
15|| 🚀 **GPU-native** | PyTorch autograd throughout — differentiable from mask geometry to CD |
16||| 🧪 **Tested** | 880+ unit tests, cross-checked against CXRO material database |
17|| 📦 **Zero commercial dependencies** | Apache 2.0 — fork, modify, deploy freely |
18|| 🌐 **Web API + Dashboard** | FastAPI REST server with interactive web UI |
19|| 📓 **Teaching-ready** | 6 executable Jupyter notebooks covering full pipeline |
20|
21|---
22|
23|## What makes euvsimulator different?
24|
25|euvsimulator is the **only open-source tool that models the complete EUV lithography pipeline from photon to CD**:
26|
27|| Module | Method | euvsimulator | IMD | GD-Calc | OpenLithoHub |
28||--------|--------|--------|-----|---------|--------------|
29|| **Material constants** | CXRO/Henke f₁,f₂ | ✅ | ✅ | ❌ | ❌ |
30|| **Multilayer mirror** | Transfer-Matrix (S-matrix) | ✅ | ✅ | ❌ | ❌ |
31|| **Mask diffraction** | RCWA 1D/2D + S-matrix cascade | ✅ | ❌ | ✅ | ❌ |
32|| **Aerial image** | Hopkins/Abbe + pupil + source | ✅ | ❌ | ❌ | ❌ |
33|| **High-NA optics** | Anamorphic 4×/8×, Zernike | ✅ | ❌ | ❌ | ❌ |
34|| **Resist chemistry** | Dill ABC + PEB + development | ✅ | ❌ | ❌ | ❌ |
35|| **Plasma source** | LPP Sn-droplet spectral model | ✅ | ❌ | ❌ | ❌ |
36|| **Stochastics** | Shot noise, LER/LWR | ✅ | ❌ | ❌ | ✅ |
37|| **CD metrology** | Process window, Bossung | ✅ | ❌ | ❌ | ❌ |
38|| **Optimization** | Differentiable OPC/ILT bridge | ✅ | ❌ | ❌ | ✅ |
39|| **Web API** | REST + dashboard | ✅ | ❌ | ❌ | ❌ |
40|
41|IMD is the gold standard for multilayer reflectivity. GD-Calc solves rigorous coupled-wave analysis. OpenLithoHub benchmarks OPC quality. **euvsimulator is the only tool that connects all the physics** — from plasma spectrum through mask diffraction to developed resist profile.
42|
43|---
44|
45|## Verified reference calculations
46|
47|All material constants verified against the CXRO/Henke database.
48|Full details in [`docs/testberechnungen.md`](docs/testberechnungen.md).
49|
50|| Test | Result | Method |
51||------|--------|--------|
52|| **Mo optical constants** (91.84 eV) | n = 0.92335, k = 0.00647 | CXRO database interpolation |
53|| **Si optical constants** (91.84 eV) | n = 0.99900, k = 0.00183 | CXRO database interpolation |
54|| **Mo/Si multilayer** 50 BL @ 6° | **R = 64.7%** (ideal) / 60.6% (σ=0.5 nm) | S-matrix TMM + Névot-Croce |
55|| **Wavelength: 13.5 nm** | — | E = hc/λ = 91.84 eV |
56|| **Illumination: NA 0.33** | Conventional, σ = 0.8 | Dipole / annular / quasar |
57|| **Aerial image NILS** | **5.48** @ 64 nm pitch, 32 nm CD (ideal) → **2.70** with SE blur 10 nm | Hopkins formulation + SE blur |
58|| **Process window** | CD vs. dose × focus | Bossung plot |
59|

61|
62|---
63|
64|### Secondary-Electron (SE) Blur
65|
66|The `se_blur_nm` parameter models the resist point-spread function: EUV photoelectrons
67|and Auger electrons undergo a random walk before generating photoacid, blurring the
68|aerial image at the nm scale. This is **the dominant physical cause of finite NILS**
69|in real EUV processes.
70|
71|```python
72|from euvsimulator.pipeline import SimulationConfig, RESIST_PRESETS
73|
74|# Ideal optical image (unrealistically high NILS)
75|cfg = SimulationConfig(se_blur_nm=0.0)
76|
77|# Realistic CAR resist
78|cfg = SimulationConfig(se_blur_nm=RESIST_PRESETS["CAR"])  # 5.0 nm
79|
80|# Or explicit
81|cfg = SimulationConfig(se_blur_nm=10.0)
82|```
83|
84|Typical values:
85|- `RESIST_PRESETS["CAR"]` = 5.0 nm (chemically amplified resist)
86|- `RESIST_PRESETS["nonCAR"]` = 2.5 nm (non-CAR)
87|- `RESIST_PRESETS["HighNA"]` = 3.0 nm (High-NA EUV, smaller features)
88|
89|**Without SE blur, NILS reflects only the 3-order optical contrast and is unrealistically high (~5–8). With 5–10 nm blur, NILS drops to the physically correct range of 2–3.**
90|
91|---
92|
93|## Quick start
94|
95|### Installation
96|
97|```bash
98|# From GitHub (latest main branch)
99|pip install git+https://github.com/Flowbudget/euvsimulator.git
100|
101|# Or clone and install from source (for development)
102|git clone https://github.com/Flowbudget/euvsimulator.git
103|cd euvsimulator
104|pip install -e .                       # install from local source
105|pip install -e ".[dev]"                # with dev dependencies
106|```
107|
108|### Command-line interface
109|
110|```bash
111|# End-to-end simulation
112|euv simulate --period=64 --cd=32 --dose=20
113|
114|# End-to-end with realistic SE blur (10 nm)
115|euv simulate --period=64 --cd=32 --dose=20 --se-blur=10
116|
117|# Use CAR resist preset (5 nm SE blur)
118|euv simulate --period=64 --cd=32 --dose=20 --resist-preset=CAR
119|
120|# Process window (dose-focus Bossung plot)
121|euv process-window --period=64 --cd=32
122|
123|# Web dashboard (REST API + interactive UI)
124|euv serve
125|# → http://localhost:8000
126|
127|# Query material database
128|euv materials Mo --energy=91.84
129|
130|# Generate test mask (GDSII)
131|euv make-mask --period=64 --cd=32 --output=mask.gds
132|
133|# Performance benchmark
134|euv bench
135|
136|# System info
137|euv info
138|```
139|
140|### Python API
141|
142|```python
143|from euvsimulator.pipeline import SimulationConfig, run_simulation
144|
145|cfg = SimulationConfig(
146|    period_nm=64, line_width_nm=32,
147|    dose_mj_cm2=20, na=0.33, sigma=0.8,
148|    resist_model="full_chem",
149|    se_blur_nm=5.0,  # CAR resist
150|)
151|result = run_simulation(cfg)
152|print(f"CD = {result.cd_nm:.1f} nm")
153|print(f"NILS = {result.nils_value:.3f}")
154|
155|# With RCWA mask-3D (Phase 4)
156|result_rcwa = run_simulation(cfg, use_rcwa=True)
157|print(f"RCWA CD = {result_rcwa.cd_nm:.1f} nm")
158|```
159|
160|### Jupyter Notebooks (6 tutorials)
161|
162|```bash
163|cd notebooks
164|jupyter lab  # or: jupyter notebook
165|```
166|
167|| Notebook | Description |
168||----------|-------------|
169|| `01_aerial_image.ipynb` | TMM → RCWA → Hopkins → SE blur → NA/σ sensitivity |
170|| `02_nils_cd.ipynb` | NILS definition, SE blur impact, Bossung curves, resolution limits |
171|| `03_resist_chain.ipynb` | Dill ABC → PEB reaction-diffusion → Mack development → 1/√D scaling |
172|| `04_process_window.ipynb` | DoF/EL extraction, MEEF, SE blur/NA sweeps, CSV/PNG export |
173|| `05_stochastics.ipynb` | Poisson shot noise, LER/LWR extraction, multi-realisation stats, QE sweep |
174|| `06_mask3d.ipynb` | Thin-mask vs RCWA (mask-scale), best focus shift, TE/TM |
175|
176|All notebooks execute cleanly via `jupyter nbconvert --execute` (tested in CI).
177|
178|---
179|
180|## Architecture
181|
182|```
183|src/euvsimulator/
184|├── source/         LPP Sn-plasma emission model (spectrum + dose)
185|├── materials/      CXRO atomic scattering factors f₁,f₂ (Z = 1–92)
186|├── optics/         Multilayer TMM (S-matrix, Névot-Croce, grading)
187|├── mask3d/         RCWA 1D/2D Fourier Modal Method (stable S-matrix)
188|├── aerial/         Abbe/Hopkins imaging, pupil, source shapes
189|├── resist/         Dill ABC exposure, PEB, development, shot noise
190|├── io/             CLI, GDSII, rasterization
191|├── metro/          CD metrology, process window, SEM rendering
192|├── opc/            Differentiable OpenILT bridge
193|├── accel/          GPU acceleration + VRAM management
194|├── etch/           Etch bias model
195|├── calibrate/      Wafer calibration (scipy optimisation)
196|├── api/            FastAPI REST server + web dashboard
197|└── pipeline.py     End-to-end simulation orchestration
198|```
199|
200|```
201|┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
202|│ SOURCE │ → │  MASK  │ → │OPTICS │ → │ AERIAL │ → │ RESIST │ → │ METRO  │
203|│ LPP Sn │   │ RCWA   │   │ TMM   │   │Hopkins│   │Dill ABC│   │ CD/PW  │
204|└────────┘   └────────┘   └────────┘   └────────┘   └────────┘   └────────┘
205|```
206|
207|---
208|
209|## CLI reference
210|
211|| Command | Description |
212||---------|-------------|
213|| `euv simulate` | Full end-to-end simulation (CLI args or YAML/JSON config) |
214|| `euv process-window` | Dose-focus Bossung grid → DoF + EL |
215|| `euv make-mask` | Generate line/space test mask (GDSII) |
216|| `euv materials` | List elements / query n + ik at any photon energy |
217|| `euv serve` | Launch the REST API + web dashboard |
218|| `euv bench` | Performance benchmark |
219|| `euv info` | System + module overview |
220|| `euv version` | Print version |
221|| `euv calibrate` | Calibrate resist-model parameters to measured wafer CD data |
222|
223|---
224|
225|## Documentation
226|
227|Full Sphinx documentation at [`docs/`](docs/):
228|- [Overview](docs/overview.rst)
229|- [Installation](docs/install.rst)
230|- [Architecture](docs/architecture.rst)
231|- [Quickstart](docs/quickstart.rst)
232|- [API reference](docs/api/modules.rst)
233|- [Contributing](docs/contributing.rst)
234|
235|Build locally:
236|```bash
237|pip install sphinx sphinx-rtd-theme
238|cd docs && make html
239|```
240|
241|---
242|
243|## Project status
244|
245|| Milestone | Status |
246||-----------|--------|
247|| Project scaffold & CXRO materials | ✅ |
248|| Multilayer optics (S-matrix TMM) | ✅ |
249|| Mask 3D (RCWA 1D + 2D) | ✅ RCWA 1D/2D (S-matrix), integrated via `use_rcwa=True`; runs at mask scale (`mask_demagnification`, 4×). ⚠️ `absorber_taper_deg`/`mask_undercut_nm` are **not implemented** — non-default values raise `NotImplementedError` (2026-09-04; before that they were silently ignored) |
250|| Aerial image (Abbe/Hopkins + SE blur) | ✅ |
251|| High-NA imaging (anamorphic) | ✅ |
252|| End-to-end pipeline | ✅ |
253|| LPP source model | ✅ |
254|| Resist chemistry (Dill ABC + PEB + Mack) | ✅ Depth-resolved Dill exposure, isotropic PEB reaction-diffusion with acid-base quenching, Mack rate, Eikonal (fast-sweeping) development front with lateral dissolution (`development_model="eikonal"`, 2026-09-04) |
255|| Stochastic effects (shot noise, LER/LWR) | ✅ Shot noise, LER/LWR, 1/√Dose scaling, Monte-Carlo |
256|| CD metrology & process window | ✅ |
257|| Inverse lithography (OpenILT bridge) | ✅ |
258|| GPU acceleration | ✅ |
259|| REST API + web UI | ✅ |
260|| Tutorials & documentation | ✅ 6 notebooks complete |
261|| Docker deployment | ✅ |
262|| **CI/CD pipeline** | ✅ **GitHub Actions: Linux/macOS/Windows × Python 3.10–3.13** |
263||| **Test count** | **880+ passing, no expected failures** (2026-09-05; see `pytest tests`) |
264|| **License** | Apache 2.0 |
265|
266|---
267|
268|## Roadmap / Known TODOs
269|
270|> **Validation status (2026-09-06).** The numerics are validated against exact solutions and
> conservation laws (Fresnel/effective-medium limits and R+T=1 for the RCWA, mass conservation of
> the PEB solver, exact Eikonal arrival times, tiling and grid-refinement invariance of the CD).
> The default resist is built around Yamamoto et al. 2011, Polymer A (dissolution parameters,
> PEB kinetics), with every number traceable to a measurement in the source comments of
> `pipeline.py`: the dose scale is anchored to that paper's own flood-exposure measurements
> (deprotection rate and acid lifetime from the FT-IR kinetics, Figs. 3/4), which then reproduce
> the independent dissolution threshold of Fig. 5 (0.76 vs ≈ 0.8 mJ/cm²,
> `tests/test_yamamoto_anchor.py`); Table 2's PROLITH Arrhenius pair did not (≈ 3.4× off) and is
> kept as a guard test. The absorption coefficient B is computed from the resist composition
> via the CXRO tables (4.44 µm⁻¹, `tests/test_absorption_coefficient.py`), and the Dill C is a
> direct base-titration measurement (LBNL, MET-2D, 0.0152 cm²/mJ) rather than the PROLITH fit
> value, so that the implied acids per absorbed photon (1.0–1.2) sit near the measured 1.4–2.1
> instead of 6 (`tests/test_acid_yield.py`). Two caveats remain:
> this is a very sensitive 2011 research resist (dose-to-size ≈ 1.3 mJ/cm² at 64 nm pitch), so
> its sensitivity and LWR are not those of a production resist and should not be compared with
> the literature without a resist-specific calibration (`euv calibrate`); and the default PEB blur (7.9 nm = sqrt(2·D·t_eff) with D = 4.2 nm²/s measured by Kang 2010 at
> 90 °C for the same polymer class, and the acid's effective lifetime from the full 110 °C curve of
> Yamamoto Fig. 3; `peb_temperature_c` selects the measured kinetics at 80–140 °C) is inside the 7.5–12 nm band of
> directly measured blur lengths of named EUV resists but is not a measurement on this resist at its
> 110 °C PEB. Two named-resist anchors exist (`euvsimulator.presets`, data under `data/anchors/`):
> NXE1716 (Vesters 2017/2019: digitised dissolution curve + 22 nm lines on an NXE3300B) and MET-2D /
> XP 5271 (LBNL C and acid yield, Sekiguchi Mack set, Anderson/Naulleau blur, E-size and LER).
> Neither validates the chain yet: the NXE1716 printing dose comes out 1.8× too high (a
> flood-vs-pattern dose inconsistency in the source data, log Fortsetzung 29), and the LER
> comparisons showed that photon shot noise alone is not the roughness -- at MET-2D it gives 0.7 nm
> 3σ against 6.7 nm measured. The derived dissolution-noise model (`development_stochasticity`,
> counting statistics of the blocked polymer units per dissolution cell, no fitted parameter) brings
> that to 5.0 nm, but scales roughly with 1/cell size (10 nm at 2.15 nm cells) and the per-row
> Eikonal has no y-coupling, so it stays off by default (log Fortsetzungen 30–34). Measured roughness values carry SEM bias
> (Lorusso/Mack 2018), which the anchor data record.
271|
272|| Area | Description | Priority |
273||------|-------------|----------|
274|| **Resist `full_chem` parameters** | Dill A/B/C/Q, PEB k/t/D/σ, Mack params exposed in Config & CLI | ✅ Done |
275|| **Stochastics in pipeline** | Integrate photon shot noise + LER/LWR → `SimulationResult` | ✅ Done |
276|| **Process window visualization** | `--output-plot` (PNG heatmap) + `--output-csv` for `euv process-window` | ✅ Done |
277|| **RCWA / Mask-3D in pipeline** | Switch from analytic thin-mask to RCWA for real mask topography | ✅ Done (v1.0) |
278|| **High-NA EUV** | Anamorphic pupil, polarisation (TE/TM), Zernike aberrations | Research |
279|| **Citation metadata** | `CITATION.cff` + Zenodo DOI for v1.0 | Medium |
280|
281|Scientific status, open physics issues and the full verification record are kept in
[`docs/audit_2026-09-04_vollpruefung.md`](docs/audit_2026-09-04_vollpruefung.md) and
[`docs/claude_code_arbeitslog.md`](docs/claude_code_arbeitslog.md); earlier reports are
indexed in [`docs/history/`](docs/history/README.md).
282|
283|---
284|
285|## Discoverability & Citation
286|
287|### GitHub Topics
288|`euv-lithography` `semiconductor-simulation` `computational-lithography` `rcwa` `hopkins-imaging` `resist-modeling` `dill-model` `multilayer-optics` `plasma-physics` `open-source` `python` `pytorch` `fastapi` `scientific-computing`
289|
290|### For researchers
291|If you use euvsimulator in your research, please cite it:
292|
293|```bibtex
294|@software{euvsimulator2026,
295|  author       = {Flowbudget},
296|  title        = {euvsimulator: Open Source EUV Lithography Simulator},
297|  version      = {1.0.3},
298|  year         = {2026},
299|  url          = {https://github.com/Flowbudget/euvsimulator},
300|  license      = {Apache-2.0},
301|  doi          = {10.5281/zenodo.XXXXXXX}
302|}
303|```
304|
305|A Zenodo DOI will be minted with the v1.0 release.
306|
307|---
308|
309|## License
310|
311|Apache 2.0 — see [`LICENSE`](LICENSE).
312|
313|---
314|
315|## How to contribute
316|
317|We welcome contributions! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.
318|
319|- 🐛 Open an [issue](https://github.com/Flowbudget/euvsimulator/issues) for bugs
320|- 💡 Start a [discussion](https://github.com/Flowbudget/euvsimulator/discussions) for features
321|- 🔀 Submit pull requests on the `main` branch
322|- 📝 Improve documentation or add tutorials
323|- 🎓 If you use euvsimulator in research, cite it! (citation coming with v1.0)
324|
325|---
326|
327|## Support
328|
329|PayPal: **gofter@web.de** — send via PayPal Friends & Family
330|
331|Development supported by [GitHub Sponsors](https://github.com/sponsors/Flowbudget) and PayPal donations.
332|OpEnUV is open source — contributions welcome. ❤️