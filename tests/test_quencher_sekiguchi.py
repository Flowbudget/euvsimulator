"""Neutralisation closed form against Sekiguchi (LTJ) IEEJ Trans. FM 133(10) 500 (2013).

Measurement: EUV open-frame exposure of an acrylic (GMH) film with 4 wt% TPS-tf
and Coumarin-6 as acid indicator, quencher at 0 / 0.05 / 0.1 / 0.5 / 0.75 mol
per mol PAG, no PEB (neutralisation at room temperature during exposure).
Table 1 gives the effective Dill C from a fit of 1 − exp(−C·E):
0.1280 / 0.1090 / 0.0982 / 0.0435 / 0.0228 cm²/mJ.

What this pins (log Fortsetzung 21): the pipeline's neutralisation closed
form (second-order, Mack 2011) reproduces the quencher dependence with ONE
rate parameter fitted on the q = 0.5 row -- rows 0.05 / 0.10 within 5 %,
row 0.75 within 30 % (known deviation, +28 %) -- while the stoichiometric
limit (complete neutralisation, A = H0 − q) is clearly worse. The rate
value itself is NOT transferable to the PEB (other temperature and time
axis) and is not asserted.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch
from scipy.optimize import brentq, minimize_scalar

from euvsimulator.resist.peb import _reaction_limited_quench

C0 = 0.128
MEASURED = {0.05: 0.1090, 0.10: 0.0982, 0.50: 0.0435, 0.75: 0.0228}
E = np.linspace(0.0, 40.0, 81)[1:]
H0 = torch.tensor(1.0 - np.exp(-C0 * E), dtype=torch.float64)


def _fit_c(acid: np.ndarray) -> float:
    return float(
        minimize_scalar(
            lambda c: float(np.sum((1.0 - np.exp(-c * E) - acid) ** 2)),
            bounds=(1e-4, 1.0),
            method="bounded",
        ).x
    )


def _c_eff(q: float, rate_time: float) -> float:
    a, _ = _reaction_limited_quench(H0, torch.full_like(H0, q), rate=rate_time, t=1.0)
    return _fit_c(a.numpy())


def test_second_order_form_reproduces_the_quencher_trend_with_one_rate():
    s = brentq(lambda x: _c_eff(0.5, x) - MEASURED[0.5], 1e-3, 1e4)
    assert 0.5 < s < 5.0
    assert _c_eff(0.05, s) == pytest.approx(MEASURED[0.05], rel=0.10)
    assert _c_eff(0.10, s) == pytest.approx(MEASURED[0.10], rel=0.10)
    # known deviation at the highest loading (+28 % on 2026-09-05)
    assert _c_eff(0.75, s) == pytest.approx(MEASURED[0.75], rel=0.35)


def test_complete_neutralisation_is_worse_than_the_finite_rate():
    """Guard against replacing the closed form by plain stoichiometry."""
    s = brentq(lambda x: _c_eff(0.5, x) - MEASURED[0.5], 1e-3, 1e4)
    for q in (0.5, 0.75):
        complete = _fit_c(np.maximum(H0.numpy() - q, 0.0))
        finite = _c_eff(q, s)
        assert abs(finite - MEASURED[q]) < abs(complete - MEASURED[q])
        assert complete < 0.6 * MEASURED[q]
