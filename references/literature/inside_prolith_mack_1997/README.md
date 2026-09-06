# Inside PROLITH (Chris A. Mack, 1997) — vollständiges Lehrbuch

Lokal archiviert für die Recherche zu den Mack-Entwicklungsmodell-Parametern
(`mack_R_max`, `mack_R_min`, `mack_n`, `mack_M_th` in `SimulationConfig`,
`src/euvsimulator/pipeline.py`) im Rahmen des autonomen Arbeitszyklus,
Aufgabe 1 (siehe `docs/claude_code_arbeitslog.md`).

| Feld | Wert |
|---|---|
| Citation | Mack, C. A. "Inside PROLITH: A Comprehensive Guide to Optical Lithography Simulation." FINLE Technologies, Inc., Austin, TX (1997) |
| Quelle/URL | https://lithoguru.com/scientist/litho_papers/Inside_PROLITH.pdf (frei vom Autor selbst gehostet, kein Bezahlzugang nötig) |
| Heruntergeladen am | 2026-09-02 |
| Umfang | 179 Seiten, vollständiges Buch |
| Datei | `Inside_PROLITH_Mack_1997.pdf` |

## Warum relevant

Kapitel 7 ("Photoresist Development"), Fig. 7-1 und 7-2, zeigt das Original- bzw.
Enhanced-Mack-Entwicklungsmodell mit den illustrativen Beispielwerten
`rmax=100 nm/s, rmin=0.1 nm/s, mTH=0.5, n=2/4/8/16` (Fig. 7-1) bzw.
`rmax=100, rresin=10, rmin=0.1, n=5` (Fig. 7-2b). Diese Werte stimmen exakt
(R_max, R_min, M_th) bzw. nahezu (n) mit den aktuellen `SimulationConfig`-Defaults
in euvsimulator überein — das ist mit hoher Wahrscheinlichkeit ihr Ursprung.

**Wichtig:** Es handelt sich hier um eine generische Lehrbuch-Illustration des
Autors, um die *Form* des Modells zu zeigen — **nicht** um einen an einen
gemessenen (schon gar nicht EUV-spezifischen) Resist gefitteten Wert. Die
Defaults sind damit nachvollziehbar herkunftsbelegt, aber weiterhin **nicht**
wissenschaftlich als EUV-CAR-repräsentativ validiert. Details und offene
Punkte: siehe Kommentar bei `mack_R_max` etc. in `pipeline.py` sowie
`docs/claude_code_arbeitslog.md`.

**Note (2026-09-06):** the PDF itself is no longer part of this repository. Chris Mack offers
*Inside PROLITH* (1997) as a free download on his own site, lithoguru.com; the copyright stays
with the author, and redistributing the file here was not covered by any licence. Cite the
book, download it from the author.
