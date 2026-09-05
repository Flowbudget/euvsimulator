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

Band used here: [1.3, 3.0]. The defaults give ~6.0, i.e. C and G0 are not
consistent with each other (plan stage A2 decides which one moves); until then
the band test is a strict xfail and the current value is pinned so that any
change to C, G0 or B is visible here.
"""

from __future__ import annotations

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


def test_default_yield_is_pinned():
    """Today's value from the defaults (C 0.090 cm^2/mJ, G0 0.2 nm^-3, B 4.44 um^-1)."""
    assert acids_per_absorbed_photon(SimulationConfig()) == pytest.approx(5.96, abs=0.05)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Defaults imply ~6.0 acids per absorbed photon; measured FQY is 1.4-2.1 "
        "(LBNL Table 3) / ~2 (Kozawa). C (PROLITH fit) and G0 (Mack 2011) come "
        "from different resists -- resolved in plan stage A2."
    ),
)
def test_default_yield_within_measured_band():
    lo, hi = FQY_BAND
    assert lo <= acids_per_absorbed_photon(SimulationConfig()) <= hi


def test_yamamoto_pag_loading_does_not_rescue_the_band():
    """With Yamamoto's 3.1 mol% PAG (~0.15 nm^-3) the yield is still ~4.5 > 3."""
    phi = acids_per_absorbed_photon(SimulationConfig(pag_density_per_nm3=0.15))
    assert phi == pytest.approx(4.47, abs=0.05)
    assert phi > FQY_BAND[1]
