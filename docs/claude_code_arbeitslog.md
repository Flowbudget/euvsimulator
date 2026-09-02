# Claude Code — Arbeitslog (autonomer Zyklus)

Dieses Log wird von Claude Code nach jedem abgeschlossenen Aufgabenpunkt ergänzt (nicht
überschrieben). Ziel: Der Projekt-Owner kann jederzeit den Fortschritt einsehen, ohne die
laufende Arbeit unterbrechen zu müssen. Format pro Eintrag: Datum, Aufgabenpunkt, was gemacht
wurde, was gefunden wurde, was offen bleibt, Commit-Referenz.

Kontext: Vor diesem Log wurde am 2026-09-02 bereits eine erste Prüfung der Commits `dccb7ea`
und `7ae7199` durchgeführt (siehe `audit/CLAUDE_CODE_REVIEW_dccb7ea_7ae7199_2026-09-02.md`),
dabei ein echter NILS=0.0-Bug im RCWA-Pfad gefunden und behoben.

---

## 2026-09-02 — Vorarbeit: NILS-Wraparound-Fix (aus vorheriger Prüfung, jetzt committed)

**Was:** `abbe.nils()` fehlte die periodische Wraparound-Fallunterscheidung, die
`pipeline._cd_via_aerial_threshold()` bereits hatte. Bei der Standard-`--use-rcwa`-CLI-Benchmark
gab `nils()` `0.0` zurück statt eines sinnvollen Werts.

**Gefunden durch:** End-to-End-Falsifikation (echte CLI-Ausführung statt nur Unit-Tests).

**Fix:** Paarungsschleife in `nils()` an die bereits korrekte Logik aus `pipeline.py` angeglichen.

**Verifiziert:** Reproduktionsfall NILS 0.0 → 3.971. 91 direkt betroffene Tests grün, volle
Suite (797 Tests) zur Bestätigung ausgeführt (Ergebnis siehe nächster Eintrag/Commit-Message).

**Details:** Siehe Nachtrag in `audit/CLAUDE_CODE_REVIEW_dccb7ea_7ae7199_2026-09-02.md`.

---

## 2026-09-02 — Aufgabe 1: Externe Referenzrecherche für Resist-Parameter

**Was:** Literaturrecherche (Websuche + Primärquellen als PDF gelesen, keine erfundenen Werte)
für Dill A/B/C/Q, PEB-Diffusion und Mack R_max/R_min/n/M_th. Ergebnisse als Kommentare mit
Quellenangabe direkt bei den Parametern in `pipeline.py` (`SimulationConfig`) dokumentiert.

**Gefundene Quellen (echte, primär gelesene Papers, nicht nur Suchmaschinen-Zusammenfassung):**

1. Fallica, R.; Stowers, J. K.; Grenville, A.; Frommhold, A.; Robinson, A. P. G.; Ekinci, Y.
   "Dynamic absorption coefficients of chemically amplified resists and nonchemically amplified
   resists at extreme ultraviolet." *J. Micro/Nanolith. MEMS MOEMS* 15(3), 033506 (2016).
   doi:[10.1117/1.JMM.15.3.033506](https://doi.org/10.1117/1.JMM.15.3.033506) — direkt gemessene
   Dill-A/B/C-Werte für mehrere EUV-spezifische CAR-Plattformen.
2. Lavery, K. A.; Choi, K.-W.; Vogt, B. D.; Prabhu, V. M.; Lin, E. K.; Wu, W.; Satija, S. K.;
   Leeson, M. J.; Cao, H. B.; Thompson, G.; Deng, H.; Fryer, D. S. "Fundamentals of the
   Reaction-Diffusion Process in Model EUV Photoresists." *Proc. SPIE* 6153, 615313 (2006),
   NIST/Intel-Kollaboration, Neutronenreflektometrie an einem Modell-EUV-Bilayer-Resist.

**Wichtiger Befund (belegt, noch NICHT umgesetzt):** Laut Fallica et al. gilt für EUV-CAR-Resists
A ≪ B (bleachable ≪ unbleachable), mit B ≈ Gesamtabsorptionskoeffizient α (einige μm⁻¹) — das
Gegenteil vom DUV/i-line-Regime (A ≫ B). Der aktuelle Code hat `dill_A=0.5 > dill_B=0.2` — laut
dieser Quelle im falschen Regime. Literaturwerte für EUV-CAR (Fallica Fig. 6, ungefähr von der
Balkengrafik abgelesen): A≈0.2–0.45 μm⁻¹, B≈4–5 μm⁻¹, C≈0.13–0.43 cm²/mJ.
`dill_C=0.05` liegt im Bereich anderer (nicht EUV-spezifischer) Studien (0.037–0.055 cm²/mJ),
aber unterhalb von Fallicas eigenen EUV-CAR-Messungen.

**PEB-Parameter (`peb_D`, `peb_sigma_diff`):** Gut durch Lavery et al. gestützt — gemessene
Diffusionslänge 5–15nm, Diffusionskoeffizient 2–8 nm²/s (aus cm²/s umgerechnet); aktuelle
Defaults (5.0, 5.0) liegen innerhalb bzw. am unteren Rand dieser gemessenen Bereiche.

**Mack-Parameter (`mack_R_max/R_min/n/M_th`):** **Keine belastbare EUV-spezifische, referenzierte
Quelle gefunden.** Ein häufig in Lehrmaterial zitiertes Beispiel (Resist "PD523AD", DUV/i-line-Ära,
nicht EUV, nicht primärquellenverifiziert) zeigt zwei stark unterschiedliche Parametersätze
(Mth=0.060 bzw. 0.450 je nach Prozessbedingung) — zeigt nur Größenordnung und große Streuung,
ist aber keine verlässliche Referenz. **Das ist eine reine Ermessensentscheidung ohne Beleg** im
Sinne der Stop-Kriterien dieses Auftrags — daher nicht verändert, sondern im Code klar als offen
markiert.

**Verifiziert:** `SimulationConfig()` lädt weiterhin fehlerfrei (Werte unverändert, nur
dokumentiert). `test_pipeline.py` + `test_full_chem_config.py`: 50/50 Tests grün.

**Offen für Aufgabe 2:** Die Dill-A/B-Korrektur ist gut belegt und könnte umgesetzt werden — das
würde aber bereits referenzierte Simulationsergebnisse verändern (siehe Stop-Kriterium im
Auftrag: "Änderung würde Ergebnisse verändern, die bereits als gründlich geprüft gelten"). Die
Mack-Parameter-Neuabstimmung (Aufgabe 2/3) hat keine solide externe Grundlage — hier ist eine
explizite Rückmeldung des Nutzers nötig, bevor mit Ermessenswerten weitergearbeitet wird.

---
