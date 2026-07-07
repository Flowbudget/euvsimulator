# 🏭 EUV Lithography Simulator – Commercial Strategy & Blueprint
**Status: 2026-07-07** | **Created by Hermes Agent** | **Classification: Strategic Planning Document**

> **⚠️ REVIEW WARNING (2026-07-07):** This document has been UPDATED based on a destructive review.
> **Corrected Errors:** (1) ELitho has NO RCWA (only TMM+Fourier), (2) Export control is not universally solvable, (3) VRAM for RCWA >>16GB, (4) Panoramic HyperLith v7 underestimated, (5) Data gap ~65/20/15% instead of 80/15/5%
> **Full Review:** `./2026-07-07-EUV-Lithography-Simulator-Strategy-DESTRUCTIVE-REVIEW.md`

---

## Executive Summary (CORRECTED)

> **An EUV lithography simulator is ~65% realizable from publicly available data and open-source code, with another ~20% fittable.** The remaining ~15% (exact resist chemistry, scanner calibration, multilayer interdiffusion) are trade secrets. **BUT:** ELitho (the tool we identified as core) has NO RCWA – it only implements TMM+Fourier optics. The critical component (rigorous mask-3D solver) must be developed from scratch. The market niche (China/export-restricted markets) is smaller than initially assumed (SMIC has ASML access), but education + research + SMEE remain genuine opportunities. Export to China is NOT universally legal – EU Dual-Use Regulation and Wassenaar must be reviewed.

---

## Part 1: 🎯 The Niche

### 1.1 Primary Niche – China / Export-Restricted Markets (CORRECTED)

**Revised analysis after review:** SMIC (the most well-known Chinese fab) HAS ASML scanners (NXE:3400C) and access to Brion Tachyon – acquired before the 2023 export restrictions. The primary niche is therefore **not** SMIC itself, but:

| Group | Examples | Size |
|-------|----------|------|
| **Research institutes without scanners** | IMECAS, PKU, CAS Institute | ~15 institutions |
| **SMEE (scanner developer)** | Shanghai Micro Electronics Equipment | 1 organization |
| **Chinese universities** | Tsinghua, Fudan, UCAS | ~20 universities |
| **Smaller fabs without ASML EUV** | Research, non-production | ~5–10 |

**Size:** ~10–15 organizations with real need, estimated: **$2–$10 million/year** (revised from $10–30M).

**BUT – CRITICAL CAVEAT:** Export to China is **NOT** universally legal. EU Dual-Use Regulation 2021/821, Wassenaar Arrangement Category 3 (Electronics), and the German AWV can classify EUV simulation software as requiring a permit – regardless of the open-source license. BAFA review BEFORE product development is mandatory.

### 1.2 Secondary Niches

| Niche | Customers | USP | Accessibility |
|-------|-----------|-----|---------------|
| **Education sector** | 100+ universities worldwide | "EUV Lite" for €2,000/year | Easy, brand-building |
| **Chip startups** | ~200 startups | Pay-per-simulation (Cloud) | SaaS infrastructure |
| **Small fabs** | X-Fab, LFoundry | Site license <€50,000 | Medium |
| **Research labs** | Fraunhofer, IHP, CEA | Open Core + Support | Open source base |
| **Non-ASML fabs** | Canon, Nikon, SMEE | Scanner-independent | Medium |

### 1.3 Product Positioning

```
           HIGH-PRICED
               │
               │    KLA PROLITH ($50k–$500k)
               │    Synopsys S-Litho
    COMPLEX ───┼─── SIMPLE
               │    ★ OUR PRODUCT ★
               │    (Open Core + Commercial)
               │    Panoramic ($10k–$200k)
               │
           LOW-PRICED
```

**Position:** Affordable, modern, open-source-based alternative focused on:
- **Modern API** (REST, Python SDK, Jupyter Notebooks)
- **GPU-native simulation** (TorchLitho/PyTorch backend)
- **Transparent models** (no black box)
- **SaaS/pay-per-use** available
- **German hosting** → EU GDPR-compliant, export-friendly

---

## Part 2: 🧩 Open-Source License Compatibility

Before any code is written, it must be clear: **Which open-source components can we safely incorporate into a commercial product?**

### 2.1 License Traffic Light

| Project | License | Commercially usable? | Conditions |
|---------|---------|:--------------------:|------------|
| **ELitho** | **MIT** | ✅ Yes | No restrictions. Attribution suffices. |
| **EUVlitho** | **MIT** | ✅ Yes | No restrictions. |
| **OpenILT** | **MIT** | ✅ Yes | Ideal foundation for mask optimization. |
| **TorchLitho 2.0** | **Apache-2.0** | ✅ Yes | Observe patent clause. Document changes. |
| **TorchResist** | **Apache-2.0** | ✅ Yes | As usual with Apache. |
| **OxiPhoton** | **Apache-2.0** | ✅ Yes | (API showed NOASSERTION, LICENSE file is Apache-2.0) |
| **LithographySimulator** | **LGPL-2.1** | ⚠️ Yes, with restriction | LGPL permits commercial use. **Do not modify** → link dynamically. Or keep as separate submodule. |
| **PyTorch** | **BSD-3** | ✅ Yes | Commercial, no restrictions. |
| **High-NA EUV Sim** | **NONE** | ❌ No | Without license = All Rights Reserved. We may not use it. |

### 2.2 Strategy: How to Handle Licenses

| License | Strategy |
|---------|----------|
| **MIT** | Incorporate directly, preserve copyright header |
| **Apache-2.0** | Incorporate directly, maintain NOTICE file, document changes |
| **LGPL-2.1** | Keep as **separate submodule**, dynamic linking. Core product remains proprietary. |
| **No license** | Avoid entirely. Use only as inspiration source. |

**Recommended license model for the product itself:**
- **Open Core:** AGPL-3.0 or Apache-2.0 (for community)
- **Commercial Features:** Proprietary license (plugins, enterprise add-ons)
- **Role models:** GitLab, VS Code, n8n

---

## Part 3: 🏗️ Product Architecture

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WEB UI / DASHBOARD                        │
│           (React/Vue – Visual Workflow Editor, Results)          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API / WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                    PYTHON SDK / CLI                              │
│  (Jupyter-capable, CI/CD-integration, Batch Processing)         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                    CORE ENGINE (Python/PyTorch)                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ OPTICS MODULE│  │ SOURCE MODULE│  │ RESIST MODULE    │      │
│  │ (MIT)        │  │ (Custom)     │  │ (Apache-2.0)    │      │
│  │ - TMM (Multi)│  │ - Sn-Plasma  │  │ - SE Cascade MC │      │
│  │ - RCWA (Mask)│  │ - Spectrum   │  │ - CA Model      │      │
│  │ - Abbe/Fourier│ │ - Collector  │  │ - Stochastics   │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ OPTIMIZATION LAYER  (Apache-2.0)                       │     │
│  │ OpenILT + Diff. Resist + Custom                        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  GPU ACCELERATION (PyTorch CUDA) ←── NVIDIA/AMD GPU             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   INPUT/OUTPUT LAYER                             │
│                                                                  │
│  INPUT:                    OUTPUT:                              │
│  - GDSII/OASIS Layout      - Aerial Image (TIFF/PNG)            │
│  - Mask Design             - Resist Contour (GDSII)             │
│  - Process Parameters      - CD/Metrology Data (CSV)            │
│  - Source Parameters       - SEM Simulation                     │
│                             - Process Window (PW)               │
│                             - OPC/RET Models                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Interfaces (API/Interface Design)

| Interface | Protocol | Purpose |
|-----------|----------|---------|
| **REST API** | HTTPS/JSON | Cloud/SaaS integration, CI/CD pipelines |
| **Python SDK** | `pip install euv-sim` | Scripting, notebooks, automation |
| **CLI** | `euv-sim run --config config.yaml` | Batch processing in fabs |
| **Jupyter Extension** | Widgets + Visuals | Interactive exploration |
| **GDSII/OASIS Import** | File | Layout integration (standard) |
| **SEM Image Export** | PNG/TIFF + Header | Comparison with real wafer images |
| **OPC Bridge** | OpenILT-compatible | Inverse lithography integration |

### 3.3 Software Stack (Recommendation) – CORRECTED

| Layer | Technology | Rationale | Status |
|-------|------------|-----------|--------|
| **Language** | Python (Core), Rust (Performance-Critical) | Python = ML/GPU-native, Rust for RCWA/Plasma | To be written from scratch |
| **GPU** | PyTorch (CUDA) | TorchLitho-compatible | ✅ |
| **Numerics** | NumPy, SciPy, PyTorch | No proprietary solvers needed | ✅ |
| **Mask-3D Solver (RCWA/Waveguide)** | **MUST BE DEVELOPED FROM SCRATCH** | ELitho has NO RCWA – only TMM+Fourier | ❌ Missing per review |
| **Multilayer Optics** | ELitho (MIT) OR OxiPhoton (Apache-2.0) | TMM for multilayer mirrors ✅ | ✅ ELitho's `multilayer.py` usable |
| **Fourier Optics (Aerial Image)** | ELitho (MIT) | Abbe/Hopkins method | ✅ Present in ELitho |
| **Optics Simulation** | TorchLitho 2.0 (Apache-2.0) | GPU-accelerated, M3D-simplified | ⚠️ No rigorous RCWA |
| **Resist Simulation** | TorchResist (Apache-2.0) | Differentiable resist | ✅ |
| **Mask Optimization** | OpenILT (MIT) | Inverse lithography – but for DUV, EUV port needed | ⚠️ |
| **GPU VRAM** | **16 GB (RTX 5060 Ti) is NOT sufficient for production RCWA** | Only 5×5µm demo possible | ❌ VRAM limit |
| **Web UI** | React/Vue | Modern, portable | Custom development |
| **Visualization** | Plotly, Matplotlib | Interactive aerial images | ✅ |

---

## Part 4: 🔬 Physical Data – Availability

### 4.1 Publicly Available Data (✅ Free – as of July 2026)

| Data | Source | Accuracy |
|------|--------|----------|
| Refractive indices Mo, Si, Ru, Ta, Sn @13.5nm | **CXRO/Henke database** | Research-grade |
| Atomic scattering factors f₁,f₂ (Z=1–92, 10–30000 eV) | **CXRO ASCII download** | Standard reference |
| Mo/Si multilayer reflectivity (40–60 pairs, TMM) | **ELitho/OxiPhoton code** | Simulation-grade |
| Sn-plasma parameters (Tₑ 25–35 eV, nₑ 10²¹) | **Published ARCNL/SPIE papers** | Research |
| Resist SE range (2–10 nm), quantum yield (1–4 e⁻/photon) | **Kozawa et al., Tagawa et al.** | Research literature |
| Aerial image calculation methods | **Hopkins (partial coherence), Abbe** | Standard textbook |

### 4.2 Self-Calculable / Fittable (⚙️)

| Data | Method |
|------|--------|
| Absorber etch profiles (sidewall angle, Ta/TaN) | Geometric modeling + literature values |
| Resist diffusion length | Fit to published CD data |
| Scanner aberrations | Arbitrary Zernike polynomials (freely definable) |
| Source pulse shape (temporal) | Literature values + fitting |

### 4.3 Not Public – Trade Secrets (❌ No Access)

| Data | Protected by | Significance |
|------|--------------|-------------|
| ASML scanner calibration (exact pupil shape) | ASML/NXE | *Not needed for simulation core* |
| Exact resist formulation (CAR/MOR) | Tokyo Ohka / JSR | *Generalized model instead* |
| ASML droplet generator nozzle design | ASML (Zygo) | *Not needed* – only output parameters |
| Source out-of-band spectrum | ASML/Cymer | Can be approximated from paper data |

### 4.4 Conclusion: Data Gap – CORRECTED (Review Findings)

```
Public:      65% ■■■■■■■□□□
Fittable:    20% ■■■■□□□□□□
Trade Secret: 15% ■■■□□□□□□□
```

**The Revised Assessment (from destructive review):**
- CXRO data is for **ideal layers** – real multilayers have interdiffusion, roughness, oxidation → 5–10% reflectivity error
- Resist parameters from Kozawa/Tagawa are for **prototype resists**, not current CAR/MOR → 20–30% CD deviation
- Sn-plasma spectrum (ARCNL) for ideal parameters → out-of-band radiation missing
- **Acceptable for education/research tool**
- **Too inaccurate for fab decisions** (CD budget, OPC rules) → calibration against real wafer data needed

---

## Part 5: 🆚 Competitive Matrix – CORRECTED

| Criterion | KLA PROLITH | Synopsys S-Litho | Panoramic HyperLith v7 | **OUR PRODUCT** |
|-----------|:-----------:|:-----------------:|:----------------------:|:---------------:|
| Price/seat | $50k–$500k | $30k–$80k | $10k–$200k | **$2k–$30k** |
| GPU-native | ❌ CPU | ❌ CPU | ✅ HSS (GPU) | ✅ **PyTorch-native** |
| API/REST | ❌ | ❌ | ⚠️ SOAPI | ✅ **REST + Python SDK** |
| Open source | ❌ | ❌ | ❌ | ✅ **Open Core** |
| SaaS/Cloud | ❌ | ❌ | ❌ | ✅ **Optional** |
| EU export | ❌ US | ❌ US | ❌ US | ✅ **EU-Hosting** |
| Rigorous mask solver | ✅ RCWA | ✅ RCWA+FEM | ✅ TRIG (Waveguide) | ❌ **MUST BE NEW** |
| SEM simulation | ❌ | ❌ | ✅ PanSEM | ❌ |
| Source-mask optimization | ⚠️ ProDATA | ✅ | ✅ PanSO | ❌ |
| OPC/ILT | ⚠️ | ✅ | ✅ FullChip | ⚠️ OpenILT (EUV port) |
| Expert resist DB | ✅ | ✅ | ✅ ARMI | ❌ TorchResist generic |
| Learning curve | 📈 Steep | 📈 Steep | 📈 Steep | 📉 **Flat (SDK+Notebooks)** |
| Education license | ❌ None | ❌ None | ❌ None | ✅ **€2,000 Academy** |
| China-legal | ❌ Embargo | ❌ Embargo | ❌ Embargo | ⚠️ **BAFA review needed** |

---

## Part 6: 💰 Business Model

### 6.1 Product Tiers

| Tier | Price/Year | Target Audience | Features |
|------|:----------:|-----------------|----------|
| **FREE** (Open Core) | **Free** | Community, hobbyist | Core Engine, CLI, Basic Python SDK |
| **ACADEMY** | **€2,000** | Universities | FREE + Web UI, Tutorials, 50 Seats |
| **LAB** | **€15,000** | Research labs | ACADEMY + GPU-Accel, TorchResist+OpenILT |
| **FAB** | **€50,000** | Small fabs, startups | LAB + OPC/ILT, CD Metrology, SEM Comparison |
| **ENTERPRISE** | **€150,000+** | Foundries, large fabs | FAB + On-Premise, Custom Models, SLA |
| **CLOUD** | **Pay-per-Use** | Startups, ad-hoc | Simulation-as-a-Service: ~€30/h GPU time |

### 6.2 Open Core vs. Commercial – CORRECTED (Review Critique)

**Problem identified in review:** OpenILT (MIT, 231 stars) and TorchResist (Apache-2.0) are already open source and contain the valuable features (OPC, resist simulation). If these are in the Open Core, why would anyone buy the Commercial version?

**AGPL-Copyleft risk:** Semiconductor fabs often have AGPL aversion. ASML/KLA tools use proprietary licenses.

**Revised demarcation:**

| Open Core (Apache-2.0 – NOT AGPL) | Commercial Only |
|-------------------------------------|-----------------|
| Core Engine (TMM+Fourier+GPU) | **Wafer data calibration** (CD adjustment) |
| CLI + Basic Python SDK | **Enterprise SDK** (Batch, Full-Chip) |
| Simple aerial image (1D, 10×10µm) | **Advanced RCWA/Waveguide Solver** (2D, Full-Chip) |
| Example notebooks | **Resist parameter library** (fitted to TOK/JSR) |
| OpenILT Basic (DUV) | **OpenILT EUV port + optimization** |
| TorchResist Basic | **SEM calibration + CD metrology** |
| Community support | **Support + Training + Custom Models** |
| | **Source-Mask Optimization (SMO)** |
| | **Etch Bias Model** |

The **real value creation** is not in the code, but in:
1. **Calibrated models** (fitted to real wafer data – only the product operator can do this)
2. **Support and service** (fabs pay for reliability)
3. **EUV-specific ports** (OpenILT is for DUV, EUV porting is complex)

---

## Part 7: 🗺️ Roadmap (3 Milestones) – CORRECTED

> **Review critique:** 3 months for POC was unrealistic (ELitho has no RCWA, missing GPU port, OpenILT EUV adaptation). Realistic: **6+ months for a real POC.**

### Legal Review (Months 0–2)
- [ ] **BAFA inquiry**: Does EUV sim software fall under EU Dual-Use 2021/821?
- [ ] **Freedom-to-Operate analysis**: Patent search at DPMA/USPTO (ASML, KLA, Panoramic)
- [ ] **Open-source license check**: LGPL-2.1 (LithographySimulator) properly integrated

### Scientific Prototype (Months 3–6)

- [ ] **Deploy ELitho core**: TMM multilayer + Fourier optics on Debian
- [ ] **TorchLitho 2.0 Integration** for GPU-accelerated M3D approximation
- [ ] **Begin RCWA/Waveguide Solver** in PyTorch/Rust as new development
- [ ] **Simple aerial image** (5×5µm, 1D mask, CPU)
- [ ] **REST API + Python SDK** foundation
- [ ] **Public GitHub release** (Open Core, Apache-2.0)

### Feature Complete (Months 7–12)

- [ ] **Sn-plasma source module** (literature-based)
- [ ] **2D RCWA for production mask sizes** (CPU cluster/cloud GPU)
- [ ] **Resist model** (TorchResist + SE cascade, calibration against paper data)
- [ ] **GDSII import + OPC Bridge** (OpenILT EUV port)
- [ ] **Source-Mask Optimization (SMO)** – see Missing Modules
- [ ] **Etch Bias Model**
- [ ] **Web UI** (job control, results)
- [ ] **Academy Tier launch** (€2,000/year)

### Commercial Release (Months 13–18)

- [ ] **Wafer data calibration pipeline** (CD adjustment)
- [ ] **SEM simulation comparison** (CD metrology)
- [ ] **Cloud/SaaS platform** (€30/h GPU time)
- [ ] **Closed beta** (3–5 institutes in China/Europe)
- [ ] **Product launch: LAB + FAB + ENTERPRISE tiers**

### Critical Paths (identified in review):
| Critical Path | Duration | Risk |
|---------------|:--------:|:----:|
| RCWA/Waveguide Solver | 6–8 months | High – no OSS basis |
| Export control review | 2–6 months | Medium – Blocks China distribution |
| OpenILT EUV port | 2–4 months | Medium |
| GPU VRAM optimization | 2–4 months | Medium – 16GB RTX 5060 insufficient |
| Wafer data calibration | 3–6 months | High – needs real measurement data |

---

## Part 8: ⚠️ Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|:------:|:-----------:|------------|
| Export control (EU Dual Use) | High | Medium | Obtain BAFA review early. Declare product clearly as "simulation without manufacturing reference" |
| IP infringement (Patent) | High | Low-Medium | Freedom-to-Operate analysis before launch. ASML/KLA patents mostly on hardware/calibration, not simulation |
| License conflicts (LGPL, etc.) | Medium | Low | Already reviewed: keep LGPL as submodule |
| China market collapses | Medium | Medium | Diversification: education, cloud, fabs |
| ASML/KLA releases free tool | Medium | Low | No incentive – would cannibalize existing customers |
| Open-source competition | Low | Low | Needs >2 years to become serious |
| Physics models inaccurate | Medium | Medium | Iterative calibration against published CD data from papers |

---

## Part 9: ✅ What Is Already Clear – CORRECTED

| Area | Status | Details |
|------|--------|---------|
| **Market niche** | ⚠️ Revised | $2–10M (instead of $10–30M), focus on research+SMEE+education |
| **Open-source components** | ✅ Reviewed | MIT, Apache-2.0, LGPL okay – but **no project is production-ready** |
| **Physical data** | ⚠️ ~65% public | Revised from 80%. Remaining 15% trade secrets |
| **Numerical methods** | ⚠️ Partial | TMM+Fourier available (ELitho), but **RCWA must be new** |
| **GPU stack** | ❌ Limit | RTX 5060 Ti (16GB) insufficient for production RCWA |
| **Interfaces** | ✅ Defined | REST, Python SDK, CLI, GDSII |
| **License model** | ⚠️ Adjusted | Apache-2.0 instead of AGPL. Value creation in calibration+support |
| **Export control** | 🔴 Unresolved | BAFA review mandatory before product development |
| **Patents** | ⚠️ Unresolved | Freedom-to-Operate analysis needed (ASML, KLA, Panoramic) |
| **Customer validation** | ❌ Not done | First China/Europe contacts missing |
| **Missing modules** | ❌ 9 identified | SMO, OPC, Etch-Bias, SEM, Full-Chip, Hot-Spot, PW, Pupil Optimization, Multilayer Defects |

## Part 10: 🔴 Missing Modules (Review-Identified)

| Missing Module | Importance | Rationale |
|:---------------|:----------:|-----------|
| **Source-Mask Optimization (SMO)** | 🔴 High | Standard workflow for EUV ≤7nm |
| **Optical Proximity Correction (OPC)** | 🔴 High | Without OPC useless for fabs – OpenILT is ILT, not classic OPC |
| **Etch Bias/Etch Simulation** | 🟡 Medium | 10–20% CD bias without etch model |
| **Exposure Pupil Optimization** | 🟡 Medium | Scanner aberration compensation |
| **Full-Chip Mode** | 🟡 Medium | EDA integration, defect detection, PV band |
| **CD-SEM Comparison/Metrology** | 🟡 Medium | Panoramic has PanSIA – we need one too |
| **Process Window + Bossung Plots** | 🟢 Medium | Industry-standard output format |
| **Hot-Spot Detection** | 🟢 Medium | Design-for-Manufacturing |
| **Multilayer Defect Simulation** | 🟢 Low | Niche feature |
| **Resist Parameter Library** | 🟡 Medium | Calibrated TOK/JSR parameters = €€€ |

## Part 11: 🔮 Next Concrete Steps (revised)

1. ❌ **Do NOT immediately start ELitho+TorchLitho integration** – first clarify export control
2. 🔴 **BAFA inquiry**: "Does EUV sim software fall under EU Dual-Use 2021/821?"
3. 🔴 **ELitho code audit**: What is in there (TMM+Fourier) – what is not (RCWA)
4. 🟡 **TorchLitho-2.0 code audit**: Does it offer sufficient M3D replacement?
5. 🟡 **Market validation**: Real conversations with 3–5 China institutes + Fraunhofer
6. 🟡 **Panoramic HyperLith v7**: Obtain trial license for feature comparison
7. 🟢 **CXRO material database** as static library

---

## Part 12: 📚 Appendix – All Sources

### Software
- [EUVlitho](https://github.com/takahashi-edalab/EUVlitho) – MIT
- [ELitho](https://github.com/takahashi-edalab/elitho) – MIT
- [LithographySimulator](https://github.com/quarterwave0/LithographySimulator) – LGPL-2.1
- [TorchLitho 2.0](https://github.com/OpenOPC/TorchLitho-2.0) – Apache-2.0
- [OpenILT](https://github.com/OpenOPC/OpenILT) – MIT
- [TorchResist](https://github.com/ShiningSord/TorchResist) – Apache-2.0
- [OxiPhoton](https://github.com/cool-japan/oxiphoton) – Apache-2.0
- [OpenLithoHub](https://openlithohub.com) – Benchmarks

### Physical Data
- [CXRO/Henke Database](https://henke.lbl.gov/optical_constants/) – Atomic scattering factors
- [ELitho config.py](https://github.com/takahashi-edalab/elitho) – EUV refractive indices embedded
- [IMD Software](https://cxro.lbl.gov/imd/) – Multilayer mirror design

### Market
- KLA Patterning Simulation Group (kla.com)
- Panoramic Technology Inc. (panoramictech.com)
- Synopsys → Keysight acquisition (2025)
- SEMI EDA Market Reports

### Scientific Papers
- H. Tanabe et al., SPIE 2025 – Rigorous EM sim + CNN for EUV
- Kozawa et al. – Resist stochastics (fundamentals)
- ARCNL Code Comparison Workshop – LPP Plasma

---

*Created by Hermes Agent on 2026-07-07. Sources: GitHub API, CXRO/Henke database, SPIE Digital Library, KLA/Panoramic product pages, SEMI market data, DuckDuckGo Lite, Startpage.*

**File:** `KnowledgeBase/2026-07-07-EUV-Lithography-Simulator-Strategy.md`