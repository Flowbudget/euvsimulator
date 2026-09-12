"""Full simulation pipeline — end-to-end EUV lithography simulation.

Connects all modules: mask → RCWA → aerial image → resist → CD.

Resist presets (typical SE blur sigma for different resist types):
    RESIST_PRESETS = {
        "CAR": 2.5,      # Chemically Amplified Resist (DEFAULT_SE_BLUR_NM)
        "nonCAR": 2.5,   # Non-chemically amplified / metal resist
        "HighNA": 3.0,   # High-NA EUV (thinner resist)
    }
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Optional

import torch

from euvsimulator.accel.device import select_device, set_default_dtype
from euvsimulator.aerial.abbe import aerial_from_orders, nils
from euvsimulator.constants import HC_EV_NM
from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity
from euvsimulator.resist.develop import (
    MackModel,
    dissolution_cell_noise,
    edge_positions_from_arrival,
    eikonal_development,
    surface_advancement_level_set,
)
from euvsimulator.resist.exposure import (
    dill_abc_exposure,
    sample_pag_quencher_acid,
)
from euvsimulator.resist.peb import (
    reaction_diffusion_pde,
    reaction_diffusion_with_quenching,
)
from euvsimulator.resist.stochastic import (
    extract_edges,
    extract_ler,
    extract_lwr,
    ler_estimate,
    photon_deposition_shot_noise,
)

# Resist presets — typical SE blur sigma [nm] for different resist types
# Reference dose of the aerial_threshold resist model [mJ/cm²]. That model
# has no chemistry: it prints wherever the aerial intensity exceeds a fixed
# fraction (resist_threshold_norm) of the image's mean intensity AT THIS
# REFERENCE DOSE, so the threshold in absolute units is
# resist_threshold_norm · mean(I) · (REFERENCE / dose). The number is a
# model-definition constant (it fixes what "threshold_norm = 0.5" means),
# not a physical or calibrated quantity; it was previously an unnamed
# literal in two places.
AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2 = 20.0


class SimulationCancelledError(RuntimeError):
    """Raised by run_simulation when its progress hook asks it to stop."""


# progress hook: called as progress(done, total) before each stochastic
# realisation; returning False cancels the run (SimulationCancelledError).
ProgressHook = Callable[[int, int], bool]

# Default resist composition for the first-principles Dill B (see the dill_B
# field): poly(hydroxystyrene) C8H8O with 35 % of the phenol sites carrying a
# tBOC group (adds C5H8O2 per protected site), film density 1.20 g/cm3.
DEFAULT_RESIST_COMPOSITION = {"C": 8 + 0.35 * 5, "H": 8 + 0.35 * 8, "O": 1 + 0.35 * 2}
DEFAULT_RESIST_DENSITY_G_CM3 = 1.20
# = linear_absorption_coefficient_per_um(composition, density); pinned by
# tests/test_absorption_coefficient.py
DEFAULT_DILL_B_PER_UM = 4.44

# Secondary-electron blur sigma [nm] of the default resist chain. Thackeray,
# Wagner, Kang et al. (Dow), J. Photopolym. Sci. Technol. 23(5) 631 (2010),
# Sec. 4 / Eq. (8): the measured EUV total blur of 11.5 nm decomposes as
# 9.7 nm latent-image reaction-diffusion (+) 4.3 nm polymer radius of gyration
# (+) 2.5 nm EUV-specific term (+) 3.7 nm unexplained, in quadrature. The
# 2.5 nm is the mean radius of their Monte-Carlo acid cloud per absorbed
# photon (IP 9.75 eV, PAG reaction radius 1.3 nm) and is used by them as a
# blur length; Mack, Biafore & Smith 2011 (JM3 10, 033019) put the electron
# blur radius at 2.1-3.3 nm from a different model. No DIRECT measurement of
# the SE blur alone was found (log Fortsetzung 26); this is the one value that
# sits inside a measured decomposition. It is the sigma of the 2D Gaussian
# that gaussian_se_blur applies to the dose map and to each photon-deposition
# realisation (resist/stochastic.py); it is NOT applied by the
# aerial_threshold model, which thresholds the aerial image directly.
DEFAULT_SE_BLUR_NM = 2.5

# Blocked (acid-labile) polymer sites per nm^3 of the default resist: 35 %
# protection (Yamamoto 2011, Polymer A) of the monomer-unit density that
# DEFAULT_RESIST_COMPOSITION / DEFAULT_RESIST_DENSITY_G_CM3 give (155.2 g/mol
# per unit -> 4.66 units/nm^3) = 1.63 nm^-3. Cross-check: Jin 2025 (Osaka)
# states 2.26 nm^-3 for 54.6 % t-BOC PHS (this arithmetic gives 2.54). Used by
# the development-noise model (resist/develop.dissolution_cell_noise).
DEFAULT_BLOCKED_SITE_DENSITY_PER_NM3 = 1.63


def acids_per_absorbed_photon(cfg: "SimulationConfig") -> float:
    """Acids generated per ABSORBED EUV photon in the low-dose limit implied by
    the configured Dill C, PAG density and absorption coefficient.

    dH/dE = C·G0 [nm⁻³ per mJ/cm²] (acid = G0·(1 − e^{−C·E}), E → 0) divided by
    the absorbed photon density per unit dose, N_ph·α with N_ph = photons per
    nm² per mJ/cm² (0.68 at 13.5 nm) and α = A + B in nm⁻¹ (thin-film limit,
    no depth averaging). This is the "film quantum yield" of Brainard/LBNL
    (acids per absorbed photon; measured 1.4–2.1 for EUV-2D, MET-2D, XP-5496 at
    standard PAG loadings, OSTI 1004159 Table 3) and Kozawa's acid-generation
    quantum efficiency (≈ 2), and it ties C, G0 and B together -- three numbers
    that otherwise come from three different sources.
    """
    photon_energy_J = 6.62607015e-34 * 2.99792458e8 / (cfg.wavelength_nm * 1e-9)
    photons_per_nm2_per_mjcm2 = 1e-3 / photon_energy_J / 1e14
    alpha_per_nm = (cfg.dill_A + cfg.dill_B) * 1e-3
    return cfg.dill_C * cfg.pag_density_per_nm3 / (photons_per_nm2_per_mjcm2 * alpha_per_nm)


# Secondary-electron blur sigma [nm] per resist family. Only "CAR" is sourced
# (see SimulationConfig.se_blur_nm); "nonCAR" and "HighNA" are unsourced
# placeholders kept for CLI compatibility (2026-09-06, log Fortsetzung 26).
RESIST_PRESETS = {
    "CAR": DEFAULT_SE_BLUR_NM,  # Thackeray et al. 2010 EUV-specific blur term
    "nonCAR": 2.5,  # UNSOURCED placeholder (metal-oxide resists; Inpria-YA fit gives 3.3)
    "HighNA": 3.0,  # UNSOURCED placeholder
}


@dataclass
class SimulationResult:
    """Results from a full pipeline simulation.

    Parameters
    ----------
    aerial_image : (G, G) float64
        Computed aerial image intensity.
    resist_profile : (G, G) float64
        Developed resist profile (1 = developed through the film, 0 = resist remaining).
    cd_nm : float
        Critical dimension [nm] (0 if not measurable).
    nils_value : float
        Normalised Image Log-Slope at line edge.
    absorber_reflectivity : float
        Reflectivity of the absorber region (normalised).
    clear_field_reflectivity : float
        Intensity reflectivity |r_ML|² of the absorber-free multilayer at
        the chief-ray angle (unpolarised average when use_rcwa=True). The
        aerial image is divided by this value so that an open frame
        exposes the resist to exactly ``dose_mj_cm2`` (see
        ``SimulationConfig.dose_mj_cm2``); it is reported here so the
        mask-level intensity can be recovered as
        ``aerial_image * clear_field_reflectivity``.
    ler_nm : float
        Line-edge roughness [nm] (1σ). Only populated when enable_stochastic=True.
    lwr_nm : float
        Line-width roughness [nm] (1σ). Only populated when enable_stochastic=True.
    """

    aerial_image: torch.Tensor
    resist_profile: torch.Tensor
    cd_nm: float = 0.0
    nils_value: float = 0.0
    absorber_reflectivity: float = 0.0
    ler_nm: float = 0.0
    lwr_nm: float = 0.0
    clear_field_reflectivity: float = 1.0
    ler_metadata: dict | None = None  # Structured LER metadata (large_n estimator)
    # Populated when stochastic_ler_estimator="large_n".  Keys: ler_nm,
    # n_rows, n_eff, l_int_px, l_int_nm, uncertainty_nm, ci95_low_nm,
    # ci95_high_nm, seed_count, estimator, rho_truncation, disclaimer.
    # None for the legacy estimator.


@dataclass
class SimulationConfig:
    """Configuration for a full pipeline simulation.

    Parameters
    ----------
    wavelength_nm : float
        Exposure wavelength [nm] (default: 13.5).
    na : float
        Numerical aperture (default: 0.33).
    sigma : float
        Partial coherence factor (default: 0.8).
    period_nm : float
        Mask pattern period [nm] (default: 64).
    line_width_nm : float
        Absorber line width [nm] (default: 32).
    absorber_height_nm : float
        Absorber thickness [nm] (default: 60).
    absorber_material : str
        Absorber material (default: "Ta").
    n_rcwa_orders : int
        RCWA Fourier orders (default: 21).
    dose_mj_cm2 : float
        Exposure dose [mJ/cm²] (default: 20).
    grid : int
        Simulation grid size (default: 256).
    device : str
        PyTorch device (default: "auto"). Use "auto" to auto-select GPU
        if available, or "cpu"/"cuda" explicitly.


    Experimental options (2.0.0; off by default, documented in docs/physics.md):
    ``development_stochasticity`` (dissolution-cell noise), ``development_model="eikonal3d"``
    (y-coupled front), ``peb_model="reaction_diffusion"`` (concurrent PEB, NIST law),
    ``exposure_stochasticity`` (PAG/quencher counting), ``ler_passband_nm`` (metrology band),
    ``peb_temperature_c`` (measured kinetics at 80-140 C). Their physics is sourced; their effect
    on printed results is characterised in the log, not validated against independent data.
    """

    wavelength_nm: float = 13.5
    na: float = 0.33
    sigma: float = 0.8
    illumination_shape: str = "conventional"
    # Scanner-style source geometry (2026-09-06, stage B1): inner radius and
    # pole opening angle for annular/dipole/quasar; None = legacy fixed poles.
    # imec NXE3300B "dipole 90X, sigma 0.62/0.90" (Vesters 2019, Sec. 4.3.2):
    # illumination_shape="dipole", sigma=0.90, sigma_inner=0.62, pole_opening_deg=90.
    sigma_inner: float | None = None
    pole_opening_deg: float | None = None
    ml_n_bilayers: int = 50
    ml_d_mo_nm: float = 2.8
    ml_d_si_nm: float = 4.1
    ml_gamma: float | None = None
    ml_grading_linear_nm: float = 0.0
    ml_grading_parabolic_nm: float = 0.0
    ml_roughness_nm: float = 0.0
    ml_capping: str = "Ru"
    ml_capping_nm: float = 2.5
    period_nm: float = 64.0
    line_width_nm: float = 32.0
    absorber_height_nm: float = 60.0
    absorber_material: str = "Ta"
    n_rcwa_orders: int = 21
    # Projection demagnification (mask-to-wafer). period_nm/line_width_nm are
    # WAFER-scale; the physical mask carries mask_demagnification × larger
    # features and is what the RCWA solver must see: the diffraction angles
    # at the mask are asin(sin θ_CRA − m·λ/(M·P)), and only at these angles is
    # the Mo/Si Bragg mirror's angular acceptance (≈ ±10° about the 6° chief
    # ray for the default stack) correctly applied to each order. Running the
    # RCWA at wafer scale (the behaviour before 2026-09-04) put the ±1 orders
    # of a 64 nm-pitch grating at +18°/−6°, where the mirror reflects 0.08 vs
    # 0.65, and produced a 10.8× (instead of the physical ≈1.2×) ±1-order
    # asymmetry. 4× is the NXE/EXE isotropic value (constants.DEMAGNIFICATION);
    # High-NA EXE:5000 is anamorphic 4×(x)/8×(y) -- this 1D line/space model
    # resolves x only, so 4× is also correct there. Not used by the thin-mask
    # path, whose Fourier coefficients are scale-free.
    mask_demagnification: float = 4.0
    # Exposure dose [mJ/cm²] in the STANDARD lithographic convention: the
    # energy density delivered to the resist at the wafer in a large clear
    # (absorber-free) area. Mack, "Inside PROLITH" (1997), ch. 9: "Let E be
    # the nominal exposure energy (i.e., the intensity in a large clear
    # area times the exposure time), I(x) the normalized image intensity
    # ... the exposure energy as a function of position within the resist
    # is just E·I(x)·I(z)." This is the same scale on which dose-to-clear
    # (E0), dose-to-size and dill_C [cm²/mJ] are defined and published, so
    # values from the literature (Yamamoto 2011, Vesters 2019, PSI resist
    # screening) are directly comparable. run_simulation() enforces it by
    # dividing the Hopkins image (which is relative to unit illumination of
    # the MASK, i.e. an open frame comes out at |r_ML|² ≈ 0.65) by the
    # multilayer's clear-field reflectivity -- see the normalisation block
    # there. Before 2026-09-04 this division was missing and the resist saw
    # only 0.647 × the nominal dose (docs/audit_2026-09-04_vollpruefung.md, A2).
    dose_mj_cm2: float = 20.0
    # (resist_threshold, a field that was never read, removed 2026-09-04;
    # resist_threshold_norm below is the one the aerial_threshold model uses.)
    resist_model: str = "aerial_threshold"
    resist_threshold_norm: float = 0.5
    # Secondary-electron blur sigma [nm], see DEFAULT_SE_BLUR_NM (Thackeray
    # 2010). Until 2026-09-06 the default was 0.0, which in the stochastic
    # full_chem path means white Poisson noise per grid pixel: on a 0.17 nm
    # grid that is 0.007 photons per pixel, single-photon spikes of ~250 mJ/cm²
    # saturate the Dill law and the line does not print at all (LWR = 0,
    # log Fortsetzung 26). The SE PSF is what makes the noise grid-invariant.
    se_blur_nm: float = DEFAULT_SE_BLUR_NM
    focus_nm: float = 0.0
    grid: int = 256
    device: str = "auto"

    # Dill ABC exposure parameters.
    #
    # LITERATURE REFERENCE (2026-09-02 research pass, see
    # docs/claude_code_arbeitslog.md and audit/ for the full trail):
    # Fallica, R.; Stowers, J. K.; Grenville, A.; Frommhold, A.; Robinson,
    # A. P. G.; Ekinci, Y. "Dynamic absorption coefficients of chemically
    # amplified resists and nonchemically amplified resists at extreme
    # ultraviolet." J. Micro/Nanolith. MEMS MOEMS 15(3), 033506 (2016).
    # doi:10.1117/1.JMM.15.3.033506 — directly measured Dill A/B/C for
    # several EUV-specific CAR platforms ("EUV 1/2/3/3+S" in the paper,
    # organic, undisclosed manufacturer; Fig. 6 there).
    #
    # Measured ranges for EUV-specific organic CAR (their Fig. 6, values
    # read off the bar chart, approximate):
    #   A ~= 0.2-0.45 um^-1, B ~= 4-5 um^-1, C ~= 0.13-0.43 cm^2/mJ.
    # Other C measurements cited therein (different resists/methods):
    #   0.04 cm^2/mJ (film-thickness-loss method, ref. 16 in the paper),
    #   0.0409 +/- 0.0023 cm^2/mJ (FTIR, ref. 17), 0.037-0.055 cm^2/mJ
    #   (refs. 18-20) -- i.e. C ~= 0.04-0.5 cm^2/mJ across methods/resists.
    #
    # IMPORTANT physical finding from the paper (Sec. 3.2): for EUV CAR,
    # A is much smaller than the total absorption coefficient alpha, and
    # B ~= alpha (i.e. A << B) -- the OPPOSITE regime from i-line/g-line
    # resists, which have A >> B. CORRECTED (2026-09-02, second research
    # pass) to A=0.3, B=4.5 um^-1 -- the midpoint of Fallica et al.'s own
    # measured EUV-CAR range (A~=0.2-0.45, B~=4-5 um^-1). Independently
    # corroborated by a second, unrelated real-resist calibration
    # (Schnattinger PhD thesis, FAU 2008/2009, open.fau.de -- A=0.0,
    # B=2.36 um^-1 for a real 193nm ArF-immersion CAR resist; same A<<B
    # regime, though that source is NOT itself used for the EUV magnitude
    # since it's the wrong wavelength -- see mack_* parameters below for
    # why that distinction matters).
    #
    # ARCHITECTURE GAP, discovered 2026-09-03 (round 9, while wiring
    # MackModel into the pipeline -- see mack_R_max note below): dill_A and
    # dill_B currently have ZERO EFFECT ON ANY SIMULATION OUTPUT, full stop
    # -- not just "not used on the aerial_threshold path" as an earlier,
    # narrower version of this note claimed. Verified by grepping the
    # entire src tree: cfg.dill_A/cfg.dill_B are read nowhere outside this
    # dataclass declaration and the CLI pass-through in io/cli.py. The one
    # function in this codebase that DOES implement real Beer-Lambert
    # depth-resolved absorption with A and B, dill_abc_exposure() in
    # resist/exposure.py, is exported from resist/__init__.py but never
    # called from pipeline.py or anywhere else -- the full_chem path
    # instead calls the separate, simplified dose_to_acid() (same file),
    # which only takes C and Q and has no depth/absorption-coefficient
    # concept at all. Confirmed experimentally, not just by reading code:
    # SimulationConfig(dill_A=.., dill_B=.., ...) with every combination of
    # old/new values, all else equal, produces bitwise-identical
    # aerial_image AND full_chem outputs (cd_nm, ler_nm, lwr_nm) as long as
    # dill_C is held fixed -- isolating dill_C alone reproduces 100% of an
    # observed golden-value LER/LWR shift that an earlier commit incorrectly
    # attributed to dill_A/B (see test_ler_production_integration.py and
    # test_development_stochasticity.py, corrected in the same commit as
    # this note). So this is NOT a regression of the "solide geprüft"
    # aerial_threshold reference values (dill_A/B were never used there
    # either), but the citation work above for dill_A/B, real and carefully
    # sourced as it is, is currently inert -- a second, separate wiring gap
    # alongside the mack_R_max/R_min/n one below, not yet fixed here.
    # UPDATE (2026-09-03, round 9 -- see mack_R_max/mack_R_min/mack_n/mack_M_th
    # below for the full story): dill_A/B replaced again with a SELF-CONSISTENT
    # set from a single real EUV-exposed resist -- Yamamoto, H.; Kozawa, T.;
    # Tagawa, S. (Osaka University); Mimura, T.; Iwai, T.; Onodera, J. (Tokyo
    # Ohka Kogyo Co.). "Dissolution Kinetics in Chemically Amplified EUV
    # Resist." J. Photopolym. Sci. Technol. 24(4), 405-410 (2011), free via
    # J-STAGE: https://www.jstage.jst.go.jp/article/photopolymer/24/4/24_4_405/_pdf
    # (fetched and read directly, including a 300dpi page render to confirm
    # table units against a possible OCR error -- see mack_M_th note for that
    # check). Real EUV exposure (Energetic/Energetiq EQ-10M source), a real
    # PHS-derivative CAR resist ("Polymer A", 35% acid-labile protecting
    # groups, TPS-tf PAG, TOK-affiliated formulation -- not a branded product
    # name, but genuine industrial chemistry, not a lab curiosity), Table 2's
    # "ABC Parameters" (their label for the classic Dill A/B/C model, fit for
    # direct use in PROLITH): A=0/µm, B=1.06/µm, C=0.08997 cm²/mJ.
    # A=0 agrees with (and is even more extreme than) the A<<B EUV regime
    # already established by Fallica et al. 2016 (A~=0.2-0.45, B~=4-5); B is
    # ~4x smaller than Fallica's range -- legitimate resist-to-resist
    # variation (absorber/PAG loading differs by formulation), not a
    # contradiction, and not averaged away with Fallica's numbers: this
    # project's "no compromises" rule favors one INTERNALLY CONSISTENT set
    # (A, B, C, Rmax, Rmin, Mth, n all fit together from the same real
    # measurement campaign) over a patchwork of independently-best-per-
    # parameter picks that were never fit against each other. Fallica et
    # al.'s ranges remain valuable as an independent cross-check that the
    # regime (not the exact numbers) is right -- kept in the paragraph below.
    # CAVEAT (2026-09-05, tests/test_yamamoto_anchor.py): implemented in the
    # standard Mack forms (acid = 1 - exp(-C*E); M = exp(-k*acid*t_PEB); Mack
    # R(M)), Table 2 does NOT reproduce the paper's own measurements on the
    # same resist at the same PEB (110 C / 60 s): Fig. 3 (FTIR, 1.4 mJ/cm²)
    # shows a protection ratio of ~0.18 after 60 s where the chain gives 0.60,
    # and Fig. 5 (RDA dissolution rate vs. flood dose, 35 % protection) puts
    # the dissolution threshold at ~0.8 mJ/cm² where the chain puts it at
    # ~2.7 mJ/cm² -- both readings from the figures (axis-calibrated, ±10 %),
    # both giving the same factor ~3.4 in k*C. The paper's own PEB kinetics
    # (Eq. 1) contains an acid-loss term (K_loss / acid lifetime) and a
    # reaction order m that PROLITH's Table-2 translation and this chain do
    # not carry; no value for either is published. Consequence: the SHAPE
    # parameters (Mth, n, Rmax/Rmin, B) are sourced, but the absolute dose
    # scale of the default resist is uncertain by at least that factor and
    # is NOT a validation of sensitivity in either direction. The PROLITH
    # doses of 20-30 mJ/cm² quoted in the paper are set values for profile
    # plots, not a dose-to-size, and are not an anchor either.
    # Bleachable absorption coefficient [1/µm] -- Yamamoto et al. 2011 (EUV-native, self-consistent
    # with dill_B/C and mack_* below); Fallica et al. 2016 independently confirms the same A<<B
    # regime (their range 0.2-0.45); see note above
    dill_A: float = 0.0
    # Non-bleachable absorption coefficient [1/µm]. COMPUTED from the default
    # resist's composition (2026-09-05), not taken from Yamamoto Table 2:
    # far from absorption edges the EUV absorption of an organic film is fixed
    # by composition and density through the CXRO f2 factors (materials.
    # linear_absorption_coefficient_per_um). Polymer A of Yamamoto 2011 is PHS
    # with 35 % acid-labile protection; with a tBOC-type group and 1.20 g/cm3
    # (Kang et al. 2010's density for the same polymer class) that gives
    # 4.44 µm-1 (PHS itself 4.0-4.2, PMMA 5.2, oxygen-free polystyrene 2.95).
    # Table 2's 1.06 µm-1 is below polystyrene and therefore not possible for a
    # PHS film; three independent measurements agree with the computed range
    # (Sekiguchi InTech 2011 Table 6: MET-1K/2D 4.32/5.21; Fallica et al. 2016:
    # 4-5; Kang et al. 2010). Effect measured before the change (arbeitslog
    # Fortsetzung 19): absorbed fraction 5.2 % -> 19 %, dose-to-size +14-16 %,
    # photon-shot-noise LWR down by ~2.5-3.5x. tests/test_absorption_coefficient.py
    # pins this default to the derivation.
    dill_B: float = DEFAULT_DILL_B_PER_UM
    #
    # dill_C ADDITIONAL CROSS-CHECK (2026-09-02, third research pass): Kazazis,
    # D. et al. (ARCNL), "Absorption coefficient and exposure kinetics of
    # photoresists at EUV," Proc. SPIE 10143, 101430A (2017), freely hosted
    # at ir.arcnl.nl (ARCNL = Dutch EUV lithography institute, ASML-affiliated).
    # Measured Dill C directly for seven real, state-of-the-art organic EUV CAR
    # formulations (P1-P3, several PAG loadings): 0.010-0.021 cm^2/mJ -- LOWER
    # than both the current default and Fallica et al.'s own EUV-CAR range
    # (0.13-0.43). Combined honest range across all real EUV-CAR measurements
    # found in this search: ~0.010-0.43 cm^2/mJ, i.e. a >40x spread between
    # different real resists. dill_C is evidently strongly resist-specific (PAG
    # chemistry/loading dependent, per this same paper); 0.05 remains a
    # defensible order-of-magnitude pick within this wide envelope, not an
    # outlier, so left unchanged -- but do not treat 0.05 as "the" EUV CAR
    # value if a specific resist is being modeled; recalibrate per-resist.
    # UPDATE (2026-09-03, round 9): replaced with Yamamoto et al. 2011's
    # self-consistent C=0.08997 cm²/mJ (see the dill_A/B note above for the
    # full citation and the internal-consistency reasoning) -- comfortably
    # inside the 0.010-0.43 cm²/mJ envelope already established below by
    # Fallica/Kazazis, so this is not a magnitude surprise, just a switch to
    # a value that is fit jointly with dill_A/B/mack_R_max/mack_R_min/
    # mack_M_th/mack_n from one real EUV measurement rather than picked
    # independently.
    # UPDATE (2026-09-06, plan stage A2, log Fortsetzung 25): 0.08997 -> 0.0152.
    # The PROLITH-fitted C values (Yamamoto 2011 Polymer A 0.090; Sekiguchi
    # InTech 2011 Table 6 MET-1K/2D 0.086/0.090; Sekiguchi IEEJ 2013 0.128 ->
    # 0.0435 WITH QUENCHER) are effective parameters: a pure exposure C cannot
    # depend on the quencher, and in the low-dose regime (C*E << 1) the
    # deprotection data they were fitted to only fix the product k*C. Direct
    # measurements of C in exactly this model's convention, acid = G0*(1 -
    # exp(-C*E)) with E the INCIDENT dose, are a factor 4-9 lower:
    #   * Brainard et al. (LBNL), "Film Quantum Yields of EUV & Ultra-High PAG
    #     Photoresists", OSTI 1004159, Eq. (1) and Table 3 -- base-titration /
    #     clearing-dose method (chemical acid count): MET-2D (XP5271D) 0.0152,
    #     XP-5496 0.0167, EUV-2D 0.046-0.051 cm²/mJ.
    #   * Fallica et al. (PSI/ARCNL), Proc. SPIE 10143, 101430A (2017) -- EUV
    #     bleaching (PAG decay with incident flux), Fig. 9: seven EUV CARs
    #     0.010-0.021 cm²/mJ, no PAG-loading dependence up to +40 %. (Cited
    #     as "Kazazis et al." in the paragraph above; first author is Fallica.)
    # 0.0152 is LBNL's value for MET-2D, the resist for which Sekiguchi's
    # Table 6 gives the PROLITH set (B 5.21, C 0.090) -- the same resist,
    # measured two ways, factor 6 apart. With G0 = 0.2 nm^-3 and B = 4.44 µm^-1
    # the acids per absorbed photon become 1.0 at the surface (LBNL-style,
    # 80 nm film: 1.24 vs their measured 1.39) instead of 6.0 with C = 0.090
    # (tests/test_acid_yield.py). Yamamoto's Fig. 3/4/5 anchors are kept by
    # re-deriving peb_k from the same data (see peb_k). Preflight (monkey-
    # patch, pre-registered): dose-to-size +2.7/+2.9 % (P = 64/44), photon-
    # shot-noise LWR unchanged within ±3 %, anchors within their pins.
    # Photo-rate constant [cm²/mJ]; includes the PAG quantum efficiency (Mack 2013 EUV exposure
    # model), no separate Q factor.
    dill_C: float = 0.0152
    # dill_Q -- REMOVED 2026-09-04. The former field multiplied the Dill
    # acid yield, acid = Q·(1 − e^{−C·E}), capping it at Q = 0.5. That
    # double-counts the PAG quantum efficiency: in Mack's EUV exposure model
    # (Mack, "Stochastic exposure kinetics of EUV photoresists: Trapping
    # model", 2013, Eqs. 8 and 10) φ_PAG is a FACTOR INSIDE the Dill C
    # parameter, C ∝ φ_PAG·σ_e-PAG·…, and the acid concentration saturates
    # at 1 (every PAG converts at infinite dose). dill_C here is Yamamoto
    # et al. 2011's PROLITH-fitted value, which already contains φ_PAG. A
    # separate Q therefore has no physical place; it was calibration by
    # another name (docs/audit_2026-09-04_vollpruefung.md, A5, and
    # docs/claude_code_arbeitslog.md "Fortsetzung 9/10").

    # PEB (reaction-diffusion) parameters.
    #
    # LITERATURE REFERENCE for peb_D: Lavery, K. A.; Choi, K.-W.; Vogt,
    # B. D.; Prabhu, V. M.; Lin, E. K.; Wu, W.; Satija, S. K.; Leeson,
    # M. J.; Cao, H. B.; Thompson, G.; Deng, H.; Fryer, D. S.
    # "Fundamentals of the Reaction-Diffusion Process in Model EUV
    # Photoresists." Proc. SPIE 6153, 615313 (2006) (NIST/Intel, neutron
    # reflectivity on a model EUV bilayer resist). Measured directly
    # (their Figs. 4b/5a, long-ranged front, 90-130 C PEB, 30 s):
    #   diffusion coefficient D ~= 2-8 x1e-14 cm^2/s = 2-8 nm^2/s
    #
    # LITERATURE REFERENCE for the diffusion LENGTH (sigma): Anderson,
    # C. N. "Extreme Ultraviolet Lithography: A Few More Pieces of the
    # Puzzle." PhD dissertation, UC Berkeley / LBNL (2009), freely hosted
    # at OSTI.gov (US DOE public-access mandate):
    # https://www.osti.gov/servlets/purl/961531 -- directly measured
    # deprotection blur (the same physical quantity as sigma_diff here)
    # for multiple REAL, NAMED, commercial EUV (13.5nm) CAR resists (TOK
    # EUVR P1123 across PEB 80-120C, and Rohm&Haas XP-5435/5271/5496,
    # EH-27 across PAG/base loading). Two independent measurement metrics
    # (contact-hole and corner), cross-validated, 1.2-1.75nm RMS error
    # bars. Measured blur spans 9.7-38.4nm; the unmodified/"Reference"
    # formulations (i.e. not artificially detuned for the study) cluster
    # around 17-35nm. This is a fully EUV-native measurement -- no
    # wavelength-transfer caveat, unlike dill_A/B's secondary corroborating
    # source above.
    #
    # peb_D default below (3.3 nm^2/s) is chosen so that, combined with
    # peb_t_bake=60s, it reproduces sigma=sqrt(2*D*t)~=20nm -- inside
    # both the Lavery D-range (2-8 nm^2/s) and the Anderson blur-range
    # (9.7-38.4nm, close to the "Reference" formulations' 17-35nm
    # cluster). peb_sigma_diff is now None by default so peb_D (the
    # quantity actually reported in the literature) is the parameter
    # that takes effect; set peb_sigma_diff explicitly only to bypass
    # peb_D/peb_t_bake with a directly-specified blur length (e.g. when
    # matching one specific measured resist from the Anderson table
    # above without recomputing D).
    #
    # BUG FIX (2026-09-02): previously peb_sigma_diff defaulted to 5.0
    # (a concrete float, not None), and reaction_diffusion_analytical()
    # always prefers sigma_diff over D+t_bake when sigma_diff is given
    # (see resist/peb.py) -- so peb_D/--peb-D was DEAD, silently ignored
    # by the pipeline regardless of what the user set it to. Same class
    # of bug as the earlier-fixed CLI --threshold dead-parameter issue.
    # Fixed by making peb_sigma_diff Optional (None default) and passing
    # D=cfg.peb_D through in run_simulation()'s _cd_via_full_chem() call.
    # Acid diffusivity [nm²/s]. 4.2 ± 0.3 nm²/s is the FT-IR bilayer measurement
    # of Kang et al. 2010 (Macromolecules 43, 4275, Table 2) for P(HOSt-co-tBA)
    # at 90 °C PEB -- the closest measured polymer class to the default resist
    # (PHS with 35 % acid-labile protection), independent of film thickness and
    # PAG loading (2/5 %). Caveat: the default PEB is 110 °C; Kang's Arrhenius
    # fit (ln A = 44 ± 8, Ea = 127 ± 25 kJ/mol) would put D(110 °C) near 60 nm²/s,
    # but ±25 kJ/mol is a factor ≈ 500, so the extrapolation is not used and
    # the 90 °C value stands with this caveat. Until 2026-09-05 the value was
    # 3.3, back-calculated so that D·60 s reproduced Anderson 2009's 19.9 nm
    # blur -- a reasoning that no longer holds now that the diffusion time is
    # the acid's effective lifetime (10.5 s): the default blur is
    # sqrt(2·D·t_eff) = 9.4 nm, inside the band of directly measured blur
    # lengths of named EUV CARs (7.5-12 nm: LBNL resist PSF, Langner 2010,
    # Thackeray 2010) without being fitted to it (log Fortsetzung 22).
    peb_D: float = 4.2
    # peb_k STATUS (2026-09-02): UNCITED. A real EUV-adjacent kinetics study
    # was found -- Prabhu, V. M. et al. (NIST), "Characterization of the
    # Photoacid Diffusion Length and Reaction Kinetics in EUV Photoresists
    # with IR Spectroscopy," Macromolecules 43(9), 4276 (2010), NIST
    # tsapps.nist.gov/publication/get_pdf.cfm?pub_id=904320 (free) -- Table 2
    # gives kP=0.51 nm^3/s for a model bilayer system at 90C PEB, in a
    # bimolecular rate law dphi/dt = kP*H*(1-phi) with H in nm^-3. This does
    # NOT translate directly into this codebase's k (used as a pseudo-
    # first-order rate against the dimensionless, already-normalised `acid`
    # from dose_to_acid): the correct mapping would be roughly k_equivalent =
    # kP * H0 (H0 = initial PAG density, ~0.013-0.026 nm^-3 in that paper),
    # giving k_equivalent ~= 0.007-0.013 s^-1 -- an order of magnitude SMALLER
    # than the current 0.3, which would make the CD=64nm degeneracy below
    # worse, not better. That NIST system is also a deliberately slow model
    # compound built for trackable IR kinetics, not a production EUV resist,
    # so its absolute rate is not necessarily representative anyway. Left
    # unchanged pending real calibration data; see the dill_Q and mack_M_th
    # notes for the fuller picture of why this can't be fixed in isolation.
    # peb_k UPDATE 2026-09-03 (round 9): Yamamoto et al. 2011 (see dill_A/B
    # note above) reports Arrhenius parameters for the deprotection reaction
    # at their own PEB condition (110°C/60s -- the same condition used for
    # the dissolution-rate table): "Thermal Decomp. Ea = 27.8 kJ/mol",
    # "Thermal Decomp. ln(Ar) = 6.1 /s" in Table 2. This would in principle
    # give a real, EUV-native k(T) = Ar*exp(-Ea/RT) -- BUT the paper's own
    # body text states essentially the same number with a DIFFERENT unit
    # ("activation energy of ca. 21.4-27.8 Kcal/mol for polymer A",
    # confirmed by re-rendering the actual PDF page at 300dpi to rule out an
    # OCR artifact -- the printed table really does say "kJ/mol" while the
    # printed body text really does say "Kcal/mol" for what appears to be
    # the same 27.8 figure). A kcal-vs-kJ mixup is a 4.184x error, which
    # would swing k(T) by many orders of magnitude in an Arrhenius
    # exponential -- far too large to guess at. NOT adopted: computing a
    # number from an internally inconsistent primary source and presenting
    # it as "real data" would be exactly the kind of ungrounded derivation
    # this project does not want. Left at the existing uncited 0.3 pending
    # either resolving the unit ambiguity (e.g. finding the underlying SPIE
    # 2009 conference paper by the same authors, which may not share the
    # apparent typo) or a fresh calibration.
    #
    # FOLLOW-UP (2026-09-03, same session, "was machen wir da jetzt?"): the
    # kJ/mol reading is the physically plausible one of the two -- computed
    # both at T=383.15K (110C, Yamamoto et al.'s own dissolution-rate/PROLITH
    # PEB condition): kJ/mol gives k=0.0723/s (a normal deprotection rate);
    # kcal/mol gives k=6.2e-14/s, which would mean no measurable deprotection
    # in 150s at any of the 80-140C conditions Yamamoto et al. themselves
    # report successfully fitting -- self-contradictory with their own
    # results, so this is now fairly strong internal evidence for "kJ/mol"
    # over "Kcal/mol" specifically (not proof; the source is still
    # internally inconsistent). Still NOT adopted as the default, because
    # k=0.0723 combined with dill_Q=0.5 (Mack et al. 2011's own baseline,
    # see dill_Q note above) gives cd_nm=64.0 -- just short of this
    # project's own empirically-found resolvable window (peb_k needs to
    # reach ~0.083 with dill_Q=0.5 fixed, or dill_Q needs to reach ~0.57
    # with peb_k=0.0723 fixed -- see dill_Q note for the fuller window).
    # Two independently-published real numbers landing just outside, rather
    # than wildly outside, the resolvable region is itself informative (the
    # model isn't nonsensical) -- and it turned out to be exactly that: a
    # limitation of the region being measured against, not of the numbers.
    #
    # RESOLVED (2026-09-03, "wire it in properly"): the "just outside"
    # result above was measured against the OLD, simplified full_chem chain
    # (2D-only, binary threshold_development). With dill_abc_exposure() and
    # the continuous MackModel/surface_advancement_level_set() now wired
    # into _cd_via_full_chem (see dill_A/B and mack_R_max notes), the SAME
    # k=0.0723 combined with dill_Q=0.5 gives cd_nm=36.5 (target
    # line_width_nm=32.0) -- a real, non-degenerate, dose-monotonic result.
    # ADOPTED as the new default for the same reason as dill_Q above: this
    # is Yamamoto et al. 2011's own real, cited Arrhenius-derived rate (kJ/mol
    # reading, see above), not a new or re-guessed number.
    # Deprotection rate constant [s⁻¹] at the default PEB (110 °C). 1.4 s⁻¹ is
    # Kdp of Yamamoto et al. 2011, Polymer A (35 % protection), read from the
    # Arrhenius plot of their FT-IR kinetics (Fig. 4, point at 1/T = 0.002616
    # K⁻¹ ≙ 109 °C; axis-calibrated reading, ±15 %). Until 2026-09-05 the
    # default was 0.0723 s⁻¹ from Table 2's Arrhenius pair (Ea = 27.8 "kJ/mol",
    # ln Ar = 6.1) -- PROLITH's translation, which reproduces neither the
    # paper's Fig. 3 deprotection curve nor its Fig. 5 dissolution threshold
    # (log Fortsetzung 15/20). With this Kdp AND the acid lifetime below, the
    # chain reproduces Fig. 3 at all five read points (≤ 0.08) and the
    # independent Fig. 5 threshold (0.75 vs ≈ 0.8 mJ/cm²), tests/
    # test_yamamoto_anchor.py. No fit to Fig. 5 was made.
    # UPDATE (2026-09-06, A2): 1.4 -> 7.87 s⁻¹ together with dill_C 0.090 ->
    # 0.0152. Fig. 3/4 determine the deprotection rate k*H at the flood dose
    # of 1.4 mJ/cm², i.e. k*H = 1.4 s⁻¹ * 0.1184 = 0.166 s⁻¹ (Yamamoto's "Kdp"
    # is normalised to HIS acid concentration, which his C = 0.090 puts at
    # H = 0.118). With the directly measured C the same dose gives H = 0.02105,
    # so the same measured rate is k = 0.166 / 0.02105 = 7.87 s⁻¹. No new
    # degree of freedom -- the same measurement, split differently. Chain
    # after the change: P(60 s) = 0.177 (Fig. 3: 0.18), threshold 0.764 mJ/cm²
    # (Fig. 5: ≈ 0.8), tests/test_yamamoto_anchor.py.
    # UPDATE (2026-09-06, C1, log Fortsetzung 37): 7.87 -> 10.95 s⁻¹ together with
    # tau 10.5 -> 7.54 s. Both now come from the fit of this chain's law to the
    # complete digitised 110 °C curve of Fig. 3 (≈ 106 points, rms 0.014)
    # instead of five hand-read points: k·H0 = 0.2305 s⁻¹, tau = 7.54 s, same
    # product k·H0·tau = 1.73 (P∞ 0.176, Fig. 5 threshold 0.766 -- unchanged),
    # shorter effective time (default PEB blur 9.4 -> 7.9 nm). Preflight:
    # dose-to-size P = 64 +0.2 %, P = 44 -4 %, photon LWR at P = 44 -6 %.
    # The same fits at 80-140 C are available through peb_temperature_c.
    peb_k: float = 10.947
    # PEB temperature [°C] (2026-09-06, plan stage C1). When set, peb_k and
    # peb_acid_lifetime_s are REPLACED by Yamamoto 2011 Polymer A's measured
    # kinetics at that temperature (resist/kinetics.py: per-temperature fits
    # of Fig. 3, 80-140 C, log-linear in 1/T, clamped with a warning). None
    # keeps the explicit peb_k / peb_acid_lifetime_s (the 110 C values).
    # peb_D is not temperature-scaled (Kang 2010: one temperature).
    peb_temperature_c: float | None = None
    # PEB model (2026-09-06, plan stage C2): "analytical" = diffuse-then-quench
    # closed form (resist/peb.reaction_diffusion_with_quenching; the goldens);
    # "reaction_diffusion" = concurrent diffusion, trapping by deprotected
    # sites, neutralisation and deprotection (Kang/NIST 2009 Eqs. 1-3,
    # resist/peb.reaction_diffusion_pde), validated on the NIST bilayer
    # diffusion lengths (tests/test_reaction_diffusion_pde.py). With the
    # latter, peb_acid_lifetime_s is not used; the acid loss is
    # peb_k_trap_per_s * h * phi, and peb_k should be the NIST-law value
    # (8.93 s^-1 at 110 C; peb_temperature_c sets both consistently).
    peb_model: str = "analytical"
    # Trapping rate constant [1/s] of the reaction_diffusion model at the
    # default 110 C PEB: fit of the Kang/NIST law to Yamamoto's Fig. 3 curve
    # (log Fortsetzung 38; NIST measure 0.026 at 90 C on a JSR resist, this
    # table gives 0.053 at 90 C for Polymer A).
    peb_k_trap_per_s: float = 0.2076
    # Quencher diffusivity [nm^2/s] for the reaction_diffusion model; None = same
    # as the acid (Osaka 2025 assumption; NIST do not fit it separately).
    peb_D_quencher: float | None = None
    # Average acid lifetime τ [s] during the PEB (first-order acid loss;
    # Yamamoto et al. 2011 Eq. 1 "τ", Kang et al. 2010 "trapping"). 10.5 s
    # follows from the Fig. 3 plateau at 110 °C: M∞ = exp(−Kdp·H0·τ) = 0.17
    # with k·H0 = 0.166 s⁻¹ (H0 = 1 − exp(−C·1.4 mJ/cm²), see peb_k). None = no
    # loss (the model before 2026-09-05). Deprotection, D·t diffusion length
    # and neutralisation use the effective time τ(1 − e^{−t/τ})
    # (resist.peb.effective_reaction_time). Consequence: the default resist
    # is a very sensitive 2011 research resist (dose-to-size ≈ 1.3 mJ/cm² at
    # 64 nm pitch, σ_PEB 7 nm) -- a property of the source, not a target.
    peb_acid_lifetime_s: float | None = (
        7.54  # 110 C full-curve fit (C1); was 10.5 (5-point reading)
    )
    peb_t_bake: float = 60.0  # Bake time [s]
    # Analytical diffusion sigma [nm], optional direct override of peb_D+peb_t_bake -- see
    # note above
    peb_sigma_diff: float | None = None

    # Mack development parameters.
    #
    # ORIGIN IDENTIFIED (2026-09-02, third research pass): Rmax=100 nm/s,
    # Rmin=0.1 nm/s, and Mth=0.5 below are an EXACT match, and n=5 a close
    # match, to the worked illustrative example in Chris Mack's own
    # canonical reference text:
    #   Mack, C. A. "Inside PROLITH: A Comprehensive Guide to Optical
    #   Lithography Simulation." FINLE Technologies, Austin, TX (1997),
    #   Ch. 7 ("Photoresist Development"), Fig. 7-1: "Development rate
    #   plot of the Original Mack model ... (rmax = 100 nm/s, rmin = 0.1
    #   nm/s, mTH = 0.5, and n = 2, 4, 8, and 16)"; Fig. 7-2 similarly
    #   uses rmax=100, rmin=0.1, and n=5 as one of its illustrated cases.
    #   Freely hosted by the author: https://lithoguru.com/scientist/litho_papers/Inside_PROLITH.pdf
    #   (read directly, not via search-summary; full 179-page book archived
    #   locally at references/literature/inside_prolith_mack_1997/).
    #
    # IMPORTANT CAVEAT (background, applies to mack_n/mack_M_th below, see
    # UPDATE for mack_R_max/mack_R_min): the "Inside PROLITH" values are a
    # GENERIC TEXTBOOK ILLUSTRATION Mack chose to demonstrate the *shape*
    # of the Original/Enhanced Mack model as n is varied -- not fit to any
    # measured photoresist, EUV or otherwise. Traceable to a well-known,
    # authoritative source (not an arbitrary guess), but NOT evidence of
    # being physically representative of a real EUV CAR resist.
    #
    # UPDATE (2026-09-03, PROVISIONAL -- see status below): mack_R_max and
    # mack_R_min replaced with EUV-native values from a real measurement.
    # Vesters, Y.; De Simone, D.; De Gendt, S. "Dissolution Rate Monitor
    # Tool to Measure EUV Photoresist Dissolution." J. Photopolym. Sci.
    # Technol. 30(6), 675-681 (2017), free via J-STAGE:
    # https://www.jstage.jst.go.jp/article/photopolymer/30/6/30_675/_pdf
    # Fig. 6 plots a dissolution contrast curve for two REAL, ASML
    # NXE-scanner-designated EUV (13.5nm) resists (NXE1716 = high
    # quencher loading, NXE1717 = low quencher loading), explicitly
    # captioned "Data is fitted using original Mack model." No numeric
    # table is given, only the plot -- values below were extracted by
    # rendering the page at 400dpi, calibrating the pixel-to-value mapping
    # against the axis gridlines (log-scale, verified self-consistent to
    # <0.5px across multiple independent decades on both axes), and
    # locating the actual data-marker pixel centroids at the lowest- and
    # highest-dose measured points (NOT the fitted curve, and NOT
    # extrapolated to dose=0/infinity -- see raw per-resist values below).
    # Cross-checked against the paper's own text ("both Rmin and Rmax for
    # the high quencher resist are higher than for the lower quencher
    # resist") -- the extracted numbers confirm this in both directions.
    #   NXE1716 (high Q): ~0.017 nm/s (at 1.0 mJ/cm^2) to ~241 nm/s (at 25.4 mJ/cm^2)
    #   NXE1717 (low Q):  ~0.012 nm/s (at 1.0 mJ/cm^2) to ~174 nm/s (at 25.1 mJ/cm^2)
    # Defaults below use the geometric mean of the two resists (a
    # defensible way to combine two distinct real measurements into one
    # default without arbitrarily preferring one formulation), NOT a new
    # number invented to "look reasonable": Rmax = sqrt(241*174) = 205
    # nm/s, Rmin = sqrt(0.017*0.012) = 0.0143 nm/s.
    #
    # STATUS -- READ BEFORE TRUSTING THESE NUMBERS: an email was sent
    # 2026-09-03 to the corresponding author (Danilo De Simone, imec,
    # danilo.desimone@imec.be) asking for the actual fitted Rmax/Rmin/n/
    # Mth table behind Fig. 6, since a graph reading -- however carefully
    # pixel-calibrated -- is still a reconstruction, not the authors' own
    # number. THESE VALUES ARE PROVISIONAL pending that reply (or
    # independent confirmation). If/when a reply arrives: replace the
    # values below with the authors' real numbers, update this comment
    # and docs/claude_code_arbeitslog.md accordingly, and remove this
    # provisional-status paragraph. Do not let this note go stale --
    # if you are reading this long after 2026-09, either the reply
    # arrived and this should already be resolved, or it didn't and that
    # is itself worth telling the user rather than silently trusting a
    # months-old "pending" label.
    #
    # SEPARATE, ALREADY-KNOWN ISSUE -- these parameters currently have
    # ZERO EFFECT ON SIMULATION OUTPUT: mack_R_max/mack_R_min/mack_n are
    # only used for __post_init__ bounds validation below; the actual
    # full_chem development step (_cd_via_full_chem in this file) calls
    # threshold_development(inhib, threshold=cfg.mack_M_th) -- a binary
    # threshold, not the continuous Mack R(M) rate equation. The MackModel
    # class implementing that equation exists (resist/develop.py) but is
    # never instantiated in the actual pipeline. So updating Rmax/Rmin
    # here is a documentation/readiness improvement for when that class
    # gets wired in (a separate, larger task -- see project status memory
    # / docs/claude_code_arbeitslog.md), NOT a change to current
    # simulation behavior, and does NOT touch the CD=64nm degeneracy
    # documented below at mack_M_th (that issue is about the PEB/
    # threshold step, not about these development-rate parameters).
    #
    # UPDATE 2 (2026-09-03, round 9 -- GitHub/code-repo + conference-archive
    # search, triggered by the user explicitly rejecting "search but don't
    # verify" and demanding every proposed avenue actually be searched):
    # found a SECOND, INDEPENDENT, EUV-native Rmax/Rmin source, and the
    # first EUV-native source for mack_n found in this entire project.
    # Itani, T.; Kaneyama, K.; Kozawa, T.; Tagawa, S. "Dissolution
    # characteristics of chemically amplified EUV resist," Selete / Osaka
    # University, EIPBN 2008 conference paper, freely hosted:
    # https://eipbn.org/abstracts/2008/papers/P-6B-12.pdf
    # (fetched and read directly -- not a search-summary claim). Real EUV
    # exposure (Energetiq EQ-10MR EUV source), real 2.38wt% TMAH
    # development, dissolution rate measured with a Litho-tech Japan RDA
    # (resist development analyzer) instrument -- not a graph reading,
    # this is the authors' own Table 1, verbatim:
    #   PHS resist:       Rmax = 8.5e1 nm/s (85),    Rmin = 1.7e-3 nm/s, slope m = 2.5
    #   Molecular resist: Rmax = 9.3e1 nm/s (93),    Rmin = 1.0e-1 nm/s, slope m = 7.0
    # ("slope m" is Selete's label for the Mack contrast/selectivity
    # exponent -- the same role as "n" in the Original Mack model used
    # elsewhere in this file.) PHS = polyhydroxystyrene, the standard
    # polymer backbone of mainstream chemically-amplified positive
    # resists (the closer analogue to a generic commercial CAR); the
    # "molecular resist" is a distinct, smaller-molecule resist class,
    # kept separate below rather than averaged with PHS since they are
    # different chemistries (unlike Vesters' NXE1716/1717, which are the
    # same resist family at two quencher loadings and so were legitimately
    # averaged).
    # CROSS-VALIDATION: both Rmax values (85, 93 nm/s) and both Rmin
    # values (0.0017, 0.1 nm/s) sit within the same order of magnitude as
    # the independently-derived Vesters et al. 2017 values above (Rmax
    # 174-241 nm/s, Rmin 0.012-0.017 nm/s) -- two unrelated EUV
    # measurements, 9 years apart, different institutions (Selete/Osaka
    # vs. imec/KU Leuven), different instruments, agreeing on the
    # magnitude of both plateaus. This does not replace the Vesters-based
    # Rmax/Rmin defaults (NXE1716/1717 are named, production-representative
    # ASML resists -- a closer match to "a real commercial EUV CAR" than
    # Selete's generic PHS/molecular classes), but it substantially
    # de-risks them: the PROVISIONAL flag above is about awaiting De
    # Simone's own fitted numbers for THIS SPECIFIC curve, not about
    # whether the values are physically plausible for an EUV resist --
    # that plausibility now has independent, cited support.
    # mack_n IS updated below, from Mack's generic "Inside PROLITH"
    # illustration to the real, EUV-measured PHS-resist value (2.5) --
    # this is the first non-illustrative, EUV-native n found. Judgment
    # call: PHS (mainstream CAR backbone) chosen over "molecular resist"
    # (7.0, a different, non-mainstream chemistry) as the more
    # representative default; flagged as PROVISIONAL for the same reason
    # as Rmax/Rmin (a single 2008 conference-abstract table, not a
    # multiply-confirmed value) -- update if a better EUV-native n
    # surfaces (e.g. if De Simone's reply includes one for NXE1716/1717).
    #
    # UPDATE 3 (2026-09-03, round 9 continued -- "dann los", user explicitly
    # asked to keep pursuing a specific paywalled lead's free-access options):
    # while chasing a paywalled SPIE 2009 paper by Yamamoto/Kozawa/Tagawa
    # (Osaka University) + Mimura/Iwai/Onodera (Tokyo Ohka Kogyo), found its
    # freely-accessible open-journal counterpart instead -- see the dill_A/B
    # note above for the full citation (J. Photopolym. Sci. Technol. 24(4),
    # 405-410, 2011, free via J-STAGE). This is the SINGLE MOST COMPLETE
    # EUV-native source found in this entire project: Table 2 gives Rmax,
    # Rmin, Mth, AND n -- the full Mack quadruplet -- fit TOGETHER with
    # dill_A/B/C from ONE real EUV-exposed resist ("Polymer A"), explicitly
    # for use as PROLITH calculation parameters (PROLITH's native resist
    # model is the Original Mack model used throughout this file):
    #   Development Rmax = 68.6 nm/s
    #   Development Rmin = 0.10 nm/s
    #   Development Mth  = 0.39
    #   Development n    = 18.2
    # Verified by reading the actual paper (not a search summary) and by
    # rendering the table's page at 300dpi to rule out OCR errors on every
    # number (see the peb_k note above for the one place that check found a
    # real problem -- the PEB Arrhenius parameters, NOT this table).
    # SUPERSEDES the two provisional sources above as the adopted default:
    # Vesters et al. 2017 (Rmax/Rmin only, pixel-read off a graph, no Mth/n)
    # and Itani et al. 2008 (Rmax/Rmin/n only, no Mth, two different generic
    # resist classes, not fit jointly with any Dill parameters). Both are
    # kept in the comments above/below as independent order-of-magnitude
    # cross-checks, not discarded -- they still matter for judging whether
    # this new set is physically reasonable:
    #   Rmax 68.6 nm/s: between Itani's PHS value (85) and same order as
    #     Vesters' pair (174-241) -- consistent.
    #   Rmin 0.10 nm/s: matches Itani's molecular-resist value (0.1)
    #     exactly, within the Vesters range order of magnitude (0.012-0.017)
    #     -- consistent.
    #   n 18.2: notably higher than Itani's PHS value (2.5) or Mack's own
    #     illustrative 5 -- a much steeper/sharper threshold response. Not
    #     contradicted by anything else found (no other real EUV n to
    #     compare against besides Itani's), but flagged here as the one
    #     number in this set furthest from prior expectation; if a future
    #     source disagrees sharply on n specifically, treat that as the
    #     more likely candidate for revision, not Rmax/Rmin/Mth/dill_A/B/C.
    #   Mth 0.39: the single biggest gap this project has had all along --
    #     first real, cited EUV-native value found for this parameter at
    #     all (Mack's own 0.5 was always a generic textbook illustration).
    # STILL NOT FULLY CONFIRMED (hence STATUS below, same posture as the
    # superseded Vesters PROVISIONAL flag): "Polymer A" is TOK-affiliated
    # real industrial CAR chemistry, not a named commercial product like
    # Vesters' NXE1716/1717, and this is one paper/one measurement campaign,
    # not yet independently multiply-confirmed for the Mth/n pair
    # specifically. Tested experimentally (2026-09-03): swapping in this
    # full set (dill_A/B/C + mack_M_th together) does NOT change the
    # pre-existing full_chem CD=64.0nm degeneracy documented below --
    # verified by direct SimulationConfig()/run_simulation() calls before
    # committing this change, not assumed. This is expected (the
    # degeneracy's root cause is peb_k/dill_Q, not dill_C/mack_M_th, per the
    # quantified analysis below) and means adopting these values is safe:
    # it does not silently change any already-reported simulation result.
    # Max development rate [nm/s] -- Yamamoto et al. 2011 (EUV-native, self-consistent with
    # dill_A/B/C and mack_R_min/Mth/n); cross-validated in order of magnitude by Vesters et al. 2017
    # (174-241 nm/s) and Itani et al. 2008 (85-93 nm/s). Wired into the level-set development front
    # via MackModel/surface_advancement_level_set since round 9's CD=64nm degeneracy fix (see note
    # below) -- DOES affect simulation output (verified: mack_R_max=68.6/10/200 ->
    # CD=36.5/64.0/29.5nm at defaults); an earlier version of this comment ("currently has no
    # effect") predated that wiring and was stale, corrected 2026-09-04
    mack_R_max: float = 68.6
    # Min development rate [nm/s] -- Yamamoto et al. 2011 (EUV-native, self-consistent with
    # dill_A/B/C and mack_R_max/Mth/n); matches Itani et al. 2008's molecular-resist value (0.1)
    # exactly, within Vesters et al. 2017's order of magnitude (0.012-0.017). DOES affect simulation
    # output (verified: mack_R_min=0.10/1.0/5.0 -> CD=36.5/30.5/0.0nm at defaults); see mack_R_max
    # comment above for why an older "no effect" claim here was stale and has been corrected
    mack_R_min: float = 0.10
    # PRIMARY-SOURCE RE-VERIFICATION (2026-09-04, scientific-development mandate
    # Phase 3): re-fetched Yamamoto et al. 2011 directly from J-STAGE (open
    # access, https://www.jstage.jst.go.jp/article/photopolymer/24/4/24_4_405/_pdf)
    # and re-read Table 2 ("Calculation parameters of Polymer A on PROLITH",
    # p.409) myself, independent of the prior session's catalog entry --
    # n=18.2 is confirmed correct, exactly as printed there, alongside all six
    # other Table 2 values this file adopts. IMPORTANT CAVEAT found while doing
    # this: the paper itself never writes out the Mack rate equation or defines
    # how its "a" parameter relates to n/M_th -- Table 2 is presented purely as
    # "parameters fed into PROLITH", assuming the reader already knows
    # PROLITH's (i.e. Mack's own) standard formula. Verified this codebase's
    # own MackModel.rate() (resist/develop.py) uses that same standard,
    # textbook form -- a = (n+1)/(n-1)*(1-M_th)^n, R(M) = R_max*(a+1)*(1-M)^n /
    # (a+(1-M)^n) + R_min -- so the n=18.2 read from this table is being used
    # in the same mathematical context PROLITH itself would use it in, not
    # silently reinterpreted under a different "a" convention.
    #
    # Quantified consequence of n=18.2 (not previously computed, only
    # qualitatively described as "notably steeper" before this check): with
    # M_th=0.39, a = (n+1)/(n-1)*(1-M_th)^n = 1.38e-4 -- an extremely small
    # value, meaning R(M) transitions from 10% to 90% of R_max over just
    # ΔM ≈ 0.14 (M=0.31 to M=0.45). This -- not a numerical artefact or
    # mis-transcription -- is the direct, mathematically inevitable root cause
    # of the extreme CD-vs-dose/CD-vs-parameter sensitivity documented
    # elsewhere in this file and in docs/claude_code_arbeitslog.md (e.g. a
    # 0.1 mJ/cm^2 dose step or the uncited se_blur_nm value alone shifting CD
    # by 5+ nm near the resist's resolution edge): a small shift in the
    # depth-resolved, time-integrated M(t) field near M_th gets amplified by
    # this near-step-function rate response. Independently corroborated by
    # the paper's own Figure 6/text: at 26nm film thickness Polymer A shows
    # "considerable bridge of pattern side walls" (i.e. a narrow, finicky
    # process window even in the original 2011 measurement), vs. "almost
    # vertical" profiles only at the 50nm thickness this codebase's own
    # resist_thickness_nm default already uses.
    #
    # Conclusion: KEPT UNCHANGED. This is a correctly-sourced, correctly-used
    # real value; the sensitivity it produces is a genuine property of this
    # specific resist's contrast, not a bug to fix or a number to adjust.
    # Dissolution selectivity (contrast) -- Yamamoto et al. 2011 (EUV-native, self-consistent with
    # dill_A/B/C and mack_R_max/R_min/Mth); notably steeper than Itani et al. 2008's PHS value (2.5)
    # or Mack's generic textbook 5 -- flagged, not silently trusted. DOES affect simulation output
    # (verified: mack_n=18.2/5.0/40.0 -> CD=36.5/0.0/60.0nm at defaults); see mack_R_max comment
    # above for why an older "no effect" claim here was stale and has been corrected; see the
    # primary-source re-verification note directly above for the quantified reason this value makes
    # CD so sensitive
    mack_n: float = 18.2
    # Threshold inhibitor concentration -- Yamamoto et al. 2011 (EUV-native, self-consistent with
    # dill_A/B/C and mack_R_max/R_min/n); first real EUV-native value found for this parameter
    # (previously Mack's own generic textbook illustration, 0.5); used by the full_chem development
    # step
    mack_M_th: float = 0.39

    # Depth-resolved exposure/development parameters (2026-09-03, round 9 --
    # added when wiring dill_abc_exposure()/MackModel into the full_chem
    # pipeline for the first time; see resist_model docstring/note below).
    # Both defaults are read directly from the SAME Yamamoto et al. 2011
    # source as dill_A/B/C and mack_R_max/R_min/Mth/n above (see dill_A/B
    # comment for the full citation), so the depth-resolved chain stays
    # internally self-consistent rather than mixing in a new, independently
    # sourced number:
    #   resist_thickness_nm: the paper's own PROLITH simulation used two
    #   film-thickness cases (26nm and 50nm) for Polymer A; 50nm is the one
    #   they report giving "an almost vertical" (i.e. well-resolved) profile
    #   -- 26nm showed "considerable bridge of pattern side walls," their
    #   own words for a failure mode, so 50nm is the physically-appropriate
    #   case to default to, not an arbitrary pick between the two.
    #   develop_time_s: the paper's own dissolution-rate measurement
    #   (Sec. 2, the same measurement Table 2's Rmax/Rmin/Mth/n are fit
    #   from) developed in NMD-3 (2.38% TMAH) for 30s at 23C.
    # Resist film thickness [nm] -- Yamamoto et al. 2011's own better-resolved PROLITH case (26nm
    # showed sidewall bridging in their own results); see note above
    resist_thickness_nm: float = 50.0
    # Development time [s] -- Yamamoto et al. 2011's own dissolution-rate measurement condition
    # (NMD-3, 2.38% TMAH, 23C), self-consistent with mack_R_max/R_min/Mth/n above; see note above
    develop_time_s: float = 30.0
    # Development front model (2026-09-04). "eikonal": the dissolution front is
    # an isotropic wave with local speed R(M); its first-arrival time obeys
    # |∇T| = 1/R with T = 0 on the top surface (fast sweeping, Zhao 2005) --
    # lateral dissolution, undercut and sidewall angle are represented
    # (resist/develop.py::eikonal_development, validated against exact
    # solutions in tests/test_eikonal_development.py). "column": the former
    # vertical-column time-of-flight, T = Σ dz/R down each column, no lateral
    # dissolution -- kept as the fast approximation and as the limit the
    # Eikonal solver reduces to without lateral rate variation. The column
    # model artificially keeps lines alive that lateral development would
    # erode (Fortsetzung 14): it is NOT a physical development model.
    # "eikonal" (per-row (x, z) first arrival, Zhao 2005 fast sweeping), "eikonal3d"
    # (rows coupled by a y-term, B3.4 2026-09-06 -- use with development_stochasticity),
    # "column" (time-integrated per column, no lateral development)
    development_model: str = "eikonal"
    # Number of depth layers for the resolved exposure/PEB/development chain -- a NUMERICAL
    # resolution choice, not a physical parameter; matches this codebase's own n_rcwa_orders
    # convention, not independently cited
    n_develop_layers: int = 21

    # ─────────────────────────────────────────────────────────────────
    # RESOLVED (2026-09-03, round 9): `full_chem`'s CD=64.0nm degeneracy.
    # History kept below for the record -- this was a real, hard-won
    # multi-stage finding, not obvious in hindsight.
    #
    # ORIGINAL ISSUE (root-caused 2026-09-02): with all parameters at their
    # then-current defaults, `resist_model="full_chem"` produced cd_nm ==
    # 64.0 (the entire field "undeveloped"). Root cause, quantified: the
    # OLD chain used a flat cutoff, M_t = exp(-peb_k*acid*peb_t_bake), only
    # "developed" where M_t <= mack_M_th; at the original defaults this
    # threshold was never crossed (short by roughly 2x in the required
    # peb_k*acid_max*peb_t_bake product).
    #
    # THE FIX HAD TWO INDEPENDENT PARTS, both completed in this round:
    #
    # (1) REAL DATA for every resist-chemistry parameter. Yamamoto et al.
    #     2011 (J. Photopolym. Sci. Technol. 24(4), 405-410, free via
    #     J-STAGE -- see dill_A/B and mack_R_max notes above) supplied a
    #     complete, self-consistent, EUV-native Dill A/B/C + Mack
    #     Rmax/Rmin/Mth/n septuplet from one real measured resist -- found
    #     via a 9-round, ~39-source search (institutional repositories,
    #     government archives, conference archives back to 2008, code/data
    #     repositories, author-centric/citation-trail follow-ups; see
    #     $HOME/mack fits/catalog.md and docs/claude_code_arbeitslog.md
    #     for the full trail). dill_Q and peb_k needed a separate,
    #     mechanistic investigation (see their own notes above): dill_Q
    #     corresponds to Mack's phi_PAG, a fundamentally different quantity
    #     from the "quantum yield"/FQY the EUV-resist literature actually
    #     publishes (which is why naive literature search for dill_Q could
    #     never succeed), with only one real candidate value found anywhere
    #     (Mack et al. 2011's own baseline, 0.5); peb_k's only real
    #     candidate was Yamamoto et al. 2011's own Arrhenius fit (0.0723,
    #     after resolving a kcal/kJ ambiguity in the source).
    #
    # (2) THE MODEL ITSELF was the other half of the problem, not just the
    #     numbers. Testing dill_Q=0.5/peb_k=0.0723 against the OLD 2D-only,
    #     flat-threshold chain gave cd_nm==64.0 (short by ~13% in the
    #     required product) or cd_nm==0.0 (overshoot) depending on which
    #     parameter was swept -- close, but never a resolved line, for
    #     EITHER real candidate value. Wiring in the two previously-inert
    #     capabilities that already existed in this codebase --
    #     dill_abc_exposure() (real depth-resolved Beer-Lambert absorption,
    #     making dill_A/B finally load-bearing; see dill_A/B "ARCHITECTURE
    #     GAP" note above) and MackModel/surface_advancement_level_set()
    #     (the continuous, time-integrated Mack R(M) rate equation,
    #     replacing the flat M_th cutoff; see mack_R_max "SEPARATE,
    #     ALREADY-KNOWN ISSUE" note above) -- changed the answer: the SAME
    #     dill_Q=0.5, peb_k=0.0723 now give cd_nm=36.5 at the default dose
    #     (target line_width_nm=32.0), confirmed dose-monotonic (15->30
    #     mJ/cm2 gives 64.0->13.0nm smoothly) and with a physically sane
    #     43% developed-area fraction -- not a numerical fluke.
    #
    # CONCLUSION: the "two real numbers land just outside the resolvable
    # region" finding from earlier in this round was not evidence that
    # dill_Q/peb_k needed different values -- it was evidence that the
    # SIMPLIFIED chain being tested against was itself the limitation.
    # `full_chem` is now driven by real, cited, EUV-native values for
    # every one of dill_A/B/C/Q, peb_D/k/t_bake, and mack_R_max/R_min/
    # Mth/n, running through the physically complete depth-resolved
    # exposure/PEB/development chain, producing a non-degenerate,
    # dose-monotonic CD. Two gaps remain, both explicitly non-blocking:
    # (a) none of the resist-chemistry values are yet independently
    # confirmed by more than one source at the exact-number level (several
    # are cross-validated in ORDER OF MAGNITUDE by a second source, see
    # each parameter's own comment) -- real experimental dose/CD
    # calibration data via `euv calibrate`, when available, remains the
    # way to tighten this further; (b) the stochastic LER/LWR path is
    # intentionally NOT yet updated to use the same depth-resolved/
    # continuous-Mack chain (see _cd_via_full_chem's own docstring) --
    # a distinct, separate follow-up.
    # ─────────────────────────────────────────────────────────────────

    # Stochastic / Shot Noise parameters
    enable_stochastic: bool = False  # Enable photon shot noise + LER/LWR
    stochastic_n_realisations: int = 1  # Number of independent noise realisations
    # REMOVED (2026-09-03, round 9, stochastic path wired to MackModel): both
    # stochastic_develop_threshold and stochastic_quantum_efficiency were
    # dead-parameter-adjacent -- the latter (an "acid molecules per absorbed
    # photon" duplicate of dill_Q) was never read anywhere in the simulation
    # at all (same bug class as the dill_A/B/mack_R_max gaps found earlier
    # this round); the former drove a standalone binary threshold on raw
    # acid concentration with no PEB step, now superseded by the same
    # resist_thickness_nm/develop_time_s/mack_M_th-driven MackModel chain
    # the deterministic CD path uses (see _cd_via_full_chem's stochastic
    # block). Removed rather than left as unused API surface, consistent
    # with how this round has treated every other dead-parameter finding.
    stochastic_seed: int | None = None  # RNG seed (None = random)
    # Correlation-aware large-N LER (STEP 5.1/5.2B)
    #
    # REFERENCE CONFIGURATION FOR SCIENTIFIC LER VALIDATION:
    #   se_blur_nm               = 5.0
    #   dose_mj_cm2              = 40.0
    #   stochastic_ler_grid_y    = 4096
    #   stochastic_ler_estimator = "large_n"
    #
    # Note: se_blur_nm=0.0 (the default until 2026-09-06) is white per-pixel
    # noise -> N_eff = N, grid-dependent and, through the Dill saturation,
    # physically wrong for the full_chem chain (see se_blur_nm); it warns.
    # The reference configuration was used for the internal LER audits
    # (N_eff ~= 59, LER ~= 0.07 nm at 40 mJ/cm2); it is a reference for
    # internal scientific validation, NOT yet experimentally validated.
    stochastic_ler_grid_y: int = 4096  # Requested Y dimension of the stochastic LER field
    stochastic_ler_estimator: str = "large_n"  # "large_n" | "legacy"
    # Metrology passband (p_min, p_max) [nm] applied to the edge/width profiles
    # before the roughness statistics (resist/stochastic.bandlimit_along_rows);
    # None = full simulated band (default, goldens). Anchors carry their
    # source's band: Anderson & Naulleau 2008 (10, 834); imec biased CD-SEM
    # protocol, Vesters 2019 Sec. 5.3 (10.8, 5500). Log Fortsetzung 36.
    ler_passband_nm: tuple[float, float] | None = None
    # development_stochasticity -- history: the former event-based model
    # (resist/develop.py::stochastic_development, still a standalone function)
    # was disabled 2026-09-04 (audit A6) because its output depended on the
    # numerical layer count and its "strength" was a fitted, unit-less knob.
    # Since 2026-09-06 (plan stage B3, log Fortsetzung 32/33) True enables the
    # derived model resist/develop.py::dissolution_cell_noise: the development
    # rate of each dissolution cell fluctuates with the Poisson statistics of
    # the blocked polymer units it contains (Mack 2010 "Ultimate limits" Eq. 36
    # -> Mack 2010 "Stochastic development" KPZ roughening). Its only physical
    # parameter is blocked_site_density_per_nm3; dissolution_cell_nm is a
    # discretisation length (noise power per volume is cell-size independent,
    # tests/test_dissolution_cell_noise.py). Applies to the stochastic chain
    # only (the deterministic chain is the mean field). Preflight at the MET-2D
    # anchor: photon+PAG LER 1.97 -> 3.5-3.6 nm 3sigma, i.e. a ~3 nm floor.
    development_stochasticity: bool = False
    blocked_site_density_per_nm3: float = DEFAULT_BLOCKED_SITE_DENSITY_PER_NM3
    # Dissolution cell edge [nm] for the noise above; 4.3 nm = polymer radius of
    # gyration of Thackeray et al. 2010 (JPST 23(5) 631), a physical anchor for
    # the size of the unit that dissolves as a whole.
    dissolution_cell_nm: float = 4.3

    # PAG / quencher / acid-base quenching -- ONE chemistry for both chains.
    #
    # The deterministic (mean-field) full_chem chain and the sampled-molecule
    # chain (exposure_stochasticity=True) run the SAME PEB step,
    # resist/peb.py::reaction_diffusion_with_quenching: acid and quencher
    # diffuse, then neutralise (reaction-limited closed form, Mack, Biafore &
    # Smith 2011, Proc. SPIE 7972, Eq. 15), then deprotection. The only
    # difference is where the initial fields come from -- the mean field
    # h0 = 1 − exp(−C·E), q0 = ρ_Q/ρ_PAG, or a Poisson/Binomial sample of the
    # molecule counts per voxel (resist/exposure.py::sample_pag_quencher_acid).
    # Hence the deterministic result is the large-number limit of the
    # stochastic one (tests/test_stochastic_consistency.py); before
    # 2026-09-04 the deterministic chain had no quencher at all while the
    # stochastic chain applied one per grid voxel where it was effectively
    # inert (docs/audit_2026-09-04_vollpruefung.md, A4).
    #
    # exposure_stochasticity=True adds the counting statistics of a FINITE
    # PAG/quencher population (a noise source distinct from photon shot
    # noise, which is always on with enable_stochastic=True). Opt-in.
    #
    # PARAMETER CLASSES (material properties of ONE resist formulation):
    #  - pag_density_per_nm3 = 0.2: Mack et al. 2011 Table I baseline
    #    ("Baseline stochastic resist parameters for EUV simulations").
    #    Order-of-magnitude check against this codebase's development/
    #    exposure source: Yamamoto et al. 2011 used 3.1 mol% PAG in a
    #    methacrylate resist (~4.8 monomer units/nm³ at ~1.2 g/cm³, MW~150)
    #    → ≈0.15 nm⁻³, consistent.
    #  - acid_base_quench_rate_nm3_per_s = 15: same table; converted to
    #    k_Q·G0 = 3 s⁻¹ inside the PEB step (Mack 2011, stated explicitly).
    #  - quencher_density_per_nm3: DEFAULT 0.0. The Dill/PEB/Mack parameters
    #    of this codebase are Yamamoto et al. 2011's PROLITH set (Table 2:
    #    Rmax/Rmin/Mth/n, Ea/ln(Ar), A/B/C) -- that table contains NO quencher
    #    or base loading, so a quencher-free chemistry is the only one
    #    consistent with those parameters. Loading Mack 2011's 0.05 nm⁻³
    #    (q0/h0-ratio 0.25) on top -- the pre-2026-09-04 default -- is a
    #    combination with no source and a measured consequence: dose-to-size
    #    of the 22 nm line at 44 nm pitch moves from 6.6 to 21.2 mJ/cm²
    #    (preflight_phase1_quench.py), i.e. the base is then the dominant
    #    unmodelled-by-any-source parameter of the whole chain. A user with a
    #    self-consistent set (Mack 2011's own exposure C = 0.08652 cm²/mJ with
    #    its densities) can set it explicitly; the physics path is complete.
    #    No freely available single source with exposure + PEB + quenching +
    #    development parameters for one real resist was found (see
    #    docs/claude_code_arbeitslog.md "Fortsetzung 7").
    # ON = sample discrete PAG/quencher populations instead of mean-field acid; see note above
    exposure_stochasticity: bool = False
    # Initial PAG number density [nm^-3] -- Mack, Biafore & Smith 2011 Table I; see note above
    pag_density_per_nm3: float = 0.2
    # Initial quencher (base) number density [nm^-3]; 0 = the quencher-free chemistry of the
    # Yamamoto 2011 parameter set -- see note above (Mack 2011 Table I would be 0.05)
    quencher_density_per_nm3: float = 0.0
    # Acid-base quenching rate constant k_Q [nm^3/s]. UPDATE 2026-09-06 (C2, log
    # Fortsetzung 38): 15 -> 1.2. Mack 2011's 15 nm^3/s (Table I) is a model
    # assumption, as is Osaka 2025's 12.6 (0.5 nm radius); the only
    # measurement-based value comes from the NIST bilayer diffusion lengths
    # (Kang et al. 2009, Table 2: 76/56/36/23 nm): with their own kinetics
    # (kP 1.6, kT 0.026, DH 4.2) the concurrent reaction-diffusion model
    # reproduces the two quencher-in-target-layer cases only for k_Q ~ 1.0-1.5
    # (tests/test_reaction_diffusion_pde.py); 12.6-15 gives 11/4 nm. With
    # 1.2 the neutralisation during a 60 s PEB is NOT complete
    # (k_Q*G0*t ~ 1.8 at G0 = 0.2), which the analytical closed form handles.
    acid_base_quench_rate_nm3_per_s: float = 1.2

    # Mask-3D / RCWA parameters (Phase 4)
    use_rcwa: bool = False  # Use full RCWA instead of thin-mask analytic
    absorber_taper_deg: float = 90.0  # Sidewall angle from horizontal (90 = vertical)
    mask_undercut_nm: float = 0.0  # Undercut at absorber base [nm]
    # (mask_sidewall_roughness_nm removed 2026-09-04: it was accepted by the
    # config and the CLI but never read by any model.)

    def __post_init__(self):
        # Validate dose
        if self.dose_mj_cm2 <= 0:
            raise ValueError(f"dose_mj_cm2 must be > 0, got {self.dose_mj_cm2}")
        # Validate resist parameters
        if self.dill_C <= 0:
            raise ValueError("dill_C must be > 0")
        if self.peb_k <= 0:
            raise ValueError("peb_k must be > 0")
        if self.peb_acid_lifetime_s is not None and self.peb_acid_lifetime_s <= 0:
            raise ValueError("peb_acid_lifetime_s must be > 0 or None")
        if self.peb_temperature_c is not None:
            from euvsimulator.resist.kinetics import yamamoto_polymer_a_kinetics

            if not (80.0 <= self.peb_temperature_c <= 140.0):
                warnings.warn(
                    f"peb_temperature_c = {self.peb_temperature_c} is outside the measured "
                    "80-140 C of Yamamoto 2011 Fig. 3; kinetics clamped to the nearest end.",
                    stacklevel=2,
                )
            k, tau = yamamoto_polymer_a_kinetics(self.peb_temperature_c, self.dill_C)
            self.peb_k = k
            self.peb_acid_lifetime_s = tau
            if self.peb_model == "reaction_diffusion":
                from euvsimulator.resist.kinetics import yamamoto_polymer_a_kinetics_nist_law

                self.peb_k, self.peb_k_trap_per_s = yamamoto_polymer_a_kinetics_nist_law(
                    self.peb_temperature_c, self.dill_C
                )
        if self.peb_model not in ("analytical", "reaction_diffusion"):
            raise ValueError(
                f"peb_model must be 'analytical' or 'reaction_diffusion', got {self.peb_model!r}"
            )
        if self.peb_k_trap_per_s < 0:
            raise ValueError("peb_k_trap_per_s must be >= 0")
        if self.se_blur_nm < 0:
            raise ValueError("se_blur_nm must be >= 0")
        if self.enable_stochastic and self.resist_model == "full_chem" and self.se_blur_nm == 0:
            warnings.warn(
                "se_blur_nm = 0 with enable_stochastic: photon shot noise is then white per "
                "grid pixel (grid-dependent) and single-photon spikes saturate the Dill law; "
                "use the SE-PSF (default 2.5 nm, Thackeray 2010).",
                stacklevel=2,
            )
        if self.peb_t_bake <= 0:
            raise ValueError("peb_t_bake must be > 0")
        if self.mack_R_max <= self.mack_R_min:
            raise ValueError("mack_R_max must be > mack_R_min")
        if self.mack_n <= 1:
            raise ValueError("mack_n must be > 1")
        if not (0 < self.mack_M_th < 1):
            raise ValueError("mack_M_th must be in (0, 1)")
        # Validate stochastic parameters
        if self.enable_stochastic:
            if self.resist_model != "full_chem":
                raise ValueError("enable_stochastic=True requires resist_model='full_chem'")
            if self.stochastic_n_realisations < 1:
                raise ValueError("stochastic_n_realisations must be >= 1")
        if self.ler_passband_nm is not None:
            p_min, p_max = self.ler_passband_nm
            if not (0.0 < p_min < p_max):
                raise ValueError("ler_passband_nm must be (p_min, p_max) with 0 < p_min < p_max")
        if self.blocked_site_density_per_nm3 <= 0:
            raise ValueError("blocked_site_density_per_nm3 must be > 0")
        if self.dissolution_cell_nm <= 0:
            raise ValueError("dissolution_cell_nm must be > 0")
        # Chemistry densities (used by both chains, see the PAG/quencher note)
        if self.pag_density_per_nm3 <= 0:
            raise ValueError("pag_density_per_nm3 must be > 0")
        if self.quencher_density_per_nm3 < 0:
            raise ValueError("quencher_density_per_nm3 must be >= 0")
        if self.acid_base_quench_rate_nm3_per_s < 0:
            raise ValueError("acid_base_quench_rate_nm3_per_s must be >= 0")
        # LER estimator configuration (no artificial upper bound on grid_y)
        if self.stochastic_ler_grid_y < 1:
            raise ValueError("stochastic_ler_grid_y must be a positive integer")
        if self.development_model not in ("eikonal", "eikonal3d", "column"):
            raise ValueError(
                "development_model must be 'eikonal', 'eikonal3d' or 'column', got "
                f"{self.development_model!r}"
            )
        if self.stochastic_ler_estimator not in ("large_n", "legacy"):
            raise ValueError(
                "stochastic_ler_estimator must be 'large_n' or 'legacy', "
                f"got {self.stochastic_ler_estimator!r}"
            )


def _cd_via_aerial_threshold(
    aerial: torch.Tensor,
    cfg: SimulationConfig,
    half: int,
    line_width_px: int,
) -> tuple[float, torch.Tensor, float]:
    """Extract CD from the aerial image using a normalised intensity threshold.

    For a positive-tone resist:
    - Bright regions (space) → develop → 0 (developed)
    - Dark regions (absorber) → undeveloped → 1 (remaining)
    - CD = width of the undeveloped (below-threshold) region

    The threshold is ``resist_threshold_norm × mean(aerial) × 20 / dose``.

    Returns (cd_nm, resist_profile, nils_value).
    """
    G = aerial.shape[0]
    device = aerial.device
    cut = aerial[half, :]  # centre-row cut
    # FIXED threshold relative to nominal-dose intensity (c0² × nominal dose),
    # NOT 0.5 × mean(aerial).  The dose normalisation makes CD dose-dependent
    # and physically correct (higher dose → higher intensity → threshold crossed
    # at a different part of the profile).
    # c0 is the mean reflectivity (a·duty + b·(1−duty)); reconstructed here from
    # the aerial DC level.
    dc_level = float(aerial.mean())
    threshold_val = (
        cfg.resist_threshold_norm
        * dc_level
        * (AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2 / max(cfg.dose_mj_cm2, 1e-9))
    )
    dx_nm = cfg.period_nm / G
    device = aerial.device

    # NILS at the printed Optical-CD threshold edge (Mack).
    dx_nm = cfg.period_nm / cfg.grid
    nils_val = nils(aerial, half, line_width_px, dx_nm, threshold=threshold_val)

    # Positive-tone developed mask (used for visualization, unchanged)
    dev = (cut > threshold_val).float()
    dev_2d = dev.unsqueeze(0).expand(G, G).clone()

    # Sub-pixel CD extraction via linear threshold-crossing interpolation.
    # Same crossing logic as nils() — finds pairs of (below-threshold run)
    # crossings and uses the longest pair for CD.
    crossings: list[float] = []  # crossing positions in pixels
    for i in range(G - 1):
        a = float(cut[i])
        b = float(cut[i + 1])
        da = a - threshold_val
        db = b - threshold_val
        if da == 0.0 and db == 0.0:
            continue
        if da * db > 0.0:
            continue
        denom = b - a
        if abs(denom) < 1e-30:
            continue
        t = (threshold_val - a) / denom
        if t < 0.0 or t > 1.0:
            continue
        crossings.append(i + t)

    if len(crossings) < 2:
        cd_nm = 0.0
    else:
        # Pair consecutive crossings to find below-threshold runs.
        # For a periodic profile, crossings alternate between
        # below-threshold and above-threshold edges.
        # Each consecutive pair (x_k, x_{k+1}) defines a run.
        # Also consider the wrap-around pair (x_last, x_first + G).
        best_width_px = -1.0
        for k in range(len(crossings)):
            x0 = crossings[k]
            x1 = crossings[(k + 1) % len(crossings)]
            if k == len(crossings) - 1:
                x1 = x1 + G  # wrap around periodic boundary
            mid_px = 0.5 * (x0 + x1)
            if mid_px > G:
                mid_px = mid_px - G
            i_mid = min(G - 1, max(0, int(round(mid_px))))
            if float(cut[i_mid]) >= threshold_val:
                continue  # above-threshold → not an absorber run
            width = x1 - x0
            if width > best_width_px:
                best_width_px = width
        if best_width_px < 0.0:
            cd_nm = 0.0
        else:
            cd_nm = best_width_px * dx_nm

    return cd_nm, dev_2d, nils_val


def _peb_step(acid_3d, quencher_arg, cfg, dx_nm, dz_nm):
    """The PEB of the chain for both models (see SimulationConfig.peb_model)."""
    if cfg.peb_model == "reaction_diffusion":
        return reaction_diffusion_pde(
            acid_3d,
            quencher_arg,
            torch.ones_like(acid_3d),
            D=cfg.peb_D,
            k=cfg.peb_k,
            k_trap=cfg.peb_k_trap_per_s,
            quench_rate=cfg.acid_base_quench_rate_nm3_per_s,
            t_bake=cfg.peb_t_bake,
            dx=dx_nm,
            pag_density=cfg.pag_density_per_nm3,
            dz=dz_nm,
            D_quencher=cfg.peb_D_quencher,
        )
    return reaction_diffusion_with_quenching(
        acid_3d,
        quencher_arg,
        torch.ones_like(acid_3d),
        D=cfg.peb_D,
        k=cfg.peb_k,
        quench_rate=cfg.acid_base_quench_rate_nm3_per_s,
        t_bake=cfg.peb_t_bake,
        acid_lifetime_s=cfg.peb_acid_lifetime_s,
        sigma_diff=cfg.peb_sigma_diff,
        dx=dx_nm,
        pag_density=cfg.pag_density_per_nm3,  # k_Q [nm^3/s] -> k_Q*G0 [1/s]
        dz=dz_nm,
    )


def _develop_depth(inhib_3d, mack, dx_nm, dz_nm, cfg, return_arrival=False, rate_multiplier=None):
    """Developed depth map [nm] per the configured development model.

    With ``return_arrival=True`` also returns the bottom-layer arrival-time
    row field (H, W) for the Eikonal model, or ``None`` for the column model
    (which has no lateral information; its CD stays pixel-quantised).
    """
    if cfg.development_model in ("eikonal", "eikonal3d"):
        # "eikonal3d" (2026-09-06, B3.4): rows coupled through a y-term in the
        # Godunov update -- the true 3D first arrival; needed when the rate
        # field has cell-scale structure along y (development_stochasticity).
        depth, T = eikonal_development(
            inhib_3d,
            mack,
            dx=dx_nm,
            dz=dz_nm,
            t_develop=cfg.develop_time_s,
            return_arrival=True,
            rate_multiplier=rate_multiplier,
            dy=(dx_nm if cfg.development_model == "eikonal3d" else None),
            n_iter=(24 if cfg.development_model == "eikonal3d" else 6),
        )
        return (depth, T[-1]) if return_arrival else depth
    if rate_multiplier is not None:
        raise NotImplementedError(
            "development_stochasticity requires development_model 'eikonal' or 'eikonal3d'"
        )
    depth = surface_advancement_level_set(
        inhib_3d, mack, dx=dx_nm, dz=dz_nm, t_develop=cfg.develop_time_s
    )
    return (depth, None) if return_arrival else depth


def _peb_blur_radius_px(cfg, dx_nm: float) -> int:
    """Half-width [px] of the lateral PEB Gaussian exactly as gaussian_se_blur
    truncates it (4 sigma, rounded), or 0 when the PEB does not blur.
    """
    sigma = None
    if cfg.peb_sigma_diff is not None and cfg.peb_sigma_diff > 0:
        sigma = float(cfg.peb_sigma_diff)
    elif cfg.peb_D > 0 and cfg.peb_t_bake > 0:
        s = (2.0 * cfg.peb_D * cfg.peb_t_bake) ** 0.5
        sigma = s if s > 0.1 else None
    if sigma is None:
        return 0
    return int(4.0 * sigma / dx_nm + 0.5)


def _noisy_depth_map(d_eff, cfg, *, n_layers, dx_nm, dz_nm, q0_rel, mack, rng, tile_rows=1024):
    """Developed-depth map (H, W) of one noisy 2D dose realisation.

    The chain exposure -> PEB (diffuse, quench, deprotect) -> development is
    the one the deterministic path runs, applied here in **y-tiles with a
    halo** instead of on the whole ``(n_layers, H, W)`` stack: for the 61440-
    row large-N LER fields the stack alone is 2.6 GB and the PEB/Eikonal
    working sets ~10x that (measured 2026-09-05, the tests were OOM-killed).

    Exactness. Every step is either pointwise, per column (z-blur, Beer-
    Lambert), per row (Eikonal) or a lateral circular convolution truncated
    at 4 sigma (gaussian_se_blur); with a halo of one more row than that
    radius, taken periodically from the full field, the interior rows of a
    tile receive exactly the contributions they receive in the full
    convolution, so the result equals the unchunked one to FFT rounding
    (tests/test_stochastic_chunking.py). With sampled molecules the draw for
    each tile comes from its own generator seeded from *rng* once up front,
    so a tile's molecules are the same whether it is processed as interior
    or as a neighbour's halo -- one consistent realisation, independent of
    how the rows are grouped. A field of at most *tile_rows* rows is a
    single tile drawn directly from *rng* (no halo), i.e. unchanged.
    """
    H, W = d_eff.shape
    radius = _peb_blur_radius_px(cfg, dx_nm)
    halo = radius + 1 if radius > 0 else 0
    tile_rows = max(int(tile_rows), halo)
    # Rows are distributed evenly over floor(H / tile_rows) tiles so that EVERY
    # tile (including the last) has at least tile_rows >= halo rows -- a short
    # remainder tile would otherwise contribute fewer halo rows than assumed
    # and misalign the interior slice.
    n_tiles = max(1, H // tile_rows)
    base, extra = divmod(H, n_tiles)
    bounds = [0]
    for t in range(n_tiles):
        bounds.append(bounds[-1] + base + (1 if t < extra else 0))
    thickness_um = cfg.resist_thickness_nm / 1000.0
    alpha = cfg.dill_A + cfg.dill_B  # [1/um]
    z_um = torch.linspace(0.0, thickness_um, n_layers, device=d_eff.device)
    # development noise: one seed per realisation, drawn BEFORE any tiling
    # decision so that the field (anchored to absolute rows) is identical for
    # every tiling; nothing is drawn when the option is off, so the photon/PAG
    # streams of the existing goldens are unchanged.
    dev_seed = (
        int(torch.randint(0, 2**62, (1,), generator=rng, device="cpu"))
        if cfg.development_stochasticity
        else None
    )
    if n_tiles == 1:
        halo = 0
        tile_gens = [rng]
    else:
        seeds = torch.randint(0, 2**62, (n_tiles,), generator=rng, device="cpu")
        tile_gens = []
        for t in range(n_tiles):
            g = torch.Generator(device=d_eff.device)
            g.manual_seed(int(seeds[t]))
            tile_gens.append(g)

    def tile_rows_of(t):
        return bounds[t], bounds[t + 1]

    def sampled_tile(t):
        """Acid/quencher sample of whole tile t (own generator, reproducible)."""
        y0, y1 = tile_rows_of(t)
        dose_z = d_eff[y0:y1].unsqueeze(0) * torch.exp(-alpha * z_um.view(-1, 1, 1))
        return sample_pag_quencher_acid(
            dose_z,
            C=cfg.dill_C,
            pag_density=cfg.pag_density_per_nm3,
            quencher_density=cfg.quencher_density_per_nm3,
            dx=dx_nm,
            dz=dz_nm,
            rng=tile_gens[t],
        )

    depth_parts = []
    for t in range(n_tiles):
        y0, y1 = tile_rows_of(t)
        rows = torch.arange(y0 - halo, y1 + halo, device=d_eff.device) % H
        if cfg.exposure_stochasticity:
            # PAG/quencher molecular discreteness (see SimulationConfig's
            # exposure_stochasticity note). The per-molecule conversion
            # probability is 1 - exp(-C*E), the same Dill-C law as the mean-
            # field path; dill_A/dill_B give the Beer-Lambert depth profile.
            if halo == 0:
                acid_3d, quencher_3d = sampled_tile(t)
            else:
                prev_t, next_t = (t - 1) % n_tiles, (t + 1) % n_tiles
                a_prev, q_prev = sampled_tile(prev_t)
                a_cur, q_cur = sampled_tile(t)
                a_next, q_next = sampled_tile(next_t) if next_t != prev_t else (a_prev, q_prev)
                # halo rows: the last `halo` rows of the previous tile and the
                # first `halo` rows of the next one (periodic); tiles are at
                # least `halo` rows long by construction
                acid_3d = torch.cat([a_prev[:, -halo:], a_cur, a_next[:, :halo]], dim=1)
                quencher_3d = torch.cat([q_prev[:, -halo:], q_cur, q_next[:, :halo]], dim=1)
                del a_prev, q_prev, a_cur, q_cur, a_next, q_next
            quencher_arg = quencher_3d
        else:
            acid_3d, _ = dill_abc_exposure(
                d_eff[rows],
                A=cfg.dill_A,
                B=cfg.dill_B,
                C=cfg.dill_C,
                thickness=thickness_um,
                n_layers=n_layers,
            )
            # photon-shot-noise-only chain: same mean-field quencher as the
            # deterministic path (uniform q0), same PEB step
            quencher_arg = q0_rel
        _, _, inhib_3d = _peb_step(acid_3d, quencher_arg, cfg, dx_nm, dz_nm)
        del acid_3d
        rate_mult = None
        if dev_seed is not None:
            rate_mult = dissolution_cell_noise(
                inhib_3d,
                mack,
                blocked_density_per_nm3=cfg.blocked_site_density_per_nm3,
                cell_nm=cfg.dissolution_cell_nm,
                dx=dx_nm,
                dz=dz_nm,
                row_index=rows,
                seed=dev_seed,
            )
        depth = _develop_depth(inhib_3d, mack, dx_nm, dz_nm, cfg, rate_multiplier=rate_mult)
        del inhib_3d, rate_mult
        n_int = y1 - y0
        depth_parts.append(depth[halo : halo + n_int])
    return torch.cat(depth_parts, dim=0)


def _cd_via_full_chem(
    aerial: torch.Tensor,
    cfg: SimulationConfig,
    period_m: float,
    half: int,
    line_width_px: int,
    energy_eV: float,
    progress: ProgressHook | None = None,
) -> tuple[float, torch.Tensor, float, float, float, dict[str, Any] | None]:
    """Extract CD via full resist chemistry chain (dose → acid → PEB → develop).

    Depth-resolved chain (2026-09-03, round 9; PEB step unified 2026-09-04):
    dill_abc_exposure() (real Beer-Lambert absorption via dill_A/B,
    depth-resolved acid generation) -> reaction_diffusion_with_quenching()
    (PEB per depth layer: diffuse acid + quencher, neutralise, deprotect --
    the same step the sampled-molecule chain uses, with q0 = ρ_Q/ρ_PAG) ->
    MackModel.rate() via surface_advancement_level_set() (continuous
    Mack R(M) development front, time-integrated over cfg.develop_time_s)
    -> a pixel is "developed" where the front has cleared all the way
    through cfg.resist_thickness_nm. This REPLACES the previous 2D-only,
    single-layer dose_to_acid()+threshold_development(mack_M_th) chain,
    which (a) never used dill_A/B at all (Beer-Lambert absorption was not
    modelled, see the dill_A/B "ARCHITECTURE GAP" note in SimulationConfig
    above) and (b) never used mack_R_max/R_min/n (the Mack rate equation
    itself was never evaluated, only M_th as a flat cutoff -- see the
    mack_R_max "SEPARATE, ALREADY-KNOWN ISSUE" note above, now resolved by
    this change).

    UPDATE (2026-09-03, same round, "mach den stochastischen Pfad auch"):
    the stochastic LER/LWR path below now uses the SAME depth-resolved
    dill_abc_exposure() -> reaction_diffusion_analytical() ->
    MackModel/surface_advancement_level_set() chain per noise realisation,
    applied to the photon-shot-noise-perturbed dose instead of the clean
    one. This replaces the old, even-more-simplified stochastic chain,
    which skipped PEB entirely (went straight from noisy 2D acid to a
    threshold) and used its own independent stochastic_develop_threshold/
    stochastic_quantum_efficiency parameters -- the latter was dead code
    (declared, validated, never read; same bug class as dill_A/B/
    mack_R_max), and both are now removed from SimulationConfig in favour
    of the same resist_thickness_nm/develop_time_s/mack_M_th the
    deterministic path uses, so a pixel means the same thing ("developed")
    in both paths.
    """
    dx_nm = period_m / cfg.grid * 1e9

    # Resist-chemie-Kette (Dill ABC → PEB → Entwicklung)
    # Alle Parameter kommen jetzt aus cfg (mit Defaults aus SimulationConfig)
    dose_map = aerial.clone().float()

    # Apply SE blur to dose map (this is what resist sees)
    from euvsimulator.resist.exposure import gaussian_se_blur

    if cfg.se_blur_nm > 0.0:
        dose_map_blurred = gaussian_se_blur(dose_map, sigma=cfg.se_blur_nm, dx=dx_nm)
    else:
        dose_map_blurred = dose_map

    # NILS is evaluated AFTER development, at the edge the chemistry actually
    # prints (see the CD extraction below). Until 2026-09-04 it was taken at
    # the aerial_threshold model's reference-dose threshold, which has no
    # meaning for the chemistry chain (it returned 0 whenever that threshold
    # missed the image, e.g. at dose 4 mJ/cm²).

    # Depth-resolved acid generation (real Beer-Lambert via dill_A/B).
    # inhibitor from dill_abc_exposure() itself is discarded (not inhib_3d)
    # -- this codebase's PEB step (reaction_diffusion_analytical) models a
    # CATALYTIC CAR resist, where deprotection happens during PEB from a
    # fully-protected M=1 start, not during exposure itself (matching the
    # pre-existing 2D chain's own convention, unchanged here).
    n_layers = max(int(cfg.n_develop_layers), 2)
    dz_nm = cfg.resist_thickness_nm / (
        n_layers - 1
    )  # layer spacing [nm]; used by PEB (z-diffusion) and development
    acid_3d, _ = dill_abc_exposure(
        dose_map_blurred,
        A=cfg.dill_A,
        B=cfg.dill_B,
        C=cfg.dill_C,
        thickness=cfg.resist_thickness_nm / 1000.0,  # nm -> µm
        n_layers=n_layers,
    )
    inhib_in_3d = torch.ones_like(acid_3d)
    # Mean-field PEB with the SAME diffuse-then-quench step as the sampled
    # chain (see SimulationConfig's PAG/quencher note): q0 = ρ_Q/ρ_PAG in
    # the relative units of the acid field (0 by default).
    q0_rel = cfg.quencher_density_per_nm3 / cfg.pag_density_per_nm3
    del inhib_in_3d
    # uniform loading as a float (no full-field allocation); isotropic
    # diffusion with the same sigma along z (Neumann at the surfaces)
    _, _, inhib_3d = _peb_step(acid_3d, q0_rel, cfg, dx_nm, dz_nm)

    # Continuous Mack development, time-integrated through the resist depth.
    mack = MackModel(R_max=cfg.mack_R_max, R_min=cfg.mack_R_min, n=cfg.mack_n, M_th=cfg.mack_M_th)
    depth_map, arrival_bottom = _develop_depth(
        inhib_3d, mack, dx_nm, dz_nm, cfg, return_arrival=True
    )
    # Resist-Profil für Visualisierung (1 = developed/dissolved all the way
    # through the film, 0 = undeveloped/remaining) -- same binary semantics
    # as the previous threshold_development() output, now derived from a
    # depth- and time-resolved Mack-rate front instead of a flat M_th cutoff.
    dev_chem = (depth_map >= cfg.resist_thickness_nm - 1e-6).float()

    # ── Stochastic post-processing ──
    # Event-based photon deposition shot noise (Step 2 of the design audit):
    #   dose_map -> Poisson photons -> SE-PSF (inside photon_deposition_shot_noise)
    #             -> D_eff -> acid_noisy -> develop -> LER/LWR
    # The SE-PSF is applied ONCE, inside photon_deposition_shot_noise.
    # dose_map (unblurred) is passed, and dose_to_acid uses apply_blur=False,
    # so no second SE blur is applied.
    ler_metadata = None
    if cfg.enable_stochastic:
        rng = torch.Generator(device=dose_map.device)
        if cfg.stochastic_seed is not None:
            rng.manual_seed(cfg.stochastic_seed)

        use_large_n = cfg.stochastic_ler_estimator == "large_n"
        if use_large_n:
            # Correlation-aware large-N LER (STEP 5.2B/5.2C):
            # deterministic Y-periodic extension BEFORE stochastic generation.
            # Any positive grid_y is supported via repeat + trim.  This is
            # mathematically justified because the current aerial field is
            # exactly y-invariant (max|aerial[y+1]-aerial[y]| = 0, verified
            # by test_aerial_y_invariance): every row is bitwise identical,
            # so the circular Y-blur wrap connects identical rows for ANY N.
            # If a true 2D mask/RCWA field (not y-invariant) is introduced,
            # this assumption must be re-evaluated.
            grid_y = cfg.stochastic_ler_grid_y
            repetitions = math.ceil(grid_y / dose_map.shape[0])
            stoch_dose = torch.tile(dose_map, (repetitions, 1))[:grid_y]
        else:
            stoch_dose = dose_map

        ler_vals = []
        lwr_vals = []
        dev_fields = []
        intensity_fields = []
        stochastic_cd_vals = []  # mean line width per realisation [nm]
        # Only ABSORBED photons generate acid, so only they contribute to
        # the exposure shot noise (Mack, Biafore & Smith 2011, J. Micro/
        # Nanolith. MEMS MOEMS 10(3), 033019: the absorbed photon density is
        # D·α/E_ph). With the same Beer-Lambert coefficient the depth-
        # resolved chain uses (α = dill_A + dill_B, treated as unbleached --
        # see dill_abc_exposure), the fraction of incident photons absorbed
        # in the film is 1 − exp(−α·t). Sampling the 2D incident field with
        # this fraction reproduces the Poisson statistics of the COLUMN
        # total of absorbed photons exactly; it does not resolve the (small)
        # depth dependence of the relative noise, which would need a per-
        # layer draw. Before 2026-09-04 absorption was left at its default
        # of 1.0 (every incident photon counted): with the default 50 nm /
        # 1.06 µm⁻¹ film (the default until 2026-09-05) that is 19× too many
        # photons and a 4.4× (linear)
        # to 7.9× (measured, through the Mack nonlinearity) under-estimate
        # of the photon-shot-noise LWR -- docs/audit_2026-09-04_vollpruefung.md, A1.
        alpha_per_um = cfg.dill_A + cfg.dill_B
        thickness_um = cfg.resist_thickness_nm / 1000.0
        absorbed_fraction = 1.0 - math.exp(-alpha_per_um * thickness_um)
        for i_real in range(cfg.stochastic_n_realisations):
            if progress is not None and not progress(i_real, cfg.stochastic_n_realisations):
                raise SimulationCancelledError("cancelled by the progress hook")
            d_eff = photon_deposition_shot_noise(
                stoch_dose,
                se_blur_nm=cfg.se_blur_nm,
                dx_nm=dx_nm,
                photon_energy_eV=energy_eV,  # from wavelength via HC_EV_NM
                dose_to_energy_factor=6.241509074e15,
                absorption=absorbed_fraction,
                rng=rng,
            )
            # Same depth-resolved exposure -> PEB -> Mack-rate chain as the
            # deterministic path above (n_layers, mack, dz_nm reused from
            # there), now applied to the noisy dose. depth_map_noisy [nm]
            # is this realisation's continuous "how far the front got"
            # field -- the direct analogue of the old acid_noisy, but
            # physically complete (depth-resolved absorption + PEB, not a
            # bare Dill-C exponential on 2D dose).
            # Depth-resolved exposure (sampled molecules or mean field) ->
            # PEB -> development, processed in y-tiles with a halo so the
            # 61440-row LER fields never hold the full 3D stack (see
            # _noisy_depth_map). Same physics as the deterministic path.
            depth_map_noisy = _noisy_depth_map(
                d_eff,
                cfg,
                n_layers=n_layers,
                dx_nm=dx_nm,
                dz_nm=dz_nm,
                q0_rel=q0_rel,
                mack=mack,
                rng=rng,
            )
            # developed is left as the raw continuous depth field here
            # (NOT pre-binarised) so extract_ler/lwr's own `developed >
            # threshold` binarisation and the `intensity` sub-pixel
            # crossing agree on the same threshold/scale. Threshold is
            # thickness MINUS a small epsilon, matching the
            # deterministic path's own `>=` convention above: depth_map
            # is clamped to a max of exactly resist_thickness_nm (see
            # surface_advancement_level_set), so a strict `>` against
            # the unmodified thickness would never fire for a fully
            # cleared pixel -- found and fixed 2026-09-03 alongside the
            # threshold/intensity pairing bug in this same block.
            # (development_stochasticity acts inside _noisy_depth_map on the
            # development rate; the edge extraction is the same.)
            developed = depth_map_noisy
            edge_threshold = cfg.resist_thickness_nm - 1e-6
            edge_intensity = depth_map_noisy
            # Mean line width of this realisation (the stochastic CD), for
            # the large-number-limit invariant and as a diagnostic.
            _l_edge, _r_edge = extract_edges(
                developed, threshold=edge_threshold, dx=dx_nm, intensity=edge_intensity
            )
            _w = _r_edge - _l_edge
            _w = _w[~torch.isnan(_w)]
            stochastic_cd_vals.append(float(_w.mean()) if _w.numel() > 0 else float("nan"))
            if use_large_n:
                dev_fields.append(developed)
                intensity_fields.append(edge_intensity)
            else:
                ler_vals.append(
                    extract_ler(
                        developed,
                        threshold=edge_threshold,
                        dx=dx_nm,
                        intensity=edge_intensity,
                    )
                )
            lwr_vals.append(
                extract_lwr(
                    developed,
                    threshold=edge_threshold,
                    dx=dx_nm,
                    intensity=edge_intensity,
                    passband_nm=cfg.ler_passband_nm,
                )
            )

        if use_large_n:
            # One LER estimate per realization (spatial N_eff within each
            # field), aggregated over seeds (between-seed SE/CI).
            est = ler_estimate(
                dev_fields,
                # defined in the loop above; constant across realisations
                threshold=edge_threshold,
                dx=dx_nm,
                intensity=intensity_fields,
                edge="both",
                estimator="large_n",
                passband_nm=cfg.ler_passband_nm,
                seed_count=cfg.stochastic_n_realisations,
            )
            ler_nm = est.ler_nm
            ler_metadata = {
                "ler_nm": est.ler_nm,
                "n_rows": est.n_rows,
                "n_eff": est.n_eff,
                "l_int_px": est.l_int_px,
                "l_int_nm": est.l_int_nm,
                "uncertainty_nm": est.uncertainty_nm,
                "ci95_low_nm": est.ci95_low_nm,
                "ci95_high_nm": est.ci95_high_nm,
                "seed_count": est.seed_count,
                "estimator": est.estimator,
                "rho_truncation": est.rho_truncation,
                "disclaimer": est.disclaimer,
                # Mean line width of the stochastic realisations [nm]. Differs
                # from cd_nm (deterministic, mean-field) by the effect of
                # nonlinearities on the noise; converges to cd_nm as the
                # molecule density -> inf (tests/test_stochastic_consistency.py).
                "stochastic_cd_nm": float(torch.tensor(stochastic_cd_vals).nanmean())
                if stochastic_cd_vals
                else float("nan"),
            }
        else:
            ler_nm = float(torch.tensor(ler_vals).nanmean())
        lwr_nm = float(torch.tensor(lwr_vals).nanmean())
    else:
        ler_nm = 0.0
        lwr_nm = 0.0

    # CD-Extraktion aus dem entwickelten Resistprofil (dev_chem)
    # dev_chem: 1 = developed/dissolved, 0 = undeveloped/remaining
    # Für positive-tone: CD = width of undeveloped region (value 0)
    dev_for_cd = dev_chem[half, :].float()  # middle row of developed profile
    runs = _find_runs_1d(dev_for_cd, target=0)  # find runs of undeveloped (0)
    if len(runs) == 0:
        cd_nm = 0.0
        nils_val = float("nan")
    else:
        longest = max(runs, key=lambda r: r[1] - r[0])
        lidx, ridx = longest
        cd_nm = (ridx - lidx + 1) * dx_nm
        whole_row_undeveloped = (ridx - lidx + 1) >= dev_for_cd.shape[0]
        if arrival_bottom is not None:
            # Sub-pixel line width from the bottom-layer arrival time
            # (Eikonal model): the pixel count above is quantised to dx,
            # which made every CD-vs-parameter curve a staircase (and
            # `euv calibrate` blind on coarse grids, 2026-09-05). Falls back
            # to the pixel count if the interpolation finds no line.
            x_l, x_r = edge_positions_from_arrival(
                arrival_bottom[half, :], cfg.develop_time_s, dx_nm
            )
            if x_r == x_r and x_l == x_l:
                cd_nm = x_r - x_l
        # NILS at the printed edges: the image intensity at the boundary
        # between the last developed and the first undeveloped pixel defines
        # the threshold at which this chemistry prints; nils() then measures
        # CD·|dI/dx|/I at the crossings of that level (Mack 2007 §4.5).
        if whole_row_undeveloped:
            # Nothing developed (CD = pitch): there is no printed edge, so no
            # NILS. Before 2026-09-11 the threshold was taken from the
            # wrap-around pixels and nils() reported a spurious value (0.47
            # at 64 nm pitch) for a line that does not exist (campaign
            # 2026-09-07, docs/campaign_2026-09-07/README.md).
            nils_val = float("nan")
        else:
            row_i = dose_map_blurred[half, :]
            W_ = row_i.shape[0]
            i_l = 0.5 * (float(row_i[(lidx - 1) % W_]) + float(row_i[lidx]))
            i_r = 0.5 * (float(row_i[ridx]) + float(row_i[(ridx + 1) % W_]))
            nils_val = nils(
                dose_map_blurred, half, line_width_px, dx_nm, threshold=0.5 * (i_l + i_r)
            )
    # dev_2d für Visualisierung
    dev_2d = dev_chem.clone()

    return cd_nm, dev_2d, nils_val, ler_nm, lwr_nm, ler_metadata


def _find_runs_1d(x: torch.Tensor, target: int = 0) -> list:
    """Find consecutive runs of ``x == target`` in a 1D tensor.

    Returns list of (start_idx, end_idx) inclusive.
    """
    padded = torch.cat(
        [
            torch.tensor([1 - target], device=x.device),
            x,
            torch.tensor([1 - target], device=x.device),
        ]
    )
    diffs = torch.diff(padded.float())
    starts = torch.where(diffs < -0.5)[0]
    ends = torch.where(diffs > 0.5)[0] - 1
    return [(int(s), int(e)) for s, e in zip(starts, ends)]


def run_simulation(
    cfg: Optional[SimulationConfig] = None,
    *,
    progress: ProgressHook | None = None,
    **kwargs,
) -> SimulationResult:
    """Run a full end-to-end EUV lithography simulation.

    Parameters
    ----------
    cfg : SimulationConfig, optional
        Simulation configuration.  Omit for defaults.
    progress : callable, optional
        ``progress(done, total)`` is called before each stochastic realisation;
        returning ``False`` cancels the run with :class:`SimulationCancelledError`.
    **kwargs
        Override individual config parameters.

    Returns
    -------
    SimulationResult
    """
    if cfg is None:
        cfg = SimulationConfig(**kwargs)
    else:
        for k, v in kwargs.items():
            setattr(cfg, k, v)

    # Resolve device
    if cfg.device == "auto":
        device = select_device(prefer_gpu=True)
    else:
        device = torch.device(cfg.device)

    # Set default precision
    set_default_dtype(torch.complex128, torch.float64)

    wavelength_m = cfg.wavelength_nm * 1e-9
    # Derive photon energy from wavelength (single source of truth)
    energy_eV = HC_EV_NM / cfg.wavelength_nm
    period_m = cfg.period_nm * 1e-9
    line_m = cfg.line_width_nm * 1e-9
    half = cfg.grid // 2

    # ── 1. Materials ──────────────────────────
    table = CXROTable()

    # ── 5. Aerial image from complex diffraction orders (TMM + Hopkins) ──
    # Compute the complex reflectivity of the ML mirror and the absorber+ML stack
    # via TMM.  Then compute the 1D aerial image directly from the Fourier
    # coefficients of the binary complex mask using the Hopkins formulation.
    theta0 = torch.tensor(math.radians(6.0), dtype=torch.float64)
    wl_t = torch.tensor([wavelength_m], dtype=torch.float64)
    n_si, k_si = table.refractive_index("Si", energy_eV)
    n_sub = torch.tensor(complex(n_si, k_si), dtype=torch.complex128)

    # Build multilayer stack (without absorber)
    ml_stack = mo_si_stack(
        n_bilayers=cfg.ml_n_bilayers,
        d_mo_nm=cfg.ml_d_mo_nm,
        d_si_nm=cfg.ml_d_si_nm,
        gamma=cfg.ml_gamma,
        grading_linear_nm=cfg.ml_grading_linear_nm,
        grading_parabolic_nm=cfg.ml_grading_parabolic_nm,
        capping_layer=cfg.ml_capping if cfg.ml_capping != "none" else None,
        d_cap_nm=cfg.ml_capping_nm,
    )

    # TMM: ML-only reflectivity (space regions)
    _, r_space = reflectivity(
        ml_stack.n_layers,
        ml_stack.thicknesses,
        wl_t,
        theta0,
        n_substrate=n_sub,
        roughness_nm=cfg.ml_roughness_nm,
    )
    r0_space = r_space[0]

    # Clear-field (open-frame) intensity reflectivity of the bare mirror,
    # TE and TM, used below to put the aerial image on the exposure-dose
    # scale (see SimulationConfig.dose_mj_cm2). TM is only needed for the
    # RCWA path's unpolarised average but is cheap, so compute both here.
    _, r_space_tm = reflectivity(
        ml_stack.n_layers,
        ml_stack.thicknesses,
        wl_t,
        theta0,
        n_substrate=n_sub,
        te=False,
        roughness_nm=cfg.ml_roughness_nm,
    )
    R_clear_te = float((abs(r0_space) ** 2).real)
    R_clear_tm = float((abs(r_space_tm[0]) ** 2).real)
    if R_clear_te <= 1e-12 or R_clear_tm <= 1e-12:
        raise ValueError(
            "Multilayer clear-field reflectivity is ~0 (TE "
            f"{R_clear_te:.3e}, TM {R_clear_tm:.3e}); the exposure dose is "
            "defined relative to the open frame and cannot be applied."
        )

    # TMM: absorber-on-ML reflectivity (absorber lines)
    n_ta_c, k_ta_c = table.refractive_index(cfg.absorber_material, energy_eV)
    n_abs = torch.tensor(complex(n_ta_c, k_ta_c), dtype=torch.complex128)
    d_abs = torch.tensor([cfg.absorber_height_nm * 1e-9], dtype=torch.float64)
    full_n = torch.cat([n_abs.unsqueeze(0), ml_stack.n_layers])
    full_d = torch.cat([d_abs, ml_stack.thicknesses])

    _, r_ab = reflectivity(
        full_n,
        full_d,
        wl_t,
        theta0,
        n_substrate=n_sub,
        roughness_nm=cfg.ml_roughness_nm,
    )
    r0_abs = r_ab[0]

    # Average absorber reflectivity (diagnostic)
    space_frac = 1.0 - cfg.line_width_nm / cfg.period_nm
    absorber_reflectivity = float(
        (abs(r0_abs) ** 2 * (1.0 - space_frac) + abs(r0_space) ** 2 * space_frac).real
    )

    # ── Mask diffraction orders: thin-mask analytic OR full RCWA ──
    duty = cfg.line_width_nm / cfg.period_nm  # η = absorber fraction
    n_orders = min(cfg.n_rcwa_orders, cfg.grid // 2)
    order_indices = list(range(-n_orders, n_orders + 1))

    if cfg.use_rcwa:
        from euvsimulator.mask3d.geometry import MaskLayer, MaskStack, build_permittivity_profile
        from euvsimulator.mask3d.rcwa_torch import RCWA1D, RCWAConfig

        # Build mask stack WITHOUT Ru in the absorber layers.
        # Ru is part of the ML operator (the ML stack's top layer).
        # The RCWA grating consists of the Ta absorber only (60 nm).
        n_ta_c, k_ta_c = table.refractive_index(cfg.absorber_material, energy_eV)
        layers = [
            MaskLayer(
                material=cfg.absorber_material,
                thickness_nm=cfg.absorber_height_nm,
                nk=complex(n_ta_c, k_ta_c),
                etched=True,
            ),
        ]
        # Absorber taper / undercut are NOT implemented in
        # build_permittivity_profile (it builds a binary, vertical-sidewall
        # grating). Refuse non-default values instead of silently ignoring
        # them (behaviour before 2026-09-04): a parameter that is accepted
        # and does nothing misrepresents the model.
        if cfg.absorber_taper_deg != 90.0 or cfg.mask_undercut_nm != 0.0:
            raise NotImplementedError(
                "absorber_taper_deg / mask_undercut_nm are not implemented in the "
                "RCWA mask geometry (binary vertical-sidewall grating only); got "
                f"taper={cfg.absorber_taper_deg}, undercut={cfg.mask_undercut_nm}. "
                "Use the defaults (90.0, 0.0) or implement the sloped-sidewall "
                "multi-slice profile in mask3d/geometry.py first."
            )

        # The RCWA sees the PHYSICAL mask: wafer dimensions × demagnification
        # (see SimulationConfig.mask_demagnification). Order index m is the
        # same on both sides -- the mask spatial frequency m/(M·P) maps to
        # m/P at the wafer -- so the amplitudes feed aerial_from_orders()
        # with the wafer period unchanged.
        M_demag = float(cfg.mask_demagnification)
        if M_demag <= 0.0:
            raise ValueError(f"mask_demagnification must be > 0, got {M_demag}")
        period_mask_m = period_m * M_demag
        mask = MaskStack(
            absorber_layers=layers,
            multilayer_bilayers=cfg.ml_n_bilayers,
            d_mo_nm=cfg.ml_d_mo_nm,
            d_si_nm=cfg.ml_d_si_nm,
            substrate_nk=complex(n_si, k_si),
            period_nm=cfg.period_nm * M_demag,
            line_width_nm=cfg.line_width_nm * M_demag,
        )

        eps_profile, thicknesses, eps_sub = build_permittivity_profile(
            mask, n_samples=1024, device=str(device)
        )

        # RCWA solver for TE polarization (standard for EUV)
        rcwa_cfg = RCWAConfig(
            wavelength=wavelength_m,
            n_orders=cfg.n_rcwa_orders,
            theta=math.degrees(theta0),
            polarization="TE",
            device=device.type,
        )
        solver = RCWA1D(rcwa_cfg)
        orders_te = solver.solve(
            eps_profile,
            thicknesses,
            period_mask_m,
            n_incident=torch.tensor(
                [1.0 + 0.0j, 1.0 + 0.0j], dtype=torch.complex128, device=device
            ),
            ml_stack=ml_stack,  # P1-2: order-diagonal ML operator
        )
        # Also compute TM for future High-NA
        rcwa_cfg_tm = RCWAConfig(
            wavelength=wavelength_m,
            n_orders=cfg.n_rcwa_orders,
            theta=math.degrees(theta0),
            polarization="TM",
            device=device.type,
        )
        solver_tm = RCWA1D(rcwa_cfg_tm)
        orders_tm = solver_tm.solve(
            eps_profile,
            thicknesses,
            period_mask_m,
            n_incident=torch.tensor(
                [1.0 + 0.0j, 1.0 + 0.0j], dtype=torch.complex128, device=device
            ),
            ml_stack=ml_stack,  # P1-2: order-diagonal ML operator
        )

        # Unpolarized illumination: TE and TM are orthogonal incoherent
        # polarization states.  The physical average is applied AFTER
        # aerial (intensity) reconstruction, NOT on the complex fields
        # (P1 fix, 2026-08-31).  Intensity maps are averaged below.
        # Order labels MUST be the solver's own m-vector. The previous
        # expression torch.arange(-cfg.n_rcwa_orders // 2, ...) used Python
        # floor division (-11 // 2 == -6), producing 12 labels [-6..5] for 11
        # amplitudes: every RCWA order was mislabelled by one, the 0th order
        # was imaged as m = -1 (tilted image, TCC-damped to ~0.69 of the
        # mirror reflectivity for an EMPTY grating). Found 2026-09-04 by the
        # open-frame dose invariant (tests/test_dose_convention.py); the
        # earlier RCWA/thin-mask plausibility test tolerated a 0.5-1.2 ratio
        # and so never caught it.
        solver_m = solver.m.to(torch.int64)
        order_indices = solver_m.tolist()
    else:
        # Thin-mask analytic Fourier coefficients (existing path)
        a = r0_abs
        b = r0_space
        c0 = a * duty + b * (1.0 - duty)

        amplitudes = torch.zeros(len(order_indices), dtype=torch.complex128, device=device)

        for idx, m in enumerate(order_indices):
            if m == 0:
                amplitudes[idx] = c0
            else:
                cm = (a - b) * math.sin(math.pi * m * duty) / (math.pi * m)
                amplitudes[idx] = cm

    # Compute aerial image from orders (Hopkins formulation)
    order_tensor = torch.tensor(order_indices, dtype=torch.int64, device=device)
    if cfg.use_rcwa:
        # Physical unpolarized average: I = (I_TE + I_TM) / 2.
        # TE and TM are orthogonal incoherent states — averaging must
        # happen AFTER the quadratic (intensity) reconstruction.
        aerial_te = aerial_from_orders(
            orders_te,
            order_tensor,
            period_m=period_m,
            na=cfg.na,
            wavelength_m=wavelength_m,
            sigma=cfg.sigma,
            illumination_shape=cfg.illumination_shape,
            grid=cfg.grid,
            focus_nm=cfg.focus_nm,
            sigma_inner=cfg.sigma_inner,
            pole_opening_deg=cfg.pole_opening_deg,
        )
        aerial_tm = aerial_from_orders(
            orders_tm,
            order_tensor,
            period_m=period_m,
            na=cfg.na,
            wavelength_m=wavelength_m,
            sigma=cfg.sigma,
            illumination_shape=cfg.illumination_shape,
            grid=cfg.grid,
            focus_nm=cfg.focus_nm,
            sigma_inner=cfg.sigma_inner,
            pole_opening_deg=cfg.pole_opening_deg,
        )
        # Each polarisation is normalised to ITS OWN open-frame intensity
        # before averaging, so an absorber-free mask yields exactly 1 for
        # both and the unpolarised image is a clear-field-normalised image.
        aerial = (aerial_te / R_clear_te + aerial_tm / R_clear_tm) / 2.0
        clear_field_reflectivity = 0.5 * (R_clear_te + R_clear_tm)
    else:
        aerial = aerial_from_orders(
            amplitudes,
            order_tensor,
            period_m=period_m,
            na=cfg.na,
            wavelength_m=wavelength_m,
            sigma=cfg.sigma,
            illumination_shape=cfg.illumination_shape,
            grid=cfg.grid,
            focus_nm=cfg.focus_nm,
            sigma_inner=cfg.sigma_inner,
            pole_opening_deg=cfg.pole_opening_deg,
        )
        # Thin-mask path: the Hopkins sum is relative to unit illumination
        # of the mask (open frame -> |r_ML|²). Divide by the clear-field
        # reflectivity so an open frame -> 1 (TE, the polarisation the
        # thin-mask coefficients were computed for).
        aerial = aerial / R_clear_te
        clear_field_reflectivity = R_clear_te

    # ── Exposure-dose scale ──
    # aerial is now the normalised image intensity I(x) of Mack's definition
    # (open frame == 1), so multiplying by the exposure dose gives the
    # energy density actually delivered to the resist, E·I(x) [mJ/cm²]
    # (SimulationConfig.dose_mj_cm2 has the citation). This is an absolute
    # scaling, NOT a max-normalisation: the aerial_threshold model's
    # threshold is a fixed fraction of the nominal-dose intensity, so CD is
    # dose-dependent (higher dose -> narrower line for positive resist), and
    # the full_chem model's Dill exposure and photon counting see the
    # physical wafer dose. Mirror losses (ml_roughness_nm, ml_n_bilayers,
    # ...) no longer change the resist dose -- a scanner calibrates dose at
    # the wafer -- they enter only through the image contrast.
    aerial = aerial * cfg.dose_mj_cm2

    # ── 6. CD Extraction from Aerial Image ──────────────────────
    # Use the aerial image directly to extract CD via intensity threshold.
    # This is the most robust approach for general use; the full resist
    # chemistry chain (dose_to_acid → PEB → development) is available
    # via resist_model="full_chem" but requires carefully tuned params.
    line_width_px = int(round(cfg.line_width_nm / (period_m / cfg.grid * 1e9)))
    if cfg.resist_model == "full_chem":
        cd, dev, nils_val, ler_nm, lwr_nm, ler_metadata = _cd_via_full_chem(
            aerial, cfg, period_m, half, line_width_px, energy_eV, progress=progress
        )
    else:
        cd, dev, nils_val = _cd_via_aerial_threshold(aerial, cfg, half, line_width_px)
        ler_metadata = None
        ler_nm = 0.0
        lwr_nm = 0.0

    return SimulationResult(
        aerial_image=aerial,
        resist_profile=dev,
        cd_nm=cd,
        nils_value=float(nils_val),
        absorber_reflectivity=absorber_reflectivity,
        ler_nm=ler_nm,
        lwr_nm=lwr_nm,
        clear_field_reflectivity=clear_field_reflectivity,
        ler_metadata=ler_metadata,
    )


def simulate_line_space(
    period_nm: float = 64.0,
    cd_nm: float = 32.0,
    dose_mj_cm2: float = 20.0,
    na: float = 0.33,
    sigma: float = 0.8,
    grid: int = 256,
    device: str = "auto",
) -> SimulationResult:
    """Convenience: run a standard line/space simulation.

    Returns
    -------
    SimulationResult
    """
    cfg = SimulationConfig(
        period_nm=period_nm,
        line_width_nm=cd_nm,
        dose_mj_cm2=dose_mj_cm2,
        na=na,
        sigma=sigma,
        grid=grid,
        device=device,
    )
    return run_simulation(cfg)
