"""Structural uncertainty bands for a calibrated resist (2.1, 2026-09-06).

A fit to a wafer FEM pins the parameters of ONE model structure. Two
structural choices of the chain are not decided by any freely available
measurement and move printed results by up to a factor 2 (docs/physics.md
Sec. 7): the acid-loss law during the PEB (first-order lifetime, the
``"analytical"`` model, versus trapping by deprotected sites, the
``"reaction_diffusion"`` model) and the size of the unit that dissolves as a
whole (``dissolution_cell_nm``, bracketed 1-5 nm by Schmid/Willson 2001 and
Thackeray 2010). This module evaluates the calibrated chain at the corners of
those choices and reports the resulting band of dose-to-size and roughness,
so that a prediction is handed over with the uncertainty the sources leave,
not as a single number. Bootstrap confidence intervals of the fitted
parameters (calibrate.bootstrap_fit) are a separate, statistical band.

The two laws need different deprotection rates for the same flood curve
(Yamamoto 2011 Fig. 3 at 110 C: k = 10.947 1/s with the first-order lifetime,
8.929 1/s with trapping; pipeline.PEB_K_DEFAULT_PER_LAW). The corners
therefore swap the law together with its k: a default k becomes the other
law's default, an explicit (calibrated) k is carried over by the ratio of the
two fits, and with ``peb_temperature_c`` both laws take that temperature's
fits. Until 2026-10 the trapping corner ran with the first-order law's k.

Roughness values are simulated (no SEM bias); compare with unbiased
measurements or add the metrology's bias (Lorusso/Mack 2018).
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Callable, Dict, Optional

from euvsimulator.pipeline import (
    PEB_K_DEFAULT_PER_LAW,
    DefaultPebK,
    SimulationCancelledError,
    SimulationConfig,
    run_simulation,
)

# progress(fraction, label) -> keep going?  (GUI jobs; None = no reporting)
BandsProgress = Callable[[float, str], bool]

PEB_LAWS = ("analytical", "reaction_diffusion")
DISSOLUTION_CELLS_NM = (1.0, 4.3)


def peb_k_under_law(base: Dict[str, Any], law: str) -> Dict[str, Any]:
    """SimulationConfig keywords that run ``base``'s resist under the PEB ``law``.

    ``base["peb_model"]`` (default ``"analytical"``) names the law under which
    ``base["peb_k"]`` was obtained. Returns ``peb_model=law`` plus, where it
    must change, the k of the same resist under ``law``:

    * no peb_k, or the unset default (:class:`~euvsimulator.pipeline.DefaultPebK`):
      nothing, SimulationConfig resolves the default of ``law``;
    * ``peb_temperature_c`` set: nothing, SimulationConfig takes both laws'
      fits at that temperature;
    * an explicit k under the other law: k times the ratio of the two laws'
      fits to the same 110 C flood curve (8.929/10.947 towards the trapping
      law, its inverse back). k_trap stays the base's value (default:
      Polymer A's 0.2076 1/s).
    """
    if law not in PEB_LAWS:
        raise ValueError(f"law must be one of {PEB_LAWS}, got {law!r}")
    base_law = base.get("peb_model", "analytical")
    if base_law not in PEB_LAWS:
        raise ValueError(f"base peb_model must be one of {PEB_LAWS}, got {base_law!r}")
    out: Dict[str, Any] = {"peb_model": law}
    k = base.get("peb_k")
    if (
        law == base_law
        or k is None
        or isinstance(k, DefaultPebK)
        or base.get("peb_temperature_c") is not None
    ):
        return out
    out["peb_k"] = k * PEB_K_DEFAULT_PER_LAW[law] / PEB_K_DEFAULT_PER_LAW[base_law]
    return out


def _dose_to_size(
    make_cfg: Callable[..., SimulationConfig],
    target_nm: float,
    lo: float,
    hi: float,
    rtol: float = 1e-3,
) -> float:
    """Dose [mJ/cm2] at which the printed CD falls to target_nm.

    The CD falls with dose.  NaN unless cd(lo) > target_nm >= cd(hi).  The
    default bracket 0.3-60 spans a factor 200, so the bisection is geometric
    and stops at hi/lo <= 1 + rtol; the returned geometric midpoint is then
    within rtol/2 of the crossing.  The former 9 linear steps resolved only
    +-0.058 mJ/cm2 (+9 % at the trapping law's 0.54 mJ/cm2) and returned a
    dose just above lo when the crossing lay below lo.
    """
    if not 0.0 < lo < hi:
        raise ValueError(f"need 0 < dose_lo < dose_hi, got {lo} and {hi}")
    if run_simulation(make_cfg(dose_mj_cm2=hi)).cd_nm > target_nm:
        return float("nan")  # does not print within the search range
    if run_simulation(make_cfg(dose_mj_cm2=lo)).cd_nm <= target_nm:
        return float("nan")  # already at or below size at lo: crossing below the range
    while hi / lo > 1.0 + rtol:
        mid = math.sqrt(lo * hi)
        if run_simulation(make_cfg(dose_mj_cm2=mid)).cd_nm > target_nm:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def structural_bands(
    base: Dict[str, Any],
    *,
    target_cd_nm: float,
    dose_lo: float = 0.3,
    dose_hi: float = 60.0,
    grid: int = 128,
    rows: int = 1024,
    seeds: tuple[int, ...] = (1, 2, 3),
    cells_nm: tuple[float, ...] = DISSOLUTION_CELLS_NM,
    progress: Optional[BandsProgress] = None,
) -> Dict[str, Any]:
    """Dose-to-size and 3-sigma LWR of the calibrated chain under both PEB laws
    and both dissolution-unit sizes.

    ``base``: SimulationConfig keyword arguments of the calibrated resist
    (period, line width, film, Mack, exposure, PEB). ``base["peb_model"]``
    (default ``"analytical"``) is the law its kinetics belong to; each corner
    runs its own law with the k from :func:`peb_k_under_law`. Returns a dict
    with the per-corner values, the k each law ran with and min/max bands;
    NaN where a corner does not print or its dose-to-size lies outside
    [dose_lo, dose_hi]. The LWR corners run the analytical law.
    ``progress(fraction, label)`` is called before each corner; returning
    ``False`` raises :class:`SimulationCancelledError`.
    """
    n_steps = len(PEB_LAWS) + 1 + len(cells_nm)
    step = 0

    def tick(label: str) -> None:
        nonlocal step
        if progress is not None and not progress(step / n_steps, label):
            raise SimulationCancelledError("cancelled by the progress hook")
        step += 1

    law_kw = {law: peb_k_under_law(base, law) for law in PEB_LAWS}

    def make(law: str, **over) -> SimulationConfig:
        kw = dict(base)
        kw.update(resist_model="full_chem", grid=grid)
        kw.update(law_kw[law])
        kw.update(over)
        return SimulationConfig(**kw)

    d2s: Dict[str, float] = {}
    for law in PEB_LAWS:
        tick(f"dose-to-size, PEB law {law}")
        d2s[law] = _dose_to_size(
            lambda dose_mj_cm2, law=law: make(law, dose_mj_cm2=dose_mj_cm2),
            target_cd_nm,
            dose_lo,
            dose_hi,
        )

    lwr: Dict[str, float] = {}
    ref = d2s["analytical"]
    if ref == ref:  # not NaN

        def lwr_at(**over) -> float:
            vals = []
            for s in seeds:
                r = run_simulation(
                    make(
                        "analytical",
                        dose_mj_cm2=ref,
                        enable_stochastic=True,
                        stochastic_n_realisations=1,
                        stochastic_ler_grid_y=rows,
                        stochastic_seed=s,
                        **over,
                    )
                )
                vals.append(3.0 * r.lwr_nm)
            return statistics.mean(vals)

        tick("LWR, photon shot noise")
        lwr["photon_shot_noise"] = lwr_at()
        for a in cells_nm:
            tick(f"LWR, dissolution cell {a:g} nm")
            lwr[f"dissolution_cell_{a:g}_nm"] = lwr_at(
                development_stochasticity=True, dissolution_cell_nm=a
            )

    finite_d2s = [v for v in d2s.values() if v == v]
    finite_lwr = [v for v in lwr.values() if v == v]
    # the k each law ran with, as SimulationConfig resolved it (a law default,
    # a peb_temperature_c fit or the carried-over explicit k)
    k_per_law = {law: float(make(law, dose_mj_cm2=1.0).peb_k) for law in PEB_LAWS}
    return {
        "dose_to_size_mj_cm2": d2s,
        "peb_k_per_law": k_per_law,
        "dose_to_size_band": [min(finite_d2s), max(finite_d2s)] if finite_d2s else None,
        "lwr_3sigma_nm_at_analytical_d2s": lwr,
        "lwr_3sigma_band": [min(finite_lwr), max(finite_lwr)] if finite_lwr else None,
        "notes": (
            "dose band = acid-loss law (first-order lifetime vs trapping by deprotected "
            "sites), each with its own k for the same flood curve (peb_k_per_law); "
            "LWR band = photon shot noise alone .. plus "
            f"dissolution-cell noise for cells of {cells_nm} nm; simulated values carry "
            f"no SEM bias; grid {grid}, {rows} rows, seeds {seeds}"
        ),
    }
