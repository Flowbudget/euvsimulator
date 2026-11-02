"""Structural uncertainty bands (calibrate/bands.py, 2.1)."""

from __future__ import annotations

import math

from euvsimulator.calibrate.bands import structural_bands


def test_bands_have_the_documented_structure_and_are_ordered():
    base = dict(period_nm=64.0, line_width_nm=32.0, se_blur_nm=2.5)
    out = structural_bands(base, target_cd_nm=32.0, grid=64, rows=256, seeds=(1,), cells_nm=(4.3,))
    d2s = out["dose_to_size_mj_cm2"]
    assert set(d2s) == {"analytical", "reaction_diffusion"}
    assert all(v > 0 for v in d2s.values() if not math.isnan(v))
    lo, hi = out["dose_to_size_band"]
    assert lo <= hi
    lwr = out["lwr_3sigma_nm_at_analytical_d2s"]
    assert set(lwr) == {"photon_shot_noise", "dissolution_cell_4.3_nm"}
    assert lwr["dissolution_cell_4.3_nm"] >= 0.8 * lwr["photon_shot_noise"]
    assert out["lwr_3sigma_band"][0] <= out["lwr_3sigma_band"][1]
    assert "SEM bias" in out["notes"]
