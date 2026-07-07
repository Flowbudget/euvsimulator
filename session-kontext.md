# OpEnUV – Projektkontext (Session 07.07.2026)

## Projektname
- **Öffentlich:** OpEnUV (OpEn + EUV = Open Source Extreme UV)
- **Intern/Code:** `euv`

## Lizenz & Philosophie
- **Apache-2.0** (Open Source)
- Open Core + Commercial Plugins (Support, Kalibrierung, Training)
- Spenden via GitHub Sponsors / Open Collective
- **Open Source ≠ umsonst:** Blutiger Kernel frei, Support + Kalibrierung kosten Geld

## Ziel
Open-Source-EUV-Lithographie-Simulator vom Sn-Plasma bis zur CD-Metrologie.
Primär: Bildung, Forschung, Chip-Startups, SMEE (China – sofern Export erlaubt).
Sekundär: Kleine Fabs ohne KLA/ASML-Budget.

## Nische (revidiert nach destruktivem Review)
- SMIC hat ASML-Scanner + Brion Tachyon → nicht unsere Kunden
- Echte Nische: **Forschung + SMEE + Bildung** → $2–10M adressierbar
- **Exportkontrolle nicht pauschal lösbar:** BAFA-Prüfung vor China-Vertrieb zwingend
- **Open Source privilegiert:** EU-Dual-Use hat Ausnahmen für Forschung/Bildung

## Technischer Stack
- **Sprache:** Python (Core) + Rust (Performance – RCWA-Solver via PyO3)
- **GPU:** PyTorch CUDA
- **Limit:** RTX 5060 Ti (16 GB VRAM) – kein produktives Full-Chip-RCWA
- **Lösung:** Hybrid-Ansatz: Rust für rigorose RCWA offline → CNN-Surrogat für Runtime
- **Zielplattform:** Debian 12/13

## Open-Source-Basis (Lizenzen geprüft ✅)
| Projekt | Lizenz | Nutzung |
|---------|--------|---------|
| ELitho | MIT | `multilayer.py` (TMM) direkt übernehmen |
| TorchResist | Apache-2.0 | Resist-Simulation |
| OpenILT | MIT | Maskenoptimierung (benötigt EUV-Port) |
| TorchLitho 2.0 | Apache-2.0 | GPU-Acceleration |
| OxiPhoton | Apache-2.0 | Inspiration Rust-TMM |
| gdstk | BSD-3 | GDSII I/O |
| KLayout | GPL-3.0 | GDS-Viewer (optionales Tool) |
| LithographySimulator | LGPL-2.1 | Als Submodul separat halten |

**Wichtigste Erkenntnis:** ELitho hat KEIN RCWA – nur TMM+Fourier. Der Mask-3D-Solver muss neu entwickelt werden (6-8 Monate).

## Korrigierte Annahmen (aus destruktivem Review)
1. ❌ ELitho hat RCWA → ✅ **Nein, nur TMM+Fourier. Neuentwicklung nötig.**
2. ❌ MIT-Code aus DE → legal nach China → ✅ **EU-Dual-Use/Wassenaar prüfen. Nicht pauschal legal.**
3. ❌ 16 GB VRAM reichen → ✅ **Faktor 1000 daneben. Nur 5×5µm Demo.**
4. ❌ Panoramic ist Nischenplayer → ✅ **HyperLith v7 hat TRIG, PanSEM, PanSO, ARMI.**
5. ❌ Daten 80% öffentlich → ✅ **Eher 65% öffentlich, 20% fitbar, 15% Trade Secrets.**

## Entwicklungsplan (Opus 4.8)
- **Gesamtdauer:** ~21 Sprints (12 Monate) bis Fab-Ready
- **Erster E2E-Durchlauf:** Sprint 6 (Woche 12)
- **Erster OSS Release:** Sprint 10 (Woche 20) – REST API + CLI
- **Erstes Geld:** Sprint 19+ – Akademie-Tier (2.000€/Jahr)

## Bauplan Phase 1 (Monate 0–6)
```
Sprint 1 (W1-2):  Repo, CI, Material-DB, CXRO-Import
Sprint 2 (W3-4):  TMM Multilayer (ELitho)
Sprint 3 (W5-6):  RCWA 1D PyTorch (kritisch!)
Sprint 4 (W7-8):  GDSII I/O + Dummymasken
Sprint 5 (W9-10): Aerial Image (Abbe) + Pupille
Sprint 6 (W11-12): ERSTER E2E-DURCHLAUF 🎉
Sprint 7 (W13-14): Plasmaquelle + Dosis
Sprint 8 (W15-16): Resist (TorchResist)
Sprint 9 (W17-18): Resist stochastisch + LER
Sprint 10 (W19-20): REST API + OSS RELEASE 🚀
Sprint 11 (W21-22): Rust RCWA (rigoros)
Sprint 12 (W23-24): RCWA 2D
```

## Wichtige Entscheidungen (Session 07.07.2026)
1. ✅ **Nicht sofort mit ELitho-Integration beginnen** – erst BAFA prüfen
2. ✅ **RCWA/Waveguide = Hybrid Rust + PyTorch CNN Surrogat**
3. ✅ **Open Source, Apache-2.0** (nicht AGPL)
4. ✅ **GitHub Sponsors + Open Collective für Spenden**
5. ✅ **CLI-Name: `euv`**
6. ✅ **Fallback: Opus 4.8 wenn DeepSeek hängt** – aber nicht als Dauerlösung (10× teurer)

## Ausstehende Punkte
- [ ] BAFA-Anfrage: Fällt EUV-Sim unter EU-Dual-Use?
- [ ] Freedom-to-Operate Patentanalyse (ASML, KLA, Panoramic)
- [ ] GitHub Repository anlegen
- [ ] Erste Kontakte zu China-Instituten + Fraunhofer
- [ ] Panoramic Test-Lizenz besorgen

## Dateien in diesem Projekt
| Datei | Beschreibung |
|-------|-------------|
| `README.md` | Projekt-Übersicht |
| `2026-07-07-EUV-Projektplan-OPUS.md` | Detaillierter Sprint-Plan (Opus 4.8) |
| `_docs/strategie.md` | Marktanalyse + Architektur |
| `_docs/strategie-review.md` | Destruktiver Review (Korrekturen) |
| `_docs/recherche.md` | Technische Recherche (Komponenten) |
| `session-kontext.md` | **Diese Datei** – vollständiger Session-Kontext |

---

*Erstellt: 07.07.2026 | Session: Hermes Agent | Modelle: DeepSeek V4 Flash, Claude Opus 4.8*