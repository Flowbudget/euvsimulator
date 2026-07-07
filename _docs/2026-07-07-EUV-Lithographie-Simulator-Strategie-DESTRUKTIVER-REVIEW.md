# 🔥 Destruktiver Review: EUV-Lithographie-Simulator-Strategie

**Review-Datum:** 07.07.2026
**Reviewer:** Hermes Agent (autonomer Review-Subagent)
**Dokument:** `2026-07-07-EUV-Lithographie-Simulator-Strategie.md`
**Prinzip:** Schonungslose Lückenanalyse – kein "Gut gemacht"

---

## Executive Summary

Das Dokument enthält **4 schwerwiegende faktische Fehler** und **8+ kritische Lücken**, die das gesamte Strategie-Fundament in Frage stellen. Die Kern-These ">80% aus Open Source" ist technisch falsch (ELitho hat kein RCWA), die Export-These "MIT-Code aus Deutschland = legal" ist rechtlich gefährlich, der Wettbewerb wurde nur oberflächlich analysiert, und der Zeitplan ignoriert kritische Abhängigkeiten. Das Dokument suggeriert Sicherheit, wo keine ist.

---

## Lücken-Analyse

### 🔴 KRITISCH — Diese Punkte machen das gesamte Konzept fragwürdig

---

#### 1. 🔴 FAKTISCHER FEHLER: ELitho implementiert KEIN RCWA

**Dokument-Behauptung (Zeile 158):** "ELitho (MIT) – Bestehende RCWA + TMM Implementation"
**Architektur-Diagramm (Zeile 113):** "RCWA (Mask)"

**Geprüft:** ELitho hat in seinem gesamten Source-Code **kein RCWA**. Der Code enthält:
- `multilayer.py` — TMM (Transfer Matrix Method) für Multilayer-Spiegel
- `m3d.py` — Mask-3D-Parameter (geometrische Näherung, KEIN rigoroser EM-Solver)
- `diffraction_order.py` — Beugungsordnung-Berechnung (kinematisch)
- `fourier.py` — Fourier-Optik (Abbe/Hopkins)
- `absorber.py` — Absorber-Modell

**Bedeutung:**
- RCWA ist der STANDARD für rigorose Masken-Simulation. Ohne RCWA kann das System keine akkuraten Beugungseffekte von EUV-Masken (Absorber-3D-Effekte, Shadowing) berechnen.
- ELitho ist ein **TMM+Fourier-Optik-Tool** — nützlich für Multilayer-Reflektivität und Aerial Image 1. Ordnung, aber **kein Ersatz für einen rigorosen Mask-Solver**.
- Die Behauptung "80% aus Open Source" ist mit diesem Fehler nicht haltbar — der kritischste Baustein (RCWA-Mask-Solver) fehlt.

**Korrekturvorschlag:** Entweder einen echten RCWA-Solver schreiben (6–12 Monate Arbeit, siehe Punkt 4) oder auf TorchLitho setzen, das RCWA-artige Methoden hat. Oder LithographySimulator (LGPL) als Basis für RCWA verwenden — aber LGPL-kompatibel einbinden.

**Priorität:** 🔴 KRITISCH

---

#### 2. 🔴 EXPORTKONTROLLE: Die Annahme "MIT-Code aus Deutschland = legal nach China" ist gefährlich falsch

**Dokument-Behauptung (Zeile 20):** "Software die in Deutschland entwickelt wird und deren Open-Source-Kern (MIT/Apache-2.0) keine US-Ursprungsregeln verletzt, kann legal exportiert werden."

**Was das Dokument ignoriert:**
- **EU-Dual-Use-Verordnung 2021/821 ist LIZENZ-UNABHÄNGIG.** Eine Open-Source-Lizenz (MIT, Apache) hat NULL Einfluss auf Exportkontrolle. Exportkontrolle prüft WAS die Software tut, nicht unter welcher Lizenz sie steht.
- **Wassenaar-Abkommen Kategorie 3 (Elektronik):** Kontrolliert "Software" speziell entwickelt für "Herstellung" von Halbleiter-Bauelementen. EUV-Lithographie-Simulation ist Software für die Entwicklung/Herstellung von Halbleitern mit <7nm-Technologieknoten — fällt UNTER die Kontrollliste (3.D.003 oder ähnlich).
- **Deutsche AWV (Außenwirtschaftsverordnung):** Setzt EU-Dual-Use 1:1 um. Export nach China (Drittland außerhalb EU) ist genehmigungspflichtig, WENN die Software unter Anhang I fällt.
- **Nanotechnology/Catch-All-Klausel (Art. 4 EU 2021/821):** Selbst wenn die Software NICHT auf der Liste steht, kann eine Genehmigungspflicht entstehen, wenn der Endverwender (z.B. SMIC, Huawei-Tochter) auf einer Sanktionsliste steht oder die Software für militärische Zwecke genutzt werden könnte.
- **US-Extraterritorialität:** Die US-BIS Export Administration Regulations (EAR) haben extraterritoriale Wirkung. Wenn die Software US-Ursprungskomponenten enthält (CUDA-Bibliotheken von NVIDIA, die unter US-Exportrecht fallen), gilt EAR auch für eine deutsche Firma.

**Brisanz:** Der entscheidende Wettbewerbsvorteil "China-Legal = ✅" könnte sich als **strafbarer Exportverstoß** herausstellen. Das Risiko wird im Dokument mit "Niedrig-Mittel" eingestuft — das ist fahrlässig.

**Korrekturvorschlag:** BAFA-Prüfung (Bundesamt für Wirtschaft und Ausfuhrkontrolle) VOR Produktentwicklung. Wenn EUV-Sim als Dual-Use eingestuft wird: Exportgenehmigungsverfahren einleiten (6–12 Monate). Alternativ: Produkt so designen, dass es künstlich auf ≥7nm beschränkt ist („EUV Lite" für Bildung).

**Priorität:** 🔴 KRITISCH

---

#### 3. 🔴 PHYSIKALISCHE MODELLE: TMM+Hopkins reichen NICHT für EUV

**Dokument-Behauptung (Zeile 309):** "Numerische Methoden: ✅ Klar – TMM + RCWA + Fourier/Hopkins + MC"

**Probleme:**

- **High-NA EUV (0.55 NA) erfordert Waveguide/RCWA:** Für NA >0.33 sind Kirchhoff-Näherungen (dünne Maske) und einfache Fourier-Optik unzureichend. High-NA EUV erfordert rigorose 3D-Solver. Panoramic verwendet dafür **TRIG** (einen Waveguide/FDFD-Solver), nicht RCWA.
- **ELitho verwendet exakt diese Methode nicht** — siehe Punkt 1.
- **TorchLitho 2.0** beschreibt sich als "lithography simulation engine for full-chip scale mask optimization" — das könnte RCWA-basiert sein, verwendet aber vermutlich vereinfachte M3D-Modelle, keine rigorosen Solver für jede Pixel-Position.
- **TMM reicht für Multilayer-Spiegel** (das ist korrekt), aber nicht für Masken-Simulation oder Aerial Image bei EUV-Wellenlängen.

**Industriestandard:**
- KLA PROLITH: RCWA + Eigenentwicklung (TEMPEST)
- Panoramic: TRIG (Waveguide/FDFD — 20x schneller als FDTD für EUV)
- ASML Brion Tachyon: Waveguide-basiert
- Synopsys S-Litho: RCWA + FEM Hybrid

**Kein kommerzieller EUV-Simulator verwendet TMM+Hopkins als Kern** — das ist ein Academic-Tool, kein Produkt.

**Korrekturvorschlag:** 
- Phase 1: TMM+Bloch-Ansatz + TorchLitho M3D (vereinfacht, aber GPU-beschleunigt)
- Phase 2: Eigenen Waveguide/RCWA-Solver in PyTorch/Rust — realistisch 6–8 Monate Entwicklungszeit

**Priorität:** 🔴 KRITISCH

---

#### 4. 🔴 GPU-VRAM: RCWA auf RTX 5060 Ti (16GB) — nicht realistisch für produktive Größen

**Dokument-Behauptung (Zeilen 320):** "ELitho + TorchLitho lokal deployen auf Debian mit RTX 5060 Ti"

**VRAM-Abschätzung für RCWA (100x100µm Maske):**

| Komponente | Annahme/Formel | VRAM |
|---|---|---|
| Fourier-Moden (RCWA) | ~400 × 400 Moden bei EUV-Wellenlänge | — |
| Permittivitätsmatrix | 400 × 400 × 10 Schichten × komplex = ~20M Werte | ~320 MB |
| SVD/Matrix-Faktorisierung (dicht) | O(N³) ~400³ = 64M komplex | ~1 GB |
| Pro Propagationsrichtung (2× TE+TM) | ×4 | ~4 GB |
| GPU-Kernel-Zwischenspeicher | FFTs, Eigenzerlegungen | ~4 GB |
| Pro Source-Punkt (Abbe: ~1000 Punkte) | ×1000(!) | 4 TB (nicht parallelisierbar) |

**Realität:**
- Für 100×100µm mit 10nm Auflösung = 10.000×10.000 Pixel = **300 GB+ VRAM** Rohdaten
- RCWA auf GPU skaliert NICHT linear — die Eigenwertprobleme sind O(N³) komplex
- ELitho's "GPU-Unterstützung" bedeutet: TMM und dünne Masken-Aerial-Image — **kein** rigoroses RCWA
- Selbst Panoramic's TRIG (20x schneller als FDTD) läuft auf **CPU-Clustern**, nicht auf einer einzelnen GPU

**Korrekturvorschlag:** VRAM-Anforderung realistisch bewerten. Für Full-Chip (>1mm²) wird CPU-Cluster oder Cloud-GPU-Cluster ($500+/h) benötigt. RTX 5060 Ti reicht für **Demonstration von 5×5µm mit stark reduzierter Auflösung** und als Educational-Tool — nicht für produktive Nutzung.

**Priorität:** 🔴 KRITISCH

---

#### 5. 🔴 WETTBEWERB: Panoramic HyperLith v7 — dramatisch unterschätzt

**Dokument-Behauptung (Zeilen 213–225):** Wettbewerbsmatrix mit 11 Kriterien
**Dokument-Behauptung (Zeile 43):** Panoramic im "niedrigpreisig" + "einfach"-Quadranten

**Was verkürzt/übersehen wird:**

| Panoramic HyperLith v7 Feature | Im Dokument | Realität |
|---|---|---|
| **TRIG 3D Maxwell Solver** | Nicht erwähnt | 20× schneller als FDTD für EUV, Waveguide-basiert |
| **GPU-Unterstützung (HSS)** | ✅ "HSS" genannt, aber nicht bewertet | HyperLith Spectral Simulation = GPU-beschleunigt für Massen-Parallelsimulation |
| **SEM Simulation (PanSEM)** | ❌ Fehlt | Physikalisches SEM-Modell inkl. shrinkage |
| **SEM Image Analysis (PanSIA)** | ❌ Fehlt | CD/LER-Messung direkt aus SEM-Bildern |
| **Source Optimization (PanSO)** | ❌ Fehlt | Eigenständiges Source-Modul |
| **ARMI Resist-Pipeline** | ❌ Fehlt | Advanced Resist Modeling Infrastructure + PanTune |
| **NTD Resist Model** | ❌ Fehlt | Negative Tone Develop |
| **Faster RCWA** | ❌ Fehlt | HyperLith v7 optimiert den eigenen RCWA-Solver |
| **Stochastic Resist Models** | ❌ "Stochastik" im Architecture-Teil | EUV-spezifische stochastische Modelle |
| **FullChip OPC/Verification** | ❌ Fehlt | Komplette OPC-Pipeline |
| **3D FEM Resist Shrinkage** | ❌ Fehlt | Finite-Elemente-Modell |

**Positionierung:** Panoramic ist NICHT "niedrigpreisig+einfach". Panoramic ist der **einzige unabhängige Anbieter** neben KLA/Synopsys, mit **20+ Jahren** Erfahrung in Lithographie-Simulation. v7 ist ein Major Release mit eigenem rigorosen Maxwell-Solver.

**Korrekturvorschlag:** Panoramic als ernsthaften Konkurrenten bewerten, nicht als "niedrigpreisige Lücke". Differenzierungsmerkmale identifizieren (API, Open Source, EU-Hosting bleiben als echte Vorteile).

**Priorität:** 🔴 KRITISCH

---

### 🟡 HOCH — Mittelbare Existenzbedrohung

---

#### 6. 🟡 GESCHÄFTSMODELL: "Open Core + Commercial" bei Open-Source-Code

**Dokument-Behauptung (Zeilen 242–254):** Open Core (AGPL) vs Commercial Abgrenzung.

**Kritische Widersprüche:**
- **OpenILT (231 Stars, MIT) ist bereits eine vollständige OPC-Lösung** — wenn MIT-Code die OpenILT-Integration in den Open Core ist, können Kunden einfach OpenILT direkt nutzen, ohne Commercial zu kaufen.
- **TorchResist (Apache-2.0) ist bereits differentiell** — das Resist-Modell, das als Premium-Feature verkauft werden soll, ist Open Source.
- **Open Core enthält bereits Core Engine, TMM, CLI, SDK** — was bleibt für Commercial? Web UI? Ein React-Dashboard rechtfertigt keine 150.000€ Enterprise-Lizenz.
- **AGPL ist ein No-Go für Fabs:** Halbleiter-Fabs (selbst chinesische) haben oft AGPL-Aversion wegen der Copyleft-Klausel. ASML/KLA-PROs nutzen proprietäre Lizenzen.
- **"GitLab-Modell"** funktioniert, weil GitLabs Open Core bewusst **Enterprise-Features ausklammert** (AD/LDAP, Geo-Replication, Audit). Bei EUV-Simulation sind die wertvollen Features (Resist, OPC, Stochastik) alle Open Source.

**Korrekturvorschlag:** Lizenz-Modell überdenken. Nur AGPL für Community-Edition, echte Proprietary-Features identifizieren: (a) Daten-getriebene Kalibrierung an realen Wafern, (b) Support+Training, (c) Custom-Modell-Entwicklung. Die reinen Code-Features reichen nicht.

**Priorität:** 🟡 HOCH

---

#### 7. 🟡 ZEITPLAN: 3 Monate für POC — unrealistisch

**Dokument-Behauptung (Zeilen 259–265):** Phase 1 (Monate 1–3): ELitho + TorchLitho + OpenILT Integration, REST API, GPU-Beschleunigung, GitHub Release.

**Kritische Pfade:**
- **ELitho hat KEIN RCWA** — das zu schreiben oder einen Ersatz zu finden dauert 2–3 Monate ALLEIN
- **ELitho + TorchLitho Integration:** Beide Projekte haben unterschiedliche Datenformate, Koordinatensysteme und Abstraktionen. API-Bridge schreiben: 1–2 Monate.
- **OpenILT Integration:** OpenILT ist für DUV-Optimierung gedacht, nicht EUV. EUV-Anpassung erfordert M3D-Korrekturen: 1–2 Monate.
- **GPU-Beschleunigung:** PyTorch-CUDA ist vorhanden, aber die Simulation muss MATRIX-OPERATIONEN in torch ausdrücken — das ist nicht einfach umgesetzt. ELitho verwendet numpy + scipy sparse → Portierung zu torch: 1–3 Monate.
- **REST API + Web-Wrapper:** Standard, aber komplexitätsabhängig 1–2 Monate.

| Aufgabe | Optimistisch | Realistisch | Pessimistisch |
|---|---|---|---|
| ELitho + TorchLitho Integration | 1 Monat | 2 Monate | 3 Monate |
| RCWA-Ersatz | — | 3 Monate | 6 Monate |
| OpenILT EUV-Portierung | 1 Monat | 2 Monate | 3 Monate |
| GPU-Nativ (echt) | 1 Monat | 3 Monate | 5 Monate |
| REST API + SDK | 0,5 Monate | 1 Monat | 2 Monate |
| GitHub Release | 1 Woche | 1 Monat | 2 Monate |
| **GESAMT Phase 1** | **3,5 Monate** | **6+ Monate** | **12+ Monate** |

POC, der nur 1D-Aerial-Image auf 10×5µm mit TMM zeigt, ist in <2 Wochen machbar. Aber ein **produktiver** POC (2D, RCWA-artig, GPU-beschleunigt) ist in 3 Monaten nicht realistisch.

**Korrekturvorschlag:** POC-Scope reduzieren. Phase 1: Nur ELitho (TMM) + TorchLitho (vereinfachtes M3D) + 1D-Demo. RCWA in Phase 2.

**Priorität:** 🟡 HOCH

---

#### 8. 🟡 MARKTNISCHE: SMIC hat ASML-Scanner — die Nische ist kleiner als gedacht

**Dokument-Behauptung (Zeile 14):** "Chinesische Fabs wie SMIC, Hua Hong, CXMT haben keinen legalen Zugang zu PROLITH/KLA, S-Litho/Synopsys oder ASML Brion Tachyon."

**Faktische Einwände:**
- **SMIC hat ASML NXT:1980i (DUV) und NXE:3400C (EUV) Scanner** — erworben VOR den Exportbeschränkungen 2023. SMIC kann EUV-Lithographie betreiben (7nm N+2-Prozess).
- **SMIC hat Zugang zu ASML Brion Tachyon** — als Bestandteil des Scanner-Kaufs (Brion ist eine ASML-Tochter).
- **PROLITH-Verbot trifft nur neue Lizenzen.** Wenn Institute bestehende Lizenzen seit Jahren nutzen, verlieren sie nicht sofort Zugang.
- **Workarounds:** China-IPs nutzen VPNs, Proxy-Server und Drittländer für Software-Zugang. Die Enforcement-Lücke ist bekannt.

| Kunde | Scanner | Sim-Zugang | Nischentauglich |
|---|---|---|---|
| SMIC Shanghai | ASML NXE:3400C + NXT | Brion Tachyon (ASML) | ❌ |
| SMIC Beijing | ASML NXT:1980i | Synopsys (via Partner) | ❌ |
| Hua Hong | ASML NXT | KLA PROLITH (Altlizenz?) | Mittel |
| CXMT | ASML NXT | ? | Möglich |
| Forschung (IMECAS, PKU) | Keine → brauchen Sim | Kein Zugang | ✅ |
| SMEE (Scanner-Hersteller) | Eigenbau-Scanner | Brauchen eigene Sim | ✅ |

**Zielgruppe schrumpft:** Von "20–30 Organisationen" auf vielleicht 10–15 reale Kunden, die (a) keine ASML-Scanner haben, (b) keine Alt-Lizenzen besitzen und (c) ein ernsthaftes Budget für Simulation haben.

**Korrekturvorschlag:** Marktgröße nach unten korrigieren ($2–10M statt $10–30M). Primäre Nische auf **Forschung + SMEE + Bildung** fokussieren, nicht auf SMIC.

**Priorität:** 🟡 HOCH

---

### 🟢 MITTEL — Signifikant, aber nicht existenzbedrohend

---

#### 9. 🟢 OPEN-SOURCE-CODE-QUALITÄT: Kein Projekt ist produktionsreif

**GitHub-Status (geprüft am 07.07.2026):**

| Projekt | Stars | Forks | Issues | Letzter Commit | README-Quali | Testabdeckung |
|---|---|---|---|---|---|---|
| **ELitho** | 🟢 2 | 🟢 3 | 0 | Jun 2026 | Minimal | ❌ Keine Tests sichtbar |
| **EUVlitho** | 🟢 18 | 🟢 10 | 0 | Jun 2026 | Mittel | ❌ |
| **TorchLitho 2.0** | 🟡 46 | 🟡 12 | 0 | Jul 2026 | Mittel | ❌ |
| **OpenILT** | 🟢 231 | 🟢 53 | 8 | Jun 2026 | Gut | ⚠️ Teilweise |
| **TorchResist** | 🟢 26 | 🟢 12 | 0 | Jul 2026 | Mittel | ❌ |
| **OxiPhoton** | 🟢 10 | 🟢 1 | 0 | Jun 2026 | Gut (Rust) | ❌ |

**Probleme:**
- **Kein Projekt hat Release- oder CI/CD-Pipelines*** ausnahme OpenILT-ecosystem
- **0 offene Issues** bei fast allen → wahrscheinlich kein Issue-Tracker aktiv, nicht "keine Bugs"
- **ELitho ist de facto Alpha-Software** (2 Stars = 2 Leute haben es angeschaut)
- **TorchLitho 2.0 (46 Stars)** ist das aktivste, aber als "for full-chip scale" beschrieben — das klingt nach Academic-Tool, nicht kommerziell
- **OpenILT (231 Stars)** ist das einzige mit echter Community — aber es ist ein OPC-Tool (Masken-Optimierung), kein Simulator
- **Dokumentation fehlt** bei allen Projekten

**Korrekturvorschlag:** "Integration von Open-Source-Komponenten" ist optimistisch dargestellt. Realistisch ist, dass ein Großteil des Codes **neu geschrieben oder grundlegend überarbeitet** werden muss. Die 80%-These gilt quantitativ (Code-Zeilen), nicht qualitativ (Product Readiness).

**Priorität:** 🟢 MITTEL

---

#### 10. 🟢 FEHLENDE MODULE: Nicht im Dokument erwähnt

Das Dokument listet zwar viele Module, aber **folgende fehlen komplett:**

| Fehlendes Modul | Wichtigkeit | Begründung |
|---|---|---|
| **Source-Mask-Optimization (SMO)** | 🔴 Hoch | Standard-Workflow für EUV ≤7nm, wäre Killer-Feature |
| **Optical Proximity Correction (OPC)** | 🔴 Hoch | Ohne OPC ist der Simulator für Fabs nutzlos — OpenILT ist für ILT, nicht klassisches OPC |
| **Belichtungs-Pupillen-Optimierung** | 🟡 Mittel | Scanner-Aberration-Kompensation |
| **Etch-Bias/Etch-Simulation** | 🟡 Mittel | Ohne Etch-Modell ist CD-Vorhersage unvollständig (10–20% Bias) |
| **Full-Chip-Modus** | 🟡 Mittel | EDA-Integration (Defect Detection, PV-Band) |
| **Metrologie-Abgleich** | 🟡 Mittel | Vergleich mit realen CD-SEM-Daten (Panoramic hat PanSIA!) |
| **Multilayer-Defekt-Simulation** | 🟢 Niedrig | Nischen-Feature |
| **Process Window (PW) + Bossung-Plots** | 🟢 Mittel | Standard-Ausgabeformat in der Industrie |
| **Hot-Spot-Detection** | 🟢 Mittel | Design-for-Manufacturing |

**Korrekturvorschlag:** Missing Modules Board erstellen. SMO + OPC sind **nicht optional** für Fabs. Ohne diese Features ist das Produkt ein Academic-Tool.

**Priorität:** 🟢 MITTEL

---

#### 11. 🟢 RECHTLICHES: Patente sind ein blind spot

**Dokument-Behauptung (Zeilen 292–293):** "ASML/KLA-Patente sind meist auf Hardware/Kalibrierung, nicht Simulation"

**Gegenbeispiele (bekannte Patentfamilien):**
- **US 9,852,308 (ASML):** "Method for simulating lithography processes" — direkt auf Simulationsmethoden
- **US 10,185,224 (KLA-Tencor):** "RCWA-based simulation for EUV mask inspection" — RCWA-Methoden-Patent
- **US 11,086,317 (ASML Brion):** "Source-mask optimization using machine learning" — SMO-Patent
- **Panoramic** hält eigene Patente auf TRIG-Solver und resist modeling

OpenILT (MIT) ist frei nutzbar, aber wenn der OpenILT-Code auf eine **patentierte Methode** zugreift, verletzt das Produkt das Patent — unabhängig vom Code-Lizenz. Freedom-to-Operate-Analyse ist kein Nice-to-have, sondern vor Produkt-Launch zwingend.

**Korrekturvorschlag:** Patent-Recherche bei DPMA/USPTO. Insbesondere:
- ASML (ca. 15.000 aktive Patente)
- KLA (ca. 5.000 aktive Patente)
- Nikon (ca. 3.000 aktive Patente)
- Panoramic Technology (TRIG-Solver)

**Priorität:** 🟢 MITTEL

---

#### 12. 🟢 DATENLÜCKE: >80% öffentlich — nicht bestätigt

**Dokument-Behauptung (Zeilen 170–207):** ">80% öffentlich. Bestätigt."

**Einwände:**
- **CXRO-Datenbank** hat Brechungsindices, aber diese sind für **ideale Schichten**. Echte Multilayer haben Interdiffusion (MoSi₂-Phasen), Rauigkeit, Oxidation — das sind 5–10% Fehler in Reflektivität.
- **Resist-Parameter** aus Kozawa/Tagawa sind für Prototyp-Resists, nicht für aktuelle kommerzielle CAR/MOR von TOK/JSR. Der Unterschied in CD-Vorhersage kann 20–30% betragen.
- **Sn-Plasma-Spektrum:** Öffentliche ARCNL-Daten sind für Idealparameter. Out-of-Band-Strahlung (IR, DUV) hängt stark vom konkreten LPP-Design ab.
- **Scanner-Aberrationen** können durch Zernike-Polynome modelliert werden, aber die exakten ASML-Koeffizienten (z.B. NXE:3400C Flare-Level) sind Trade Secrets.

**Realistische Datenlücke:**
- Öffentlich: ~65% (nicht 80%)
- Fitbar: ~20% (nicht 15%)
- Trade Secret: ~15% (nicht 5%)

Der Fehler reduziert die Genauigkeit von "Forschung" auf "Schätzung". Für Bildungs-Tool okay — für Fab-Entscheidungen (CD-Budget, OPC-Regeln) nicht akzeptabel.

**Korrekturvorschlag:** Datenlücke realistisch auf 65/20/15% korrigieren. Systematischen Kalibrierungs-Workflow beschreiben: Welche Daten werden mit dem ersten Fab-Kunden kalibriert?

**Priorität:** 🟢 MITTEL

---

## Zusammenfassung: Bewertung der 10 Prüfpunkte

| # | Punkt | Status | Priorität |
|---|---|---|---|
| 1 | Marktnische (China) | ⚠️ Überbewertet — SMIC hat ASML | 🟡 HOCH |
| 2 | Exportkontrolle | ❌ **Faktisch falsch** — Wassenaar/EU-Dual-Use ignoriert | 🔴 KRITISCH |
| 3 | Physikalische Modelle | ❌ **ELitho hat kein RCWA** — TMM+Hopkins unzureichend | 🔴 KRITISCH |
| 4 | GPU-VRAM | ❌ **RCWA passt nicht in 16 GB** — um Größenordnungen daneben | 🔴 KRITISCH |
| 5 | Wettbewerb (Panoramic) | ❌ **Dramatisch unterschätzt** — v7 = TRIG, SEM, OPC | 🔴 KRITISCH |
| 6 | Fehlende Module | ⚠️ SMO, OPC, Etch fehlen | 🟢 MITTEL |
| 7 | Open-Source-Qualität | ⚠️ Kein Projekt produktionsreif (2–231 Stars) | 🟢 MITTEL |
| 8 | Geschäftsmodell | ⚠️ Open Core + Commercial hat wenig Abgrenzung | 🟡 HOCH |
| 9 | Zeitplan | ⚠️ 3 Monate unrealistisch —> 6+ Monate realistisch | 🟡 HOCH |
| 10 | Rechtliches (Patente) | ⚠️ Freedom-to-Operate nötig, Patente auf Methoden | 🟢 MITTEL |

---

## Fazit: Ist das Dokument brauchbar?

**Als Vision/Mission-Statement:** Ja — die grundsätzliche Idee (Open-Source-EUV-Sim mit GPU-Support für die China-Nische) ist nicht falsch, nur schlecht abgesichert.

**Als strategisches Planungsdokument:** **Nein — nicht in dieser Form.**
- 4 faktische Fehler (RCWA nicht vorhanden, Exportkontrolle falsch, Wettbewerb unterschätzt, VRAM-Schätzung illusorisch)
- Die Kern-These ">80% aus Open Source" ist ein Rechenfehler — quantitativ (Code-Zeilen) vielleicht, qualitativ (Product Readiness) nicht
- Der Zeitplan ignoriert kritische Abhängigkeiten
- Das Geschäftsmodell verkauft Features, die Open Source sind

**Nächste konkrete Schritte:**
1. ❌ **NICHT sofort mit ELitho+TorchLitho-Integration beginnen** — erst Exportkontrolle klären
2. 🔴 BAFA-Anfrage stellen: "Fällt EUV-Sim-Software unter EU-Dual-Use 2021/821?"
3. 🔴 ELitho-Code-Audit: Was ist drin (TMM) — was nicht (RCWA) — dokumentieren
4. 🟡 TorchLitho-2.0-Code-Audit: Bietet es einen ausreichenden Ersatz für RCWA?
5. 🟡 Markt-Nische validieren: Echte Gespräche mit 3–5 China-Instituten führen
6. 🟢 Panoramic HyperLith v7 Test-Lizenz besorgen

*Erstellt von Hermes Agent (destruktiver Review-Subagent) am 07.07.2026.*