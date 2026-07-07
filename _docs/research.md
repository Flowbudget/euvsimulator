# 🔬 EUV Lithography Simulator – Components & Resources
**Date: 2026-07-07** | **Research: Hermes Agent**

---

## 1. Overview: What an EUV Simulator Must Cover

A complete EUV lithography simulator models the entire optical path from the plasma source to the developed resist:

```
Plasma Source (LPP, Sn Droplet, 13.5nm)
    ↓
Illumination Optics (Collector Mirror, Homogenizer)
    ↓
Reflective Mask (Mo/Si Multilayer + Absorber Structures)
    ↓
Projection Optics (4× Anamorphic Mirrors, NA 0.33/0.55)
    ↓
Aerial Image (at Wafer Level)
    ↓
Photoresist (Exposure, Secondary Electrons, Chem. Amplification)
    ↓
Development / Etching
```

---

## 2. 🔧 Open-Source Software (GitHub)

### 2.1 Complete EUV Simulators

| Project | Stars | Language | Description |
|---------|:-----:|:-------:|-------------|
| [**EUVlitho**](https://github.com/takahashi-edalab/EUVlitho) | ★18 | C++/Python | Rigorous EM simulator for EUV + CNN fitting for M3D parameters |
| [**ELitho**](https://github.com/takahashi-edalab/elitho) | ★2 | Python | Python-based High-NA EUV simulator (SPIE publication) |
| [**High-NA EUV Sim**](https://github.com/JiSeok1579/high-na-euv-sim) | ★0 | ? | 0.55 NA High-NA EUV, source→wafer with M3D+Resist+SMO |
| [**LithographySimulator**](https://github.com/quarterwave0/LithographySimulator) | ★40 | Python | Abbe method, partial coherence, GPU (PyTorch) |

### 2.2 Lithography Optics & Masks

| Project | Stars | Description |
|---------|:-----:|-------------|
| [**TorchLitho 2.0**](https://github.com/OpenOPC/TorchLitho-2.0) | ★46 | Differentiable lithography simulation, GPU, full-chip (ASICON'25) |
| [**OpenILT**](https://github.com/OpenOPC/OpenILT) | ★231 | Inverse Lithography Technology – mask optimization as inverse problem |
| [**OpenLithoHub**](https://openlithohub.com) | – | Benchmarks, OPC/ILT metrics, public leaderboard |
| [**OxiPhoton**](https://github.com/cool-japan/oxiphoton) | ★10 | EM wave propagation in Rust – includes multilayer mirror simulation |

### 2.3 Photoresist Simulation

| Project | Stars | Description |
|---------|:-----:|-------------|
| [**TorchResist**](https://github.com/ShiningSord/TorchResist) | ★26 | Differentiable resist simulation, PyTorch |
| **DragonResist-EUV-Foundry** | – | Production-grade resist framework (<3.5% deviation from wafer data) – GitHub appears private |
| **TU Delft Resist-MC** | – | Monte Carlo simulation of EUV↔Metal-Oxide Resist interaction |

### 2.4 General Lithography Simulators

| Project | Stars | Description |
|---------|:-----:|-------------|
| [**Advanced Lithography Sim**](https://github.com/hamzanael2k/Advanced-Lithography-Simulation-Tool) | ★12 | General lithography simulator |
| **Optolithium** (Gitee) | – | Optical lithography (educational) |

---

## 3. 📐 Physical Modules (What Must Be Built)

### 3.1 Plasma Source (LPP – Laser Produced Plasma)

```
┌─────────────────────────────────────────────────────────┐
│  Laser → Sn Droplet → Plasma → 13.5 nm EUV Emission     │
└─────────────────────────────────────────────────────────┘
```

**Parameters:**
- Wavelength: **13.5 nm** (92 eV, in-band)
- Source: CO₂ laser (10.6 µm) or Nd:YAG onto tin micro-droplets
- Pre-pulse shapes droplet → disk → Main Pulse → plasma
- Typical power: ~250W in-band (ASML NXE:3600D)
- **Open Source:** No complete plasma source simulation found
- **Research:** ARCNL (Amsterdam), Source Code Comparison Workshop (annual)
- **Custom build:** SPARTAN/FLYCHK atomic codes (NLTE plasma), RADCAL/POST for radiation transport

### 3.2 Illumination Optics (Illuminator)

```
┌─────────────────────────────────────────────────────────┐
│  Collector (Ellipsoid Multilayer) → Homogenizer → Mask   │
└─────────────────────────────────────────────────────────┘
```

- **Mo/Si Multilayer Mirrors:** 40–60 layers, ~70% reflectivity at 13.5 nm
- Collector: Ellipsoid or Winston cone geometry
- Homogenizer: Fly's-eye array or faceted mirrors
- **Simulation:** Transfer-matrix method (TMM), OxiPhoton (Rust), IMD Software
- **OxiPhoton:** Has `multilayer_mirror.rs` – good starting point

### 3.3 Reflective Mask (Reticle)

```
┌─────────────────────────────────────────────────────────┐
│  Absorber (Ta/TaN/TaBN) → 40× Mo/Si ML → Substrate      │
└─────────────────────────────────────────────────────────┘
```

- **Mask 3D (M3D) Effects:** Absorber edges diffract EUV → critical for imaging
- **EUVlitho/ELitho:** Rigorous EM simulation for M3D effects
- **CNN Fitting:** EUVlitho trains CNN from rigorous simulations → fast
- OpenILT for mask optimization (OPC/ILT)

### 3.4 Projection Optics

```
┌─────────────────────────────────────────────────────────┐
│  6–8 anamorphotic multilayer mirrors → 4× Reduction     │
└─────────────────────────────────────────────────────────┘
```

- **Low-NA:** NA 0.33 (current ASML NXE)
- **High-NA:** NA 0.55 (ASML EXE:5000 – Twinscan EXE)
- Anamorphotic: Different magnification in X/Y (4×/8×)
- Wavefront aberrations must be < λ/50
- **Simulation:** TorchLitho 2.0 (GPU), OxiPhoton

### 3.5 Aerial Image

```
┌─────────────────────────────────────────────────────────┐
│  Partial Coherence (σ) → Abbe Method → Intensity         │
└─────────────────────────────────────────────────────────┘
```

- **Abbe Method:** Summation over illumination source points
- Partial coherence (σ 0.2–1.0)
- Illumination modes: Conventional, Annular, Quasar, Dipole
- **LithographySimulator:** Implements Abbe + various modes
- **High-NA EUV Sim:** Complete from source→aerial image

### 3.6 Photoresist

```
┌─────────────────────────────────────────────────────────┐
│  EUV Photon → Photoelectron → Secondary Electron Cascade │
│  → Acid Generator → Chemical Amplification → Solubility  │
└─────────────────────────────────────────────────────────┘
```

- EUV photons (92 eV) generate primary photoelectrons
- Secondary electron cascade (0–20 eV) – shorter range than DUV
- Stochastic effects (noise) dominant at <10 nm structures
- **TorchResist:** Open source, differentiable resist modeling
- **TU Delft MC Sim:** Monte Carlo for metal-oxide resists
- **Custom build:** Discrete Stochastic Model (DSM), solved diffusion equations

### 3.7 Process Simulation (Development + Etch)

```
┌─────────────────────────────────────────────────────────┐
│  Developer Solution → Solubility Contrast → Etch Profile │
└─────────────────────────────────────────────────────────┘
```

- Anisotropic/isotropic etching
- Mack model (development kinetics)
- Kinetic Monte Carlo for rough edges (LER/LWR)

---

## 4. 🥇 Recommended Architecture (Blueprint)

Component | Recommended Approach | Open Source Basis
-----------|-------------------|------------------
**Plasma Source** | LPP Sn Droplet, CO₂ laser pulse, 13.5 nm | FLYCHK/SPARTAN (research codes)
**Collector** | 40° grazing incidence, ellipsoid | OxiPhoton TMM + custom geometry
**Multilayer Mirror** | Mo/Si, 40–60 pairs, TMM simulation | OxiPhoton `multilayer_mirror.rs`
**Mask** | Ta absorber on Mo/Si, M3D rigorous or CNN | **EUVlitho** / **ELitho**
**Illumination** | Coherence σ 0.2–0.8, Annular/Quasar | **LithographySimulator** (Abbe)
**Projection** | 4× reduction, NA 0.33–0.55, anamorphotic | **TorchLitho 2.0** (GPU)
**Aerial Image** | Partial coherence, Abbe sum | **High-NA EUV Sim**
**Resist** | CAR or MOR, SE cascade, stochastic | **TorchResist** + TU Delft MC
**Etch** | Anisotropic, Mack model | Custom build (simple)

---

## 5. 🧪 Alternative / Niche Sources

| Source | Description |
|--------|-------------|
| **PROLITH** (KLA) | Commercial, gold standard – but not open source |
| **S-Litho** (Synopsys) | Commercial, predictive lithography |
| **DragonResist** | Production-grade resist (<3.5%), GitHub unknown |
| **IMD Software** | Multilayer mirror design (CXRO Berkeley) |
| **CXRO / Berkeley Lab** | Center for X-Ray Optics, computations + databases |
| **ARCNL** (Amsterdam) | Academic Research Center for Nanolithography – public codes |
| **SPIE Advanced Lithography** | Annual conference, open-access proceedings |
| **arXiv cs.CE/cond-mat.mtrl-sci** | Latest preprints on lithography simulation |

---

## 6. ✅ Gap Analysis

### What Exists Open Source ✅
- [x] Rigorous EM simulation for Mask 3D (EUVlitho/ELitho)
- [x] GPU-accelerated lithography simulation (TorchLitho, LithographySimulator)
- [x] Inverse lithography / mask optimization (OpenILT)
- [x] Resist simulation (TorchResist, TU Delft)
- [x] Multilayer optics simulation (OxiPhoton)
- [x] Benchmarks & metrics (OpenLithoHub)

### What Is Missing / Must Be Custom Built ❌
- [ ] **Plasma source simulation** (Sn droplet, LPP, 13.5nm emission) – no open-source library
- [ ] **Complete anamorphotic optics chain** (6–8 mirrors) – partially in TorchLitho
- [ ] **Coupled source→wafer workflow** – individual modules must be integrated
- [ ] **Experimental validation** – no simulated output without calibration against real wafer data
- [ ] **Thermal management** – mirrors heat up from EUV (no model)
- [ ] **Contamination** (carbon cracking, Sn debris) – no model
- [ ] **Stochastic effects** (shot noise, LER/LWR) – partially in TorchResist

---

## 7. 📚 Scientific Basis (Papers)

| Paper | DOI / Link | Focus |
|-------|-----------|-------|
| H. Tanabe et al. (SPIE 2025) | [10.1117/1.JMM.24.2.024201](https://www.spiedigitallibrary.org/journals/journal-of-micro-nanopatterning-materials-and-metrology/volume-24/issue-2/024201) | Rigorous EM sim + CNN for EUV |
| Flow Physics of EUV Sources | [academic.oup.com/nsr](https://academic.oup.com/nsr/advance-article/doi/10.1093/nsr/nwag298) | Sn droplet flow physics |
| Microdroplet-Tin Plasma Sources | [10.1088/2040-8986/ac5a7e](https://iopscience.iop.org/article/10.1088/2040-8986/ac5a7e) | Code Comparison Workshop |
| Quantum Simulation for EUV | [arXiv:2602.20234](https://arxiv.org/html/2602.20234v1) | Quantum algorithms for resist material design |

---

## 8. 🔗 Quicklinks

```
# GitHub Repos
https://github.com/takahashi-edalab/EUVlitho
https://github.com/takahashi-edalab/elitho
https://github.com/quarterwave0/LithographySimulator
https://github.com/OpenOPC/TorchLitho-2.0
https://github.com/OpenOPC/OpenILT
https://github.com/ShiningSord/TorchResist
https://github.com/cool-japan/oxiphoton
https://github.com/JiSeok1579/high-na-euv-sim

# Portals
https://openlithohub.com
https://arcnl.nl (ARCNL Amsterdam)
https://cxro.lbl.gov (Center for X-Ray Optics)
```

---

*Created by Hermes Agent on 2026-07-07. Sources: DuckDuckGo Lite, Startpage, GitHub API, SPIE Digital Library.*