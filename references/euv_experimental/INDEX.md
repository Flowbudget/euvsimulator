# INDEX — Experimentelle EUV-Referenzdaten (eingefroren)

Zweck dieser Sammlung: **Eingefrorene externe Referenz** für einen späteren
"REAL-DATA CHECK / EXPERIMENTAL VALIDATION". KEINE Kalibrierung, KEINE
Parameteränderung des Euvsimulators. Experimentelle Messwerte werden strikt
von Simulationsergebnissen getrennt.

Datum der Archivierung: 2026-08-21
Ort: `references/euv_experimental/`

---

## Quelle 1 — PMMA-EUV (RSC Advances 2022)

| Feld | Wert |
|---|---|
| Citation | Kim K. et al. (2022), RSC Advances |
| Titel | Investigation of correlative parameters to evaluate EUV lithographic performance of PMMA |
| DOI | 10.1039/d1ra07291a |
| URL | https://pmc.ncbi.nlm.nih.gov/articles/PMC8979033/ |
| Jahr | 2022 |
| Experimenttyp | EUV-Resist-Charakterisierung (PMMA), Dosis/CD/LER |
| EUV-Wellenlänge | 13.5 nm (zu verifizieren) |
| Resist | PMMA |
| Wafer/Substrat | zu extrahieren |
| Geometrie | zu extrahieren |
| Messgrößen | CD, LER, Sensitivity/Dose-to-Clear, Contrast (zu extrahieren) |
| Rohdaten | Volltext-HTML (PMC), Tabellen/Figuren im HTML |
| Vergleich mit Euvsimulator | Dose–CD / Dose–LER-Skalierung, Nicht-CAR-Resist |
| Archivstatus | ✅ HTML archiviert; PDF manuell nachladbar (PMC blockt Automation); Extraktion offen |

## Quelle 2 — PSI Resist Screening (2023)

| Feld | Wert |
|---|---|
| Citation | Develioglu A. (2023), PSI DORA |
| Titel | The EUV lithography resist screening (published version) |
| DOI | zu verifizieren |
| URL | https://www.dora.lib4ri.ch/psi/islandora/object/psi%3A53089 |
| Jahr | 2023 |
| Experimenttyp | EUV-Resist-Screening mit Wafer-Daten, CD/LWR über Dosen |
| EUV-Wellenlänge | 13.5 nm (zu verifizieren) |
| Resist | mehrere (zu extrahieren) |
| Wafer/Substrat | 300-mm-Wafer (zu verifizieren) |
| Geometrie | Pitch/Target-CD (zu extrahieren) |
| Messgrößen | CD, LWR, evtl. LER, Dosisbereiche |
| Rohdaten | PDF (864 KB) — Tabellen/Figuren im PDF |
| Vergleich mit Euvsimulator | Bevorzugt: CD(Dosis), LWR(Dosis), Auflösungsfenster |
| Archivstatus | ✅ PDF archiviert; Extraktion offen |

## Quelle 3 — 32 nm Line / 64 nm Pitch (Microelectronic Engineering, ~2012)

| Feld | Wert |
|---|---|
| Citation | ScienceDirect PII S0167931712001700 (Vollmetadaten zu verifizieren) |
| Titel | EUV-Lithographie auf 300-mm-Wafern, 32-nm-Linien bei 64-nm-Pitch (Abstract) |
| DOI | zu verifizieren (aus HTML) |
| URL | https://www.sciencedirect.com/science/article/pii/S0167931712001700 |
| Jahr | 2012 (mutmaßlich, zu verifizieren) |
| Experimenttyp | EUV-Patterning auf 300-mm-Wafern |
| EUV-Wellenlänge | 13.5 nm |
| Resist | zu extrahieren (Abstract) |
| Wafer/Substrat | 300 mm |
| Geometrie | 32 nm Line / 64 nm Pitch |
| Messgrößen | CD, LER/LWR (nur falls im Abstract/verfügbaren Teilen) |
| Rohdaten | Abstract-HTML (1.2 MB); Volltext hinter Paywall |
| Vergleich mit Euvsimulator | Geometrie-Entsprechung zur Default-Konfiguration (period 64, line 32) |
| Archivstatus | ✅ Abstract-HTML archiviert; Volltext nicht frei zugänglich |

## Quelle 4 — UC Berkeley Dissertation (2017)

| Feld | Wert |
|---|---|
| Citation | Bhattarai S. (2017), UC Berkeley ETD |
| Titel | Study of Line Edge Roughness and Interactions of Secondary Electrons in Photoresists for EUV Lithography |
| DOI | zu verifizieren |
| URL | https://escholarship.org/uc/item/8q3089t2 |
| Jahr | 2017 |
| Experimenttyp | Dissertation: LER + Sekundärelektronen-Wechselwirkungen in EUV-Resists |
| EUV-Wellenlänge | 13.5 nm (zu verifizieren) |
| Resist | mehrere (zu extrahieren) |
| Wafer/Substrat | zu extrahieren |
| Geometrie | zu extrahieren |
| Messgrößen | LER, SE-Interaktionen (zu extrahieren) |
| Rohdaten | Wayback-HTML (77 KB); PDF manuell nachladbar (escholarship blockt Automation) |
| Vergleich mit Euvsimulator | LER + SE-Kette — direkte inhaltliche Nähe zur stochastischen SE-PSF |
| Archivstatus | ✅ Wayback-HTML archiviert (Metadaten); PDF offen |

---

## Gesamtstatus

| Quelle | Original | Quantitative Daten | Volltext |
|---|---|---|---|
| 1 PMMA | ✅ HTML | 🔶 im HTML | ✅ frei |
| 2 PSI | ✅ PDF | 🔶 im PDF | ✅ frei |
| 3 32/64 nm | ✅ Abstract-HTML | ❌ Paywall | ⚠️ nur Abstract |
| 4 UC | ✅ Wayback-HTML | 🔶 im Dokument | ⚠️ PDF manuell |

Legende: ✅ vorhanden · 🔶 vorhanden, Extraktion ausstehend · ❌ nicht verfügbar

## Wissenschaftliche Trennung

- Alle Daten in diesem Ordner sind EXTERNE EXPERIMENTDATEN.
- Sie werden NICHT mit Euvsimulator-Simulationsergebnissen vermischt.
- Vergleich erst nach Abschluss der Simulation unter nachgestellten
  experimentellen Bedingungen (Simulation − Experiment).
- KEINE Kalibrierung vor dem ersten unabhängigen Vergleich.

**Hinweis (2026-09-06, Lizenzprüfung):** Volltext- und Kontext-Extrakte aus den zitierten Artikeln (`fulltext.txt`,
`number_lines.txt`, `keyword_context.txt`) sind nicht Teil des Repositories — das wären Kopien geschützter Texte. Im Repo bleiben nur
die extrahierten Zahlenwerte mit Quellenangabe (`*.ini`, `metadata.json`); der Wortlaut ist beim jeweiligen Verlag bzw. bei PMC.
