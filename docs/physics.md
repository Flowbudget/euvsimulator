# The physics chain of euvsimulator — equations, parameters, provenance, status

Status date: 2026-09-06. Every default below names its source; "calibrated" and "assumed" are marked
as such. The working log (`docs/claude_code_arbeitslog.md`, "Fortsetzung N") holds the measurements
behind each statement; the plan (`docs/analyse_2026-09-05_stand_und_plan.md`) the open items.

## 1. Aerial image

Hopkins/Abbe partially coherent imaging with the transmission cross coefficients of a source shape on a
pupil grid (`aerial/abbe.py`). Sources: conventional disk, annular, dipole, quasar; scanner-style
annular-sector poles via `sigma_inner` / `pole_opening_deg` (imec "dipole 90X, σ 0.62/0.90"). The mask
is the thin-mask Fourier series of a 1D line/space grating with the Mo/Si multilayer and absorber
reflectivities from the transfer-matrix stack (`optics/`), or the RCWA path. The image is normalised to
the open-frame reflectivity, so `dose_mj_cm2` is the clear-field dose at wafer level. Not modelled:
flare, mask roughness, aberrations beyond defocus. Note for anchors: for a symmetric 1:1 image the edge
sits at the image mean (0.318 of the open frame at 44 nm pitch, NA 0.33), which fixes the ratio of
printing dose to flood through-dose.

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
splitting; validated on the NIST bilayer diffusion lengths (76/56/36/23 nm) with k_Q fitted on one case.
Both laws fit Yamamoto's flood curves equally; in patterns the NIST law halves the printing dose of the
default resist — which law holds for Polymer A is undecided (needs a structured measurement).

| parameter | default | source | status |
|---|---|---|---|
| k (110 °C) | 10.95 s⁻¹ | fit of the chain law to the complete digitised 110 °C curve of Yamamoto Fig. 3; k·H0 = 0.2305 s⁻¹ is what the data fix | sourced |
| τ (110 °C) | 7.54 s | same fit; τ(90 °C) = 35 s vs NIST 38 s on another resist | sourced |
| k(T), τ(T) | table 80–140 °C | all seven Fig. 3 curves; two Arrhenius regions (103 / 38 kJ/mol) | sourced (`peb_temperature_c`) |
| k_trap (110 °C) | 0.2076 s⁻¹ | NIST-law refit of the same curve | sourced (for the concurrent model) |
| D | 4.2 nm²/s | Kang 2010, FT-IR bilayer, 90 °C, no temperature scaling available | sourced (one temperature) |
| k_Q | 1.2 nm³/s | NIST bilayer cases with quencher in the receiving layer; Mack's 15 / Osaka's 12.6 are assumptions | sourced (one resist) |
| quencher | 0 (default) | NXE1716 anchor: Q/PAG 0.36 from the two-curve fit through the concurrent PEB | resist-specific |

Default PEB blur at 110 °C: √(2·4.2·7.54) = 7.9 nm, inside the 7.5–12 nm band of measured EUV-CAR blurs.

## 4. Development

Mack rate R(M) with R_max, R_min, M_th, n (Yamamoto 2011 Table 2 / Sekiguchi 2011 Table 6 for the
anchors), Eikonal first-arrival front (fast sweeping, per row; `eikonal3d` couples the rows), sub-pixel
CD from the bottom-layer arrival time. Optional dissolution noise (`development_stochasticity`): each
cell of edge a (4.3 nm, Thackeray's Rg; sources bracket 1–5 nm) carries n0·a³ polymer sites
(n0 = 1.63 nm⁻³ from the composition), the blocked count fluctuates by Poisson statistics (Mack 2010,
Eq. 36) and the cell dissolves at the Mack rate of its own protection (Mack 2010 KPZ roughening).
Lateral-grid invariant; scales ≈ 1/a (per-row solver) or a⁻⁰·⁵ (3D) — the size of the dissolving unit is
the main uncertainty of the roughness floor.

## 5. Roughness metrics

LER/LWR from edge and width profiles with a correlation-aware estimator (n_eff, l_int) and the
metrology passband of the source (`ler_passband_nm`; Anderson 10–834 nm, imec biased protocol
≈ 10.8–5500 nm). Measured values carry SEM bias (Lorusso/Mack 2018: ×1.2–1.7 for imec's biased
protocol); the anchor data record bias-corrected estimates.

For a user's own resist, `euv calibrate --bands` fits the chain to a wafer FEM and reports
dose-to-size and LWR at the corners of the two undecided structural choices (acid-loss law,
dissolution-unit size) as bands (`calibrate/bands.py`, 2.1).

## 6. Anchors and what they say

| anchor | data | chain | verdict |
|---|---|---|---|
| Yamamoto 2011 Polymer A | Fig. 3 (7 T), Fig. 5 threshold 0.8 mJ/cm² | P(t) rms ≤ 0.03, threshold 0.766 | reproduced (same source as the defaults) |
| NIST bilayer 2009 | diffusion lengths 76/56/36/23 nm | 83/68/34/28 (k_Q on case 3) | reproduced, zero free parameters otherwise |
| NXE1716 (Vesters) | DRM curves ×2, D2S 11.0, LWR 6.7 (biased) | flood rms 0.04; D2S 19–21 (1.7–1.9×); LWR 4.8–13 nm 3σ depending on the 90 °C blur | dose scale inconsistent between the two source experiments (PAB 110 vs 90 °C, substrate); LWR undetermined |
| MET-2D / XP 5271 | C, FQY, B, Mack, blur, E-size 12.5, LER 6.7 | LER 0.7 (photons) → 2.0 (+PAG) → 4.3 nm in-band (+dissolution noise) | first measured EUV roughness of the right size without a fitted knob; not validated (SEM bias unpublished, a uncertain) |

## 7. Open questions, ranked

1. Which acid-loss law holds in patterns for Polymer A (first-order τ vs trapping by deprotected sites):
   factor 2 in printing dose; needs one structured measurement on that resist. Two measurements that
   would decide it (analysis 2026-09-07, work log Fortsetzung 48): (a) dose-to-size vs PEB temperature at
   64/32 nm, 60 s bake, chain prediction D2S analytical / reaction_diffusion [mJ/cm²]: 80 °C 4.60/4.29,
   90 1.93/1.49, 100 1.49/0.91, 110 1.29/0.67, 120 1.12/0.50, 130 0.83/0.35, 140 0.71/0.27 — the ratio
   grows from 1.07 to 2.66; (b) a temperature jump, 150 s at 100 °C then 150 s at 140 °C: with acid loss
   the protection ratio stays ≈ 0.20, without loss (only a temperature-dependent accessible fraction) it
   falls to ≈ 0.04. Yamamoto's flood curves themselves cannot decide: first-order loss, trapping and an
   accessible-fraction model fit them equally (rms 0.016–0.017). The strong anti-correlation of k and τ
   across temperature (rate Ea ≈ 89 kJ/mol, extent Ea ≈ 24) is not a new effect but the trapping model's
   signature — Kang, Wu, Choi, De Silva, Ober, Prabhu, Macromolecules 43, 4275 (2010), Table 1, measured
   it on two other resists: Ea(k_P) 136 ± 3 / 152 ± 8, Ea(k_T) 86 ± 5 / 89 ± 7, Ea(D_H) 127 / 165 kJ/mol
   (P(HOSt-co-tBA) / CM4R). Those are the only free temperature series for k_trap and D; they are not
   used as defaults because they are other resists.
2. The dissolving unit a (1–5 nm): factor 2–4 in the roughness floor; a chain-based critical-ionization
   dissolution model would replace the cell.
3. NXE1716 dose scale: unpublished quencher loading, develop time and blur; request sent to imec.
4. Flare and mask roughness of the MET are not modelled; Anderson's SEM bias is unpublished.
5. D(T) has one temperature; k_Q one resist; the sampler's molecular variance (log Fortsetzung 25).
