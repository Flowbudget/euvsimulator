"""Named-resist anchors: configurations that reproduce one published data set.

Each preset states, parameter by parameter, whether the value is measured on
THAT resist, taken from a generic source, or calibrated -- so that a result
obtained with it can be read for what it is.

NXE1716 (imec / Vesters 2017, 2019)
-----------------------------------
The only freely available EUV chemically amplified resist with BOTH a
dissolution-rate contrast curve (DRM, flood exposure, Vesters et al. JPST
30(6) 675, Fig. 6) AND patterning data at the same PEB (thesis Table 4.2:
22 nm lines at 44 nm pitch on an NXE3300B, dose-to-size 11.0 mJ/cm², LWR
6.7 nm 3σ SEM-biased). The digitised curve ships as package data
(``data/anchors/vesters2017_nxe1716.json``).

Parameter provenance:

* ``mack_R_max``/``mack_R_min`` -- plateaus of the authors' Mack fit (245 /
  0.0186 nm/s); measured on NXE1716.
* ``mack_n``, ``peb_k`` -- fitted here to the authors' fit curve with this
  chain's form R = Mack(exp(-k·t_eff·H(E))), H = 1 - exp(-C·E), at fixed
  ``mack_M_th`` (the triple (k, M_th, n) is degenerate on a flood curve;
  the line prediction does not depend on the split). rms 0.04 in log10 R.
* ``dill_C`` 0.0152 (LBNL MET-2D), ``dill_B`` 4.44 (generic PHS), ``peb_D``
  4.2 (Kang 2010 at 90 °C -- the PEB temperature of this data set),
  ``peb_acid_lifetime_s`` 10.5 (Yamamoto at 110 °C; unknown at 90 °C),
  ``se_blur_nm`` 2.5 (Thackeray) -- generic, NOT measured on NXE1716.
* Optics: NA 0.33, dipole 90X sigma 0.62/0.90 (thesis Sec. 4.3.2); film 35 nm
  on AL412; develop time 30 s (imec's recipe time is not published).

Status (log Fortsetzung 27, 2026-09-06): with the DRM dose scale and no free
parameter the chain prints 22 nm lines at 19.7 mJ/cm² instead of 11.0
(factor 1.79) -- an open discrepancy that neither blur nor develop time
explains. ``NXE1716_DOSE_SCALE_CALIBRATION`` rescales k so that the chain's
dose-to-size is 11 mJ/cm²; it is a CALIBRATION and is labelled as such. At
that dose the photon-shot-noise LWR is 10.9 nm 3σ with the default 9.4 nm PEB
blur and 4.8 nm with a 5 nm blur, against 6.7 nm measured (SEM-biased): the
blur of this resist at 90 °C is not published, so the anchor brackets the
measurement rather than validating or falsifying the noise model.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from importlib import resources

import numpy as np

from euvsimulator.pipeline import SimulationConfig

ANCHOR_FILE = "vesters2017_nxe1716.json"


def load_nxe1716_anchor() -> dict:
    """The digitised Vesters 2017 Fig. 6 data and the thesis patterning row."""
    with resources.files("euvsimulator.data.anchors").joinpath(ANCHOR_FILE).open() as f:
        return json.load(f)


def mack_rate(M, R_max: float, R_min: float, M_th: float, n: float):
    """Mack 1987 development rate R(M) (same form as resist/develop.MackModel)."""
    M = np.asarray(M, dtype=float)
    a = (n + 1.0) / (n - 1.0) * (1.0 - M_th) ** n
    return R_max * (a + 1.0) * (1.0 - M) ** n / (a + (1.0 - M) ** n) + R_min


def flood_rate(cfg: SimulationConfig, dose_mj_cm2):
    """Surface dissolution rate after a uniform (flood) exposure and the PEB,
    without diffusion (uniform field) -- the quantity a DRM contrast curve
    measures, evaluated with the chain's own laws.
    """
    E = np.asarray(dose_mj_cm2, dtype=float)
    H = 1.0 - np.exp(-cfg.dill_C * E)
    tau = cfg.peb_acid_lifetime_s
    t_eff = cfg.peb_t_bake if tau is None else tau * (1.0 - math.exp(-cfg.peb_t_bake / tau))
    M = np.exp(-cfg.peb_k * t_eff * H)
    return mack_rate(M, cfg.mack_R_max, cfg.mack_R_min, cfg.mack_M_th, cfg.mack_n)


def flood_rate_quenched(cfg: SimulationConfig, dose_mj_cm2):
    """Like :func:`flood_rate` but through the chain's quenching PEB step
    (Mack 2011 second-order neutralisation with k_Q*G0, acid lifetime,
    uniform quencher q = Q/G0) -- the flood response of a resist WITH base.
    """
    import torch

    from euvsimulator.resist.peb import reaction_diffusion_with_quenching

    E = np.atleast_1d(np.asarray(dose_mj_cm2, dtype=float))
    h = torch.tensor(1.0 - np.exp(-cfg.dill_C * E), dtype=torch.float64)
    h = h.view(-1, 1, 1).expand(-1, 2, 2).clone()
    q = cfg.quencher_density_per_nm3 / cfg.pag_density_per_nm3
    _, _, M = reaction_diffusion_with_quenching(
        h,
        float(q),
        torch.ones_like(h),
        D=0.0,
        k=cfg.peb_k,
        quench_rate=cfg.acid_base_quench_rate_nm3_per_s,
        t_bake=cfg.peb_t_bake,
        sigma_diff=0.0,
        dx=1.0,
        pag_density=cfg.pag_density_per_nm3,
        acid_lifetime_s=cfg.peb_acid_lifetime_s,
    )
    return mack_rate(M[:, 0, 0].numpy(), cfg.mack_R_max, cfg.mack_R_min, cfg.mack_M_th, cfg.mack_n)


# Two-curve quencher fit (log Fortsetzung 29, 2026-09-06): NXE1716 and NXE1717
# differ only in quencher loading (2:1, Vesters 2017). Shared deprotection rate
# k and quencher ratio, per-curve Mack n and plateaus (the quencher also
# changes dissolution, Vesters: "plasticizing effect"); M_th 0.39 fixed
# (degenerate with k), C 0.0152, G0 0.2, k_Q 12.6 nm^3/s (Osaka 2025; the
# neutralisation is complete, k_Q*G0*t_eff = 26, so its value hardly matters),
# tau 10.5 s. rms 0.031 / 0.063 in log10 R. The relative quencher loading is
# the robust outcome (0.13-0.15 across tau choices); the Mack n values are
# model-dependent (a single curve cannot separate quencher from n).
NXE1716_QUENCHER_FIT = {
    "peb_k": 1.8207,
    "mack_n_1716": 4.48,
    "mack_n_1717": 7.38,
    "q_rel_1716": 0.1481,  # Q/G0 -> Q = 0.0296 nm^-3 at G0 = 0.2
    "q_rel_1717": 0.1481 / 2.0,  # the 2:1 ratio is a constraint of the fit
    "acid_base_quench_rate_nm3_per_s": 12.6,
    "peb_acid_lifetime_s": 10.5,
}


# Fit of (k, n) at M_th = 0.39 to the authors' Mack-fit curve (see module
# docstring; scratchpad b1_nxe1716.py, rms 0.042 in log10 R).
NXE1716_MACK_N = 12.76
NXE1716_PEB_K_FROM_DRM = 0.4955  # s^-1 at 90 °C with tau = 10.5 s, C = 0.0152
# Dose-scale calibration: chain dose-to-size 19.67 -> measured 11.0 mJ/cm²
# (one parameter, declared; log Fortsetzung 27).
NXE1716_DOSE_SCALE_CALIBRATION = 19.67 / 11.0


def nxe1716_config(
    *, calibrated_dose_scale: bool = False, explicit_quencher: bool = False, **overrides
) -> SimulationConfig:
    """SimulationConfig for the NXE1716 anchor (22 nm lines, 44 nm pitch, NXE3300B).

    ``calibrated_dose_scale=True`` multiplies the deprotection rate by
    ``NXE1716_DOSE_SCALE_CALIBRATION`` so that the chain prints at the measured
    11.0 mJ/cm²; with ``False`` (default) every parameter comes from the DRM
    curve or a generic source and the dose-to-size is a prediction (19.7).
    ``explicit_quencher=True`` uses the two-curve fit ``NXE1716_QUENCHER_FIT``
    (quencher as a real species, Q = 0.030 nm^-3) instead of the effective
    single-curve kinetics; the dose-to-size is the same 19.7 (the quencher is
    subtracted alike in flood and pattern, log Fortsetzung 29).
    """
    k = NXE1716_PEB_K_FROM_DRM * (NXE1716_DOSE_SCALE_CALIBRATION if calibrated_dose_scale else 1.0)
    if explicit_quencher:
        f = NXE1716_QUENCHER_FIT
        k = f["peb_k"] * (NXE1716_DOSE_SCALE_CALIBRATION if calibrated_dose_scale else 1.0)
        overrides = {
            "mack_n": f["mack_n_1716"],
            "quencher_density_per_nm3": f["q_rel_1716"] * 0.2,
            "acid_base_quench_rate_nm3_per_s": f["acid_base_quench_rate_nm3_per_s"],
            "peb_acid_lifetime_s": f["peb_acid_lifetime_s"],
            **overrides,
        }
    cfg = SimulationConfig(
        resist_model="full_chem",
        period_nm=44.0,
        line_width_nm=22.0,
        grid=256,
        na=0.33,
        illumination_shape="dipole",
        sigma=0.90,
        sigma_inner=0.62,
        pole_opening_deg=90.0,
        mack_R_max=245.0,
        mack_R_min=0.0186,
        mack_M_th=0.39,
        mack_n=NXE1716_MACK_N,
        peb_k=k,
        peb_t_bake=60.0,
        resist_thickness_nm=35.0,
        develop_time_s=30.0,
        dose_mj_cm2=11.0,
        # imec biased CD-SEM protocol (thesis Sec. 5.3): 5.38 nm y-pixels, 5.5 um images
        ler_passband_nm=(10.8, 5500.0),
    )
    return replace(cfg, **overrides) if overrides else cfg


# ---------------------------------------------------------------------------
# MET-2D / XP 5271 (Rohm and Haas), assembled from four measurement groups
# ---------------------------------------------------------------------------
MET2D_ANCHOR_FILE = "met2d_xp5271.json"


def load_met2d_anchor() -> dict:
    """LBNL (C, FQY), Sekiguchi 2011 Table 6 (B, Mack), Anderson/Naulleau 2008
    (blur, E-size, LER) for the same commercial resist; see the JSON for the
    per-entry provenance and process conditions.
    """
    with resources.files("euvsimulator.data.anchors").joinpath(MET2D_ANCHOR_FILE).open() as f:
        return json.load(f)


# Deprotection blur measured on XP 5271-D at PEB 120 C / 90 s (Anderson &
# Naulleau 2008, contact-hole metric, 23.8 nm; a width, read as FWHM ->
# sigma = 23.8 / 2.355). The corner metric gives 34.8 nm (sigma 14.8).
MET2D_BLUR_CONTACT_SIGMA_NM = 23.8 / 2.354820045
MET2D_BLUR_CORNER_SIGMA_NM = 34.8 / 2.354820045


def met2d_config(*, blur_metric: str = "contact", **overrides) -> SimulationConfig:
    """SimulationConfig for the MET-2D anchor: 50 nm 1:1 lines on the Berkeley
    MET (NA 0.3, annular sigma 0.35-0.55), 80 nm film, PEB 120 C / 90 s,
    develop 45 s (Anderson & Naulleau 2008, Table I).

    Provenance: Mack R_max/R_min/M_th/n and dill_B from Sekiguchi 2011 Table 6
    (EUV MET-2D, PEB 110 C); dill_C from LBNL (0.0152); the PEB blur is SET
    DIRECTLY from the measured deprotection blur (peb_sigma_diff), so peb_D and
    the acid lifetime do not enter the blur. The deprotection rate is NOT
    sourced for this resist in this chain's form (Sekiguchi's PROLITH
    amplification pair is tied to their C = 0.090 and to PROLITH's two-term
    PEB model); the dose scale therefore has to be calibrated to the measured
    E-size (12.5 mJ/cm^2) before any LER prediction -- see
    tests/test_met2d_anchor.py and the log (Fortsetzung 30).
    """
    sigma = MET2D_BLUR_CONTACT_SIGMA_NM if blur_metric == "contact" else MET2D_BLUR_CORNER_SIGMA_NM
    cfg = SimulationConfig(
        resist_model="full_chem",
        period_nm=100.0,
        line_width_nm=50.0,
        grid=256,
        na=0.30,
        illumination_shape="annular",
        sigma=0.55,
        sigma_inner=0.35,
        mack_R_max=170.2,
        mack_R_min=0.028,
        mack_M_th=0.518,
        mack_n=18.96,
        dill_B=5.21,
        peb_sigma_diff=sigma,
        peb_t_bake=90.0,
        resist_thickness_nm=80.0,
        develop_time_s=45.0,
        dose_mj_cm2=12.5,
        # Anderson & Naulleau 2008, Sec. III C: LER passband 10-834 nm periods
        ler_passband_nm=(10.0, 834.0),
    )
    return replace(cfg, **overrides) if overrides else cfg
