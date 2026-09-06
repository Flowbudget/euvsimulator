"""Temperature dependence of the PEB kinetics from a measured data set.

Yamamoto et al. 2011 (JPST 24(4) 405, Fig. 3) measured the protection ratio
P(t) of Polymer A during the PEB at seven temperatures, 80-140 C, after a
1.4 mJ/cm^2 flood exposure. Each curve was fitted with this chain's law

    P(t) = exp(-k*H0 * tau * (1 - exp(-t/tau)))

giving the deprotection rate k (per unit relative acid, for C = 0.0152) and
the acid lifetime tau at each temperature (data/anchors/
yamamoto2011_fig3_polymerA.json, log Fortsetzung 37). The Arrhenius plot has
two regions (reaction-controlled below ~110 C, Ea = 103 kJ/mol; diffusion-
controlled above, 38 kJ/mol -- the Byers-Petersen behaviour Yamamoto
describes), so no single Arrhenius law is used: k and tau are interpolated
log-linearly in 1/T between the measured temperatures and clamped to the
measured range 80-140 C.

The acid diffusivity D is NOT part of this: Kang et al. 2010 give D = 4.2
nm^2/s at 90 C only (their Arrhenius extrapolation is unusable, pipeline.py
peb_D note), so D stays a separate, temperature-independent parameter.
"""

from __future__ import annotations

import bisect
import json
import math
from functools import lru_cache
from importlib import resources

ANCHOR_FILE = "yamamoto2011_fig3_polymerA.json"


@lru_cache(maxsize=1)
def _table() -> tuple[list[float], list[float], list[float]]:
    with resources.files("euvsimulator.data.anchors").joinpath(ANCHOR_FILE).open() as f:
        d = json.load(f)
    per_t = d["chain_fits"]["per_temperature"]
    temps = sorted(float(t) for t in per_t)
    k = [per_t[f"{int(t)}"]["k_per_s_at_C_0.0152"] for t in temps]
    tau = [per_t[f"{int(t)}"]["tau_s"] for t in temps]
    return temps, k, tau


def _interp_log_inv_t(temp_c: float, temps: list[float], values: list[float]) -> float:
    t = min(max(temp_c, temps[0]), temps[-1])
    if t <= temps[0]:
        return values[0]
    if t >= temps[-1]:
        return values[-1]
    i = bisect.bisect_right(temps, t) - 1
    x0, x1 = 1.0 / (temps[i] + 273.15), 1.0 / (temps[i + 1] + 273.15)
    x = 1.0 / (t + 273.15)
    w = (x - x0) / (x1 - x0)
    return math.exp((1.0 - w) * math.log(values[i]) + w * math.log(values[i + 1]))


def yamamoto_polymer_a_kinetics(temp_c: float, dill_C: float = 0.0152) -> tuple[float, float]:
    """(k [1/s], tau [s]) of Yamamoto 2011 Polymer A at ``temp_c`` (80-140 C, clamped).

    k is per unit relative acid and therefore tied to the Dill C that defines
    the acid fraction at the 1.4 mJ/cm^2 flood: it is rescaled from the fit's
    C = 0.0152 by preserving k*H0 (see pipeline.py peb_k for why only k*H0 is
    measured).
    """
    temps, ks, taus = _table()
    k = _interp_log_inv_t(temp_c, temps, ks)
    tau = _interp_log_inv_t(temp_c, temps, taus)
    h0_fit = 1.0 - math.exp(-0.0152 * 1.4)
    h0 = 1.0 - math.exp(-dill_C * 1.4)
    return k * h0_fit / h0, tau


@lru_cache(maxsize=1)
def _table_nist_law() -> tuple[list[float], list[float], list[float]]:
    with resources.files("euvsimulator.data.anchors").joinpath(ANCHOR_FILE).open() as f:
        d = json.load(f)
    per_t = d["chain_fits_nist_law"]["per_temperature"]
    temps = sorted(float(t) for t in per_t)
    kph0 = [per_t[f"{int(t)}"]["kP_H0_per_s"] for t in temps]
    kt = [per_t[f"{int(t)}"]["kT_per_s"] for t in temps]
    return temps, kph0, kt


def yamamoto_polymer_a_kinetics_nist_law(
    temp_c: float, dill_C: float = 0.0152
) -> tuple[float, float]:
    """(k [1/s per relative acid], k_trap [1/s]) of Polymer A at ``temp_c`` for the
    concurrent reaction-diffusion PEB (:func:`euvsimulator.resist.peb.
    reaction_diffusion_pde`), from the fits of the same Fig. 3 curves with the
    Kang/NIST law dphi/dt = k h (1-phi), dh/dt = -k_trap h phi (data file,
    ``chain_fits_nist_law``). k is rescaled from the fit's C by preserving
    k*H0, as in :func:`yamamoto_polymer_a_kinetics`.
    """
    temps, kph0s, kts = _table_nist_law()
    kph0 = _interp_log_inv_t(temp_c, temps, kph0s)
    k_trap = _interp_log_inv_t(temp_c, temps, kts)
    h0 = 1.0 - math.exp(-dill_C * 1.4)
    return kph0 / h0, k_trap
