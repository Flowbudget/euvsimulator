# PHASE 1-2: Repository Inventory + Parameter Domain Audit
## Findings Ledger (growing)

### B1: CLI `--threshold` maps to dead parameter
CATEGORY: API / USER EXPECTATION
SEVERITY: P1 (silently ignored parameter) / P2 (user impact: only wrong for non-default vals)
LOCATION: `cli.py` line 201 vs `pipeline.py` lines 136/138
INPUT: euv simulate --threshold 0.3
OBSERVATION: CLI `--threshold` maps to `SimulationConfig.resist_threshold` (line 201).
Pipeline uses `SimulationConfig.resist_threshold_norm` (lines 258, 317).
`resist_threshold` (without `_norm`) is declared as Config field (line 136) but 
NEVER referenced in any pipeline function. It is a dead parameter.
EXPECTED: `--threshold 0.3` changes the CD/NILS threshold.
ACTUAL: No effect — `resist_threshold_norm` remains 0.5, unchanged.
EVIDENCE: grep confirmed `resist_threshold` (no _norm) appears 2 times in pipeline.py:
  line 108 (docstring) and line 136 (field declaration). Zero usage in logic.
  `resist_threshold_norm` appears 5 times, all active.
REPRODUCIBLE: Yes (simple)
SCIENTIFIC_IMPACT: User thinks they changed threshold but didn't
USER_IMPACT: User sees unchanged CD despite passing --threshold
STATUS: CONFIRMED
RECOMMENDATION: Either (a) remove `resist_threshold` and rename field, or 
  (b) make CLI map `--threshold` to `resist_threshold_norm`, or 
  (c) alias in `__post_init__`: `resist_threshold_norm = resist_threshold` 
  when the latter is set explicitly.

### B2: CLI missing `illumination_shape`
CATEGORY: API / DOMAIN
SEVERITY: P4
LOCATION: `cli.py` `simulate()` function
OBSERVATION: `illumination_shape` parameter is not exposed in CLI. Users can
only use the default "conventional" from the command line.
EVIDENCE: `cli.py simulate()` function parameters inspected — no illumination_shape.
REPRODUCIBLE: Yes
STATUS: CONFIRMED
RECOMMENDATION: Add `--illumination-shape` CLI option.

### B3: `resist_threshold_norm` docstring vs implementation mismatch
CATEGORY: DOCUMENTATION / SEMANTICS
SEVERITY: P3
LOCATION: `pipeline.py` line 244
OBSERVATION: Docstring says "The threshold is resist_threshold_norm × max(aerial)"
Actual code (line 258): `resist_threshold_norm * dc_level * (nominal_dose / max(dose, 1e-9))`
where `dc_level = mean(aerial)`, not `max(aerial)`.
Additionally multiplies by dose scaling factor (20/dose) not mentioned.
EVIDENCE: Lines 244 (doc) vs 255-258 (code)
STATUS: CONFIRMED
RECOMMENDATION: Correct docstring to match implementation.

### B4: `source/plasma.py` is standalone (not used by pipeline)
CATEGORY: ARCHITECTURE
SEVERITY: P4
LOCATION: `source/plasma.py`
OBSERVATION: LPP Sn-plasma source model is a 346-line module that is never 
imported or used by `run_simulation` or any pipeline function. It's purely 
standalone/optional.
EVIDENCE: `grep -r "source.plasma\|LPPPlasmaSource" src/euvsimulator/*.py` 
confirms no pipeline imports.
STATUS: CONFIRMED
RECOMMENDATION: Document as standalone utility.

### B5: `chunked_rcwa()` is a placeholder
CATEGORY: SOFTWARE INTEGRITY
SEVERITY: P4
LOCATION: `accel/chunked.py` lines 98-126
OBSERVATION: Returns input profile unchanged with comment "placeholder.
Full chunked RCWA to be implemented in a future release."
No warning logged. No caller in production pipeline currently uses this.
STATUS: CONFIRMED
RECOMMENDATION: Log a warning if called.

### B6: `pw_metrics()` uses dummy fallback spacings
CATEGORY: NUMERICAL / API
SEVERITY: P3
LOCATION: `metro/process_window.py` lines 263-264, 287-288
OBSERVATION: `pw_metrics()` hardcodes `focus_spacing = 1.0` and uses index-based
DoF/EL computation as fallback. If called directly (without proper focus/dose 
arrays), results are meaningless.
STATUS: CONFIRMED
RECOMMENDATION: Require actual arrays or document that caller must supply them.

### B7: Pipeline CD vs interpolated NILS-CD — documented different size
CATEGORY: METRIC CONSISTENCY (already known from A8)
SEVERITY: P3
LOCATION: `pipeline.py` vs `abbe.py nils()`
OBSERVATION: Pipeline CD = (ridx - lidx + 1) * dx_nm (pixel). NILS CD = 
interpolated crossing distance (sub-pixel). At grid=256: 27.50 vs ~27.62 nm.
Not identical. Different definition.
STATUS: CONFIRMED — expected

### B8: Grid convergence not monotonic for CD/NILS
CATEGORY: NUMERICAL ROBUSTNESS
SEVERITY: P2
LOCATION: `pipeline.py` / grid parameter
OBSERVATION: CD oscillates at low grids: 32->28.0, 48->26.67, 64->28.0, 128->28.0,
192->27.33, 256->27.50, 384->27.67, 512->27.75.
NILS: 32->5.25, 48->4.77, 64->5.19, 128->5.15, 256->4.97, 512->5.04.
Neither is monotonic. Grid=32 gives higher NILS than grid=256 (5.25 vs 4.97).
I_max constant 11.64 across all grids, I_mean varies 4.96-4.76.
EVIDENCE: `grid_convergence.json`
STATUS: CONFIRMED
RECOMMENDATION: Document grid resolution requirements. Default 256 is 
reasonable but not perfectly converged (~1% CD drift to 512).

### B9: Non-power-of-two grids silently accepted
CATEGORY: NUMERICAL / CONFIG
SEVERITY: P3
LOCATION: `SimulationConfig`
OBSERVATION: Grid values like 3, 100, 300, 1000 are accepted without warning.
Non-power-of-two grids may cause FFT issues in other modules (not directly
used in pipeline, but in hopkins.py and abbe_image).
STATUS: CONFIRMED from previous probe

### B10: dose=0 silent clamp (known A3, independently confirmed)
CATEGORY: SCIENTIFIC INTEGRITY
SEVERITY: P1
LOCATION: `pipeline.py` line 258
OBSERVATION: dose=0 clamped via `max(cfg.dose_mj_cm2, 1e-9)`. 
dose=0 => effective scaling factor = 20/1e-9 = 2e10. All aerial intensity
becomes essentially 0, CD=64 (full line). No warning.
STATUS: CONFIRMED
RECOMMENDATION: Raise ValueError for dose <= 0.

### B11: max_order=0 silent failure (known A4)
CATEGORY: SCIENTIFIC DOMAIN
SEVERITY: P2
LOCATION: `abbe.py` line 144
OBSERVATION: For periods <= 40 nm at NA=0.33, max_order = 0.
Aerial image = DC constant, CD=0, NILS=0. No warning.
STATUS: CONFIRMED
RECOMMENDATION: Add warning when max_order < 2.

### B12: sigma > 2 TCC grid saturation (known A1)
CATEGORY: NUMERICAL
SEVERITY: P2
LOCATION: `abbe.py` _compute_tcc_matrix, line 519
OBSERVATION: TCC integration grid fixed to [-2, 2]. sigma >= 2 fills entire grid.
sigma=2 and sigma=10 produce identical TCC and results.
STATUS: CONFIRMED