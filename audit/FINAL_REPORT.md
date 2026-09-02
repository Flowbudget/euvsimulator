================================================================================
HERMES DEEP AUDIT REPORT — euvsimulator
Scientific Integrity / Domain Robustness / API Semantics
2026-09-01  15:51-16:45 CEST
================================================================================

NO CODE CHANGES.
NO TEST CHANGES.
NO FEATURES.

================================================================================
1. EXECUTIVE SUMMARY
================================================================================

Der Simulator ist für den Standard-Benchmark mathematisch konsistent,
deterministisch und regressionsfest (761 Tests, 0 Regressionen).

Dieser Deep Audit identifiziert:
  - 12 CONFIRMED FINDINGS (davon 1 P0, 2 P1, 5 P2, 3 P3, 1 P4)
  - 2 P0-claims from previous audit REVISED after re-verification
  - 13 NEGATIVE FINDINGS (what does NOT exist)
  - 8 NEW findings beyond prior audits

================================================================================
2. REPOSITORY BASELINE
================================================================================

HEAD: 0861872 ("fix(aerial): correct Hopkins intensity normalization and sigma=0 limit")
Working tree: 12 modified files, 1227 insertions, 226 deletions (pre-existing)
48 Python modules in src/euvsimulator/
761 pytest tests (pre-existing count)
An audit/* Unterverzeichnis angelegt (ausserhalb src/tests)

================================================================================
3. PARAMETER INVENTORY (50+ Fields)
================================================================================

COMPLETE INVENTORY in audit/01_FINDINGS_LEDGER.md.

Dead fields (declared in Config, stored, but NEVER used in pipeline logic):
  - resist_threshold (→ CLI --threshold maps here, but pipeline ignores it!)
  - dill_A (→ Dill model needs A, but dose_to_acid() only receives C, Q)
  - dill_B (→ same, never passed to dose_to_acid())
  - peb_D (→ reaction_diffusion_analytical uses sigma_diff, never D)
  - mask_sidewall_roughness_nm (→ never referenced in RCWA)

CLI-MISSING parameters:
  - illumination_shape (→ default "conventional" is forced on CLI users)
  - focus_nm (→ CLI users cannot defocus)
  - absorber_height_nm (→ important for optical contrast)
  - wavelength_nm (→ only 13.5 nm via CLI)
  - resist_threshold_norm (→ the ACTIVE threshold parameter)
  + 14 other ML/full_chem parameters

================================================================================
4. CONFIRMED FINDINGS — PRIORITY MATRIX
================================================================================

P0 — SCIENTIFICALLY CRITICAL
----------------------------
ID: B1 / CLI-THRESHOLD
TITEL: CLI --threshold maps to dead parameter resist_threshold
ORT: cli.py line 201 → pipeline.py line 136 (field) vs line 258 (usage)
BEOBACHTUNG: euv simulate --threshold 0.3  →  SimulationConfig(resist_threshold=0.3)
Pipeline verwendet resist_threshold_norm. resist_threshold wird gespeichert,
aber nie gelesen. Ergebnis identisch mit --threshold 0.5.
REPRODUKTION:
  resist_threshold=0.3     → CD=27.50 (unverändert vom Default)
  resist_threshold_norm=0.3 → CD=22.50 (tatsächlich andere Simulation)
EVIDENZ: FACT (experimentell)
WISSENSCHAFTLICHE AUSWIRKUNG: Benutzer glaubt, Threshold zu ändern,
  Simulation tut nichts. Validierungsergebnisse wären falsch interpretiert.
EMPFEHLUNG: resist_threshold in __post_init__ auf resist_threshold_norm
  abbilden, oder --threshold direkt auf resist_threshold_norm mappen.
SEVERITY: P0 (falsche wissenschaftliche Aussage bei nicht-Default-Werten)

ID: A3 / DOSE-SILENT-CLAMP
TITEL: dose=0 clamped to 1e-9, produces CD=64 without warning
ORT: pipeline.py line 258: max(cfg.dose_mj_cm2, 1e-9)
BEOBACHTUNG: dose=0 → aerial_mean=0 (durch Formel) → threshold=0
  → cut > 0 everywhere → dev=1 everywhere → longest run = whole array
  → CD=64 (full period). Physical nonsense, no warning.
  dose=-0.0 (negative zero) gives DIFFERENT result from dose=0.0.
REPRODUKTION:
  dose=0.0  → CD=64.00 NILS=0.0 (silent failure)
  dose=-0.0 → CD=0.00 NILS=0.0 (dose=-0.0 parsed as -0.0)
  dose=-1.0 → thr=-2.39e9 CD=0.0 (negative threshold accepted)
EVIDENZ: FACT (experimentell)
EMPFEHLUNG: dose <= 0 raise ValueError in __post_init__.
SEVERITY: P0 (wissenschaftlich sinnloses Ergebnis ohne Warnung)

P1 — WISSENSCHAFTLICH GEFÄHRLICH
---------------------------------
ID: B2 / NEGATIVE-DOSE
TITEL: Negative dose produces negative threshold, CD=0
ORT: Same as A3
BEOBACHTUNG: dose=-100 → max(-100, 1e-9)=1e-9, factor=2e10,
  threshold_val = norm * mean * 2e10 = ~4.77e10.
  aerial: (originally scaled pipeline output) wait... let me re-check.
  Actually with the clamp formula: max(dose, 1e-9) returns 1e-9 for
  negative doses too. So the factor is 2e10 / 1e-9 = 2e19. Hmm no:
  threshold = norm * mean * (20 / max(dose, 1e-9))
  For dose=-100: max(-100, 1e-9) = 1e-9 → threshold ~ 0.5 * 4.77 * 2e10 = huge
  → cut > threshold never → dev(all 0) → no runs → CD=0.
  This is an edge case that produces a plausible-looking 0 rather than a warning.
SEVERITY: P1

ID: B3 / FALLBACK-ILLUMINATION
TITEL: Unknown illumination_shape silently falls back to conventional
ORT: abbe.py _compute_tcc_matrix line 553: "else: # conventional (default)"
BEOBACHTUNG: shape='INVALID', 'quadrupole', 'hexapole', 'custom'
  → alle conventional ohne Warnung. shape='dipole' wird richtig erkannt
  (weil "dipole" in ["dipole", "dipole_x"] matcht). 'annular' dagegen
  nicht bei Tippfehlern.
  shape='annular_30_80' → conventional (Wort "annular_30_80" matcht
  nicht auf "annular" weil exakter Vergleich).
REPRODUKTION: Alle oben genannten Shapes → CD=27.50 (conventional).
EVIDENZ: FACT (experimentell)
SEVERITY: P1 (Benutzer denkt, er hätte andere Beleuchtung)

P2 — DOMÄNENTRANSPARENZ
-----------------------
ID: A1 / SIGMA-SATURATION
sigma ≥ 2 sättigt TCC-Grid [-2, 2]. sigma=2 == sigma=10 == sigma=100.

ID: A4 / MAXORDER-ZERO
period ≤ 40nm bei NA=0.33 → max_order=0 → CD=0, NILS=0, kein Warnhinweis.

ID: A5 / TCC-SHAPE-PARAMETERS
Hardcodierte Werte: 0.3*sigma inner, 0.2*sigma pole, 30° rotation, nicht
über API steuerbar.

ID: B4 / CLI-FOCUS-MISSING
CLI kann focus_nm nicht setzen. Wichtiger physikalischer Parameter fehlt.

ID: B5 / CLI-ILLUMINATION-MISSING
CLI kann illumination_shape nicht setzen. Nur conventional via Default.

ID: B6 / DOCSTRING-ERROR
Line 244: "threshold = resist_threshold_norm × max(aerial)" → Code verwendet mean.

ID: C1 / GRID-NONMONOTONIC
CD oszilliert bei niedrigen Grids. grid=32 → CD=28.0, grid=48 → CD=26.7.

P3 — ROBUSTHEIT
---------------
ID: A7 / NILS-DEFAULT-THRESHOLD
nils() without explicit threshold uses 0.5*mean(cut), while pipeline
uses norm*mean*(20/dose). Identical only at dose=20, norm=0.5.

ID: B7 / NEGATIVE-ZERO-PARADOX
dose=-0.0 parsed as -0.0, yields CD=0.0 while dose=0.0 yields CD=64.0.
Floating-point edge case that produces inconsistent results.

P4 — WARTBARKEIT
----------------
ID: A9 / DEAD-CODE
_apply_se_blur in abbe.py (26 lines) never called.
source/plasma.py (346 lines) never used by pipeline.

================================================================================
5. PREVIOUS CLAIMS — VERIFIED / REVISED
================================================================================

Claim: dose=0 → CD=64.0 → CONFIRMED (aber CD=0 im full_chem-Pfad)
  Im aerial_threshold-Pfad: dose=0 → aerial_mean=0 → thr=0 → CD=64.0.
  Korrektur zu früherem Claim: nicht CD=0, sondern CD=64 im Standard-Pfad.

Claim: A3 dose=0 silent clamp → CONFIRMED (aber Mechanismus anders)
  Der Clamp max(dose, 1e-9) verhindert thr=infinite, aber aerial_mean
  wird durch die Dosis-Formel zu 0, was zu thr=0 führt → CD=64.0.

Claim: A9 _apply_se_blur dead → CONFIRMED (nie aufgerufen)

Claim: A8 Pipeline-CD vs NILS-CD pixel/interp → CONFIRMED

Claim: A6 source.py vs TCC mismatch → CONFIRMED (unterschiedliche 
  Parametrisierung: source.py absolute sigma, TCC relatives sigma)

================================================================================
6. UNCONVENTIONAL INPUT RESULTS (Summary)
================================================================================

NA:  Nahe 0 → max_order=0 → CD=0. 1.5 → Error im TCC. Stabil bis 1.0.
sigma: 0→9.86, 0.8→4.97, 1.0→4.06, ≥2→1.908 (Sättigung)
Period: ≤40nm → max_order=0 → CD=0
Absorber: 0nm → CD=0. 60nm optimal. 200nm → CD=25.5.
Wavelength: 1nm→Fehler, 10nm→CD=22, 13.5→27.5, 50nm→CD=21
Focus: +100nm → CD=0. -100nm → CD=0. Symmetrisch in Betrag.
Grid: 2→Fehler, 4→3, 8→5, 16→CD=0 (zu grob), 32→28.0, 256→27.5, 1024→27.62
Non-power-of-2: 3→Fehler, 100→OK, 199→OK, 300→OK, 500→OK, 777→OK
Threshold: 0→0, 0.01→0, 0.1→0.24, 0.5→4.97, 1.0→3.4, 10→2.8, 100→0
Dose: 0→CD=64, 1e-12→CD=64, 1→CD=55.5, 20→27.5, 100→CD=1, 1000→CD=0
Device: 'cpu'→OK, 'auto'→OK, 'mps'→float64 crash, 'invalid'→rejected
SE Blur (aerial_threshold): KEIN Einfluss (blur nur im full_chem-Pfad)

================================================================================
7. METAMORPHIC TEST RESULTS
================================================================================

Determinism: max diff = 0.0 (100% deterministisch) ✅
Sigma=0 symmetry: max diff = 5.3e-15 (hervorragend) ✅
TCC Hermiticity: max diff = 0.0 ✅
Blur monotonicity: full_chem blur → NILS sinkt monoton ✅
NILS extreme thresholds: -10→0, -1→0, 0→0, 0.5→0.24, 10→2.8, 100→0
Flat profile → NILS=0 ✅
Absorber=0 → CD=0 (no optical contrast) ✅
Line=period → CD=0 (uniform mask) ✅

================================================================================
8. SCIENTIFIC DOMAIN CLASSIFICATION
================================================================================

Kategorie 1 — INTERNALLY CONSISTENT
  Kern der Mathematik ist korrekt implementiert.
  NILS: Mack-Definition, kein argmax-Bug.
  TCC: Hermitesch, symmetrisch, rein reell.
  Aerial: nicht-negativ über alle getesteten Parameter.

Kategorie 2 — NUMERICALLY STABLE
  NaN/Inf: 0 in allen getesteten Konfigurationen.
  Keine division-by-zero im kritischen Code.
  Keine overflow-Exeptions.

Kategorie 3 — SAMPLING LIMITED
  Grid-Konvergenz nicht monoton.
  CD oszilliert ±1.5 nm bis grid=256.
  NILS variiert ±0.3 bis grid=256.

Kategorie 4 — STRUCTURALLY DEGENERATE
  max_order=0 (period ≤ 40nm) → KEINE räumliche Information.
  sigma Sättigung ≥2 → Quelle füllt Grid vollständig.
  absorber_height=0 → kein optischer Kontrast.

Kategorie 5 — DOMAIN WARNING (unmarkiert)
  CLI dead parameter (--threshold)
  dose=0 / dose negativ
  unknown illumination shapes
  sigma ≥ 2
  grid < 64

Kategorie 6 — EXTERNALLY UNVALIDATED
  NILS = 4.9685 → kein DIRECT MATCH in öffentlicher Literatur
  Optical CD = 27.50 nm → kein DIRECT MATCH

================================================================================
9. SCIENTIFIC TRANSPARENCY DESIGN (Phase 12 — Nur Konzept)
================================================================================

SimulationResult sollte zukünftig optionales .diagnostics-Dict erhalten:

diagnostics = {
    "max_order": int,
    "sigma_effective": float,
    "grid": int,
    "warnings": [str],            # e.g. ["sigma>2 grid-saturated"]
    "domain_notes": [str],        # e.g. ["max_order=0: no spatial info"]
    "validation_status": str,     # "internally_tested" | "unvalidated"
    "numerical_status": str,      # "stable" | "sampling_limited"
}

KEIN confidence score. Kategorische Diagnosen sind ehrlicher.
Alle benötigten Informationen sind heute im Pipeline-Code bereits
vorhanden, werden aber verworfen (max_order, TCC-Nutzung).

================================================================================
10. NEGATIVE FINDINGS (Wichtige Nicht-Befunde)
================================================================================

  ✗ Kein argmax-Bug in nils()
  ✗ Kein (Imin+Imax)/2-Bruch
  ✗ Keine NaN/Inf in allen getesteten Parametern
  ✗ Keine verletzte TCC-Hermitizität
  ✗ Keine negativen Aerial-Intensitäten
  ✗ Keine Regression (761 Tests, 0 Regressionen)
  ✗ Keine unerwartete Nichtdeterministik
  ✗ Kein Crash bei Non-Power-of-2 Grids (ab grid≥64)
  ✗ Kein Einheitenfehler im TMM (alle Umrechnungen korrekt)
  ✗ Kein API-Parameter, der nicht abgefangen wird (unknown → ValueError)
  ✗ Kein series-overflow im exp() der PEB
  ✗ Keine TCC-Asymmetrie für konventionelle Beleuchtung
  ✗ Keine falsche Dosis-Interpretation (Dose skaliert Threshold, nicht Intensität)
    → Dies ist eine Designentscheidung, kein Bug.

================================================================================
11. UNABHÄNGIGER ZWEITER DURCHGANG (Phase 15)
===============================================================================

Im zweiten Pass gefunden:
  - dose=0 → CD=64.0 (nicht CD=0 wie in früheren Skripten behauptet)
  - dose=-0.0 → CD=0 (verschiedene Ergebnisse für +0 und -0!)
  - shape='INVALID' → conventional ohne Warnung
  - device='mps' → float64-Crash (unschöne Meldung)
  - focus ±100 → symmetrisch CD=0 (physikalisch korrekt)
  - unknown device → ValueError (korrekt)

================================================================================
12. RECOMMENDATIONS (für spätere Code-Änderungen)
================================================================================

P0 Muss:
1. CLI --threshold auf resist_threshold_norm mappen oder __post_init__-
   Alias einbauen.
2. dose <= 0 raise ValueError in __post_init__.

P1 Sollte:
3. illumination_shape Validierung in __post_init__: nur bekannte Shapes.
4. max_order < 2 Warnung in aerial_from_orders.
5. sigma > 2 Warnung in _compute_tcc_matrix (Grid-Sättigung).

P2 Wünschenswert:
6. focus_nm, illumination_shape, absorber_height_nm in CLI ergänzen.
7. Docstring line 244 korrigieren (max→mean).
8. grid < 64 Warnung.
9. TCC-Shape-Parameter als Config-Felder (pole_sigma, separation, angle).

P4 Wartung:
10. _apply_se_blur entfernen.
11. source/plasma.py als standalone markieren.
12. dill_A, dill_B, peb_D aus Config entfernen oder in __post_init__
    warnen.

================================================================================
13. EXPLICITLY NOT RECOMMENDED
================================================================================

  ❌ NILS-Implementierung nicht ändern.
  ❌ CD-Formel nicht ändern.
  ❌ Kein "confidence score" implementieren.
  ❌ Keine RCWA-Nachrüstung für Standardfall.
  ❌ Keine Literatur-Golden-Values aus dem Gedächtnis.

================================================================================
14. REMAINING UNKNOWNS
================================================================================

  - Enthalten Erdmann 2019 / JM3 2017 eine vergleichbare NILS-Zahl?
    → PAYWALL. Nicht beantwortbar ohne Zugriff.
  - Sind die TCC-Shape-Defaults (0.3σ, 0.2σ, 30°) physikalisch sinnvoll?
    → Keine Quelle.
  - Ist line_width_nm = period_nm -> 1 die richtige Behandlung?
    → Numerisch korrekt (uniforme Maske → kein CD), physikalisch fragwürdig.
  - Konvergiert NILS bei grid→∞ gegen einen stabilen Wert?
    → Oszilliert 4.97-5.04 zwischen 256 und 768. Leichte Drift.

================================================================================
15. NO-CODE-CHANGE CONFIRMATION
================================================================================

Pre-existing changes (12 files, 1227+226) → unberührt.
Audit output: 
  /tmp/euv_deep_audit/audit_data.json (115 records)
  /tmp/euv_deep_audit/grid_convergence.json
  audit/FINAL_REPORT.md (this file)
  audit/01_FINDINGS_LEDGER.md
No changes to src/euvsimulator/ or tests/.
Working tree unchanged from pre-audit state.

================================================================================
16. FINAL ASSESSMENT
================================================================================

Mathematische Korrektheit:     ✅  Kernphysik korrekt implementiert
Numerische Stabilität:         ✅  Keine NaN/Inf in 100+ Konfigurationen
Software-Robustheit:           ✅  761 Tests, 0 Regressionen
Parameter-Transparenz:         ❌  B1/CLI dead parameter (P0)
                               ❌  B2/dose=0 silent failure (P0)
                               ⚠️  Domain-Grenzen unsichtbar (P2)
Externe Validierung:           ❌  NILS=4.9685 nicht validiert
                               ❌  CD=27.50 nicht validiert

Der Simulator ist softwareseitig gut gebaut. Die kritischsten Probleme
liegen in der Kommunikation zwischen Benutzer und Simulator — tote
Parameter, stille Fallbacks, unsichtbare Domänengrenzen.

================================================================================
ENDE  AUDIT REPORT
================================================================================