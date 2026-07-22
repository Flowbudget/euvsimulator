# OpEnUV Jupyter Notebooks

Interactive notebooks demonstrating the OpEnUV EUV lithography simulator.

## Notebooks

### 01_aerial_image.ipynb — Aerial Image Formation
Covers the complete aerial image pipeline:
- Multilayer mirror reflectivity (TMM)
- Complex mask diffraction orders (RCWA)
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
- Mack development model
- Photon shot noise → LER/LWR
- 1/√Dose scaling verification

### 04_process_window.ipynb — Process Window & Bossung Analysis
Process window characterization:
- Bossung plot computation (CD vs dose × focus)
- Depth of Focus (DoF) extraction
- Exposure Latitude (EL) calculation
- MEEF (Mask Error Enhancement Factor)
- SE blur impact on process window
- NA dependence of process window
- CSV/PNG export for reporting

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
- Thin-mask vs full RCWA comparison
- Absorber height & sidewall angle effects
- Best Focus Shift (BFS) from mask topography
- TE/TM polarization at High-NA
- Multilayer roughness impact
- Sidewall taper effects
- Mask-3D integration roadmap (Phase 4)

## Running the Notebooks

```bash
cd /Users/pi-server/Projekte/OpEnUV
jupyter lab notebooks/
```

Or start Jupyter from the project root:
```bash
cd /Users/pi-server/Projekte/OpEnUV
jupyter notebook
```

## Requirements

- OpEnUV installed in development mode (`pip install -e .`)
- JupyterLab or Jupyter Notebook
- matplotlib for plotting

```bash
pip install jupyterlab matplotlib
```