"""Full simulation pipeline — end-to-end EUV lithography simulation.

Connects all modules: mask → RCWA → aerial image → resist → CD.

Resist presets (typical SE blur sigma for different resist types):
    RESIST_PRESETS = {
        "CAR": 5.0,      # Chemically Amplified Resist (typical EUV)
        "nonCAR": 2.5,   # Non-chemically amplified / metal resist
        "HighNA": 3.0,   # High-NA EUV (thinner resist)
    }
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import torch

from euvsimulator.accel.device import select_device, set_default_dtype
from euvsimulator.aerial.abbe import aerial_from_orders, nils
from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity
from euvsimulator.resist.develop import (
    stochastic_development,
    threshold_development,
)
from euvsimulator.resist.exposure import dose_to_acid
from euvsimulator.resist.peb import reaction_diffusion_analytical
from euvsimulator.constants import HC_EV_NM
from euvsimulator.resist.stochastic import (
    extract_ler,
    extract_lwr,
    ler_estimate,
    photon_deposition_shot_noise,
)

# Resist presets — typical SE blur sigma [nm] for different resist types
RESIST_PRESETS = {
    "CAR": 5.0,  # Chemically Amplified Resist (typical EUV)
    "nonCAR": 2.5,  # Non-chemically amplified / metal resist
    "HighNA": 3.0,  # High-NA EUV (thinner resist)
}


@dataclass
class SimulationResult:
    """Results from a full pipeline simulation.

    Parameters
    ----------
    aerial_image : (G, G) float64
        Computed aerial image intensity.
    resist_profile : (G, G) float64
        Developed resist profile (0 = developed, 1 = remaining).
    cd_nm : float
        Critical dimension [nm] (0 if not measurable).
    nils_value : float
        Normalised Image Log-Slope at line edge.
    absorber_reflectivity : float
        Reflectivity of the absorber region (normalised).
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
    resist_threshold : float
        Development threshold (default: 0.5).
    grid : int
        Simulation grid size (default: 256).
    device : str
        PyTorch device (default: "auto"). Use "auto" to auto-select GPU
        if available, or "cpu"/"cuda" explicitly.
    """

    wavelength_nm: float = 13.5
    na: float = 0.33
    sigma: float = 0.8
    illumination_shape: str = "conventional"
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
    dose_mj_cm2: float = 20.0
    resist_threshold: float = 0.5
    resist_model: str = "aerial_threshold"
    resist_threshold_norm: float = 0.5
    se_blur_nm: float = 0.0
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
    # why that distinction matters). This changes full_chem path outputs;
    # it does NOT affect the aerial_threshold benchmark (dill_A/B are not
    # used on that path) so it is not a regression of the "solide
    # geprüft" reference values.
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
    dill_A: float = 0.0  # Bleachable absorption coefficient [1/µm] -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_B/C and mack_* below); Fallica et al. 2016 independently confirms the same A<<B regime (their range 0.2-0.45); see note above
    dill_B: float = 1.06  # Non-bleachable absorption coefficient [1/µm] -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_A/C and mack_* below); Fallica et al. 2016 found a higher range (4-5) for a different, undisclosed EUV-CAR formulation -- both real, resist-specific; see note above
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
    dill_C: float = 0.08997  # Photo-rate constant [cm²/mJ] -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_A/B and mack_* below); within the ~0.010-0.43 cm²/mJ range independently spanned by Fallica et al. 2016 / Kazazis et al. 2017; see note above
    #
    # dill_Q STATUS (2026-09-02, third research pass): the previous "typical
    # range 0.02-0.10 for EUV CAR" claim below was UNCITED (traced back through
    # resist/exposure.py, which also gives no source) -- flagging that
    # explicitly rather than silently inheriting an unsourced number. One real,
    # EUV-native, peer-reviewed value WAS found: Mack et al., "Stochastic
    # exposure kinetics of extreme ultraviolet photoresists: quenching model,"
    # Proc. SPIE 7972 (2011) -- their baseline Table I gives PAG Quantum
    # Efficiency phi_PAG = 0.5 (see the peb_D citation below; same table).
    # NOT adopted as the new default here, for a specific, tested reason: Q,
    # dill_C, peb_k, and mack_M_th are COUPLED (they jointly determine whether
    # the simulated resist develops at all -- see the CD=64nm "PRE-EXISTING
    # KNOWN ISSUE" note near mack_M_th below). Verified experimentally in this
    # research pass: raising Q from 0.04 to Mack et al.'s 0.5 (with every other
    # parameter at its own independently-best-cited value) does NOT produce a
    # realistic result -- it overshoots to the OPPOSITE degenerate extreme
    # (CD=0.0nm, the entire field clears) rather than a resolvable line. Ranges
    # 0.1-0.3 land somewhere between the two degenerate extremes, but picking a
    # specific point in that gap with no citation of its own would be exactly
    # the kind of ungrounded tuning this project does not want. Left at 0.04
    # (still uncited, but at least not silently swapped for an equally
    # arbitrary "improvement") pending either real experimental calibration
    # data (use `euv calibrate`) or a from-scratch, fully self-consistent
    # single-resist EUV CAR parameter set (Dill A/B/C/Q + PEB k + Mack
    # Rmax/Rmin/n/Mth all from the SAME measured resist) -- despite an
    # extensive multi-institution search (see docs/claude_code_arbeitslog.md
    # and /Users/flo/mack fits/catalog.md), no such single freely-available
    # source was found for an EUV (13.5nm) resist; the closest complete set
    # found is for a 193nm resist (see mack_* parameters below).
    dill_Q: float = 0.04  # Quantum efficiency (acid molecules per absorbed photon) -- UNCITED, see note above; do not treat the "0.02-0.10 typical" framing as sourced

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
    peb_D: float = 3.3  # Acid diffusivity [nm²/s] -- within Lavery et al. 2006's measured 2-8 nm²/s; chosen with peb_t_bake=60s to reproduce Anderson et al. 2009's measured EUV deprotection blur (see note above)
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
    peb_k: float = 0.3  # Deprotection rate constant [s⁻¹] -- UNCITED, see note above
    peb_t_bake: float = 60.0  # Bake time [s]
    peb_sigma_diff: float | None = None  # Analytical diffusion sigma [nm], optional direct override of peb_D+peb_t_bake -- see note above

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
    mack_R_max: float = 68.6  # Max development rate [nm/s] -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_A/B/C and mack_R_min/Mth/n); cross-validated in order of magnitude by Vesters et al. 2017 (174-241 nm/s) and Itani et al. 2008 (85-93 nm/s); see note above, currently has no effect on simulation output
    mack_R_min: float = 0.10  # Min development rate [nm/s] -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_A/B/C and mack_R_max/Mth/n); matches Itani et al. 2008's molecular-resist value (0.1) exactly, within Vesters et al. 2017's order of magnitude (0.012-0.017); see note above, currently has no effect on simulation output
    mack_n: float = 18.2  # Dissolution selectivity (contrast) -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_A/B/C and mack_R_max/R_min/Mth); notably steeper than Itani et al. 2008's PHS value (2.5) or Mack's generic textbook 5 -- see note above for why this is flagged, not silently trusted; see note above, currently has no effect on simulation output
    mack_M_th: float = 0.39  # Threshold inhibitor concentration -- Yamamoto et al. 2011 (EUV-native, self-consistent with dill_A/B/C and mack_R_max/R_min/n); first real EUV-native value found for this parameter (previously Mack's own generic textbook illustration, 0.5); see note above -- this IS used by the full_chem development step (unlike Rmax/Rmin/n), tested to not change the CD=64nm degeneracy (see note above and note below)

    # ─────────────────────────────────────────────────────────────────
    # PRE-EXISTING KNOWN ISSUE (confirmed, root-caused 2026-09-02, NOT
    # fixed here -- fixing it correctly requires real data, see below):
    #
    # `resist_model="full_chem"` with ALL parameters at their current
    # defaults produces a degenerate result: cd_nm == 64.0 (the entire
    # field stays "undeveloped" -- M_t never drops below mack_M_th
    # anywhere). This predates this research pass; it is NOT introduced
    # or worsened by the dill_A/B or peb_D/peb_sigma_diff corrections
    # above (those affect the optical/RCWA and diffusion-length stages
    # respectively, upstream of and independent from this failure).
    #
    # Root cause, quantified: M_t = exp(-peb_k * acid * peb_t_bake), and
    # M_t only crosses below mack_M_th when peb_k * acid_max * peb_t_bake
    # > ln(1/mack_M_th). At the ORIGINAL defaults (dill_C=0.05,
    # mack_M_th=0.5), acid_max (after PEB diffusion blur) yielded
    # peb_k*acid_max*peb_t_bake ~= 0.3-0.4, while ln(1/0.5) = 0.693 was
    # needed -- short by roughly 2x.
    #
    # UPDATE (2026-09-03, round 9): dill_C and mack_M_th above were both
    # replaced with Yamamoto et al. 2011's EUV-native, self-consistent
    # values (dill_C: 0.05 -> 0.08997; mack_M_th: 0.5 -> 0.39). Both shifts
    # individually push toward clearing (higher dill_C -> more acid;
    # lower mack_M_th -> lower bar to cross), so this was RE-TESTED
    # directly, not assumed: SimulationConfig(resist_model="full_chem")
    # with the new defaults still gives cd_nm == 64.0, identical to before.
    # The degeneracy is confirmed robust to this specific change, i.e. it
    # really is peb_k/dill_Q (still uncited, see their own notes above)
    # that is the binding constraint, not dill_C/mack_M_th -- consistent
    # with, not contradicting, the analysis below.
    #
    # This CANNOT be fixed by swapping in a single literature value for
    # just one of dill_Q, peb_k, or mack_M_th -- verified experimentally
    # in this research pass. dill_A/B/peb_D/peb_sigma_diff (optics/
    # diffusion) are now well-grounded from real EUV measurements (see
    # their own citations above), but dill_C, dill_Q, peb_k, and
    # mack_M_th are COUPLED: e.g. raising dill_Q alone from 0.04 to Mack
    # et al. 2011's real EUV-cited 0.5 (see dill_Q note above) does not
    # land on a realistic result -- it overshoots straight through to
    # the OPPOSITE degenerate extreme (cd_nm == 0.0, everything clears)
    # rather than a resolvable line, because the diffusion blur (now
    # correctly ~20nm, comparable to the 32nm half-pitch) smooths the
    # latent acid image enough that the threshold crossing is an
    # all-or-nothing event across most of the field, not a clean edge.
    #
    # The reason a single joint fix wasn't attempted here: doing so
    # without real data would mean hand-picking a point in the gap
    # between the two degenerate extremes with no citation of its own
    # -- exactly the kind of ungrounded parameter-tuning this project
    # explicitly does not want (see feedback_euvsimulator_no_compromises
    # in the maintaining assistant's memory, and the project's own
    # Grundprinzip 4). A genuinely non-compromised fix needs one of:
    #   (a) real experimental dose/focus Bossung + CD/LWR data run
    #       through this project's own `euv calibrate` command (built
    #       for exactly this joint-fit problem; no such dataset is
    #       available to this project yet), or
    #   (b) a single freely-available source giving a COMPLETE,
    #       internally self-consistent EUV-CAR (13.5nm) parameter set
    #       (Dill A/B/C/Q + PEB diffusivity/rate + Mack Rmax/Rmin/n/Mth
    #       ALL from the same measured resist).
    #
    #       UPDATE (2026-09-03, round 9): (b) is now PARTIALLY achieved.
    #       Yamamoto et al. 2011 (see dill_A/B and mack_R_max notes above,
    #       free via J-STAGE) gives a real, self-consistent, EUV-native
    #       Dill A/B/C + Mack Rmax/Rmin/Mth/n septuplet -- now adopted as
    #       the defaults above -- found via a 9-round, ~36-source search
    #       across institutional repositories (DSpace REST APIs at imec,
    #       FAU, KU Leuven), government archives (OSTI.gov), conference
    #       archives (EIPBN, the EUVL Workshop since 2008 at euvlitho.com),
    #       code/data repositories (GitHub, Zenodo, Hugging Face), and
    #       author-centric/citation-trail follow-ups (see
    #       /Users/flo/mack fits/catalog.md and
    #       docs/claude_code_arbeitslog.md for the full trail). What
    #       Yamamoto et al. does NOT cover: this codebase's own dill_Q
    #       (quantum efficiency, not part of the classic 3-parameter Dill
    #       model) and peb_k (a clean Arrhenius fit exists in the same
    #       paper, but with a unit inconsistency between its table and
    #       body text that could not be safely resolved -- see the peb_k
    #       note above). So the degeneracy below is NOT yet fixed --
    #       re-tested directly with the new dill_C/mack_M_th values,
    #       confirmed still cd_nm==64.0 -- but the search space for what's
    #       still missing has narrowed from "an entire EUV-native
    #       parameter set" to specifically "dill_Q and peb_k".
    #
    # Until (a) or (b), `resist_model="full_chem"` should be treated as
    # NOT YET SCIENTIFICALLY VALIDATED for its default parameters --
    # `resist_model="aerial_threshold"` (the default) remains the
    # solidly-tested path (see project status memory / audit/ reports).
    # ─────────────────────────────────────────────────────────────────

    # Stochastic / Shot Noise parameters
    enable_stochastic: bool = False  # Enable photon shot noise + LER/LWR
    stochastic_n_realisations: int = 1  # Number of independent noise realisations
    stochastic_develop_threshold: float = 0.3  # Development threshold for LER/LWR extraction
    stochastic_quantum_efficiency: float = 0.04  # Acid molecules per absorbed photon
    stochastic_seed: int | None = None  # RNG seed (None = random)
    # Correlation-aware large-N LER (STEP 5.1/5.2B)
    #
    # REFERENCE CONFIGURATION FOR SCIENTIFIC LER VALIDATION:
    #   se_blur_nm               = 5.0
    #   dose_mj_cm2              = 40.0
    #   stochastic_ler_grid_y    = 4096
    #   stochastic_ler_estimator = "large_n"
    #
    # Note: the software default se_blur_nm=0.0 is technically valid
    # (white noise -> N_eff = N) but is NOT the scientific reference.
    # The reference configuration was used for the internal LER audits
    # (N_eff ~= 59, LER ~= 0.07 nm at 40 mJ/cm2); it is a reference for
    # internal scientific validation, NOT yet experimentally validated.
    stochastic_ler_grid_y: int = 4096  # Requested Y dimension of the stochastic LER field
    stochastic_ler_estimator: str = "large_n"  # "large_n" | "legacy"
    # Stochastic development (STEP 5.3): event-based dissolution noise
    # on the local driving force of the stochastic-path latent image.
    development_stochasticity: bool = False  # OFF = deterministic threshold development
    development_strength: float = 1.0  # dimensionless dissolution events per pixel at drive=1
    development_correlation_nm: float = 0.5  # molecular aggregate correlation length [nm]

    # Mask-3D / RCWA parameters (Phase 4)
    use_rcwa: bool = False  # Use full RCWA instead of thin-mask analytic
    absorber_taper_deg: float = 90.0  # Sidewall angle from horizontal (90 = vertical)
    mask_undercut_nm: float = 0.0  # Undercut at absorber base [nm]
    mask_sidewall_roughness_nm: float = 0.0  # Sidewall roughness sigma [nm]

    def __post_init__(self):
        # Validate dose
        if self.dose_mj_cm2 <= 0:
            raise ValueError(f"dose_mj_cm2 must be > 0, got {self.dose_mj_cm2}")
        # Validate resist parameters
        if self.dill_C <= 0:
            raise ValueError("dill_C must be > 0")
        if self.dill_Q <= 0:
            raise ValueError("dill_Q must be > 0")
        if self.peb_k <= 0:
            raise ValueError("peb_k must be > 0")
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
            if not (0 < self.stochastic_develop_threshold < 1):
                raise ValueError("stochastic_develop_threshold must be in (0, 1)")
            if self.stochastic_quantum_efficiency <= 0:
                raise ValueError("stochastic_quantum_efficiency must be > 0")
        # LER estimator configuration (no artificial upper bound on grid_y)
        if self.stochastic_ler_grid_y < 1:
            raise ValueError("stochastic_ler_grid_y must be a positive integer")
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
    nominal_dose = 20.0
    threshold_val = (
        cfg.resist_threshold_norm * dc_level * (nominal_dose / max(cfg.dose_mj_cm2, 1e-9))
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


def _cd_via_full_chem(
    aerial: torch.Tensor,
    cfg: SimulationConfig,
    period_m: float,
    half: int,
    line_width_px: int,
    energy_eV: float,
) -> tuple[float, torch.Tensor, float, float, float]:
    """Extract CD via full resist chemistry chain (dose → acid → PEB → develop).

    Uses the Dill ABC exposure model, reaction-diffusion PEB, and threshold
    development.  All parameters come from cfg (with defaults in SimulationConfig).
    Optionally applies photon shot noise and extracts LER/LWR.
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

    # NILS on the blurred dose map (what resist actually sees).
    # Same Optical-CD threshold convention as aerial_threshold:
    #   thr = resist_threshold_norm * mean(field) * (20 / dose)
    # so NILS and CD share one printed edge even in the full_chem path.
    dc_level = float(dose_map_blurred.mean())
    nominal_dose = 20.0
    threshold_val = (
        cfg.resist_threshold_norm * dc_level * (nominal_dose / max(cfg.dose_mj_cm2, 1e-9))
    )
    nils_val = nils(dose_map_blurred, half, line_width_px, dx_nm, threshold=threshold_val)

    acid = dose_to_acid(
        dose_map_blurred,
        C=cfg.dill_C,
        Q=cfg.dill_Q,
        sigma_blur=cfg.se_blur_nm,  # kept for compatibility but apply_blur=False below
        dx=dx_nm,
        apply_blur=False,
    )
    inhib_in = torch.ones_like(acid)
    _, inhib = reaction_diffusion_analytical(
        acid,
        inhib_in,
        D=cfg.peb_D,
        k=cfg.peb_k,
        t_bake=cfg.peb_t_bake,
        sigma_diff=cfg.peb_sigma_diff,
        dx=dx_nm,
    )
    # Resist-Profil für Visualisierung (1 = undeveloped/remaining)
    # Mack threshold: use M_th from config
    dev_chem = threshold_development(inhib, threshold=cfg.mack_M_th)

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
        acid_fields = []
        for _ in range(cfg.stochastic_n_realisations):
            d_eff = photon_deposition_shot_noise(
                stoch_dose,
                se_blur_nm=cfg.se_blur_nm,
                dx_nm=dx_nm,
                photon_energy_eV=energy_eV,  # from wavelength via HC_EV_NM
                dose_to_energy_factor=6.241509074e15,
                rng=rng,
            )
            acid_noisy = dose_to_acid(
                d_eff,
                C=cfg.dill_C,
                Q=cfg.dill_Q,
                apply_blur=False,
            )
            if cfg.development_stochasticity:
                # STEP 5.3: event-based stochastic development on the
                # local driving force of the stochastic latent image.
                # OFF mode (default) keeps the deterministic threshold
                # development bitwise unchanged.
                developed = stochastic_development(
                    acid_noisy,
                    threshold=cfg.stochastic_develop_threshold,
                    strength=cfg.development_strength,
                    correlation_nm=cfg.development_correlation_nm,
                    dx=dx_nm,
                    rng=rng,
                )
            else:
                developed = (acid_noisy > cfg.stochastic_develop_threshold).float()
            if use_large_n:
                dev_fields.append(developed)
                acid_fields.append(acid_noisy)
            else:
                ler_vals.append(
                    extract_ler(
                        developed,
                        threshold=cfg.stochastic_develop_threshold,
                        dx=dx_nm,
                        intensity=acid_noisy,
                    )
                )
            lwr_vals.append(
                extract_lwr(
                    developed,
                    threshold=cfg.stochastic_develop_threshold,
                    dx=dx_nm,
                    intensity=acid_noisy,
                )
            )

        if use_large_n:
            # One LER estimate per realization (spatial N_eff within each
            # field), aggregated over seeds (between-seed SE/CI).
            est = ler_estimate(
                dev_fields,
                threshold=cfg.stochastic_develop_threshold,
                dx=dx_nm,
                intensity=acid_fields,
                edge="both",
                estimator="large_n",
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
    else:
        longest = max(runs, key=lambda r: r[1] - r[0])
        lidx, ridx = longest
        cd_nm = (ridx - lidx + 1) * dx_nm
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
    **kwargs,
) -> SimulationResult:
    """Run a full end-to-end EUV lithography simulation.

    Parameters
    ----------
    cfg : SimulationConfig, optional
        Simulation configuration.  Omit for defaults.
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
        from euvsimulator.mask3d.geometry import build_permittivity_profile, MaskLayer, MaskStack
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
        # Apply taper/undercut if specified (stored in cfg, not yet implemented)
        if cfg.absorber_taper_deg != 90.0 or cfg.mask_undercut_nm != 0.0:
            pass  # Taper/undercut grid geometry is not yet implemented in build_permittivity_profile

        mask = MaskStack(
            absorber_layers=layers,
            multilayer_bilayers=cfg.ml_n_bilayers,
            d_mo_nm=cfg.ml_d_mo_nm,
            d_si_nm=cfg.ml_d_si_nm,
            substrate_nk=complex(n_si, k_si),
            period_nm=cfg.period_nm,
            line_width_nm=cfg.line_width_nm,
        )

        eps_profile, thicknesses, eps_sub = build_permittivity_profile(
            mask, n_samples=1024, device=device
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
            period_m,
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
            period_m,
            n_incident=torch.tensor(
                [1.0 + 0.0j, 1.0 + 0.0j], dtype=torch.complex128, device=device
            ),
            ml_stack=ml_stack,  # P1-2: order-diagonal ML operator
        )

        # Unpolarized illumination: TE and TM are orthogonal incoherent
        # polarization states.  The physical average is applied AFTER
        # aerial (intensity) reconstruction, NOT on the complex fields
        # (P1 fix, 2026-08-31).  Intensity maps are averaged below.
        solver_m = torch.arange(-cfg.n_rcwa_orders // 2, cfg.n_rcwa_orders // 2 + 1, device=device)
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
        )
        aerial = (aerial_te + aerial_tm) / 2.0
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
        )

    # Normalise to dose (absolute intensity scaling, NOT max-normalisation).
    # The threshold is a FIXED fraction of the nominal-dose intensity, so the
    # CD becomes dose-dependent (higher dose -> narrower line for positive resist).
    aerial = aerial * cfg.dose_mj_cm2

    # ── 6. CD Extraction from Aerial Image ──────────────────────
    # Use the aerial image directly to extract CD via intensity threshold.
    # This is the most robust approach for general use; the full resist
    # chemistry chain (dose_to_acid → PEB → development) is available
    # via resist_model="full_chem" but requires carefully tuned params.
    line_width_px = int(round(cfg.line_width_nm / (period_m / cfg.grid * 1e9)))
    if cfg.resist_model == "full_chem":
        cd, dev, nils_val, ler_nm, lwr_nm, ler_metadata = _cd_via_full_chem(
            aerial, cfg, period_m, half, line_width_px, energy_eV
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
