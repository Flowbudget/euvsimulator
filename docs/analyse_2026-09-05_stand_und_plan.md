# euvsimulator — Umfassende Analyse des Stands und neuer Plan (2026-09-05, abends)

Grundlage: 169 Commits, 887 Tests (lokal grün, Exit 0), Arbeitslog Fortsetzungen 10–23, Literaturkatalog Runde 10
(≈ 130 Dokumente). Alle Zahlen in diesem Dokument stammen aus Messungen dieser Session oder aus zitierten Primärquellen;
Ablesungen aus Figuren sind als solche markiert.

## 1. Was die Kette heute ist — Modul für Modul

| Stufe | Modell | Herkunft der Parameter | Prüfstatus |
|---|---|---|---|
| Materialkonstanten | CXRO f₁/f₂ (Henke) | Datenbank im Repo | gegen CXRO-Referenzwerte (Mo, Si) geprüft |
| Multilayer | S-Matrix-TMM, Névot-Croce | — | R = 64,7 % ideal (CXRO-Rechnung) |
| Maske | RCWA 1D (Redheffer, Li-TM), 2D | — | Erhaltungssätze R+T = 1 (2e-6), Fresnel-/Effektivmedium-Grenzfall, Slab = TMM |
| Aerial | Hopkins/Abbe, TCC numerisch, clear-field-normiert | NA 0,33, σ 0,8 | y-Invarianz, Dosis-Konvention getestet; pupil.py/source.py **nicht verdrahtet** |
| Belichtung | Dill A/B/C, absorbierte Photonen | B **berechnet** aus Zusammensetzung (4,44 µm⁻¹); C 0,090 (Yamamoto Table 2 = Sekiguchi MET 0,086/0,090) | B: erste Prinzipien + drei Messungen; C: nur Quellenvergleich |
| PEB | Diffusion (Gauß, isotrop, ADI-Flussform), Neutralisation 2. Ordnung, Deprotektion mit Lebensdauer | k 1,4 s⁻¹, τ 10,5 s (Yamamoto Fig. 3/4, Ablesung), D 4,2 nm²/s (Kang 2010, 90 °C) | Fig.-3-Kurve ≤ 0,08; **unabhängig** Fig. 5 0,75 vs 0,8; Neutralisationsform gegen Sekiguchi (2 von 3 Zeilen ≤ 5 %) |
| Entwicklung | Eikonal-Front (Fast Sweeping), Mack R(M), Sub-Pixel-Kante | R_max 68,6, R_min 0,1, M_th 0,39, n 18,2 (Yamamoto Table 2) | exakte Lösungen, Gitterinvarianz; Mack-Werte im Rahmen von MET-1K/2D (n 12,7/19, M_th 0,52/0,62) |
| Stochastik | Poisson auf absorbierte Photonen, Binomial-PAG, Kachelung mit Halo, Large-N-LER-Schätzer | ρ_PAG 0,2 (Mack 2011) | Großzahl-Grenzwert, ρ^(−1/2), Kachel-Invarianz; Vesters-Plausibilität 1,2–1,7× |
| Kalibrierung | Nelder-Mead über FEM, `euv calibrate` | — | synthetische FEM exakt zurückgefunden |

## 2. Was in dieser Session entschieden wurde — und warum es keine Kalibrierung war

1. Dill B 1,06 → 4,44 µm⁻¹: aus CXRO-Streufaktoren berechnet; 1,06 ist für ein PHS-Polymer physikalisch unmöglich
   (unter sauerstofffreiem Polystyrol). Drei Messungen bestätigen den Bereich.
2. Deprotektionsrate 0,072 → 1,4 s⁻¹ und Säurelebensdauer 10,5 s: aus Yamamotos eigener FT-IR-Kinetik; die davon
   unabhängige Auflösungsschwelle (Fig. 5) wird ohne Anpassung auf 7 % getroffen. PROLITHs Table-2-Paar verfehlte sie um 3,4×.
3. Diffusivität 3,3 → 4,2 nm²/s: Messwert (Kang 2010) statt Rückrechnung; der Default-Blur 9,4 nm liegt im gemessenen
   Band 7,5–12 nm benannter EUV-CARs.
4. Nichts wurde an ein LWR-Ziel angepasst. Jede Änderung hatte vorab formulierte Vorhersagen; verfehlte Vorhersagen
   (V3 Dill-B-Preflight, V2 Vesters, V2 Blur bei P = 64) sind im Log festgehalten.

## 3. Befunde dieser Analyse, die noch nicht im Log stehen

### 3.1 Säureausbeute pro absorbiertem Photon ist wahrscheinlich 2–3× zu hoch
Aus den Defaults folgt im Kleindosis-Grenzfall dH/dE = C·G₀ = 0,0900·0,2 = 0,018 Säuren/nm³ pro mJ/cm²; absorbiert werden
0,68 Photonen/nm² · 4,44·10⁻³ nm⁻¹ = 0,0030 Photonen/nm³ pro mJ/cm² → **6,0 Säuren pro absorbiertem Photon** (4,5 mit
Yamamotos 3,1 mol % ≙ 0,15 nm⁻³). Gemessen: LBNL Film-Quantenausbeute 2,08 für EUV-2D (OSTI 1004159); Kozawa-Modelle
2–3. Ursache: C (Yamamoto/Sekiguchi, PROLITH-Fit, enthält implizit ein G₀) und G₀ (Mack 2011, anderer Resist) stammen aus
verschiedenen Quellen; ihr Produkt ist nicht belegt. Folge für die Stochastik: das Molekülrauschen skaliert mit G₀,
das Photonenrauschen mit C·G₀ — beides hängt an dieser Inkonsistenz. **Prüfbar:** Test „Säuren pro absorbiertem Photon
im Band 1,5–3,5" (LBNL/Kozawa) als Invariante; Korrektur über G₀ = 0,15 (Yamamoto) *und* C-Neubewertung.

### 3.2 Der Default läuft ohne Sekundärelektronen-Blur
`SimulationConfig.se_blur_nm = 0.0`; die Presets (CAR 5 nm) sind nicht Default, alle Regressionstests setzen 5 nm explizit.
Ein Nutzer, der `euv simulate --resist-model full_chem` aufruft, bekommt ein Bild ohne Elektronenblur. Quellenlage für
den Wert: Thackeray 2010 EUV-spezifischer Beitrag 2,5 nm, Kozawa Thermalisierungsdistanz 2–3 nm (optimal), Torok
Eindringtiefen, Kang/NIST; der Preset-Wert 5 nm ist unbelegt. **Entscheidung nötig:** Default aus Quellen (≈ 2,5–3 nm)
mit Preflight.

### 3.3 Photon-zu-Säure-Multiplizität fehlt in der Rauschstatistik
Mit FQY > 1 erzeugt ein absorbiertes Photon mehrere Säuren (Sekundärelektronen). Unsere Kette sampelt Photonen (Poisson)
und wandelt danach PAG-Moleküle binomial mit p = 1 − e^{−C·E_lokal}; die Bündelung mehrerer Säuren pro Photon (zusammen-
gesetzter Poisson-Prozess, Mack 2011 „Stochastic exposure kinetics") wird nicht abgebildet. Konsequenz: Rauschen im
Säurefeld tendenziell unterschätzt. Mack 2011 (im Katalog) formuliert genau dieses Modell — Preflight möglich.

### 3.4 Temperatur ist kein Parameter
k, τ, D gelten für 110 °C bzw. 90 °C; `peb_temperature` existiert nicht. Yamamoto Fig. 3 liefert Kurven für 80–140 °C,
Fig. 4 den Arrhenius für k, Kang Table 3 den (unsicheren) für D. Ein Temperaturmodell wäre aus denselben Quellen
ableitbar und mit den Fig.-3-Kurven bei 90/100/120 °C falsifizierbar.

### 3.5 Neutralisation bei PEB-Bedingungen unbelegt
k_Q = 15 nm³/s (Mack 2011) ist ein Simulationswert eines anderen Resists; mit τ = 10,5 s ist die Neutralisation bei
G₀ = 0,2 nur teilweise vollständig ((h − q)·k_Q·G₀·t_eff ≈ 3) — das Ergebnis mit Quencher hängt damit empfindlich an einem
unbelegten Wert. Sekiguchi 2013 liefert nur Raumtemperatur; +28 % Abweichung bei q = 0,75 ungeklärt.

### 3.6 Was der Optikpfad nicht kann
Thin-mask ohne Vektor-/CRA-Effekte (Audit B4), Taper/Undercut abgelehnt (raise), pupil.py/source.py (Zernike,
Beleuchtungsformen) nicht in `run_simulation`; `info` und README versprechen „Hopkins + pupil + source" und High-NA.
Das ist eine Dokumentationslücke mit Anspruchsproblem.

### 3.7 Validierungslücke bleibt strukturell
Kein einziger Resist hat Dill+PEB+Mack **und** LWR/D2S aus einer Quelle. Yamamoto: Kinetik + Auflösung, keine LWR.
Vesters NXE1716: Mack-Kurve (DRM) + D2S/LWR bei 22 nm HP, aber kein Dill/PEB. Sekiguchi MET-1K/2D: Dill+Mack(+PEB
fragwürdig), kein LWR. Deshalb ist „Plausibilität 1,2–1,7×" heute die Obergrenze des Erreichbaren.

### 3.8 Software
CI seit 31. 8. durch Billing blockiert (alle „failures" sind 0-Schritt-Jobs); mypy --strict 140 beratende Befunde;
`dx`/`dx_nm` gemischt; Arbeitslog 2745 Zeilen — die Physikbeschreibung ist über Log, Feldkommentare und CHANGELOG
verteilt, ein konsolidiertes `docs/physics.md` fehlt; 61440-Zeilen-Test 5 min (CI-Risiko); notebooks laufen.

## 4. Neuer Plan — priorisiert, jede Stufe mit falsifizierbarer Vorhersage

**Stufe A — Konsistenz der Säureerzeugung (klein, hohe Hebelwirkung)**
A1 ✅ (2026-09-05, 67f844e) Test „Säuren pro absorbiertem Photon" (`pipeline.acids_per_absorbed_photon`): mit dem alten C
   6,0 gegen gemessen 1,4–2,1 (LBNL Table 3: MET-2D 1,39, EUV-2D 1,94–2,08) / ≈ 2 (Kozawa).
A2 ✅ (2026-09-06) — anders gelöst als hier geplant: nicht G₀, sondern **C** war das Problem. LBNL Gl. (1) definiert C in
   unserer Konvention und misst per Base-Titration MET-2D 0,0152 (Sekiguchis PROLITH-Fit für denselben Resist: 0,090);
   Fallica 2017 (PSI/ARCNL, Bleaching) 0,010–0,021 für sieben EUV-CARs. PROLITH-C ist effektiv (quencherabhängig; bei
   C·E ≪ 1 nur k·C bestimmt). Umgesetzt: C 0,0152, k 7,87 s⁻¹ (Yamamotos Rate k·H = 0,166 s⁻¹ bei 1,4 mJ/cm² erhalten),
   G₀ 0,2 (LBNL-Zahlen implizieren ≈ 0,22 für MET-2D). Preflight: D2S +2,7/+2,9 %, Photonen-LWR bei D2S ±3 %, Anker halten.
   Die Vorhersage „D2S ∝ 1/C" aus dem Plan war falsch gedacht — sie galt nur bei festem k. Offen: molekulares Rauschen
   (exposure_stochasticity) statistisch sauber messen (Log Fortsetzung 25, V4).
A3 ✅ (2026-09-06) Default 2,5 nm (Thackeray 2010, EUV-spezifischer Term in gemessener Zerlegung; keine direkte
   σ_SE-Messung gefunden, Modelle 2,1–3,3). Kettenblur 9,4 ⊕ 2,5 = 9,7 nm gegen Thackerays 11,5 (Rg-Term 4,3 und
   unerklärte 3,7 fehlen bewusst). Nebenbefund: se_blur 0 war im stochastischen Pfad Modellversagen (weißes Pixelrauschen,
   Dill-Sättigung, LWR = 0) → Warnung eingebaut. Preflight: D2S +0,2/+1,2 %.

**Stufe B — Einzelquellen-Anker NXE1716 (der Weg zur ersten echten Validierung)**
B1 ✅ durchgeführt (2026-09-06, Fortsetzung 27) — **Kriterium verfehlt.** DRM-Kurve vollständig digitalisiert, Dipol-90X-Quelle
   eingebaut, Preset `presets.nxe1716_config()`. Ohne freien Parameter: D2S 19,7 statt 11,0 (1,79×; Blur/Entwicklungszeit
   erklären ≤ 2 mJ/cm²). Mit deklarierter Dosisskalen-Kalibrierung: LWR 10,9 nm 3σ (nur Photonen) gegen 6,7 gemessen (1,6×);
   mit molekularem Rauschen 19 nm; mit σ_PEB 5 nm (τ(90 °C) unbekannt) 4,8 nm → Messung eingeklammert, Rauschmodell hier
   **weder validiert noch falsifiziert** (±1,6× ohne gemessenen Blur). Kandidaten: Quencher-Kontrast (NXE1716 =
   Hoch-Quencher, Q unbekannt), α_B und Säureausbeute B0 (Dissertation Fig. 4.1/4.4, nur grafisch), τ bei 90 °C, imec-Entwicklungszeit.
B2 Nächste Schritte: (a) Fig. 4.1/4.4 digitalisieren (α_B, Säuren pro Photon für B0) → C·G₀ und α resistspezifisch;
   (b) Quencher-Modell mit Q-Beladung als Parameter am Anker prüfen (Preflight: LWR fällt mit Q?); (c) Sampler-Varianz
   (V4b) gegen analytische Poisson-Erwartung; (d) Multiplizitätsmodell (3.3).

**Stufe C — Physikvervollständigung mit Quelle**
C1 Temperaturmodell k(T) aus Yamamoto Fig. 4 (Ea aus Steigung), τ(T) aus Fig.-3-Plateaus bei 80–140 °C; Test: Fig.-3-Kurven
   bei 90/100/120 °C. D(T) nur, wenn Kangs Unsicherheit tragbar wird (sonst dokumentiert).
C2 Photon-Säure-Multiplizität (Mack 2011): Preflight LWR-Änderung bei fester Mittelwertkette.
C3 Neutralisationsrate bei PEB: Mack 2011 k_Q als beratend markieren; Test gegen Sekiguchi mit Nachreaktionszeit-Hypothese
   (erklärt +28 %?).

**Stufe D — Optik ehrlich machen**
D1 Entweder pupil.py/source.py in `run_simulation` verdrahten (Beleuchtungsformen, Zernike; Tests: Dipol vs. konventionell
   ändert NILS wie erwartet) oder Ansprüche in README/`info` streichen.
D2 Thin-mask: Vektor-/CRA-Effekt zumindest als Warnung/Flag; RCWA-2D-Tests auf Parität mit 1D-Erhaltungssätzen.

**Stufe E — Software und Dokumentation**
E1 `docs/physics.md`: konsolidierte Modellbeschreibung jeder Stufe mit Formel, Parameter, Quelle, Test (aus Log/Kommentaren
   destilliert); README auf diese Datei verweisen.
E2 CI wieder aktiv (Billing beim Nutzer), dann Matrix beobachten; 61440-Test ggf. auf 8192 Zeilen als CI-Variante.
E3 mypy-Bereinigung in kleinen, semantikfreien Schritten; `dx`-Vereinheitlichung.
E4 Literatur: Anfrage an Yamamoto/Kozawa (Rohdaten Fig. 3/5) und Vesters (Fit-Tabelle) — nur durch den Nutzer.

**Reihenfolge:** A1 → A2 → A3 → B1 → C1 → D1/E1 → C2 → C3 → Rest. A und B sind jeweils ein bis zwei Arbeitssitzungen mit
Preflight; C1 und D1 sind größer.

## 5. Risiken, offen benannt
- Figuren-Ablesungen (k, τ, Schwelle) tragen ±10–15 %; ein Original-Datensatz würde das ersetzen.
- Der Default-Resist bleibt ein 2011er Forschungsresist (D2S ≈ 1,3–1,7 mJ/cm²); Zahlen daraus dürfen nicht als
  Produktionsresist-Aussagen gelesen werden.
- Ohne CI ist die Plattform-Matrix (Windows, 3.11–3.13) ungeprüft.
