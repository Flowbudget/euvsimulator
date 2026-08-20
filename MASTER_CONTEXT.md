# EUVSIMULATOR – STRATEGISCHER MASTERKONTEXT / NEUAUSRICHTUNG

Stand: August 2026

WICHTIG:
Dieser Kontext ersetzt frühere strategische Ausrichtungen, Roadmaps und Prioritäten für EUVsimulator, sofern diese diesem Dokument widersprechen.

NICHT löschen oder überschreiben:
- bestehende funktionierende Implementierungen
- Tests
- physikalische Erkenntnisse
- Messdaten und Validierungsergebnisse
- bereits gefundene Bugs und deren Ursachen
- historische Reports

Stattdessen gilt:
Alte strategische Annahmen dürfen als VERALTET betrachtet und bei zukünftigen Entscheidungen nicht mehr als Zielvorgabe verwendet werden.

============================================================
1. ÜBERGEORDNETES ZIEL
============================================================

EUVsimulator soll langfristig ein seriöses, wissenschaftlich belastbares Open-Source-Werkzeug für EUV-Lithographie werden.

Das Ziel ist NICHT:
- ASML vollständig nachzubauen
- möglichst viele Features möglichst schnell einzubauen
- eine beeindruckende Demo zu erzeugen
- eine "KI-Approximation" physikalischer Modelle zu bauen

Das Ziel ist:

Eine offene, reproduzierbare, modular aufgebaute EUV-Lithographie-Simulationsplattform, deren physikalische Modelle nachvollziehbar, testbar und gegen analytische Lösungen, Literatur und Referenzsoftware validierbar sind.

Der Umfang darf deutlich kleiner als kommerzielle Systeme sein.

Die physikalische Korrektheit der implementierten Teilmodelle darf dagegen NICHT bewusst auf "ungefähr richtig" reduziert werden.

Grundprinzip:

WENIGER PHYSIKALISCH KORREKTE FEATURES
>
MEHR FEATURES MIT UNSICHERER PHYSIK

============================================================
2. LANGFRISTIGE VISION
============================================================

EUVsimulator soll möglichst viele wichtige Stufen der EUV-Lithographie-Kette abdecken:

1. Maskengeometrie
2. optische Eigenschaften der Maske
3. Multilayer / Spiegel
4. Diffraction / Abbe / Hopkins / TCC
5. ggf. RCWA
6. Pupil / NA / Polarisation
7. Aerial Image
8. Dose
9. Resist-Absorption
10. Photoacid generation
11. Post Exposure Bake / Diffusion
12. Resist Chemistry
13. Development
14. Final Resist Profile
15. CD / NILS / Contrast
16. Stochastic Effects
17. LER / LWR
18. Prozessfenster / Parameter Sweeps
19. Sensitivity Analysis
20. perspektivisch High-NA / Vector Effects / 2D

Dabei muss jede Stufe separat validierbar sein.

Die Architektur soll deshalb eine echte physikalische Pipeline darstellen und nicht nur einen monolithischen "Simulator"-Aufruf.

============================================================
3. WICHTIGSTE STRATEGISCHE REGEL
============================================================

PHYSICS FIRST.

Keine neue Funktion gilt als "fertig", nur weil:
- sie läuft
- Tests grün sind
- plausible Bilder erzeugt werden
- Zahlen ungefähr realistisch aussehen

Eine physikalische Implementierung gilt erst als belastbar, wenn sie mindestens eine geeignete Form von Validierung besitzt:

A) analytische Referenzlösung
oder
B) Literaturvergleich
oder
C) Vergleich mit etablierter wissenschaftlicher Software
oder
D) Grenzfall-/Erhaltungsgesetz-Test
oder
E) unabhängige numerische Referenzimplementierung

Idealerweise mehrere davon.

============================================================
4. WISSENSCHAFTLICHE SOFTWARE-STRATEGIE
============================================================

EUVsimulator soll sich architektonisch eher an seriösen wissenschaftlichen Open-Source-Projekten orientieren als an klassischen "Feature-first"-Softwareprojekten.

Wichtige Prinzipien:
- modulare Physik
- klare mathematische Definitionen
- reproduzierbare Simulationen
- deterministische Tests
- Regression Tests
- Unit Tests für physikalische Einzelmodelle
- Integration Tests für die Pipeline
- bekannte Referenzfälle
- konservative numerische Verfahren
- explizite Einheiten
- dokumentierte Annahmen
- dokumentierte Gültigkeitsbereiche
- Fehlerbudgets
- Benchmark-Suite
- wissenschaftliche Literaturreferenzen
- reproduzierbare Beispielrechnungen

Ein Feature darf "nicht implementiert" sein.

Ein Feature darf NICHT als implementiert gelten, wenn seine Physik nicht ausreichend validiert wurde.

============================================================
5. AKTUELLER TECHNISCHER STAND
============================================================

Der aktuelle EUVsimulator besitzt bereits eine funktionierende Pipeline mit unter anderem:

- Maskengeometrie
- optischer Modellierung
- Multilayer
- Aerial Image
- Abbe/Hopkins-artiger TCC-Behandlung
- Resist
- Full-Chem-Pfad
- Stochastik
- CD
- NILS
- LER/LWR
- Pipeline/API/CLI

Der aktuelle Teststand liegt bei ca. 534 bestandenen Tests.

WICHTIG:
"534 Tests passed" bedeutet NICHT "Physik ist validiert".

Es wurde inzwischen erkannt, dass einige physikalisch falsche Implementierungen trotzdem Tests bestehen können.

Deshalb muss zukünftig zwischen:

1. Software Correctness
2. Numerical Correctness
3. Physical Correctness

unterschieden werden.

============================================================
6. BEREITS IDENTIFIZIERTE PHYSIKALISCHE PROBLEME
============================================================

A) BEHOBENER AERIAL-IMAGE-FEHLER

In aerial/abbe.py wurde ein künstlicher harter coherence cutoff entfernt.

Der alte Code blockierte Interferenz von Beugungsordnungen anhand:

dm > coherence_orders

Das war physikalisch falsch, weil die Hopkins-TCC-Funktion die Kohärenz bereits kontinuierlich beschreibt.

Der TCC-Term:

2 J1(x) / x

soll die Interferenz graduell dämpfen.

Dieser Fehler wurde behoben.

Die Referenztests wurden entsprechend angepasst.

============================================================

B) RCWA IST AKTUELL NICHT VERTRAUENSWÜRDIG
============================================================

Diagnostik hat gravierende Probleme im RCWA-Pfad gezeigt.

Insbesondere:

- TM Solver liefert falsche Reflektivitäten
- bei absorbierenden Materialien kann numerisches Explodieren auftreten
- Energieerhaltung kann verletzt werden
- uniforme TM-Schicht stimmt nicht mit analytischer Fresnel-Lösung überein
- TE/TM Behandlung ist nicht ausreichend validiert
- aktuelles Field-Averaging ist für unpolarisiertes Licht fragwürdig/falsch

Deshalb:

RCWA NICHT als wissenschaftlich validierte Kernfunktion betrachten.

Der Default-Pfad use_rcwa=False ist momentan eine sinnvolle Sicherheitsmaßnahme.

RCWA soll später systematisch neu validiert bzw. repariert werden.

Nicht versuchen, RCWA einfach durch kleine numerische Tweaks "plausibel" zu machen.

Zuerst:
- analytische Grenzfälle
- Fresnel
- Energieerhaltung
- homogene Schichten
- verlustbehaftete Materialien
- einfache Gitter
- Konvergenz
- Polarisation
- Flux-Normalisierung

============================================================
C) SIGMA=0 TCC EDGE CASE
============================================================

Aktuell führt sigma=0 zu Division durch Null.

Physikalisch muss gelten:

sigma -> 0
=> vollständig kohärente Beleuchtung
=> TCC -> 1

Dieser Edge Case muss sauber implementiert und getestet werden.

============================================================
D) STOCHASTISCHE SHOT-NOISE-IMPLEMENTIERUNG
============================================================

Ein besonders wichtiger Fehler wurde identifiziert.

Die aktuelle Stochastik zeigt:

LER steigt mit Dose ungefähr wie sqrt(Dose)

statt physikalisch erwartbar:

LER ~ 1/sqrt(N)
und damit näherungsweise
LER ~ 1/sqrt(Dose)

Die Ursache liegt sehr wahrscheinlich in der Reskalierung:

noisy_acid = acid * (noisy_count / lam)

in Kombination mit der Tatsache, dass acid und lam unterschiedlich interpretiert bzw. skaliert werden.
Dieser Bereich muss grundlegend überprüft werden.

Nicht einfach einen empirischen Faktor einsetzen.

Stattdessen:

Photonenstatistik
→ Poisson
→ Energie / Photon
→ Photonenzahl
→ Absorption / Quantum Efficiency
→ Acid Generation
→ räumliche Konzentration

mathematisch sauber definieren.

Danach LER/LWR-Dosis-Skalierung erneut validieren.

============================================================
7. WICHTIGE METHODISCHE LEHRE
============================================================

Ein besonders wichtiger Punkt aus den bisherigen Arbeiten:

Plausible Ergebnisse sind kein Beweis für korrekte Physik.

Beispiele:

- NILS ~8 kann plausibel aussehen und trotzdem aus falscher Interferenz entstehen.
- ein schöner Aerial-Image-Plot beweist keine korrekte Optik.
- ein grüner Test beweist keine physikalische Korrektheit.
- eine realistisch aussehende LER beweist keine korrekte Shot-Noise-Statistik.
- Energieerhaltung muss explizit geprüft werden.
- Grenzfälle müssen explizit geprüft werden.

Deshalb zukünftig immer:

PHYSIKALISCHE HYPOTHESE
→ mathematische Formulierung
→ Implementierung
→ analytischer Test
→ Grenzfall
→ numerische Konvergenz
→ Regression
→ erst dann Integration

============================================================
8. NEUE PRIORITÄTEN
============================================================

PRIORITÄT 0:
Wissenschaftliche Vertrauenswürdigkeit herstellen.

Dazu zuerst die bestehenden Kernmodelle überprüfen.

Nicht sofort neue Features hinzufügen.

PRIORITÄT 1:
Optik vollständig stabilisieren.

Insbesondere:

- Abbe
- Hopkins/TCC
- pupil
- diffraction orders
- normalization
- dose scaling
- polarization assumptions
- multilayer coupling

PRIORITÄT 2:
RCWA entweder korrekt reparieren oder klar als experimentell kennzeichnen.

RCWA darf erst als Produktionsmodell gelten, wenn:

- Fresnel-Test
- Energieerhaltung
- homogene Schicht
- absorbierende Schicht
- einfache periodische Struktur
- Polarisation
- Konvergenz mit steigender Ordnungszahl

bestanden sind.

PRIORITÄT 3:
Resist-Physik validieren.

Insbesondere:

- Photon absorption
- acid generation
- dose normalization
- diffusion
- chemistry
- development

Jedes Modell mit separaten Tests.

PRIORITÄT 4:
Stochastik neu aufbauen/validieren.

Insbesondere:

- Poisson statistics
- photon counting
- dose scaling
- voxel/grid-size scaling
- QE
- LER/LWR
- convergence vs number of realizations

PRIORITÄT 5:
Erst danach neue physikalische Features.

============================================================
9. ARCHITEKTURZIEL
============================================================

Die Software soll langfristig aus klar getrennten physikalischen Modulen bestehen.

Beispiel:

MASK
↓
MASK OPTICS
↓
MULTILAYER
↓
DIFFRACTION / RCWA
↓
PUPIL
↓
TCC / COHERENCE
↓
AERIAL IMAGE
↓
DOSE / ABSORPTION
↓
PHOTON STATISTICS
↓
ACID GENERATION
↓
DIFFUSION / PEB
↓
CHEMISTRY
↓
DEVELOPMENT
↓
RESIST PROFILE
↓
CD / NILS / LER / LWR

Jedes Modul muss einzeln nutzbar und testbar sein.

============================================================
10. REFERENZMODELLE
============================================================

Für jedes wichtige Modul soll nach Möglichkeit ein kleines, bewusst einfaches Referenzmodell existieren.

Beispiele:

Optik:
- analytische Fourier-Rechnung
- Fresnel
- ideale Thin Mask

TCC:
- analytische Bessel-TCC
- sigma=0
- sigma=1
- bekannte Grenzfälle

Multilayer:
- unabhängige Transfer-Matrix-Referenz
- Bragg-Bedingung
- Energieerhaltung

RCWA:
- Fresnel
- homogene Schicht
- einfacher sinusförmiger/binary grating Referenzfall

Stochastik:
- analytische Poisson-Momente
- Varianz ~ Mittelwert
- LER-Dosis-Skalierung

Resist:
- einfache analytische Threshold-/Development-Fälle

============================================================
11. VALIDIERUNGS-INFRASTRUKTUR
============================================================

Langfristig soll es eine eigene Physics Validation Suite geben.

Nicht nur pytest für Softwarelogik.

Zum Beispiel:

tests/
  unit/
  integration/
  physics/
  validation/
  regression/

Physics Tests sollen explizit dokumentieren:

- welches physikalische Gesetz getestet wird
- welche Gleichung gilt
- welche Parameter verwendet werden
- welcher Toleranzbereich erlaubt ist
- warum dieser Toleranzbereich erlaubt ist
- welche Literatur/Referenz verwendet wird

============================================================
12. BENCHMARK-DATENSÄTZE
============================================================

Es sollen feste Benchmark-Fälle aufgebaut werden.

Zum Beispiel:

BENCHMARK-OPTICS-001
Simple binary mask

BENCHMARK-ML-001
Mo/Si stack at 13.5 nm

BENCHMARK-TCC-001
Partially coherent line/space

BENCHMARK-RCWA-001
Homogeneous layer

BENCHMARK-RCWA-002
Simple absorbing grating

BENCHMARK-STOCH-001
Poisson scaling

BENCHMARK-RESIST-001
Simple CAR development

Diese Benchmarks sollen langfristig unverändert bleiben.

============================================================
13. SCIENTIFIC TRACEABILITY
============================================================

Jedes nichttriviale physikalisches Modell soll dokumentieren:

- Gleichung
- Variablen
- Einheiten
- Annahmen
- Gültigkeitsbereich
- numerische Methode
- Referenz
- Implementierungsort
- Validierungstest

Wenn eine Näherung verwendet wird:

NICHT verstecken.

Explizit dokumentieren:

"Dieses Modell ist eine Näherung und gilt unter folgenden Bedingungen..."

============================================================
14. WAS NICHT GEMACHT WERDEN SOLL
============================================================

Keine "magic numbers".

Keine Parameter nur so lange verändern, bis ein erwarteter Plot entsteht.

Keine Tests so anpassen, dass ein fehlerhaftes Modell grün wird.

Keine physikalischen Aussagen allein aufgrund von Plausibilität.

Keine neue Komplexität, bevor das Fundament validiert ist.

Keine KI-basierte Korrektur physikalischer Fehler ohne mathematische Begründung.

Keine Vermischung von numerischer Stabilisierung und physikalischer Modelländerung.

============================================================
15. ROLLE VON KI / HERMES / NEMO
============================================================

KI darf beim Projekt massiv unterstützen.

Aber:

KI ist NICHT die physikalische Referenz.

Jede KI-generierte physikalische Änderung muss durch:

- Gleichung
- Referenz
- analytischen Test
- Grenzfall
- Regression

begründet werden.

Besonders bei RCWA, TCC, Maxwell, Resistchemie und Stochastik darf kein Modell nur deshalb übernommen werden, weil es "wissenschaftlich klingt".

Wenn Unsicherheit besteht:

STOPPEN.
Unsicherheit dokumentieren.
Referenz suchen.
Test bauen.
Dann implementieren.

============================================================
16. ENTWICKLUNGSSTRATEGIE
============================================================

Die weitere Entwicklung soll in folgenden Ebenen erfolgen:

LEVEL 0:
Bestehenden Code verstehen und inventarisieren.

LEVEL 1:
Physikalische Kernmodelle validieren.

LEVEL 2:
Fehlerhafte Kernmodelle reparieren.

LEVEL 3:
Referenztests und Benchmark Suite etablieren.

LEVEL 4:
Pipeline physikalisch konsistent machen.

LEVEL 5:
Stochastik und Resistmodellierung wissenschaftlich stabilisieren.

LEVEL 6:
RCWA produktionsreif machen.

LEVEL 7:
2D / vectorial / high-NA erweitern.

LEVEL 8:
Performance, API, Dokumentation und Usability optimieren.

LEVEL 9:
Publizierbare wissenschaftliche Beispiele und reproduzierbare Benchmarks.

============================================================
17. DEFINITION OF DONE
============================================================

Ein physikalisches Modul ist erst "fertig", wenn:

[ ] mathematisches Modell dokumentiert
[ ] Einheiten geprüft
[ ] Grenzfälle getestet
[ ] analytischer Vergleich vorhanden, sofern möglich
[ ] numerische Konvergenz geprüft
[ ] Energie-/Erhaltungsgesetze geprüft, sofern relevant
[ ] Regressionstest vorhanden
[ ] Parameterbereich dokumentiert
[ ] bekannte Limitationen dokumentiert
[ ] unabhängige Plausibilitätsprüfung durchgeführt

============================================================
18. AKTUELLER NÄCHSTER SCHRITT
============================================================

NICHT sofort die gesamte Roadmap weiterbauen.

Zuerst:

1. sigma=0 TCC sauber reparieren
2. Stochastic photon/acid scaling mathematisch vollständig auditieren
3. Stochastik-Dosis-Skalierung korrigieren
4. neue physikalische Regressionstests hinzufügen
5. danach Optik nochmals systematisch validieren
6. RCWA separat isolieren und reparieren
7. erst danach nächste Pipeline-Stufe erweitern

Dabei immer Änderungen einzeln durchführen und nach jeder Änderung die komplette Test-Suite laufen lassen.

============================================================
19. STRATEGISCHE LEITIDEE
============================================================

EUVsimulator soll nicht dadurch groß werden, dass es möglichst viele Modelle enthält.

Es soll dadurch groß werden, dass man den Ergebnissen vertrauen kann.

Langfristiges Qualitätsziel:

"Wenn EUVsimulator ein physikalisches Modell anbietet, muss der Benutzer wissen können:
Was wird berechnet?
Mit welcher Gleichung?
Unter welchen Annahmen?
Wie wurde es validiert?
Wo liegen die Grenzen?"

Das ist wichtiger als maximale Feature-Anzahl.

============================================================
20. KERNPRINZIP FÜR ALLE ZUKÜNFTIGEN ENTSCHEIDUNGEN
============================================================

Bei jeder Änderung zuerst fragen:

1. Welches physikalische Problem lösen wir?
2. Welche Gleichung beschreibt es?
3. Welche Annahmen machen wir?
4. Welche unabhängige Referenz haben wir?
5. Wie testen wir den Grenzfall?
6. Wie testen wir numerische Stabilität?
7. Wie verhindern wir Regressionen?
8. Wo ist das Modell gültig?
9. Was ist noch unbekannt?

Erst danach:

CODE.

============================================================
ENDE MASTERKONTEXT
============================================================
