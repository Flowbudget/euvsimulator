# Explorative Parameterkampagne, 2026-09-07

Vier Rechenkampagnen über die belegten Teile der Kette (Grid 64, Default-Resist, 1:1 Linien),
danach eine Mustersuche ohne Schlagwörter: Potenzgesetze, Invarianten, dimensionslose Gruppen,
Residuen. Skripte `run.py` (Rechnung, 32 min auf dem M1) und `analyse.py` (Auswertung), Rohdaten
`c1.csv` bis `c4.csv`. Ziel war, Zusammenhänge zu finden, die in den Modulen nicht explizit stehen.

| Kampagne | Variation | Zeilen |
|---|---|---|
| C1 Optik × Resist | Pitch 32/44/64/90, NA 0,33/0,55, σ 0,5/0,8, konventionell/annular; Dose-to-Size per Bisektion, NILS, dCD/dlnE | 32 |
| C2 PEB-Kinetik | T 80–140 °C (Yamamoto-Tabelle), Backzeit 30/60/120 s, D 2/4,2/8 nm²/s, beide Verlustgesetze; 64/32 nm | 90 |
| C3 Entwicklung | 80 Zufallssätze: Mack n 4–30, R_max 15–250 nm/s, R_min, M_th 0,25–0,6, t_dev 8–120 s, Dicke 30/50/80 nm | 80 |
| C4 Stochastik | PEB-Blur 4/8/12, SE-Blur 1,5/2,5/4, Zelle aus/2/4,3 nm, Dosis 1,0/1,5 × D2S; 512 Zeilen, 2 Seeds | 54 |

## Befunde (alle bekannt, hier quantifiziert für diese Kette)

1. **Kantendosis-Invarianz.** Lokale Dosis an der gedruckten Kante (D2S · I_mean/I_clear) = 0,518 mJ/cm²
   ± 7,6 % über alle 32 Optiken; Korrelation mit NILS −0,09, mit k1 −0,11. Leichter Trend 0,54 (NA 0,33,
   σ 0,5) → 0,50 (NA 0,55). Schwellwert-Resist-Verhalten; die Kante liegt bei symmetrischen 1:1-Bildern
   geometrisch am Bildmittelwert, Blur ändert das nicht.
2. **Deprotektion an der Kante hängt nur von k·t_eff ab.** Analytisches Gesetz: −ln M_Kante = k·t_eff·H_Kante
   = 0,618 ± 0,006 für T ≥ 110 °C; steigt auf 0,69 bei 80 °C, wenn der Blur (bis 30 nm) gegen den Pitch
   geht (Korrelation mit Blur −0,88). D2S ∝ (k·t_eff)^−1,06 (Residuum 5 %).
3. **Lumped-Parameter-Modell wiedergefunden.** Die Kante druckt dort, wo die Mack-Rate gleich Dicke/t_dev
   ist: M_Kante/M* = 1,083 ± 0,076 über 76 Zufallsresists (corr ln 0,96). Die +8 % sind die laterale
   Entwicklung der Eikonal-Front. Geschlossene Näherung: D2S ≈ −ln(1 − (−ln(1,08·M*))/(k·t_eff)) /
   (C · I_Kante), M* aus R_Mack(M*) = Dicke/t_dev. **Kein Ersatz für die 3D-Kette** (8 % Streuung), aber
   als Startwert für `euv calibrate` ~1000× schneller als die Bisektion. Vier von 80 Sätzen drucken nie
   (R_min zu hoch).
4. **Verlustgesetze unterscheiden sich rein kinetisch.** D2S(analytisch)/D2S(reaction_diffusion) wächst
   von 0,97 (80 °C, 30 s) auf 2,69 (140 °C, 120 s) und ist unabhängig von D (1,85–1,90 ± 0,6).
5. **Korrelationslänge der Kantenrauheit = 1,55 × Gesamtblur** (√(σ_PEB² + σ_SE²)), Streuung 7 %;
   Theorie für gaußgefiltertes weißes Rauschen √π = 1,77. n_eff·l_int = 0,52 · Zeilen·dx (Definition).
6. **Stochastischer CD-Bias.** Rauschen macht Linien fetter: +0,7 bis +14,6 nm (Mittel +4) gegenüber
   der deterministischen CD, am stärksten bei 2-nm-Zellen und 12 nm Blur. Photonen-LER ∝ Dosis^−1,76
   zwischen 1,0 und 1,5 × D2S (statt −0,5), weil bei D2S die Entwicklung an der Kante marginal ist.
   Zellrausch-Exzess LER² − LER²_Photon fällt von 10 (1,0×) auf 2,3 nm² (1,5×) und wächst mit dem Blur.

## Aufgelöst: der Faktor 2 in der Dosisempfindlichkeit

Ein Schwellwertmodell gibt dCD/dlnE = 2/ILS. Die Kette liefert bei 64 nm Pitch −28 nm (NA 0,33) und
−25 nm (NA 0,55) gegenüber 12,8 bzw. 6,9 nm aus dem Luftbild. Die erste Erklärung (Gauß-Dämpfung nur der
ersten Harmonischen, Restfaktor 2,2) war falsch gerechnet: direkt am geblurrten Luftbild gemessen
(σ = 8,3 nm, FFT) ist 2/ILS = 22,7 (NA 0,33) und 19,8 (NA 0,55), weil der Blur die höheren Harmonischen
des schärferen NA-0,55-Bildes stärker dämpft. Das erklärt auch die scheinbare NA-Abhängigkeit. Übrig
bleibt 1,20–1,29, gitterstabil (Grid 64/128/256) und schrittweitenunabhängig (±5 %/±2 %):

| Entwicklung | t_dev | Mack n | Restfaktor |
|---|---|---|---|
| eikonal (lateral) | 30 s | 18,2 | 1,24 |
| column (nur vertikal) | 30 s | 18,2 | 1,10 |
| eikonal | 10 s | 18,2 | 1,08 |
| eikonal | 90 s | 18,2 | 3,00 |
| eikonal | 30 s | 5,0 | 2,07 |
| eikonal | 30 s | 30,0 | 1,19 |
| column | 30 s | 5,0 | 1,10 |

Der Rest ist die laterale Entwicklung (Eikonal-Front) und der Mack-Kontrast: lange Entwicklung oder
niedriges n vergrößern die Dosisempfindlichkeit, das Säulenmodell ohne laterale Entwicklung nicht. Kein
Fehler, keine neue Physik; das Lumped-Parameter-Modell sagt dasselbe qualitativ. Nebenbefund: eikonal
gegen column verschiebt die Dose-to-Size um 37 % (1,30 gegen 1,78 mJ/cm²).

## Offen
- Bei 80 °C, 120 s, D = 8 (Blur 30 nm bei 64 nm Pitch) ist CD(Dosis) nicht monoton, die Bisektion trifft
  32 nm nicht (28,9). Ungeprüft.
