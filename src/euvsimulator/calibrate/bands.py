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

Roughness values are simulated (no SEM bias); compare with unbiased
measurements or add the metrology's bias (Lorusso/Mack 2018).
"""

from __future__ import annotations

import statistics
from typing import Any, Callable, Dict

from euvsimulator.pipeline import SimulationConfig, run_simulation

PEB_LAWS = ("analytical", "reaction_diffusion")
DISSOLUTION_CELLS_NM = (1.0, 4.3)


def _dose_to_size(
    make_cfg: Callable[..., SimulationConfig], target_nm: float, lo: float, hi: float, n: int = 9
) -> float:
    if run_simulation(make_cfg(dose_mj_cm2=hi)).cd_nm > target_nm:
        return float("nan")  # does not print within the search range
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        if run_simulation(make_cfg(dose_mj_cm2=mid)).cd_nm > target_nm:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


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
) -> Dict[str, Any]:
    """Dose-to-size and 3-sigma LWR of the calibrated chain under both PEB laws
    and both dissolution-unit sizes.

    ``base``: SimulationConfig keyword arguments of the calibrated resist
    (period, line width, film, Mack, exposure, PEB). Returns a dict with the
    per-corner values and min/max bands; NaN where a corner does not print.
    """

    def make(**over):
        kw = dict(base)
        kw.update(resist_model="full_chem", grid=grid)
        kw.update(over)
        return SimulationConfig(**kw)

    d2s: Dict[str, float] = {}
    for law in PEB_LAWS:
        d2s[law] = _dose_to_size(
            lambda dose_mj_cm2, law=law: make(peb_model=law, dose_mj_cm2=dose_mj_cm2),
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

        lwr["photon_shot_noise"] = lwr_at()
        for a in cells_nm:
            lwr[f"dissolution_cell_{a:g}_nm"] = lwr_at(
                development_stochasticity=True, dissolution_cell_nm=a
            )

    finite_d2s = [v for v in d2s.values() if v == v]
    finite_lwr = [v for v in lwr.values() if v == v]
    return {
        "dose_to_size_mj_cm2": d2s,
        "dose_to_size_band": [min(finite_d2s), max(finite_d2s)] if finite_d2s else None,
        "lwr_3sigma_nm_at_analytical_d2s": lwr,
        "lwr_3sigma_band": [min(finite_lwr), max(finite_lwr)] if finite_lwr else None,
        "notes": (
            "dose band = acid-loss law (first-order lifetime vs trapping by deprotected "
            "sites) at the fitted kinetics; LWR band = photon shot noise alone .. plus "
            f"dissolution-cell noise for cells of {cells_nm} nm; simulated values carry "
            f"no SEM bias; grid {grid}, {rows} rows, seeds {seeds}"
        ),
    }
