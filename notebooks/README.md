# euvsimulator Jupyter Notebooks

Interactive notebooks demonstrating the euvsimulator EUV lithography simulator.

## Notebooks

### 01_aerial_image.ipynb — Aerial Image Formation
Covers the complete aerial image pipeline:
- Multilayer mirror reflectivity (TMM)
- Thin-mask diffraction orders (analytic Fourier coefficients; RCWA via `use_rcwa`, see 06)
- Hopkins partial-coherence imaging
- SE blur effect
- NA / σ sensitivity

### 02_nils_cd.ipynb — NILS & CD Analysis
Explores the key lithography metrics:
- NILS definition and calculation
- SE blur impact on NILS
- CD extraction via fixed threshold
- Dose dependence (Bossung curve)
- Focus dependence
- Resolution limits (half-pitch sweep)

### 03_resist_chain.ipynb — Resist Chemistry Chain
Full resist chemistry simulation:
- Dill ABC exposure model
- PEB reaction-diffusion
- Mack dissolution rate (as implemented) and a threshold cut of the latent image
- Photon shot noise → LER/LWR in the full stochastic chain (the dose scaling law is in 05)

### 04_process_window.ipynb — Process Window & Bossung Analysis
Process window characterization:
- Bossung plot computation (CD vs dose × focus)
- Depth of Focus (DoF) extraction
- Exposure Latitude (EL) calculation
- MEEF (Mask Error Enhancement Factor)
- SE blur impact on process window
- NA dependence of process window
- CSV/JSON export for reporting

### 05_stochastics.ipynb — Stochastic Effects: Shot Noise, LER & LWR
Stochastic resist effects:
- Poisson photon shot noise on acid concentration
- LER (Line Edge Roughness) extraction
- LWR (Line Width Roughness) extraction
- Multiple realisations → statistical distributions
- 1/√Dose scaling law verification
- Integration into full simulation pipeline

### 06_mask3d.ipynb — Mask 3D Effects: RCWA, Topography & Best Focus Shift
Mask topography effects using RCWA:
- Thin-mask vs full RCWA comparison (60 nm Ta absorber, ±1-order asymmetry)
- TE/TM polarisation of the RCWA orders (6° chief ray)
- RCWA convergence with the number of retained orders
- Sidewall taper: not implemented (the pipeline rejects it)
- Multilayer roughness impact
- Best focus shift from mask topography, and its pitch dependence
- Status of the Mask-3D integration (`use_rcwa=True`)

## Running the Notebooks

```bash
cd euvsimulator            # the repository root
jupyter lab notebooks/
```

Or start Jupyter from the project root:
```bash
cd euvsimulator            # the repository root
jupyter notebook
```

## Requirements

- euvsimulator installed in development mode (`pip install -e .`)
- JupyterLab or Jupyter Notebook
- matplotlib for plotting

```bash
pip install jupyterlab matplotlib
```