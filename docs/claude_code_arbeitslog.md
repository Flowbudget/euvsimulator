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
