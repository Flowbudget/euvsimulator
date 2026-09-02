# REAL-DATA ARCHIVE REPORT
# Eingefrorene experimentelle EUV-Referenzdaten
# Datum: 2026-08-21
# Ort: references/euv_experimental/
# KEINE Simulator-Kalibrierung — nur Archivierung + Dokumentation.

## 1. Erfolgreich archivierte Quellen

| # | Quelle | Original archiviert | Volltext | Quantitative Daten |
|---|---|---|---|---|
| 1 | Kim et al. 2022, RSC Adv. (PMMA) | ✅ HTML (154 KB, PMC) | ✅ frei | 🔶 im HTML; Setup extrahiert |
| 2 | Develioglu et al. 2023, SPIE 12498 (PSI) | ✅ PDF (864 KB) | ✅ frei | 🔶 Tabellen 2-4 teilweise extrahiert |
| 3 | ScienceDirect S0167931712001700 (32/64 nm) | ✅ Abstract-HTML (1.2 MB) | ❌ Paywall | ❌ nur Abstract |
| 4 | Bhattarai 2017, UC Berkeley ETD | ✅ Wayback-HTML (77 KB) | ⚠️ PDF manuell | 🔶 im Dokument, offen |

## 2. Originaldateien + Prüfsummen (SHA-256)

- `source_01_pmma_euv/original/PMC8979033.html`
  `29a13921387677cf52535d0742fde58f92a9e5e1cb06a23ed3e7689e2aeb7eb8`
- `source_02_psi_resist_screening/original/Develioglu-2023-EUV_lithography_resist_screening.pdf`
  `3976cffd6ac7f1810a37e51400e31b5ef2cf52fb46f8d56f97dde1a130f47bb4`
- `source_03_32nm_64nm_pitch/original/sciencedirect_abstract.html`
  `2a9fb58b8669f911b86ea1d5b9720f7966adf6aed476bee540076e09ce61df8e`
- `source_04_uc_reference/original/escholarship_8q3089t2_wayback.html`
  `46414562b9428f5b3e94d2ef9e410af1f56d131b2ac5fa376d2e1cd6e633e59f`

## 3. Verfügbare quantitative Daten

### Quelle 1 — PMMA (RSC Advances 2022, DOI 10.1039/d1ra07291a)
- Setup: 160 nm PMMA, 13.5 nm, PLS-II Synchrotron
- Messgrößen: Sensitivity (Dosis bei halber Restfilmdicke), Contrast,
  linearer Absorptionskoeffizient, CD, LER
- 250-nm-Pitch-Interferenzlitho (L/S > 50 nm); DCT + Transmission
- CD-Vergleich mit Lumped-Parameter-Modell berichtet (gute Übereinstimmung)
- 🔶 Tabellenwerte: PMC-HTML enthält keine `<table>`-Elemente (Format);
  Zahlenwerte müssen aus Text/Figuren extrahiert werden
- 🔶 Figurenwerte: digitized_from_figure bei späterer Nutzung

### Quelle 2 — PSI Resist Screening (SPIE 2023, DOI 10.1117/12.2660859)
- Setup: SLS EUV-Interferenzlitho, 13.5 nm; H2-2022; 5 Vendor-Resists
  (CAR + MTR), Sub-5-nm-Kontext
- Table 2 Guidelines: 16–8 nm LS; CAR/non-CAR; 20–30 nm Dicke;
  DtS < 60 mJ/cm²; Roughness < 10 %; Z = CD³·LWR²·DtS
- Table 3 (HP 14 nm): DtS = 53.85 / 38.9 / 19.40 / (abgeschnitten) mJ/cm²
  (Vendor A-CAR / B-CAR / C-MTR / D-CAR); alle erfüllen DtS-Ziel;
  nur Vendor C-MTR erfüllt Z-Faktor; LWR_unb > 1.4 nm bei allen
- Table 4 (HP 13 nm): DtS = 51.25 / 41.2 / 24.3 / (abgeschnitten) mJ/cm²
- Fig. 6: LWR_unb vs. Dosis bei 14/13 nm HP; Iso-Z-Linien 0.46 / 0.32
- Auflösung: CAR bis 11 nm HP; MTR 13 nm HP; Rekord 6 nm HP
- 🔶 LWR-Spalten der Tabellen 3/4 im PDF (Layout fragmentiert) — manuell
  prüfen bei späterer Nutzung

### Quelle 3 — 32 nm / 64 nm Pitch (Microelectronic Engineering, ~2012)
- ❌ Quantitative Daten nicht frei zugänglich (Paywall)
- Abstract-HTML archiviert; Metadaten (Titel/Autoren/DOI) noch aus dem
  HTML zu extrahieren (steht aus)

### Quelle 4 — UC Berkeley Dissertation (2017)
- Titel identifiziert: LER + SE-Interaktionen in EUV-Photoresists
- 🔶 Quantitative Daten im Dokument, Extraktion ausstehend
  (PDF manuell von eScholarship laden)

## 4. Daten nur aus Figuren extrahierbar

- Quelle 1: Contrast-Curven, DCT-Kurven, LER-Werte in Figuren
- Quelle 2: Fig. 6 (LWR vs Dosis, 5 Vendors) — primär als Grafik
  verfügbar; Digitization mit Genauigkeitsangabe nötig

## 5. Eignung für spätere Vergleiche

| Vergleich | Beste Quelle | Begründung |
|---|---|---|
| Dose–CD | Q1 (PMMA), Q2 (DtS) | Q1: DCT/IL, Q2: DtS pro Vendor |
| Dose–LER | Q1 (LER), Q2 (Fig. 6) | Q2: LWR_unb vs Dose direkt |
| Dose–LWR | Q2 (Fig. 6 + Tabellen) | explizite LWR-Daten |
| 32-nm/64-nm-Geometrie | Q3 (falls Zugang) | direkte Geometrie-Entsprechung |
| SE-Kette/LER | Q4 (Dissertation) | inhaltliche Nähe zur SE-PSF |

## 6. Fehlende Parameter für reproduzierbaren Vergleich

- Q1: genaue Dosisbereiche (mJ/cm²) der DCT/IL; Entwickler-Prozess;
  SEM-Metrologie-Parameter; LER-Messlänge
- Q2: LWR-Messlänge (unbiased-Definition); SEM-Parameter; Entwicklung;
  Substrat-Details; vollständige Tabellen 3/4 (LWR/Z-Spalten)
- Q3: Volltext/Paywall — alle Parameter fehlen
- Q4: PDF-Download offen; Parameter nach Extraktion

## 7. Zugangsblockaden (dokumentiert)

- PMC-PDF-Endpunkt: blockt automatisierte Downloads (CAPTCHA) —
  HTML-Volltext vorhanden, PDF manuell nachladbar
- RSC-Publisher-PDF: blockt Automation (403/CAPTCHA)
- ScienceDirect-Volltext: Paywall (nur Abstract frei)
- eScholarship: CloudFront-403 für Automation; Wayback-Snapshot
  (2024-07-02) archiviert; PDF manuell nachladbar

## 8. Wissenschaftliche Trennung

- Alle Daten in `references/euv_experimental/` sind EXTERNE
  EXPERIMENTDATEN (eingefroren).
- Keine Vermischung mit Euvsimulator-Simulationsergebnissen.
- Vergleich erst nach Simulation unter nachgestellten Bedingungen
  (Simulation − Experiment). KEINE Kalibrierung vor dem ersten
  unabhängigen Vergleich.
- Keine Simulator-Parameter wurden geändert (Git-Status: nur
  STEP-5.1/5.2B-Arbeitsbaum-Änderungen + diese Archiv-Dateien).

## 9. Ausstehende Arbeiten (nicht Teil dieses Schritts)

1. PDFs Q1/Q4 manuell nachladen (User-Aktion oder späterer Versuch)
2. Metadaten Q3 aus Abstract-HTML vollständig extrahieren
3. Tabellen 3/4 Q2 (LWR/Z-Spalten) aus PDF manuell verifizieren
4. Figuren-Digitization (Q1 Contrast/LER, Q2 Fig. 6) mit
   Genauigkeitsdokumentation
5. Q4-Inhaltsanalyse (Titel/Autor/DOI verifizieren, Kapitel sichten)
