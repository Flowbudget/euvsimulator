# 🔬 EUV-Lithographie-Simulator – Komponenten & Ressourcen
**Stand: 07.07.2026** | **Recherche: Hermes Agent**

---

## 1. Überblick: Was ein EUV-Simulator abdecken muss

Ein vollständiger EUV-Lithographie-Simulator modelliert den gesamten Strahlengang von der Plasmaquelle bis zum entwickelten Resist:

```
Plasmaquelle (LPP, Sn-Droplet, 13.5nm)
    ↓
Beleuchtungsoptik (Kollektorspiegel, Homogenizer)
    ↓
Reflektive Maske (Mo/Si-Multilayer + Absorber-Strukturen)
    ↓
Projektionsoptik (4-fach anamorphotische Spiegel, NA 0.33/0.55)
    ↓
Aerial Image (Luftbild auf Wafer-Ebene)
    ↓
Photoresist (Exposition, sekundäre Elektronen, chem. Verstärkung)
    ↓
Entwicklung / Ätzen
```

---

## 2. 🔧 Open-Source-Software (GitHub)

### 2.1 Komplette EUV-Simulatoren

| Projekt | Stars | Sprache | Beschreibung |
|---------|:-----:|:-------:|-------------|
| [**EUVlitho**](https://github.com/takahashi-edalab/EUVlitho) | ★18 | C++/Python | Rigoroser EM-Simulator für EUV + CNN-Fitting für M3D-Parameter |
| [**ELitho**](https://github.com/takahashi-edalab/elitho) | ★2 | Python | Python-basierter High-NA EUV-Simulator (SPIE Publikation) |
| [**High-NA EUV Sim**](https://github.com/JiSeok1579/high-na-euv-sim) | ★0 | ? | 0.55 NA High-NA EUV, Quelle→Wafer mit M3D+Resist+SMO |
| [**LithographySimulator**](https://github.com/quarterwave0/LithographySimulator) | ★40 | Python | Abbe-Methode, partielle Kohärenz, GPU (PyTorch) |

### 2.2 Lithographie-Optik & Masken

| Projekt | Stars | Beschreibung |
|---------|:-----:|-------------|
| [**TorchLitho 2.0**](https://github.com/OpenOPC/TorchLitho-2.0) | ★46 | Differentiable Lithographie-Simulation, GPU, Full-Chip (ASICON'25) |
| [**OpenILT**](https://github.com/OpenOPC/OpenILT) | ★231 | Inverse Lithography Technology – Maskenoptimierung als inverses Problem |
| [**OpenLithoHub**](https://openlithohub.com) | – | Benchmarks, OPC/ILT-Metriken, Public Leaderboard |
| [**OxiPhoton**](https://github.com/cool-japan/oxiphoton) | ★10 | EM-Wellenausbreitung in Rust – inkl. Multilayer-Spiegel-Simulation |

### 2.3 Photoresist-Simulation

| Projekt | Stars | Beschreibung |
|---------|:-----:|-------------|
| [**TorchResist**](https://github.com/ShiningSord/TorchResist) | ★26 | Differentiable Resist-Simulation, PyTorch |
| **DragonResist-EUV-Foundry** | – | Production-Grade Resist-Framework (<3.5% Abweichung zu Wafer-Daten) – GitHub scheint evtl. privat |
| **TU Delft Resist-MC** | – | Monte-Carlo-Simulation der Wechselwirkung EUV↔Metal-Oxide-Resists |

### 2.4 Allgemeine Lithographie-Simulatoren

| Projekt | Stars | Beschreibung |
|---------|:-----:|-------------|
| [**Advanced Lithography Sim**](https://github.com/hamzanael2k/Advanced-Lithography-Simulation-Tool) | ★12 | General lithography simulator |
| **Optolithium** (Gitee) | – | Optische Lithographie (Lehrzwecke) |

---

## 3. 📐 Physikalische Module (was gebaut werden muss)

### 3.1 Plasmaquelle (LPP – Laser Produced Plasma)

```
┌─────────────────────────────────────────────────────────┐
│  Laser → Sn-Droplet → Plasma → 13.5 nm EUV Emission     │
└─────────────────────────────────────────────────────────┘
```

**Parameter:**
- Wellenlänge: **13.5 nm** (92 eV, in-band)
- Quelle: CO₂-Laser (10.6 µm) oder Nd:YAG auf Zinn-Mikrotröpfchen
- Pre-Pulse formt Droplet → Scheibe → Main-Pulse → Plasma
- Typische Leistung: ~250W in-band (ASML NXE:3600D)
- **Open Source:** Keine vollständige Plasma-Quell-Simulation gefunden
- **Forschung:** ARCNL (Amsterdam), Source Code Comparison Workshop (jährlich)
- **Selbstbau:** SPARTAN/FLYCHK atomic codes (NLTE-Plasma), RADCAL/POST für Strahlungstransport

### 3.2 Beleuchtungsoptik (Illuminator)

```
┌─────────────────────────────────────────────────────────┐
│  Kollektor (Ellipsoid-Multilayer) → Homogenizer → Maske  │
└─────────────────────────────────────────────────────────┘
```

- **Mo/Si Multilayer-Spiegel:** 40–60 Schichten, ~70% Reflektivität bei 13.5 nm
- Kollektor: Ellipsoid- oder Winston-Cone-Geometrie
- Homogenizer: Fly's-Eye-Array oder Facetten-Spiegel
- **Simulation:** Transfer-Matrix-Methode (TMM), OxiPhoton (Rust), IMD Software
- **OxiPhoton:** Hat `multilayer_mirror.rs` – guter Startpunkt

### 3.3 Reflektive Maske (Reticle)

```
┌─────────────────────────────────────────────────────────┐
│  Absorber (Ta/TaN/TaBN) → 40× Mo/Si ML → Substrat      │
└─────────────────────────────────────────────────────────┘
```

- **Mask 3D (M3D) Effekte:** Absorberkanten beugen EUV → kritisch für Imaging
- **EUVlitho/ELitho:** Rigorose EM-Simulation für M3D-Effekte
- **CNN-Fitting:** EUVlitho trainiert CNN aus rigorosen Simulationen → schnell
- OpenILT für Masken-Optimierung (OPC/ILT)

### 3.4 Projektionsoptik

```
┌─────────────────────────────────────────────────────────┐
│  6–8 anamorphotische Multilayer-Spiegel → 4× Reduction  │
└─────────────────────────────────────────────────────────┘
```

- **Low-NA:** NA 0.33 (aktuelle ASML NXE)
- **High-NA:** NA 0.55 (ASML EXE:5000 – Twinscan EXE)
- Anamorphotisch: Unterschiedliche Vergrößerung in X/Y (4×/8×)
- Wavefront-Aberrationen müssen < λ/50 sein
- **Simulation:** TorchLitho 2.0 (GPU), OxiPhoton

### 3.5 Aerial Image (Luftbild)

```
┌─────────────────────────────────────────────────────────┐
│  Partielle Kohärenz (σ) → Abbe-Methode → Intensität      │
└─────────────────────────────────────────────────────────┘
```

- **Abbe-Methode:** Summation über Beleuchtungs-Quellpunkte
- Partielle Kohärenz (σ 0.2–1.0)
- Beleuchtungsmodi: Konventionell, Annular, Quasar, Dipol
- **LithographySimulator:** Implementiert Abbe + diverse Modi
- **High-NA EUV Sim:** Vollständig von Quelle→Aerial Image

### 3.6 Photoresist

```
┌─────────────────────────────────────────────────────────┐
│  EUV Photon → Photoelektron → Sekundärelektronen-Kaskade │
│  → Säuregenerator → Chemische Verstärkung → Löslichkeit  │
└─────────────────────────────────────────────────────────┘
```

- EUV-Photonen (92 eV) erzeugen primäre Photoelektronen
- Sekundärelektronen-Kaskade (0–20 eV) – kürzere Reichweite als DUV
- Stochastische Effekte (Rauschen) dominant bei <10 nm Strukturen
- **TorchResist:** Open Source, differentiable Resist-Modellierung
- **TU Delft MC-Sim:** Monte-Carlo für Metal-Oxide Resists
- **Selbstbau:** Discrete Stochastic Model (DSM), gelöste Diffusionsgleichungen

### 3.7 Prozess-Simulation (Development + Etch)

```
┌─────────────────────────────────────────────────────────┐
│  Entwicklerlösung → Löslichkeitskontrast → Ätzprofil     │
└─────────────────────────────────────────────────────────┘
```

- Anisotropes/isotropes Ätzen
- Mack-Modell (Entwicklungskinetik)
- Kinetic Monte Carlo für raue Kanten (LER/LWR)

---

## 4. 🥇 Empfohlene Architektur (Bauplan)

Komponente | Empfohlener Ansatz | Open Source Basis
-----------|-------------------|------------------
**Plasmaquelle** | LPP Sn-Droplet, CO₂-Laser-Puls, 13.5 nm | FLYCHK/SPARTAN (Forschungscodes)
**Kollektor** | 40° Grazing-Incidence, ellipsoid | OxiPhoton TMM + eigene Geometrie
**Multilayer-Spiegel** | Mo/Si, 40–60 Paare, TMM-Simulation | OxiPhoton `multilayer_mirror.rs`
**Maske** | Ta-Absorber auf Mo/Si, M3D rigoros oder CNN | **EUVlitho** / **ELitho**
**Beleuchtung** | Kohärenz σ 0.2–0.8, Annular/Quasar | **LithographySimulator** (Abbe)
**Projektion** | 4× Reduction, NA 0.33–0.55, anamorphotisch | **TorchLitho 2.0** (GPU)
**Aerial Image** | Partial coherence, Abbe sum | **High-NA EUV Sim**
**Resist** | CAR oder MOR, SE-Kaskade, stochastisch | **TorchResist** + TU Delft MC
**Etch** | Anisotropic, Mack-Modell | Selbstbau (einfach)

---

## 5. 🧪 Alternative / Nischen-Quellen

| Quelle | Beschreibung |
|--------|-------------|
| **PROLITH** (KLA) | Kommerziell, Goldstandard – aber nicht Open Source |
| **S-Litho** (Synopsys) | Kommerziell, predictive lithography |
| **DragonResist** | Production-Grade Resist (<3.5%), GitHub unbekannt |
| **IMD Software** | Multilayer-Spiegel-Design (CXRO Berkeley) |
| **CXRO / Berkeley Lab** | Center for X-Ray Optics, Rechnungen + Datenbanken |
| **ARCNL** (Amsterdam) | Academic Research Center for Nanolithography – Public Codes |
| **SPIE Advanced Lithography** | Jährliche Konferenz, Open-Access-Proceedings |
| **arXiv cs.CE/cond-mat.mtrl-sci** | Neueste Preprints zu Litho-Simulation |

---

## 6. ✅ Gap-Analyse

### Was es Open Source gibt ✅
- [x] Rigorose EM-Simulation für Mask 3D (EUVlitho/ELitho)
- [x] GPU-beschleunigte Lithographie-Simulation (TorchLitho, LithographySimulator)
- [x] Inverse Lithography / Maskenoptimierung (OpenILT)
- [x] Resist-Simulation (TorchResist, TU Delft)
- [x] Multilayer-Optik-Simulation (OxiPhoton)
- [x] Benchmarks & Metriken (OpenLithoHub)

### Was fehlt / selbst gebaut werden muss ❌
- [ ] **Plasmaquellen-Simulation** (Sn-Droplet, LPP, 13.5nm Emission) – keine Open-Source-Bibliothek
- [ ] **Komplette anamorphotische Optik-Kette** (6–8 Spiegel) – teilweise in TorchLitho
- [ ] **Gekoppelter Source→Wafer Workflow** – einzelne Module müssen integriert werden
- [ ] **Experimentelle Validierung** – kein simulierter Output ohne Kalibrierung an echten Wafer-Daten
- [ ] **Thermisches Management** – Spiegel heizen auf durch EUV (kein Modell)
- [ ] **Kontamination** (Carbon-Cracking, Sn-Debris) – kein Modell
- [ ] **Stochastische Effekte** (shot noise, LER/LWR) – teilweise in TorchResist

---

## 7. 📚 Wissenschaftliche Basis (Paper)

| Paper | DOI / Link | Fokus |
|-------|-----------|-------|
| H. Tanabe et al. (SPIE 2025) | [10.1117/1.JMM.24.2.024201](https://www.spiedigitallibrary.org/journals/journal-of-micro-nanopatterning-materials-and-metrology/volume-24/issue-2/024201) | Rigoroser EM-Sim + CNN für EUV |
| Flow Physics of EUV Sources | [academic.oup.com/nsr](https://academic.oup.com/nsr/advance-article/doi/10.1093/nsr/nwag298) | Sn-Droplet-Strömungsphysik |
| Microdroplet-Tin Plasma Sources | [10.1088/2040-8986/ac5a7e](https://iopscience.iop.org/article/10.1088/2040-8986/ac5a7e) | Code-Comparison Workshop |
| Quantum Simulation for EUV | [arXiv:2602.20234](https://arxiv.org/html/2602.20234v1) | Quantenalgorithmen für Resist-Materialdesign |

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

# Portale
https://openlithohub.com
https://ar cnl.nl (ARCNL Amsterdam)
https://cxro.lbl.gov (Center for X-Ray Optics)
```

---

*Erstellt von Hermes Agent am 07.07.2026. Quellen: DuckDuckGo Lite, Startpage, GitHub API, SPIE Digital Library.*