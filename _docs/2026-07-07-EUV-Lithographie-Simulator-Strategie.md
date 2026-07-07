# 🏭 EUV-Lithographie-Simulator – Kommerzielle Strategie & Bauplan
**Stand: 07.07.2026** | **Erstellt von Hermes Agent** | **Klassifizierung: Strategisches Planungsdokument**

> **⚠️ REVIEW-WARNUNG (07.07.2026):** Dieses Dokument wurde AKTUALISIERT basierend auf einem destruktiven Review.
> **Korrigierte Fehler:** (1) ELitho hat KEIN RCWA (nur TMM+Fourier), (2) Exportkontrolle nicht pauschal lösbar, (3) VRAM für RCWA >>16GB, (4) Panoramic HyperLith v7 unterschätzt, (5) Datenlücke ~65/20/15% statt 80/15/5%
> **Vollständiger Review:** `./2026-07-07-EUV-Lithographie-Simulator-Strategie-DESTRUKTIVER-REVIEW.md`

---

## Executive Summary (KORRIGIERT)

> **Ein EUV-Lithographie-Simulator ist zu ~65% aus öffentlich zugänglichen Daten und Open-Source-Code realisierbar, weitere ~20% sind fitbar.** Die restlichen ~15% (exakte Resist-Chemie, Scanner-Kalibrierung, Multilayer-Interdiffusion) sind Trade Secrets. **ABER:** ELitho (unser als Kern identifiziertes Tool) hat KEIN RCWA – es implementiert nur TMM+Fourier-Optik. Der kritische Baustein (rigoroser Mask-3D-Solver) muss neu entwickelt werden. Die Marktnische (China/Export-restricted Markets) ist kleiner als initial angenommen (SMIC hat ASML-Zugang), aber Bildung + Forschung + SMEE bleiben echte Chancen. Der Export nach China ist rechtlich NICHT pauschal legal – EU-Dual-Use-Verordnung und Wassenaar müssen geprüft werden.

---

## Teil 1: 🎯 Die Nische

### 1.1 Primäre Nische – China / Export-restricted Markets (KORRIGIERT)

**Revidierte Analyse nach Review:** SMIC (die bekannteste chinesische Fab) HAT ASML-Scanner (NXE:3400C) und Zugang zu Brion Tachyon – erworben vor den Exportbeschränkungen 2023. Die primäre Nische ist daher **nicht** SMIC selbst, sondern:

| Gruppe | Beispiele | Größe |
|--------|-----------|-------|
| **Forschungsinstitute ohne Scanner** | IMECAS, PKU, CAS Institute | ~15 Institutionen |
| **SMEE (Scanner-Entwickler)** | Shanghai Micro Electronics Equipment | 1 Organisation |
| **Chinesische Universitäten** | Tsinghua, Fudan, UCAS | ~20 Unis |
| **Kleinere Fabs ohne ASML-EUV** | Forschung, nicht-produktion | ~5–10 |

**Size:** ~10–15 Organisationen mit echtem Bedarf, geschätzt: **$2–$10 Mio./Jahr** (revidiert von $10–30M).

**ABER – KRITISCHER VORBEHALT:** Der Export nach China ist **NICHT** pauschal legal. EU-Dual-Use-Verordnung 2021/821, Wassenaar-Abkommen Kategorie 3 (Elektronik) und die deutsche AWV können EUV-Simulationssoftware als genehmigungspflichtig einstufen – unabhängig von der Open-Source-Lizenz. BAFA-Prüfung VOR Produktentwicklung ist zwingend.

### 1.2 Sekundäre Nischen

| Nische | Kunden | USP | Zugänglichkeit |
|--------|--------|-----|----------------|
| **Bildungssektor** | 100+ Unis weltweit | "EUV Lite" für 2.000€/Jahr | Einfach, Brand-Building |
| **Chip-Startups** | ~200 Startups | Pay-per-Simulation (Cloud) | SaaS-Infrastruktur |
| **Kleine Fabs** | X-Fab, LFoundry | Site-License <50.000€ | Mittel |
| **Forschungslabore** | Fraunhofer, IHP, CEA | Open Core + Support | Open Source Basis |
| **Nicht-ASML-Fabs** | Canon, Nikon, SMEE | Scanner-unabhängig | Mittel |

### 1.3 Produkt-Positionierung

```
           HOCHPREISIG
               │
               │    KLA PROLITH ($50k–$500k)
               │    Synopsys S-Litho
    KOMPLEX ───┼─── EINFACH
               │    ★ UNSER PRODUCT ★
               │    (Open Core + Commercial)
               │    Panoramic ($10k–$200k)
               │
           NIEDRIGPREISIG
```

**Position:** Preisgünstige, moderne, Open-Source-basierte Alternative mit Fokus auf:
- **Moderne API** (REST, Python SDK, Jupyter Notebooks)
- **GPU-native Simulation** (TorchLitho/PyTorch-Backend)
- **Transparente Modelle** (keine Black Box)
- **SaaS/Pay-per-use** möglich
- **Deutsches Hosting** → EU-DSGVO-konform, Export-freundlich

---

## Teil 2: 🧩 Open-Source-Lizenz-Kompatibilität

Bevor eine Zeile Code geschrieben wird, muss klar sein: **Welche Open-Source-Komponenten können wir bedenkenlos in ein kommerzielles Produkt einbauen?**

### 2.1 Lizenz-Ampel

| Projekt | Lizenz | Kommerziell nutzbar? | Bedingungen |
|---------|--------|:--------------------:|-------------|
| **ELitho** | **MIT** | ✅ Ja | Keine Einschränkungen. Attribution reicht. |
| **EUVlitho** | **MIT** | ✅ Ja | Keine Einschränkungen. |
| **OpenILT** | **MIT** | ✅ Ja | Ideales Fundament für Maskenoptimierung. |
| **TorchLitho 2.0** | **Apache-2.0** | ✅ Ja | Patentklausel beachten. Änderungen dokumentieren. |
| **TorchResist** | **Apache-2.0** | ✅ Ja | Wie Apache üblich. |
| **OxiPhoton** | **Apache-2.0** | ✅ Ja | (API zeigte NOASSERTION, LICENSE-File ist Apache-2.0) |
| **LithographySimulator** | **LGPL-2.1** | ⚠️ Ja, mit Einschränkung | LGPL erlaubt kommerzielle Nutzung. **Nicht modifizieren** → dynamisch verlinken. Oder als Submodul separat halten. |
| **PyTorch** | **BSD-3** | ✅ Ja | Kommerziell, keine Einschränkungen. |
| **High-NA EUV Sim** | **KEINE** | ❌ Nein | Ohne Lizenz = All Rights Reserved. Dürfen wir nicht nutzen. |

### 2.2 Strategie: Wie mit Lizenzen umgehen

| Lizenz | Strategie |
|--------|-----------|
| **MIT** | Direkt einbauen, Copyright-Header erhalten |
| **Apache-2.0** | Direkt einbauen, NOTICE-Datei führen, Änderungen dokumentieren |
| **LGPL-2.1** | Als **separates Submodul** halten, dynamische Verlinkung. Core-Produkt bleibt proprietär. |
| **Keine Lizenz** | Komplett meiden. Nur als Inspirationsquelle nutzen. |

**Empfohlenes Lizenz-Modell für das eigene Produkt:**
- **Open Core:** AGPL-3.0 oder Apache-2.0 (für Community)
- **Commercial Features:** Proprietäre Lizenz (Plugins, Enterprise-Addons)
- **Vorbild:** GitLab, VS Code, n8n

---

## Teil 3: 🏗️ Produktarchitektur

### 3.1 System-Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                        WEB UI / DASHBOARD                        │
│           (React/Vue – Visual Workflow Editor, Ergebnisse)       │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API / WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                    PYTHON SDK / CLI                              │
│  (Jupyter-fähig, CI/CD-Integration, Batch-Processing)           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                    CORE ENGINE (Python/PyTorch)                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ OPTICS MODULE│  │ SOURCE MODULE│  │ RESIST MODULE    │      │
│  │ (MIT)        │  │ (Eigenbau)   │  │ (Apache-2.0)    │      │
│  │ - TMM (Multi)│  │ - Sn-Plasma  │  │ - SE-Kaskade MC │      │
│  │ - RCWA (Mask)│  │ - Spectrum   │  │ - CA Model      │      │
│  │ - Abbe/Fourier│ │ - Collector  │  │ - Stochastik    │      │
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
│  - Source Parameters       - SEM-Simulation                     │
│                             - Process Window (PW)               │
│                             - OPC/RET Models                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Schnittstellen (API/Interface Design)

| Schnittstelle | Protokoll | Zweck |
|---------------|-----------|-------|
| **REST API** | HTTPS/JSON | Cloud-/SaaS-Integration, CI/CD-Pipelines |
| **Python SDK** | `pip install euv-sim` | Scripting, Notebooks, Automatisierung |
| **CLI** | `euv-sim run --config config.yaml` | Batch-Processing in Fabs |
| **Jupyter Extension** | Widgets + Visuals | Interaktive Exploration |
| **GDSII/OASIS Import** | Datei | Layout-Integration (Standard) |
| **SEM Image Export** | PNG/TIFF + Header | Vergleich mit realen Wafer-Bildern |
| **OPC Bridge** | OpenILT-kompatibel | Inverse Lithography Integration |

### 3.3 Software-Stack (Empfehlung) – KORRIGIERT

| Layer | Technologie | Begründung | Status |
|-------|-------------|------------|--------|
| **Sprache** | Python (Core), Rust (Performance-Kritisch) | Python = ML/GPU-native, Rust für RCWA/Plasma | Neu zu schreiben |
| **GPU** | PyTorch (CUDA) | TorchLitho-kompatibel | ✅ |
| **Numerik** | NumPy, SciPy, PyTorch | Keine proprietären Solver nötig | ✅ |
| **Mask-3D-Solver (RCWA/Waveguide)** | **MUSS NEU ENTWICKELT WERDEN** | ELitho hat KEIN RCWA – nur TMM+Fourier | ❌ Fehlanzeige im Review |
| **Multilayer-Optik** | ELitho (MIT) ODER OxiPhoton (Apache-2.0) | TMM für Multilayer-Spiegel ✅ | ✅ ELitho's `multilayer.py` nutzbar |
| **Fourier-Optik (Aerial Image)** | ELitho (MIT) | Abbe/Hopkins Methode | ✅ In ELitho vorhanden |
| **Optik-Simulation** | TorchLitho 2.0 (Apache-2.0) | GPU-beschleunigt, M3D-vereinfacht | ⚠️ Kein rigoroses RCWA |
| **Resist-Simulation** | TorchResist (Apache-2.0) | Differentiable Resist | ✅ |
| **Maskenoptimierung** | OpenILT (MIT) | Inverse Lithography – aber für DUV, EUV-Port nötig | ⚠️ |
| **GPU-VRAM** | **16 GB (RTX 5060 Ti) reicht NICHT für produktive RCWA** | Nur 5×5µm Demo möglich | ❌ VRAM-Limit |
| **Web UI** | React/Vue | Modern, Portierbar | Eigenentwicklung |
| **Visualisierung** | Plotly, Matplotlib | Interaktive Aerial Images | ✅ |

---

## Teil 4: 🔬 Physikalische Daten – Verfügbarkeit

### 4.1 Öffentlich verfügbare Daten (✅ Kostenlos – Stand Juli 2026)

| Daten | Quelle | Genauigkeit |
|-------|--------|-------------|
| Brechungsindices Mo, Si, Ru, Ta, Sn @13.5nm | **CXRO/Henke-Datenbank** | Forschungssgenau |
| Atomare Streufaktoren f₁,f₂ (Z=1–92, 10–30000 eV) | **CXRO ASCII Download** | Standardreferenz |
| Mo/Si Multilayer-Reflektivität (40–60 Paare, TMM) | **ELitho/OxiPhoton Code** | Simulationsgenau |
| Sn-Plasma Parameter (Tₑ 25–35 eV, nₑ 10²¹) | **Veröffentlichte ARCNL/SPIE Paper** | Forschung |
| Resist SE-Reichweite (2–10 nm), Quantenausbeute (1–4 e⁻/Photon) | **Kozawa et al., Tagawa et al.** | Forschungsliteratur |
| Aerial-Image-Berechnungsmethoden | **Hopkins (partielle Kohärenz), Abbe** | Standard-Textbook |

### 4.2 Selbst berechenbar / fittbar (⚙️)

| Daten | Methode |
|-------|--------|
| Absorber-Etch-Profile (sidewall angle, Ta/TaN) | Geometrische Modellierung + Literaturwerte |
| Resist-Diffusionslänge | Fitten an veröffentlichten CD-Daten |
| Scanner-Aberrationen | Beliebige Zernike-Polynome (frei definierbar) |
| Source-Pulsform (temporal) | Literatur-Werte + Fitten |

### 4.3 Nicht öffentlich – Trade Secrets (❌ Kein Zugriff)

| Daten | Geschützt von | Bedeutung |
|-------|---------------|-----------|
| ASML Scanner-Kalibrierung (exakte Pupillenform) | ASML/NXE | *Nicht nötig für Simulations-Kern* |
| Exakte Resist-Rezeptur (CAR/MOR) | Tokyo Ohka / JSR | *Stattdessen generalisiertes Modell* |
| ASML Droplet-Generator-Düsendesign | ASML (Zygo) | *Nicht nötig* – nur Output-Parameter |
| Source-Out-of-Band-Spektrum | ASML/Cymer | Kann aus Paper-Daten approximiert werden |

### 4.4 Fazit: Datenlücke – KORRIGIERT (Review-Befund)

```
Öffentlich:   65% ■■■■■■■□□□
Fitbar:       20% ■■■■□□□□□□
Trade Secret: 15% ■■■□□□□□□□
```

**Die Revidierte Einschätzung (aus destruktivem Review):**
- CXRO-Daten sind für **ideale Schichten** – reale Multilayer haben Interdiffusion, Rauigkeit, Oxidation → 5–10% Reflektivitätsfehler
- Resist-Parameter aus Kozawa/Tagawa sind für **Prototyp-Resists**, nicht aktuelle CAR/MOR → 20–30% CD-Abweichung
- Sn-Plasma-Spektrum (ARCNL) für Idealparameter → Out-of-Band-Strahlung fehlt
- Für **Bildungs-/Forschungs-Tool** akzeptabel
- Für **Fab-Entscheidungen** (CD-Budget, OPC-Regeln) zu ungenau → Kalibrierung an realen Wafer-Daten nötig

---

## Teil 5: 🆚 Wettbewerbsmatrix – KORRIGIERT

| Kriterium | KLA PROLITH | Synopsys S-Litho | Panoramic HyperLith v7 | **UNSER PRODUKT** |
|-----------|:-----------:|:-----------------:|:----------------------:|:-----------------:|
| Preis/Seat | $50k–$500k | $30k–$80k | $10k–$200k | **$2k–$30k** |
| GPU-Nativ | ❌ CPU | ❌ CPU | ✅ HSS (GPU) | ✅ **PyTorch-native** |
| API/REST | ❌ | ❌ | ⚠️ SOAPI | ✅ **REST + Python SDK** |
| Open Source | ❌ | ❌ | ❌ | ✅ **Open Core** |
| SaaS/Cloud | ❌ | ❌ | ❌ | ✅ **Optional** |
| EU-Export | ❌ US | ❌ US | ❌ US | ✅ **EU-Hosting** |
| Rigoroser Mask-Solver | ✅ RCWA | ✅ RCWA+FEM | ✅ TRIG (Waveguide) | ❌ **MUSS NEU** |
| SEM-Simulation | ❌ | ❌ | ✅ PanSEM | ❌ |
| Source-Mask-Optimierung | ⚠️ ProDATA | ✅ | ✅ PanSO | ❌ |
| OPC/ILT | ⚠️ | ✅ | ✅ FullChip | ⚠️ OpenILT (EUV-Port) |
| Expert Resist DB | ✅ | ✅ | ✅ ARMI | ❌ TorchResist generisch |
| Lernkurve | 📈 Steil | 📈 Steil | 📈 Steil | 📉 **Flach (SDK+Notebooks)** |
| Bildungslizenz | ❌ Nichts | ❌ Nichts | ❌ Nichts | ✅ **2.000€ Akademie** |
| China-Legal | ❌ Embargo | ❌ Embargo | ❌ Embargo | ⚠️ **BAFA-Prüfung nötig** |

---

## Teil 6: 💰 Geschäftsmodell

### 6.1 Produkt-Tiers

| Tier | Preis/Jahr | Zielgruppe | Features |
|-----|:----------:|------------|----------|
| **PRE** (Open Core) | **Kostenlos** | Community, Hobby | Core Engine, CLI, Basic Python SDK |
| **AKADEMIE** | **2.000€** | Universitäten | PRE + Web UI, Tutorials, 50 Seats |
| **LAB** | **15.000€** | Forschungslabore | AKADEMIE + GPU-Accel, TorchResist+OpenILT |
| **FAB** | **50.000€** | Kleine Fabs, Startups | LAB + OPC/ILT, CD-Metrology, SEM-Vergleich |
| **ENTERPRISE** | **150.000€+** | Foundries, Großfabs | FAB + On-Premise, Custom Modelle, SLA |
| **CLOUD** | **Pay-per-Use** | Startups, Ad-hoc | Simulation-as-a-Service: ~30€/h GPU-Time |

### 6.2 Open Core vs. Commercial – KORRIGIERT (Review-Kritik)

**Problem identifiziert im Review:** OpenILT (MIT, 231 Stars) und TorchResist (Apache-2.0) sind bereits Open Source und enthalten die wertvollen Features (OPC, Resist-Simulation). Wenn diese im Open Core liegen, warum sollte jemand die Commercial Version kaufen?

**AGPL-Copyleft-Risiko:** Halbleiter-Fabs haben oft AGPL-Aversion. ASML/KLA-Tools nutzen proprietäre Lizenzen.

**Revidierte Abgrenzung:**

| Open Core (Apache-2.0 – NICHT AGPL) | Commercial Only |
|-------------------------------------|-----------------|
| Core Engine (TMM+Fourier+GPU) | **Wafer-Daten-Kalibrierung** (CD-Anpassung) |
| CLI + Basic Python SDK | **Enterprise SDK** (Batch, Full-Chip) |
| Einfache Aerial Image (1D, 10×10µm) | **Advanced RCWA/Waveguide-Solver** (2D, Full-Chip) |
| Beispiel-Notebooks | **Resist-Parameter-Bibliothek** (fittet an TOK/JSR) |
| OpenILT Basic (DUV) | **OpenILT EUV-Portierung + Optimierung** |
| TorchResist Basic | **SEM-Kalibrierung + CD-Metrologie** |
| Community-Support | **Support + Training + Custom Modelle** |
| | **Source-Mask-Optimization (SMO)** |
| | **Etch-Bias-Modell** |

Die **echte Wertschöpfung** liegt nicht im Code, sondern in:
1. **Kalibrierten Modellen** (an realen Wafer-Daten gefittet – das kann nur der Produktbetreiber)
2. **Support und Betreuung** (Fabs zahlen für Verlässlichkeit)
3. **EUV-spezifischen Portierungen** (OpenILT ist für DUV, EUV-Portierung ist aufwändig)

---

## Teil 7: 🗺️ Roadmap (3 Phasen) – KORRIGIERT

> **Review-Kritik:** 3 Monate für POC waren unrealistisch (ELitho hat kein RCWA, fehlende GPU-Portierung, OpenILT EUV-Anpassung). Realistisch: **6+ Monate für einen echten POC.**

### Phase 0: Rechtliche Klärung (Monate 0–2)
- [ ] **BAFA-Anfrage**: Fällt EUV-Sim-Software unter EU-Dual-Use 2021/821?
- [ ] **Freedom-to-Operate Analyse**: Patent-Recherche bei DPMA/USPTO (ASML, KLA, Panoramic)
- [ ] **Open-Source-Lizenz-Check**: LGPL-2.1 (LithographySimulator) richtig einbinden

### Phase 1: Scientific Prototype (Monate 3–6)

- [ ] **ELitho-Core ausrollen**: TMM-Multilayer + Fourier-Optik auf Debian
- [ ] **TorchLitho 2.0 Integration** für GPU-beschleunigte M3D-Näherung
- [ ] **RCWA/Waveguide-Solver** in PyTorch/Rust als Neuentwicklung beginnen
- [ ] **Einfache Aerial Image** (5×5µm, 1D-Maske, CPU)
- [ ] **REST API + Python SDK** Grundgerüst
- [ ] **Öffentlicher GitHub-Release** (Open Core, Apache-2.0)

### Phase 2: Feature Complete (Monate 7–12)

- [ ] **Sn-Plasma-Source-Modul** (Literatur-basiert)
- [ ] **2D-RCWA für produktive Maskengrößen** (CPU-Cluster/Cloud-GPU)
- [ ] **Resist-Modell** (TorchResist + SE-Kaskade, Kalibrierung an Paper-Daten)
- [ ] **GDSII-Import + OPC Bridge** (OpenILT EUV-Portierung)
- [ ] **Source-Mask-Optimization (SMO)** – siehe Fehlende Module
- [ ] **Etch-Bias-Modell**
- [ ] **Web UI** (Job-Steuerung, Ergebnisse)
- [ ] **Akademie-Tier Launch** (2.000€/Jahr)

### Phase 3: Commercial (Monate 13–18)

- [ ] **Wafer-Daten-Kalibrierungs-Pipeline** (CD-Anpassung)
- [ ] **SEM-Simulations-Vergleich** (CD-Metrologie)
- [ ] **Cloud/SaaS-Plattform** (30€/h GPU-Time)
- [ ] **Closed Beta** (3–5 Institute in China/Europa)
- [ ] **Produkt-Launch: LAB + FAB + ENTERPRISE-Tiers**

### Kritische Pfade (identifiziert im Review):
| Kritischer Pfad | Dauer | Risiko |
|-----------------|:-----:|:------:|
| RCWA/Waveguide-Solver | 6–8 Monate | Hoch – keine OSS-Basis |
| Exportkontroll-Prüfung | 2–6 Monate | Mittel – Blockiert China-Vertrieb |
| OpenILT EUV-Portierung | 2–4 Monate | Mittel |
| GPU-VRAM-Optimierung | 2–4 Monate | Mittel – 16GB RTX 5060 reicht nicht |
| Wafer-Daten-Kalibrierung | 3–6 Monate | Hoch – braucht echte Messdaten |

---

## Teil 8: ⚠️ Risiken & Mitigation

| Risiko | Impact | Eintrittswkt. | Mitigation |
|--------|:------:|:-------------:|-----------|
| Exportkontrolle (EU Dual Use) | Hoch | Mittel | Frühzeitig BAFA-Prüfung einholen. Produkt klar als "Simulation ohne Herstellungsbezug" deklarieren |
| IP-Verletzung (Patent) | Hoch | Niedrig-Mittel | Freedom-to-Operate-Analyse vor Launch. ASML/KLA-Patente sind meist auf Hardware/Kalibrierung, nicht Simulation |
| Lizenzkonflikte (LGPL, etc.) | Mittel | Niedrig | Bereits geprüft: LGPL als Submodul halten |
| China-Markt bricht weg | Mittel | Mittel | Diversifikation: Bildung, Cloud, Fabs |
| ASML/KLA Release kostenloses Tool | Mittel | Niedrig | Kein Anreiz – würde Bestandskunden kannibalisieren |
| Open-Source-Wettbewerb | Niedrig | Niedrig | Braucht >2 Jahre bis ernsthaft |
| Physik-Modelle ungenau | Mittel | Mittel | Iterative Kalibrierung an veröffentlichten CD-Daten aus Papern |

---

## Teil 9: ✅ Was ist jetzt schon klar – KORRIGIERT

| Bereich | Status | Details |
|---------|--------|---------|
| **Markt-Nische** | ⚠️ Revidiert | $2–10M (statt $10–30M), Fokus auf Forschung+SMEE+Bildung |
| **Open-Source-Komponenten** | ✅ Geprüft | MIT, Apache-2.0, LGPL in Ordnung – aber **kein Projekt produktionsreif** |
| **Physikalische Daten** | ⚠️ ~65% öffentlich | Revidiert von 80%. Fehlende 15% Trade Secrets |
| **Numerische Methoden** | ⚠️ Teilweise | TMM+Fourier vorhanden (ELitho), aber **RCWA muss neu** |
| **GPU-Stack** | ❌ Limit | RTX 5060 Ti (16GB) für produktive RCWA unzureichend |
| **Schnittstellen** | ✅ Definiert | REST, Python SDK, CLI, GDSII |
| **Lizenz-Modell** | ⚠️ Angepasst | Apache-2.0 statt AGPL. Wertschöpfung in Kalibrierung+Support |
| **Export-Kontrolle** | 🔴 Ungeklärt | BAFA-Prüfung zwingend vor Produktentwicklung |
| **Patente** | ⚠️ Ungeklärt | Freedom-to-Operate Analyse nötig (ASML, KLA, Panoramic) |
| **Kunden-Validierung** | ❌ Nicht gemacht | Erste China/Europa-Kontakte fehlen |
| **Fehlende Module** | ❌ 9 identifiziert | SMO, OPC, Etch-Bias, SEM, Full-Chip, Hot-Spot, PW, Pupillen-Optimierung, Multilayer-Defekte |

## Teil 10: 🔴 Fehlende Module (Review-Identifiziert)

| Fehlendes Modul | Wichtigkeit | Begründung |
|:---------------|:----------:|------------|
| **Source-Mask-Optimization (SMO)** | 🔴 Hoch | Standard-Workflow für EUV ≤7nm |
| **Optical Proximity Correction (OPC)** | 🔴 Hoch | Ohne OPC für Fabs nutzlos – OpenILT ist ILT, nicht klassisches OPC |
| **Etch-Bias/Etch-Simulation** | 🟡 Mittel | 10–20% CD-Bias ohne Etch-Modell |
| **Belichtungs-Pupillen-Optimierung** | 🟡 Mittel | Scanner-Aberrations-Kompensation |
| **Full-Chip-Modus** | 🟡 Mittel | EDA-Integration, Defect Detection, PV-Band |
| **CD-SEM-Vergleich/Metrologie** | 🟡 Mittel | Panoramic hat PanSIA – brauchen wir auch |
| **Process Window + Bossung-Plots** | 🟢 Mittel | Industrie-Standard-Ausgabeformat |
| **Hot-Spot-Detection** | 🟢 Mittel | Design-for-Manufacturing |
| **Multilayer-Defekt-Simulation** | 🟢 Niedrig | Nischen-Feature |
| **Resist-Parameter-Bibliothek** | 🟡 Mittel | Kalibrierte TOK/JSR-Parameter = €€€ |

## Teil 11: 🔮 Nächste konkrete Schritte (revidiert)

1. ❌ **NICHT sofort mit ELitho+TorchLitho-Integration beginnen** – erst Exportkontrolle klären
2. 🔴 **BAFA-Anfrage**: "Fällt EUV-Sim-Software unter EU-Dual-Use 2021/821?"
3. 🔴 **ELitho-Code-Audit**: Was ist drin (TMM+Fourier) – was nicht (RCWA)
4. 🟡 **TorchLitho-2.0-Code-Audit**: Bietet es ausreichenden M3D-Ersatz?
5. 🟡 **Markt-Validierung**: Echte Gespräche mit 3–5 China-Instituten + Fraunhofer
6. 🟡 **Panoramic HyperLith v7**: Test-Lizenz besorgen für Feature-Vergleich
7. 🟢 **CXRO-Materialdatenbank** als statische Library einbauen

---

## Teil 11: 📚 Anhang – Alle Quellen

### Software
- [EUVlitho](https://github.com/takahashi-edalab/EUVlitho) – MIT
- [ELitho](https://github.com/takahashi-edalab/elitho) – MIT
- [LithographySimulator](https://github.com/quarterwave0/LithographySimulator) – LGPL-2.1
- [TorchLitho 2.0](https://github.com/OpenOPC/TorchLitho-2.0) – Apache-2.0
- [OpenILT](https://github.com/OpenOPC/OpenILT) – MIT
- [TorchResist](https://github.com/ShiningSord/TorchResist) – Apache-2.0
- [OxiPhoton](https://github.com/cool-japan/oxiphoton) – Apache-2.0
- [OpenLithoHub](https://openlithohub.com) – Benchmarks

### Physikalische Daten
- [CXRO/Henke Datenbank](https://henke.lbl.gov/optical_constants/) – Atomare Streufaktoren
- [ELitho config.py](https://github.com/takahashi-edalab/elitho) – EUV-Brechungsindices embedded
- [IMD Software](https://cxro.lbl.gov/imd/) – Multilayer-Spiegel-Design

### Markt
- KLA Patterning Simulation Group (kla.com)
- Panoramic Technology Inc. (panoramictech.com)
- Synopsys → Keysight Übernahme (2025)
- SEMI EDA Market Reports

### Wissenschaftliche Paper
- H. Tanabe et al., SPIE 2025 – Rigoroser EM-Sim + CNN für EUV
- Kozawa et al. – Resist-Stochastik (Grundlagen)
- ARCNL Code Comparison Workshop – LPP-Plasma

---

*Erstellt von Hermes Agent am 07.07.2026. Quellen: GitHub API, CXRO/Henke-Datenbank, SPIE Digital Library, KLA/Panoramic Produktseiten, SEMI-Marktdaten, DuckDuckGo Lite, Startpage.*

**Datei:** `Wissensspeicher/2026-07-07-EUV-Lithographie-Simulator-Strategie.md`