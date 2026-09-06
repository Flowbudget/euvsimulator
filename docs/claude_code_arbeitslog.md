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

## 2026-09-04 (Fortsetzung 6): Falsifikationstests — 3 bestätigt korrekt, 1 echter neuer Befund

**Auslöser:** "mach mit allen weiteren Prüfungen weiter" — Fortsetzung von Phase 3 mit
gezielten Grenzfall-/Falsifikationstests, wie vom Mandat gefordert ("Was muss mathematisch
immer gelten?", "Was passiert bei sehr großen/kleinen Werten?").

**Test 1 — RCWA/Hopkins-Konsistenztests frisch verifiziert (nicht nur Audit-Historie
vertraut):** `test_energy_conservation_lossless` (RCWA 1D), `test_energy_conservation`
(RCWA 2D), `test_hopkins_aerial_matches_abbe` (Hopkins vs. unabhängige Abbe-Implementierung,
< 10% relativer Fehler, < 0,03 MAE) — alle frisch gelaufen, alle grün. Bestätigt: diese
Kern-Konsistenzprüfungen sind real, nicht nur behauptet.

**Test 2 — Poisson-Statistik des Photon-Schrotrauschens, unabhängig nachgerechnet:** bei
konstantem Dosisfeld (20mJ/cm², 512×512, `se_blur_nm=0`) gemessen: Varianz/Mittelwert des
verrauschten Dosisfelds = 1,468. Unabhängig aus den Umrechnungsfaktoren berechnet (Photonen-
energie 91,84eV, dose_to_energy_factor): erwartete "Dosis pro Photon" = 20mJ/cm² /
13,59 Photonen/Pixel ≈ 1,471 — **innerhalb der statistischen Stichprobenunsicherheit
identisch.** Das bestätigt: die Poisson-Photonenstatistik ist korrekt implementiert, nicht
nur "sieht plausibel aus".

**Test 3 — Reproduzierbarkeit bei festem Seed:** 3 identische Läufe mit `stochastic_seed=42`
(nicht-degenerierte Konfiguration, CD=17,19nm) geben bit-identische CD/LER/LWR. Anderer Seed
(43) weicht sinnvoll ab (LER 1,4026→1,3991, ähnliche Größenordnung, andere Realisierung).
Reproduzierbarkeit real bestätigt.

**Test 4 — Großzahlgrenzfall von `exposure_stochasticity`: ECHTER, NEUER BEFUND, NICHT
GELÖST:**

Physikalische Erwartung: bei `pag_density_per_nm3 → ∞` (Quencher-Dichte proportional
mitskaliert, Verhältnis 0,25 konstant) sollte das molekulare Zählrauschen verschwinden
(1/√N-Skalierung) UND das Ergebnis gegen den deterministischen Mean-Field-Wert (ohne
`exposure_stochasticity`) konvergieren — beide beschreiben im Grenzfall unendlich vieler
Moleküle dieselbe Kontinuums-Physik.

**Gemessen** (period_nm=44, line_width_nm=22, dose=24mJ/cm², development_stochasticity=False):

| Konfiguration | CD [nm] | LER [nm] | LWR [nm] |
|---|---|---|---|
| Deterministisch (kein exposure_stochasticity) | **23,03** | – | – |
| exposure_stochasticity, pag_density=0,2/nm³ (Default) | 17,19 | 2,68 | 5,28 |
| exposure_stochasticity, pag_density=2,0/nm³ | 17,19 | 1,05 | 2,08 |
| exposure_stochasticity, pag_density=20,0/nm³ | 17,19 | 0,00 | 0,00 |
| exposure_stochasticity, pag_density=200,0/nm³ | 17,19 | 0,00 | 0,00 |

LER/LWR verhalten sich korrekt (→0 mit steigender Dichte, wie erwartet). **Aber CD bleibt bei
17,19nm über den GESAMTEN getesteten Dichtebereich — konvergiert NICHT gegen den
deterministischen Wert 23,03nm, selbst wenn das Rauschen vollständig verschwunden ist.**

**Ursache identifiziert** (Code gelesen, nicht spekuliert): `_cd_via_full_chem`s
deterministischer Pfad (IMMER berechnet, unabhängig von `enable_stochastic`) nutzt
`dill_abc_exposure()` → `reaction_diffusion_analytical()` — **enthält keinerlei
Säure-Base-Quenching-Mechanismus.** `exposure_stochasticity=True`s Kette
(`sample_pag_quencher_acid()` → `reaction_diffusion_with_quenching()`) enthält dagegen
IMMER eine Quencher-Subtraktion (im reaktionslimitierten Sättigungsregime ≈
`max(acid-quencher, 0)`), UNABHÄNGIG von der Molekülzahl-Diskretheit selbst — auch im
perfekten Kontinuums-Grenzfall (unendlich viele Moleküle, kein Zählrauschen) bleibt diese
Subtraktion bestehen, weil das Quencher/PAG-**Verhältnis** (0,25) bei meiner Testskalierung
konstant gehalten wurde, nicht die absolute Quencher-Menge auf 0 gesetzt wurde.

**Einordnung:** Das ist kein Implementierungsfehler im Sinne von "falscher Code" — beide
Ketten sind einzeln real, zitiert und korrekt (`dill_abc_exposure` = reine Beer-Lambert-
Belichtung ohne Quenching, zitiert Yamamoto et al. 2011; `sample_pag_quencher_acid`+
`reaction_diffusion_with_quenching` = vollständige PAG/Quencher-Physik, zitiert Mack,
Biafore & Smith 2011). Das Problem ist eine **stille physikalische Inkonsistenz zwischen
den beiden Pfaden**: `exposure_stochasticity` ist NICHT nur ein "Rauschen an/aus"-Schalter,
wie der Name und die bisherige Dokumentation nahelegen — er verändert auch die MITTLERE
Chemie (fügt eine Säure-Base-Neutralisation hinzu, die der deterministische Baseline-Pfad
gar nicht kennt). Ein Nutzer, der nur "Diskretheitsrauschen hinzufügen" möchte, bekommt
implizit auch ein anderes mittleres chemisches Modell.

**Bewusst NICHT einseitig entschieden** (drei valide, unterschiedlich invasive Optionen,
jede mit echten Vor-/Nachteilen):
- **A)** So lassen, aber explizit dokumentieren, dass `exposure_stochasticity=True` das
  mittlere chemische Modell ändert, nicht nur Rauschen hinzufügt — kleinster Eingriff,
  reine Dokumentation.
- **B)** Den deterministischen `full_chem`-Basispfad um die (Mean-Field-Erwartung der)
  Quenching-Chemie erweitern, sodass beide Pfade dieselbe mittlere Chemie teilen und
  `exposure_stochasticity` wirklich NUR Rauschen hinzufügt — invasiver, ändert den
  Standard-`full_chem`-Determinismus-Pfad und damit potenziell viele bereits etablierte
  CD-Werte/Golden-Values.
- **C)** Eine separate, nur für Vergleichszwecke gedachte Mean-Field-Referenz MIT Quenching
  berechnen, ohne den bestehenden Standardpfad zu verändern.

Dies ist laut Mandat explizit ein Punkt, an dem angehalten und die Entscheidung dem Nutzer
vorgelegt werden soll, statt einseitig zu entscheiden (mehrere wissenschaftlich plausible
Optionen mit unterschiedlicher Tragweite). Kein Code geändert in dieser Runde.

**Zusätzlicher, kleinerer Befund (dokumentiert, nicht behoben):** `dx` vs. `dx_nm` als
Parametername ist im gesamten `resist/`-Paket inkonsistent — 14 Funktionssignaturen nutzen
`dx` (exposure.py, peb.py, develop.py, größte Teile von stochastic.py), 6 nutzen `dx_nm`
(neuere Funktionen in stochastic.py, `aerial/abbe.py::aerial_from_orders`). Empfehlung:
auf `dx_nm` vereinheitlichen (selbstdokumentierend, passt zum sonstigen `_nm`-Suffix-Muster
im Projekt, z.B. `resist_thickness_nm`, `se_blur_nm`), aber bewusst NICHT in dieser Runde
umgesetzt — eine echte Umbenennung von 14 Signaturen berührt viele Call-Sites, bestehende
Tests und die heute reparierten Notebooks; das wäre der "riesige Misch-Commit", vor dem das
Mandat explizit warnt. Als eigener, klar abgegrenzter Schritt vorgeschlagen, falls gewünscht.

---

## 2026-09-04 (Fortsetzung 7): exposure_stochasticity-Inkonsistenz — echte Literatursuche, Teilerfolg, ehrliches Ende

**Auslöser:** Fortsetzung des vorigen Befunds (Großzahlgrenzfall-Inkonsistenz zwischen
`exposure_stochasticity`s Chemie und dem deterministischen `full_chem`-Basispfad). Nutzer bat
um Entscheidungshilfe; auf meine Empfehlung (Option A jetzt, Option B als eigenes Projekt)
antwortete der Nutzer mit dem Wunsch nach "korrekt funktionierender" Software. Daraufhin
empirisch getestet, ob Option B (Quenching in den deterministischen Pfad) einfach umsetzbar
ist — war es nicht (siehe unten) —, danach explizit Option 2 (echte neue Literatursuche nach
einem selbstkonsistenten Einzelquellen-Parametersatz) angefordert und durchgeführt.

### Empirischer Test von Option B (Quenching deterministisch einbauen)

Mit den AKTUELLEN Defaults (`dill_Q=0,5`, `pag_density=0,2/nm³`, `quencher_density=0,05/nm³`)
über die echte Pipeline getestet (Monkey-Patch auf `reaction_diffusion_analytical`, echte
Aerial-Dosisverteilung, nicht synthetisch nachgebaut — Lektion aus einer früheren
Fehleinschätzung in dieser Sitzung beherzigt): mittlere Säure vor Quenching = 0,151, Maximum =
0,325 — beide nahe an oder nur knapp über der Quencher-Baseline (0,25). `dill_Q`-Sweep bei
dose=20 zeigt: ein nicht-degeneriertes CD braucht `dill_Q≥1,0` — **physikalisch unmöglich**
(dill_Q ist eine Wahrscheinlichkeit, ≤1 per Definition). Dosis-Sweep bei zitiertem `dill_Q=0,5`
zeigt: brauchbares CD erst ab Dosis≈150mJ/cm² (weit jenseits jedes realistischen
EUV-Budgets von 10-40mJ/cm²), weil die maximal erreichbare Säure asymptotisch gegen `dill_Q=0,5`
selbst läuft (`h=Q·(1-e^(-CE))→Q`) und davon nur 0,25 Überschuss über die Quencher-Baseline
übrigbleiben. **Option B ist mit den aktuellen Defaults nicht einfach umsetzbar** — bestätigt
empirisch, nicht nur vermutet.

### Literatursuche (deep-research-escalation-Methodik) nach einer selbstkonsistenten Quelle

**Zwischenfund (nicht die Lösung, aber wichtige Cross-Validierung):** Mack, Biafore & Smith
2013, "Stochastic exposure kinetics of extreme ultraviolet photoresists: Trapping model," J.
Vac. Sci. Technol. B 31(6), 06F603 (frei via lithoguru.com, bereits lokal archiviert als
`2013_Stochastic_exposure_kinetics_of_EUV_photoresists-Trapping_model.pdf`) — bestätigt
PAG-Dichte 0,2/nm³ als über mehrere Paper dieser Autorengruppe wiederverwendeten Baseline-Wert
(Fig. 5: φ_trap=0,8, φ_e=0,9, r=2nm, P0=0,2nm⁻³). Enthält aber keine Quencher-Physik.

**Hauptfund:** Die eigene Quelle von `pag_density`/`quencher_density`/`quench_rate` — Mack,
Biafore & Smith 2011, "Stochastic Acid-Base Quenching...", Proc. SPIE 7972, 797202 — liefert
im FLIESSTEXT direkt bei ihrer Tabelle I einen dazugehörigen, selbstkonsistenten
Belichtungsparameter: *"These values result in an exposure rate constant of **C = 0,08652
cm²/mJ**."* Und: *"Note that for the parameters of Table I, δ0 = 0 requires a dose of **3,43
mJ/cm²**."* — d.h. bei DIESEM (aus derselben Tabelle I stammenden) C-Wert gibt es bei
realistischen EUV-Dosen einen echten, robusten Säureüberschuss. Das ist die erste tatsächlich
gefundene Einzelquelle, die Belichtung UND Quenching selbstkonsistent für dieselbe
(illustrative) Konfiguration liefert.

**Wichtige Einschränkung:** Tabelle I ist explizit ein **idealisierter, synthetischer
Testfall** der Autoren (PAG-Molarabsorptivität = 0 → keine Beer-Lambert-Tiefenabsorption
überhaupt; Resistdicke 10nm statt Yamamotos reale 50nm) — kein realer, gemessener Resist.

**Empirischer Test dieses selbstkonsistenten Teilsatzes durch die volle Pipeline** (dill_C=
0,08652, dill_A=dill_B≈0, resist_thickness_nm=10, restliche Quenching-Parameter wie Tabelle I,
ABER `peb_D`/`peb_t_bake` weiterhin aus Lavery et al. 2006/Anderson et al. 2009 und
`mack_R_max/R_min/n/M_th`/`peb_k` weiterhin aus Yamamoto et al. 2011 — beides unabhängige,
NICHT zu Tabelle I gehörige Quellen): CD blieb bis Dosis=40mJ/cm² weiterhin degeneriert
(unentwickelt). Diagnose: die PEB-Diffusionslänge (σ≈20nm aus Lavery/Anderson) verschmiert das
ohnehin schmale Säureüberschuss-Signal aus Tabelle I fast vollständig über den 64nm-Pitch,
bevor die Entwicklungsstufe (Yamamoto-Mack-Modell) überhaupt greift.

### Ehrliches Fazit

Es gibt **keine einzige frei zugängliche Quelle**, die den gesamten Belichtung+PEB+Quenching+
Entwicklung-Parametersatz für einen realen Resist liefert. Das bestätigt und erweitert die
bereits sehr gründliche, 9-Runden-Literatursuche aus früheren Sitzungen (siehe `/Users/flo/mack
fits/search_log.md`) explizit auf die Belichtung+Quenching-Kombination, die dort noch nicht
geprüft worden war. Der aktuelle `full_chem`-Stack mischt jetzt nachweislich **fünf
unabhängige Quellen**: Yamamoto et al. 2011 (dill_A/B, mack_R_max/R_min/n/M_th, peb_k,
resist_thickness_nm, develop_time_s), Mack/Biafore/Smith "Stochastic exposure kinetics" 2011
(dill_Q=0,5, als synthetischer Testfall, nicht realer Resist), Mack/Biafore/Smith "Stochastic
Acid-Base Quenching" 2011 (pag_density/quencher_density/quench_rate, ebenfalls synthetischer
Testfall), Lavery et al. 2006/Anderson et al. 2009 (peb_D), und implizit CXRO/Henke et al. 1993
(Brechzahlen).

**Umgesetzt:** `pipeline.py`s `exposure_stochasticity`-Kommentar um diesen vollständigen
Befund erweitert (Option A, wie vom Nutzer bestätigt) — inklusive Hinweis, dass Nutzer, die
wenigstens Belichtung+Quenching intern konsistent haben möchten, `dill_C=0,08652` explizit
setzen können (kein neues Feld nötig, `dill_C` ist bereits voll konfigurierbar). Kein
Default-Verhalten geändert. `test_full_chem_config.py` weiterhin grün (7/7, reiner
Kommentar-Zusatz).

**Für zukünftige Sitzungen im externen Katalog vermerkt:** `/Users/flo/mack fits/catalog.json`,
Eintrag zur Quenching-Quelle, um C=0,08652/δ0-Dosis=3,43mJ/cm² als neuen, verifizierten
Fund zu sichern (nicht nur PAG/Quencher-Dichte/Rate wie zuvor).

---

## 2026-09-04 (Fortsetzung 8): Vesters-Lücke mit development_strength=15,0 neu vermessen — negatives Ergebnis

**Auslöser:** Neue Session, Übergabeprompt Punkt D. Die im Arbeitslog dokumentierte
Vesters-Lücke ("Faktor ~1,1–2,4x") stammte aus einer Ablation, die mit dem damaligen Default
`development_strength=20,0` lief. Commit `76c27e0` hat diesen Default auf 15,0 rekalibriert,
die daraus folgende Lücke wurde danach aber **nie neu gemessen** — die dokumentierte Kennzahl
war damit veraltet. Das zu korrigieren ist eine reine Messaufgabe, kein Code-Eingriff.

**Methodik / Kontamintationsschutz:** Exakte Reproduktion der Ablation aus dem Eintrag
"2026-09-04 (Fortsetzung): LWR-Ursache systematisch isoliert" (Commit `7198423`):
`period_nm=44,0`, `line_width_nm=22,0`, `se_blur_nm=5,0`, `stochastic_seed=42`,
`stochastic_n_realisations=3`, `stochastic_ler_grid_y=4096`, Dosen 22/24/25 mJ/cm².
Vorher per `git diff 7198423..HEAD -- src/` verifiziert, dass in der Zwischenzeit
**ausschließlich** `development_strength` verhaltensrelevant geändert wurde (alles andere:
Kommentare, Docstrings, der tote `__main__`-uvicorn-Pfad, sowie der `ler_estimate`-NaN-Fix,
der nur im Kein-Kante-Fall greift). Zusätzlich als eingebaute Kontrolle alle vier
Konfigurationen gemessen: A (nur Photon) und C (nur `exposure_stochasticity`) nutzen
`development_stochasticity` nicht und MUSSTEN daher unverändert reproduzieren.

**Kontrolle bestanden:** A und C reproduzierten alle sechs Werte innerhalb ≤0,0044 nm der
Arbeitslog-Werte — das ist reines Rundungsrauschen gegenüber den dort auf 2 Nachkommastellen
angegebenen Referenzwerten (max. möglicher Rundungsfehler 0,005). (Anmerkung zur eigenen
Methodik: das Messskript hatte eine unpassend enge Toleranz von 1e-6 gegen gerundete
Referenzwerte gesetzt und meldete deshalb zunächst falsche "Abweichung"-Flags — Skriptfehler,
kein Messproblem.)

**Ergebnis** (Konfiguration D = beide Stochastikquellen, der für Vesters relevante Fall):

| Dosis [mJ/cm²] | CD [nm] | LWR alt (s=20) | LWR neu (s=15) | Faktor alt | Faktor neu |
|---|---|---|---|---|---|
| 22 | 30,25 | 3,69 | 3,4248 | 1,07–1,70x | 1,00–1,58x |
| 24 | 17,19 | 5,17 | 5,3183 | 1,51–2,39x | 1,55–2,45x |
| 25 | 10,31 | 4,83 | 4,7431 | 1,41–2,23x | 1,38–2,19x |

(Faktor = simulierter 1σ-LWR geteilt durch den auf 1σ umgerechneten Vesters-Zielbereich
2,167–3,433 nm, d.h. 6,5–10,3 nm ÷ 3.)

**Befund — die Rekalibrierung hat die Vesters-Lücke NICHT geschlossen.** Gesamtspanne
1,07–2,39x (alt) → **1,00–2,45x** (neu), also minimal *breiter* statt kleiner. Die
Einzelwerte bewegten sich in beide Richtungen (Dosis 22 runter, 24 hoch, 25 leicht runter) —
kein systematischer Trend. Der für den Vesters-Vergleich relevanteste Punkt (Dosis 24,
CD=17,19 nm, am nächsten an Vesters' Ziel-CD von 22 nm) wurde sogar geringfügig schlechter
(1,51→1,55x an der Untergrenze). Die alte Reproduktion traf die dokumentierte "1,1–2,4x"
exakt (berechnet: 1,07–2,39x), womit die Nachstellung der Originalbedingungen validiert ist.

**Dokumentierte Kennzahl hiermit aktualisiert:** die Vesters-Lücke beträgt mit den aktuellen
Defaults **1,0–2,5x Überschätzung** (nicht 1,1–2,4x). Der bereits dokumentierte Vorbehalt
bleibt vollumfänglich bestehen: Vesters' Table-4.2-Werte sind "biased" (SEM-Rauschen
enthalten, siehe Eintrag "Fortsetzung 2"), die *wahre* physikalische Zielrauheit liegt also
noch niedriger — die tatsächliche Überschätzung ist entsprechend größer als diese Faktoren
zeigen.

**Nebenbefund (neu, physikalisch kohärent):** `development_strength` wirkt sehr unterschiedlich
je nach aktiver Rauschquelle. In Konfiguration B (nur `development_stochasticity`) änderte der
Wechsel 20→15 das LWR massiv (Dosis 24: 1,80→2,3787, +32 %; Dosis 25: 2,26→2,9404, +30 %),
in der kombinierten Konfiguration D dagegen kaum (Dosis 24: +3 %). `exposure_stochasticity`
dominiert dort und maskiert den Entwicklungs-Beitrag — konsistent mit der bereits
dokumentierten Nicht-Additivität der Stochastikquellen (Eintrag "Fortsetzung 6"). Bei Dosis 22
blieb B praktisch unverändert (2,84→2,8414), was zur ebenfalls dokumentierten
nicht-monotonen `development_strength`-Antwort passt.

**Einordnung:** Ein sauberes negatives Ergebnis. Es bestätigt, dass die verbleibende
Vesters-Lücke **nicht** von `development_strength` getrieben wird — die Rekalibrierung war
(gemessen an der Lücke) wirkungslos, was rückblickend zur Ablationserkenntnis passt, dass
`development_stochasticity` bei dieser Geometrie ohnehin der schwächere der beiden
Mechanismen ist. Kein Code geändert, kein Parameter angepasst; die Rekalibrierung aus
`76c27e0` bleibt gültig (sie war gegen den korrigierten 1σ-Zielbereich für die
`development_stochasticity`-allein-Konfiguration begründet, nicht gegen die kombinierte).

---

## 2026-09-04 (Fortsetzung 9): URSACHE GEFUNDEN — warum das Modell zu viel Rauheit erzeugt

**Auslöser:** Nach dem negativen Ergebnis der `development_strength`-Nachmessung (Eintrag 8)
lautete die offene Frage: das Modell **überschätzt** LWR (1,0–2,5x gegenüber dem bereits
biased Zielband, real also mehr) — warum? Reine Untersuchung, kein Codeeingriff.

### Ausgangslokalisierung (aus der bestehenden Ablation)

Photon-Schrotrauschen allein (Konfig A) liegt mit 1,5–1,7 nm bereits **im oder unter** dem
Zielband (2,17–3,43 nm, 1σ, biased). Erst `exposure_stochasticity` (Konfig C: 5,1–5,3 nm)
treibt darüber. Der Überschuss stammt also spezifisch aus der PAG/Quencher-Diskretheit.

### Hypothese 1 (Diskretisierungsabhängigkeit) — WIDERLEGT

Analytische Vorhersage vorab: `n_acid ~ Poisson(λp)` (Poisson-Thinning), also
`Var[acid] = p/λ ∝ 1/V_voxel`. Bei rein linearer Weiterverarbeitung kürzt sich V_voxel gegen
die Mittelung über V_blur/V_voxel Voxel heraus (Ergebnis gitterkonvergent); die *nichtlineare*
Quenching-Stufe dazwischen sollte diese Kürzung brechen (Jensen-Bias ∝ Var) und damit eine
Gitterabhängigkeit erzeugen.

**Erster Messversuch war fehlerhaft** und wird hier zur Transparenz mitdokumentiert:
`stochastic_ler_grid_y` wurde fest gelassen, während `grid` variierte. Da die physikalische
Messlänge = `ler_grid_y · dx` ist, schrumpfte sie dabei von 352 auf 88 nm — doppelter
Konfound: statistisch (n_eff fiel auf 4–11, Projektziel ≥30) und physikalisch (LWR ist
bandbreitenabhängig, kürzere Linie = anderes Ortsfrequenzband). Ergebnis war nicht auswertbar.

Korrigierter Aufbau (`ler_grid_y ∝ grid`, Messlänge konstant 352 nm), dose=24, seed=42:

| Konfig | grid=128 | grid=256 | grid=512 | Streuung |
|---|---|---|---|---|
| A (Photon) | 1,4930 | 1,6299 | 1,6839 | ~13 % |
| C (exposure_stoch) | 5,2177 | 5,2903 | 5,1166 | **~3 %** |

Bei 4-facher Variation der Voxelgröße bleibt C konstant → **gitterkonvergent, Hypothese
widerlegt.** Positiver Qualitätsbefund über den Code: die Diskretheitsmodellierung ist sauber
normiert. (Erklärung, warum der Jensen-Bias nicht durchschlägt: das Säurefeld ist ein dünner
Punktprozess; dessen Faltung mit einem großen Kern hängt nur von der Punktdichte ab, nicht von
der Binning-Größe.) Auch die Tiefenauflösung (`n_develop_layers` 11/21/41) zeigte keinen
systematischen Trend (4,82 / 5,15 / 4,55 nm, ±7 % Streuung).

### Rauschzerlegung (Monkey-Patch-Varianten, kein Repo-Code geändert)

Basis: Konfig C, grid=256, ler_grid_y=2048, dose=24, seed=42, Baseline-LWR = 5,2903 nm.

| Variante | LWR [nm] | Beitrag |
|---|---|---|
| V0 Baseline | 5,2903 | — |
| V1 Quencher deterministisch (kein Quencher-Zählrauschen) | 5,2757 | **+0,015** |
| V2 Säure deterministisch (Mean-Field), nur Quencher-Rauschen | 1,5509 | **+3,739** |
| V3 50 % der Diffusionsvarianz VOR dem Quenching | **0,0000** | −5,290 |
| V4 90 % der Diffusionsvarianz VOR dem Quenching | **0,0000** | −5,290 |

- **Quencher-Zählrauschen ist irrelevant** (+0,015 nm). Der Quencher wirkt rein als Schwelle.
- **PAG-Zählrauschen ist der Treiber** (~3,7 der 5,3 nm). V2 landet bei 1,55 nm, praktisch auf
  Photon-Niveau (1,63 nm bei gleichem Gitter).
- Die Reihenfolge Quenching/Diffusion ist **keine glatte Interpolation, sondern eine Klippe**:
  schon 50 % Vorglättung (σ_pre ≈ 14 nm) kollabiert das Ergebnis auf exakt 0,0 (n_eff = 2048
  = völlig uniformes Feld). Deckt sich mit dem früheren Befund, dass Blur-vor-Reaktion alles
  auf ~1e-21 zusammenbrechen ließ (Eintrag "Fortsetzung 2", 2026-09-03).

### Direkte Feldstatistik — die Ursache, quantifiziert

Echte Zwischenwerte aus der laufenden Pipeline abgegriffen (dose=24, grid=256):

| Größe | Wert |
|---|---|
| Mittlere PAG-Zahl pro Voxel λ = ρ_PAG·V_voxel | **0,0148** → 99,76 % der Voxel sind leer |
| Quencher-Schwelle q₀ = ρ_Q/ρ_PAG | 0,250 |
| Mean-Field-Säure: Mittel / Maximum | 0,1635 / **0,2712** |
| Anteil des Mean-Field-Feldes über q₀ | 13,87 % |
| Gesampelte Säure: Anteil Voxel mit Säure > 0 | **0,24 %** |
| Anteil Voxel über q₀ | 0,24 % (identisch — ein Molekül genügt) |
| Diskrete Stufenhöhe 1/λ | **67,7 = 271× die Schwelle** |

**Mechanismus:** Die Mean-Field-Chemie funktioniert bei dieser Parameterkombination praktisch
nicht — die maximal erreichbare mittlere Säure (0,2712) liegt nur **8 % über** der
Quencher-Schwelle (0,25). Das Modell erzeugt überhaupt nur deshalb Signal, weil das diskrete
Sampling seltene Spikes erzeugt, die mit einem einzigen Molekül sofort 271-fach über der
Schwelle liegen. Das Quenching ist damit keine chemische Teil-Neutralisation, sondern ein
**binärer Spike-Filter** (Voxel mit Molekül überlebt massiv, Voxel ohne wird genullt). Die
nachfolgende PEB-Diffusion mittelt diese Spikes, sodass das resultierende Säurefeld im
Wesentlichen die **lokale Spike-Dichte** abbildet — ein Schrotrauschen seltener Ereignisse,
dessen Amplitude von der Spärlichkeit und der Schwellenhöhe gesetzt wird, **nicht** von einem
physikalisch kalibrierten Rauschprozess.

### Einordnung — eine Ursache erklärt vier bisher unverbundene Beobachtungen

1. **Zu viel Rauheit** (diese Untersuchung): entsteht durch Spike-Gleichrichtung.
2. **Vorglättung kollabiert auf 0** (V3/V4 oben, und Eintrag "Fortsetzung 2"): geglättete
   Spikes fallen unter die Schwelle.
3. **Großzahlgrenzfall konvergiert nicht gegen Mean-Field** (Eintrag "Fortsetzung 6"): mehr
   Moleküle → glatteres Feld → Mean-Field kann die Schwelle nicht überqueren → Signal stirbt.
   Die damalige Deutung "Rauschen geht wie erwartet gegen 0" war unvollständig; die
   vollständige Erklärung ist diese hier.
4. **Quencher-Rauschen irrelevant** (V1): er ist reiner Schwellwertgeber.

Und es ist die direkte, jetzt **quantifizierte** Konsequenz der bereits in Eintrag
"Fortsetzung 7" dokumentierten Quellen-Inkompatibilität: `dill_Q = 0,5` deckelt die Säure
asymptotisch bei 0,5 (`h = Q·(1−e^{−CE}) → Q`), während `ρ_Q/ρ_PAG = 0,25` aus einer
**anderen** synthetischen Tabelle die Hälfte dieses Spielraums wegnimmt. Der verbleibende
Spielraum reicht der Mean-Field-Chemie nicht.

### Was daraus NICHT folgt

Die implementierte Physik ist nicht "falsch programmiert": Poisson/Binomial-Sampling ist
korrekt (Mittelwert = Mean-Field, Varianz = p/λ, unabhängig verifiziert), gitterkonvergent,
und die Quenching-Kinetik ist die zitierte geschlossene Lösung. Das Problem ist die
**Parameterkombination**, die das Modell in ein Regime zwingt, in dem der beabsichtigte
Mechanismus (molekulares Schrotrauschen auf funktionierender Chemie) durch einen anderen
(Gleichrichtung seltener Spikes an einer unerreichbaren Schwelle) ersetzt wird.

### Offen — bewusst nicht einseitig entschieden (Stop-Regel)

Ein Fix erfordert eine Entscheidung über die Parameterbasis, nicht über den Code:
- **(i)** `ρ_Q/ρ_PAG` als Kalibrierparameter behandeln (wie `dill_Q`/`peb_k` bereits
  klassifiziert sind) und auf einen Wert senken, der der Mean-Field-Chemie echten Spielraum
  lässt — mit vollständig dokumentiertem Kalibrierverfahren.
- **(ii)** Den in Eintrag "Fortsetzung 7" gefundenen selbstkonsistenten Belichtungswert
  (C = 0,08652 aus derselben Tabelle I wie ρ_PAG/ρ_Q) verwenden statt Yamamotos dill_C —
  löst die Belichtung/Quenching-Konsistenz, aber nicht PEB/Entwicklung (dort empirisch
  getestet und weiterhin degeneriert).
- **(iii)** Quenching bei dieser Parameterlage als nicht anwendbar kennzeichnen und
  `exposure_stochasticity` ohne Quencher-Subtraktion anbieten (reines PAG-Zählrauschen).

Kein Code, kein Parameter geändert. Verifikationsskripte lagen im Scratchpad, nicht im Repo.

---

## 2026-09-04 (Fortsetzung 10): Ursache der Überrauheit isoliert — PEB-Blur auf der steilen Flanke der Kontrastverlust-Kurve; Q-Fix-Hypothese aus Fortsetzung 9 als LWR-Ursache widerlegt

Auftrag: "finde zuerst heraus warum das model zuviel rauschen erzeugt" — vor jeder
Code-Änderung. Vorgehen durchgehend nach der Preflight-Methodik: Vorhersagen vorab
schriftlich, Messung per Monkey-Patch durch die echte Pipeline, kein Repo-Code geändert.
Alle Skripte im Scratchpad (`preflight_qfix.py`, `blur_diagnose.py`, `blur_diagnose_v2.py`,
`left_flank.py`, `mechanism_check.py`, `edge_saturation.py`, `mean_mismatch.py`).

### 1. Preflight des Q-Fixes (`acid = Q·(1−M)` → `acid = 1−M`, Q=1,0 an beiden Aufrufstellen)

Vier vorab festgelegte Vorhersagen, Ergebnis **1 von 4**:

| | Vorhersage | Ergebnis |
|---|---|---|
| P1 | Dosisfenster fällt in Vesters' 8–16 mJ/cm² | **erfüllt**: Dosis-zu-Größe 10,25–10,5 (vorher 24) |
| P2 | Großzahlgrenzfall konvergiert gegen det. CD | nicht erfüllt: CD 17,19 bei allen ρ_PAG, det. 20,28 |
| P3 | Vorglättung kollabiert nicht mehr auf 0 | nicht erfüllt: weiterhin exakt 0,0 |
| P4 | LWR bessert sich ~√2 | **widerlegt, Gegenrichtung**: Konfig C 5,29 → 6,01; A 1,63 → 2,75 |

Die LWR-Zunahme ist physikalisch stimmig (niedrigere korrekte Dosis → weniger Photonen →
1/√Dosis: 1,63·√(24/10,5) = 2,46 vs. gemessen 2,75). **Die Ursachenanalyse aus Fortsetzung 9
("fehlender Spielraum über der Quencher-Schwelle erzeugt die Überrauheit") ist damit als
LWR-Ursache widerlegt** — der Spielraum wurde verdreifacht, die Rauheit sank nicht. Der
Q-Fix bleibt eine eigenständig belegte Korrektur (Mack 2013 Gl. 8/10, φ_PAG steckt in C,
Doppelzählung), löst aber das Rauschproblem nicht. Nicht umgesetzt.

### 2. Analytische Vorhersage: Blur-Länge gegen Pitch

`σ_diff = √(2·peb_D·t_bake) = √(2·3,3·60) = 19,9 nm`, plus `se_blur_nm = 5,0` →
`σ_tot = 20,5 nm` bei Pitch 44 nm. Gauß-MTF bei der Grundfrequenz:
`exp(−2π²σ²/P²)` = **1,4 %** Restkontrast (linear). Derselbe Blur dämpft unkorreliertes
Voxelrauschen nur ∝ 1/σ. Also `LWR ∝ (1/σ)·exp(+2π²σ²/P²)` mit Minimum bei
**σ_opt = P/(2π) = 7,0 nm** (P=44) bzw. 10,2 nm (P=64). Vorhergesagte Verstärkung
19,9 nm gegenüber Optimum: Faktor 12 (linear, ohne Dill/Mack-Nichtlinearität).

### 3. Messung (Konfig C, exposure_stochasticity), CD konstant gehalten

`blur_diagnose_v2.py`: je σ zuerst Dosis-zu-Größe (CD=22, deterministisch, `se_blur_nm=5`
in **allen** Läufen — v1 hatte hier 0 vs. 5 gemischt und CD von 21,3 auf 15,5 driften
lassen; verworfen), dann LWR dort. grid=256, ler_grid_y=2048, 3 Realisierungen, Seed 42.

| σ_PEB | σ_tot | MTF | LWR [nm] | n_eff |
|---|---|---|---|---|
| 1,0 | 5,1 | 0,77 | 0,014 | 1104 (degeneriert, s. §5) |
| 3,0 | 5,8 | 0,71 | 5,00 | 51,8 |
| 5,0 | 7,1 | 0,60 | 2,95 | 25,6 |
| **7,0** | **8,6** | 0,47 | **1,78** | 19,8 |
| 9,0 | 10,3 | 0,34 | 1,85 | 14,9 |
| 12,0 | 13,0 | 0,18 | 2,01 | 12,4 |
| 16,0 | 16,8 | 0,057 | 4,50 | 12,5 |
| **19,9 (Default)** | **20,5** | 0,014 | **6,60** | 12,1 |

U-Kurve bestätigt, Minimum bei σ_tot = 8,6 nm (Vorhersage 7,0), **Default 3,7× über dem
Minimum**. Am Minimum liegt das LWR mit 1,78 nm **unter** dem Zielband 2,17–3,43 nm.
Gemessener Säure-Restkontrast nach PEB bei σ=19,9: 10 % (nicht 1,4 % — Dill-Sättigung
und tiefenaufgelöste Absorption regenerieren Kontrast; die lineare Formel ist im
Bereich σ_tot 7–15 nm quantitativ auf ±35 % richtig, an den Rändern nur qualitativ).

### 4. Falsifikation des Mechanismus (`mechanism_check.py`) — alle 4 Vorhersagen erfüllt

Wenn die Ursache Kontrastverlust ist, muss sie (a) für **jede** Rauschquelle gelten und
(b) mit dem Pitch skalieren:

- **Konfig A (nur Photonenrauschen, kein Quencher, keine Spikes), P=44**: LWR
  0,44 / 0,33 / 0,34 / 0,48 / 0,62 / 1,02 / 1,32 nm für σ_PEB 3/5/7/9/12/16/19,9.
  Minimum bei σ_tot = **7,07 nm** (Vorhersage 7,0). Default **4,0×** über dem Minimum.
- **Konfig C, P=64 (Default-Geometrie)**: Minimum bei σ_tot = 11,2 nm (Vorhersage 10,2),
  Default nur **1,8×** über dem Minimum — erklärt, warum das Problem bei der
  Default-Geometrie weniger auffiel.

Das ist der Kernbefund: **die Überrauheit ist keine Eigenschaft der PAG/Quencher-
Diskretheit, sondern der Blur-Länge relativ zum Pitch.** Jede Rauschquelle wird bei
σ_tot = 20,5 nm / P = 44 nm um ~4× verstärkt, weil der Kantengradient kollabiert und
Mack (n=18,2) den Restkontrast samt Rauschen wieder hochzieht.

### 5. Linke Flanke ist kein Physik-Effekt (`left_flank.py`, `mean_mismatch.py`)

Feinraster σ_PEB 1–5 mit Gitterkontrolle (grid 256 vs. 512, Linienlänge konstant):
LWR bei σ=2/3/5: 1,55/5,00/2,95 vs. 1,64/4,56/2,13 — gitterunabhängig auf ±10–30 %.
σ=1,0 und 1,5 sind degeneriert (n_eff 1104/235, LWR 0,014/0,18): **die stochastische
Realisierung entwickelt dort nirgends** (100 % unentwickelt, max. Tiefe 15,5 nm),
während der deterministische Lauf bei derselben Dosis 50,8 % freilegt. Erst vermutetes
Sättigungsartefakt des Sub-Pixel-Interpolanten ausgeschlossen (kein Bracket-Pixel
existiert). FFT/Direkt-Pfadwechsel von `gaussian_se_blur` bei kernel>64 ebenfalls
ausgeschlossen (Blur-Statistik glatt über die Schwelle, std 0,211→0,201).

`mean_mismatch.py` (je σ an der det. Dosis-zu-Größe, ler_grid_y=512, 1 Realisierung):

| σ | Pfad | ⟨acid⟩ vor PEB | ⟨quencher⟩ | ⟨acid⟩ nach PEB | ⟨M⟩ | entwickelt | CD |
|---|---|---|---|---|---|---|---|
| 1,0 | det | 0,155 | – | 0,155 | 0,534 | 50,8 % | 21,7 |
| 1,0 | photon | 0,157 | – | 0,157 | 0,531 | 50,7 % | 21,7 |
| 1,0 | expstoch | 0,158 | 0,248 | **0,157** | 0,621 | **0,0 %** | 44,0 |
| 7,0 | expstoch | 0,160 | 0,248 | 0,160 | 0,512 | 40,2 % | 26,3 |
| 19,9 | expstoch | 0,160 | 0,248 | 0,160 | 0,501 | 27,1 % | 32,1 |

Drei Befunde, alle σ-unabhängig belegt:
- **Der Quencher ist im Stochastik-Pfad faktisch inert**: er entfernt 0,3 % der Säure
  (0,158 → 0,157), obwohl ⟨quencher⟩ = 0,25 > ⟨acid⟩ = 0,16 im Mittelfeld die Säure
  vollständig neutralisieren würde. Ursache: `_reaction_limited_quench` wird auf
  Voxeln von 0,17×0,17×2,5 nm³ = 0,07 nm³ mit λ_PAG = 0,014 Molekülen ausgewertet —
  Säure und Quencher "treffen sich" nur, wenn beide Poisson-Ziehungen im selben Voxel
  landen (p ≈ 0,004). Ein Reaktionsvolumen unterhalb der Molekülgröße ist physikalisch
  bedeutungslos; Moleküle treffen sich durch Diffusion innerhalb der Bake-Zeit, nicht
  in einer Gitterzelle. Die "react-then-blur"-Reihenfolge aus Fortsetzung 6 hat die
  Diskretheit sichtbar gemacht, aber dabei den Quencher abgeschaltet; "blur-then-react"
  (das frühere Verhalten, Signal → 1e-21) war die *korrekte* Mittelfeld-Konsequenz der
  inkonsistenten Parameterlage 0,16 < 0,25 — genau das Dosisfenster-Problem, das der
  Q-Fix adressiert.
- **Der deterministische Pfad hat gar keinen Quencher.** Beide Pfade stimmen im
  Mittel überein (⟨acid⟩ nach PEB ≈ 0,16 in allen drei) — durch zwei verschiedene
  Fehler, nicht durch Konsistenz.
- **Das stochastische CD ist trotz gleichem Mittelwert um 4–22 nm gegen das
  deterministische verschoben** (26–44 vs. 22 nm), σ-abhängig, nicht monoton
  (Minimum der Abweichung bei σ 7–12). Ursache: Jensen-Ungleichung durch
  `M = exp(−k·A·t)` (konvex → ⟨M⟩ 0,62 vs. 0,53 bei σ=1) und durch die Mack-Rate
  (n=18,2, Schwelle M_th=0,39). Konfig A (Photon) ist dagegen unverzerrt (CD 20,8–21,7).
  Das ist die Erklärung für die P2-Nichtkonvergenz aus §1 und aus Fortsetzung 6:
  der Großzahlgrenzfall kann nicht konvergieren, weil die Verzerrung nicht vom
  Rauschen kommt, sondern von der Diskretisierung des Quenchings und der
  Nichtlinearität danach.

**Korrektur eigener Aussagen:** (a) v2s Spalte "CD_sto" war `r.cd_nm`, also das
deterministische CD — das stochastische CD war nie kontrolliert. (b) Die in v2
ausgewiesene Q3-Verstärkung "476×" beruhte auf dem degenerierten σ=1,0-Punkt; korrekt
sind 3,7× (Konfig C) und 4,0× (Konfig A) gegen das jeweils echte Minimum.

### 6. Quellenprüfung der Blur-Länge

- `peb_D = 3,3 nm²/s` wurde laut Kommentar (pipeline.py ~Z. 387) *gewählt*, damit
  σ = √(2Dt) ≈ 20 nm "inside Anderson's 17–35 nm Reference cluster" liegt — das ist
  eine Rückrechnung auf ein Ziel-σ, kein unabhängig gemessenes D für diesen Resist.
- **Anderson 2009** (lokal: `Anderson_2009_PhD_Thesis_EUV_Lithography_OSTI.pdf`):
  "blur" ist die Fit-Größe eines **HOST-PSF-Modells** (Houle et al., Ref. [28]),
  definiert als "the average *width* of the volume of resist polymer that is rendered
  dissolvable … by a single photo-generated acid" (Fußnote i, Kap. 5). **Die
  funktionale Form der PSF ist in der Dissertation nirgends angegeben; "Gaussian"
  kommt im Blur-Kapitel nicht vor.** Die Identifikation "Anderson-Blur = Gauß-σ" im
  Code-Kommentar ist aus der Quelle nicht belegbar. Andersons Werte gelten für
  50–100-nm-Strukturen (Kontaktloch-Metrik mit 50-nm-Löchern); 22 nm Blur bei 50-nm-
  Linien bezeichnet er selbst als "degrading" (Kap. 6.5). Seine Zusammenfassung sagt
  wörtlich, dass bei Blur groß gegen die Strukturgröße "LER reduction from improved
  counting statistics becomes dominated by an increase in LER due to reduced
  deprotection contrast" — exakt der hier gemessene Mechanismus.
- **Vesters 2019** (lokal), Kap. 1.5.5 und 3: zitiert D_acid "typically 1–10 nm²/s"
  und ADL "5–70 nm" für EUV-Resists, mit ADL = √(2·D·t) (1D-Bilayer-Definition → das
  ist ein Gauß-σ, die Formel im Code ist mit Vesters konsistent). Zugleich: für
  Half-Pitch < 20 nm "strong focus has been put in reducing acid diffusion length";
  "high acid diffusion length is detrimental to resolution and roughness". Gemessene
  laterale Säure-Diffusionsgeschwindigkeiten seiner 20-nm-HP-Resists: 2,5–17 pm/s
  (Tab. 3.2) — Kantenbewegung < 1 nm pro 60 s PEB.
- **Ergebnis: eine Quelle für σ_diff eines 22-nm-HP-EUV-CAR-Resists wurde nicht
  gefunden.** 19,9 nm liegt innerhalb der von Vesters zitierten Literaturspanne, ist
  aber für diesen Strukturmaßstab weder belegt noch — nach den Messungen oben —
  physikalisch haltbar (MTF 1,4 %).

### 7. Antwort auf die Auftragsfrage

Das Modell erzeugt zu viel Rauheit, weil die PEB-Diffusionslänge (19,9 nm, plus 5 nm
SE-Blur) beim Validierungs-Pitch 44 nm auf der steilen rechten Flanke der
Kontrastverlust-Kurve liegt, 2,4× über dem Optimum P/(2π) ≈ 7 nm. Der Kantengradient
kollabiert, die stark nichtlineare Mack-Entwicklung hebt Restkontrast und Rauschen
gemeinsam wieder an, und jede Rauschquelle erscheint ~4× verstärkt. Beim Optimum liegt
das Modell mit 1,8 nm (Konfig C) bzw. 0,3 nm (Konfig A) *unter* dem Zielband. Der Wert
19,9 nm ist eine Rückrechnung auf eine Anderson-Zahl, deren PSF-Form nicht dokumentiert
ist und die für 50–100-nm-Strukturen gemessen wurde.

Zweiter, davon unabhängiger Befund: der `exposure_stochasticity`-Pfad ist keine treue
stochastische Version des Mittelfeld-Pfads — Quencher faktisch inert (Reaktionsvolumen
unterhalb der Molekülgröße), deterministischer Pfad ohne Quencher, stochastisches CD
um 4–22 nm verzerrt. Das erklärt P2/P3 aus §1 und ist mit dem Q-Fix allein nicht behebbar.

### Offen — Entscheidung nach Stop-Regel erforderlich (physikkonsequent, mehrere Optionen)

Kein Code, kein Parameter geändert. Drei getrennte Baustellen, jede mit Optionen:
1. **σ_diff**: Quelle für den Validierungsmaßstab fehlt → als Kalibrierparameter
   deklarieren (nicht als Lavery/Anderson-Konstante) und gegen Vesters kalibrieren, ODER
   als Nutzerparameter mit ehrlichem "nicht literaturbelegt" belassen.
2. **Q-Fix**: eigenständig belegt, verschiebt Dosisfenster auf 10,5 mJ/cm²; erhöht das
   LWR am aktuellen σ (Photonen bei niedrigerer Dosis).
3. **Quenching-Diskretisierung**: Reaktion auf Diffusionsskala statt Gittervoxel auswerten
   und in *beiden* Pfaden konsistent anwenden — Modellentscheidung (welche Skala, welche
   Kinetik), keine mechanische Korrektur.

---

## 2026-09-04 (Fortsetzung 11): Phase 0 — Fundament (Dosisskala, Photonenzählung, Q, k_Q·G₀, tote Parameter) — und drei dabei gefundene Bugs

Mandat des Nutzers: „Folge deinem Plan … falsifiziere … baue keine hardcodierten Werte ein, die
die Physik zum Laufen bringen." Vorgehen je Punkt: Vorhersagen → Monkey-Test → Code → Invariantentest.

### 0.1 Dosis-Konvention (Audit A2) — umgesetzt

Primärquelle: Mack, *Inside PROLITH* (1997), Kap. 9: „Let E be the nominal exposure energy
(i.e., the intensity in a large clear area times the exposure time), I(x) the normalized image
intensity … the exposure energy as a function of position within the resist is just E·I(x)·I(z)."
Preflight (`preflight_dosenorm.py`, alle 5 Vorhersagen erfüllt): offene Maske → 1,000; aerial_threshold
CD/NILS bitgleich; full_chem CD(neu, 0,647·D) = CD(alt, D); Photon-LWR bitgleich bei gleicher
Wafer-Dosis; Dosis-zu-Größe P=44 → **15,04 mJ/cm²** (Vesters 8–16).
Code: `run_simulation` teilt das Hopkins-Bild durch |r_ML|² (TE; RCWA: TE/TM getrennt), neues
Ergebnisfeld `clear_field_reflectivity`, Guard gegen |r|²→0, `dose_mj_cm2` dokumentiert.
Tests: `tests/test_dose_convention.py` (offene Maske = Dosis; unabhängig von Spiegelverlusten;
Photonenzahl = D·A·f/E; RCWA = Dünnmaske im offenen Feld; Guard).

### Dabei gefunden: zwei RCWA-Bugs (beide vor diesem Tag in jedem `use_rcwa=True`-Lauf wirksam)

- **Ordnungs-Beschriftung um eins verschoben.** `torch.arange(-cfg.n_rcwa_orders // 2, …)`:
  Python-Floor-Division gibt für 11 Ordnungen die 12 Labels −6…5; die 0. Ordnung wurde als
  m = −1 abgebildet und von der TCC auf 0,692 gedämpft (offene Maske: 6,92 statt 10,0).
  Der alte Plausibilitätstest (`ratio in [0.5, 1.2]`) hat das toleriert. Fix: `solver.m`.
- **RCWA auf Wafer- statt Maskenskala.** Periode 64 nm → ±1. Ordnungen bei +18°/−6°, wo die
  Mo/Si-Bragg-Reflektivität 0,08 statt 0,65 beträgt (gemessen: 0°/6°: 0,647; 9°: 0,58;
  12°: 0,16; 18°: 0,08) → ±1-Asymmetrie **10,8×**. Auf Maskenskala (256 nm, ±1 bei +9°/+3°):
  1,19× (physikalische Abschattung). `constants.DEMAGNIFICATION` existierte, wurde nie benutzt.
  Fix: neues Feld `mask_demagnification = 4.0` (dokumentiert, 1D-x-Skala auch für High-NA
  korrekt), Gitter und Solver auf M·P. RCWA/Dünnmaske-Mittelwertverhältnis 0,82 → 0,95, CD
  25,16 → 27,46 (Dünnmaske 27,58). Das RCWA-Bild bleibt bei 6° asymmetrisch (Musterverschiebung
  ~3,8 nm) — Physik, nicht Bug; ein zunächst geschriebener Symmetrie-Test war falsch und wurde
  durch einen Maskenskalen-/Asymmetrie-Test (Grenze 2, Regime 5× getrennt) ersetzt.

### 0.2 Absorbierte Photonen (Audit A1) — umgesetzt

`absorption = 1 − exp(−(A+B)·t)` an `photon_deposition_shot_noise` durchgereicht (Mack/Biafore/
Smith 2011: n_abs = D·α·V/E_ph). Säulen-Gesamtstatistik exakt, Tiefenabhängigkeit des relativen
Rauschens nicht aufgelöst (dokumentiert). Tests: `tests/test_photon_absorption.py` (rel. Rauschen
= 1/√(N·η) für η = 1/0,25/0,05; Pipeline übergibt η; η konsistent mit Tiefenprofil).

### Dabei gefunden: `dill_B` wurde nie benutzt

`dill_abc_exposure` entpackte `B, H, W = dose.shape` — die Batchgröße (1) **überschrieb den
Dill-B-Parameter**: α = A + 1,0 µm⁻¹ unabhängig vom konfigurierten `dill_B`. Gefunden durch den
Konsistenztest η ↔ Tiefenprofil (erwartet 0,0564, gemessen 0,0535 → α = 1,10 = 0,1 + 1). Fix:
`n_batch`. Folge: alle bisherigen full_chem-Ergebnisse liefen mit α = 1,0 statt 1,06 (6 %), und
mein z-Diffusions-Monkey-Test in Fortsetzung 10 („dill_B = 8") lief faktisch mit B = 1 — sein
Null-Ergebnis ist damit nicht belastbar und wird in Phase 2 wiederholt.

### 0.3 Q-Doppelzählung (Audit A5) — `dill_Q` entfernt

`acid = 1 − M` (Mack 2013 Gl. 10; φ_PAG in C, Gl. 8). Feld, Validierung, drei Aufrufstellen,
CLI-Option, Kalibrier-Startwerte/-Grenzen, `sample_pag_quencher_acid`-Parameter entfernt;
Notebook 05 §10 von `dill_Q`- auf `dill_C`-Sweep umgeschrieben; Tests: Konfiguration **lehnt**
`dill_Q` ab (TypeError), Säureausbeute sättigt bei 1.

### 0.3b k_Q·G₀ (Audit A4-Einheiten) — umgesetzt

`reaction_diffusion_with_quenching` verlangt jetzt `pag_density` und rechnet intern
k_Q·G₀ = 15 nm³/s · 0,2 nm⁻³ = 3 s⁻¹ (Mack 2011, Z. 555 wörtlich). Test `tests/test_quench_units.py`
(geschlossene Form gegen k_Q·G₀; ≠ unkonvertiert; Erhaltung h−q; Gleichkonzentrationsfall 1/(1+h₀rt)).

### 0.4 Tote Parameter, Magic Numbers, ehrliche Fehler

- `resist_threshold` und `mask_sidewall_roughness_nm` (nie gelesen) entfernt, inkl. CLI.
- `nominal_dose = 20.0` (2×) → `AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2` mit Erklärung
  (Modelldefinitions-Konstante, keine Physik).
- Taper/Undercut: `pass` → `NotImplementedError` bei Nicht-Default (Mandat §12).
- `geometry.py`: hart codierte Mo/Si-n,k → CXRO-Tabelle; `eps_sub` als Bulk-Näherung dokumentiert.

### Konsequenz für den Arbeitspunkt — und eine falsifizierbare Vorhersage für Phase 1

Mit Wafer-Konvention und Säure bis 1 druckt der Yamamoto-Default die 32-nm-Linie (P=64,
se_blur 5) bei **≈5,7 mJ/cm²** (CD 34,0 bei 5,5; 27,5 bei 6,0), bei P=44 bei ≈7 — unter Vesters'
8–16. Das ist **kein** Anlass zum Parameterdrehen: der deterministische Pfad hat noch keinen
Quencher. Mack 2011 (Z. 468): „for the parameters of Table I, δ₀ = 0 requires a dose of
3.43 mJ/cm²" — die Dosis, die der Quencher neutralisiert. **Vorhersage:** Quenching konsistent in
beiden Pfaden (Phase 1) hebt die Dosis-zu-Größe um ≈3 mJ/cm² auf ≈9–10 (P=44) — ohne
Parameteränderung. Wird in Phase 1 vorab als Preflight geprüft.

Test-Arbeitspunkt der stochastischen Regressionstests deshalb von (implizit) 20 auf
`TEST_DOSE = 5.5` gesetzt (bei 20 ist die Linie weggebelichtet, LER = NaN); Golden-Werte neu
abgeleitet (reine Messung der Testkonfiguration, siehe Commit). Commit `e96b440`, gepusht.

---

## 2026-09-04 (Fortsetzung 12): Phase 1 — eine Chemie für beide Pfade; Quencher-Vorhersage widerlegt; Yamamoto-Anker

### Preflight (`preflight_phase1_quench.py`) — Q1 widerlegt, Q2/Q3 bestätigt

Modell: Operator-Splitting **diffundieren → reagieren** in beiden Pfaden (Mack 2011 Baseline
D_A = D_Q; für gleiche Diffusivitäten und vollständige Reaktion exakt max(blur(h₀) − q₀, 0)).
- **Q1 widerlegt in der Größe:** Mack-2011-Beladung (q₀/ρ_PAG = 0,25) verschiebt die Dosis-zu-Größe
  nicht um E(q₀) = 3,2, sondern um **+14,6 mJ/cm²** (P=44: 6,60 → 21,19; P=64: 5,62 → 19,40).
  Meine Abschätzung ignorierte, dass die Kante bei ~50 % Bildintensität liegt und der Mack-
  Schwellwert (M_th = 0,39 ↔ h ≈ 0,22) die nötige Säure festlegt; 0,25 abziehen verdoppelt die
  Säureanforderung an der Kante.
- **Q2/Q3 bestätigt:** LWR bei ρ_PAG = 0,2/2/20/200 nm⁻³: 7,48 / 1,90 / 2,12 / 2,31 nm — konvergiert
  gegen den Photonenboden, nicht gegen 0 (Photonenrauschen ist eine separate Quelle).

### Parameterklassen-Entscheidung: `quencher_density_per_nm3` Default 0,05 → **0,0**

Primärquelle Yamamoto et al. 2011, Table 2 („Calculation parameters of Polymer A on PROLITH"):
Rmax 68,6, Rmin 0,10, Mth 0,39, n 18,2, Ea 27,8 kJ/mol, ln(Ar) 6,1/s, A 0, B 1,06/µm, C 0,08997 —
**kein Quencher, keine Base.** Die im Code kombinierte Mack-2011-Beladung ist damit eine
Kombination zweier Resists ohne Quelle (Fortsetzung 7 fand keinen selbstkonsistenten Satz), und
sie wäre nach der Messung oben der dominante Parameter der ganzen Kette. Default 0 ist die einzige
mit Yamamotos Satz konsistente Wahl; sie bewegt die Dosis-zu-Größe **weg** von Vesters (6,6 statt
8–16) — also keine Anpassung an ein Ziel. Die Physik (Quencher in beiden Pfaden) ist vollständig
implementiert; wer einen selbstkonsistenten Satz hat, setzt die Dichte explizit.
Plausibilitätscheck ρ_PAG: Yamamoto nutzt 3,1 mol % PAG → ≈0,15 nm⁻³, konsistent mit Mack 2011 (0,2).

### Umsetzung

- `reaction_diffusion_with_quenching`: diffundieren → reagieren (Docstring mit Befund, warum
  „react first" den Quencher inert machte und warum „blur first" früher kollabierte: Q-Deckel +
  Dosisskala). Verlangt `pag_density`.
- Deterministischer Pfad und Photon-only-Pfad rufen dieselbe Funktion mit uniformem q₀ = ρ_Q/ρ_PAG.
- Neues Metadatum `stochastic_cd_nm` (mittlere Linienbreite der Realisierungen).
- `development_stochasticity=True` → `NotImplementedError` (A6); `development_strength`,
  `development_correlation_nm` entfernt; `stochastic_development` bleibt als experimentelle
  Einzelfunktion mit Funktionstests.
- Tests `tests/test_stochastic_consistency.py`: mit Photonen-Sampler = Erwartungswert konvergiert
  das stochastische CD für ρ_PAG → ∞ auf ±1 Pixel gegen das deterministische — **mit und ohne
  Quencher** (P2-Invariante aus Fortsetzung 6/10 erfüllt); Molekülrauschen → Photonenboden
  (±10 %); q₀ = 0 ⇒ PEB-Schritt bitgleich mit `reaction_diffusion_analytical`.
- Erste Testfassung war falsch: ρ → ∞ entfernt nur das Molekül-, nicht das Photonenrauschen; mit
  Photonenrauschen blieb ein Versatz von 2,5 nm (Jensen durch Mack-Nichtlinearität) — physikalisch,
  kein Bug; Test entsprechend umgebaut.

### Neuer Validierungsanker (offen): Yamamoto 2011 selbst

Yamamoto simulierte mit **genau diesem Parametersatz** in PROLITH 26- und 50-nm-L/S bei
**20, 25, 30 mJ/cm²** (σ = 0,5, Film 70/150 nm, PEB 110 °C/60 s, Entwicklung 30 s TMAH 2,38 %).
Unser Modell druckt mit demselben Satz (ohne Quencher) bei 5,6–6,6 mJ/cm² — **Faktor 3–5 zu
empfindlich gegenüber der Quelle der Parameter selbst.** Yamamotos PEB-Kinetik enthält eine
Reaktionsverzögerung T_d und eine **Säure-Lebensdauer τ** (Z. 512–514) — ein Säureverlust-
mechanismus, den unser `M = exp(−k·h·t)` nicht hat; PROLITHs Modell hat ihn. Das ist die
naheliegendste Erklärung und wird in Phase 4 gegen diesen Anker geprüft — nicht durch
Parameterdrehen, sondern durch Modellvervollständigung. Bedingungen, die schon stimmen:
PEB 110 °C/60 s (k = 446·e^{−27800/(8,314·383)} = 0,072 s⁻¹ = `peb_k`), Entwicklung 30 s.

---

## 2026-09-04 (Fortsetzung 13): Phase 2a — RCWA: drei Fehler in der Modenkopplung, gefunden über Erhaltungssätze

Ausgangspunkt war der geplante Wechsel des TM-Zweigs auf Li's inverse Regel (Audit B5). Der
Preflight (`preflight_rcwa_tm.py`) ergab, dass die Faktorisierungsregel **nicht** das Problem war:
Laurent und Li konvergierten gleich schlecht, und ein verlustfreies dielektrisches Gitter
(ε = 2,25/1, P = 200 nm, λ = 300 nm, d = 150 nm) verletzte die Energieerhaltung: R + T = 0,56 (TM),
1,004 (TE). Systematische Eingrenzung mit exakten Grenzfällen:

| Test | Erwartung | Befund (alt) |
|---|---|---|
| Homogene Schicht | = TMM, R+T = 1 | TE ✓, TM: R = TMM, aber R+T = 0,47 |
| Effektivmedium P ≪ λ (P = 20 nm) | TM → ⟨1/ε⟩⁻¹-Platte: R = 0,0296 | **0,209**, driftet mit M (0,22 → 0,13) |
| Gitter, d → 0 | Fresnel Vakuum\|Substrat: 0,0417 (TE) | **0,0336** |
| Rayleigh → Gittermoden → Rayleigh über d = 0 | = direkte Grenzfläche (basisunabhängig) | Abweichung 0,17 |

Ursachen (jede einzeln numerisch bestätigt, `rcwa_energy.py`, `preflight_rcwa_tm2.py`, Zufalls-Algebra-Tests):

1. **Redheffer-Sternprodukt mit vertauschten Resolventen** (`_redheffer_star_matrix`): S₁₁ nutzte
   (I − A₂₂B₁₁)⁻¹ statt (I − B₁₁A₂₂)⁻¹ (Push-through-Identität: (I−B₁₁A₂₂)⁻¹B₁₁ = B₁₁(I−A₂₂B₁₁)⁻¹).
   Für skalare Blöcke (TMM, homogene Schichten) kommutiert alles — deshalb blieben alle bisherigen
   Tests grün. Mit Zufallsmatrizen: Komposition zweier Grenzflächen durch eine beliebige Modenbasis
   weicht um 19 von der direkten Grenzfläche ab; korrigiert: 7·10⁻¹⁴, assoziativ. **Betraf jede
   RCWA-Rechnung mit Gitter, TE und TM.**
2. **TM-Formulierung**: Eigenproblem mit Laurent-Regel, Modenadmittanz V = [ε]WQ⁻¹, Rayleigh-
   Admittanz εk₀/k_z — für homogene Schichten zufällig konsistent, für Gitter falsch. Aus Maxwell
   (TM, H_y): ∂_z((1/ε)∂_z H) + ∂_x((1/ε)∂_x H) + k₀²H = 0 → A = [1/ε]⁻¹(I − K_x[ε]⁻¹K_x)
   (Li 1996; Lalanne & Morris 1996), V = [1/ε]WQ (E_x = (i/k₀)(1/ε)∂_z H_y), Y = k_z/(k₀ε).
3. **ML-Operator TM-Vorzeichen**: `optics.tmm` liefert den E-Feld-Koeffizienten; die RCWA-TM-
   Amplituden sind H_y, für die reflektierte Welle gilt r_H = −r_E. Leeres Gitter über dem
   Mo/Si-Stapel: ohne Vorzeichen |r₀|² 0,633/Phase −1,5° statt 0,639/−12,6°; mit: identisch.

Nach der Korrektur (`tests/test_rcwa_physics.py`, 12 Tests): Slab = TMM (TE/TM, 1e-8), Fresnel-Grenzfall
(1e-6), Effektivmedium TE 0,3 %/TM 1,2 %, Energieerhaltung R+T = 1 auf 2·10⁻⁶ (TE und TM, M = 11 und 41),
ML-Operator Betrag und Phase (1e-6), Sternprodukt basisunabhängig (1e-10). Die Toeplitz-Matrix
selbst war korrekt (gegen die analytische Fourierreihe des Rechteckprofils geprüft).

**Ehrlich zur Wirkung auf EUV-Masken:** Für das reale Ta-Gitter (schwacher Permittivitätskontrast,
ε_Ta ≈ 0,914 + 0,066i gegen 1) sind die Folgen klein: P = 64 nm: RCWA/Dünnmasken-Mittelwert 0,950 → 0,958,
CD 27,46 → 27,38 nm; P = 44 nm: Verhältnis 0,90, CD 13,19 (Dünnmaske 14,37). Die Fehler wurden erst an
Testgittern mit starkem Kontrast (ε = 2,25) groß — genau deshalb sind Erhaltungssätze als Tests
unverzichtbar: die bisherigen Plausibilitätstests (RCWA/Dünnmaske in [0,5, 1,2]) hätten sie nie gefunden.
`rcwa2d.py` (nicht in der Pipeline) enthielt dasselbe Sternprodukt und wurde identisch korrigiert.
Ein Test in `test_pipeline.py` verwendete als „analytische Schranke" Σ|Δ_i|²/4 statt der korrekten
(Σ|Δ_i|)²/4 (Cauchy-Schwarz über die Hopkins-Doppelsumme) — hielt nur, solange TE ≈ TM; korrigiert.

---

## 2026-09-04 (Fortsetzung 14): Phase 2b — Blur-Kernel war auf die Bildbreite geklemmt; ADI-Massenerhaltung; z-Diffusion; Eikonal-Druckbarkeit

### Der Blur-Kernel wurde stillschweigend abgeschnitten (nicht im Audit)

Beim Isotropie-Test der neuen z-Diffusion fiel auf, dass ein einzeiliges Feld lateral kaum geblurrt
wurde. Ursache in `gaussian_se_blur`: `kernel_size` wurde auf `min(H, W)` geklemmt (255 px beim
256-px-Gitter). Für σ_PEB = 19,9 nm bei dx = 0,172 nm (Kernel 695 px) heißt das: Abschnitt bei
±1,1σ, renormiert — keine Gaußfunktion mehr. Gemessen (Kosinus der Pitch-Frequenz, P = 44, 256 px):

| σ_PEB | Kernel | MTF Code (alt) | MTF exakt | Verhältnis |
|---|---|---|---|---|
| 5 | 175 px (FFT) | 0,779 | 0,775 | 1,00 |
| 7 | 245 px (FFT) | 0,611 | 0,607 | 1,01 |
| 10 | 351 → 255 px | 0,395 | 0,361 | 1,09 |
| 14 | 489 → 255 px | 0,229 | 0,136 | 1,69 |
| **19,9** | **695 → 255 px** | **0,122** | **0,018** | **6,9** |

**Konsequenzen:** (1) Jede Rechnung mit σ_PEB ≳ 7,3 nm bei Gitter 256 (P = 44) bzw. ≳ 10,6 nm (P = 64)
lief mit einem abgeschnittenen Kernel — der „Default 19,9 nm" hatte effektiv eine MTF wie ≈ 13 nm.
(2) Die σ-Skala der U-Kurve in Fortsetzung 10 ist für σ_PEB ≥ 9 nach rechts verzerrt; der Mechanismus
(Kontrastverlust ∝ exp(−2π²σ²/P²) gegen Rauschdämpfung ∝ 1/σ) und das Minimum bei P/(2π) bleiben,
die Verstärkungsfaktoren am Default sind mit exaktem Kernel **größer** (Neu-Messung unten).
(3) Mit exaktem Kernel bleiben bei σ_PEB = 19,9 nm 1,8 % Kontrast — die 22-nm-Linie bei P = 44 druckt
dann **bei keiner Dosis**, auch im Säulenmodell. Fix: kein Clamping; exakte periodische Faltung (FFT,
gewickelte Kernel-Taps akkumuliert) für alle Kernel > 64 px oder > Bildbreite; Abschneiden bei 4σ statt
3σ (MTF-Fehler 1e-4 statt 5e-3). `tests/test_blur.py` pinnt die analytische MTF exp(−2π²σ²f²) für
σ = 1…40 nm, Massenerhaltung, einzeilige Felder, FFT = direkt.

### ADI: Flussform statt Spiegelform

Meine erste „Korrektur" (Spiegel-Ghost auch implizit) machte es schlimmer (+2,7 % Masse): die Spiegel-
form hat Spaltensumme −1 und ist nicht konservativ. Konservativ ist die Flussform (1+α)A₀ − αA₁ mit
explizit A₁ − A₀ — jetzt beidseitig; `tests/test_peb_numerics.py`: Masse auf 1e-12 erhalten
(α = 2,5 / 10 / 0,5), Dirichlet verliert Masse. Der ADI-Löser ist nicht im Pipeline-Pfad.

### z-Diffusion (Audit B2) — umgesetzt

`reaction_diffusion_with_quenching(…, dz=…)`: derselbe Gauß entlang z, gesichtssymmetrische
Spiegelung (Ghost −k = f_{k−1}; nur diese erhält die Spaltensumme exakt — „reflect" um das Randsample
leckt Σ f_j k(j) − f₀ Σ k(k), gemessen +0,44 %). Pipeline übergibt dz an allen drei Aufrufstellen.
Tests: Spaltensumme 1e-12, σ ≫ Film → Tiefenmittel, Isotropie (σ_z = σ_x auf 5 %). Preflight vorher
(`audit_zdiff2.py`, noch mit geklemmtem lateralem Kernel): Dosis-zu-Größe −0,03 % (α = 1,06), −2,8 %
(α = 8 µm⁻¹).

### Eikonal-Druckbarkeit — ehrliches Ergebnis

Mit lateraler Entwicklung (`preflight_eikonal.py`, `preflight_eikonal_sigma.py`) ~~ist die 22-nm-Linie
bei P = 44 mit dem Yamamoto-Satz (Mack n = 18,2, R_max 68,6, 30 s) bei keinem σ_PEB ≤ 12 nm auf
22 nm druckbar~~ — **FALSCH, korrigiert in Fortsetzung 15:** der Scan hatte 2,5 mJ/cm² Schrittweite und
hat das ≈ 1 mJ/cm² breite Fenster übersprungen; P = 44/22 druckt mit σ_PEB ≤ 12 nm bei D2S 4,4–5,8.
Richtig bleibt: P = 64/32 nm druckt mit glattem Fenster (D2S ≈ 5,9–6,4), und das Säulenmodell hat
die Linie bei σ = 19,9 nm künstlich am Leben gehalten.

Neu-Messung P = 64/32 nm mit **exaktem Kernel + z-Diffusion + Eikonal** (CD [nm] gegen Dosis [mJ/cm²]):

| σ_PEB | 4,0 | 4,5 | 5,0 | 5,5 | 6,0 | 6,5 | 7,0 | 8,0 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 19,9 (Default) | 64 | 64 | 35,5 | 14 | 0 | 0 | 0 | 0 | 0 |
| 12 | 35 | 28,5 | 24 | 20,5 | 17,5 | 15 | 12,5 | 7,5 | 0 |
| 7 | 31,5 | 28,5 | 26 | 23,5 | 22 | 20,5 | 19 | 16,5 | 12,5 |
| 3 | 31,5 | 29 | 27 | 25,5 | 24 | 22,5 | 21,5 | 19,5 | 16,5 |

Mit dem Default σ = 19,9 nm existiert die 32-nm-Linie nur in einem Messerkanten-Fenster (5,0–5,5),
mit σ ≤ 12 nm in einem glatten Fenster. Das ist konsistent mit Yamamotos eigener Aussage, dass sein
Resist bei 26 nm L/S „considerable bridging" zeigte — ein 2011-Resist für ≥ 50-nm-Strukturen.
**Konsequenz:** `development_model = "eikonal"` ist jetzt Default (mit `"column"` als dokumentierter
Näherung); die stochastischen Regressionstests laufen an einem stabilen Arbeitspunkt
(σ_PEB = 7 nm, 4,0 mJ/cm²), und die Frage des Default-σ (Phase 3) ist damit nicht mehr Kalibrierung
gegen ein LWR-Ziel, sondern die Frage, welche Diffusionslänge zu welchem Resist gehört.

### U-Kurve neu gemessen (exakter Kernel, absorbierte Photonen, z-Diffusion; noch Säulenmodell)

`mechanism_check.py`, je σ an der eigenen Dosis-zu-Größe, Konfig A = nur Photonenrauschen:

| P = 44 nm, σ_PEB | σ_tot | D2S | LWR_A [nm] | | P = 64 nm, σ_PEB (Konfig C) | D2S | LWR [nm] |
|---|---|---|---|---|---|---|---|
| 3 | 5,8 | 6,57 | **3,07** | | 5 | 6,06 | 2,20 |
| 5 | 7,1 | 6,60 | 3,11 | | 7 | 5,89 | 2,17 |
| 7 | 8,6 | 6,61 | 3,53 | | 10 | 5,71 | 2,24 |
| 9 | 10,3 | 6,61 | 4,76 | | 14 | 5,64 | 3,35 |
| 12 | 13,0 | 6,60 | 8,47 | | 19,9 | 5,64 | 8,00 |
| 16 | 16,8 | 6,59 | 12,06 | | 25 | 5,65 | 13,17 |
| 19,9 | 20,5 | 6,59 | 10,65 | | | | |

Mit exaktem Kernel liegt das Minimum bei P = 44 am kleinsten gemessenen σ (5,8 nm), der Default ist
3,5× darüber (P = 64: 3,7×). Bemerkenswert: **reines Photonenrauschen** mit korrekter Absorption und
Dosis liefert bei P = 44 am Optimum ≈ 3,1 nm — am oberen Rand von Vesters' Band (2,17–3,43 nm) bei
6,6 mJ/cm²; Vesters' Resists arbeiten bei 8–16 mJ/cm² (mehr Photonen: 3,1·√(6,6/12) ≈ 2,3 nm).
Der Photonenboden ist also physikalisch dort, wo er sein sollte; die frühere „Überrauheit" war
die Summe aus geklemmtem Kernel, einfallenden statt absorbierten Photonen, falscher Dosisskala
und dem 19,9-nm-Blur.

### P = 44 nm mit exaktem Kernel + Eikonal — ~~druckt keine 22-nm-Linie~~ (FALSCH, siehe Fortsetzung 15)

`preflight_eikonal_sigma.py` (Dosis-Scan 1–60 in 25 Schritten = 2,46 mJ/cm² Schrittweite, Bisektion nur,
wenn ein Scanpunkt innerhalb 22 ± 6 nm lag) meldete σ_PEB = 1–9 nm als „nicht druckbar" (Scanpunkte
3,46 → CD 44; 5,92 → CD 14). **Das war ein Artefakt der Schrittweite:** der Feinscan (Fortsetzung 15)
zeigt zwischen 4,4 und 5,4 mJ/cm² eine stetige CD-Dosis-Kurve durch 22 nm. Was von diesem Absatz
bleibt: das Fenster ist schmal (CD 44 → 17 nm innerhalb von ≈ 1 mJ/cm² bei σ = 7), und die
Phase-3-Schlussfolgerung — keine unterbestimmte Anpassung von vier Mack-Parametern an zwei
Vesters-Zahlen, stattdessen `euv calibrate` auf Eikonal umstellen — gilt unverändert, jetzt mit
richtiger Begründung (Fortsetzung 15: Photonen-LWR am D2S ≈ 9 nm, Faktor 3 über Vesters, *und*
der Yamamoto-Satz reproduziert die Messungen seiner eigenen Quelle nicht).

### Nebenbefund: NILS im full_chem-Pfad war bedeutungslos

`_cd_via_full_chem` bewertete NILS an der Schwelle des aerial_threshold-Modells
(0,5·mean·20/Dosis) — bei 4 mJ/cm² liegt diese über dem Bildmaximum → NILS = 0 (die Golden-Ableitung
zeigte „NILS = 0.0000"). Jetzt: NILS = CD·|dI/dx|/I am Bildniveau der tatsächlich entwickelten Kante
(Mack 2007 §4.5), NaN ohne gedruckte Linie; `resist_threshold_norm` beeinflusst full_chem nicht mehr.
Ein Test hatte das alte Verhalten festgeschrieben („full_chem NILS must change with
resist_threshold_norm") — invertiert.

---

## 2026-09-05 (Fortsetzung 15): Zwei eigene Fehler korrigiert, ein Anker gekippt

### 1. „P = 44 nicht druckbar" war ein Scan-Artefakt

Der Feinscan (`scan_p44_low.py`, Gitter 256, se_blur 5, Eikonal, exakter Kernel) mit 0,1–0,2 mJ/cm²
Schritten — CD [nm] gegen Wafer-Dosis [mJ/cm²]:

| σ_PEB | 4,4 | 4,6 | 4,8 | 5,0 | 5,2 | 5,4 | 5,6 | 5,8 | 6,0 | 6,5 |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 22,7 | 21,0 | 19,6 | 18,2 | 17,2 | 16,5 | 15,5 | 14,8 | 14,1 | 12,7 |
| 7 | 44,0 | 28,9 | 24,1 | 21,0 | 18,9 | 17,2 | 15,8 | 14,8 | 13,4 | 11,0 |

Die Kurve ist stetig; die 22-nm-Linie existiert. `preflight_eikonal_sigma.py` hatte mit 2,46 mJ/cm²
Schrittweite (Scanpunkte 3,46 und 5,92) das Fenster übersprungen und dann gar nicht erst bisektiert.
Lehre, in die Memory übernommen: **nie „nicht druckbar" aus einem Scan schließen, dessen Schrittweite
größer als die erwartete Fensterbreite ist.** CHANGELOG, Memory und die beiden Absätze in
Fortsetzung 14 sind korrigiert (durchgestrichen, nicht gelöscht).

### 2. σ-Scan bei P = 44 mit Bisektion (`p44_sigma_scan_eikonal.py`)

Vorhersagen vorab: V1 D2S steigt monoton mit σ; V2 Photonen-LWR minimal bei kleinem σ, Anstieg
> 9 nm; V3 Dosis-Latitude wird mit σ schlechter. Messung (D2S durch 12-fache Bisektion in [3,5; 7],
CD bei ±5 % Dosis, LWR nur Photonenrauschen, 2 Realisierungen × 1024 Zeilen, Seed 42):

| σ_PEB | σ_tot | D2S | CD | CD(−5 %) | CD(+5 %) | LWR_Photon | n_eff |
|---|---|---|---|---|---|---|---|
| 1 | 5,1 | 4,38 | 21,7 | 24,1 | 20,3 | 8,98 | 10,2 |
| 3 | 5,8 | 4,48 | 22,0 | 24,1 | 19,9 | 9,09 | 10,1 |
| 5 | 7,1 | 4,67 | 21,7 | 24,8 | 19,6 | 9,87 | 8,9 |
| 7 | 8,6 | 4,94 | 21,7 | 26,1 | 19,3 | 10,49 | 7,7 |
| 9 | 10,3 | 5,27 | 22,0 | 29,9 | 17,9 | 12,16 | 6,6 |
| 12 | 13,0 | 5,80 | 21,7 | 44,0 | 13,4 | 12,62 | 5,7 |
| 15 | 15,8 | 6,23 | 22,0 | 44,0 | 2,1 | 12,85 | 11,6 |

V1, V2, V3 bestätigt. Ab σ_PEB = 12 nm liegt ±5 % Dosis außerhalb des Fensters (44 = Raum nicht
klar, 2 = Linie weg). n_eff 6–12 heißt: die LWR-Werte sind auf ≈ ±25 % genau — die Größenordnung
(9–13 nm) ist belastbar, die Nachkommastellen nicht.

**Zuordnung des 9-nm-Photonenbodens** (`p44_lwr_attribution.py`): Fortsetzung 14 hatte mit dem
Säulenmodell bei dessen D2S 6,57 ein Photonen-LWR von 3,07 nm gemessen. Vorhersage A (reiner
Dosis-Effekt): Säulenmodell bei 4,48 → 3,07·√(6,57/4,48) = 3,7 nm. Gemessen:

| Modell | Dosis | CD_det | LWR_Photon | n_eff |
|---|---|---|---|---|
| Eikonal, 4 Real., Seed 7 | 4,48 | 22,0 | **8,43** | 12,0 |
| Säule | 4,48 | 32,0 | 6,11 | 9,2 |
| Säule | 5,0 | 28,5 | 5,11 | 9,5 |
| Säule | 6,0 | 23,7 | 3,15 | 9,1 |
| Säule | 6,57 | 22,0 | 2,38 | 10,7 |

Vorhersage A **falsifiziert**: das Säulenmodell steigt bei sinkender Dosis viel steiler als √(1/E)
(2,4 → 6,1 nm), weil die gedruckte Kante bei kleiner Dosis auf dem flachen Fuß der Dosis-CD-Kurve
sitzt (dCD/dE ≈ 8,5 nm pro mJ/cm² bei σ = 3). Eikonal verschiebt das D2S von 6,6 auf 4,5 (laterale
Entwicklung frisst die Linie, also weniger Dosis für die Sollbreite) und verstärkt zusätzlich um
≈ 1,4× (6,1 → 8,4). Der Photonenboden von ≈ 3 nm aus Fortsetzung 14 war also eine Eigenschaft des
Säulenmodells an *dessen* Arbeitspunkt, nicht des Resists. Mit physikalischer Entwicklung liegt der
Yamamoto-Satz bei 22 nm HP bei D2S ≈ 4,5 (Vesters 8–16) und Photonen-LWR ≈ 9 nm (Vesters 2,2–3,4).
Beide Abweichungen zeigen in dieselbe Richtung: **zu wenig Photonen pro Kante** — d. h. der Satz ist
im Modell zu empfindlich für einen 22-nm-HP-Vergleich. Ob das am Satz oder am Modell liegt, klärt
Punkt 3.

### 3. Der „Yamamoto-Anker" (Fortsetzung 12) war falsch gelesen — und der richtige Anker kippt den Satz

Fortsetzung 12 nahm Yamamotos PROLITH-Dosen 20/25/30 mJ/cm² als Empfindlichkeitsanker („Faktor 3–5
zu empfindlich"). Neu gelesen (`2011_Yamamoto_JPST_Dissolution_Kinetics_EUV_Resist.pdf`, S. 409):
„The exposure dose is set to 20, 25, 30 mJ/cm²" — gesetzte Werte für Profilbilder, keine
Dosis-zu-Größe. **Kein Anker.** Was die Arbeit aber *misst* — am selben Resist (Polymer A, 35 %
Schutz, 3,1 mol % TPS-tf), bei derselben PEB (110 °C/60 s) und Entwicklung (2,38 % TMAH, 30 s):

- **Fig. 3** (FTIR, Flutbelichtung 1,4 mJ/cm², EQ-10M): Schutzgrad P(t) bei 110 °C fällt in ≈ 15 s
  auf ein Plateau ≈ 0,17; P(60 s) ≈ 0,18 (Ablesung ±0,03).
- **Fig. 5** (RDA-800EUV, Auflösungsrate gegen Flutdosis, log/log): 35 %-Kurve bei 0,1 nm/s bis
  0,65 mJ/cm², 1,5 nm/s bei 0,75, ≈ 60 nm/s ab 0,84 mJ/cm² (Achse kalibriert: 0,1 → px 362, 1 → px
  740; Ablesung ±10 % in der Dosis). Schwelle (R_max/2) ≈ **0,8 mJ/cm²**.

Unsere Kette mit Table 2 in Standard-Mack-Form (acid = 1 − e^{−C·E}, M = e^{−k·acid·t}, M₀ = 1 nach
Mack 1997 Gl. 5.33/5.34 — die Pipeline macht das richtig, `inhib_in_3d = ones_like`; mein erster
Testentwurf hatte fälschlich den PAG-Rest als M₀ genommen):

| Größe | Yamamoto gemessen | Kette (Table 2) | Faktor in k·C |
|---|---|---|---|
| P(60 s, 110 °C, 1,4 mJ/cm²) | ≈ 0,18 | 0,598 | 3,3 |
| Flut-Schwelle R_max/2 | ≈ 0,8 mJ/cm² | 2,75 mJ/cm² | 3,4 |

Zwei unabhängige Figuren, derselbe Faktor ≈ 3,4: **Table 2 reproduziert in unserer (und Macks)
Standardform die Messungen seiner eigenen Quelle nicht.** Erklärung im Paper selbst: Yamamotos
PEB-Kinetik (Gl. 1) hat einen Säureverlust-Term (K_loss/τ) und eine Reaktionsordnung m; die
FTIR-Kurven plateauen bei 0,17 (Säure verbraucht/verloren), was ein einfaches e^{−k·h·t} nicht kann.
Werte für K_loss, m, T_d sind nicht publiziert; Table 2 ist PROLITHs Übersetzung ohne diese Terme.
Das Kdp bei 110 °C aus Fig. 4 (Arrhenius-Plot, 35 %-Punkte, Achsen kalibriert: 1/T 0,0020 → px 350,
0,0035 → px 1330; log K 10 → px 75, 0,1 → px 815) liegt bei ≈ 1,4 s⁻¹ (Punkt bei 1/T = 0,002616 =
109 °C: K = 1,41; ±15 %) — Table 2 gibt 0,072 s⁻¹, **Faktor ≈ 19.** Die Steigung der 35 %-Punkte
(2,3 bei 119 °C → 0,11 bei 78 °C) ergibt Ea ≈ 84 kJ/mol ≈ 20 kcal/mol; Table 1 nennt 27,8 **kcal**/mol,
Table 2 „27,8 **kJ**/mol" mit ln(Ar) = 6,1 — die Table-2-Arrhenius-Paarung ist also PROLITHs
Ersatz-Parametrisierung, nicht das FTIR-Kdp (mit kcal wäre k bei 110 °C ≈ 10⁻¹³ s⁻¹). Damit ist die
Fortsetzung-12-Hypothese „uns fehlt τ" nur die halbe Wahrheit: mit Kdp ≈ 1,4 *und* τ ≈ 11 s wäre das
Plateau 0,17 erklärbar (e^{−1,4·0,118·11} = 0,16), mit Table 2 allein nicht — dort fehlt zuerst der
Faktor 19 in k, und der Faktor 3,4 in der Flutschwelle ist das, was davon nach Sättigung durch
M_th/n übrig bleibt.

**Konsequenz (keine Kalibrierung, keine Abkürzung):**
- Die *Form*-Parameter (M_th, n, R_max/R_min, B) bleiben die einzige komplette EUV-Quelle und
  Default. Die *absolute Dosisskala* des Default-Resists ist um mindestens Faktor 3,4 unsicher —
  in **beide** Richtungen kein Empfindlichkeitsanker mehr. So steht es jetzt im `dill_A`-Kommentar
  in `pipeline.py`.
- `tests/test_yamamoto_anchor.py`: beide Messungen als **`xfail(strict=True)`**-Tests kodiert. Sie
  schlagen heute aus dokumentiertem Grund fehl und schlagen als *unerwartet bestanden* an, sobald
  eine Modelländerung die Kette zur eigenen Quelle konsistent macht; ein dritter Test pinnt die
  heutigen Kettenzahlen (0,598 / 2,75), damit der Faktor nicht stillschweigend driftet.
- Ein Säureverlust-Term ohne publizierte Zeitkonstante wäre ein versteckter Knopf → **nicht**
  eingebaut. Wer Fig. 3/5 reproduzieren will, braucht Kdp und τ aus einer Quelle; Yamamoto liefert
  nur die Kurven.
- Vesters bleibt damit ein *Ziel* für einen 22-nm-HP-Resist mit eigenem Satz (`euv calibrate`,
  jetzt mit `--period/--cd/--grid/--se-blur`), nicht für den Yamamoto-Default.

### 4. Stand der Regressionsmodule

Notebooks 01–06 laufen mit dem Phase-2b-Code fehlerfrei durch (nbconvert, 6 × „Writing"). Die vier
Stochastik-Module (51 Tests) laufen zur Zeit erneut mit sichtbarer Zusammenfassung; der erste Lauf
hatte Exit 0, aber nur 28 Punkte und keine Summenzeile — das habe ich nicht als „grün" gewertet.

---

### 5. `euv calibrate`: Rauchtest findet einen Verdrahtungsfehler und eine Numerik-Grenze

Falsifikationsaufbau: synthetische FEM aus dem Modell selbst (P = 64/32, Gitter 64, se_blur 5,
σ_PEB = 7, Dosen 4,0/4,5/5,0/5,5 → CD 32/28/26/24), dann `euv calibrate` mit Startwert σ = 12 und
nur `peb_sigma_diff` als Fit-Parameter. Vorhersage: σ = 7 ± 1 wird wiedergefunden.

**Ergebnis 1 (Bug):** σ = 1,0, RMSE 6,56 nm. Spur mit gepatchtem `run_simulation`: die Pipeline
simulierte `line_width_nm = 24` — die Schleifenvariable `cd` des CSV-Loaders (`for d, f, cd in …`)
überschrieb die Typer-Option `--cd`; jeder Fit nahm die *letzte gemessene CD* als Sollbreite.
Fix in `cli.py` (Umbenennung, Kommentar), Regressionstest `tests/test_cli_calibrate.py` (CliRunner
mit Stub-Simulation prüft, dass `--period/--cd/--grid/--se-blur` unverändert ankommen und nur die
Parameter der Startwert-Datei gefittet werden). Vor 2026-09-04 war die Geometrie fest 64/32 —
der Bug war damit unsichtbar, weil `cd` gar nicht existierte.

**Ergebnis 2 (Numerik):** nach dem Fix σ = 11,4, RMSE 1,73 (42 Auswertungen). RMSE-Landschaft
direkt gemessen: σ ≤ 3 → 1,73; 5 → 1,00; **6–8 → 0,00**; 9 → 1,00; 10 → 1,41; 12 → 2,45. Das
Minimum existiert, aber die CD ist bei Gitter 64 auf 1 nm (= dx) quantisiert, das Objektiv ist
stückweise konstant, und Nelder-Mead mit 5 %-Anfangsschritt (0,6 nm) sieht von 12 aus nur ein
Plateau. Keine Optimierer-Kosmetik als Abhilfe (größerer Startsimplex würde das Symptom
verschieben); die richtige Stelle ist die CD-Extraktion: sub-pixel-Interpolation der
Entwicklungstiefe an der Kante, wie sie bei NILS schon gemacht wird. → nächster Preflight
(Vorhersage: CD bei Gitter 64 dann innerhalb ±0,5 nm der Gitter-256-Referenz; Fit findet 7 ± 0,5).

### 6. Preflight Sub-Pixel-CD: Tiefenkarte falsifiziert, Ankunftszeit bestätigt

Vorhersagen vorab (`preflight_subpixel_cd.py`, `preflight_subpixel_T.py`; P = 64/32, σ = 7,
se_blur 5, Dosen 4,0–5,5): P1 |CD_sub(Gitter 64) − CD_pix(Gitter 256)| ≤ 0,5 nm; P2 monoton,
Schritte < 1 nm pro 0,1 mJ/cm²; P3 |CD_sub(256) − CD_pix(256)| ≤ 0,25 nm.

**Variante A — Interpolation der Entwicklungstiefe** (wie im Stochastik-Pfad für LER): falsifiziert.
Sägezahn bei Gitter 64 (4,1–4,3: 30,80/30,79/30,66, dann 4,4: 30,00, dann 28,80), P1 in 10 von 13,
P2 in 4 Fällen verletzt. Grund: an der Resistflanke fällt die Tiefe innerhalb eines Pixels von
„durch + Überschuss" (52,5) auf einen Teilwert — die lineare Interpolation misst dort die zufällige
Teiltiefe des Nachbarpixels, nicht die Kantenlage.

**Variante B — Interpolation der Ankunftszeit T auf der untersten Schicht** (Eikonal): bestätigt.
T wächst hinter der Kante linear mit ≈ 10 s pro Pixel (Front im unbelichteten Resist mit
R_min = 0,1 nm/s), die Kreuzung T = t_dev ist also die Strecke, die die laterale Front in den
Nachbarpixel eingedrungen ist — erster Ordnung exakt.

| Dosis | CD_pix(64) | CD_T(64) | CD_pix(256) | CD_T(256) |
|---|---|---|---|---|
| 4,0 | 32,00 | 31,65 | 31,50 | 31,42 |
| 4,2 | 30,00 | 30,33 | 30,00 | 30,07 |
| 4,4 | 30,00 | 29,14 | 29,00 | 28,87 |
| 4,6 | 28,00 | 28,06 | 28,00 | 27,78 |
| 4,8 | 28,00 | 27,06 | 26,50 | 26,78 |
| 5,0 | 26,00 | 26,14 | 26,00 | 25,84 |
| 5,5 | 24,00 | 24,08 | 23,50 | 23,77 |

CD_T(64) ist monoton und glatt (Schritte 0,45–0,6 nm pro 0,1 mJ/cm²) und liegt in allen 13 Punkten
innerhalb 0,35 nm von CD_T(256). Gegen die *quantisierte* Referenz CD_pix(256) verletzen 3 Punkte P1
um ≤ 0,06 nm und 3 Punkte P3 um ≤ 0,03 nm — P1/P3 waren gegen eine Referenz mit ±0,25 nm eigener
Unschärfe formuliert; das ist kein Befund gegen die Methode, aber ich notiere es, statt die
Schwelle nachträglich zu verschieben. Umsetzung: CD des deterministischen Pfads aus T_unten
(Eikonal); das Säulenmodell hat keine laterale Information und bleibt pixelquantisiert
(dokumentiert).

**Umgesetzt:** `eikonal_development(..., return_arrival=True)`, neue Funktion
`edge_positions_from_arrival(T_row, t_develop, dx)` (periodisch, längster ungeklärter Lauf, NaN ohne
Linie/Raum), `_develop_depth(..., return_arrival=True)` liefert die unterste T-Schicht; der
deterministische Pfad nimmt die Sub-Pixel-Breite, wenn sie existiert, sonst die Pixelzahl; NILS
arbeitet weiter mit den Pixelindizes der Kante. Säulenmodell unverändert (pixelquantisiert).
Tests `tests/test_subpixel_cd.py`: exakte Kreuzung auf synthetischer Zeile, periodischer Umlauf,
Degenerationen, Monotonie/Glattheit bei Gitter 64, Gitter 64 vs 256 < 0,5 nm. 13/13 grün
(inkl. bestehender Eikonal-Tests).

**Rauchtest nach Sub-Pixel-CD:** `euv calibrate` (Start σ = 12, 36 Auswertungen) findet
**σ = 7,51 nm, RMSE 0,30 nm**. Vorhersage war 7 ± 0,5 — um 0,01 verfehlt, und zwar aus einem
benennbaren Grund: die synthetische FEM wurde *vor* der Änderung mit pixelquantisierten CDs
(32/28/26/24) erzeugt, gegen die eine glatte Kurve nicht exakt bei 7 liegen kann. Kein
Nachjustieren der Schwelle; mit einer glatten FEM wäre der Test zu wiederholen (offen, klein).

### 7. Regression der Stochastik-Module: OOM-Kill gefunden und behoben

Die ersten zwei Läufe der vier Stochastik-Module endeten nach 28 Punkten ohne Summenzeile bei
Exit 0 — der Exit-Code war der von `tail` in der Pipe, nicht der von pytest. Einzeln mit echtem
Exit-Code: `test_stochastic_pipeline` 5/5, `test_development_stochasticity` 9/9,
`test_ler_production_integration` **Exit 137 (SIGKILL)** bei `test_arbitrary_n_rows[61440]`,
auch allein (Peak-Footprint 43,7 GB auf einer 8,6-GB-Maschine). Speichersonde (`memprobe.py`,
Feld 21 × 4096 × 256, 0,18 GB): PEB-Schritt 2,0 GB, Eikonal 2,1 GB Zusatz — je ≈ 11× Feldgröße;
bei 61440 Zeilen (2,6 GB Feld) also ≈ 30 GB pro Schritt. Ursache: Phase 2b hat die PEB auf 3D
(z-Blur) und die Entwicklung auf die 3D-Eikonal-Front gehoben, beides auf dem vollen Stapel.

**Behebung ohne Ergebnisänderung:** (1) Eikonal zeilenweise in Blöcken (`chunk_rows`, bitweise
identisch, Test); (2) xy-FFT-Blur schichtweise, z-Blur zeilenweise (bitweise identisch bzw.
5e-15); (3) die verrauschte Kette Belichtung → PEB → Entwicklung läuft in y-Kacheln (1024 Zeilen)
mit periodischem Halo = 4σ/dx + 1 Zeilen (`pipeline._noisy_depth_map`). Exaktheitsargument: alle
Schritte sind punktweise, spaltenweise (z-Blur, Beer-Lambert), zeilenweise (Eikonal) oder die
bei 4σ abgeschnittene zirkuläre Faltung — mit Halo ≥ Radius erhalten die Innenzeilen einer Kachel
genau die Beiträge der Vollfeld-Faltung. Gemessen (`tests/test_stochastic_chunking.py`,
1536 Zeilen, 1 Kachel vs 3): max|Δdepth| < 1e-9, LWR identisch auf 1e-9. Für gesampelte Moleküle
zieht jede Kachel aus einem eigenen, einmal aus dem Lauf-RNG geseedeten Generator, damit die
Halo-Zeilen dieselben Moleküle tragen wie als Innenzeilen — eine Realisierung, unabhängig von
der Gruppierung. Felder ≤ 1024 Zeilen bleiben eine Kachel direkt aus dem Lauf-RNG (Goldens
unverändert). Nach der Änderung: PEB 1,5 GB, Eikonal 1,1 GB Zusatz bei 4096 Zeilen — und die
Kette sieht nie mehr als ≈ 1024 + 2·Halo Zeilen. 61440-Test läuft erneut mit Speichermessung.

**Konsistenztests:** `test_large_number_limit_has_no_roughness_without_photon_noise` (LWR < 0,1 px
bei ρ = 2000) war mit 0,0172 gegen 0,0172 nur um 0,0002 nm bestanden — der Rest ist Molekül-
rauschen, kein Interpolationsrauschen. Messung mit Photonen-Sampler = Mittelwert (`rho_scaling.py`,
P = 44, D2S 4,94): LWR = 2,55 / 0,557 / 0,232 / 0,088 / 0,017 nm für ρ = 0,2 / 2 / 20 / 200 / 2000 —
Faktor 150 über vier Dekaden, ρ^(−1/2) erwartet 100. Test umgeschrieben auf dieses Skalengesetz
(Faktor 5–20 pro zwei Dekaden). `test_molecular_noise_vanishes_to_photon_floor` verlangte
„sparse > dense" mit Photonenrauschen: 10,08 vs 10,83 nm — die Molekülkomponente (2,5 nm) addiert
sich quadratisch zu +3 %, unter der Streuung des Schätzers bei n_eff ≈ 9; die Ordnung ist mit
Photonenrauschen nicht prüfbar und wird nicht mehr behauptet. Geblieben: dense ≈ photon_only
(gleicher Seed) auf 10 %.

**Ergebnis:** `test_arbitrary_n_rows[61440]` allein: **bestanden in 312 s, Spitzen-RSS 1,82 GB**
(vorher 43,7 GB Footprint, SIGKILL). Konsistenzmodul nach Umschreibung 5/5.

**Rauchtest mit glatter FEM (nach Sub-Pixel-CD erzeugt: 31,65/28,59/26,14/24,08):** `euv calibrate`
ab Start 12 → **σ = 7,0000, RMSE 0,000** (38 Auswertungen). Vorhersage 7 ± 0,3 bestätigt; die
Abweichung 7,51 zuvor war die Quantisierung der alten Zieldaten.

### 8. Nacharbeiten

- `tests/test_cli_commands.py`: `version`, `info`, `materials`, `make-mask` (GDS mit 3 Polygonen),
  `process-window` (Gitter 64, 3×3) — Audit E7 (7/8 Kommandos ungetestet) abgearbeitet; `serve`
  und `bench` bewusst nicht.
- Säulenmodell-Test in `tests/test_subpixel_cd.py`: läuft, CD ≥ Eikonal-CD (keine laterale
  Auflösung), bleibt dx-quantisiert.
- Audit E8 (`dx` vs `dx_nm`, 16 gegen 7 Signaturen): alle `dx` sind Nanometer; eine
  Massenumbenennung öffentlicher Parameter ist kosmetisch und bleibt offen.
- Notebooks 01–06 nach Sub-Pixel-CD und Kachelung erneut ausgeführt (6 × „Writing", keine Fehler).

## 2026-09-05 (Fortsetzung 16): Lokale Vollprüfung („auf Herz und Nieren"), weil die CI steht

GitHub Actions ist seit 2026-08-31 durch das Ausgabenlimit blockiert (jeder Job endet nach ~10 s mit
der Billing-Annotation). Deshalb lokal alles, was die CI täte, plus Falsifikation der heute neuen Pfade.

1. **Lint (CI-Job „Lint & Type Check", nicht beratend):** `ruff check` fand 157 Befunde, `ruff format
   --check` 35 unformatierte Dateien — der Job war seit den Kommentar-Erweiterungen vom 2026-09-02/03
   gebrochen, unbemerkt, weil die CI nicht lief. Bereinigt: `ruff format` (35 Dateien), Auto-Fixes
   (Importreihenfolge, Docstring-Anführungszeichen), 33 überlange Zeilen per Skript umgebrochen
   (Trailing-Kommentare der `SimulationConfig`-Felder als vorangestellte Kommentarblöcke, CLI-Hilfetexte
   als Klammer-Konkatenation — Text byteweise identisch, per Assertion geprüft), toter
   `__main__`-Block in `test_full_chem_config.py` mit Aufruf einer gelöschten Testfunktion (F821)
   entfernt, ein Lambda zu `def`. Jetzt: „All checks passed", 101 Dateien formatiert.
2. **mypy --strict (in der CI `|| true`):** 140 Befunde in 24 Dateien, überwiegend Tensor/float-Unionen,
   komplexe Skalare in Tensor-Zuweisungen, untypisierte Defs. Durchgesehen: keiner ist ein
   Laufzeitfehler (z. B. `(None, None)`-Bounds sind für SciPy gültig). Nicht bereinigt — das wäre
   Typannotations-Arbeit ohne Physiknutzen; bleibt offen.
3. **Zwei echte Randfälle in heutigem Code gefunden und behoben** (vor dem Suite-Lauf): (a) in
   `_noisy_depth_map` konnte die letzte Kachel kürzer als der Halo sein (H kein Vielfaches von 1024)
   → weniger Halo-Zeilen als angenommen, Innenausschnitt verschoben; jetzt gleichmäßige Verteilung
   auf floor(H/1024) Kacheln, jede ≥ Halo; Test mit H = 1300 (2 × 650) bitgenau bis 1e-9 gegen
   ungestückelt. (b) `edge_positions_from_arrival` bei T = ∞ im Nachbarpixel (nur bei R = 0
   möglich): Kante auf die Pixelfläche statt Division durch ∞.
4. **Paketbau (CI-Job „Build"):** `uv build` → Wheel + sdist 1.0.3 fehlerfrei.
5. **Python-Matrix:** lokal läuft 3.14; CI testet 3.10–3.13. Frisches 3.10-venv (uv, torch 2.14):
   schnelle Suite **825 bestanden, 2 xfail** — keine 3.10-Inkompatibilität in den heutigen Annotationen.
6. **CLI Ende-zu-Ende:** `euv simulate --resist-model full_chem --grid 128 --dose 4.0 --peb-sigma-diff 7
   --se-blur 5` → CD 31,49 nm, NILS 3,93 (Sub-Pixel-CD sichtbar: keine Ganzzahl mehr).
7. **Volle Suite mit `-n auto` und echtem Exit-Code** (alle 4 Stochastik-Module inklusive
   61440-Zeilen-Test): siehe Zeile unten.

**Ergebnis volle Suite (`pytest tests -n auto`, Exit 0): 876 bestanden, 2 xfail (Yamamoto-Anker),
11 min 36 s.** Nach der Lint-Bereinigung zusätzlich die schnelle Suite unter Python 3.10 (825 + 2 xfail)
und die von der Umformatierung berührten Module (55 + 2 xfail) — die Umformatierung ist semantikfrei
(ruff format; Kommentar-/String-Umbrüche mit Byte-Identität geprüft).

## 2026-09-05 (Fortsetzung 17): Prüfung der vier Stochastik-Regressionsmodule

Auf Wunsch des Nutzers alle 51 Tests in `test_stochastic_pipeline`, `test_development_stochasticity`,
`test_ler_production_integration`, `test_stochastic_consistency` gelesen und gegen den heutigen
Code gestellt. Urteil: die geprüften Invarianten sind echt (Seed-Determinismus, Block-/Kachel-
Äquivalenz, Großzahl-Grenzwert gegen die deterministische CD, ρ^(−1/2), CD/NILS unverändert mit
Stochastik, Metadaten), keine Tautologien, Goldens als Regressions-Pins mit Herkunft.

**Zwei Vermutungen gemessen, eine falsifiziert:**
- Preflight `preflight_T_edges_lwr.py` — LER/LWR aus der Ankunftszeit-Kante statt der Tiefenkarte
  (Vorhersagen: Goldens-Konfiguration < 2 % Unterschied; reines Molekülrauschen bei ρ = 2000 mit
  Ankunftszeit *kleiner*, weil der Tiefen-Sägezahn wegfällt). Gemessen: (a) P = 64, σ 7, 4,0, 1024
  Zeilen: LWR 2,966 → 3,011 (+1,5 %), LER 1,852 → 1,871; (b) ρ = 2000, Photonen aus: LWR 0,0194 →
  0,0204, ρ = 20: 0,232 → 0,255. **(b) falsifiziert:** die Tiefenkarten-Interpolation trägt kein
  messbares Pseudo-Rauschen bei; der 0,02-nm-Boden ist Molekülrauschen. Kantenextraktion bleibt.
- Der von keinem Test berührte Pfad „mehrere Kacheln + gesampelter Quencher" läuft: P = 44,
  21 mJ/cm², ρ_PAG 0,2 / ρ_Q 0,05, 1300 Zeilen: eine Kachel stochCD 15,41 / LWR 2,13 (n_eff 12,7),
  zwei Kacheln 15,07 / 2,49 (13,3) — verschiedene Ziehungen per Konstruktion, gleiche Physik.

**Befunde und Umsetzung:**
1. Veraltete Texte: Modulkopf des LER-Moduls („N_eff ≥ 30 im Default", „Konvergenz ≤ 1 %" bei 4 %
   im Test), drei `dill_Q`-Kommentarblöcke, n_eff-Kommentar (17,8 statt Golden 30,3), Toleranz-
   begründung im Konsistenztest („deterministische CD pixelquantisiert"), `dill_Q=0.5` im
   Pipeline-Modul — alle ersetzt. `test_neff_ge_30` prüft jetzt den Default (4096 Zeilen, n_eff
   30,3) statt 8192.
2. „Pipeline-equivalent" für `_make_acid_large` war falsch: synthetische Kette (alle einfallenden
   Photonen, dose_to_acid C = 0,05, keine PEB, Schwelle 0,3). Modulkopf und Docstring sagen das jetzt;
   der Dosis-Skalierungs-Pin ist als Eigenschaft der Kunstkette benannt.
3. `dose_to_acid(Q=…)` (Default 0,04) war der überlebende Zwilling des entfernten `dill_Q` —
   im Quellcode ohne Aufrufer, in Tests mit Q = 1 bzw. kleinen Q. Parameter entfernt, Ausbeute
   1 − e^{−C·E}; sieben Aufrufer in vier Testdateien angepasst, `test_resist` 76/76 grün.
4. Redundante Zusicherung in `test_stochastic_produces_ler_lwr` → `isfinite and > 0`.

Laufzeit-Hinweis: 61440-Zeilen-Test ≈ 5 min (kritischster Posten für die CI-Matrix).

**Ergebnis nach Umsetzung:** die vier Module mit `-n auto` und echtem Exit-Code: **51 bestanden in
10 min 30 s (Exit 0)**; schnelle Suite nach der Q-Entfernung 825 bestanden + 2 xfail; Lint/Format sauber.

## 2026-09-05 (Fortsetzung 18): Literaturrunde 10 — was für euvsimulator daraus folgt

Auf Nutzerwunsch („mehr Fachliteratur, was uns noch fehlt, alle Sprachen, auch Patente, auch weitere Mack-Fits") eine
bedarfsgetriebene Suche; Katalog und Suchprotokoll in `/Users/flo/mack fits/` (Runde 10), ≈ 65 neue Dateien. Für den
Simulator unmittelbar relevant:

1. **Säureverlust ist messbar und gemessen:** Kang et al. 2010 (Macromolecules 43, 4275; NIST/Intel) fitten FT-IR-Kinetik
   mit kP, Trapping-Rate kT (0–0,05 s⁻¹) und DH (≈ 4,2 nm²/s bei 90 °C) für einen EUV-Resist (Rohm&Haas CM4R, PAG 1 %,
   H0 = 0,0129 nm⁻³). Das ist die Modellform, die unserer PEB fehlt (Fortsetzung 15, Yamamoto-Plateau). Kein Einbau ohne
   Preflight; aber jetzt gibt es eine Primärquelle mit Zahlen für die Diskussion.
2. **Zwei benannte EUV-CARs mit vollständigem Dill+Mack-Satz aus Messung** (Sekiguchi, InTech 2011, Table 6; LTJ-Methodik
   wie Yamamoto): MET-1K/MET-2D bei EUV: B 4,32/5,21 µm⁻¹, C 0,086/0,090 cm²/mJ, Rmax 221/170 nm/s, Rmin 0,039/0,028,
   Mth 0,624/0,518, n 12,65/18,96; PEB 110 °C/90 s, Film 125 nm. Die PEB-Arrhenius-Werte der Tabelle sind teils
   unphysikalisch (Diffusivität ln(Ar) = 30 „Rundwert"; Amplification-Ea 2–4 kcal/mol) — nur Dill/Mack belastbar.
   Folge: Yamamotos Dill B = 1,06 µm⁻¹ ist am unteren Rand; drei unabhängige Quellen (Sekiguchi, Fallica 2016/2017, Kang)
   liegen bei 4–5 µm⁻¹ für organische CARs. Das ändert die absorbierte Photonenzahl um ×4 — Kandidat für den nächsten
   Preflight (Photonenrauschen bei B = 4,3 statt 1,06).
3. **Dill C vs. Quencher gemessen** (Sekiguchi IEEJ 2013, Table 1): effektives C fällt von 0,128 (kein Quencher) auf 0,0228
   cm²/mJ bei Q/PAG = 0,75 — ein unabhängiger Test für unseren Quencher-Pfad (mittlere Säure nach Neutralisation).
4. **Resist-Blur direkt gemessen** (Langner 2010, PSI/imec/ASML): Ld = 14,5 nm (Fujifilm FEVS-P1101), NILS-korrigiert 11,8;
   Thackeray 2010: Gesamtblur 10,6–11,8 nm mit 2,5 nm EUV-spezifischem Anteil. Das rahmt unseren se_blur = 5 nm und den
   Default σ_PEB = 19,9 nm ein: 19,9 ist deutlich über allen gemessenen Blur-Längen benannter EUV-CARs.
5. **Rezepturen mit Wirkung:** Shin-Etsu-/JSR-Patente geben Quencher 4–9 pbw auf 100 pbw Polymer, EUV-Empfindlichkeit
   17–33 mJ/cm², LWR 3,2–4,5 nm (32-nm-L/S) — Umrechnung in ρ_Q (nm⁻³) über Molmassen möglich.
6. **Stochastik-Referenz aus der Industrie:** Samsung (Sci. Rep. 2025): 36-nm-Pitch, LWR 2,1 nm bei 40 mJ/cm² → 7,5 nm bei
   20 mJ/cm² (Materialstochastik dominiert). Vergleichsdatensatz neben Vesters.
Kein Code geändert.

## 2026-09-05 (Fortsetzung 19): Preflight Dill B — 1,06 µm⁻¹ (Yamamoto) gegen 4,32/5,21 µm⁻¹ (Sekiguchi MET-1K/2D)

Anlass: drei unabhängige Quellen (Sekiguchi InTech 2011 Table 6: 4,32/5,21; Fallica 2016: 4–5; Kang 2010: CM4R) setzen den
nicht-bleichbaren Absorptionskoeffizienten organischer EUV-CARs auf 4–5 µm⁻¹; Yamamoto Table 2 gibt 1,06. Es wird KEIN Code
geändert; `dill_B` ist Konfigurationsparameter. Vorhersagen vorab (Film 50 nm, se_blur 5, σ_PEB 7, Eikonal):
- **V1** absorbierter Anteil 1 − e^{−B·t}: 5,2 % → 19,4 % (4,32) → 22,9 % (5,21) — rein analytisch, dient als Kontrolle des Codes.
- **V2** Dosis-zu-Größe steigt mit B nur schwach (+3…+12 %): die Säureerzeugung hängt von der *einfallenden* Dosis ab
  (C·E), B wirkt nur über den Tiefengradienten (Fußbereich sieht e^{−B·t} = 0,81 statt 0,95 der Oberflächendosis).
- **V3** Photonen-LWR am jeweiligen D2S fällt mit B um den Faktor √(19,4/5,2) ≈ 1,9 (Bereich 1,6–2,2), weil nur absorbierte
  Photonen zum Schrotrauschen zählen und D2S sich kaum ändert. Bei 5,21: Faktor ≈ 2,1.
- **V4** Die LWR-Abhängigkeit vom Pitch bleibt: P = 44 weiterhin deutlich rauer als P = 64 (Faktor > 2), unabhängig von B.
Gemessen wird mit `preflight_dill_B.py` (P = 64/32 Gitter 128; P = 44/22 Gitter 256; Bisektion D2S; 2 Realisierungen × 1024
Zeilen, Seed 42, Photonen-only-Pfad).

**Ergebnis (`preflight_dill_B.py`):**

| P/lw | B [µm⁻¹] | absorbiert | D2S [mJ/cm²] | LWR_Photon [nm] | n_eff | stochCD [nm] |
|---|---|---|---|---|---|---|
| 64/32 | 1,06 | 5,2 % | 3,93 | 3,59 | 22 | 33,0 |
| 64/32 | 4,32 | 19,4 % | 4,55 (+16 %) | 1,04 | 19 | 31,9 |
| 64/32 | 5,21 | 22,9 % | 4,73 (+20 %) | 1,09 | 22 | 31,7 |
| 44/22 | 1,06 | 5,2 % | 4,94 | 10,49 | 7,7 | 26,2 |
| 44/22 | 4,32 | 19,4 % | 5,62 (+14 %) | 3,25 | 7,7 | 22,5 |
| 44/22 | 5,21 | 22,9 % | 5,83 (+18 %) | 2,41 | 7,8 | 21,8 |

- **V1 bestätigt** (Code rechnet 1 − e^{−B·t} exakt).
- **V2 mechanisch richtig, Bereich verfehlt:** D2S steigt um 14–20 %, vorhergesagt 3–12 %. Der Fehler war meine Abschätzung:
  der Fuß des Films sieht e^{−B·t}·(Oberfläche) = 0,81 statt 0,95, also braucht die Kette 0,95/0,81 = 1,17 mehr Dosis, damit
  die unterste Schicht klärt — genau die gemessenen +14…+16 % bei 4,32. Keine neue Physik, eine schlampige Zahl.
- **V3 in der Größe falsifiziert:** LWR fällt um Faktor 3,2–3,5 (4,32) bzw. 3,3–4,3 (5,21), vorhergesagt 1,6–2,2 aus √N.
  Erklärung, mit Messung belegt: bei B = 1,06 lag die Kette in einem nichtlinearen Rauschregime — die stochastische CD (26,2)
  wich um 4 nm von der deterministischen (22,0) ab (Jensen-Bias durch Mack-Nichtlinearität und laterale Entwicklung); mit
  4× mehr Photonen verschwindet der Bias (22,5 ≈ 22,0) und mit ihm die Zusatzverstärkung. LWR ∝ 1/√N gilt nur im linearen
  Regime; die Vorhersage hat das ignoriert. Bei n_eff 7,7 ist der P = 44-Wert auf ≈ ±25 % genau; die Diskrepanz zu 1,9 liegt
  weit außerhalb.
- **V4 bestätigt:** P = 44 bleibt 3,1× rauer als P = 64.

**Einordnung, ohne Kalibrierung:** mit B im Bereich der drei unabhängigen Quellen liegt das reine Photonen-LWR bei 22 nm HP
bei 2,4–3,3 nm (D2S 5,6–5,8 mJ/cm²). Das ist Vesters' Band (2,2–3,4) bei einer Dosis unterhalb von Vesters (8–16) — kein
Fit, kein Anker, aber ein Hinweis, dass die „Überrauheit" aus Fortsetzung 10 zu einem großen Teil ein falscher
Absorptionskoeffizient war. Nächste Schritte: (a) Streuung mit weiteren Seeds und Zwischenwert B = 2,5 messen, (b) B für
PHS-Polymere aus CXRO-Streufaktoren rechnen (erste Prinzipien statt Quellenvergleich), (c) erst dann über den Default entscheiden.

### Erste-Prinzipien-Kontrolle: Dill B aus CXRO-Streufaktoren (kein Quellenvergleich, reine Physik)

α = 4πβ/λ mit β = (r_e λ²/2π)·Σ_i N_i f₂,i (Henke/CXRO), f₂ bei 91,84 eV aus der projekteigenen CXRO-Datenbank
(`euvsimulator.materials`): C 0,766, H 0,033, O 2,765, S 1,130, F 4,273.

| Polymer | ρ [g/cm³] | α [µm⁻¹] |
|---|---|---|
| PHS (C₈H₈O) | 1,15 / 1,20 | 4,02 / 4,19 |
| PHS mit 35 % tBOC-Schutz (Yamamoto Polymer A, Annahme tBOC) | 1,15 | 4,25 |
| PHS-co-tBA 65/35 (NIST-Typ) | 1,20 | 4,43 |
| PMMA | 1,18 | 5,20 |
| Polystyrol | 1,05 | 2,95 |
| TPS-Triflat (PAG, rein) | 1,4 | 5,98 |

Befund: **Kein PHS-basiertes Polymer kann bei 13,5 nm einen Absorptionskoeffizienten von 1,06 µm⁻¹ haben** — selbst
sauerstofffreies Polystyrol liegt bei 2,95, und der Sauerstoffanteil des PHS treibt den Wert auf ≈ 4,0–4,4. Yamamotos
Table-2-Wert B = 1,06 ist damit nicht nur ein Ausreißer gegenüber Sekiguchi (4,32/5,21), Fallica (4–5) und Kang, sondern
physikalisch ausgeschlossen (mögliche Ursachen: PROLITH-Eingabe in anderen Einheiten, Absorbanz statt Koeffizient — nicht
aufklärbar). Konsequenz: der Default-B wird aus der Zusammensetzung des Default-Resists *berechnet* (PHS, 35 % geschützt,
ρ = 1,15–1,20 → 4,25–4,43 µm⁻¹) und als Funktion mit Test in `materials.py` hinterlegt, damit die Ableitung reproduzierbar
bleibt — keine Kalibrierung, keine Übernahme eines Fremdwerts. Die Dichte ist die einzige Annahme (Literaturbereich für PHS
1,15–1,2 g/cm³; Kang 2010 verwendet 1,2).

**Nachmessung mit weiteren Seeds (P = 44, `preflight_dill_B2.py`), Photonen-LWR [nm] (n_eff 6–8, je ±25 %):**
B = 1,06 bei D2S 4,94: 10,49 / 9,89 / 11,29 / 10,56 (Seeds 42/7/11/23) → Mittel **10,6**; B = 4,32 bei D2S 5,62: 3,25 / 5,85 /
5,17 / 2,72 → Mittel **4,25**, Streuung groß (stochCD 21,6–24,3, d. h. das nichtlineare Regime ist bei P = 44 noch nicht ganz
verlassen). Ehrliches Verhältnis: **≈ 2,5 (Bereich 1,8–3,9)**, nicht die 3,2 des Einzelseeds. Gegen V3 (1,6–2,2) bleibt das
knapp außerhalb, aber die Falsifikation ist schwächer als oben geschrieben; bei P = 64 (n_eff ≈ 20) steht der Faktor 3,45
belastbarer. Zwischenwert B = 2,0: D2S 5,12, LWR 7,9 — monoton.

**Umsetzung (2026-09-05):** `materials.linear_absorption_coefficient_per_um(composition, density)` (CXRO f₂, Henke-Formel;
Einheitenfehler r_e in Metern beim ersten Entwurf durch PMMA-Kontrolle gefunden: 0,052 statt 5,2), `pipeline.DEFAULT_RESIST_
COMPOSITION/DENSITY/DILL_B_PER_UM` (PHS + 0,35 tBOC, 1,20 g/cm³ → 4,44 µm⁻¹), Default `dill_B = 4.44` in `SimulationConfig` und
CLI, `tests/test_absorption_coefficient.py` (PMMA 4,6–5,6 als Literaturkontrolle, PHS-Familie 3,8–4,7, Polystyrol-Boden > 2,5,
Dichte-Linearität, Default = Herleitung ±0,02). Schnelle Suite mit neuem Default: 830 bestanden + 2 xfail — kein Test hatte
den alten Wert als Zahl gepinnt. Stochastische Goldens werden neu abgeleitet (Arbeitspunkt bleibt σ_PEB 7 nm, 4,0 mJ/cm²;
D2S bei P = 64 jetzt 4,55, die Linie druckt dort mit ≈ 34 nm). Zwischenwert aus der Nachmessung: B = 3,0 → D2S 5,33, LWR 7,3 nm.

**Neue Goldens (derive_goldens.py, σ_PEB 7, 4,0 mJ/cm², Seed 42, P = 64):** LARGE_N LER 1,4022 / LWR 2,3955 (vorher 2,3891 /
4,0033), n_eff 32,2, l_int 16,06 nm, ρ-Trunkierung 126, Legacy LER 0,3398 / LWR 0,5112 (vorher 0,8469 / 1,4741), CD 36,25 nm,
NILS 3,89. Alle Rauheitspins fallen um Faktor 1,7 (Großzahl) bis 2,5–2,9 (Legacy) — konsistent mit dem Preflight.

**Regression nach der Umstellung:** vier Stochastik-Module 50/51 — der Großzahl-Test [q = 0] fiel mit 0,36 nm (2,1 px) gegen
Toleranz 1,5 px. Ursache kein Physikfehler, sondern ein Extraktor-Mismatch: seit der Sub-Pixel-CD misst `cd_nm` die
Ankunftszeit-Kreuzung, die Realisierungen messen die Tiefenkarten-Kreuzung; beide unterscheiden sich für sich genommen um
bis zu ≈ 1 px (Preflight Fortsetzung 15). Der Test verglich also zwei Schätzer, nicht die Invariante. Umgeschrieben auf
Feld-gegen-Feld: gesampelte Kette (ρ = 0,2/20/2000, Photonen aus) gegen Mittelfeld-Kette auf denselben Kacheln, gleicher
Extraktor; Zusicherungen: Breite ≤ 0,5 px, mittlere Tiefenabweichung monoton fallend und < 0,1 px bei ρ = 2000, grobe
Schranke 3 px gegen `cd_nm`. 2/2 bestanden (99 s). Notebooks 03/05 riefen `dose_to_acid(Q=…)` — Q-Zeile entfernt.

## 2026-09-05 (Fortsetzung 20): Preflight Säureverlust — kann ein Lebensdauer-Term die Kette mit Yamamotos Messungen versöhnen?

Modellform (Yamamoto 2011 Gl. 1, „τ average acid lifetime"; Kang 2010 Trapping kT): Säure zerfällt erster Ordnung,
H(t) = H₀e^{−t/τ}; damit M(t) = exp(−k·H₀·τ·(1 − e^{−t/τ})), Plateau M∞ = exp(−k·H₀·τ). Kein Code wird geändert: die
Deprotektion wird per Monkey-Patch mit effektiver Reaktionszeit t_eff = τ(1 − e^{−t/τ}) gerechnet.

Messwerte aus Fortsetzung 15 (Ablesungen ±10 %): Fig. 3 (110 °C, 1,4 mJ/cm²): P(5 s) ≈ 0,60, P(10) ≈ 0,35, P(20) ≈ 0,22,
P(40) ≈ 0,18, P(60) ≈ 0,18; Fig. 4: Kdp(110 °C) ≈ 1,4 s⁻¹; Fig. 5: Flutschwelle (R_max/2) ≈ 0,8 mJ/cm².

Vorhersagen vorab:
- **V1** Mit Table-2-k (0,0723 s⁻¹) reproduziert **kein** τ die Fig.-3-Kurve: k·H₀ = 0,0085 s⁻¹ ist zu klein für den Abfall
  in 10–15 s; das Plateau 0,17 verlangte τ ≈ 200 s, dann läge P(60) bei ≈ 0,64. Säureverlust allein rettet Table 2 nicht.
- **V2** Mit k = 1,4 s⁻¹ (Fig. 4) und τ aus dem Plateau (k·H₀·τ = −ln 0,17 → τ ≈ 10,5 s) trifft die Kurve Fig. 3 in Form
  und Höhe: P(5) ≈ 0,5, P(10) ≈ 0,35, P(60) ≈ 0,17 (Abweichung < 0,1 an allen fünf Stützstellen).
- **V3 (der eigentliche Test, Fig. 5 ist von Fig. 3/4 unabhängig):** mit (k = 1,4, τ ≈ 10,5) verschiebt sich die
  Flutschwelle von 2,75 auf **0,6–0,9 mJ/cm²** (Handrechnung: M∞ = M_th bei 1 − e^{−C·E} = 0,94/14,7 → E ≈ 0,75).
- **V4** Bildseitig wird der Resist damit ≈ 3,5× empfindlicher: D2S bei P = 64/32, σ_PEB 7, Gitter 128 fällt von 4,55 auf
  **1,1–1,7 mJ/cm²**, und das Photonen-LWR steigt entsprechend (weniger Photonen) auf das 1,5–2-fache des heutigen Werts.
Konsequenz bei Bestätigung: die Kette *kann* die Primärmessungen reproduzieren, aber nur mit Kdp und τ aus den Figuren,
nicht mit Table 2 — also einem Parameterpaar, das im Paper nur grafisch vorliegt. Ob das in den Code kommt, entscheidet
sich an V3 und an der Frage, ob Kdp/τ als *Ablesungen* belastbar genug für einen Default sind.

**Ergebnis (`preflight_acid_loss.py`):**

| k [s⁻¹] | τ [s] | P(5) | P(10) | P(20) | P(40) | P(60) | max|Δ| zu Fig. 3 | Flutschwelle E_th [mJ/cm²] |
|---|---|---|---|---|---|---|---|---|
| 0,0723 (Table 2) | ∞ | 0,96 | 0,92 | 0,84 | 0,71 | 0,60 | 0,62 | 2,75 |
| 0,0723 | 10,5 | 0,97 | 0,95 | 0,93 | 0,92 | 0,91 | 0,74 | > 60 |
| 0,0723 | 200 | 0,96 | 0,92 | 0,85 | 0,73 | 0,64 | 0,63 | 3,25 |
| 1,4 (Fig. 4) | ∞ | 0,44 | 0,19 | 0,04 | 0,00 | 0,00 | 0,18 | 0,13 |
| **1,4** | **10,5** | **0,52** | **0,34** | **0,23** | **0,18** | **0,18** | **0,08** | **0,75** |

- **V1 bestätigt:** kein τ rettet Table 2 (Abweichung ≥ 0,62 an der Fig.-3-Kurve).
- **V2 bestätigt:** (k = 1,4, τ = 10,5) trifft alle fünf Stützstellen von Fig. 3 auf ≤ 0,08 — im Rahmen der Ablesegenauigkeit.
- **V3 bestätigt (der unabhängige Test):** Flutschwelle 0,75 mJ/cm² gegen Fig. 5 ≈ 0,8 (Vorhersage 0,6–0,9), ohne einen
  Parameter an Fig. 5 anzupassen; k allein (ohne τ) gäbe 0,13, τ allein ist wirkungslos — beide Terme sind nötig.
- **V4 bestätigt in der Richtung:** D2S bei P = 64/32 fällt von 4,55 auf **1,27 mJ/cm²** (Vorhersage 1,1–1,7); Photonen-LWR
  steigt von 1,04 auf 2,87 nm (Faktor 2,8, vorhergesagt 1,5–2 — erneut stärker als √N, gleiche Nichtlinearität wie in
  Fortsetzung 19).

**Bedeutung:** Die Kette in ihrer heutigen Form (Mack-Deprotektion + Säurelebensdauer erster Ordnung) reproduziert mit
zwei Parametern aus den Figuren des Papers (Kdp aus Fig. 4, τ aus dem Fig.-3-Plateau) die davon unabhängige Fig. 5. Damit
ist die Aussage aus Fortsetzung 15 („Table 2 reproduziert seine Quelle nicht") auf die Ursache reduziert: PROLITHs
Table-2-Arrhenius (0,072 s⁻¹, ohne Verlust) ist die falsche Übersetzung; die Physik des Papers ist konsistent.
Umsetzungsvorschlag (noch nicht ausgeführt): Konfigurationsfeld `peb_acid_lifetime_s` (None = kein Verlust, exakte
geschlossene Form über t_eff = τ(1 − e^{−t/τ}) für Deprotektion *und* Diffusionszeit), Default (k, τ) = (1,4 s⁻¹, 10,5 s) mit
Ablesungen als Quelle, die beiden strict-xfail-Anker werden zu echten Tests. Preis: der Default-Resist wird bildseitig
≈ 3,5× empfindlicher (D2S ≈ 1,3 mJ/cm² bei P = 64), das Photonen-LWR steigt entsprechend, Goldens erneut neu.

**Umsetzung (2026-09-05, Nutzerentscheidung „bau die Lebensdauer ein, (1,4 s⁻¹, 10,5 s) als Default"):**
`resist.peb.effective_reaction_time(t, τ)` = τ(1 − e^{−t/τ}); `reaction_diffusion_analytical` und
`reaction_diffusion_with_quenching` mit `acid_lifetime_s` (Deprotektion exakt, D·t-Diffusionslänge exakt, Neutralisation
gleiche Näherung); `SimulationConfig.peb_k = 1.4`, `peb_acid_lifetime_s = 10.5` (Validierung > 0 oder None), beide
Aufrufstellen der Pipeline, CLI `--peb-acid-lifetime` (0 = aus), Kalibrier-Startwert peb_k 1,4. Anker-Tests: die zwei
strict-xfails sind echte Tests (Fig.-3-Kurve an fünf Stützstellen ≤ 0,1; Schwelle 0,75 ± 0,03 gepinnt), plus Guard-Test,
der das Table-2-Paar mit 0,60/2,75 festhält. Test-Arbeitspunkte von 4,0 auf 1,1 mJ/cm² (P = 64) bzw. 1,55 (P = 44), Bisektion
ab 0,3; Sub-Pixel-Dosen 1,06–1,24. Neue Goldens (1,1 mJ/cm², Seed 42): LARGE_N LER 2,7350 / LWR 4,9579, n_eff 28,7
(→ n_eff-Test mit 8192 Zeilen), l_int 18,09, ρ-Trunk 198, Legacy 0,7931 / 1,5328, CD 36,61, NILS 3,87.

**Regression nach der Lebensdauer:** schnelle Suite 834/834 (keine xfails mehr); Stochastik-Module 48/51 — drei
Konsistenztests, deren Schranken Zahlen des alten Arbeitspunkts waren: (1) Großzahl-Grenzwert verlangte mittlere
Feldabweichung < 0,1 px bei ρ = 2000; am neuen Arbeitspunkt (D2S 1,5 statt 4,9 mJ/cm² bei P = 44 → 3,3× weniger
Säuremoleküle je Voxel) liegt sie bei 0,026–0,036 nm (0,15–0,21 px), die Konvergenz selbst ist intakt (3,7 → 0,22 → 0,03).
Schranke ersetzt durch die Invariante dev(2000) < dev(20)/5 (ρ^(−1/2) erwartet 10) plus grobe 0,3 px. (2) ρ^(−1/2)-Test:
Verhältnis sparse/mittel = 25 statt ≤ 20 — die ρ = 0,2-Realisierung hat 7,3 nm LWR an einer 22-nm-Linie und liegt im
nichtlinearen Regime (Mack-Schwelle + laterale Front verstärken nur); Obergrenze für das dünne Paar entfernt (Floor 5
bleibt), dichtes Paar unverändert 5–20 (gemessen 8). Beides physikalisch begründet, keine Zahl wurde an den Messwert
angepasst.
(3) Großzahl-Grenzwert mit Quencher (q = 0,25): Mittelfeld-Breite 25,4 nm gegen deterministische 22,0 — 3,4 nm, kein
Extraktor-Effekt. Ursache gefunden: die Pipeline rechnet k_Q·G₀ mit dem *konfigurierten* G₀; der Test skaliert ρ_PAG auf
2000 nm⁻³, um das Zählrauschen zu töten, und skaliert damit ungewollt die Neutralisationsrate um 10⁴. Vor der Lebensdauer
war das unsichtbar (bei 60 s Backzeit ist die Neutralisation auch bei G₀ = 0,2 vollständig: (h − q)·k_Q·G₀·t ≈ 18); mit
t_eff = 10,5 s ist sie es nicht mehr (≈ 3) — der Test verglich also eine vollständige mit einer unvollständigen
Neutralisation. Fix im Test, nicht im Code: Fixture pinnt G₀ = 0,2 nm⁻³ für die Rate in allen Aufrufen, die
Molekülzahl skaliert weiter. Physikalische Nebenerkenntnis: mit Säurelebensdauer ist die Quencher-Neutralisation in
diesem Resist ratenbegrenzt — ein Effekt, den das Modell jetzt trägt und der später gegen Sekiguchis Dill-C-gegen-
Quencher-Tabelle geprüft werden kann.

## 2026-09-05 (Fortsetzung 21): Preflight Quencher — Sekiguchi (IEEJ 2013) Dill C gegen Quencherbeladung

Messung (IEEJ Trans. FM 133(10) 500, japanisch; `mack fits/pdfs/jstage/IEEJ_2013_…`): EUV-Open-Frame-Belichtung (EQ-10M,
13,5 nm), Pseudo-Resist aus Acrylpolymer GMH (GBLMA/MAdMA/HAdMA 40/40/20) + 4 Gew.-% TPS-tf + Coumarin-6 (2× PAG-Molmenge)
als Säureindikator, Quencher mit 0 / 0,05 / 0,1 / 0,5 / 0,75 Mol pro Mol PAG, Film 100 nm (Messzelle 400 nm), PAB 100 °C/60 s,
**kein PEB** — die Neutralisation läuft bei Raumtemperatur während der Belichtung, Sekiguchi modelliert sie bimolekular
mit der Dosis als Zeitachse (Gl. 3/4, kq). Table 1: effektives C aus Fit [H⁺] = 1 − e^{−C·E}: **0,1280 / 0,1090 / 0,0982 /
0,0435 / 0,0228 cm²/mJ.**

Was prüfbar ist und was nicht: unsere Pipeline neutralisiert in der PEB mit k_Q·G₀·t_eff (Mack 2011, zweite Ordnung) —
andere Temperatur, andere Zeitachse; der *Wert* k_Q·G₀·t ist hier nicht testbar. Testbar ist die **Funktionsform** der
Neutralisation (bimolekular, Stöchiometrie H − Q) gegen die gemessene Quencherabhängigkeit des effektiven C, mit C₀ = 0,128
aus der q = 0-Zeile und derselben Fit-Prozedur (Least Squares von 1 − e^{−C·E} auf 0–40 mJ/cm²).

Vorhersagen vorab:
- **V1 (Stöchiometrie-Grenzfall, vollständige Neutralisation, A = max(H₀ − q, 0)):** effektives C fällt mit q, und zwar
  *stärker* als gemessen bei kleinen q (die Schwelle unterdrückt die Anfangssteigung komplett), Ordnung: C_eff(0,05) ≈
  0,10–0,11, C_eff(0,75) ≈ 0,02–0,03. Zahlen werden vom Skript vor dem Vergleich ausgegeben.
- **V2 (Sekiguchis/Macks bimolekulare Form mit endlicher Rate, ein freier Parameter kq·E-Skala, an q = 0,5 gefittet):**
  die übrigen drei Zeilen (0,05, 0,1, 0,75) werden auf ±15 % getroffen. Scheitert V2, ist die zweite-Ordnung-Form an dieser
  Messung falsifiziert — dann wäre auch unser PEB-Neutralisationsmodell fraglich.

**Ergebnis (analytisch, Fit-Fenster 0–40 mJ/cm², C₀ = 0,128):**

| q = Q/PAG | gemessen C_eff | V1 vollständig (H₀ − q) | V2 bimolekular, s an q = 0,5 gefittet (s = 1,27) |
|---|---|---|---|
| 0,05 | 0,1090 | 0,1052 | 0,1139 (+4 %) |
| 0,10 | 0,0982 | 0,0864 | 0,1010 (+3 %) |
| 0,50 | 0,0435 | 0,0223 | 0,0435 (Fit) |
| 0,75 | 0,0228 | 0,0079 | 0,0292 (+28 %) |

- **V1 falsifiziert:** vollständige Neutralisation unterschätzt das effektive C bei hoher Beladung um Faktor 2–3 — die
  Neutralisation ist auf der Zeitskala der Messung (Raumtemperatur, Belichtungsdauer) *unvollständig*. Das heißt auch:
  ein Modell, das Quencher als reine Stöchiometrie (H − Q) behandelt, wäre an dieser Messung widerlegt.
- **V2 teilweise bestätigt:** die zweite-Ordnung-Form (identisch mit Mack 2011 / `peb._reaction_limited_quench`) trifft
  mit einem einzigen Ratenparameter die Zeilen 0,05 und 0,10 auf 3–4 %, verfehlt aber 0,75 um +28 % (Schranke ±15 %).
  Die Form trägt also den Trend, aber bei hoher Beladung bleibt zu viel Säure übrig — Kandidaten: Neutralisation läuft
  nach der Belichtung bis zur Messung weiter (mehr Zeit bei hohem q wirksamer), oder Farbstoff/Quencher-Konkurrenz.
  Nicht auflösbar ohne Sekiguchis Rohkurven.
- **Folge für die Pipeline:** keine Codeänderung; der Ratenparameter ist bei PEB-Bedingungen nicht aus dieser Messung
  ableitbar. Als lokaler Test hinterlegt (`tests/test_quencher_sekiguchi.py`): die Pipeline-Funktion
  `_reaction_limited_quench` muss Sekiguchis Zeilen 0,05/0,10 auf 10 % und 0,75 auf 35 % reproduzieren, und der
  Stöchiometrie-Grenzfall muss *schlechter* sein — damit die Form und ihre bekannte Abweichung festgehalten sind.

## 2026-09-05 (Fortsetzung 22): Blur-Default — Befund vorab und Preflight

**Befund 1 (Nebenwirkung der Lebensdauer, bisher undokumentiert):** der Default-Blur wird aus D·t gebildet, und t ist seit
Fortsetzung 20 die effektive Zeit t_eff = 10,47 s. Damit ist der implizite Default nicht mehr 19,9 nm, sondern
σ = √(2·3,3·10,47) = **8,31 nm** — ohne dass D geändert wurde. Physikalisch richtig (Säure diffundiert nur, solange sie lebt),
aber die Herkunft von D = 3,3 nm²/s war eine *Rückrechnung* auf Andersons 19,9 nm bei t = 60 s; diese Begründung ist mit
der Lebensdauer hinfällig. D braucht eine eigene Quelle.

**Befund 2 (Quellenlage für D):** für Yamamotos Polymer A gibt es keine Diffusionsmessung. Nächste gemessene Verwandte:
Kang et al. 2010 (NIST), P(HOSt-co-tBA), FT-IR-Bilayer: **DH = 4,2 ± 0,3 nm²/s bei 90 °C** (Table 2; unabhängig von
Schichtdicke und PAG-Beladung 2/5 %). Arrhenius (Table 3, „A" ist ln A): ln A = 44 ± 8, Ea = 127 ± 25 kJ/mol — die
Extrapolation auf 110 °C ergäbe ≈ 60 nm²/s, aber ±25 kJ/mol entspricht einem Faktor ≈ 500; unbrauchbar als Default.
Direkte Blur-Messungen benannter EUV-CARs (Runde 10): LBNL-PSF σ ≈ 7,6 nm (MET-1K), Langner Ld 14,5 nm ≙ σ_Bild ≈ 10 nm
(FEVS-P1101), Thackeray 9,3–11,8 nm, Sekiguchi/PROLITH 10 nm — Band **≈ 7,5–12 nm**.

**Entscheidung, die geprüft wird:** D = 4,2 nm²/s (Kang 2010, gemessen, gleiche Polymerklasse, 90 °C; 110 °C-Wert
unmessbar/unbelegt) statt 3,3 (Rückrechnung). Mit t_eff = 10,47 s: σ = √(2·4,2·10,47) = **9,4 nm**. Kein Fit — die
unabhängige Kontrolle ist, ob 9,4 nm im Band der direkt gemessenen Blur-Längen liegt (ja: 7,5–12). Vorhersagen für den
Preflight (`preflight_blur_default.py`, D = 3,3 → 4,2, σ implizit 8,3 → 9,4, se_blur 5):
- **V1** D2S bei P = 64/32 (Gitter 128) ändert sich um < 10 %; bei P = 44/22 (Gitter 256) um < 15 % (mehr Blur → weniger
  Kontrast → etwas mehr Dosis).
- **V2** Photonen-LWR am jeweiligen D2S steigt um 5–25 % (σ_tot 9,7 → 10,6 nm liegt bei P = 44 jenseits des U-Kurven-Minimums
  ≈ 7 nm; bei P = 64 näher am Minimum ≈ 10 nm, daher dort kleinerer Effekt).
- **V3** Die 22-nm-Linie bei P = 44 druckt weiterhin (D2S existiert im Fenster 0,3–8 mJ/cm²).

**Ergebnis (`preflight_blur_default.py`, Photonen-only, 2 × 1024 Zeilen, Seed 42):**

| P/lw | D [nm²/s] | σ_PEB | σ_tot | D2S [mJ/cm²] | LWR_Photon [nm] | n_eff |
|---|---|---|---|---|---|---|
| 64/32 | 3,3 | 8,31 | 9,70 | 1,269 | 3,41 | 15 |
| 64/32 | 4,2 | 9,38 | 10,63 | 1,277 (+0,6 %) | 2,75 (−19 %) | 15 |
| 44/22 | 3,3 | 8,31 | 9,70 | 1,621 | 6,86 | 8,5 |
| 44/22 | 4,2 | 9,38 | 10,63 | 1,669 (+3 %) | 7,83 (+14 %) | 8,3 |

- **V1 bestätigt** (D2S +0,6 % / +3 %). **V3 bestätigt.**
- **V2 nur bei P = 44 bestätigt** (+14 %, im Bereich 5–25 %); bei P = 64 fällt das LWR um 19 % statt zu steigen. Bei
  n_eff ≈ 15 ist ±20 % die Streuung eines Einzelseeds, also kein belastbarer Gegenbefund — aber auch kein Anstieg: bei
  P = 64 liegt σ_tot = 10,6 nm nahe dem U-Kurven-Minimum P/(2π) = 10,2 nm, wo die Ableitung verschwindet; meine Vorhersage
  „5–25 % auch bei P = 64" war zu grob. Festgehalten als halb verfehlt.
- **Entscheidung:** D = 4,2 nm²/s (Kang 2010, Table 2, gemessen an P(HOSt-co-tBA) bei 90 °C) ersetzt die Rückrechnung 3,3.
  Damit ist der Default-Blur σ = 9,4 nm — im Band der direkt gemessenen Blur-Längen benannter EUV-CARs (7,5–12 nm), ohne
  daran angepasst zu sein. Bekannte Unsicherheit: Yamamotos PEB ist 110 °C, Kangs Messung 90 °C; die Arrhenius-Extrapolation
  ist mit ±25 kJ/mol unbrauchbar, daher bleibt der 90 °C-Wert mit dieser Einschränkung stehen (dokumentiert im Feldkommentar).

## 2026-09-05 (Fortsetzung 23): Vesters-Vergleich als Prüfung — mit dem vollständig belegten Default-Satz

Referenz: Vesters, Dissertation KU Leuven 2019, Table 4.2 (NXE3300, NA 0,33, 22 nm HP bei 44 nm Pitch, CD-SEM, LWR 3σ,
biased): Referenzresists ohne Sensibilisator **A0 = NXE1631: D2S 16,0 mJ/cm², LWR 7,4 ± 0,3 (3σ) ≙ 2,47 (1σ)**;
**B0 = NXE1716: 11,0 mJ/cm², 6,7 ± 0,3 ≙ 2,23** (Table 4.1; NXE1716 ist derselbe Resist, dessen Auflösungsratenkurve mit
Mack-Fit in JPST 30(6) 675 vorliegt); mit Sensibilisator 8–11 mJ/cm², 6,5–10,3 (3σ). Unser Default ist Yamamotos 2011er
Polymer A — ein anderer Resist; ein Fit findet nicht statt. Geprüft wird, ob die Photonenrausch-Größenordnung der Kette
mit einer Industriemessung bei 22 nm HP verträglich ist, wenn man die Dosisdifferenz herausrechnet.

Vorhersagen vorab (`preflight_vesters.py`, P = 44/22, Gitter 256, Defaults: σ_PEB 9,4, se_blur 5, B 4,44, k 1,4, τ 10,5):
- **V1** D2S_ours = 1,6–1,8 mJ/cm² (Fortsetzung 22: 1,669) → Faktor 6–10 empfindlicher als A0/B0. Erwartet, kein Ziel.
- **V2** Photonen-LWR (1σ) am D2S = 7–9 nm über mehrere Seeds (n_eff ≈ 8 je Lauf).
- **V3 (der eigentliche Test):** photonenstatistisch auf die Vesters-Dosen skaliert, LWR·√(D2S_ours/D2S_ref), liegt das
  Ergebnis im Bereich 1,6–3,7 nm (Faktor ≤ 1,5 um A0 2,47 / B0 2,23). Handrechnung: 7,8·√(1,67/16) = 2,5; ·√(1,67/11) = 3,1.
  Scheitert V3, ist die Rauschgröße der Kette um mehr als 1,5× von einer Industriemessung entfernt.
- **V4** Mit Molekülrauschen (ρ_PAG 0,2, kein Quencher) steigt das LWR am D2S um 10–30 % gegenüber Photonen-only.

**Ergebnis (`preflight_vesters.py`):** D2S_ours = **1,669 mJ/cm²** (CD 21,97). Photonen-only LWR (1σ) über drei Seeds:
7,83 / 10,21 / 10,50 → **Mittel 9,5 nm** (n_eff 6–8 je Lauf). Mit Molekülrauschen (ρ 0,2): 11,89 / 10,60 → 11,2 nm (**+18 %**).
Photonenstatistisch skaliert: auf A0 (16 mJ/cm²) **3,07 nm gegen 2,47 gemessen (Faktor 1,24)**; auf B0 (11 mJ/cm²)
**3,71 gegen 2,23 (Faktor 1,66)**.

- **V1 bestätigt.** **V4 bestätigt** (+18 %).
- **V2 verfehlt:** Mittel 9,5 nm statt 7–9 — der Einzelseed aus Fortsetzung 22 (7,8) lag am unteren Rand der Streuung;
  bei n_eff ≈ 7 sind ±25 % pro Lauf normal, drei Seeds streuen 7,8–10,5.
- **V3 halb bestätigt:** A0 innerhalb Faktor 1,5 (1,24), B0 knapp außerhalb (1,66). Beide Referenzwerte sind *biased*
  CD-SEM-Werte (SEM-Rauschen enthalten), die wahren Rauheiten liegen also niedriger — der Überschuss der Kette ist eher
  größer als 1,2–1,7. Zwei Gründe, die ohne den gleichen Resist nicht trennbar sind: (1) die √Dosis-Skalierung gilt im
  linearen Regime; bei 1,7 mJ/cm² arbeitet die Kette im nichtlinearen Verstärkungsregime (Fortsetzung 19/20), d. h. der
  skalierte Wert überschätzt; (2) Blur und Kontrast des 2011er Resists (σ_tot 10,6 nm) sind nicht die der NXE-Resists.

**Urteil:** kein grober Widerspruch mehr — vor Phase 2b lag die Kette um Faktor 3–4 über dem Band, jetzt liegt sie nach
Dosis-Skalierung um 1,2–1,7 darüber, mit erkennbaren, benannten Gründen. Das ist eine Plausibilitätsprüfung, keine
Validierung: dafür bräuchte es Dill/PEB/Mack-Parameter und LWR *desselben* Resists (NXE1716 wäre der Kandidat: Mack-Kurve
liegt vor, Dill/PEB nicht). Keine Codeänderung, keine Anpassung.

## 2026-09-05 (Fortsetzung 24): Stufe A1 — Säuren pro absorbiertem Photon als Invariante

**Herleitung:** dH/dE = C·G₀ im Kleindosis-Grenzfall (acid = G₀(1 − e^{−C·E})); absorbierte Photonen pro Volumen und Dosis
= N_ph·α mit N_ph = 1 mJ/cm² / E_ph = 6,8·10¹³ cm⁻² = 0,68 nm⁻² und α = 4,44·10⁻³ nm⁻¹ → 3,0·10⁻³ nm⁻³ pro mJ/cm².
Defaults (C 0,090, G₀ 0,2): **6,0 Säuren pro absorbiertem Photon**; mit Yamamotos 3,1 mol % (≈ 0,15 nm⁻³): 4,5.

**Messband (Primärquellen, Runde 10):** Brainard/LBNL „Film Quantum Yields of EUV & Ultra-High PAG Photoresists"
(OSTI 1004159), FQY = Säuren pro *absorbiertem* Photon: EUV-2D 2,08 (Fig. 2; Neumessung 1,94, Table 3), **MET-2D 1,39**,
XP-5496 1,45 (Table 3, 80-nm-Filme, PEB 130 °C); bei Ultra-hoch-PAG-Beladung steigt FQY etwa linear mit [PAG] (Fig. 5).
Kozawa (JPST 28(4) 501, Fig. 2): Quanteneffizienz ≈ 2,0 (anionengebundene Resists). Band für Standardbeladungen:
**1,4–2,1**, Obergrenze mit hoher Beladung ≈ 3.

**Befund:** 6,0 liegt um Faktor 3 über dem Band — C (Yamamoto/Sekiguchi, PROLITH-Fit) und G₀ (Mack 2011, anderer Resist)
sind nicht miteinander konsistent. Nebenbefund: LBNLs „corrected C-parameter" für MET-2D ist **0,0152 cm²/mJ**, Sekiguchis
PROLITH-C für denselben Resist **0,090** — Faktor 6; die beiden „C" sind offenbar verschieden definiert (LBNL bezieht C auf
die dichtekorrigierte Filmabsorbanz und den Clearing-Dose-Fit). Das ist für Stufe A2 die zentrale Frage: welches C gehört
zu unserem Modell acid = 1 − e^{−C·E} mit *einfallender* Dosis E.

**Umsetzung A1:** `pipeline.acids_per_absorbed_photon(cfg)`; `tests/test_acid_yield.py` mit strict-xfail auf das Band
[1,3; 3,0] (fällt heute mit 6,0) und einem Pin des heutigen Werts. Kein Default geändert — das ist A2.

## 2026-09-06 (Fortsetzung 25): Stufe A2 — Preflight „direkt gemessenes C" (Vorhersagen VOR dem Lauf)

**Befund aus den Quellen (vor jeder Code-Änderung):**
1. LBNL (OSTI 1004159) definiert C in Gl. (1) exakt in unserer Konvention: Säuren = [PAG]·(1 − e^{−C·E})·N_A mit E = einfallende
   Dosis; C wird per Base-Titration/Clearing-Dose bestimmt — eine *chemische* Messung der Säure gegen Dosis, unabhängig von
   der PEB-Kinetik. Table 3: **MET-2D (XP5271D) C = 0,0152 cm²/mJ**, XP-5496 0,0167, EUV-2D 0,046.
2. Sekiguchi Table 6 gibt für *denselben* MET-2D C = 0,090 (FT-IR-Deprotektion + PROLITH-Fit); Yamamotos Polymer A 0,08997.
   Faktor 6. Dass das PROLITH-C ein *effektiver* Parameter ist, zeigt Sekiguchi IEEJ 2013: C fällt mit Quencherbeladung
   (0,128 → 0,0435) — ein reines Belichtungs-C dürfte vom Quencher nicht abhängen.
3. Degeneration in unserem Modell: Deprotektion M = exp(−k·H·t_eff) mit H = 1 − e^{−C·E} ≈ C·E bei C·E ≪ 1. Yamamotos Fig. 3/4
   (Flood 1,4 mJ/cm²) bestimmen daher nur das Produkt k·H(1,4) = 1,4·0,1184 = 0,166 s⁻¹, nicht k und C getrennt. Mit
   C = 0,0152 folgt H(1,4) = 0,02105 und **k = 0,166/0,02105 = 7,87 s⁻¹** (kein neuer Freiheitsgrad — dieselbe Messung, anders
   aufgeteilt). Yamamotos „Kdp = 1,4 s⁻¹" ist eine Modellgröße *seines* C, keine C-unabhängige Beobachtung.
4. Aus LBNL Table 3 lässt sich [PAG] rückrechnen (FQY = C·[PAG]/(N_ph·(1−T)/d)): MET-2D ≈ 0,22 nm⁻³, EUV-2D ≈ 0,10 nm⁻³.
   Macks G₀ = 0,2 liegt also bei MET-2D innerhalb 10 % — G₀ bleibt.

**Vorschlag A2:** dill_C 0,08997 → **0,0152** (LBNL MET-2D, direkte Messung, unsere Konvention), peb_k 1,4 → **7,87 s⁻¹**
(k·H aus Yamamoto Fig. 3 erhalten), G₀ 0,2 unverändert. Ergibt FQY (Oberfläche, Kleindosis) = 1,01; LBNL-Stil (80-nm-Film,
T 0,71) = 1,24 vs. gemessen 1,39 (−11 %, erklärbar durch [PAG] 0,2 vs. 0,22).

**Vorab festgelegte, falsifizierbare Vorhersagen (Monkey-Patch C = 0,0152, k = 7,87):**
- V1 Yamamoto-Anker: P(60 s, 1,4 mJ/cm²) unverändert 0,18 ± 0,005; Fig.-5-Schwelle 0,73 ± 0,01 (Pin 0,75 ± 0,03 hält).
- V2 D2S (deterministisch, full_chem): P = 64: 1,277 → **1,20–1,26**; P = 44: 1,669 → **1,55–1,62** (Säure jetzt linearer,
  alte Sättigung −5,5 %/−7,3 % entfällt fast).
- V3 LWR nur Photonenrauschen, P = 44, 3 Seeds: Mittel innerhalb **±10 % von 9,5 nm** (Rauschen hängt nicht von C ab,
  nur die Steigung dM/dE bei D2S).
- V4 LWR Photonen + molekular (exposure_stochasticity), P = 44, 2 Seeds: Mittel **12–16 nm** (vorher 11,2; jetzt ≈ 1 Säure
  pro absorbiertem Photon → Säurezählrauschen vergleichbar mit Photonenrauschen).
- V5 `acids_per_absorbed_photon` = 1,01 ± 0,01; Bandtest [1,3; 3,0] fällt weiterhin (Definitionsunterschied Oberfläche vs.
  Filmmittel; LBNL-Stil 1,24).
Falsifikation: V2 außerhalb ±10 % oder V3 > ±15 % → Degenerationsannahme falsch, Vorschlag zurück.

**Preflight-Ergebnis (Monkey-Patch C = 0,0152, k = 7,87; scratchpad/preflight_C.py):**

| | Vorhersage | Messung | Status |
|---|---|---|---|
| V1 P(60 s, 1,4 mJ/cm²) | 0,18 ± 0,005 | 0,1765 | hält |
| V1 Fig.-5-Schwelle | 0,73 ± 0,01 | **0,764** | **Richtung falsch** (Pin 0,75 ± 0,03 hält) |
| V2 D2S P = 64 | 1,20–1,26 | **1,312** (+2,7 %) | **Richtung falsch**; Kriterium ±10 % hält |
| V2 D2S P = 44 | 1,55–1,62 | **1,718** (+2,9 %) | **Richtung falsch**; Kriterium ±10 % hält |
| V3 LWR Photonen, P = 44 | 9,5 ± 10 % | 9,77 (8,86/10,07/10,38) | hält |
| V4 LWR Photonen + molekular | 12–16 | 10,38 (8,65/12,11), +6 % | **falsifiziert / unterbestimmt** |
| V5 FQY Oberfläche | 1,01 | 1,007 | hält |

Fehleranalyse V1/V2: Ich hatte die Sättigungskorrektur gegen das *lineare* Gesetz gerechnet statt gegen den Ankerpunkt
1,4 mJ/cm², an dem k·H erhalten wird. Relativ zum Anker hat das neue (linearere) Modell bei der Kantendosis ≈ 0,76 mJ/cm²
**2,3 % weniger** Säure (alt: H(0,75)/H(1,4) = 0,5515; neu: 0,5387) → Schwelle und D2S steigen um 2–3 %. Alle drei Abweichungen
haben dieselbe Ursache und Größe; die Degenerationsannahme (nur k·H zählt bei C·E ≪ 1) ist damit bestätigt, meine Vorzeichen-
rechnung war falsch. V4: mit 2 Seeds à n_eff ≈ 8 ist jede LWR-Schätzung ±20 % unsicher (Seed 42 mit molekularem Rauschen
8,65 < 8,86 ohne — anderer RNG-Strom, also nicht „dasselbe Photonenrauschen plus Zusatz"). Der frühere Befund „+18 %"
(Fortsetzung 23) hatte dieselbe Schwäche. Ein Lauf mit 6 Seeds × 4 Realisationen × 2048 Zeilen für alt/neu wurde gestartet und
wegen Laufzeit (> 2 h, CPU-Konkurrenz mit der Golden-Ableitung) abgebrochen — wird nach der Suite mit kleinerer Statistik
nachgeholt. Vorregistrierung dafür bleibt: Überschussvarianz (molekular) neu/alt ≈ 5,6, falls binomiales Säurezählen dominiert.

**Entscheidung:** Kriterien V2 ±10 %/V3 ±15 % gehalten → umgesetzt: dill_C 0,0152, peb_k 7,87, CLI-Defaults, Pins in
test_acid_yield (1,007 Oberfläche; LBNL-Stil 80 nm 1,20; MET-2D-Nachrechnung 1,24 vs. 1,39 innerhalb 20 %), Table-2-Guard-Test
mit explizitem C = 0,08997. Zweite direkte C-Quelle gesichert: Fallica et al. 2017 (PSI/ARCNL, SPIE 10143; im Code bisher
falsch als „Kazazis" zitiert): 0,010–0,021 cm²/mJ, Bleaching-Methode. Goldens werden neu abgeleitet (derive_goldens.py).

**Suite nach A2:** zwei Testtoleranzen waren Zahlen des alten Betriebspunkts, keine Invarianten — beide skalieren mit der
Säurezahl pro Voxel (∝ C·G₀·E): `test_stochastic_chunking` (Mittelwertvergleich zweier Tilings, Toleranz 1 px bei C·G₀ = 0,18)
→ G₀ im Test 2,0 → 12,0 (gleiche Säurezahl, rein statistische Größe); `test_stochastic_consistency` absolute Schranke
0,3 px → 1 px (Erwartung 0,3·√(0,090/0,0152) = 0,73 px, gemessen 0,44 px). Alle Invarianten (Monotonie, ≥ 5× über zwei
Dekaden, Breite ±0,5 px) hielten unverändert. Golden-Werte neu: LER 3,490 (vorher 2,735) bei festem 1,1 mJ/cm² — reiner
Betriebspunkt-Effekt: alte Defaults bei dosisgleich skaliertem Punkt (1,0707) geben CD 37,7/LER 3,78, neue bei 1,1
CD 37,9/LER 3,49. Läufe: volle Suite 891 bestanden + 1 (die Schranke), danach das Modul allein 5/5, Chunking-Modul 4/4.

**V4b (nach Commit 076e0e1; scratchpad/preflight_V4b.py, 3 Seeds × 2 Realisationen × 2048 Zeilen, P = 44, G₀ = 0,2):**

| Satz | nur Photonen | + molekular | Verhältnis | Überschussvarianz |
|---|---|---|---|---|
| alt (C 0,090, k 1,4) | 9,78 ± 0,9 | 10,86 ± 0,6 | 1,11 | 22 nm² (± ≈ 20) |
| neu (C 0,0152, k 7,87) | 10,29 ± 0,04 | 12,32 ± 0,2 | 1,20 | 46 nm² (± ≈ 5) |

Vorregistriert war Überschussvarianz neu/alt ≈ 5,6 (binomiales Säurezählen ∝ 1/(C·G₀)); gemessen ≈ 2,0 — bei der
Unsicherheit des alten Werts (± 20 nm²) nicht scharf, aber 5,6 ist unwahrscheinlich. Für den neuen Satz ist der Befund
belastbar: molekulares Rauschen erhöht die LWR um ≈ 20 % (46 nm² Überschuss gegen ≈ 106 nm² Photonenvarianz), d. h. weniger
als die naive Zählstatistik erwartet (Säuren ≈ absorbierte Photonen im Blur-Volumen → Faktor √2 ≈ +41 %). Warum der
Binomial-Sampler weniger Varianz liefert als Poisson-Zählen der Säuren, ist **nicht verstanden** — kein Code geändert.
Offen für Stufe C (Multiplizität/Rauschmodell): Sampler gegen eine analytische Poisson-Erwartung auf einem uniformen
Feld prüfen (Varianz der Säurezahl pro Voxel und nach Blur), bevor exposure_stochasticity als Default diskutiert wird.

## 2026-09-06 (Fortsetzung 26): Stufe A3 — Sekundärelektronen-Blur-Default (Vorhersagen VOR dem Lauf)

**Quellen (alle PDFs im Katalog, Zahlen nachgeprüft):**
- Thackeray et al. (Dow), JPST 23(5) 631 (2010), Abschnitt 4/Gl. (8): EUV-Gesamtblur 11,5 nm (gemessen, 28-nm-Linien) =
  9,7 (Latentbild-RD) ⊕ 4,3 (Rg) ⊕ **2,5 (EUV-spezifisch)** ⊕ 3,7 (unerklärt). Die 2,5 nm sind der „average radius of the
  simulated acid distribution" (Monte Carlo, 5000 Absorptionsereignisse, Best-fit-Parameter: IP 9,75 eV, Reaktionsradius
  1,3 nm, PAG-Anregung 5,5 eV) — modellabgeleitet, als Blurterm in Quadratur benutzt. Als mittlerer Radius entspräche das
  σ ≈ 2,0 (2D) bzw. 1,6 nm (3D); Thackeray setzt ihn direkt als Blurlänge ein.
- Mack, Biafore, Smith 2011 (JM3 10, 033019), S. 385 f.: „electron blur radius" 2,1–3,3 nm je nach Annahmen (Modell).
- Kozawa/Tagawa, JPST 24(2) 137 (2011): Thermalisierungsdistanz 3–7 nm (mittlerer Elektron–Kation-Abstand, kein σ),
  optimal 3 nm für 11 nm HP (Theorie).
- Fallica 2016 / Kazazis (aus früherer Runde): kein SE-Blur-Wert. **Keine direkte Messung von σ_SE gefunden** — der Wert
  ist in allen Quellen modellabgeleitet; Thackerays 2,5 nm ist der einzige, der in einer *gemessenen* Zerlegung steht.
- Der Preset-Wert 5 nm (RESIST_PRESETS „CAR") und die CLI-Hilfe „5–10 realistic" sind unbelegt.

**Vorschlag:** se_blur_nm-Default 0,0 → **2,5 nm** (Thackeray), Presets: CAR 2,5, nonCAR/HighNA unverändert bis Quelle;
CLI-Hilfe korrigiert. Unser PEB-Blur 9,4 nm (√(2·D·t_eff)) neben Thackerays 9,3/9,7 nm Säure-RD: Gesamtblur der Kette
√(9,4² + 2,5²) = 9,73 nm gegen Thackerays 11,5 (der Rg-Term 4,3 und der unerklärte Rest fehlen bei uns — bewusst, keine Quelle
für ein Rg-Modell).

**Vorab festgelegte Vorhersagen (se_blur 0 → 2,5 nm, Defaults sonst wie nach A2):**
- V1 D2S deterministisch: Modulationsverlust exp(−2π²(9,73² − 9,4²)/P²) = 3 % (P = 64) bzw. 6 % (P = 44) →
  D2S P = 64: 1,312 → **1,31–1,34**; P = 44: 1,718 → **1,73–1,79**.
- V2 Photonen-LWR P = 44, 3 Seeds × 2 Real. × 1024 Zeilen (Referenz preflight_C: 9,77): Rauschen −3 % durch Glättung,
  Steigung −6 % → **innerhalb ±6 % von 9,77**.
- V3 aerial_threshold-Default (symmetrische Linie, Schwelle 0,5): Blur verschiebt eine symmetrische Kante nicht →
  **|ΔCD| < 0,1 nm**; NILS sinkt um ≈ 3 % (P = 64).
Falsifikation: V1 > +8 % oder V2 > ±10 % → Blur wirkt anders als Modulationsargument; dann Ursache suchen, nicht Default setzen.

**Preflight-Ergebnis A3 (scratchpad/preflight_se.py):**

| | Vorhersage | Messung | Status |
|---|---|---|---|
| V1 D2S P = 64, 0 → 2,5 nm | +0…+2 % | 1,297 → 1,299 (+0,2 %) | hält |
| V1 D2S P = 44, 0 → 2,5 nm | +1…+4 % | 1,649 → 1,668 (+1,2 %) | hält |
| V2 Photonen-LWR P = 44 bei 2,5 nm | ±6 % von 9,77 (Referenz war 5 nm) | 9,10 (7,06/10,20/10,04) | −7 %, mit 3 Seeds à ±20 % unentscheidbar |
| V2 bei 0 nm | — | **LWR = 0,000** | **Modellversagen bei se_blur 0** |
| V3 aerial_threshold | ΔCD < 0,1 nm, NILS −3 % | CD und NILS exakt gleich | Blur wird dort **gar nicht angewandt** |

Anmerkung zu V1: die absoluten Bänder (1,31–1,34 / 1,73–1,79) bezogen sich irrtümlich auf die 5-nm-Referenz aus
preflight_C; die *relativen* Vorhersagen halten. Befund V2/0 nm: `photon_deposition_shot_noise` ist bei se_blur 0 weißes
Poisson-Rauschen pro Gitterpixel — auf 0,172 nm Gitter 0,007 Photonen/Pixel, > 99 % leere Pixel und Einzelspitzen von
≈ 250 mJ/cm²; dort sättigt 1 − e^{−C·E}, die mittlere Säure bricht auf < 50 % des Mean-Field-Werts ein, die Linie druckt
nicht (keine Kante → LWR 0). Der SE-PSF ist genau das, was das Rauschen gitterinvariant macht — der alte Default 0 war für
den stochastischen full_chem-Pfad physikalisch falsch, nicht nur „ideal". V3: `_cd_via_aerial_threshold` bekommt das
rohe Luftbild; se_blur_nm wirkt nur im full_chem-Pfad (dokumentiert, nicht geändert — das Schwellenmodell ist bewusst
resistfrei).

**Umgesetzt:** `DEFAULT_SE_BLUR_NM = 2.5` (Thackeray-Term, Provenienz und Grenzen im Kommentar), Preset CAR 5 → 2,5,
nonCAR/HighNA als UNSOURCED markiert; Validierung se_blur_nm ≥ 0 und **Warnung** bei enable_stochastic mit se_blur 0;
CLI-Defaults simulate/process-window 0 → 2,5, calibrate 5 → 2,5, Hilfetext „5–10 realistic" entfernt (unbelegt);
tests/test_se_blur_default.py (Default, Quadratursumme 9,7 nm gegen Thackeray, Spike-Nachweis bei 0 nm, linearer
Dill-Bereich bei 2,5 nm, Warnung). Regressionstests setzen 5 nm explizit → Goldens unverändert.

## 2026-09-06 (Fortsetzung 27): Stufe B1 — NXE1716-Anker (Vesters 2017/2019), Vorhersagen VOR dem Lauf

**Daten (alle aus Primärquellen, nachgelesen):**
- Vesters, De Simone, De Gendt, JPST 30(6) 675 (2017), Fig. 6 (= Dissertation Fig. 2.7): DRM-Kontrastkurve R(E) von NXE1716
  (hoher Quencher) nach Flood-Belichtung auf dem NXE3300, PAB 110 °C/60 s, Film 40 nm, PEB 90 °C/60 s, TMAH (Paper: 0,026 N,
  Dissertation §4.3.6: 0,26 N — vermutlich Tippfehler im Paper). Original-Mack-Fit der Autoren als gestrichelte Linie.
  **Digitalisierung** (scratchpad/fig6_digitised.json, Overlay geprüft): Seite 6 mit 400 dpi, Gitter 486,5 px/Dekade (x) und
  181,8 px/Dekade (y), Ankerlinien x = 1 mJ/cm² bei px 251,5, y = 0,01 nm/s bei px 974,5; schwarze Komponenten (< 70) klassifiziert
  in Marker (19×19 px) und Fit-Striche. Fit-Linie: Plateaus 0,0186 / 245 nm/s; Marker: 1,0/0,0151 … 24,7/243.
- Dissertation Table 4.2 (B0 = NXE1716 ohne Sensibilisator): **D2S 11,0 mJ/cm², LWR 6,7 ± 0,3 nm (3σ, CD-SEM-biased)**,
  44 nm Pitch, 22 nm Linien, kein Reticle-Bias; §4.3.2: 35 nm Resist auf AL412, **NXE3300B Dipol 90X σ 0,62/0,90**, PEB 90 °C/60 s,
  TMAH 0,26 N, CD-SEM CG-5000 500 V/8 pA, keine Rauschkorrektur.

**Mack-Fit an die digitalisierte Fit-Linie** (Kettenform R = Mack(M), M = exp(−κ·H(E)), H = 1 − e^{−C·E}): Rmax/Rmin fest
(245/0,0186); (κ, Mth, n) sind aus einer Flood-Kurve **degeneriert** (Korrelation −1,00/0,99): Mth 0,39 (Default) → a = 0,0721,
n = 11,9; Mth 0,518 → 0,0513/11,0; Mth 0,7 → 0,0283/10,0; alle rms 0,04 in log₁₀R. Da Blur *vor* der Nichtlinearität wirkt,
ist die Linienvorhersage von der Aufteilung unabhängig (bis auf die Dill-Sättigung, C·E ≤ 0,2). Gewählt: Mth 0,39, n aus Fit,
κ aus Fit mit H(E) und C = 0,0152 → k = κ/t_eff.

**Beleuchtung:** neue Sektor-Quelle (abbe.py: sigma_inner, pole_opening_deg) für Dipol 90X. Befund: bei 44 nm Pitch, NA 0,33
liegen die ±1. Ordnungen bei ±0,93 — jede Dipol-Quellpunkt ist Zweistrahl → TCC(0,±1) = 0,5/0,5 exakt, identisch mit der
Legacy-Dipolgeometrie (in Fokus unterscheidet sich nur die Defokus-Empfindlichkeit); konventionell σ 0,8: 0,4655 (NILS 3,13
statt 3,52).

**Preset NXE1716 (kein freier Parameter für D2S):** Mack 245/0,0186/n_fit/0,39; κ_fit; C 0,0152 (LBNL, nicht NXE-spezifisch);
B 4,44 (generische PHS-Zusammensetzung); D 4,2 (Kang, 90 °C = Vesters' PEB); τ 10,5 (110-°C-Wert, bei 90 °C unbekannt);
SE 2,5; G₀ 0,2, Q 0 (Quencher steckt effektiv in κ/Mth); Film 35 nm; Entwicklung 30 s (imec-Zeit unbekannt).

**Vorab festgelegte Vorhersagen:**
- P1 D2S (22 nm CD, Dipol 90X) ohne freien Parameter: **12,5 ± 3,5 mJ/cm²** (gemessen 11,0). Begründung: Kante bei I ≈ 0,5,
  35 nm in 30 s verlangt R ≥ 1,2 nm/s → E_lokal ≈ 7 → ≈ 14, Blur senkt es.
- P2 LWR (nur Photonen, 3 Seeds × 2 Real. × 1024 Zeilen) bei der Ketten-D2S: **3σ = 8–13 nm** gegen gemessen 6,7 (biased).
  Erfolgskriterium des Plans: ≤ 1,3× = 8,7 nm. Meine Erwartung: knapp verfehlt (Fortsetzung 23: 1,66× beim Default-Resist).
- P3 Fallback (ein Parameter κ auf D2S = 11 kalibriert): LWR ändert sich um < 15 % gegenüber P2.
- P4 NILS am Druckpunkt (nach Entwicklung): 2,5–3,5.

**B1-Ergebnis (scratchpad/b1_nxe1716.py):** Fit κ = 5,19, n = 12,8 (rms 0,042) → k = 0,496 s⁻¹ bei 90 °C (bei C 0,0152, τ 10,5).

| | Vorhersage | Messung (Kette) | Status |
|---|---|---|---|
| P1 D2S ohne freien Parameter | 12,5 ± 3,5 | **19,7 mJ/cm²** (gemessen 11,0; bei 11,0 druckt nichts, CD = Pitch) | **falsifiziert**, Faktor 1,79 |
| P2 LWR bei Ketten-D2S 19,7 | 3σ 8–13 | 3σ 6,40 (5,81/6,43/6,96) | unter Band — aber bei 1,8× zu hoher Dosis, nicht vergleichbar |
| P3 κ ×1,79 → D2S 10,7; LWR | Änderung < 15 % | 3σ **9,05 (Mittel)** / 5,7 (Median); Seeds 5,74/5,19/**16,2** | Mittel +41 % (Ausreißer Seed 11), Median −10 % |
| P4 NILS am Druckpunkt | 2,5–3,5 | 2,92 | hält |

Bewertung: Die Null-Parameter-Vorhersage der Druckdosis scheitert um 1,8×. Naheliegende Ursache: der Blur. Bei P = 44 nm
dämpft σ_tot = 9,7 nm die Säuremodulation um exp(−2π²σ²/P²) = 0,38; die Space-Mitte sieht damit nur ≈ 0,69 der Flood-
äquivalenten Dosis → Schaltpunkt 12,7 mJ/cm² der DRM-Kurve wird erst bei ≈ 18 mJ/cm² erreicht (beobachtet 19,7). Weitere
Kandidaten: τ bei 90 °C (unbekannt, bestimmt t_eff und damit σ), Quencher (in der Flood-Kurve nur effektiv enthalten;
in Linien wirkt er kontrastverstärkend), Entwicklungszeit (imec unbekannt). Diagnoseläufe folgen (keine Fits).
LWR am kalibrierten Punkt: 3 Seeds à n_eff ≈ 8 reichen nicht (Seed 11 zeigt 5,4 nm 1σ — vermutlich Linienabriss);
Lauf mit 6 Seeds × 2 Real. × 2048 Zeilen, mit/ohne molekulares Rauschen, gestartet (b1_lwr_stats.py).

**D2S-Diagnose (keine Fits; scratchpad/b1_d2s_diag.out), Luftbild normiert: I_max 0,63, I_min 0,004 (Space-Mitte sieht 0,63·D):**

| Variante | D2S (mJ/cm²) |
|---|---|
| Basis σ 9,4 ⊕ 2,5, 30 s | 19,7 |
| σ_PEB 7 / 5 / 3 | 18,5 / 17,9 / 17,5 |
| Entwicklung 60 s | 18,2 |
| SE-Blur 0 | 19,5 |
| σ 3 + 60 s / σ 5 + 60 s / σ 3 + 120 s | 15,9 / 16,3 / 14,1 |

Der Blur erklärt also nur ≈ 2 mJ/cm² der Lücke; selbst σ 3 nm mit 120 s Entwicklung bleibt bei 14,1 (1,28×). Kern des Problems:
bei D = 11 sieht die Space-Mitte lokal 6,9 mJ/cm², wo die DRM-Flood-Kurve 0,8 nm/s liefert — 35 nm in 30 s brauchen ≥ 1,2 nm/s
(E ≥ 7,4). Die Flood-Dosisskala der DRM-Messung und die Druckdosis des Patterning-Experiments sind mit unserer Kette um
1,3–1,8× inkonsistent, unabhängig vom Blur. Kandidaten, die die Kette nicht enthält: Quencher-Kontrastwirkung in Linien (in der
Flood-Kurve nur effektiv), Unterschied DRM-Film (40 nm auf SiO₂) vs. 35 nm auf AL412, Entwicklungszeit/-rezept von imec
(unbekannt), Definition der Scanner-Dosis. **Nicht** durch Nachjustieren zu schließen — dokumentiert als offene Diskrepanz;
für die LWR-Prüfung gilt der Ein-Parameter-Fallback (κ ×1,79) des Plans.

**LWR-Statistik am kalibrierten Punkt (b1_lwr_stats.py: 6 Seeds × 2 Realisationen × 2048 Zeilen, D2S 10,69, k ×1,79):**

| Rauschmodell | LWR 1σ (Mittel ± sem) | 3σ | gemessen (3σ, SEM-biased) | Verhältnis |
|---|---|---|---|---|
| nur Photonen | 3,63 ± 0,39 (2,4–4,6) | **10,9 nm** | 6,7 ± 0,3 | **1,6×** |
| Photonen + molekular (G₀ 0,2) | 6,34 ± 0,45 | 19,0 nm | 6,7 | 2,8× |

Feldlängen-Check (1024/2048/4096 Zeilen, 2 Seeds): 3,2/3,8 · 2,9/3,7 · 5,0/3,2 — kein Trend, aber Streuung ±25 % pro Lauf;
die 1024-Zeilen-Werte 1,7–1,9 aus P3 waren der untere Ausläufer. NILS am Druckpunkt 2,92 (P4 hält).

**Bewertung nach vorregistriertem Kriterium (≤ 1,3×): verfehlt.** Die Kette überschätzt die LWR von NXE1716 um ≥ 1,6× (die
Messung ist SEM-biased, der wahre Wert liegt noch tiefer). Das ist dieselbe Richtung und Größe wie der Vesters-Vergleich mit dem
Default-Resist (Fortsetzung 23: 1,24–1,66×). Was der Kette an diesem Anker fehlt bzw. unbelegt ist:
1. **Quencher** — NXE1716 ist der Hoch-Quencher-Resist; in der Kette nur effektiv über κ/Mth der Flood-Kurve. In Linien
   verstärkt der Quencher den Kontrast des latenten Bilds (Mack/Biafore/Smith 2011, Quenching-Studie) und senkt die LWR.
   Ohne Q-Beladung von NXE1716 (unveröffentlicht) nicht modellierbar.
2. **Absorption α_B** — Dissertation Fig. 4.1 (nur grafisch); wir nehmen 4,44 µm⁻¹. Höheres α → mehr absorbierte Photonen →
   weniger Rauschen (∝ α^{−1/2}); Fig. 4.4 gibt Säuren pro absorbiertem Photon für B0 (grafisch) — beides für B2 digitalisieren.
3. **τ bei 90 °C** unbekannt (Blur 9,4 nm aus 110-°C-τ), **Entwicklungszeit** imec unbekannt.
4. Molekulares Rauschen des Samplers (V4b, Fortsetzung 25) nicht verstanden — mit G₀ 0,2 wäre die Kette 2,8× daneben.
Keine Parameteranpassung vorgenommen. Preset `presets.nxe1716_config()` mit deklarierter Dosisskalen-Kalibrierung
(`calibrated_dose_scale=True`, ×1,79) und die digitalisierte Kurve als Paketdaten (`data/anchors/vesters2017_nxe1716.json`);
`tests/test_nxe1716_anchor.py` prüft nur die Flood-Kurven-Reproduktion (rms ≤ 0,06) und die Provenienz, nicht das Drucken.

**LWR-Sensitivität am kalibrierten Punkt (b1_lwr_sens.py, 3 Seeds × 2 Real. × 2048 Zeilen, feste Dosis 10,69 — CD verschiebt sich):**

| Variante | LWR 1σ | CD |
|---|---|---|
| Basis (σ_PEB 9,4) | 3,49 (3,79/4,19/2,50) | 22,0 |
| σ_PEB 5 nm | **1,37** (1,34/1,49/1,29) | 19,9 |
| dill_B 6,5 µm⁻¹ | 3,73 | 25,7 (unterbelichtet) |
| Entwicklung 60 s | 2,14 | 17,8 (überbelichtet) |

Der PEB-Blur ist der dominante Hebel: mit σ 5 nm fällt die LWR um 2,5× (Kantensteigung bei P = 44 steigt mit der Modulation
0,38 → 0,75 stärker als das Rauschen zunimmt). Die 9,4 nm stammen aus D (Kang, 90 °C) und τ = 10,5 s (Yamamoto, 110 °C);
τ bei 90 °C ist unbekannt. **Das B1-Urteil hängt damit an einem unbelegten Parameter** — mit σ ≈ 5–7 nm läge die Kette
innerhalb des 1,3×-Kriteriums; das ist keine Bestätigung, sondern die Aussage, dass die LWR-Vorhersage ohne gemessenen
Blur des Resists nicht schärfer als ±2× ist. Nachlauf bei angepasster D2S für σ 5 folgt.

**Nachlauf σ_PEB = 5 nm bei eigener D2S (b1_sigma5.py, 6 Seeds × 2 Real. × 2048 Zeilen):** unkalibriert D2S 17,9 (Faktor 1,63
statt 1,79 — der Blur erklärt auch hier nur ≈ 2 mJ/cm²); kalibriert D2S 10,77; **LWR 1σ 1,60 ± 0,13 → 3σ 4,8 nm** gegen 6,7 gemessen
(0,71×; SEM-biased, unbiased vermutlich 5–6 → nahe dran).

**Revidiertes B1-Urteil:** Die Photonen-LWR der Kette am NXE1716-Anker liegt je nach PEB-Blur zwischen 4,8 nm (σ 5) und 10,9 nm
(σ 9,4) 3σ und klammert die Messung (6,7 biased) ein. Der Blur bei 90 °C ist für diesen Resist nicht belegt (τ nur bei 110 °C).
Damit ist das Rauschmodell an diesem Anker **weder validiert noch falsifiziert** — die Vorhersage ist ohne gemessenen Blur nicht
schärfer als ±1,6×. Die Dosisskalen-Diskrepanz (1,6–1,8×) bleibt unabhängig davon bestehen und ist der belastbarere Befund.
Konsequenz für B2: erst den Blur (bzw. τ(90 °C)) und α_B/Säureausbeute (Dissertation Fig. 4.1/4.4) resistspezifisch belegen,
dann erneut vorhersagen; kein Parameter wurde an die LWR angepasst.

**2026-09-06, Nutzer:** Anfrage an Danilo De Simone (imec) abgeschickt (Entwurf: mack fits/email_draft_vesters_imec.md; Bitten:
Mack-Fit-Parameter NXE1716/1717, Quencherbeladung, Entwicklungszeit, Blur/Säureausbeute bei 90 °C). Antwort ausstehend.

## 2026-09-06 (Fortsetzung 28): Literatur-Runde 11 — Quencher, Blur bei 90 °C, Lebensdauer (Details: mack fits/search_log.md, catalog.md)

Drei neue Primärquellen, alle frei und archiviert:
1. **NIST/Intel, SPIE 7273 (2009), JSR-EUV-Resist, PEB 90 °C:** kP 1,6 nm³/s, **kT 0,026 s⁻¹ → τ = 38 s bei 90 °C**, DH 4,2 nm²/s;
   Diffusionslänge modellfrei 36 nm ohne / **14 nm mit Quencher** (60 mol % rel. PAG). Erste belegte Lebensdauer bei 90 °C — und
   der direkte Beleg, dass der Quencher die wirksame Diffusionslänge um 2,6× senkt. Für den NXE1716-Anker heißt das: τ(90 °C)
   wäre eher 38 s als 10,5 s (Blur ohne Quencher noch größer), der Quencher ist der Hebel, der das kompensiert.
2. **Anderson & Naulleau (LBNL), OSTI 950847, Table I/II:** XP 5271 (= MET-2D) bei PEB 120 °C/90 s: Deprotection-Blur 23,8 (Contact)
   / 34,8 (Corner) nm, E-size 12,5 mJ/cm² (50 nm 1:1, MET NA 0,3), LER 6,7 ± 0,2 nm; dazu Basisreihen für XP 5435/5496/EH27 und
   PEB-Reihen für TOK P1123 / Fuji 1195. **MET-2D wird damit zum vollständigsten Anker:** C + FQY (LBNL), B + Mack + Arrhenius
   (Sekiguchi Table 6), Blur + E-size + LER (Naulleau) — vier Messgruppen, ein Handelsresist; Vorbehalte: Chargen 2008–2011,
   PEB 110/120/130 °C je Quelle, Blur-Definition der HOST-PSF (σ vs. FWHM) noch zuzuordnen.
3. **Osaka-Dissertation Jin 2025 (Kozawa-Gruppe):** benannter Modell-CAR mit PAG 0,2 / Quencher 0,1 nm⁻³, PEB 110 °C/90 s,
   Neutralisationsradius 0,5 nm mit D 1,0 nm²/s → k_Q ≈ 12,6 nm³/s (Macks 15 nm³/s damit erstmals unabhängig gestützt),
   Entwicklungsschwelle Cth 1,3–1,5 von 2,26 nm⁻³ (M_th ≈ 0,34–0,42, unser Default 0,39). Belichtung EB, nicht EUV.
Nebenfund: Shin-Etsu-Patent US 10,809,617 (Google-Patents-Volltext) — PAG:Quencher ≈ 8:4,5 Massenteile, aber ArF-Test.
Nicht gefunden: Quencherbeladung der NXE-Resists, Vesters' Fit-Tabelle (Anfrage läuft).

**Konsequenz für den Plan (B2):** (a) Quencher explizit modellieren und am NXE1716/1717-Kurvenpaar (Q-Verhältnis 2:1) fitten;
(b) MET-2D als zweiten Anker aufbauen (Preset aus vier Quellen, Vorhersage E-size 12,5 und LER 6,7 bei 50 nm 1:1 mit MET-Optik);
(c) τ(90 °C) = 38 s (NIST) als belegten Wert für 90-°C-Presets führen, mit Quencher statt ohne.

**Nachtrag Blur-Definition:** Andersons „deprotection blur" ist eine Breite („average width of the volume … rendered dissolvable by a
single acid"), Modellkern HOST-PSF (Houle/Hinsberg 2000); Naulleaus PSF-Fits sind als FWHM angegeben. Als FWHM gelesen: MET-2D
(120 °C) σ ≈ 10,1 nm — nahe unserem Default 9,4; **Produktionsresists bei 90 °C (P1123, Fuji 1195): σ ≈ 5,7–7,6 nm** — genau der
Bereich, in dem der NXE1716-Anker das 1,3×-Kriterium träfe (4,8 nm 3σ bei σ 5; 10,9 bei 9,4). Kein Beleg für NXE1716 selbst,
aber ein belegtes Band für 90-°C-CARs, das die 9,4 nm (110-°C-τ) als zu groß ausweist.

## 2026-09-06 (Fortsetzung 29): B2a — expliziter Quencher am NXE1716/1717-Kurvenpaar (Vorhersagen VOR dem Fit)

**Daten:** Fig. 6 grau (NXE1717, halbe Quencherbeladung) digitalisiert wie die schwarze Kurve (Pixel 90–175): 11 Marker, 30
Fit-Stützstellen, Plateaus 0,0119 / 157,7 nm/s (schwarz 0,0186 / 245 — Vesters: „both Rmin and Rmax higher for the high-quencher
resist", Weichmacherwirkung). Beide Kurven im Paketdatensatz `vesters2017_nxe1716.json`.

**Modell (Kettenfunktionen, kein Ersatzmodell):** acid h = 1 − e^{−C·E} (C 0,0152), Neutralisation nach Mack 2011 zweiter Ordnung
(`reaction_diffusion_with_quenching`, k_Q·G₀), M = exp(−k·t_eff·h_rest), R = Mack(M) mit Plateaus je Kurve aus den Daten.
Fest (mit Quelle): τ = 38 s (NIST/Intel 90 °C), k_Q = 12,6 nm³/s (Osaka 2025, 4π·0,5 nm·2 nm²/s; Mack 15 zum Vergleich), G₀ 0,2,
M_th 0,39 (mit k degeneriert). **Frei, gemeinsam für beide Kurven:** k, n, q₁₇₁₇ mit **q₁₇₁₆ = 2·q₁₇₁₇** (q relativ zu G₀).

**Vorhersagen:**
- V1 q₁₇₁₆ aus der Dosisverschiebung der Schaltflanken (≈ 2,6–4 mJ/cm² ↔ ΔH 0,04–0,06): **q₁₇₁₆ = 0,06–0,15** (Q = 0,012–0,03 nm⁻³,
  Q/PAG ≈ 0,1) — deutlich unter Mack 2011 (0,25) und Osaka (0,5).
- V2 rms(log₁₀R) ≤ 0,08 für beide Kurven mit *gemeinsamem* k, n; sonst ist „gleiche Kinetik, nur 2:1 Quencher" falsch.
- V3 n bleibt 10–14.
- V4 Linien (Preset NXE1716 mit gefittetem Quencher, τ 38 s, ohne Kalibrierung): **D2S ändert sich um < 10 %** gegenüber 19,7 —
  der Quencher wird in Flood und Linie gleich abgezogen, die Dosisdiskrepanz bleibt (Begründung: Space-Mitte braucht dieselbe
  Restsäure wie der Flood-Schaltpunkt). Falls D2S doch auf < 15 fällt, war die Diskrepanz Quencher/τ.
- V5 LWR am kalibrierten Punkt (6 Seeds × 2 Real. × 2048 Zeilen): **10–40 % unter 10,9 nm 3σ** (Quencher schärft das latente Bild;
  τ 38 s vergrößert den Blur, Quencher kürzt die Reichweite) — Band 6,5–9,8 nm.

**Ergebnis gemeinsamer Fit (k, n, q geteilt; τ 38 s, k_Q 12,6):** k = 0,287 s⁻¹, n = 4,6, q₁₇₁₆ = 0,077 (Q = 0,015 nm⁻³), rms 0,131 / 0,129
(τ 10,5: k 1,08, n 7,0, q₁₇₁₆ 0,095, rms 0,079 / 0,103). **V1 hält (q im Band), V2 und V3 fallen.** Befund: die schwarze Kurve
(hoher Quencher) ist in log-Dosis *breiter* als die graue, ein subtraktiver Quencher bei gleicher Kinetik macht sie *schmaler*;
außerdem zeigt die schwarze Kurve eine Schulter bei 7–8 mJ/cm² (Marker 1,3/1,8 nm/s, dann Sprung auf 71 bei 10). „Gleiche
Kinetik, nur 2:1 Quencher" ist damit falsifiziert. Physikalisch motivierte Verfeinerung (vorab festgelegt): Vesters führt die
höheren Plateaus des Hoch-Quencher-Resists auf eine Weichmacherwirkung in der *Entwicklung* zurück → Mack-n je Kurve frei,
k (Deprotektion: gleiches Polymer, gleicher PAG, gleiche PEB) und q-Verhältnis 2:1 geteilt. Vorhersage V2b: rms ≤ 0,08 beide,
q₁₇₁₆ weiter 0,06–0,15; sonst bleibt auch der Quencher-Anteil unbestimmt.

**Ergebnis verfeinerter Fit (k, q geteilt; n je Kurve; Plateaus aus Daten):**

| τ | k (s⁻¹) | n₁₇₁₆ / n₁₇₁₇ | q₁₇₁₆ (rel. G₀) | Q₁₇₁₆ (nm⁻³) | rms₁₆ / rms₁₇ |
|---|---|---|---|---|---|
| 38 s (NIST, 90 °C) | 0,489 | **2,0 (Schranke)** / 3,5 | 0,126 ± 0,004 | 0,025 | 0,074 / 0,066 |
| 10,5 s | 1,82 | 4,5 / 7,4 | 0,148 ± 0,005 | 0,030 | 0,031 / 0,063 |
| Einzelkurve frei (1716) | 0,172 | 12,8 | **0,000** | – | 0,042 |
| Einzelkurve frei (1717) | 0,922 | 2,7 | 0,085 | – | 0,052 |

V2b hält (rms ≤ 0,08), V1 hält (q₁₇₁₆ 0,13–0,15 → **Q/PAG ≈ 0,13–0,15**, Q ≈ 0,025–0,03 nm⁻³ bei G₀ 0,2). Aber: n₁₇₁₆ läuft bei τ 38 s
an die untere Schranke (2,0) — Quencher-Abzug und Mack-n formen beide die Flanke und sind gegenläufig korreliert; aus einer
Einzelkurve ist q gar nicht bestimmbar (1716 allein: q = 0, n = 12,8). Belastbar ist daher nur das *Paar*-Ergebnis für q
(0,12–0,15, robust gegen τ), nicht die n-Werte. Für die Linien-Vorhersage wird q₁₇₁₆ = 0,126 (τ 38 s) und 0,148 (τ 10,5)
geprüft; Q/PAG ≈ 0,13 liegt zwischen Mack 2011 (0,25) und den Naulleau-Basisreihen (relativ) und unter Osaka (0,5).

**V4 (Linien mit explizitem Quencher, ohne Kalibrierung), Satz τ 38 s / q₁₇₁₆ 0,126 / n 2,0:** D2S = **23,5 mJ/cm²** (vorher 19,7,
gemessen 11,0); bei 11,0 druckt weiterhin nichts. Vorhersage „< 10 % Änderung" **falsifiziert nach oben** (+19 %): τ = 38 s macht
t_eff = 30 s und den Blur √(2·4,2·30) = 15,9 nm, was die Modulation bei 44 nm Pitch weiter dämpft; der Quencher wird in Flood
und Linie gleich abgezogen. Die Dosisdiskrepanz ist mit belegtem τ und Quencher also *größer*, nicht kleiner. τ-10,5-Satz und
die Quencher-frei-Varianten laufen nach.

**Strukturanalyse der Dosisdiskrepanz (kein Fit, reine Arithmetik der Kette):** Für ein symmetrisches 1:1-Bild liegt die
Kante bei x = P/4 exakt auf dem *Mittelwert* der Intensität — Blur und Quencher ändern die Säure dort nicht (Symmetrie des
Kosinus). Chain-Luftbild bei 11 mJ/cm²: max 0,628, min 0,004, **Mittel 0,318** des Open-Frame. Der Rand druckt, wenn die Kette
bei der mittleren Dosis in der Entwicklungszeit durch den Film kommt: DRM-Kurve → R ≥ 35 nm/30 s = 1,17 nm/s ab
**E_through = 6,96 mJ/cm²** (60 s: 6,45). Also D2S ≈ 6,96/0,318 = 21,9 (Bisektion 19,7, Rest ist Kantengeometrie). Umgekehrt
verlangt die gemessene D2S 11,0 ein Durchentwickeln bei 3,5 mJ/cm², wo die DRM-Kurve 0,02 nm/s liefert (Faktor 60 in der Rate,
≈ 2 in der Dosis). **Folgerung: Kein Blur-, Quencher- oder Entwicklungszeit-Parameter kann das schließen — die DRM-Flood-Kurve
und das Patterning-Experiment sind unter jedem symmetrischen Bildmodell um ≈ 2× in der Dosisskala inkonsistent.** Dokumentierte
Unterschiede der beiden Experimente: PAB 110 °C/60 s (DRM, Paper Table 1) vs. 90 °C/60 s (Patterning, Dissertation §4.3.1),
Substrat SiO₂ (DRM) vs. AL412-Unterlage (Patterning), Film 40 vs. 35 nm. Zum Vergleich: E-size/E0 ≈ 2–3 ist in der Literatur
üblich (LBNL: BMET E-size = 2× AMET E0); die Kette liegt mit 19,7/7,0 = 2,8 im Normalbereich — nur *imecs* E0 wäre dann ≈ 4,
nicht 7. Das ist eine Frage an die Autoren (gestellt), nicht an den Simulator. Die deklarierte Dosisskalen-Kalibrierung ×1,79
bleibt die ehrliche Handhabung; der Quencher-Fit liefert q₁₇₁₆ ≈ 0,13 für die LWR-Prüfung (V5).

## 2026-09-06 (Fortsetzung 30): B2b — MET-2D (XP 5271) als zweiter Anker, Vorhersagen VOR dem Lauf

**Datensatz** `data/anchors/met2d_xp5271.json`: LBNL (C 0,0152, FQY 1,39, α 4,37, 80-nm-Film, PEB 130 °C), Sekiguchi Table 6
(B 5,21, Mack 170,2/0,028/0,518/18,96, PEB 110 °C/90 s, Film 125 nm), Anderson/Naulleau OSTI 950847 (XP 5271-D: Blur 23,8
Contact / 34,8 Corner, E-size 12,5 mJ/cm² für 50 nm 1:1, LER 6,7 ± 0,2 nm (50 nm) / 5,2 (100 nm), PEB 120 °C/90 s, 80 nm,
MF26A 45 s; MET NA 0,3, annular σ 0,35–0,55, Dunkelfeldmaske). Chargen/PEB je Quelle verschieden — dokumentiert.

**Preset** `presets.met2d_config()`: Blur direkt als gemessene Größe gesetzt (σ = 23,8/2,355 = 10,1 nm; Corner-Variante 14,8),
Mack und B von Sekiguchi, C von LBNL, Optik/Film/Entwicklung von Anderson. **Nicht belegt in unserer Form:** die Deprotektions-
rate bei 120 °C (Sekiguchis PROLITH-Paar k(120 °C) = 2,0 s⁻¹ ist an C = 0,090 und PROLITHs zweigliedriges PEB-Modell gebunden;
eine Flood-Kurve für MET-2D liegt nicht vor). Deshalb wird — wie bei NXE1716 — die Dosisskala (k) deklariert an E-size 12,5
kalibriert und **nur die LER vorhergesagt**. LER-Konvention bei Anderson: Einzellinien-LER, Mittel über 54 Linien; ob 1σ oder 3σ,
nennt das Paper nicht explizit (die *Unsicherheit* ist 3σ) — LBNL-Praxis ist 3σ; wird als 3σ gelesen und so vermerkt.

**Vorhersagen (6 Seeds × 2 Real. × 2048 Zeilen, nur Photonenrauschen):**
- P1 LER 3σ bei 50 nm 1:1, Blur 10,1 nm: **4–7 nm** (gemessen 6,7; Kriterium ≤ 1,3× → ≤ 8,7). Begründung: 80-nm-Film absorbiert 34 %
  statt 14 %, Feature 50 statt 22 nm, Blur ähnlich → weniger relatives Rauschen als beim NXE1716-Anker (10,9 bei σ 9,4).
- P2 mit Corner-Blur 14,8 nm: LER **höher** als P1 um 20–60 % (bei P = 100 nm kostet der größere Blur Steigung, gewinnt wenig Glättung).
- P3 LER bei 100 nm 1:1 (gemessen 5,2): Verhältnis LER(50)/LER(100) der Kette **1,1–1,6** (gemessen 1,29).
Falsifikation: P1 > 8,7 nm → Rauschmodell überschätzt auch hier; P1 < 3 nm → unterschätzt (Molekülrauschen fehlt).

**V5-Ergebnis (expliziter Quencher, k per Bisektion auf D2S = 11,0; τ 10,5, q₁₇₁₆ 0,148, n 4,48; 6 Seeds × 2 Real. × 2048 Zeilen):**
k 1,82 → 6,06 (×3,33 — die frühere Skalierung „×Dosisverhältnis" gilt mit Quencher nicht, sie hatte 15 statt 11 ergeben);
**LWR 1σ 3,70 ± 0,36 → 3σ 11,1 nm** gegen 10,9 ohne expliziten Quencher. **V5 falsifiziert:** bei gleicher D2S schärft der
subtraktive Quencher das latente Bild nicht — die Kontrastverstärkung durch Quencher existiert nur im Vergleich *bei gleicher
Dosis* zum quencherfreien Resist, nicht bei angepasster Dosis. Satz τ 38 s: mit 15,9 nm Blur erreicht keine Kalibrierung
CD 22 bei 11 mJ/cm² (Modulation zu klein) — abgebrochen. Fazit B2a: q₁₇₁₆ ≈ 0,13–0,15 (rel.) ist ein echter Fund aus dem
Kurvenpaar, aber weder D2S noch LWR des Ankers hängen davon ab; die Diskrepanzen liegen woanders.

**B2b-Ergebnis MET-2D (b2_met2d.py):** unkalibriert (Default-k 7,87 aus Yamamoto) E-size 1,1 mJ/cm² — die Yamamoto-Kinetik
ist für MET-2D nicht übertragbar; kalibriert k = 0,696 (E-size 13,2 statt 12,5 durch Bisektionsraster, +5 %).

| | Vorhersage | Kette (nur Photonen, 3σ) | gemessen (Anderson) |
|---|---|---|---|
| P1 LER 50 nm 1:1, Blur σ 10,1 | 4–7 nm | **0,74 ± 0,02 nm** | 6,7 ± 0,2 |
| P2 mit Corner-Blur 14,8 | +20…60 % | 0,81 (+9 %) | – |
| P3 LER(50)/LER(100) | 1,1–1,6 | 0,90 (0,82 nm bei 100 nm) | 1,29 (5,2 nm) |

**Alle drei falsifiziert — in die Gegenrichtung von NXE1716.** Bei 80 nm Film (34 % absorbiert), 13 mJ/cm² und 50-nm-Linien trägt
Photonenschrotrauschen < 1 nm 3σ; die gemessenen 6,7 nm sind zu ≥ 85 % etwas anderes. Das deckt sich mit Andersons eigener
Schlussfolgerung im selben Papier („intrinsic LER floor ≈ 3–4 nm across a wide range of resists", Titel: „Don't always blame
the photons"), plus SEM-Rauschen (S-4800, 2 kV, unkorrigiert), Maskenrauheit und Flare des MET. Gemeinsam mit NXE1716
(Photonen-LWR 1,6× *zu hoch* bei 22 nm HP / 35 nm Film) ergibt sich: **das Rauschmodell der Kette ist ein reines Photonenmodell;
es fehlt ein dosisunabhängiger Sockel (Polymer/Entwicklung/SEM), und der Photonenterm selbst ist am dünnen Film zu groß.**
Beide Anker zusammen sind damit informativer als jeder allein. Nächster Test läuft: molekulares Rauschen (exposure_stochasticity)
am MET-2D-Punkt — erreicht es den Sockel nicht, liegt er in Entwicklung/Polymer (development_stochasticity ist seit Audit A6
deaktiviert) oder in der Messung (SEM-Bias).

**MET-2D mit molekularem Rauschen (b2_met2d_mol.py, 3 Seeds × 2 Real. × 2048 Zeilen):** nur Photonen 0,73 nm 3σ; Photonen +
PAG-Zählrauschen (G₀ 0,2) **1,97 nm 3σ** — immer noch 3,4× unter den gemessenen 6,7 nm. In Quadratur fehlen ≈ 6,4 nm, die weder
Photonen- noch PAG-Statistik liefern. Kandidaten für B3, jeweils mit Beleg zu prüfen: SEM-Rauschbias (Anderson unkorrigiert;
Mack/Lorusso-PSD-Methodik gibt Größenordnungen), Entwicklungs-/Polymerstochastik (Kozawa: Polymergröße; Mack: stochastische
Auflösung; `development_stochasticity` seit Audit A6 deaktiviert), Masken-LER des MET-Retikels, Flare. Erst der Bias, dann das
Modell — sonst wird der Sockel an eine Messartefakt-Zahl gefittet.

## 2026-09-06 (Fortsetzung 31): B3 — LER-Sockel, Schritt 1: SEM-Bias der Ankerwerte (Quellen)

- **Lorusso, Rutigliani, Van Roey, Mack, „Unbiased roughness measurements: Subtracting out SEM effects", Microelectron. Eng. 190
  (2018) 33** — `lithoguru/2018_Unbiased_Roughness_Measurement.pdf` (frei). Table 1 (16-nm-Linien, 500 eV, imec-Protokoll):
  biased LWR 4,47–5,10 nm 3σ, unbiased 3,63–3,70 → SEM-Anteil in Quadratur 2,6–3,6 nm. Table 2: **EUV, 32 nm Pitch, 500 V, 1024
  Rechteckpixel (Vesters' biased Protokoll): biased/unbiased = 1,66, Differenz 2,19 nm** → b 5,5 / u 3,3 → SEM-Anteil ≈ 4,4 nm;
  0,8-nm-Quadratpixel 2048: 1,39 / 1,44 nm. Vesters-Dissertation §5.3 bestätigt das Protokoll (CG-5000, 500 eV, 8 pA, 16 Frames,
  Rechteckscan 1024 px für biased; unbiased ab Kap. 5 per Fractilia metroLER — Kap. 4 (unser Anker) nur biased). Table 7.1 der
  Dissertation nennt B0 als „CAR PTD + Metal sensitizer, 44 nm, LER 4,6 (= LWR/√2), 11 mJ/cm²" (biased).
- **Folge für NXE1716:** unbiased LWR ≈ √(6,7² − (3,5…4,4)²) = **5,1–5,7 nm 3σ** (Verhältnismethode 1,4–1,66: 4,0–4,8). Vergleich
  Kette (nur Photonen): 10,9 (σ 9,4) bzw. 4,8 (σ 5) — der Photonenterm allein liegt je nach Blur *über oder knapp unter* dem
  unbiased Wert; ein zusätzlicher Sockel hätte hier also wenig Platz (≤ 3 nm in Quadratur bei σ 5).
- **Anderson (MET-2D):** S-4800, 2 kV, 100–150k, keine Korrektur, kein Bias-Wert publiziert; die 6,7 nm bleiben eine Obergrenze.
  Andersons „intrinsic LER floor 3–4 nm" ist ebenfalls biased gemessen. Kette 0,73 (Photonen) / 1,97 (mit PAG-Zählung).
  Selbst mit einem SEM-Anteil wie bei imec (≈ 4 nm) bliebe unbiased ≈ 5,4 nm — Faktor 2,7 über der Kette.
Damit ist der Sockel real, aber kleiner als die Rohzahlen suggerieren: Größenordnung 3–5 nm 3σ bei 50-nm-Linien/80-nm-Film.

**B3, Schritt 2 — Kandidat „Zählstatistik der geschützten Einheiten" (Mack 2010, „LER and the Ultimate Limits of Lithography",
`lithoguru/2010_LER_Ultimate_Limits.pdf`, Gl. 36/37):** σ_m²/m² = 1/(n₀,blocked·m·V) + (Kamp·t)²·(σ_h,eff/h)²·… — der erste Term ist
die Poisson-Statistik der blockierten Polymereinheiten, die unsere Kette *nicht* sampelt (exposure_stochasticity sampelt nur PAG/
Quencher; die Deprotektion bleibt Mean-Field). Überschlag für MET-2D (n₀ ≈ 2 nm⁻³, m ≈ 0,5 an der Kante, Blur-Volumen
(2√π·10 nm)³ ≈ 4·10⁴ nm³): σ_m/m ≈ 0,5 % → Kantenversatz ≈ 0,1 nm — **vernachlässigbar bei 10 nm Blur** (Macks eigenes Beispiel:
4,3 % bei (10 nm)³ ohne Blur-Mittelung, dominiert vom Säureterm). Der Sockel von 3–5 nm liegt also nicht in der Deprotektions-
statistik, sondern in der **Entwicklung** (Macks Stochastik-Papiere 2009/2010: Rauigkeitswachstum der Auflösungsfront,
dynamisches Skalieren; jetzt archiviert `lithoguru/2009_…/2010_Stochastic_Development.pdf`) und/oder in der Messung (Anderson:
2 kV, unkorrigiert). Nächster Schritt: Macks Entwicklungsmodell lesen — nur wenn es dimensionierte Parameter mit Quelle liefert,
wird es implementiert (Audit A6 bleibt bindend).

## 2026-09-06 (Fortsetzung 32): B3, Schritt 3 — Entwicklungsrauschen aus der Zählstatistik der Auflösungszellen (Vorhersagen VOR dem Lauf)

**Quelle des Mechanismus:** Mack, „Stochastic modeling of photoresist development in two and three dimensions", JM3 9, 041202
(2010) (`lithoguru/2010_Stochastic_Development.pdf`): eine oberflächenlimitierte Auflösung mit zellweise verrauschter Rate
(σ_r/r, Zelle = Gitter 1 nm) fällt in die KPZ-Universalitätsklasse (1+1: α 0,5, β 1/3; 2+1: α 0,4, β 0,25); die gesättigte
Rauigkeit skaliert σ_sat ≈ σ̂_sat·L^α mit σ̂_sat ≈ 0,15–0,21 (2+1, Fig. 10) für σ_r/r 0,1–0,3 → bei L ≈ 500 nm ≈ 2 nm (1σ) —
die Größenordnung des gemessenen Sockels. Macks σ_r/r ist dort eine Annahme; hier wird sie **abgeleitet**: pro Auflösungszelle
der Kantenlänge a sind N = n₀·m·a³ blockierte Einheiten vorhanden (Mack 2010 „Ultimate Limits", Gl. 36, erster Term), deren
Poisson-Streuung δm/m = 1/√N über die Mack-Kurve in eine Ratenstreuung σ_lnR = |dlnR/dm|·m/√N übersetzt wird — lokal, aus
dem vorhandenen M-Feld, ohne freien Parameter. Neue Größen mit Quelle: n₀ (blockierte Einheiten; Kozawa/Jin 2025: 2,26 nm⁻³ bei
54,6 % t-BOC; Polymer A 35 %: ≈ 2,1 nm⁻³) und a (Auflösungseinheit: Thackeray 2010 Rg 4,3 nm; Alternative 1 nm = Macks Gitter).
Einschränkung der Kette: der Eikonal-Löser arbeitet je y-Zeile in (x, z) — Zellrauschen ist über y nur über die Zellgröße
korreliert, KPZ-Glättung entlang y fehlt; das Ergebnis ist damit eher eine Obergrenze des Effekts.

**Preflight (Monkey-Patch: MackModel.rate × exp(ξ·σ_lnR), ξ ~ N(0,1) je Zelle a³, hochgetastet):**
- P1 MET-2D (kalibriert, Photonen + PAG-Zählung: 1,97 nm 3σ): mit a = 4,3 nm **LER 3σ 3–6 nm** (der Sockel erscheint);
  mit a = 1 nm ähnlich oder kleiner (mehr Zellen mitteln). Falsifikation: < 2,5 nm → Zellstatistik erzeugt den Sockel nicht.
- P2 NXE1716 (σ 9,4, Photonen 10,9 nm 3σ): Anstieg < 20 % (Quadratur eines 3–6-nm-Sockels).
- P3 Dosisunabhängigkeit: am MET-2D-Punkt bei 1,5× Dosis fällt der Photonenanteil ∝ 1/√Dosis, der Zellanteil bleibt.

**Preflight-Ergebnis Entwicklungsrauschen (b3_devnoise.py, MET-2D kalibriert, Photonen + PAG-Zählung, 3 Seeds × 2 Real. × 2048 Zeilen):**

| | Vorhersage | Messung (3σ) | Status |
|---|---|---|---|
| P1 ohne Zellrauschen | – | 1,97 nm | Referenz |
| P1 a = 4,3 nm | 3–6 nm | **3,60 nm** (Sockel in Quadratur 3,0) | hält |
| P1 a = 1,0 nm | ähnlich/kleiner | 3,47 nm | hält — **zellgrößen-invariant** (Rauschleistung/Volumen ∝ 1/(n₀·m), unabhängig von a) |
| P3 1,5× Dosis, a = 4,3 | Photonenanteil fällt, Sockel bleibt | 2,86 nm (CD 40, nicht auf Maß) | qualitativ konsistent |

Befunde: (1) Die aus der Poisson-Statistik der blockierten Einheiten abgeleitete Ratenstreuung erzeugt einen Sockel von ≈ 3 nm
3σ am MET-2D-Punkt — die Größenordnung des gemessenen Rests (unbiased ≈ 5,4 bei imec-artigem Bias; biased 6,7). (2) Das
Ergebnis hängt nicht von der Zellgröße ab (a = 1 vs. 4,3 nm: 3,47 vs. 3,60) — der einzige physikalische Parameter ist n₀. (3) Zwei
Mängel des Monkey-Patches: die lognormale Streuung exp(ξσ) hat Mittelwert exp(σ²/2) > 1 → CD driftet (57,8/51,0/50,8); n_eff
springt auf ≈ 100, d. h. das Zusatzrauschen ist zellskalig weiß entlang y (Eikonal je Zeile, keine KPZ-Glättung) — Obergrenze.
Nächste Schritte: mittelwerttreu (exp(ξσ − σ²/2)), P1 wiederholen, P2 NXE1716; dann Implementierung als
`development_stochasticity` mit n₀ aus der Zusammensetzung und Zellgröße als numerischem Parameter mit Invarianztest.

## 2026-09-06 (Fortsetzung 33): B3 — Entwicklungsrauschen implementiert (`development_stochasticity`)

**Zwei Lehren aus dem Preflight vor der Implementierung:** (1) Die lognormale Linearisierung exp(ξ·σ_lnR) mit σ_lnR =
|dlnR/dM|·M/√n explodiert dort, wo die Mack-Kurve steil ist (n = 19: σ_lnR ≈ 2,5 → Multiplikatoren e^{±5}); mittelwerttreu
(−σ²/2) verschiebt sie die CD trotzdem (54–63 nm statt 50, Medianrate e^{−3}). Deshalb **exakte Form**: pro Zelle wird die
Schutzfraktion selbst gestreut, M_cell = M + ξ·√(M/(n₀·a³)) (Gauß-Näherung der Poisson-Zählung, n₀·a³ ≈ 130 Plätze bei
a = 4,3 nm), und die Zelle löst sich mit R(M_cell); Multiplikator R(M_cell)/R(M). (2) Kachelinvarianz: der Realisations-Seed
für das Zellrauschen wird *vor* der Kachel-Entscheidung gezogen (bei n_tiles = 1 werden sonst keine Kachel-Seeds gezogen und
der Strom verschiebt sich); Zellgitter an absoluten Indizes verankert, je Zellzeile ein eigener Generator (seed, Zellzeile) →
bitidentisch für jede Kachelung (Test mit 1300 Zeilen, 512 vs. 10⁶). Bei ausgeschalteter Option wird nichts gezogen — alle
Goldens unverändert.

**Code:** `resist/develop.dissolution_cell_noise` (Quellen im Docstring: Mack 2010 JM3 9, 041202; Mack 2010 „Ultimate limits"
Gl. 36; Thackeray 2010 Rg 4,3 nm), `eikonal_development(rate_multiplier=…)` (chunk-sicher), `_develop_depth(…, rate_multiplier)`,
`_noisy_depth_map` (Seed + Feld je Kachel inkl. Halo), Config `blocked_site_density_per_nm3` (1,63 aus Zusammensetzung: 35 % von
4,66 Einheiten/nm³; Jin 2025: 2,26 bei 54,6 %) und `dissolution_cell_nm` (4,3). Der NotImplementedError von Audit A6 ist
ersetzt; das alte ereignisbasierte `stochastic_development` bleibt eine unbenutzte Standalone-Funktion. Nicht-Eikonal-
Entwicklung mit Rauschen → NotImplementedError (bewusst). Tests: `tests/test_dissolution_cell_noise.py` (Dichte aus
Zusammensetzung, Poisson-Streuung per Inversion mit linearem Ratengesetz, quenched/reproduzierbar/zellkonstant, absolute
Zeilenverankerung, Kachelinvarianz bitgenau, deterministische Kette unbeeinflusst, Validierung).

**Läufe mit dem implementierten Modell (b3_anchors_devnoise.py):** D2S/E-size werden *mit* Rauschen neu bisektiert (Mittel-CD
über 3 Seeds), dann LER/LWR mit 6 Seeds × 2 Real. × 2048 Zeilen; Zellgröße 4,3 und 2,15 nm am MET-2D-Punkt (Abhängigkeit ist
Physik, nicht Numerik — wird gemessen). Vorhersage (aus dem Preflight): MET-2D LER 3σ 2,5–4 nm; NXE1716 LWR < +20 %.

## 2026-09-06 (Fortsetzung 34): B3 — Ankerläufe mit dem implementierten Entwicklungsrauschen

**MET-2D (kalibriert, Photonen + PAG-Zählung + Zellrauschen, E-size mit Rauschen neu bisektiert: 13,17, unverändert), 6 Seeds × 2 Real. × 2048 Zeilen:**

| Zellgröße a | LER 1σ | 3σ | n_eff | gemessen |
|---|---|---|---|---|
| ohne Zellrauschen | 0,658 | 1,97 | 25 | 6,7 (biased) |
| **4,3 nm (Rg, Thackeray)** | 1,655 ± 0,017 | **4,96 nm** | 120–155 | 6,7 (biased), ≈ 5,4 falls Bias wie bei imec |
| 2,15 nm | 3,404 ± 0,042 | 10,21 nm | 320–350 | – |

Befund: **nicht zellgrößeninvariant** — halbe Zelle, doppelte LER (≈ ∝ 1/a). In der linearen Näherung war die Rauschleistung pro
Volumen zellunabhängig; in der exakten Form (M_cell → R(M_cell), Mack-Exponent 19) und mit der Erstankunfts-Entwicklung
(schnellster Pfad nutzt schnelle Zellen) ist sie es nicht. Die Zellgröße ist damit ein *physikalischer* Parameter — die Größe der
Einheit, die als Ganzes in Lösung geht — mit Quelle (Rg 4,3 nm), aber die Vorhersage trägt die Unsicherheit dieser Größe fast
linear. Zweiter Befund: n_eff 140–340 → die Zusatzrauigkeit ist zellskalig weiß entlang y, weil der Eikonal-Löser jede y-Zeile
unabhängig löst (keine KPZ-Glättung quer zur Zeile). Ein echter 3D-Löser (x, y, z) würde die Front über Nachbarzellen mitteln und
sowohl die Hochfrequenzanteile als auch die Zellgrößen-Sensitivität dämpfen — Kandidat B3.4, erst nach Gitter- und NXE1716-Lauf.
Mit a = 4,3 nm liegt die Kette bei 0,74× des biased bzw. ≈ 0,9× des bias-korrigierten Messwerts; das ist keine Validierung, weil a
den Wert um Faktor 2 verschieben kann, aber der erste Sockel mit Herleitung statt Knopf.

## 2026-09-06 (Fortsetzung 35): B3.4 — y-gekoppelter Eikonal-Löser (Vorhersagen VOR dem Lauf)

Der bisherige Löser löst jede y-Zeile als eigenes (x, z)-Problem (Zhao 2005, vektorisiert über y). Mit zellskaligem Ratenrauschen
ist das falsch: die Erstankunftsfront darf schnelle Zellen auch aus Nachbarzeilen erreichen (KPZ-Glättung quer zur Zeile).
Umsetzung: dritter Godunov-Term (Zhao 2005, d = 3: sortierte Nachbarn, 1-/2-/3-Term-Lösung), y periodisch, Nachbarwerte aus dem
vorigen Durchlauf (Jacobi in y, Gauss-Seidel in z, x), Abbruch bei tol; `dy=None` → bitidentisch zum alten Löser.
Invarianten geprüft: gleichförmige Rate T = z/R exakt; y-uniformes Zufallsfeld: 3D − 2D = 0 exakt; y-variables Feld:
max(3D − 2D) = 0, Mittel 2D − 3D = 0,097 s (mehr Wege → nie später). Option `development_model="eikonal3d"`; Default bleibt
„eikonal" (Goldens unverändert). Kacheln: y-Kopplung endet am Kachelrand, der Halo (> 200 Zeilen) ist viel größer als die
Kopplungslänge (Zellgröße) — Kachelabweichung wird gemessen, nicht angenommen.

**Vorhersagen (MET-2D kalibriert, Photonen + PAG + Zellrauschen, 3 Seeds × 2 Real. × 1024 Zeilen):**
- P1 a = 4,3 nm: LER 3σ **2,5–4 nm** (2D: 4,96); n_eff fällt von ≈ 140 auf < 60 (Hochfrequenzanteil geglättet).
- P2 a = 2,15 nm: **< 6 nm** (2D: 10,2) — die Zellgrößenabhängigkeit wird schwächer (Verhältnis 2,15/4,3 unter 1,6 statt 2,06).
- P3 ohne Zellrauschen (nur Photonen + PAG): 3D ändert die LER um < 10 % (glatte Felder).
- P4 Kachelung 512 vs. 10⁶ Zeilen bei 1300 Zeilen (Zellrauschen, 3D): max |ΔTiefe| < 0,5 nm, LWR-Differenz < 2 %.
Falsifikation: P1 > 4,5 nm oder P2/P1 > 1,8 → die Kopplung glättet nicht wie erwartet; dann bleibt B3 bei der 2D-Aussage.

**Gitterabhängigkeit (b3_grid.py, MET-2D, a = 4,3, 3 Seeds × 2 Real. × 2048 Zeilen):** grid 512 (dx 0,195 nm) LER 1σ 1,650 →
3σ 4,95 gegen 4,96 bei grid 256 — **lateral gitterinvariant**; die Zelle, nicht das Pixel, bestimmt das Rauschen (im Gegensatz
zum alten ereignisbasierten Modell von Audit A6). n_eff sinkt bei feinerem Gitter (37–92 statt 120–155), weil die Korrelations-
länge in Pixeln wächst; die LER-Zahl bleibt.

**NXE1716 mit Zellrauschen (2D-Löser, kalibriert, D2S mit Rauschen 10,70 ≈ unverändert, 6 Seeds × 2 Real. × 2048 Zeilen):**
LWR 1σ 4,99 ± 0,10 → **3σ 14,95 nm** (ohne Zellrauschen 10,9; Sockel in Quadratur 10,2 nm). Vorhersage „< +20 %" **falsifiziert**
(+37 %). Am dünnen Film (35 nm, dz 1,75 nm), bei 22 nm HP und flacher Mack-Kurve (n 12,8) ist der Zellbeitrag dreimal so groß
wie bei MET-2D — gegen unbiased ≈ 5,4 nm (Messung) liegt die Kette damit 2,8× zu hoch. Das ist die Kehrseite der 2D-Löser-
Überschätzung (weißes Zellrauschen entlang y); die Entscheidung fällt mit dem 3D-Preflight (Fortsetzung 35).

**P4 (3D + Zellrauschen, 1300 Zeilen, Kachel 512 vs. 10⁶):** max |ΔTiefe| < 10⁻⁴ nm, LWR identisch (< 10⁻⁴) — **kachelinvariant bis auf
Rundung** (nicht bitgenau: die Jacobi-Durchläufe konvergieren im Halo auf leicht anderen Wegen), weil die y-Kopplung pro Jacobi-Durchlauf eine Zeile weit reicht (≤ n_iter = 24 Zeilen) und der Halo (4σ/dx + 1
≥ 60 Zeilen) sie vollständig abdeckt. Als Test festgehalten.

**Ergebnis 3D-Preflight (b3_eik3d.py, MET-2D kalibriert, 3 Seeds × 2 Real. × 1024 Zeilen):**

| | Vorhersage | 2D | 3D | Status |
|---|---|---|---|---|
| P3 ohne Zellrauschen | Δ < 10 % | 1,88 | 1,88 (identisch) | hält |
| P1 a = 4,3 | 2,5–4 nm | 5,04 | **5,14 nm**, n_eff 212 (2D: 59) | **falsifiziert** — keine Glättung |
| P2 a = 2,15 | < 6 nm; P2/P1 < 1,8 | 10,2 | 7,41; **P2/P1 = 1,44** | Verhältnis hält, Absolutwert knapp nicht |
| P4 Kachelung | Δ < 0,5 nm | – | exakt 0 | hält |
| Rechenzeit | – | 44–49 s | 354–466 s (8–9×) | – |

Deutung: Die Amplitude der Erstankunfts-Rauigkeit wird von der Zellstatistik (quenched disorder) gesetzt, nicht von der
Lösergeometrie; die y-Kopplung verändert das Spektrum (kürzere Korrelation, n_eff 212) und mildert die Zellgrößenabhängigkeit
(∝ a⁻⁰·⁵ statt a⁻¹), senkt die LER aber nicht. Ein Eikonal-Löser hat keinen Krümmungsterm (KPZ-ν), die Front bleibt zellskalig
zackig. `eikonal3d` bleibt als validierte Option (Invarianten, exakte Kachelung) erhalten, Default bleibt „eikonal".

**Der entscheidende Nebenbefund:** n_eff 60–340 heißt, die Zusatzrauigkeit liegt bei Perioden von wenigen nm — **außerhalb des
Messbandes**: Anderson wertet 10–834 nm Periode aus (OSTI 950847, §III C), imec/metroLER ebenfalls bandbegrenzt (Pixel 0,8 nm,
PSD-Rauschabzug). Unser Schätzer integriert bis 2 Pixel (0,35–0,8 nm). Vergleich Kette–Messung ist damit nicht bandgleich; ein
messbandgleicher LER-Schätzer (Bandpass in y, Grenzen aus der jeweiligen Quelle) ist kein Physik-Knopf, sondern die
Voraussetzung für jeden Vergleich. Nächster Schritt B3.5: Passband im Schätzer, dann beide Anker neu bewerten. Vorhersage:
der Zellanteil fällt stark (MET-2D 5,0 → 3–4 nm, NXE1716 15 → 8–10), der Photonenanteil (Korrelation ≈ Blur) kaum.

## 2026-09-06 (Fortsetzung 36): B3.5 — messbandgleicher LER/LWR-Schätzer (Vorhersagen VOR dem Lauf)

Messbänder aus den Quellen: Anderson/Naulleau 2008 (OSTI 950847 §III C): Perioden **10–834 nm** (Rauschgrenze bis Bildhöhe).
Vesters 2019 §5.3 (imec „biased"-Protokoll, Kap. 4): Rechteckscan 1024 px mit Pixel 0,88 × 5,38 nm, Bildhöhe 5,5 µm → Perioden
**≈ 10,8–5500 nm** (Nyquist des 5,38-nm-Pixels); unbiased-Protokoll 2048 px × 0,8 nm → 1,6–1640 nm mit PSD-Rauschabzug.
Kette: Feld 2048 Zeilen × dx 0,17–0,39 nm → Perioden 0,35–800 nm, ungefiltert. Umsetzung: `ler_passband_nm=(p_min, p_max)`
in SimulationConfig (None = Vollband, Default; Goldens unverändert), Bandpass per FFT entlang y auf die Kantenprofile vor
RMS/Autokorrelation (periodisches Feld, DC bleibt entfernt); Anker-Presets tragen ihr Messband.

**Vorhersagen (Band Anderson für MET-2D, Band imec-biased für NXE1716; a = 4,3, 2D-Löser, 6 Seeds × 2 Real. × 2048 Zeilen):**
- P1 MET-2D Photonen + PAG: 1,97 → **1,6–1,9 nm** (Korrelation ≈ Blur 10 nm, wenig Leistung unter 10 nm Periode).
- P2 MET-2D + Zellrauschen: 4,96 → **3,0–4,0 nm** (Zellanteil bei 4-nm-Perioden liegt großteils unter 10 nm).
- P3 NXE1716 Photonen: 10,9 → **9–10,5 nm**; P4 NXE1716 + Zellrauschen: 15,0 → **8–10 nm**.
Falsifikation: P2 > 4,5 oder P4 > 11 → der Zellanteil ist nicht hochfrequent genug, dann bleibt die Überschätzung ein Modellfehler.

**Ergebnis bandbegrenzt (b3_passband.py, 6 Seeds × 2 Real. × 2048 Zeilen, a = 4,3, 2D-Löser):**

| | Vorhersage | Vollband | **Messband** | gemessen (biased) | unbiased-Schätzung |
|---|---|---|---|---|---|
| P1 MET-2D Photonen + PAG | 1,6–1,9 | 1,97 | **1,97** | 6,7 | ≈ 5,4 (falls Bias wie imec) |
| P2 MET-2D + Zellrauschen | 3,0–4,0 | 4,96 | **4,29** | 6,7 | ≈ 5,4 |
| P3 NXE1716 Photonen | 9–10,5 | 10,9 | **10,86** | 6,7 | 5,1–5,7 |
| P4 NXE1716 + Zellrauschen | 8–10 | 14,95 | **13,15** | 6,7 | 5,1–5,7 |

Bewertung nach Vorregistrierung: P1/P3 praktisch unverändert (Photonenterm hat keine Leistung unter 10 nm Periode — erwartet);
**P2 knapp, P4 klar verfehlt** (Kriterium „P4 > 11 → Modellfehler bleibt"). Nur ≈ 30 % der Zellrausch-Leistung liegt unter
10 nm Periode; in-band bleiben bei MET-2D 3,8 nm und bei NXE1716 7,4 nm (Quadratur). Stand B3 damit:
- **MET-2D:** Kette 4,3 nm 3σ (Photonen 2,0 ⊕ Zellen 3,8) gegen 6,7 biased / ≈ 5,4 bias-korrigiert — innerhalb der Bias-
  Unsicherheit (Andersons Bias ist nicht publiziert). Das ist das erste Mal, dass die Kette eine gemessene EUV-LER ohne
  Rauschknopf in der richtigen Größe liefert; validiert ist es nicht, solange (i) Andersons SEM-Anteil und (ii) die
  Auflösungseinheit a (Rg 4,3 nm) nicht unabhängig belegt sind — a verschiebt den Zellterm ∝ 1/a.
- **NXE1716:** Kette 13,2 gegen 5,1–5,7 unbiased (2,4×). Der Photonenterm allein (10,9) ist schon 2× zu groß und hängt am
  Blur 9,4 nm (τ von 110 °C; mit σ 5 nm: 4,8); der Zellterm addiert 7,4 nm in Quadratur. Beide Anker zusammen sagen: die
  Zellstatistik erklärt den Sockel am dicken Film/50 nm, am dünnen Film/22 nm HP überschätzt die Kette systematisch —
  Kandidaten mit Beleg-Pfad: Blur bei 90 °C (C1-Temperaturmodell aus Yamamoto Fig. 3 + NIST τ 38 s mit Quencher), n₀ und a für
  NXE1716 (unbekannt), und die Eikonal-Front ohne Krümmungsterm (zackig auf Zellskala).
Keine Parameter wurden an Messwerte angepasst; `development_stochasticity` und `ler_passband_nm` bleiben per Default aus.

## 2026-09-06 (Fortsetzung 37): C1 — Temperaturmodell k(T), τ(T) aus Yamamoto 2011 Fig. 3/4 (Vorhersagen VOR der Digitalisierung)

Quelle: Yamamoto et al., JPST 24(4) 405 (2011), Fig. 3: Schutzgrad P(t) bei 80/90/100/110/120/130/140 °C nach 1,4 mJ/cm² Flood,
Polymer A (35 %); Fig. 4: Arrhenius von Kdp mit **zwei Bereichen** (tief: reaktionskontrolliert, hoch: diffusionskontrolliert,
Byers–Petersen); Table 1: Ea 27,8 „kcal/mol" für 35 % (Text) vs. „kJ/mol" (Table 2 der PROLITH-Parameter) — die Einheitenfrage
aus Fortsetzung 15. Gl. (1) des Papers enthält K_loss (Säureverlust) und Ordnung m.
Vorgehen: Fig. 3 per Farbclusterung je Temperatur digitalisieren, je Kurve unser Kettengesetz P(t) = exp(−k·H₀·τ·(1 − e^{−t/τ}))
fitten (H₀ = 1 − e^{−C·1,4} fest, C = 0,0152 → k·H₀ und τ je T), dann Arrhenius für k und τ.

**Vorhersagen:**
- V1 Einheitenfrage: Anfangssteigungen k·H₀ von 80 → 110 °C wachsen um Faktor **≥ 5** (kcal-Lesart: Ea 116 kJ/mol → k(80)/k(110)
  ≈ 0,09) und nicht nur um 1,7 (kJ-Lesart). Aus der Vorschau: 80 °C erreicht P ≈ 0,4 erst nach 150 s, 110 °C P ≈ 0,18 in 20 s.
- V2 τ(T) fällt mit T (Säureverlust thermisch aktiviert): τ(90 °C) = **20–45 s** (τ(110 °C) = 10,5), verträglich mit NIST 38 s
  bei 90 °C (JSR-Resist) innerhalb Faktor 2; τ(130–140 °C) < 6 s.
- V3 Plateaus P∞ = exp(−k·H₀·τ) fallen monoton mit T (0,4 → 0,05); die Fits liefern rms ≤ 0,03 je Kurve.
- V4 Folge für 90-°C-Presets: t_eff(90) = τ(1 − e^{−60/τ}) = 18–40 s → Blur √(2·4,2·t_eff) = **12–18 nm** ohne Quencher — der
  NXE1716-Anker würde damit bei 11 mJ/cm² *nicht* drucken; das wäre der belegte Beweis, dass D = 4,2 nm²/s (Kang, quencherfrei)
  in Linien mit Quencher nicht als freie Diffusion wirkt (NIST: Diffusionslänge 36 → 14 nm mit Quencher).

**Ergebnis Digitalisierung Fig. 3 (7 Kurven × ≈ 106 Stützstellen bis 111 s, Farbclusterung, Overlay geprüft; scratchpad/
yam_fig3_digitised.json) und Fits des Kettengesetzes je Temperatur (H₀ = 0,02105 bei C 0,0152):**

| T (°C) | k·H₀ (s⁻¹) | k (s⁻¹) | τ (s) | P∞ | rms |
|---|---|---|---|---|---|
| 80 | 0,0142 | 0,67 | 69,0 | 0,376 | 0,010 |
| 90 | 0,0439 | 2,09 | **35,2** | 0,213 | 0,012 |
| 100 | 0,0978 | 4,65 | 16,3 | 0,202 | 0,014 |
| 110 | 0,2305 | **10,95** | **7,5** | 0,176 | 0,014 |
| 120 | 0,502 | 23,8 | 4,1 | 0,128 | 0,021 |
| 130 | 0,439 | 20,9 | 6,2 | 0,065 | 0,029 |
| 140 | 0,624 | 29,6 | 5,1 | 0,041 | 0,019 |

Arrhenius k: 80–110 °C **Ea = 103 kJ/mol = 24,7 kcal/mol** (Yamamoto Table 1: 27,8 kcal/mol → **die kcal-Lesart ist richtig**,
Fortsetzung 15 aufgelöst), 110–140 °C 38 kJ/mol (diffusionskontrolliert, Byers–Petersen — wie im Paper beschrieben).
τ: 80–110 °C „Ea" −83 kJ/mol (τ fällt steil), 110–140 °C −10 kJ/mol (τ ≈ 4–6 s, Plateau).
- V1 hält (k(80)/k(110) = 0,06, Faktor 16 statt ≥ 5). V2 hält: **τ(90 °C) = 35 s**, NIST (JSR-Resist) 38 s — zwei Resists, zwei
  Methoden, 8 % Abstand. V3 hält (P∞ monoton bis auf 100/110: 0,202/0,176; rms ≤ 0,03).
- Nebenbefund 110 °C: Vollkurven-Fit k·H₀ 0,2305, τ 7,5 statt der 5-Punkt-Lesung (0,166, 10,5). Produkt k·τ·H₀ = 1,73 identisch
  (P∞, Fig.-5-Schwelle unverändert), aber t_eff 7,5 statt 10,5 s → **Default-Blur 9,4 → 7,9 nm**. Preflight vor Übernahme.
- V4 ist durch Fortsetzung 29 schon belegt: mit τ ≈ 38 s (Blur 15,9 nm) druckt NXE1716 bei 11 mJ/cm² nicht (D2S 23,5) —
  D = 4,2 nm²/s als freie Diffusion über t_eff(90 °C) ist in Linien mit Quencher falsch; NIST misst mit Quencher 14 statt 36 nm.
Fig. 4 (Arrhenius-Punkte) wurde nicht weiter digitalisiert: die Fig.-3-Fits liefern Kdp(T) in unserer eigenen Modellform.

**Preflight 110-°C-Verfeinerung (k 10,95, τ 7,5 statt 7,87/10,5), Default-Resist, vorab:** D2S P = 64: 1,297 → **1,27–1,30** (Blur
−15 % → Modulation +1,5 %); P = 44: 1,649 → **1,58–1,64**; Photonen-LWR P = 44 bei eigener D2S (3 Seeds × 2 × 1024): **−5…−20 %**
gegenüber 9,1 (weniger Glättung, aber steilere Kante: bei P = 44 dominiert die Steigung). Yamamoto-Anker: P(60) 0,176, Schwelle
unverändert ±1 %.

**Preflight-Ergebnis 110-°C-Verfeinerung (c1_preflight.py):**

| | Vorhersage | alt (7,87 / 10,5) | neu (10,95 / 7,54) | Status |
|---|---|---|---|---|
| P(60 s, 1,4) / Schwelle | ±1 % | 0,1765 / 0,764 | 0,1776 / 0,766 | hält |
| D2S P = 64 | 1,27–1,30 | 1,299 | 1,301 (+0,2 %) | am Bandrand (praktisch unverändert) |
| D2S P = 44 | 1,58–1,64 | 1,668 | 1,602 (−4 %) | hält |
| Photonen-LWR P = 44 | −5…−20 % | 9,10 | 8,52 (−6 %) | hält |

**Übernommen:** peb_k 10,95 s⁻¹, peb_acid_lifetime_s 7,54 s (Vollkurven-Fit statt 5-Punkt-Lesung; gleiche Quelle, gleiches Produkt,
Default-Blur 9,4 → 7,9 nm), CLI-Defaults, `peb_temperature_c` (80–140 °C, log-linear in 1/T zwischen den gemessenen Temperaturen,
Warnung bei Klammerung) und `--peb-temperature`. Datensatz `data/anchors/yamamoto2011_fig3_polymerA.json` (7 Kurven + Fits).
Tests: `tests/test_peb_temperature.py` (Tabelle reproduziert, τ(90) vs NIST innerhalb 15 %, alle sieben Kurven rms ≤ 0,03,
k·H₀-Erhalt bei anderem C, Klammer-Warnung). Goldens werden neu abgeleitet (t_eff 10,47 → 7,54 s; Regressionstests setzen
σ_PEB = 7 explizit, nur die Deprotektion ändert sich um 0,4 %).
Goldens neu (derive_goldens.py, TEST_DOSE 1,1, σ_PEB 7 explizit): LER 3,4549120045 (vorher 3,4895922982), LWR 6,5152989645, n_eff 32,12,
l_int 16,10, ρ-Trunkierung 145, Legacy 0,8741763497 / 1,6958567854 — Verschiebung ≈ 1 %, wie erwartet (nur t_eff-Effekt auf die
Deprotektion). Fünf-Punkt-Test der Fig.-3-Kurve auf die digitalisierten Werte umgestellt (die Handlesung 0,60 bei 5 s war 0,1 zu hoch).

## 2026-09-06 (Fortsetzung 38): C2 — PEB als gekoppelte Reaktions-Diffusion mit gleichzeitiger Neutralisation (Vorhersagen VOR dem Lauf)

Befund aus C1/B2: Unsere PEB-Stufe diffundiert die Säure erst vollständig (σ = √(2·D·t_eff)) und neutralisiert danach
(geschlossene Form). Real laufen Diffusion, Verlust, Neutralisation und Deprotektion gleichzeitig; Säure, die in die
quencherreiche Linie diffundiert, wird dort sofort verbraucht — die wirksame Reichweite der Deprotektion ist viel kürzer als die
freie Diffusionslänge (NIST/Kang 2009: 36 → 14 nm mit Quencher). Genau das fehlt der Kette (NXE1716 mit τ(90 °C) undruckbar).
**Modell (Kang/Prabhu, NIST, SPIE 7273 Gl. in §2; Mack 2011 Quenching):** ∂H/∂t = D_H∇²H − k_T·H − k_Q·H·Q; ∂Q/∂t = D_Q∇²Q − k_Q·H·Q;
∂M/∂t = −k_P·H·M. Alle Parameter mit Quelle: D_H 4,2 nm²/s (Kang 90 °C), k_T = 1/τ(T) (Yamamoto/NIST), k_Q 12,6–15 nm³/s (Osaka/Mack),
k_P (aus k·H₀ der Fig.-3-Fits bzw. NIST 1,6 nm³/s), D_Q (Osaka: = D_H; NIST fittet D_Q nicht separat).
**Anker mit null freien Parametern: NIST Table 2** (Bilayer, PEB 90 °C/900 s, PAG 2 Massen-% oben = 0,035 nm⁻³ (TPS-Triflat 412 g/mol,
1,2 g/cm³), Quencher 60 mol % rel. PAG, alle PAG konvertiert (150 mJ/cm² DUV), Löslichkeitsschwelle Deprotektion 0,14):
gemessene Diffusionslängen **76 / 56 / 36 / 23 nm** (kein Q / Q oben / Q unten / Q beidseitig), NISTs eigene Modellvorhersage
79 / 59 / 30 / 23.
**Vorhersagen:** P1 1D-Rechnung mit NISTs Parametern (kP 1,6, kT 0,026, DH 4,2, DQ = DH, kQ 12,6) trifft die vier Längen innerhalb
**±20 %** (NISTs Fit: ±17 % beim dritten Fall). P2 Ohne Quencher-Term (unser bisheriges Bild) sind Fall 2–4 identisch mit Fall 1 →
das alte Modell kann die Tabelle nicht reproduzieren. P3 Nach Einbau in die Kette: NXE1716 (q 0,13, τ 35 s, D 4,2) druckt bei
< 20 mJ/cm² (statt „nicht"), D2S bleibt aber > 11.

**1D-Nachrechnung NIST Table 2 (scratchpad/c2_nist_bilayer.py, explizit, dx 0,5 nm, 900 s):** Erste Fassung mit *unserem* Verlustgesetz
(k_T·H, erster Ordnung) ergab 25/12/6/2 nm — Faktor 3–14 zu kurz: **NISTs Trapping ist k_T·H·φ**, also Verlust durch bereits
deprotektierte Stellen (Gl. 2 im Paper), nicht erster Ordnung in der Zeit. Mit den exakten NIST-Gleichungen (Gl. 1–3) und k_Q = 12,6:
**83 / 68,5 / 11 / 4 nm** gegen gemessen 76 / 56 / 36 / 23 (NIST-Modell 79 / 59 / 30 / 23). Fälle 1–2 (P1 ±20 %: 1,09 / 1,22 —
Fall 2 knapp außerhalb) passen, Fälle 3–4 mit Quencher im Zielfilm sind 3–6× zu kurz → **k_Q = 12,6–15 nm³/s ist um eine
Größenordnung zu groß**; NIST nennt k_Q in Table 1 nicht. P2 hält (ohne Quencherterm wären alle Fälle gleich). Folge: k_Q wird
als *ein* Parameter an Fall 3 bestimmt und Fall 4 als Vorhersage geprüft (vorregistriert: k_Q ≈ 1–2 nm³/s, Fall 4 dann ±25 %).
Das betrifft auch Macks 15 nm³/s und Osakas 12,6 (beides Modellannahmen, keine Messungen) — und unsere Quencher-Fits (B2), die
mit „vollständiger Neutralisation" rechneten.

**k_Q-Scan (NIST-Gleichungen, D_Q = D_H, ein Parameter an Fall 3, Fall 4 als Vorhersage):**

| k_Q (nm³/s) | Fall 1 | Fall 2 | Fall 3 | Fall 4 |
|---|---|---|---|---|
| gemessen | 76 | 56 | 36 | 23 |
| 0,5 | 83 | 73 | 43,5 | 38,5 |
| **1,0** | 83 | 68,5 | **33,5** | **27,5** |
| **1,5** | 83 | 66 | **28,5** | **22,0** |
| 2,0 | 83 | 64,5 | 25 | 18,5 |
| 12,6 (Osaka) / 15 (Mack) | 83 | 68,5 | 11 / 10 | 4 / 3 |

**k_Q(90 °C) ≈ 1,0–1,5 nm³/s** (JSR-Resist, NIST 2009): Fall 3 und 4 innerhalb ±20 %, Vorhersage für Fall 4 hält (vorregistriert ±25 %).
Fall 2 bleibt +22 % (Quencher in der Säureschicht) — Modellgrenze, nicht nachjustiert. Immobiler Quencher (D_Q = 0) ändert wenig
(26,5 / 21,5). **Unser Default k_Q = 15 nm³/s (Mack 2011, Modellannahme) ist damit um eine Größenordnung zu groß** — der einzige
messbasierte Wert liegt bei ≈ 1,2 nm³/s. Konsequenz für die Kette: (i) Neutralisation ist bei PEB-Bedingungen *nicht* vollständig
(k_Q·G₀·t_eff ≈ 1,2·0,2·7,5 = 1,8 statt 26), (ii) der Quencher-Fit B2 (q₁₇₁₆ ≈ 0,13) beruhte auf vollständiger Neutralisation und
ist neu zu bewerten, (iii) das Trapping k_T·H·φ (Verlust nur an deprotektierten Stellen) ist ein anderes Gesetz als unser τ.

**Modellvergleich auf Yamamoto Fig. 3 (beide Gesetze, je 2 Parameter pro Temperatur):** NIST-Trapping k_T·H·φ rms 0,012–0,027,
erster Ordnung (τ) rms 0,010–0,029 — **Flood-Daten unterscheiden die Gesetze nicht** (φ ist dort räumlich uniform). Der Bilayer
unterscheidet sie um Faktor 3 (25 vs 83 nm). Entscheidung C2: neues PEB-Modell `reaction_diffusion` mit NISTs Gl. 1–3 (Trapping an
deprotektierten Stellen, gleichzeitige Neutralisation und Deprotektion, Diffusion von H und Q), Parameter je Temperatur aus den
Fig.-3-Refits (k_P·H₀, k_T; 110 °C: 0,188 s⁻¹, 0,208 s⁻¹; 90 °C: 0,037, 0,053 — NIST JSR bei 90 °C: k_T 0,026, Faktor 2 zwischen
Resists), k_Q 1,2 nm³/s (NIST-Bilayer), D_H 4,2, D_Q = D_H (Annahme, Osaka/NIST). Default bleibt das analytische Modell (Goldens);
Umschaltung per Config. Test mit null freien Parametern: NIST Table 2 durch die Kettenfunktion (Fall 3/4 ±25 %).

**C2 umgesetzt (Kernfunktion):** `resist/peb.reaction_diffusion_pde` — NIST Gl. 1–3 in relativen Konzentrationen, Operator-Splitting
(exakte Gauß-Diffusion per FFT lateral + z, dann exakte Neutralisation zweiter Ordnung, Trapping k_T·h·φ, Deprotektion), Schrittweite
so, dass σ_Schritt ≥ 3 Zellen. `tests/test_reaction_diffusion_pde.py`: **NIST Table 2 durch die Kettenfunktion: alle vier Fälle
innerhalb der vorregistrierten Toleranzen** (76/56/36/23; k_Q 1,2 an Fall 3, Fall 4 als Vorhersage), Quencher verkürzt die Reichweite
um > 40 %, uniformer Flood reduziert auf die ODE (Vergleich mit feiner expliziter Integration, 2·10⁻³).

**C2 in der Kette:** `peb_model="reaction_diffusion"` (Config, beide Pfade über `_peb_step`), `peb_k_trap_per_s` (110 °C: 0,2076),
`peb_D_quencher` (None = D), `peb_temperature_c` setzt für dieses Modell (k, k_trap) aus der NIST-Gesetz-Tabelle
(`kinetics.yamamoto_polymer_a_kinetics_nist_law`). Default bleibt „analytical" (Goldens). Die Neutralisationskonstante wird in einem
eigenen Schritt behandelt (Default 15 → 1,2 betrifft auch den analytischen Pfad mit Quencher).

**Vorhersagen Kette (vor dem Lauf), Default-Resist bei 110 °C, deterministisch:** P1 reaction_diffusion vs analytical bei gleichem
k·H₀-Produkt: D2S P = 64 innerhalb ±5 % (uniforme Flood-Äquivalenz beider Gesetze; im Muster Trapping nur in deprotektierten
Spaces → etwas mehr Reichweite → D2S eher niedriger). P2 NXE1716-Preset (q₁₇₁₆ 0,13, k_Q 1,2, k_trap(90 °C) 0,053, D 4,2, k aus
DRM-Refit mit NIST-Gesetz): druckt bei **< 20 mJ/cm²** (mit τ-Gesetz und τ(90 °C) 35 s: undruckbar); D2S bleibt > 11.
Nebenbefund beim Umstellen der Defaults: die Anker-Presets (NXE1716, MET-2D) hatten τ nicht explizit gesetzt; mit dem C1-Default 7,54 s
verschob sich die NXE1716-Flood-Kurve (Schaltpunkt 19,6 statt 13,5) — die Presets pinnen jetzt τ = 10,5 s (der Wert ihres Fits).
Regel daraus: ein Preset, das aus einem Fit stammt, muss *alle* Größen des Fits explizit tragen, nicht nur die gefitteten.

**C2-Preflight-Ergebnis (c2_preflight.py; Laufzeit ≈ 45 min allein auf dem M1, das PDE-Modell braucht bei grid 256 ≈ 900 Schritte):**

| | Vorhersage | analytisch | reaction_diffusion | Status |
|---|---|---|---|---|
| P1 D2S P = 64 (Default-Resist, 110 °C) | ±5 % | 1,296 | **0,672** (−48 %) | **falsifiziert** |
| P1 D2S P = 44 | ±5 % | 1,597 | **0,838** (−48 %) | **falsifiziert** |
| P2 NXE1716 ohne Quencher (k 0,131, n 16,7 aus DRM-Refit mit NIST-Gesetz, rms 0,046) | D2S < 20 | 19,7 (τ-Gesetz) | 21,4 | falsifiziert (knapp) |
| P2 NXE1716 mit q 0,148, k_Q 1,2 | – | – | 39,7 | nicht fair: Flood-Refit ohne Quencher, Muster mit Quencher (Doppelzählung) |

Deutung: Beim NIST-Gesetz verliert Säure nur an deprotektierten Stellen; in schwach belichteten Bereichen (kleines φ) lebt sie
über die ganze Bake-Zeit und deprotektiert weiter, beim τ-Gesetz ist sie nach 7,5 s weg. Auf der Flood-Kurve (φ uniform, 1,4 mJ/cm²)
sind beide Gesetze ununterscheidbar (Fortsetzung 38), im Muster halbiert das NIST-Gesetz die Druckdosis. **Welches Gesetz für
Polymer A gilt, ist mit Yamamotos Daten nicht entscheidbar**; der NIST-Bilayer (JSR-Resist) spricht für das NIST-Gesetz. Deshalb:
`reaction_diffusion` bleibt validierte Option, Default „analytical" (Goldens, Rechenzeit ×6), die Sensitivitätsverdopplung ist
als *falsifizierbare Differenz* dokumentiert — eine einzige strukturierte Messung an Polymer A (Bilayer oder Dosis-zu-Maß) würde
sie entscheiden. NXE1716: das PDE-Modell ändert die 1,8×-Dosisdiskrepanz nicht (21,4 vs 19,7); ein konsistenter Quencher-Fit
(Flood *mit* Quencher im PDE-Modell, k_Q 1,2) steht aus und ist mit ≈ 1 h Laufzeit pro Fit auf dieser Maschine zu planen.
Suite C1/C2: 934 bestanden + 1 Konvergenzschranke (`test_stochastic_consistency`, 0,0866 nm gegen 0,5 px = 0,0859): der Zählrausch-Rest
bei ρ = 2000 skaliert mit 1/√(ρ·V_Blur), V_Blur ist mit dem C1-Blur (9,4 → 7,9 nm) um 0,59 kleiner → Schranke 0,75 px (Invarianten
unverändert), Modul danach 5/5. Notebooks wurden mit den C1-Defaults neu ausgeführt (vor dem k_Q-Default; nur Notebooks mit Quencher
> 0 wären betroffen — keine). Laufzeitregel (M1, 8 GB): ein schwerer Lauf zur Zeit, Preflights klein.

## 2026-09-06 (Fortsetzung 39): Quencher-Fit NXE1716/1717 im Reaktions-Diffusions-Modell (Vorhersagen VOR dem Lauf)

Konsistent zum C2-Modell: Flood-Kurven beider Resists mit `reaction_diffusion_pde` (uniform, D wirkungslos), k_trap(90 °C) = 0,0528
(Polymer-A-Tabelle), k_Q = 1,2 nm³/s, G₀ 0,2, Mth 0,39, Plateaus aus den Daten, geteiltes k, n je Kurve, q₁₇₁₆ = 2·q₁₇₁₇.
Vorhersagen: V1 q₁₇₁₆ = 0,10–0,18 (k_Q·G₀ = 0,24 s⁻¹ → Neutralisation im Flood in ≈ 4 s praktisch vollständig, also nahe B2);
V2 rms ≤ 0,08 beide Kurven; V3 Muster (grid 128, 1024 Zeilen, deterministisch) D2S NXE1716 mit Quencher im PDE-Modell **18–30 mJ/cm²**
(gemessen 11) — die Dosisdiskrepanz bleibt; V4 Laufzeit des Muster-Preflights auf dem M1 < 30 min.

**B4b Quellen für die Auflösungseinheit a (leichte Recherche während des Laufs):** Schmid/Willson 2001 (SPIE 4345, frei): Monomer ≈ 1 nm,
Rg typischer Kette ≈ 5 nm, Critical-Ionization-Gittermodell mit Monomerzellen. Zusammen mit Thackeray (Rg 4,3) und Jin 2025 (Mw 12,7k)
ist a physikalisch auf 1–5 nm eingegrenzt; unser 4,3 nm liegt am oberen Rand. Da der Sockel ∝ 1/a (2D) ist, bleibt seine Unsicherheit
Faktor 2–4, bis die Auflösungseinheit über ein Kettenmodell (CI) statt einer Zelle belegt ist. Notiert im Katalog.

**Ergebnis PDE-konsistenter Quencher-Fit (c2_qfit.py):** k = 0,461 s⁻¹, n₁₇₁₆ = 12,7, n₁₇₁₇ = 14,2, **q₁₇₁₆ = 0,363** (Q = 0,073 nm⁻³,
Q/PAG 0,36), rms 0,042 / 0,070. V2 hält; **V1 falsifiziert** (erwartet 0,10–0,18): im NIST-Gesetz überlebt Säure bei kleinem φ länger und
die Neutralisation mit k_Q 1,2 ist anfangs unvollständig, also braucht dieselbe Dosisverschiebung mehr Quencher. Q/PAG 0,36 liegt
zwischen Mack 2011 (0,25) und Osaka 2025 (0,5) — plausibler als die 0,13 aus B2 — und die Mack-n liegen bei 13–14 statt an der
Schranke 2. **V3: D2S (PDE, Quencher, grid 128) = 18,97 mJ/cm²** (vorhergesagt 18–30; gemessen 11,0): die Dosisdiskrepanz bleibt
bei 1,7×, unabhängig vom PEB-Gesetz. **V4:** 11 s pro Lauf bei grid 128, Preflight gesamt 95 s — das PDE-Modell ist bei grid 128
praktikabel, bei grid 256 (dt ∝ dx²) ≈ 8× teurer. Umsetzung: zweiter Konstantensatz `NXE1716_QUENCHER_FIT_PDE` im Preset
(`explicit_quencher=True, peb_model="reaction_diffusion"`), Flood-Helfer `flood_rate_pde`, Test auf beide Kurven.

## 2026-09-06 (Fortsetzung 40): C2b — Photon-Säure-Multiplizität (Analyse und Vorhersage VOR dem Lauf)

Plan-Punkt 3.3 behauptete: „die Bündelung mehrerer Säuren pro Photon (zusammengesetzter Poisson-Prozess, Mack 2011) wird nicht
abgebildet". Analyse: Die Kette sampelt Photonen (Poisson je Voxel), verteilt jede Photonenenergie mit dem SE-PSF und konvertiert
PAG binomial mit p = 1 − e^{−C·E_lokal}. Bedingt auf das Photonenfeld ist die Säurezahl A binomial mit Var ≈ E (p klein); über die
Photonen gemittelt gilt Var(A) = Var(E[A|N]) + E[Var(A|N)] = m²·N + m·N = N·m·(m + 1) — exakt die Varianz eines zusammengesetzten
Poisson-Prozesses mit Poisson-verteilter Multiplizität (Mittel m Säuren pro absorbiertem Photon). Räumlich sind die Säuren eines
Photons innerhalb des PSF-Radius gebündelt. **Die Multiplizität ist also implizit enthalten**, sofern die Verteilung der Säuren pro
Photon Poisson-artig ist; abweichen könnte nur eine nicht-Poisson-Verteilung (Mack 2011 Table 3: Cmax, r_e, γ).
**Vorhersage (Sampler, uniforme Dosis, Blöcke ≫ PSF):** Fano-Faktor Var(A)/E(A) der Säurezahl pro Block = **1 + m mit m = 1,0**
(Defaults: C 0,0152, G₀ 0,2, α 4,44 → 1,0 Säure/absorb. Photon an der Oberfläche) → **2,0 ± 0,2**; ohne Photonenrauschen (Mean-Field-
Dosis) 1,0. Trifft das zu, schließt C2b ohne Codeänderung; sonst fehlt Varianz.

**Ergebnis C2b:** Fano-Faktor der Säurezahl pro 21,8-nm-Block: mit Photonenrauschen **1,913** (Vorhersage 2,0 ± 0,2), mit Mean-Field-Dosis
0,955 (Vorhersage 1,0). Beide halten → die Photon-Säure-Multiplizität (Poisson-artig, Mittel m = 1,0 Säuren pro absorbiertem Photon)
ist in der Kette bereits enthalten; Plan-Punkt 3.3 war ein Irrtum der Analyse vom 2026-09-05. Kein Code geändert; als Test gepinnt
(`tests/test_acid_multiplicity.py`). Offen bleibt nur eine *nicht*-Poisson-Verteilung der Säuren pro Photon (Mack 2011 Table 3, γ),
für die keine Messung vorliegt.
