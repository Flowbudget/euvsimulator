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

## 2026-09-03 — Mack R_max/R_min: EUV-nativer, aber PROVISORISCHER Fund eingebaut

**Kontext:** Fortsetzung der Mack-Parameter-Recherche (siehe `/Users/flo/mack fits/catalog.md`,
inzwischen 28 Quellen). Bester Fund: Vesters, De Simone, De Gendt (imec/KU Leuven), *J.
Photopolym. Sci. Technol.* 30(6), 675 (2017), frei über J-STAGE — echte, bei ASML-NXE-Scannern
benannte EUV-Resists (NXE1716, NXE1717), explizit mit dem Original-Mack-Modell gefittet, aber
nur als Diagrammkurve (Fig. 6) publiziert, keine Zahlentabelle.

**Rigorose Neuvermessung statt Schätzung:** Seite mit 400dpi gerendert, alle Haupt-Gitterlinien
pixelgenau erkannt (Konsistenz <0.5px über mehrere Dekaden), Datenpunkt-Marker exakt lokalisiert.
Gegenprobe bestanden: Meine Messung bestätigt die im Fließtext behauptete Beziehung (High-
Quencher-Resist hat höheres Rmin UND Rmax) in beide Richtungen.

**Umgesetzt:** `mack_R_max: 100.0→205.0`, `mack_R_min: 0.1→0.0143` (geometrisches Mittel der
beiden real gemessenen Resists, um nicht willkürlich einen zu bevorzugen). `mack_n`/`mack_M_th`
bewusst NICHT verändert — aus zwei Plateau-Punkten pro Kurve lässt sich weder die Steilheit (n)
noch der Schwellenwert (Mth) sauber zurückrechnen, ohne das unbekannte Dosis→Schutzgrad-Modell
der Autoren selbst zu erfinden.

**Wichtige Einordnung, zweifach:**
1. **Diese Werte sind ausdrücklich PROVISORISCH.** Der Nutzer hat am 2026-09-03 die
   korrespondierende Autorin (Danilo De Simone, imec) direkt angeschrieben und um die echten
   gefitteten Werte gebeten. Bis zur Antwort (oder einer unabhängigen Bestätigung) gelten diese
   Zahlen als vorläufig — ausführlich im Code bei `mack_R_max` dokumentiert, inkl. Hinweis, das
   nicht stillschweigend als "erledigt" zu betrachten, falls diese Notiz mal alt wird.
2. **Diese Änderung hat aktuell KEINE Auswirkung auf Simulationsergebnisse.**
   `mack_R_max`/`mack_R_min`/`mack_n` werden nur in `__post_init__` zur Validierung genutzt —
   der eigentliche `full_chem`-Entwicklungsschritt ruft `threshold_development()` auf (binärer
   Schwellenwertvergleich), nicht die kontinuierliche Mack-R(M)-Gleichung. `MackModel` existiert
   in `resist/develop.py`, wird aber nirgends instanziiert (bereits bekanntes, separates
   Problem, siehe Projekt-Status-Erinnerung — "Aufgabe 3" der ursprünglichen Liste). Diese
   Änderung ist also reine Dokumentations-/Vorbereitungsarbeit für den Tag, an dem das verdrahtet
   wird — kein Fix für die CD=64nm-Entartung.

**Wie mit Unsicherheit umgegangen wird (Frage des Nutzers "wie würdest du es tun"):** Kein
separates Tracking-System eingeführt (wäre Überkonstruktion für den aktuellen Projektstand) —
stattdessen: (a) der Wert selbst trägt "PROVISIONAL" im Kommentar direkt daneben, nicht nur in
einem separaten Dokument, damit niemand die Zahl kopiert ohne den Kontext zu sehen; (b) der
Kommentar nennt explizit, was bei Antwort/Nicht-Antwort zu tun ist; (c) Status zusätzlich hier im
Arbeitslog und im `mack fits`-Katalog nachverfolgt. Wenn die Antwort eintrifft: Kommentar, Wert
und diesen Log-Eintrag aktualisieren, "PROVISIONAL" entfernen.

**Verifiziert:** `SimulationConfig()` lädt fehlerfrei. Vollständige Testsuite läuft (Ergebnis
siehe nächster Eintrag/Commit).

---

## 2026-09-03 (Fortsetzung): GitHub/Code-Repo-Suche + zweite EUV-native Quelle für mack_n

**Auslöser:** Nutzer wies zurecht darauf hin, dass ich Suchkanäle (GitLab, Firmen-GitHub-Orgs,
Kaggle) nur *vorgeschlagen*, aber nicht tatsächlich durchsucht hatte ("du schlägst mir Quellen
vor aber durchsuchst sie nicht?!"). Danach explizite Anweisung, überall weiterzusuchen, bis wir
die Daten haben.

**Ergebnislos, aber tatsächlich durchsucht:** GitLab (API verlangt Auth), Kaggle, Hugging-Face-
Datasets (ein Fund — `carbon-lab/xrr-photoresist`, echte Synchrotron-XRR-Rohdaten zu einem
TOK-Resist, aber keine Dill/Mack-Parameter), PyPI, GitHub-Orgs von imec/LamResearch/Inpria/
merckgroup/zeiss (keine lithografierelevanten Repos — der "imec"-Treffer war ein
namensgleiches, unabhängiges Kollektiv), CORE.ac.uk (Bot-Schutz), CiNii/japanische Suche.

**Neuer Kanal — euvlitho.com (EUVL Workshop, jährliche Konferenz seit 2008, komplett frei):**
Über ein GitHub-Topic-Suche gefundenes fremdes High-NA-EUV-Simulatorprojekt
(`JiSeok1579/high-na-euv-sim`) verwies in seiner Literaturliste auf diese bisher nie durchsuchte
Konferenzarchiv-Site. Systematisch durchsucht: Sitemap → alle Jahres-Abstracts/Proceedings-PDFs
2008–2021 → einzelne nummerierte Paper. Mehrere Multi-Trigger-Resist-Paper (Vesters/Popescu/
Robinson, teils mit De Simone) gefunden und frei geladen (Birmingham-PURE-Repository, J-STAGE,
PSI-DORA-Repository) — keines enthielt eine numerische Mack-Tabelle. Eine KI-Websuch-
zusammenfassung behauptete einen Mack-Fit mit Entwicklertemperatur-Abhängigkeit für ein
MTR-Paper — **in keinem tatsächlich gelesenen Original verifizierbar, daher explizit NICHT
übernommen** (mutmasslich eine Konflation der Suchzusammenfassung).

**🏆 Fund: Itani, Kaneyama, Kozawa, Tagawa (Selete/Osaka University), EIPBN 2008, frei via
eipbn.org.** Eine echte, explizite Zahlentabelle (nicht aus einem Diagramm rekonstruiert) für
zwei mit echtem EUV-Licht belichtete, real entwickelte Resists:
- PHS-Resist (Standard-CAR-Polymerbasis): Rmax=85nm/s, Rmin=0.0017nm/s, Steigung m=2.5
- Molekularer Resist: Rmax=93nm/s, Rmin=0.1nm/s, m=7.0

Beide Rmax/Rmin-Werte bestätigen unabhängig die Größenordnung der bereits verwendeten
Vesters-2017-Werte (anderes Institut, anderes Instrument, 9 Jahre Abstand). **m=2.5 (PHS) ist
der erste echte EUV-native Wert für `mack_n` im gesamten Projekt** — bisher stand dort nur
Mack's generischer Lehrbuchwert 5.0.

**Umgesetzt in `pipeline.py`/`cli.py`:**
- `mack_n: 5.0 → 2.5` (PROVISIONAL, Itani et al. 2008, PHS-Resist-Wert gewählt statt des
  molekularen Resists, da PHS die mainstream-CAR-Chemieklasse ist)
- `mack_R_max`/`mack_R_min`-Kommentar um die Kreuzvalidierung durch Itani ergänzt (Zahlenwerte
  selbst unverändert — Vesters' NXE1716/1717 bleiben näher an einem echten Produktresist als
  Itanis generische Resistklassen)

**Nebenfund beim Bearbeiten (echter, bisher unentdeckter Bug):** `cli.py`s
`--mack-R-max`/`--mack-R-min`/`--mack-n`-CLI-Defaults sowie die Fallback-Werte im
`calibrate`-Befehl (`initial_params`, `pipeline_fn`) waren seit der letzten Runde (Commit
`ed40397`) nie mit `pipeline.py`s `SimulationConfig`-Defaults synchronisiert worden — die CLI
hätte ohne explizite Flags stillschweigend die alten Werte (100.0/0.1/5.0) benutzt. Jetzt
konsistent.

**Neuer paywalled Fund (nicht adoptiert, nur dokumentiert):** Vesters/De Simone/De Gendt,
"Influence of Post Exposure Bake time on EUV photoresist RLS trade-off", Proc. SPIE 10143
(2017) — echte PEB-Kinetik-Studie an 6 realen EUV-CAR-Resists, aber via lirias.kuleuven.be-API
bestätigt: kein PDF hinterlegt, auch im eigenen Institutsrepository nur Metadaten.

**Verifiziert:** `uv run python -c "SimulationConfig()"` lädt fehlerfrei mit den neuen Werten.
Vollständige Testsuite: 796/797 bestanden, die eine Fehlschlag ist die bereits bekannte,
unabhängige `test_metro.py`-Altlast (verwaister `import euv.metro` aus der OpEnUV-Umbenennung)
— keine Regression durch diese Änderungen.

**Verbleibende Lücke (Stand zu diesem Zeitpunkt):** `mack_M_th` weiterhin ohne EUV-native
Quelle. Vollständiger Suchverlauf (35 katalogisierte Quellen über 9 Runden) in
`/Users/flo/mack fits/search_log.md` und `catalog.json`.

---

## 2026-09-03 (Fortsetzung, "dann los"): Hauptfund — vollständiger, in sich konsistenter
## EUV-nativer Dill+Mack-Parametersatz (Yamamoto et al. 2011)

**Auslöser:** Nutzer bat, den konkret genannten nächsten Schritt tatsächlich zu verfolgen —
Zugang zum paywalled SPIE-2009-Paper von Yamamoto/Kozawa/Tagawa (Osaka University) und
Mimura/Iwai/Onodera (Tokyo Ohka Kogyo, TOK) zu prüfen.

**Paywalled Paper blieb unzugänglich** (SPIE-Seite durch Bot-Schutz gesichert, bewusst nicht
umgangen; kein Volltext auf ResearchGate; Autoren-eigene heutige Laborseite betrifft anderes
Forschungsfeld; CrossRef nur Metadaten). Bei der Suche nach freien Parallel-Publikationen
derselben Gruppe fand eine direkte J-STAGE-Titelsuche stattdessen den bereits publizierten,
frei zugänglichen offenen Zwillingsartikel derselben Autoren im selben Journal wie unser
bisher bester Fund (Vesters 2017).

**🏆🏆 Yamamoto, Kozawa, Tagawa, Mimura, Iwai, Onodera, "Dissolution Kinetics in Chemically
Amplified EUV Resist", J. Photopolym. Sci. Technol. 24(4), 405-410 (2011), frei via J-STAGE.**
Tabelle 2 gibt die vollständigen PROLITH-Berechnungsparameter für einen echten
EUV-belichteten Resist ("Polymer A", PHS-Derivat mit 35% Schutzgruppen, TOK-Chemie) — alle
sieben Werte aus EINER Messkampagne gemeinsam gefittet:

- **Dill (ABC):** A=0/µm, B=1.06/µm, C=0.08997 cm²/mJ
- **Mack:** Rmax=68.6nm/s, Rmin=0.10nm/s, **Mth=0.39**, n=18.2

Das ist der erste vollständige, in sich konsistente EUV-native Parametersatz der gesamten
Suche — insbesondere der seit Projektbeginn gesuchte Mth-Wert (bisher nur Mack's generische
Lehrbuch-Illustration 0.5).

**Rigoros verifiziert, nicht nur übernommen:**
- PDF direkt gelesen (nicht nur Suchzusammenfassung)
- Tabellenseite bei 300dpi gerendert, um OCR-Fehler auszuschließen — dabei tatsächlich einen
  echten Fehler im Original entdeckt: die PEB-Aktivierungsenergie steht in der Tabelle als
  "27.8 kJ/mol", im Fließtext als "ca. 27.8 Kcal/mol" für denselben Wert. Ein Kcal/kJ-Fehler
  wäre Faktor 4.184 — bei einem Arrhenius-Term über Größenordnungen. Diese spezifische
  Ableitung für `peb_k` deshalb bewusst NICHT übernommen, nur als offene Ambiguität im Code
  dokumentiert.
- Vor dem Commit empirisch getestet: `SimulationConfig()`/`run_simulation()` mit alten vs.
  neuen Werten verglichen — die bekannte CD=64nm-Entartung im `full_chem`-Pfad bleibt exakt
  unverändert (bestätigt: `peb_k`/`dill_Q` sind weiterhin der bindende Engpass, nicht
  `dill_C`/`mack_M_th`).

**Umgesetzt:** `dill_A/B/C` und `mack_R_max/R_min/n/M_th` in `pipeline.py` und `cli.py`
(inkl. `calibrate`-Fallback-Werte) auf die Yamamoto-Werte gesetzt. Der bisherige Flickenteppich
(Fallica für Dill, Vesters für Rmax/Rmin, Itani für n, Mack's Lehrbuch für Mth) bleibt als
Kreuzvalidierung in den Kommentaren erhalten, wird aber nicht mehr als Default verwendet —
ein einzelner, gemeinsam gefitteter Satz aus einer echten Messung ist physikalisch belastbarer
als unabhängig bestpassend ausgewählte Einzelwerte, die nie zusammen gefittet wurden.

**Eine Auffälligkeit bewusst im Code geflaggt statt verschwiegen:** `mack_n=18.2` ist deutlich
höher als jeder andere in dieser Suche gefundene n-Wert (Itani: 2.5–7.0, Mack's generisch: 5) —
eine viel steilere Schwellenantwort. Nicht durch andere Quellen widerlegt, aber explizit als
der am wenigsten durch Vorerwartung gestützte Wert markiert.

**Verifiziert:** `uv run python -c "SimulationConfig()"` lädt fehlerfrei; `full_chem`-CD
bleibt 64.0nm (erwartet, siehe oben), `aerial_threshold`-CD unverändert (27.6nm, da
dill_A/B/C dort nicht verwendet werden).

**Vollständige Testsuite deckte einen echten Folgeeffekt auf (kein Bug, aber muss behandelt
werden):** 5 statt 1 Fehlschlag. 4 davon in `test_development_stochasticity.py`/
`test_ler_production_integration.py` — beide nutzen `_car_cfg()` mit `resist_model="full_chem"`
und ungesetzten `dill_A/B/C` (also den neuen Defaults). `dill_C` (0.05→0.08997) ändert
`dose_to_acid()`s Ausgabe, die in die stochastischen LER/LWR-Schätzer einfließt — die dort
hinterlegten "Golden Values" (harte Zahlenvergleiche zur Regressionserkennung) stammen noch
von den alten Dill-Werten. **[KORREKTUR, 2026-09-03, nachträglich beim MackModel-Wiring
entdeckt: hier stand ursprünglich fälschlich, `dill_A+dill_B` (Gesamtabsorption) sei die
Ursache. Tatsächlich haben `dill_A`/`dill_B` im gesamten Code NULL Effekt auf irgendein
Simulationsergebnis — sie werden nirgends gelesen, nur deklariert/durchgereicht. Isoliert
per direktem Test bestätigt: `dill_C` allein reproduziert 100% der beobachteten
Golden-Value-Verschiebung. Siehe den entsprechenden Log-Eintrag weiter unten für die volle
Aufarbeitung.]** Das ist eine **echte, erwartete Konsequenz** der bewussten Parameteränderung,
kein Implementierungsfehler — im selben Stil aktualisiert, wie es das Projekt bereits einmal
bei der "P1-1 TCC correction" gehandhabt hat (dokumentierter Grund + alter Wert im Kommentar
erhalten, nicht stillschweigend überschrieben). Alle sechs betroffenen Konstanten
(`GOLDEN_LARGE_N_LER`, `GOLDEN_LARGE_N_LWR`, `GOLDEN_LEGACY_LER`, `GOLDEN_LEGACY_LWR`,
`GOLDEN_N_EFF`, `GOLDEN_L_INT_NM`, `GOLDEN_RHO_TRUNC`, plus ein inline verwendeter Duplikatwert)
mit frisch berechneten, reproduzierbaren Werten (seed=42) aktualisiert. Volle Testsuite danach
erneut laufen lassen: **796/797 bestanden, die eine Fehlschlag wieder nur die bereits bekannte,
unabhängige `test_metro.py`-Altlast** — keine Regression durch diese Änderungen.

**Verbleibende Lücken:** `dill_Q` und `peb_k` weiterhin unbelegt (Letzteres trotz eines
Beinahe-Fundes an der o.g. Einheiten-Ambiguität gescheitert) — das sind jetzt die einzigen
beiden noch offenen Parameter im gesamten Satz. Separate, unveränderte Architektur-Aufgabe:
`MackModel` ist weiterhin nicht in die Pipeline verdrahtet. Vollständiger Suchverlauf (37
katalogisierte Quellen über 9 Runden) in `/Users/flo/mack fits/search_log.md` und
`catalog.json`.

---

## 2026-09-03 (Fortsetzung): dill_Q/peb_k — vom Zahlensuche- zum Kalibrier-Problem verstanden

**Auslöser:** "was machen wir da jetzt?" — statt weiter blind nach Zahlen zu suchen, wurde das
Fenster für `dill_Q`/`peb_k` erst empirisch mit dem eigenen Code kartiert.

**Empirisch:** Mit `peb_k=0,0723` (Yamamoto's eigener Arrhenius-Fit, siehe unten) braucht
`dill_Q` ein Fenster von ~0,57–0,95 für eine reale (nicht entartete) CD. Mack et al. 2011s
eigener "Baseline"-Wert (0,5, bereits zitiert) und ihr eigenes theoretisches Maximum (1,0)
liegen knapp außerhalb, auf gegenüberliegenden Seiten — zwei real zitierte Zahlen kombiniert
verfehlen das Ziel nur um ~13%, statt wie zuvor um Größenordnungen.

**Ein Beinahe-Fehler, rechtzeitig gefangen:** Bei der Suche nach einem realen "Quantum
Yield"-Wert hätte eine schlecht formatierte PDF-Extraktion (OSTI-Quelle, echte benannte
Rohm-and-Haas-Resists EUV-2D/MET-2D/XP-5496) beinahe die Spalte "Transmittance" (0,56–0,71)
mit "Quantum Yield" verwechselt. Mit `-layout` neu extrahiert und korrigiert, bevor irgendeine
Zahl verwendet wurde: die echten Werte sind 1,94/1,39/1,45 — alle über 1.

**Die eigentliche Erkenntnis:** Mack et al. 2011 (frei via lithoguru.com) unterscheiden explizit
zwei verschiedene physikalische Größen: **φ_PAG** (Wahrscheinlichkeit, dass ein bereits
angeregtes PAG-Molekül zu Säure reagiert, auf [0,1] begrenzt — entspricht exakt `dill_Q`s Rolle
im Code, `acid = Q*(1-M)`) und **Y0/"Film Quantum Yield"** (Säuren pro absorbiertem Photon,
kann bei EUV wegen Sekundärelektronen->Mehrfachanregung benachbarter PAGs >1 sein — genau
das, was die gesamte Literatur, die wir gefunden haben, tatsächlich misst und veröffentlicht).
φ_PAG selbst wird laut Mack's eigener Methodik nicht direkt gemessen, sondern nur durch
Rückfitten gegen eine Monte-Carlo-Simulation gewonnen — keine Publikation in der gesamten
Suche berichtet einen gemessenen φ_PAG für einen realen Resist.

**Konsequenz:** Weitere Literatursuche für `dill_Q` ist strukturell aussichtslos — die
Literatur berichtet systematisch die falsche Größe. `dill_Q`/`peb_k` sind für dieses Modell
echte Kalibrierkonstanten (Weg: `euv calibrate` gegen reale Dosis/CD-Daten), keine
literaturzitierbaren Naturkonstanten. Das bestätigt den bereits im Code dokumentierten Weg —
jetzt mechanistisch begründet statt nur vermutet. Alles ausführlich in den `dill_Q`-, `peb_k`-
und "PRE-EXISTING KNOWN ISSUE"-Kommentaren in `pipeline.py` dokumentiert; keine
Verhaltensänderung der Simulation (nur Dokumentation), verifiziert.

Vollständiger Suchverlauf (39 katalogisierte Quellen über 9 Runden) in
`/Users/flo/mack fits/search_log.md` und `catalog.json`.

---

## 2026-09-03 (Fortsetzung): MackModel + dill_abc_exposure verdrahtet — CD=64nm-Problem gelöst

**Auslöser:** "wie gehts weiter?" → Empfehlung, `MackModel` tatsächlich in die Pipeline zu
verdrahten, statt nur Werte zu dokumentieren, die nichts bewirken. Nutzer: "beides zusammen"
(auch `dill_abc_exposure` für echte tiefenaufgelöste Belichtung).

**Ein zweiter, unerwarteter Fund beim Start der Arbeit:** `dill_A`/`dill_B` werden im
GESAMTEN Code nirgends gelesen — nur deklariert und durchgereicht. Dieselbe Bug-Klasse wie
bei `MackModel`. Dabei fiel auf, dass eine frühere Commit-Erklärung (LER/LWR-Golden-Values
seien wegen `dill_A+dill_B` geändert) faktisch falsch war — tatsächlich war `dill_C` allein
verantwortlich. Per direktem Isolationstest bestätigt und in drei Dateien korrigiert
(`pipeline.py`, beide betroffenen Testdateien), bevor mit der eigentlichen Aufgabe
weitergemacht wurde.

**Umbau:** `_cd_via_full_chem`s deterministischer Zweig nutzt jetzt:
1. `dill_abc_exposure()` — echte tiefenaufgelöste Beer-Lambert-Absorption über `dill_A`/`dill_B`
   (21 Tiefenschichten, neuer Parameter `n_develop_layers`)
2. `reaction_diffusion_analytical()` — PEB, jetzt pro Tiefenschicht (die Funktion war bereits
   dimensionsagnostisch, keine Änderung nötig)
3. `MackModel.rate()` über `surface_advancement_level_set()` — kontinuierliche
   Zeit-integrierte Entwicklungsfront statt binärem Schwellenwertvergleich

Neue Config-Parameter `resist_thickness_nm` (50nm) und `develop_time_s` (30s) — beide direkt
aus derselben Yamamoto-et-al.-2011-Quelle zitiert wie die übrigen Resist-Parameter (50nm ist
explizit der Fall, den die Autoren selbst als gut aufgelöst beschreiben; 26nm zeigte in ihren
eigenen Worten "considerable bridge of pattern side walls"). Der stochastische LER/LWR-Zweig
bleibt bewusst unangetastet (eigenständiges Subsystem, eigener Umbau als Folgearbeit).

**Der eigentliche Durchbruch:** Mit der neuen, physikalisch vollständigen Kette wurden
`dill_Q=0,5` (Mack et al. 2011, echter zitierter Basiswert) und `peb_k=0,0723`
(Yamamoto et al. 2011, echter zitierter Arrhenius-Wert) — beide zuvor als "real, aber
funktioniert nicht" verworfen — erneut getestet. Ergebnis: **CD=36,5nm** bei der
Standarddosis (Ziel-Linienbreite: 32nm) — real, nicht entartet, und bestätigt dosis-monoton
(15→30 mJ/cm²: CD 64,0→13,0nm, glatt fallend) sowie mit plausiblem Flächenanteil (43%
entwickelt). **Beide Werte als neue Defaults übernommen.**

**Erkenntnis:** Das "knapp daneben"-Ergebnis von vorhin (13% Abstand) war kein Hinweis, dass
die Zahlen falsch waren — es war ein Hinweis, dass das VEREINFACHTE Modell, gegen das getestet
wurde, selbst die Einschränkung war. `full_chem` läuft jetzt komplett mit echten, zitierten,
EUV-nativen Werten für Dill A/B/C/Q, PEB D/k/t_bake und Mack Rmax/Rmin/Mth/n durch die
physikalisch vollständige, tiefenaufgelöste Kette.

**Verifiziert:**
- `aerial_threshold`-Pfad unverändert (27,6nm, keine Regression)
- Dosis-Sweep monoton und physikalisch plausibel
- Vollständige Testsuite (Ergebnis siehe nächster Eintrag/Commit)

**Verbleibend:** (a) keiner der Resist-Chemie-Werte ist bislang durch mehr als eine Quelle auf
Zahlenebene exakt bestätigt (nur Größenordnung, siehe einzelne Parameter-Kommentare) — echte
Kalibrierdaten via `euv calibrate` bleiben der Weg, das weiter zu verfestigen; (b) der
stochastische LER/LWR-Pfad nutzt weiterhin sein eigenes, unabhängiges vereinfachtes Modell —
eigenständige Folgearbeit.

---

## 2026-09-03 (Fortsetzung): stochastischer LER/LWR-Pfad ebenfalls auf MackModel verdrahtet

**Auslöser:** "ja, mach den stochastischen Pfad auch." Ziel: derselbe tiefenaufgelöste
`dill_abc_exposure → PEB → MackModel`-Kette, die den deterministischen CD-Pfad bereits
repariert hat, jetzt auch für den photonenrauschgetriebenen LER/LWR-Zweig.

**Vier echte, unabhängige Bugs gefunden und behoben, in dieser Reihenfolge:**

1. **Performance-Bug (vorbestehend, aber erst jetzt sichtbar):** `gaussian_se_blur`s direkte
   Faltung skaliert bei großem Kernel (PEB-Diffusion, σ≈20nm → Kernel≈250px) und vielen
   Tiefenschichten/Zeilen katastrophal — 41s für einen einzigen PEB-Aufruf bei
   `grid_y=1024`, hochgerechnet auf den Standard `grid_y=4096` mehrere Minuten pro
   Realisierung. **Fix:** FFT-basierte zirkuläre Faltung als Fast-Path für große Kernel
   (`_fft_circular_blur`) — mathematisch identisch zur direkten Faltung (beide berechnen
   zirkuläre Faltung, nur unterschiedlich schnell), numerisch auf ~2e-8 verifiziert.
   Ergebnis: 41s → 0,19s bei 4x größerem Grid (>800x Speedup).

2. **Tiefenquantisierung maskiert Rauschen:** `surface_advancement_level_set` gab nur
   `n_layers` (21) diskrete Tiefenwerte zurück (Treppenfunktion) — das photonische Rauschen
   ist viel feiner als eine Stufe (2,5nm), wurde also komplett weggerundet, LER=0 exakt.
   **Fix:** lineare Interpolation innerhalb der letzten (Grenz-)Schicht statt Treppenfunktion
   — verbessert nebenbei auch den deterministischen Pfad (glattere, genauere Tiefenwerte
   statt Quantisierung auf 21 Stufen).

3. **Threshold/Intensity-Kopplungsfehler:** `extract_ler`/`extract_lwr`/`ler_estimate`
   binarisieren `developed` intern nochmal mit demselben `threshold`, der auch für die
   Sub-Pixel-Interpolation von `intensity` genutzt wird. Ein bereits-binäres `developed`
   (0/1) mit `threshold=50` (nm-Skala) verglichen ergibt immer `False` — komplett degeneriert.
   **Fix:** für den OFF-Modus wird jetzt das rohe kontinuierliche Tiefenfeld sowohl als
   `developed` als auch als `intensity` übergeben (konsistente Skala); für den ON-Modus
   (`development_stochasticity=True`, bereits binär von `stochastic_development()`)
   `threshold=0.5`, keine Intensity-Interpolation.

4. **`development_stochasticity=True` strukturell inert:** Die "Drive"-Formel
   (`(latent-threshold)/threshold`) wurde für die ALTE Säure-Konzentrations-Skala entworfen,
   wo Überschwingen über den Schwellenwert leicht 100%+ betragen konnte. Mit der neuen,
   tiefenbasierten Skala liegt das maximale Überschwingen (eine Extraschicht) bei nur ~5% —
   `development_strength=1.0` (alter Default) ergab praktisch Rate=0 überall.
   **Fix:** `development_strength` empirisch neu kalibriert (über mehrere Seeds verifiziert)
   auf 20.0 — nicht literaturzitiert (das ist ein numerischer Raten-Regler, keine physikalische
   Resist-Eigenschaft), aber notwendig, damit das Feature überhaupt wieder etwas tut.

**Weiterer Fund beim Testen:** drei Testdateien (`test_ler_production_integration.py`,
`test_development_stochasticity.py`, `test_stochastic_pipeline.py`) pinnten `dill_Q=1.0`
explizit — ein Überbleibsel, um die ALTE, kaputte Kette zu einem nicht-entarteten Ergebnis
zu zwingen. Mit der neuen Kette flutet `dill_Q=1.0` das gesamte Feld (kein Rand mehr messbar,
"no valid edges found"). Alle drei auf die neuen, echten Defaults (`dill_Q=0,5`) umgestellt.

**Ein weiterer echter Design-Kompromiss, bewusst nicht verwässert:** `test_neff_ge_30`
erwartete `n_eff >= 30` beim bloßen Standard-`grid_y=4096`. Die neue, physikalisch
vollständigere Kette hat eine echte, deutlich längere räumliche Korrelationslänge (reale
PEB-Diffusion koppelt jetzt benachbarte Zeilen korrekt: `l_int_nm` stieg von ~8,4 auf ~29,2),
wodurch `n_eff` bei 4096 Zeilen von ~61 auf ~17,8 sank. Statt die Schwelle des Tests
stillschweigend zu senken ODER den globalen Default zu verdoppeln (und damit die Rechenkosten
jedes Standard-Aufrufs), fordert nur dieser eine Test jetzt explizit mehr Zeilen an
(`grid_y=8192`, verifiziert `n_eff≈37`) — der globale Default bleibt bei 4096.

**Ressourcenschonend getestet** (nachdem der volle Suite-Lauf den Mac überlastet hatte):
jede Testdatei einzeln statt der gesamten Suite auf einmal. Alle 797 Tests über alle Dateien
verteilt geprüft: 796 bestanden, 1 (bekannte, unabhängige `test_metro.py`-Altlast)
unverändert. Kein Testfehler durch diese Änderungen offen.

**Verbleibend, bewusst nicht angegangen:** die `development_strength=20.0`-Kalibrierung ist
grob (funktionsfähig, nicht feinabgestimmt); eine genauere Kalibrierung bräuchte echte
LWR-Messdaten für einen realen Resist, nicht nur "ergibt einen plausiblen Wert."

---

## 2026-09-03 (Fortsetzung): Realitätscheck — simulierte LWR gegen echte Vesters-Messdaten

**Auslöser:** "wie gehts weiter?" → Vorschlag, die gerade reparierten LER/LWR-Ausgaben gegen
echte publizierte Messdaten zu prüfen. Nutzer: "ja, mach." Datenquelle: Vesters' Dissertation
(KU Leuven 2019, Table 4.2, bereits in Runde 6 katalogisiert) — echte Dosis-zu-Größe- und
LWR-Werte für 6 reale EUV-CAR-Resist-Formulierungen (A0/ALow/AHigh, B0/BLow/BHigh) bei 22nm
Halbraster (44nm Pitch) auf einem echten ASML-NXE3300-Scanner: Dosis 8–16 mJ/cm², LWR
6,5–10,3nm.

**Befund 1 — Dosis-Verschiebung (erklärbar, kein Alarmsignal):** Bei denselben Prozess-
bedingungen (44nm Pitch, 22nm Ziel-Linienbreite) entwickelt unser aktuelles "Polymer
A"-Modell (Yamamoto et al. 2011) bei Vesters' realen Dosen (8–16 mJ/cm²) **gar nicht**
(CD bleibt beim Periodenwert, komplett unentwickelt). Das auflösbare Fenster unseres Modells
liegt bei dieser Geometrie erst bei ~22–27 mJ/cm² — grob 40–70% höher als die realen,
dosisoptimierten Produktionsresists brauchen. Physikalisch gut erklärbar: "Polymer A" ist in
der Originalarbeit selbst ein Forschungs-/Prototyp-Resist (PHS-Derivat, Standard-
Schutzgruppen-Chemie), während Vesters' Resists gezielt über Quencher-Beladung auf niedrige
Dosis hin optimierte Produktionsformulierungen sind (genau das ist der Kern ihrer eigenen
Arbeit — "ALow"/"AHigh" als Dosis-vs-LWR-Tradeoff-Varianten).

**Befund 2 — LWR-Größenordnung (echte, quantifizierte Lücke):** Im eigenen auflösbaren
Dosisfenster (22–25 mJ/cm²) liefert unser Simulator LWR≈1,8–2,3nm — real gemessen sind es
6,5–10,3nm. **Unser Simulator unterschätzt reales LWR um Faktor ~3–5x.**
`development_stochasticity=True` (molekulare Auflösungsgranularität, siehe oben) schließt
diese Lücke nur marginal (2,44 statt 2,34nm bei Dosis 22) — die fehlende Rauschquelle liegt
also nicht primär dort.

**Ehrliche Einordnung der Lücke (nicht weiter verifizierte Arbeitshypothese, keine
bestätigte Erklärung):** Unser stochastischer Belichtungspfad (`photon_deposition_shot_noise`)
modelliert nur Photonen-Zählstatistik, nicht die nachgelagerte PAG-/Quencher-Molekülzahl-
Diskretheit (bei EUV eine bekannte, dominante zusätzliche Rauschquelle — siehe die in Runde 9
gefundene Literatur zu Sekundärelektronen-Kaskaden und Photonen-zu-Säure-Verstärkung). Zudem
enthält real gemessenes LWR typischerweise auch SEM-Messrauschen (Metrologie-Beitrag), das
eine reine Physik-Simulation naturgemäß nicht hat — ein Teil der 3-5x-Lücke könnte allein
daher stammen. Keines von beidem wurde in dieser Runde weiter untersucht oder bestätigt.

**Einordnung:** Das ist ein echter, sauber quantifizierter Befund — kein Fehlschlag, sondern
eine ehrliche Charakterisierung der aktuellen Grenzen des stochastischen Modells (fehlende
PAG/Quencher-Diskretheit im Belichtungsschritt, nicht im Entwicklungsschritt). Nicht in Code
umgesetzt (reine Validierungs-/Charakterisierungsarbeit, keine Änderung an Pipeline/Tests).

**Nächster möglicher Schritt, falls gewünscht:** die PAG-/Quencher-Molekülzahl-Diskretheit
tatsächlich in den Belichtungsschritt einbauen (analog zu `sample_species()`-artigen Modellen,
die Photonen→PAG→Säure als getrennte Poisson-/Binomial-Stufen behandeln, nicht nur Photonen-
Schrotrauschen) — würde die LWR-Lücke wahrscheinlich (nicht sicher) weiter schließen, ist aber
ein neuer, nicht-trivialer Architektur-Baustein, kein einfacher Parameter-Fix.

---

## 2026-09-03 (Fortsetzung 2): PAG-/Quencher-Molekülzahl-Diskretheit im Belichtungsschritt

**Auslöser:** "baue die PAG-/Quencher-Diskretheit in den Belichtungsschritt ein" — direkte
Umsetzung des oben skizzierten nächsten Schritts, um die 3-5x-LWR-Unterschätzung anzugehen.

**Neue Quelle:** Mack, Biafore & Smith 2011, "Stochastic Acid-Base Quenching Kinetics in
Chemically Amplified Photoresists," Proc. SPIE 7972, 797202 (frei via lithoguru.com) — NICHT
dieselbe Mack-2011-Arbeit wie die für `dill_Q` verwendete ("Stochastic exposure kinetics").
Table I liefert die drei zentralen neuen Konstanten: PAG-Dichte 0,2/nm³, Quencher-Dichte
0,05/nm³, Säure-Base-Quench-Rate 15 nm³/s.

**Neuer Code:**
- `resist/exposure.py`: `sample_pag_quencher_acid()` — sampelt `n_PAG ~ Poisson(rho_PAG·V_voxel)`
  (tatsächlich im Voxel anwesende Moleküle, nicht nur ihr Mittelwert), `n_acid ~
  Binomial(n_PAG, Q·(1-exp(-C·dose)))`, `n_Q ~ Poisson(rho_Q·V_voxel)` unabhängig. Beide
  Ausgaben normiert auf `rho_PAG` (Mack's h=H/G0, q=Q/G0-Konvention).
- `resist/peb.py`: `_reaction_limited_quench()` — geschlossene Lösung der bimolekularen
  Neutralisationskinetik dh/dt=dq/dt=-rate·h·q über die MINOR-Spezies (die, die auf 0
  getrieben wird), numerisch stabil über den unsigned Abstand `d=|h0-q0|` statt des
  vorzeichenbehafteten Deltas (vermeidet Exponential-Overflow im säure-limitierten Fall).
  `reaction_diffusion_with_quenching()` verkettet Reaktion + PEB-Diffusion + dieselbe
  Deprotektionskinetik wie der Mean-Field-Pfad.
- `pipeline.py`: neues `exposure_stochasticity: bool = False`-Flag (Default AUS) plus
  `pag_density_per_nm3`, `quencher_density_per_nm3`, `acid_base_quench_rate_nm3_per_s`
  (alle drei mit Table-I-Zitat). Im stochastischen Zweig von `_cd_via_full_chem`: bei
  `exposure_stochasticity=True` wird `dose_z` (Beer-Lambert-Tiefenprofil) berechnet, durch
  `sample_pag_quencher_acid` geschickt, dann durch `reaction_diffusion_with_quenching`, und
  fällt danach in dieselbe `surface_advancement_level_set`-Weiterverarbeitung wie der
  Mean-Field-Zweig.

**Zwei Bugs beim Aufbau gefunden und behoben (Unit-Ebene):**
1. `p_convert` in `sample_pag_quencher_acid` fehlte anfangs der `Q`-Faktor (war
   `1-exp(-C·dose)` statt `Q·(1-exp(-C·dose))`) — inkonsistent mit der Mean-Field-Konvention.
2. `_reaction_limited_quench` benutzte beim Rekonstruieren der Major-Spezies das
   VORZEICHENBEHAFTETE `delta` statt den unsigned Abstand `d` — im Quencher-Überschuss-Fall
   (q0>h0) ergab das `q_final=0` statt korrekt `q0-h0`. Gefangen durch 5 eigenständige
   Testfälle (Säure-Überschuss, Quencher-Überschuss, Entartungsfall h0=q0, t=0, vektorisierter
   Batch mit Nullen).

**Dritter, größerer Bug — gefunden erst über die volle Pipeline, nicht per Unit-Test:**
Mit beiden o.g. Fixes lief die Pipeline fehlerfrei durch, lieferte aber bei JEDER getesteten
Dosis (16–80 mJ/cm²) exakt LER=LWR=0,0 — trotz eines sauberen, dosisabhängigen CD (58nm bei
16mJ, 34,5nm bei 20mJ, 19,5nm bei 25mJ, 0 ab 30mJ). Ein exaktes `0,0` bei JEDER Dosis (nicht
nur ein kleiner Wert) deutete auf ein strukturelles Problem, nicht auf Unterkalibrierung.

Debugging per `monkey-patching` der echten Pipeline-Funktionsaufrufe (nicht per isoliertem
Nachbau-Skript, das sich vorher als irreführend erwiesen hatte — Lektion: bei Verdacht auf
einen Pipeline-Bug IMMER die echten Zwischenwerte aus dem laufenden `run_simulation()`
abgreifen, nie eine Nachbildung von Hand vertrauen):
- `dose_z` (Eingang) zeigte echte, plausible räumliche Variation (0,45–11,07, Mittel 4,65) —
  kein Bug dort.
- `A_out` (Säure NACH Quenching+Blur) lag bei Mittel 5,5e-8, Max 0,003 — praktisch überall
  Null. `M_out` (Inhibitor nach Deprotektion) lag bei 0,9866–1,0 — praktisch KEINE
  Deprotektion irgendwo. Das erklärte die flache `depth_map` = `mack_R_min·develop_time_s` =
  3,0nm überall (identisch zum früheren "uniform 3.0"-Befund aus dem isolierten
  Nachbau-Skript — der war also doch kein Artefakt, sondern real).

**Ursache:** `reaction_diffusion_with_quenching()` wendete die Reihenfolge Blur→Reaktion an
(erst über die volle PEB-Diffusionslänge ~20nm — bei den benutzten Gitterauflösungen mehrere
hundert Pixel Kernel-Radius über hunderte statistisch unabhängige Y-Tile-Zeilen gemittelt —
DANN die Neutralisationskinetik). Bei `quench_rate=15 nm³/s`, `t_bake=60s` läuft die Reaktion
für praktisch jeden Säureüberschuss ≥~0,001 (in den normierten Einheiten) bis zur vollständigen
Sättigung durch (`d·rate·t≫1`). Wird diese saturierende Reaktion auf ein bereits über ~100+
Voxel ENSEMBLE-GEMITTELTES Feld angewendet, reproduziert sie nur noch das (bei den
zitierten PAG/Quencher-Dichten nahe Null liegende) Ensemble-Mittel — genau das gesamplete
molekulare Rauschen, das diese Funktion einfangen sollte, ist zu diesem Zeitpunkt bereits
weggemittelt.

Physikalisch korrekt ist die umgekehrte Reihenfolge: "reaction-limited" Kinetik bedeutet per
Definition, dass die Reaktion schnell/lokal gegenüber der Diffusion ist — genau das
rechtfertigt erst die Behandlung als lokal durchmischte bimolekulare ODE auf Voxel-Skala. Sie
muss also auf den ROHEN, ungeblurrten Pro-Voxel-Zählwerten arbeiten (repräsentiert die
molekulare Diskretheit vor der PEB-Diffusion), und erst das REAKTIONSPRODUKT wird anschließend
über die PEB-Länge geblurrt (repräsentiert die Diffusion der nach der Neutralisation
verbliebenen Säure während der restlichen Backzeit).

Numerisch verifiziert an synthetischen Daten (H=1024, gleiche Parameter): Blur→Reaktion ergab
Mittel/Std = 3,7e-21/8,0e-21 (vollständig entartet); Reaktion→Blur ergab Mittel/Std =
0,029/7,2e-4 (echtes, nicht-entartetes Signal). Fix: Reihenfolge in
`reaction_diffusion_with_quenching()` getauscht (Reaktion zuerst, Diffusion danach),
Docstring entsprechend korrigiert.

**Ergebnis nach dem Fix** (`exposure_stochasticity=True` allein, `stochastic_ler_grid_y=4096`,
3 Realisierungen):

| Dosis [mJ/cm²] | CD [nm] | LER [nm] | LWR [nm] |
|---|---|---|---|
| 16 | 58,0 | 0,49 | 0,98 |
| 20 | 34,5 | 0,87 | 1,65 |
| 25 | 19,5 | 0,76 | 1,40 |

Echte, nicht-entartete, dosisabhängige Werte — das Feature funktioniert jetzt für sich
genommen. Zum Vergleich bei 16mJ/cm² lieferte `development_stochasticity=True` allein (der
bereits vorhandene Mechanismus) LWR=3,24nm — größenordnungsmäßig näher an Vesters echten
6,5–10,3nm als `exposure_stochasticity` allein (0,98nm).

**Offener Befund — NICHT gelöst, ehrlich stehen gelassen:** beide Mechanismen KOMBINIERT
(`development_stochasticity=True` UND `exposure_stochasticity=True`) ergaben bei 16mJ/cm²
LWR=0,22nm — WENIGER als `development_stochasticity` allein (3,24nm), obwohl zwei zusätzliche,
unabhängige Rauschquellen naiv eine Zunahme (Addition in Quadratur) erwarten ließen. Ursache
noch nicht identifiziert; Arbeitshypothese: `development_strength=20,0` wurde ausschließlich
für die Overshoot-Skala des Mean-Field-Belichtungspfads empirisch kalibriert (siehe Eintrag
oben), und das `depth_map_noisy`-Feld aus dem `exposure_stochasticity`-Zweig hat vermutlich
eine strukturell andere Overshoot-Verteilung (near-threshold statt breiter Streuung), wodurch
dieselbe `development_strength` den Kantenübergang eher glättet als verrauscht. Nicht weiter
untersucht in dieser Runde — bewusste Entscheidung, den Kern-Bugfix (Blur-Reihenfolge) zuerst
zu sichern, bevor in eine zweite, separate Kalibrierungsrunde investiert wird.

**Getestet:** `test_full_chem_config.py` (7 grün), `test_development_stochasticity.py`
(19 grün), `test_stochastic_pipeline.py` (5 grün) — alle unverändert grün, da
`exposure_stochasticity` standardmäßig aus ist und der geänderte Code (`reaction_diffusion_
with_quenching`) nur in diesem neuen, per Default inaktiven Zweig aufgerufen wird. Keine
golden-value-Anpassungen nötig.

**Noch offen:** die o.g. Kombinations-Kalibrierung; ein direkter Vesters-Vergleich mit
`exposure_stochasticity=True` (mit oder ohne `development_stochasticity`) im echten
8–16mJ/cm²-Dosisfenster (bislang nur bei 16mJ getestet, da das Modell bei niedrigeren Dosen
weiterhin gar nicht entwickelt, siehe Befund 1 oben); Commit dieser Änderungen steht noch aus.

---

## 2026-09-04: Kombinations-Kalibrierung untersucht — Befund: keine Fehlkalibrierung, sondern echte Architektur-Wechselwirkung

**Auslöser:** "ja, geh der Kalibrierung nach" — Untersuchung des oben offen gelassenen Befunds,
dass `development_stochasticity` + `exposure_stochasticity` kombiniert bei 16mJ/cm² WENIGER
LWR ergibt (0,22nm) als `development_stochasticity` allein (3,24nm).

**Root-Cause-Analyse** (über echte Pipeline-Zwischenwerte, `surface_advancement_level_set`
abgegriffen, `stochastic_ler_grid_y=1024`, 1 Realisierung, dose=16): `stochastic_development()`
berechnet `drive = max(0, (depth_map_noisy - resist_thickness_nm) / resist_thickness_nm)` und
zieht daraus Poisson-Ereignisse mit Rate `strength·drive`. Der Vergleich der beiden Modi:

| | `exposure_stochasticity=False` | `exposure_stochasticity=True` |
|---|---|---|
| depth_map Mittel/Std [nm] | 18,4 / 18,0 | 13,7 / 13,0 |
| drive Mittel | 0,00465 | 0,000107 (**43x kleiner**) |
| Anteil Pixel mit drive>0 | 11,0% | 0,54% (**20x kleiner**) |

`exposure_stochasticity` verschiebt die `depth_map_noisy`-Verteilung strukturell nach unten:
weniger Pixel erreichen überhaupt eine nennenswerte Überschreitung von `resist_thickness_nm`
(volle Klärung). Das ist eine direkte Folge desselben Quencher-Schwellen-Mechanismus, der
`exposure_stochasticity` selbst erst funktionsfähig macht (Eintrag oben) — ein Großteil des
Resists sitzt nahe der Quencher-Baseline und liefert nur knapp genug übrige Säure, um überhaupt
zu entwickeln, mit entsprechend wenig Überschuss darüber hinaus. `development_stochasticity`s
`drive`-Mechanismus braucht aber genau diesen Überschuss als "Treibstoff" — mit
`exposure_stochasticity` aktiv bleibt davon strukturell weniger übrig, unabhängig von
`development_strength`.

**Sweep-Test, um zu prüfen ob reines Hochskalieren von `development_strength` das kompensiert**
(kombiniert, dose=16, 3 Realisierungen, `stochastic_ler_grid_y=4096`):

| strength | LWR kombiniert [nm] | LWR nur `development_stochasticity` [nm] |
|---|---|---|
| 20 (aktueller Default) | 0,22 | 3,24 |
| 100 | 0,93 | 3,52 |
| 200 | **1,22 (Maximum)** | 3,54 |
| 400 | 0,88 | — |
| 800 | 0,90 | — |
| 1600 | 0,69 | — |

Zwei Befunde:
1. Der kombinierte Modus hat ein **nicht-monotones Maximum bei strength≈200** (1,22nm) — bei
   noch höherer Stärke sättigt der Poisson-Rate-Mechanismus gegen deterministische
   Schwellenentwicklung (dokumentiertes Verhalten von `stochastic_development`: "in the limit
   strength -> infinity the model reduces to the deterministic threshold development", also
   wieder WENIGER Rauschen), das Optimum liegt dazwischen.
2. **Selbst am eigenen Optimum (1,22nm) bleibt der kombinierte Modus deutlich unter
   `development_stochasticity` allein (3,24–3,54nm, selbst stabil über strength=20–200).**
   Kein getesteter `development_strength`-Wert bringt die Kombination auch nur in die Nähe von
   `development_stochasticity` allein, geschweige denn darüber hinaus.

**Schlussfolgerung:** Dies ist **keine Fehlkalibrierung, die sich durch einen anderen
`development_strength`-Wert beheben lässt**, sondern eine echte, strukturelle Wechselwirkung:
`exposure_stochasticity`s Quencher-Schwelle und `development_stochasticity`s
Depth-Overshoot-`drive`-Mechanismus konkurrieren um dieselbe "Überschuss-Marge" im Resist,
und Ersteres verbraucht/reduziert sie strukturell, bevor Letzteres sie nutzen kann. Die beiden
Mechanismen sind **nicht additiv unabhängig**, wie ursprünglich (naiv) angenommen.

**Entscheidung:** `development_strength`-Default (20,0) bleibt **unverändert** — er ist korrekt
für den bereits validierten `development_stochasticity`-allein-Pfad kalibriert (Phase 5,
golden values), und ein anderer Wert würde nur für die Kombination optimieren, ohne diese
über das bessere Einzelmechanismus-Ergebnis zu heben — das wäre ungerechtfertigtes Tuning
ohne echten Nutzen. **Empfehlung für Nutzer dieses Modells:** aktuell `development_stochasticity`
ODER `exposure_stochasticity` einzeln verwenden (beide Default aus), nicht kombiniert — die
Kombination liefert derzeit kein besseres Ergebnis als der bessere der beiden Einzelmechanismen.
Eine echte Vereinheitlichung (z.B. `drive` direkt aus dem Säure-Quencher-Überschuss statt aus
dem Tiefen-Overshoot ableiten) wäre ein größerer Architektur-Umbau, hier nicht umgesetzt (nicht
angefragt, keine ausreichende Datenbasis für eine neue Formel ohne weitere Kalibrierungsdaten).

**Verbleibende Vesters-Lücke:** unverändert real — der beste bisher gefundene Einzelmechanismus
(`development_stochasticity` allein) liefert bei 16mJ/cm² LWR≈3,2–3,5nm gegen real gemessene
6,5–10,3nm, also weiterhin ein Faktor ~2–3x zu klein. `exposure_stochasticity` allein liegt mit
≈0,98nm bei derselben Dosis noch weiter darunter. Kein Code geändert in dieser Runde (reine
Charakterisierungs-/Kalibrierungsuntersuchung, keine Bugs gefunden).

---

## 2026-09-04 (Fortsetzung): LWR-Ursache systematisch isoliert — KORREKTUR des vorigen Befunds

**Auslöser:** "1. LWR-Ursache systematisch isolieren" — Ablationsstudie, um die verbleibende
Vesters-Lücke auf ihre einzelnen Rauschquellen zurückzuführen.

**Methodik-Fehler zuerst gefunden und korrigiert:** die eben abgeschlossene Kombinations-
Kalibrierungsuntersuchung (voriger Eintrag) lief bei `period_nm=64` (Software-Default), NICHT
bei Vesters' echter Geometrie (`period_nm=44, line_width_nm=22`, siehe Validierungseintrag
weiter oben). Das ist dieselbe Geometrie-Inkonsistenz, die auch schon den ursprünglichen
"Faktor 3-5x"-Befund erschwert. Die gesamte Ablationsstudie wurde daher bei der KORREKTEN
Vesters-Geometrie wiederholt.

**Ablation bei `period_nm=64` (falsche Geometrie, zur Einordnung, dose=16, CD=58nm):**

| Konfiguration | LWR [nm] |
|---|---|
| A: nur Photon-Schrotrauschen | 3,17 |
| B: + development_stochasticity | 3,24 (+2%) |
| C: + exposure_stochasticity | 0,98 (**-69%**) |
| D: beide kombiniert | 0,22 (**-93%**) |

Bei dieser (falschen) Geometrie dominiert Photon-Schrotrauschen fast vollständig, und
`exposure_stochasticity` UNTERDRÜCKT es (Kontrastverschärfungs-Artefakt, siehe unten).

**Ablation bei `period_nm=44, line_width_nm=22` (korrekte Vesters-Geometrie), drei
verschiedene Dosen/CDs, `stochastic_n_realisations=3`, `se_blur_nm=5,0` konsistent:**

| Dosis [mJ/cm²] | CD [nm] | A: Photon | B: +dev.stoch | C: +exp.stoch | D: beide |
|---|---|---|---|---|---|
| 22 | 30,25 | 2,38 | 2,84 | 4,24 | 3,69 |
| 24 | 17,19 | 1,61 | 1,80 | 5,28 | 5,17 |
| 25 | 10,31 | 2,39 | 2,26 | 4,93 | 4,83 |

**Genau umgekehrtes Bild** gegenüber `period_nm=64`: bei der tatsächlich relevanten Geometrie
VERSTÄRKT `exposure_stochasticity` das LWR deutlich (C/D durchweg 2-3x über A/B), statt es zu
unterdrücken. Der Effekt ist über drei unterschiedliche Dosen/CDs (30, 17, 10nm) konsistent,
kein Zufallstreffer an einem einzelnen Punkt.

**KORREKTUR des vorigen Eintrags:** die dort dokumentierte Schlussfolgerung
("development_stochasticity + exposure_stochasticity kombiniert ist strikt schlechter als
development_stochasticity allein, über den ganzen getesteten strength-Bereich") gilt NUR bei
`period_nm=64` und ist NICHT allgemeingültig — bei der für den Vesters-Vergleich tatsächlich
relevanten Geometrie (44nm Pitch, CD nahe 22nm) ist es GENAU UMGEKEHRT: die Kombination (D)
schneidet deutlich besser ab als jeder Einzelmechanismus. Die Empfehlung "einzeln statt
kombiniert verwenden" aus dem vorigen Eintrag wird hiermit zurückgezogen — sie war an eine
nicht-repräsentative Testgeometrie gebunden, nicht an eine universelle Modelleigenschaft.

**Aktualisierte Vesters-Lücke** (bei CD nahe dem Zielwert 22nm, Dosis 24mJ/cm², beide
Mechanismen kombiniert): LWR=5,17nm gegen real gemessene 6,5–10,3nm — **Faktor nur noch
~1,25–2x, nicht mehr 3–5x wie zuvor berichtet.** Die Lücke ist damit deutlich kleiner als in
der ursprünglichen Validierung (bdea3b6) und im vorigen Eintrag angenommen — beide beruhten
auf einem Vergleichspunkt ohne `exposure_stochasticity` bzw. auf der falschen Geometrie.

**Separater, wichtiger Befund — extreme Parameterempfindlichkeit nahe CD≈18-24nm:** beim
Aufbau dieser Ablation wurde zunächst ein scheinbarer Bug gefunden (`enable_stochastic=True`
änderte den DETERMINISTISCHEN `cd_nm`-Wert, obwohl der RNG-unabhängig sein sollte: 23,7nm vs.
18,6nm bei identischer Dosis). Durch Vergleich der Zwischenwerte (`aerial`-Eingabe bitidentisch,
aber `acid_3d` bereits verschieden) wurde die Ursache gefunden: ein Fehler im eigenen Testskript
(`se_blur_nm` war zwischen den beiden Vergleichsläufen inkonsistent — 0,0 vs. 5,0 — nicht als
Absicht, sondern vergessen). Mit konsistentem `se_blur_nm` verschwindet die Diskrepanz
vollständig; **kein echter Pipeline-Bug.** Der Vorfall deckt aber auf: bei diesem CD-Bereich
(nahe Vesters' Zielwert 22nm) reagiert das Modell EXTREM empfindlich auf kleine
Parameteränderungen — allein der (unzitierte) `se_blur_nm`-Wert verschiebt CD hier um >5nm, und
eine Dosisänderung von nur 0,1mJ/cm² (23,9→24,0) verschiebt CD um >6nm (siehe feine Dosis-
Sweep-Werte oben). Plausible Ursache: `mack_n=18,2` ("notably steeper than textbook", bereits
im Code als Ausreißer geflaggt) macht die CD-vs-Dosis-Kurve in diesem Resistmodell nahezu
stufenförmig. Das bedeutet: JEDE einzelne LWR-Zahl in dieser und der vorigen Validierungsrunde
ist nur an genau dem getesteten (Dosis-, Blur-, Geometrie-)Punkt aussagekräftig — kleine
Konfigurationsabweichungen können CD und damit LWR stark verschieben. Keine Korrektur an
`mack_n` vorgenommen (real zitierter Yamamoto-et-al.-2011-Wert, nicht willkürlich) — als
Interpretationsvorbehalt für alle bisherigen und künftigen full_chem-Zahlen festgehalten, nicht
als Fehler behoben.

**Verbleibend offen:** ob die verbleibende Faktor-1,25-2x-Lücke durch SEM-Metrologie-Rauschen
(in echten Messungen enthalten, in reiner Physik-Simulation nicht), durch weitere, noch nicht
modellierte Rauschquellen, oder durch die o.g. Parameterempfindlichkeit selbst (evtl. optimistisch
getroffener Vergleichspunkt) erklärt wird, ist nicht untersucht. Kein Code geändert in dieser
Runde (reine Charakterisierung); nur Dokumentation aktualisiert.

---

## 2026-09-04 (Fortsetzung 2): SEM-Metrologie-Hypothese verifiziert — Vesters' Table 4.2 ist NACHWEISLICH SEM-rauschbehaftet

**Auslöser:** "ja, geh der SEM-Metrologie-Hypothese nach" — Überprüfung, ob die verbleibende
Faktor-1,25-2x-LWR-Lücke (voriger Eintrag) dadurch erklärt wird, dass unsere reine
Physik-Simulation (kein SEM-Messrauschen) gegen SEM-Messwerte verglichen wird, die selbst
Messrauschen enthalten.

**Primärquelle direkt geprüft:** `Vesters_2019_PhD_Thesis_KULeuven.pdf` liegt lokal vor
(`/Users/flo/mack fits/pdfs/`), als Volltext extrahiert und durchsucht.

**Zentraler Fund — Abschnitt 1.8.2 "Scanning Electron Microscopy" (S. 59-62) der Thesis,
wörtlich:** CD-SEM-Detektoren erzeugen ein "white noise signal... even for a perfectly flat
surface". Dieses Rauschen kann durch PSD-Analyse als "background noise" identifiziert und
abgezogen werden, was einen sogenannten **"unbiased"** LER/LWR-Wert liefert, der SYSTEMATISCH
NIEDRIGER ist als der rohe ("biased") SEM-Messwert. Wörtliches Zitat der Thesis: **"the
roughness results from the start of the thesis (Chap. 3 and Chap. 4) are presenting only
biased measurements, while for data obtained later (Chap. 5 and Chap. 7) unbiased
measurements were possible."**

**Table 4.2 — unsere gesamte Vergleichsreferenz (LWR 6,5-10,3nm) — liegt in Kapitel 4** und ist
laut diesem wörtlichen Zitat der Thesis selbst **explizit NUR als "biased" (SEM-rauschbehaftet)
gemessen worden.** Die Tabellenüberschrift selbst bestätigt das: "LWR values as measured by
CD-SEM" (S. 103), ohne jede Unbiasing-Korrektur — zum Zeitpunkt von Kapitel 3/4 existierte die
dafür nötige Software (Fractilia metroLER) am imec noch nicht in der Autorin eigenen Aussage.

**Größenordnung des reinen Metrologie-Rauschbeitrags (Thesis, Fig. 1.62, S. 61):** bei
IDENTISCHEM SEM-Bild variiert der gemessene LWR-Wert allein durch die Wahl der
Filterbox-Größe des Kantenerkennungs-Algorithmus zwischen **3,4nm und 11,2nm** — ein Faktor
3,3x, ausschließlich durch Metrologie-Einstellungen, NICHT durch reale Resist-Rauheit
verursacht (Quelle dort: Mack & Bunday 2017, SPIE, DOI 10.1117/12.2258631). Das zeigt: ein
"biased" CD-SEM-LWR-Wert kann NICHT direkt als physikalische Wahrheit interpretiert werden.

**Näherungsweise Kalibrierung der "unbiased" Größenordnung für vergleichbare EUV-CAR-Resists**
(aus DERSELBEN Thesis, Kapitel 5, wo Fractilia-Unbiasing bereits verfügbar war — andere
Resist-Serie [MTR statt Sensitizer A/B], aber gleiche Messmethodik/gleicher Autor/gleiches
Labor, daher der bestverfügbare Vergleichsmaßstab):

| Sample/Bedingung | unbiased LWR [nm] |
|---|---|
| MTR2204, 16nm HP | 3,7 (LER, nicht LWR) |
| MTR2204, 20nm HP, 34nm FT, 44,5mJ/cm² | 2,9 |
| MTR2200, 20nm HP, 33nm FT, 28mJ/cm² | 3,2 |

Diese unbiased-Werte liegen bei **2,9-3,2nm für vergleichbare 20nm-HP-Strukturen** — DEUTLICH
NÄHER an unserem simulierten, rein physikalischen LWR (5,17nm bei CD≈17-23nm, voriger
Eintrag) als an Vesters' eigenen BIASED Table-4.2-Werten (6,5-10,3nm). Kein exakter
Same-Sample-Biased/Unbiased-Vergleich für die Table-4.2-Proben selbst verfügbar (die Thesis
sagt ausdrücklich, dass diese Proben nie unbiased nachgemessen wurden) — daher bleibt dies
eine PLAUSIBILISIERUNG per Analogie, keine exakte Korrektur.

**Ergänzende Quelle (Severi et al. 2022, "Chemically amplified resist CDSEM metrology
exploration for high NA EUV lithography," J. Micro/Nanopattern. 21(2), 021207, lokal
vorliegend):** bestätigt unabhängig, dass unbiased-LWR-Bestimmung SNR-abhängig und bei
niedrigem Signal-Rausch-Verhältnis unzuverlässig ist, und dass rohe (biased) CD-SEM-Werte
generell NICHT direkt mit physikalischer Resist-Rauheit gleichgesetzt werden können.

**Schlussfolgerung:** Die SEM-Metrologie-Hypothese ist NICHT nur plausibel, sondern durch die
Primärquelle selbst BESTÄTIGT: unser Vergleichsmaßstab (Table 4.2) enthält nachweislich
SEM-Rauschen, das unsere reine Physik-Simulation naturgemäß nicht hat. Der Vergleich
"5,17nm simuliert vs. 6,5-10,3nm real gemessen" war von Anfang an (seit der ursprünglichen
Validierung bdea3b6) ein Äpfel-Birnen-Vergleich (unbiased-Simulation gegen biased-Messung).
Bei einem fairen Vergleich gegen unbiased-Referenzwerte für vergleichbare EUV-CAR-Resists
(2,9-3,2nm bei ähnlicher Feature-Größe, aus derselben Thesis) liegt unsere Simulation (5,17nm)
sogar EHER ÜBER dem, was man von echter physikalischer Rauheit erwarten würde — die
verbleibende "Lücke" könnte also GAR KEINE fehlende Physik in unserem Modell sein, sondern
größtenteils oder vollständig ein Artefakt des Vergleichs gegen die falsche (rauschbehaftete)
Referenzgröße.

**Wichtiger Vorbehalt:** dies ist eine Plausibilisierung per Analogie (andere Resist-Serie,
gleiche Thesis/Methodik), KEINE exakte quantitative Korrektur für die Table-4.2-Proben selbst
— eine solche existiert laut der Thesis nicht, da diese Proben nie unbiased nachgemessen
wurden. Die tatsächliche SEM-Rauschkomponente für die SPEZIFISCHEN Sensitizer-A/B-Proben bei
44nm Pitch/16mJ könnte kleiner oder größer sein als die hier als Analogie herangezogenen
MTR-Werte (andere Resist-Chemie, andere Pitch/Dosis-Kombination). Keine weitere Verifikation
in dieser Runde möglich (kein Zugriff auf Rohdaten/PSD-Kurven der Table-4.2-Messungen).

**Empfehlung:** die "Faktor 2-3x zu klein"-Charakterisierung aus der ursprünglichen Validierung
(bdea3b6) sollte NICHT mehr als offene, ungeklärte Modell-Schwäche behandelt werden, sondern
als wahrscheinlich größtenteils durch einen Referenz-Metrik-Fehler (biased statt unbiased
Vergleichsdaten) erklärt. Ein sauberer nächster Schritt (falls gewünscht) wäre, gezielt nach
UNBIASED LWR-Referenzdaten bei genau 44nm Pitch/22nm HP zu suchen (z.B. weitere imec/SPIE-
Veröffentlichungen mit Fractilia-metroLER-Angaben bei dieser Geometrie), statt Table 4.2
direkt weiterzuverwenden. Kein Code geändert in dieser Runde (reine Literaturrecherche/
Charakterisierung).

---

## 2026-09-04 (Fortsetzung 3): KRITISCHE KORREKTUR — 3σ-vs-1σ-Konventionsfehler kehrt die gesamte Vesters-Schlussfolgerung um

**Auslöser:** "ja suche" — weitere Suche nach exakteren unbiased-Referenzdaten für die
SEM-Metrologie-Hypothese (voriger Eintrag). Bei dieser Suche (u.a. im Paper "E-beam metrology
and line local critical dimension uniformity", pitch 24-32nm, unbiased LWR 3σ dort im Bereich
2,6-4,0nm) fiel auf, dass DORT die Achsenbeschriftung explizit "Unbiased LWR 3σ (nm)" lautet —
was den Verdacht auslöste, dass auch Vesters' Table 4.2 eine 3σ-Konvention verwenden könnte,
die bisher nicht mit unserer eigenen Simulator-Konvention abgeglichen wurde.

**Verifiziert, mit Zitat:** Vesters' Thesis, Abschnitt 1.5 (S. 33), definiert LER/LWR EXPLIZIT
und mit Formel als 3σ-Größen: *"line edge roughness (LER) and line width roughness (LWR).
These are expressed as the 3\*sigma variation..."*, mit der expliziten Formel
`LWR = 3σ_w = 3·√(Σ(wᵢ-w̄)²/N)` (Gl. 1.4, S. 33). Das ist die Standard-Halbleiterindustrie-
Konvention (3σ ≈ 99,7%-Bandbreite), NICHT willkürlich.

**Eigener Code verifiziert:** `extract_lwr()` in
[stochastic.py:884](../src/euvsimulator/resist/stochastic.py) gibt wörtlich
`float(torch.std(width_finite, unbiased=False))` zurück — die REINE Standardabweichung
(1σ), OHNE jeden Faktor 3. Durchgängig im Code selbst als "(1σ)" dokumentiert
(`pipeline.py:73/75`, `stochastic.py:29/31/553/866`) — unser Code ist intern
KONSISTENT und korrekt dokumentiert, aber diese 1σ-Konvention wurde in KEINEM der bisherigen
Vesters-Vergleiche (weder in der ursprünglichen Validierung bdea3b6 noch in den beiden
vorigen Einträgen von heute) gegen Vesters' 3σ-Konvention umgerechnet — beide Seiten wurden
die ganze Zeit direkt, unkorrigiert nebeneinandergestellt.

**Korrigierte Rechnung** (Vesters Table 4.2, 3σ → 1σ durch Division durch 3):

| Sample | 3σ (Vesters, roh) | 1σ (korrekt umgerechnet) |
|---|---|---|
| A0 | 7,4 | 2,47 |
| ALow | 6,5 | 2,17 |
| AHigh | 9,2 | 3,07 |
| B0 | 6,7 | 2,23 |
| BLow | 9,4 | 3,13 |
| BHigh | 10,3 | 3,43 |

**1σ-Bereich (korrekt umgerechnet, weiterhin biased/SEM-rauschbehaftet): 2,17–3,43nm.**

**Vergleich mit unserem simulierten LWR (bereits 1σ, kombinierter Mechanismus, Vesters-
Geometrie, aus dem Ablations-Eintrag von heute):**

| Dosis/CD | simuliert (1σ) | Verhältnis zu 2,17–3,43nm (1σ, biased) |
|---|---|---|
| dose=22, CD=30nm | 3,69nm | **1,07–1,70x zu hoch** |
| dose=24, CD=17nm | 5,17nm | **1,51–2,39x zu hoch** |
| dose=25, CD=10nm | 4,83nm | **1,41–2,23x zu hoch** |

**Das kehrt die Schlussfolgerung der letzten drei Einträge (und der ursprünglichen Validierung
bdea3b6) VOLLSTÄNDIG um:** statt "unser Modell unterschätzt LWR um Faktor 1,25–2x" ist es bei
korrekter Sigma-Konvention **"unser Modell überschätzt LWR um Faktor ~1,1–2,4x gegenüber den
biased (SEM-rauschbehafteten) Messwerten"** — und da biased-Werte SYSTEMATISCH HÖHER als die
wahre physikalische Rauheit liegen (SEM-Rauschen addiert sich, siehe voriger Eintrag zur
SEM-Metrologie-Hypothese), wäre die Überschätzung gegenüber der WAHREN physikalischen Rauheit
(unbiased) sogar noch GRÖSSER, nicht kleiner. Die beiden Korrekturen (SEM-Rauschen entfernen,
3σ→1σ umrechnen) wirken in dieser Kombination also in DIESELBE Richtung, nicht gegeneinander.

**Wichtige Einordnung, was das NICHT bedeutet:** dies bedeutet NICHT, dass die Photon-Schrot-
rauschen-Physik oder die PAG/Quencher-Diskretheit-Implementierung selbst fehlerhaft sind (beide
wurden unabhängig als real und nicht-degeneriert verifiziert, siehe die entsprechenden
Bugfix-Einträge). Es bedeutet, dass der QUANTITATIVE Zielwert, gegen den diese Mechanismen
in den letzten Tagen bewertet wurden, systematisch falsch war (3x zu hoch angesetzt). Die
`development_strength=20,0`-Kalibrierung selbst war davon NICHT betroffen — sie wurde
ursprünglich nur gegen "produziert überhaupt ein nicht-degeneriertes Ergebnis" kalibriert,
nicht gegen einen spezifischen Vesters-Zielwert (siehe der entsprechende Eintrag oben), ist
also nicht direkt durch diesen Fehler verzerrt worden — aber jede quantitative Aussage darüber,
"wie nah" das Modell an der Realität ist, muss neu bewertet werden.

**Verbleibend offen / nächste Schritte (nicht in dieser Runde umgesetzt):**
1. Systematische Prüfung, ob DIESELBE 3σ/1σ-Verwechslung auch in anderen Teilen des Projekts
   vorliegt (z.B. `nils`/NILS-Vergleiche, andere Zitate in `pipeline.py`-Kommentaren, die
   Literaturwerte referenzieren, ohne deren Sigma-Konvention zu prüfen).
2. Bei Bedarf: `development_strength` und ggf. `se_blur_nm`/`pag_density_per_nm3`/
   `quencher_density_per_nm3` neu kalibrieren, DIESMAL gegen den korrekt umgerechneten
   1σ-Zielbereich (2,17–3,43nm biased, vermutlich noch niedriger unbiased) statt den
   ursprünglichen (falschen) 3σ-Rohwerten.
3. `docs/claude_code_arbeitslog.md`s frühere Einträge (insbesondere die ursprüngliche
   bdea3b6-Validierung und die letzten zwei Einträge von heute) NICHT gelöscht, sondern
   bewusst stehengelassen als Teil der ehrlichen Fehlerhistorie — dieser Eintrag ist die
   maßgebliche Korrektur.

Kein Code geändert in dieser Runde (reine Verifikations-/Dokumentationsarbeit). Dies ist der
wichtigste Einzelbefund der gesamten Vesters-Validierungsserie und sollte vor jeder weiteren
quantitativen Aussage über die LWR-Modellgüte berücksichtigt werden.

---

## 2026-09-04 (Fortsetzung 4): systematische Prüfung auf denselben 3σ/1σ-Fehler + development_strength-Rekalibrierung

**Auslöser 1:** "prüf den Rest auf denselben Fehler" — systematische Suche im gesamten `src/`-
Baum nach weiteren Stellen, die einen externen Literatur-LER/LWR-Wert ohne Sigma-Konventions-
Prüfung zitieren.

**Ergebnis:** genau EINE weitere Fundstelle, `pipeline.py`s `exposure_stochasticity`-
Motivationskommentar (zitierte Vesters' 6,5-10,3nm als unkonvertierten Zielwert). Korrigiert
(Commit 774fde4): Kommentar verweist jetzt auf die korrigierten Zahlen und den vorigen
Arbeitslog-Eintrag, statt die (jetzt widerlegte) "unterschätzt"-Aussage als Fakt stehen zu
lassen. Geprüft und als NICHT betroffen ausgeschlossen: Test-Golden-Values (Selbstkonsistenz-
Schnappschüsse über Commits hinweg, kein externer Vergleich), CDU/LCDU (kommt im Code nirgends
vor), der interne `stochastic_ler_grid_y`-Referenzwert (`N_eff≈59, LER≈0,07nm bei 40mJ/cm²`,
reiner Selbstvergleich ohne externe Quelle), der Forschungskatalog unter `/Users/flo/mack
fits/` (Hintergrundnotizen, in keinen Simulator-Default eingeflossen), und `development_
strength=20,0` selbst (war nie gegen einen Vesters-Zahlenwert kalibriert, sondern nur gegen
"produziert überhaupt ein nicht-degeneriertes Ergebnis").

**Auslöser 2:** "development_strength gegen den korrigierten 1σ-Zielbereich neu kalibrieren" —
da `development_strength` NIE gegen einen echten externen Zielwert kalibriert war (siehe oben),
jetzt erstmals eine echte Kalibrierung gegen den korrigierten 1σ-Zielbereich (~2,2-3,4nm,
Vesters' Table 4.2 bei 44nm Pitch/22nm HP, korrekt von 3σ auf 1σ umgerechnet).

**Sweep** (`development_stochasticity=True`, `exposure_stochasticity=False`, korrekte Vesters-
Geometrie, drei Dosen × vier Seeds):

| strength | dose=22 [nm] | dose=24 [nm] | dose=25 [nm] |
|---|---|---|---|
| 5 | 0,00 | 0,00 | 0,00 |
| 10 | 2,09 | 2,43 | 2,30 |
| 12 | 3,97 | 7,20 | 8,45 (instabiler Übergang, siehe unten) |
| 14 | 2,73 | 3,70 | 5,06 |
| **15** | **2,47** | **2,28** | **3,02** |
| 16 | 2,34 | 1,88 | 2,43 |
| 18 | 2,40 | 1,83 | 2,36 |
| 20 (alter Default) | 2,84 | 1,80 | 2,26 |
| 30 | 2,98 | 1,94 | 2,12 |
| 40 | 2,51 | 1,91 | 2,22 |

`strength=15` trifft den Zielbereich [2,17; 3,43] an allen drei Dosen (Mittel über 4 Seeds:
2,47/2,28/3,02nm) — konsistenter als der alte Default 20,0, der bei dose=24 knapp
unterschreitet (1,80nm). Bei `strength≈12` zeigt sich ein scharfer, instabiler Übergang
(LWR springt auf 4-8,4nm) — dieselbe, bereits an anderer Stelle dokumentierte numerische
Empfindlichkeit durch `mack_n=18,2`s Steilheit, kein neuer Fund. `strength=15` liegt
komfortabel jenseits dieser Kante.

**Fix:** `development_strength`-Default von 20,0 auf **15,0** geändert (Commit 76c27e0),
Kommentar entsprechend erweitert (Historie beider Kalibrierungsrunden dokumentiert, nicht
überschrieben).

**Getestet** (ressourcenschonend, einzeln): `test_development_stochasticity.py` (19 grün),
`test_full_chem_config.py` + `test_stochastic_pipeline.py` (12 grün),
`test_ler_production_integration.py` (32 grün) — alle unverändert grün, KEINE
Golden-Value-Anpassung nötig, da keiner der gepinnten Werte den strength-sensitiven Pfad bei
einem verschobenen Wert prüft.

**Weiterhin nicht literaturzitiert** (bewusst, wie schon beim alten Wert): `development_
strength` bleibt ein numerischer Raten-Regler, keine physikalische Resist-Eigenschaft — jetzt
aber gegen einen korrekt umgerechneten externen Zielwert geprüft statt nur gegen "produziert
überhaupt ein Ergebnis".

---

## 2026-09-04 (Fortsetzung 5): Wissenschaftliches Entwicklungsmandat — Phase 3, drei Prüfungen

**Auslöser:** Nutzer erteilt ein umfassendes "Master-Prompt"-Mandat (siehe volle Anweisung in
der Session), das eine sehr strenge wissenschaftliche/softwaretechnische Weiterentwicklung von
euvsimulator fordert: keine Parameteranpassung, um Testwerte zu treffen; strikte Trennung von
Kalibrierung und Validierung; jede physikalische Annahme muss dokumentiert und, wo möglich,
gegen Primärquellen verifiziert werden. Phase 1 (Zustandsreproduktion) und Phase 2 (sichere
mechanische Fixes: `euv`→`euvsimulator`-Altlasten, alle 6 Notebooks repariert, `ler_estimate`-
Robustheitsfix) sind in separaten Commits dokumentiert (`144a803`, `56e2ca0`, `b40ae8f`,
`4749088`). Dieser Eintrag deckt Phase 3 (wissenschaftliche Prüfungen) ab.

### Prüfung 1: `mack_n=18,2` gegen Primärquelle — siehe Commit `f2292e8` für den vollen,
im Code selbst dokumentierten Befund. Kurzfassung: Yamamoto et al. 2011 direkt von J-STAGE
erneut geladen und selbst gelesen (nicht nur dem Katalog-Eintrag vertraut), Tabelle 2 (S. 409)
bestätigt n=18,2 exakt. Eigene `MackModel`-Formel verifiziert identisch zur klassischen
Mack-Konvention. Berechnet: `a=(n+1)/(n-1)*(1-Mth)^n = 1,38e-4` — extrem klein, was den
10%→90%-Übergang von R(M) auf nur ΔM≈0,14 komprimiert. Das ist die mathematisch zwingende,
korrekte Ursache der seit Tagen beobachteten extremen CD-Empfindlichkeit — kein Bug, keine
Fehlübertragung. PDF jetzt lokal archiviert (`/Users/flo/mack fits/pdfs/`, vorher nur als
URL referenziert).

### Prüfung 2: Multilayer-Parameter-Quellenlage — siehe Commit `f2292e8`. Bilayer-Periode
(6,9nm) via Bragg-Bedingung verifiziert (6,787nm Vakuum-Näherung, 1,66% Abweichung, konsistent
mit erwarteter Brechzahlkorrektur). Mo/Si-Aufteilung, Bilagenzahl (50), Ru-Capping-Dicke:
KEINE spezifische Primärquelle gefunden oder verifiziert (Websuche fand nur ähnliche Werte in
nicht zurückverfolgten Papers/Patenten) — laut Mandat explizit als "physikalisch plausibler
Ingenieurs-Default, NICHT literaturbelegt" dokumentiert, statt zu spekulieren oder eine Quelle
zu erfinden.

### Prüfung 3: PSI-HP13/14nm-Re-Validierung mit der aktuellen Resist-Kette

**Ziel:** die alte, im August gefundene Diskrepanz (`STEP_5.2C_FIRST_EXPERIMENTAL_VALIDATION_
REPORT.txt`: Simulator-LER 160x unter PMMA-Literaturwert) mit der seither komplett
überarbeiteten `full_chem`-Kette (MackModel-Verdrahtung, PAG/Quencher-Diskretheit, 3σ/1σ-Fix)
neu bewerten.

**PMMA-Vergleich (Kim et al. 2022):** bewusst NICHT wiederholt — PMMA ist kein chemisch
verstärkter Resist (löst durch Kettenspaltung, nicht säurekatalysierte Entschützung), die
gesamte `full_chem`-Kette modelliert explizit CAR-Chemie. Dieser Vergleich war und bleibt
strukturell "NOT_COMPARABLE", unabhängig von der Modellgüte — erneutes Testen hätte keinen
Erkenntniswert.

**PSI-Vergleich (Develioglu et al. 2023, Proc. SPIE 12498, 1249805, DOI 10.1117/12.2660859,
lokal archiviert unter `references/euv_experimental/source_02_psi_resist_screening/`) —
diesmal sinnvoll, da echte CAR-Vendoren, dieselbe Resist-Klasse wie unser Modell:**

Direkt aus dem Original-PDF gelesen (Tabelle 3/4, S. 5-6):

| HP [nm] | Vendor (CAR) | Dose-to-Size [mJ/cm²] | LWR_unb [nm] |
|---|---|---|---|
| 14 | A | 53,85 | 2,51 |
| 14 | B | 38,9 | 2,63 |
| 14 | D | 36,95 | 2,40 |
| 13 | A | 51,25 | 2,84 |
| 13 | B | 41,2 | 2,58 |
| 13 | D | 26,38 | 2,97 |

**Sigma-Konvention verifiziert (S. 2, Abschnitt 1.2, wörtlich):** "The SEM parameters have
been set along the same lines as the roughness protocol of IMEC" — dasselbe Protokoll, das
in Vesters' Thesis (vorheriger Eintrag) explizit als 3σ dokumentiert ist. Kein expliziter
"3σ"-String in diesem spezifischen PDF gefunden, aber die direkte Protokoll-Referenz ist ein
starkes Indiz, kein Beweis — als Annahme, nicht als Fakt, gekennzeichnet. Umgerechnet auf 1σ
(÷3, falls die Annahme zutrifft): **0,80–0,99nm** Zielbereich, nicht 2,4–2,97nm. LWR ist
zusätzlich bereits "unbiased" (SEM-Rauschen per PSD-Fit entfernt, PSI-eigene Software "SMILE")
— ein saubererer Vergleichspunkt als Vesters' biased Table 4.2.

**Eigener Test der aktuellen `full_chem`-Kette bei HP14nm (period_nm=28, line_width_nm=14):**

| Konfiguration | Dosis-Scan | Ergebnis |
|---|---|---|
| resist_thickness_nm=50 (unser Default) | 26–54 mJ/cm² (deckt den realen PSI-DtS-Bereich ab) | CD=28 (unentwickelt) oder CD=0 (durchentwickelt) bei fast jeder Dosis; nur bei dose=32mJ/cm² ein einzelner Zwischenwert (CD=7,66nm) — ein Fenster von **~1mJ/cm² Breite** |
| resist_thickness_nm=25 (PSI's tatsächliche Filmdicke, 20-30nm laut Paper Tabelle 2) | 20–54 mJ/cm² | AUSSCHLIESSLICH CD=28 oder CD=0 gefunden — kein auflösender Punkt in der getesteten Auflösung identifiziert |

**Befund:** bei HP13/14nm-Geometrie hat das aktuelle "Polymer A"-Modell **praktisch kein
nutzbares Prozessfenster** — das Modell ist bei dieser Pitch-Größe fast überall binär
(voll entwickelt oder gar nicht), unabhängig von der Dosis. Das ist **kein Bug**, sondern
dieselbe, in Prüfung 1 quantifizierte `mack_n=18,2`-Steilheit, die bei sehr engem Pitch
(wo die Aerial-Image-Dosis-Modulation über eine kürzere Distanz komprimiert ist) noch
extremer wirkt als bei den bisher getesteten 44-64nm-Pitches. Ein sinnvoller
LWR-Vergleich gegen die PSI-HP13/14nm-Daten ist mit diesem Chemie-Parametersatz **nicht
durchführbar** — nicht weil das Modell "falsch" ist, sondern weil "Polymer A" (kalibriert
bei 50nm-Pitch/32nm-CD, Yamamoto et al. 2011) außerhalb seines validierten
Geltungsbereichs eingesetzt würde. Das deckt sich mit der PSI-Studie selbst, die explizit
feststellt, dass bei diesen Auflösungen spezialisierte Chemie (Multi-Trigger Resist,
"MTRs demonstrated better Z-factor values owing to their high sensitivity") nötig ist,
nicht einfache Single-PAG-CAR-Chemie wie "Polymer A".

**Einordnung — dritte unabhängige Bestätigung eines bereits etablierten Musters:** wie
bei der Vesters-Validierung (44nm Pitch) und der PMMA-Prüfung (falsche Resist-Klasse) zeigt
sich erneut: der Geltungsbereich von "Polymer A"/Yamamoto et al. 2011 ist eng (grob 44-64nm
Pitch, CD-Bereich ~15-40nm bei den bisher getesteten Dosen) und generalisiert nicht auf
aggressivere Nodes. Das ist eine ehrliche Charakterisierungsgrenze des aktuell verwendeten
Parametersatzes, keine Modell-Fehlfunktion.

**Nicht umgesetzt in dieser Runde:** kein Code geändert (reine Charakterisierung); keine
neue Chemie/Kalibrierung für HP13/14nm eingeführt (wäre eine echte Kalibrierungsaufgabe mit
eigenem Datensatz, nicht Teil dieser Prüfung, und laut Mandat streng von Validierung zu
trennen).

---
