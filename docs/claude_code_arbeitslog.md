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

**Nutzer-Antwort:** Option B gewählt ("gezielter nach EUV-spezifischen Mack-Fits suchen, auch
wenn das an eine Bezahlschranke stoßen könnte").

---

## 2026-09-02 — Aufgabe 1 (Fortsetzung): Gezielte Mack-Parameter-Suche (Option B)

**Was:** Fünf weitere gezielte Websuchen + Versuche, konkrete SPIE-/Konferenz-Paper direkt zu
lesen (WebFetch auf PDF- und HTML-Fassungen, `curl` gegen eScholarship, Semantic-Scholar-API).

**Ergebnis: Zwei konkrete, thematisch exakt passende Kandidaten gefunden, aber beide von hier
aus nicht frei zugänglich (Bezahlschranke bzw. JS-Block):**
1. "Extraction and identification of resist modeling parameters for EUV Lithography," *Proc.
   SPIE* 6923, 69230T (2008) — SPIE Digital Library + ResearchGate liefern 403/leer.
2. Long, L. T.; Neureuther, A. R.; Naulleau, P. P. "Three-dimensional modeling of EUV
   photoresist using the multivariate Poisson propagation model." *J. Micro/Nanopatterning
   Mater. Metrol.* 20(3), 034601 (2021). doi:[10.1117/1.JMM.20.3.034601](https://doi.org/10.1117/1.JMM.20.3.034601)
   — SPIE Digital Library liefert leeren Inhalt beim Abruf; eScholarship-Mirror
   (escholarship.org/uc/item/5d17b1sr) ist eine JS-Single-Page-App, per `curl`/WebFetch nicht
   auslesbar. Eine (nicht selbst gelesene, nur aus einer Suchmaschinen-Zusammenfassung
   stammende) Erwähnung deutete auf einen kalibrierten Entwicklungsrate-Punkt bei
   Entschützungsgrad 0.27 = 35nm/30s hin — **das wird NICHT als Zahl übernommen**, da nicht am
   Original verifiziert (genau die Art unbelegter Übernahme, die dieses Projekt vermeiden soll).

**Ehrliches Fazit:** Trotz genuiner, mehrstufiger Suche keine frei zugängliche, EUV-spezifische,
primärquellenverifizierte Quelle für Mack R_max/R_min/n/M_th gefunden. Beide Kandidaten-Paper
sind im Code als Zeiger dokumentiert (`pipeline.py`, Kommentar bei `mack_*`), falls du oder Hermes
institutionellen Zugang habt.

**Verifiziert:** `SimulationConfig()` lädt weiterhin fehlerfrei nach der erweiterten
Dokumentation.

**Damit ist Aufgabe 1 abgeschlossen** (Dill A/B/C/Q und PEB solide referenziert; Mack-Parameter
mit bestem Aufwand recherchiert, Lücke transparent dokumentiert statt erfunden). Wartet auf
Nutzer-Entscheidung, wie mit der Mack-Lücke in Aufgabe 2/3 umzugehen ist.

---

## 2026-09-02 — Aufgabe 1 (Fortsetzung 2): Ursprung der Mack-Defaults gefunden

**Auslöser:** Nutzer teilte Hinweise einer anderen KI (Grok) zu Fundorten für EUV-Mack-Fits mit
(SPIE, lithoguru.com, Herstellerdatenblätter, IMEC/ASML). Das war kein neuer Zahlenwert, sondern
ein Hinweis, gezielter zu suchen — daraufhin `site:lithoguru.com` durchsucht.

**Fund:** Chris Macks eigenes, frei gehostetes Standardwerk **"Inside PROLITH: A Comprehensive
Guide to Optical Lithography Simulation"** (FINLE Technologies, 1997), Kapitel 7
("Photoresist Development"), Fig. 7-1 zeigt das Original-Mack-Modell mit den illustrativen
Beispielwerten `rmax=100 nm/s, rmin=0.1 nm/s, mTH=0.5, n=2/4/8/16`; Fig. 7-2 nutzt zusätzlich
`n=5` als einen der gezeigten Fälle. Das ist eine **exakte Übereinstimmung** mit den aktuellen
`mack_R_max`, `mack_R_min`, `mack_M_th`-Defaults im Code (und einer nahen Übereinstimmung bei
`mack_n`) — mit hoher Wahrscheinlichkeit ihr tatsächlicher Ursprung.

**Wichtige Einordnung:** Das ist eine generische Lehrbuch-Illustration, um die *Form* des
Modells bei variierendem `n` zu zeigen — **kein** Fit an einen gemessenen (schon gar nicht
EUV-spezifischen) Resist. Damit sind die Defaults jetzt nachvollziehbar herkunftsbelegt (keine
freie Erfindung), aber weiterhin nicht wissenschaftlich als EUV-CAR-repräsentativ validiert.

**Buch komplett lokal archiviert** (auf Nutzerwunsch): 179 Seiten, frisch von
`lithoguru.com` heruntergeladen (kein Bezahlzugang nötig — vom Autor selbst frei gehostet),
unter `references/literature/inside_prolith_mack_1997/Inside_PROLITH_Mack_1997.pdf` mit
begleitender `README.md`.

**Verifiziert:** `SimulationConfig()` lädt fehlerfrei, `test_pipeline.py` +
`test_full_chem_config.py`: 50/50 grün.

---

## 2026-09-02 — Aufgabe 2 (Teil): Dill A/B, PEB-Diffusion korrigiert; toter `peb_D`-Parameter gefunden und behoben

**Auslöser:** Nutzer bat um Weiterarbeit an euvsimulator, mit explizitem Prinzip "keine
Kompromisse" (siehe Erinnerung `feedback_euvsimulator_no_compromises`). Umgesetzt wurden die
zwei Korrekturen, für die inzwischen saubere, mehrfach belegte Daten vorlagen.

**1. Dill A/B vertauscht (behoben):** `dill_A: 0.5→0.3`, `dill_B: 0.2→4.5` μm⁻¹. Belegt durch
Fallica et al. 2016 (EUV-nativ, siehe vorheriger Eintrag) UND unabhängig durch die
Schnattinger-Dissertation (193nm, nur als Muster-Bestätigung genutzt, nicht für die Größenordnung
selbst). Betrifft nur den `full_chem`-Pfad, nicht die als solide geprüft geltende
`aerial_threshold`-Referenz — keine Regression der bereits validierten Werte.

**2. Toter Parameter `peb_D`/`--peb-D` gefunden und behoben:** `pipeline.py` rief
`reaction_diffusion_analytical()` nie mit `D=cfg.peb_D` auf — da `peb_sigma_diff` immer einen
konkreten Float-Default hatte, wurde `D` laut Funktionslogik in `resist/peb.py` IMMER ignoriert.
Nutzer, die `--peb-D` gesetzt hätten, hätten stillschweigend keinen Effekt gesehen — dieselbe
Fehlerklasse wie der früher behobene tote `--threshold`-CLI-Parameter. Fix: `peb_sigma_diff` ist
jetzt `Optional[float] = None` (expliziter Override), `peb_D` treibt per Default die
Diffusionslänge über `sqrt(2·D·t_bake)`. `peb_D: 5.0→3.3` nm²/s, gewählt so dass mit
`peb_t_bake=60s` die Ziel-Diffusionslänge (~20nm) reproduziert wird — beides einzeln im
Lavery-et-al.-2006-Messbereich (2-8 nm²/s) verankert.

**3. PEB-Diffusionslänge korrigiert (EUV-nativ, kein Wellenlängen-Haken):** `peb_sigma_diff`
effektiver Default jetzt ~20nm statt 5nm. Beleg: Anderson-Dissertation (OSTI 961531, LBL, echte
benannte EUV-Resists bei 13.5nm, gemessene Entschützungs-Unschärfe 9.7-38.4nm, "Reference"-
Formulierungen clustern bei 17-35nm). CLI-Defaults und `calibrate`-Suchbereiche
(`peb_sigma_diff`, `mack_n`) konsistent nachgezogen und verbreitert, wo die alten Bounds jetzt
bekannte reale Werte künstlich abgeschnitten hätten (Grundprinzip 2 — keine künstlichen Grenzen).

**4. Tiefere Erkenntnis, NICHT gefixt (bewusst, siehe unten):** `resist_model="full_chem"`
produziert mit allen Default-Parametern weiterhin `CD=64nm` (komplett unentwickelt) — ein
vorbestehendes, durch diese Änderungen weder verursachtes noch verschlimmertes Problem.
Root-Cause quantitativ diagnostiziert: `peb_k · acid_max · peb_t_bake ≈ 0.3-0.4`, nötig wäre
`> 0.693` für einen Schwellenwert-Übertritt. **Experimentell verifiziert, dass das NICHT durch
Ersetzen eines einzelnen Parameters lösbar ist:** `dill_Q` von 0.04 auf den real-EUV-belegten
Wert 0.5 (Mack et al. 2011, Tabelle I, `φPAG`) angehoben, schießt direkt durch bis zum
GEGENTEILIGEN Entartungsfall (`CD=0.0nm`, alles entwickelt sich weg) — kein Zwischenwert wäre
eigenständig belegt, nur erraten. `peb_k` (unbelegt) und `dill_C` (jetzt mit ARCNL-2017-Beleg,
0.010-0.021 cm²/mJ für echte EUV-CAR-Formulierungen, aber >40x Streuung über reale Resists)
wurden geprüft und ausführlich dokumentiert (Zitate + offene Fragen direkt im Code bei
`mack_M_th`), aber NICHT verändert, weil jede Einzeländerung ohne eigenen Beleg genau die
Art Kompromiss wäre, die der Nutzer explizit ausgeschlossen hat. Vollständige, in sich
konsistente EUV-CAR-Parametersätze (Dill+PEB+Mack aus EINEM real gemessenen Resist) wurden trotz
sehr breiter Suche (siehe `/Users/flo/mack fits/catalog.md`, jetzt ~25 Quellen über
lithoguru.com, imec-publications.be, open.fau.de, OSTI.gov, ARCNL, Zitationsketten) nicht frei
zugänglich gefunden — nur für 193nm (Schnattinger). **Empfehlung:** entweder echte
Bossung-Kalibrierdaten über `euv calibrate` einspeisen, sobald verfügbar, oder weiter gezielt
nach einem einzelnen vollständigen EUV-193nm-äquivalenten Fund suchen.

**Verifiziert:** Vollständige Testsuite nach allen Änderungen: 796/797 grün (1 unabhängiger,
vorbestehender Fehlschlag in `test_metro.py`, siehe früherer Eintrag). Keine Regression.

---
