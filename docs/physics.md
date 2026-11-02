# The physics chain of euvsimulator — equations, parameters, provenance, status

Status date: 2026-09-06; chain numbers marked 2026-10-03 were re-measured after the 2026-10 fixes. Every default below names its source; "calibrated" and "assumed" are marked
as such. Open items are ranked in section 7.

## 1. Aerial image

Hopkins/Abbe partially coherent imaging with the transmission cross coefficients of a source shape on a
pupil grid (`aerial/abbe.py`). Sources: conventional disk, annular, dipole, quasar; scanner-style
annular-sector poles via `sigma_inner` / `pole_opening_deg` (imec "dipole 90X, σ 0.62/0.90"). The mask
is the thin-mask Fourier series of a 1D line/space grating with the Mo/Si multilayer and absorber
reflectivities from the transfer-matrix stack (`optics/`), both referred to the absorber top (the space
reflectance carries the vacuum round trip through the absorber height; until 2026-10 it referred to the
multilayer top, which put the absorber phase off by 2kd·cos 6°), or the RCWA path.
The chief-ray incidence is 6° (`pipeline.ML_INCIDENCE_DEG`, degrees); the TMM
entry points take **radians**, so the value is converted once before the call. The image is
normalised to the open-frame reflectivity, so `dose_mj_cm2` is the clear-field dose at wafer level. Not
modelled: flare, mask roughness, aberrations beyond defocus. Note for anchors: for a symmetric 1:1 image the edge
sits at the image mean (0.335 of the open frame at 44 nm pitch, NA 0.33, dipole 90X σ 0.62/0.90 as in the NXE1716 anchor), which fixes the ratio of
printing dose to flood through-dose.

The fast `aerial_threshold` model thresholds the image at a fraction of its own mean intensity
(scaled with dose). For one mask that is a fixed dose threshold; across masks it is not, because
the mean follows the mask duty cycle. MEEF at 64/32 nm: 0.48 with the mean-relative threshold,
1.03 with a fixed absolute threshold on the same images, 1.28 in the full chemistry at grid 256
(1.28 at grid 128; 2026-10-03).
Mask-to-mask comparisons (MEEF, pitch sweeps at one threshold) belong to `full_chem`.

## 2. Exposure

Dill ABC with Beer–Lambert attenuation through the film and acid = G0·(1 − e^{−C·E}):

| parameter | default | source | status |
|---|---|---|---|
| A | 0 µm⁻¹ | Yamamoto 2011 (no bleaching at EUV) | sourced |
| B | 4.44 µm⁻¹ | computed from the resist composition and density via CXRO f₂ (`materials.py`); Sekiguchi 2011 / Fallica 2016 measure 4.3–5.2 for named CARs | derived |
| C | 0.0152 cm²/mJ | LBNL base-titration value for MET-2D (OSTI 1004159, Eq. 1 = this convention); Fallica 2017 bleaching 0.010–0.021 for seven EUV CARs. PROLITH fits (0.09) are effective parameters (quencher-dependent; only k·C is fixed by flood data) | sourced |
| G0 (PAG) | 0.2 nm⁻³ | Mack 2011; LBNL's numbers imply ≈ 0.22 for MET-2D | sourced |
| acids per absorbed photon | 1.0 (surface), 1.2 LBNL-style | consequence of C, G0, B; LBNL measure 1.4–2.1 | consistency check (`tests/test_acid_yield.py`) |
| SE blur σ | 2.5 nm | Thackeray 2010 EUV-specific term inside a measured 11.5 nm decomposition; models 2.1–3.3 (Mack 2011); no direct measurement exists | sourced (model-derived) |

Photon shot noise: Poisson deposition of absorbed photons per voxel, spread by the SE point spread
function; with PAG sampling the acid count is compound-Poisson (Var/E = 1 + acids per photon,
`tests/test_acid_multiplicity.py`) (grid-invariant only with a non-zero SE blur — with 0 the Dill law saturates on single-photon
spikes and nothing prints). Optional PAG/quencher counting statistics (`exposure_stochasticity`).

## 3. Post-exposure bake

Two models. `"analytical"` (default, goldens): diffuse (σ = √(2·D·t_eff)) → neutralise (second-order
closed form, Mack 2011) → deprotect, M = exp(−k·h·t_eff) with the first-order acid lifetime
t_eff = τ(1 − e^{−t/τ}). `"reaction_diffusion"`: the concurrent system of Kang et al. (NIST) 2009,
dφ/dt = k h (1−φ), ∂h/∂t = D∇²h − k_trap h φ − k_Q G0 h q, ∂q/∂t = D_Q∇²q − k_Q G0 h q, solved by operator
splitting; validated on the NIST bilayer diffusion lengths (76/56/36/23 nm). With NIST's full Table 1 set
(k_Q 1.6, D_Q 7.3) it reproduces NIST's own model prediction (79/59/30/23 nm) within 7 %.
Both laws fit Yamamoto's flood curves equally, each with its own rate constant: at 110 °C k = 10.95 s⁻¹
with τ = 7.54 s, or k = 8.93 s⁻¹ with k_trap = 0.2076 s⁻¹. `peb_model` selects the pair; an unset `peb_k`
takes the chosen law's k, an explicit `peb_k` is kept. Until 2026-10 `"reaction_diffusion"` ran with the
analytical law's 10.95 next to its own k_trap, a pair that misses the flood curve (P(60 s) 0.139 instead of
0.178; Fig. 3: 0.176). In patterns the NIST law halves the printing dose of the default resist (64/32 nm,
dose-to-size 1.28 vs 0.65 mJ/cm² at grid 64, 1.26 vs 0.64 at grid 128, measured 2026-10-03; the old
mismatched pair gave 0.53 at grid 64, a factor 2.4) — which law holds for Polymer A is undecided (needs a
structured measurement).

| parameter | default | source | status |
|---|---|---|---|
| k (110 °C), `"analytical"` | 10.95 s⁻¹ | fit of the chain law to the complete digitised 110 °C curve of Yamamoto Fig. 3; k·H0 = 0.2305 s⁻¹ is what the data fix | sourced |
| τ (110 °C) | 7.54 s | same fit; τ(90 °C) = 35 s vs NIST 38 s on another resist | sourced |
| k(T), τ(T) | table 80–140 °C | all seven Fig. 3 curves; two Arrhenius regions (103 / 38 kJ/mol) | sourced (`peb_temperature_c`) |
| k (110 °C), `"reaction_diffusion"` | 8.93 s⁻¹ | NIST-law fit of the same curve, k·H0 = 0.188 s⁻¹; the default of that law since 2026-10 (before: 10.95) | sourced (for the concurrent model) |
| k_trap (110 °C) | 0.2076 s⁻¹ | same NIST-law fit, together with k = 8.93 s⁻¹ | sourced (for the concurrent model) |
| D | 4.2 nm²/s | Kang 2010, FT-IR bilayer, 90 °C, no temperature scaling available | sourced (one temperature) |
| k_Q | 1.2 nm³/s | NIST 2009 Table 1: 1.6 ± 1.0 (FTIR kinetics fit); 1.2 chosen on the bilayer cases 3/4, inside that range; Mack's 15 / Osaka's 12.6 are assumptions | sourced (one resist) |
| quencher | 0 (default) | NXE1716 anchor: Q/PAG 0.36 from the two-curve fit through the concurrent PEB | resist-specific |

Default PEB blur at 110 °C: √(2·4.2·7.54) = 7.9 nm, inside the 7.5–12 nm band of measured EUV-CAR blurs.

## 4. Development

Mack rate R(M) with R_max, R_min, M_th, n (Yamamoto 2011 Table 2 / Sekiguchi 2011 Table 6 for the
anchors), Eikonal first-arrival front (fast sweeping, per row; `eikonal3d` couples the rows), sub-pixel
CD from the arrival time at the film bottom (z = film thickness; until 2026-10 one layer below
it, 0.37 nm too wide at 21 layers). Optional dissolution noise (`development_stochasticity`): each
cell of edge a (4.3 nm, Thackeray's Rg; sources bracket 1–5 nm) carries n0·V polymer sites
(n0 = 1.63 nm⁻³ from the composition; V = (ax·dx)²·(az·dz) is the grid block that carries one draw,
ax = max(1, round(a/dx)), az = max(1, round(a/dz)), so the noise power per volume var·V = M/n0 is the
same on every grid; up to and including 2.2.1 the code used a³ for every block), the blocked count
fluctuates by Poisson statistics (Mack 2010, Eq. 36) and the cell dissolves at the Mack rate of its
own protection (Mack 2010 KPZ roughening).
Lateral-grid invariant; scales ≈ 1/a (per-row solver) or a⁻⁰·⁵ (3D) (measured before the 2026-10 fixes,
not re-measured) — the size of the dissolving unit is the main uncertainty of the roughness floor.

## 5. Roughness metrics

LER/LWR from edge and width profiles with a correlation-aware estimator (n_eff, l_int) and the
metrology passband of the source (`ler_passband_nm`; Anderson 10–834 nm, imec biased protocol
≈ 10.8–5500 nm). Measured values carry SEM bias (Lorusso/Mack 2018: ×1.2–1.7 for imec's biased
protocol). The NXE1716 anchor records a bias-corrected estimate next to the biased value
(`lwr_unbiased_estimate_nm` 5.1–5.7 nm against 6.7 nm); the MET-2D anchor records only SEM values
without noise correction, and no bias was published, so they are upper bounds.

For a user's own resist, `euv calibrate --bands` fits the chain to a wafer FEM and reports
dose-to-size and LWR at the corners of the two undecided structural choices (acid-loss law,
dissolution-unit size) as bands (`calibrate/bands.py`, 2.1). The law corner swaps the law together
with its k: a default k becomes the other law's default, a calibrated k is carried over by the ratio
of the two laws' fits to Yamamoto's 110 °C curve (8.93/10.95; k_trap stays Polymer A's), and with
`peb_temperature_c` both laws take that temperature's fits. The k each law ran with is reported
(`peb_k_per_law`). Until 2026-10 the trapping corner ran with the analytical law's k, which made the
dose band of the default resist a factor 2.40 instead of 1.96 (grid 128).

## 6. Anchors and what they say

| anchor | data | chain | verdict |
|---|---|---|---|
| Yamamoto 2011 Polymer A | Fig. 3 (7 T), Fig. 5 threshold 0.8 mJ/cm² | P(t) rms ≤ 0.03, threshold 0.762 | reproduced (same source as the defaults) |
| NIST bilayer 2009 | diffusion lengths 76/56/36/23 nm | 84/68.5/31.5/25.5 (k_Q 1.2, D_Q = D_H); with Table 1 (k_Q 1.6, D_Q 7.3) 84/63/28.5/21.5 against NIST's model 79/59/30/23 | within 25 % of the measurement, within 7 % of NIST's model |
| NXE1716 (Vesters) | DRM curves ×2, D2S 11.0, LWR 6.7 (biased) | flood rms 0.04; D2S 18.7 (1.70×, 2026-10-03; 19.7 and, with the reaction-diffusion PDE, 21.4 before the 2026-10 fixes, the latter not re-measured); LWR 4.8–13 nm 3σ depending on the 90 °C blur (measured before the 2026-10 fixes, not re-measured) | dose scale inconsistent between the two source experiments (PAB 110 vs 90 °C, substrate); LWR undetermined |
| MET-2D / XP 5271 | C, FQY, B, Mack, blur, E-size 12.5, LER 6.7 (SEM, upper bound) | LER 0.7 (photons) → 2.0 (+PAG) → 4.3 nm in-band (+dissolution noise) (measured before the 2026-10 fixes, not re-measured) | first measured EUV roughness of the right size without a fitted knob; not validated (SEM bias unpublished, a uncertain) |

## 7. Open questions, ranked

1. Which acid-loss law holds in patterns for Polymer A (first-order τ vs trapping by deprotected sites):
   factor 2 in printing dose; needs one structured measurement on that resist. Two measurements that
   would decide it: (a) dose-to-size vs PEB temperature at
   64/32 nm, 60 s bake, chain prediction D2S analytical / reaction_diffusion [mJ/cm²]: 80 °C 4.49/4.22,
   90 1.90/1.46, 100 1.46/0.90, 110 1.28/0.65, 120 1.10/0.49, 130 0.82/0.33, 140 0.70/0.26 — the ratio
   grows from 1.06 to 2.67 (grid 64, each law with its own fits via `peb_temperature_c`; the 110 °C pair
   is also the default of each `peb_model`; re-measured 2026-10-03 after the 2026-10 fixes (sampling,
   film-bottom CD, thin-mask phase reference), within 5.4 % of the campaign values of 2026-09-07);
   (b) a temperature jump, 150 s at 100 °C then 150 s at 140 °C: with acid loss the protection ratio
   stays ≈ 0.20, without loss (only a temperature-dependent accessible fraction) it falls to ≈ 0.04.
   Yamamoto's flood curves themselves cannot decide: first-order loss, trapping and an
   accessible-fraction model fit them equally (rms 0.016–0.017). The strong anti-correlation of k and τ
   across temperature (rate Ea ≈ 89 kJ/mol, extent Ea ≈ 24) is not a new effect but the trapping model's
   signature — Kang, Wu, Choi, De Silva, Ober, Prabhu, Macromolecules 43, 4275 (2010), Table 1, measured
   it on two other resists: Ea(k_P) 136 ± 3 / 152 ± 8, Ea(k_T) 86 ± 5 / 89 ± 7, Ea(D_H) 127 / 165 kJ/mol
   (P(HOSt-co-tBA) / CM4R). Those are the only free temperature series for k_trap and D; they are not
   used as defaults because they are other resists.
2. The dissolving unit a (1–5 nm): factor 2–4 in the roughness floor (measured before the 2026-10 fixes, not re-measured); a chain-based critical-ionization
   dissolution model would replace the cell.
3. NXE1716 dose scale: unpublished quencher loading, develop time and blur; not published.
4. Flare and mask roughness of the MET are not modelled; Anderson's SEM bias is unpublished.
5. D(T) has one temperature; k_Q one resist; the sampler's molecular variance.
