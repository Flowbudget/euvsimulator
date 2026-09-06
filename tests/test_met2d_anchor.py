"""MET-2D / XP 5271 anchor: data file, preset provenance and the measured-blur
mapping. Line-printing numbers are not asserted (see log Fortsetzung 30).
"""

from __future__ import annotations

import pytest

from euvsimulator.presets import (
    MET2D_BLUR_CONTACT_SIGMA_NM,
    load_met2d_anchor,
    met2d_config,
)


def test_anchor_data_is_shipped_and_consistent():
    d = load_met2d_anchor()
    rows = d["anderson_naulleau_2008_osti_950847"]["rows"]
    assert [r["id"] for r in rows] == ["XP 5271-J", "XP 5271-K", "XP 5271-D"]
    # more base -> higher E-size and lower LER, as the paper states
    assert rows[0]["e_size_mj_cm2"] < rows[1]["e_size_mj_cm2"] < rows[2]["e_size_mj_cm2"]
    assert rows[0]["ler_50nm_1to1_nm"] > rows[2]["ler_50nm_1to1_nm"]
    assert d["lbnl_film_quantum_yield"]["dill_C_cm2_per_mJ"] == 0.0152
    assert d["sekiguchi_2011_table6_euv_met2d"]["dill_B_per_um"] == 5.21


def test_preset_follows_the_sources():
    c = met2d_config()
    assert (c.mack_R_max, c.mack_R_min, c.mack_M_th, c.mack_n) == (170.2, 0.028, 0.518, 18.96)
    assert c.dill_B == 5.21 and c.dill_C == 0.0152
    assert c.peb_sigma_diff == pytest.approx(23.8 / 2.3548, rel=1e-3)
    assert MET2D_BLUR_CONTACT_SIGMA_NM == pytest.approx(10.11, abs=0.01)
    assert (c.period_nm, c.line_width_nm, c.na, c.illumination_shape) == (
        100.0,
        50.0,
        0.3,
        "annular",
    )
    assert (c.sigma_inner, c.sigma) == (0.35, 0.55)
    assert (c.resist_thickness_nm, c.peb_t_bake, c.develop_time_s) == (80.0, 90.0, 45.0)
    assert met2d_config(blur_metric="corner").peb_sigma_diff == pytest.approx(
        34.8 / 2.3548, rel=1e-3
    )
