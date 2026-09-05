"""Acids per absorbed EUV photon -- the invariant that ties C, G0 and B together.

The default resist takes Dill C from Yamamoto/Sekiguchi (PROLITH fit), G0 from
Mack 2011 and B from the composition. Each is sourced on its own, but together
they imply a film quantum yield (acids per ABSORBED photon, low-dose limit)

    Phi = C * G0 / (N_ph * alpha),   N_ph = 0.68 photons/nm^2 per mJ/cm^2

that has been measured directly:

* Brainard et al. (LBNL, OSTI 1004159), Table 3 / Fig. 2: EUV-2D 2.08 (1.94 on
  re-measurement), MET-2D 1.39, XP-5496 1.45 -- 80-125 nm films, PEB 130 C.
  FQY rises roughly linearly with PAG loading (Fig. 5), i.e. values around 3
  are reached only with ultra-high PAG loading.
* Kozawa & Tagawa, J. Photopolym. Sci. Technol. 28(4) 501 (2015), Fig. 2:
  acid-generation quantum efficiency ~ 2 for anion-bound resists.

Band used here: [1.3, 3.0] for the LBNL-style yield (absorbed fraction of the
film, not the surface value). History: with the PROLITH-fitted C = 0.090 the
defaults gave 6.0; since 2026-09-06 (stage A2) C is LBNL's directly measured
0.0152 cm²/mJ for MET-2D, giving 1.0 at the surface and 1.24 LBNL-style for
their 80 nm film (measured 1.39; the 11 % gap is G0 0.2 vs the ~0.22 nm^-3
their numbers imply). The current values are pinned so that any change to C,
G0 or B is visible here.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from euvsimulator.pipeline import SimulationConfig, acids_per_absorbed_photon

FQY_BAND = (1.3, 3.0)


def test_photon_density_and_alpha_enter_as_expected():
    """Phi scales linearly with C and G0 and inversely with (A + B)."""
    base = SimulationConfig()
    phi0 = acids_per_absorbed_photon(base)
    twice_c = replace(base, dill_C=2 * base.dill_C)
    half_g0 = replace(base, pag_density_per_nm3=0.5 * base.pag_density_per_nm3)
    twice_alpha = replace(base, dill_B=2 * (base.dill_A + base.dill_B) - base.dill_A)
    assert acids_per_absorbed_photon(twice_c) == pytest.approx(2 * phi0)
    assert acids_per_absorbed_photon(half_g0) == pytest.approx(0.5 * phi0)
    assert acids_per_absorbed_photon(twice_alpha) == pytest.approx(0.5 * phi0)


def lbnl_style_yield(cfg: SimulationConfig, film_nm: float) -> float:
    """LBNL's film quantum yield: acids per photon absorbed by the WHOLE film.

    Same low-dose limit as ``acids_per_absorbed_photon`` but with the mean
    absorption over the film, (1 - exp(-alpha*d)) / d, instead of the surface
    coefficient alpha; for their 80 nm MET-2D film the two differ by 16 %.
    """
    alpha = (cfg.dill_A + cfg.dill_B) * 1e-3
    absorbed_fraction = 1.0 - math.exp(-alpha * film_nm)
    return acids_per_absorbed_photon(cfg) * alpha * film_nm / absorbed_fraction


def test_default_yield_is_pinned():
    """Today's values from the defaults (C 0.0152 cm^2/mJ, G0 0.2 nm^-3, B 4.44 um^-1)."""
    cfg = SimulationConfig()
    assert acids_per_absorbed_photon(cfg) == pytest.approx(1.007, abs=0.01)
    assert lbnl_style_yield(cfg, film_nm=80.0) == pytest.approx(1.20, abs=0.02)


def test_met2d_yield_matches_lbnl_within_20_percent():
    """LBNL Table 3, MET-2D: C 0.0152, 80 nm film, transmittance 0.71, FQY 1.39.

    Using their C and film but this project's G0 (Mack 2011, 0.2 nm^-3) and
    absorption coefficient (4.44 vs their 4.37 um^-1) reproduces the measured
    yield within 20 % (their own EUV-2D re-measurements scatter by 10 %).
    """
    cfg = SimulationConfig(dill_C=0.0152, dill_B=4.37)
    assert lbnl_style_yield(cfg, film_nm=80.0) == pytest.approx(1.39, rel=0.20)


def test_default_yield_within_measured_band():
    """Default resist, evaluated LBNL-style for the default film thickness."""
    cfg = SimulationConfig()
    lo, hi = FQY_BAND
    assert 0.8 * lo <= lbnl_style_yield(cfg, film_nm=cfg.resist_thickness_nm) <= hi


def test_prolith_c_would_put_the_yield_far_outside_the_band():
    """The pre-A2 default (PROLITH-fitted C = 0.08997) implied 6 acids per photon."""
    phi = acids_per_absorbed_photon(SimulationConfig(dill_C=0.08997))
    assert phi == pytest.approx(5.96, abs=0.05)
    assert phi > 4 * 1.39  # four times LBNL's measured MET-2D yield
