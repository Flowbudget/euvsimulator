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


# Fit of (k, n) at M_th = 0.39 to the authors' Mack-fit curve (see module
# docstring; scratchpad b1_nxe1716.py, rms 0.042 in log10 R).
NXE1716_MACK_N = 12.76
NXE1716_PEB_K_FROM_DRM = 0.4955  # s^-1 at 90 °C with tau = 10.5 s, C = 0.0152
# Dose-scale calibration: chain dose-to-size 19.67 -> measured 11.0 mJ/cm²
# (one parameter, declared; log Fortsetzung 27).
NXE1716_DOSE_SCALE_CALIBRATION = 19.67 / 11.0


def nxe1716_config(*, calibrated_dose_scale: bool = False, **overrides) -> SimulationConfig:
    """SimulationConfig for the NXE1716 anchor (22 nm lines, 44 nm pitch, NXE3300B).

    ``calibrated_dose_scale=True`` multiplies the deprotection rate by
    ``NXE1716_DOSE_SCALE_CALIBRATION`` so that the chain prints at the measured
    11.0 mJ/cm²; with ``False`` (default) every parameter comes from the DRM
    curve or a generic source and the dose-to-size is a prediction (19.7).
    """
    k = NXE1716_PEB_K_FROM_DRM * (NXE1716_DOSE_SCALE_CALIBRATION if calibrated_dose_scale else 1.0)
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
    )
    return replace(cfg, **overrides) if overrides else cfg
