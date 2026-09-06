"""The default fit bounds of `euv calibrate` must contain the chain's defaults,
otherwise the optimiser is clamped before it starts (found 2026-09-06 with
peb_k: bound 2.0 vs default 10.95).
"""

from __future__ import annotations

from euvsimulator.calibrate.wafer_fit import DEFAULT_BOUNDS
from euvsimulator.pipeline import SimulationConfig


def test_default_bounds_contain_the_defaults():
    cfg = SimulationConfig()
    assert {"dill_C", "peb_k", "peb_sigma_diff", "mack_R_max", "mack_n", "mack_M_th"} <= set(
        DEFAULT_BOUNDS
    )
    for name, (lo, hi) in DEFAULT_BOUNDS.items():
        value = getattr(cfg, name)
        if value is None:  # peb_sigma_diff: derived from D and the lifetime by default
            continue
        assert lo < value < hi, (name, lo, value, hi)
