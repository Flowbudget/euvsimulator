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
