"""NXE1716 anchor (Vesters 2017/2019): the chain's flood response must
reproduce the digitised DRM contrast curve, and the preset's provenance
constants are pinned. Line-printing numbers are NOT asserted here (open
discrepancy, log Fortsetzung 27) -- they live in the log and the docstring.
"""

from __future__ import annotations

import numpy as np
import pytest

from euvsimulator.presets import (
    NXE1716_DOSE_SCALE_CALIBRATION,
    flood_rate,
    load_nxe1716_anchor,
    nxe1716_config,
)


def test_anchor_data_is_shipped_and_sane():
    d = load_nxe1716_anchor()
    fit = np.array(d["authors_mack_fit_E_R"])
    mk = np.array(d["markers_E_R"])
    assert fit.shape[0] >= 20 and mk.shape[0] >= 12
    assert d["plateaus_nm_per_s"]["R_max"] == 245.0
    assert d["patterning_thesis_table_4_2_B0"]["dose_to_size_mj_cm2"] == 11.0
    # rates rise monotonically with dose along the authors' fit
    assert np.all(np.diff(fit[:, 1]) >= 0)


def test_chain_flood_curve_matches_the_authors_mack_fit():
    """Rms deviation in log10 R over the 25 digitised fit points <= 0.06 (the
    fit itself reaches 0.042); markers agree within a factor 3 except where a
    marker sits on the steep flank (E 8-10 mJ/cm², where 3 % in E is 50 % in R).
    """
    d = load_nxe1716_anchor()
    cfg = nxe1716_config()
    fit = np.array(d["authors_mack_fit_E_R"])
    model = flood_rate(cfg, fit[:, 0])
    rms = float(np.sqrt(np.mean((np.log10(model) - np.log10(fit[:, 1])) ** 2)))
    assert rms <= 0.06, rms
    # plateaus
    assert flood_rate(cfg, 1.0) == pytest.approx(0.0186, rel=0.05)
    assert flood_rate(cfg, 30.0) == pytest.approx(245.0, rel=0.05)


def test_calibrated_dose_scale_is_declared_not_hidden():
    a = nxe1716_config()
    b = nxe1716_config(calibrated_dose_scale=True)
    assert b.peb_k == pytest.approx(a.peb_k * NXE1716_DOSE_SCALE_CALIBRATION)
    assert NXE1716_DOSE_SCALE_CALIBRATION == pytest.approx(19.67 / 11.0)
    # the calibrated chain's flood switch (R = R_max/2) moves from 13.5 to ~7.2 mJ/cm²
    E = np.linspace(2.0, 30.0, 2000)

    def sw(c):
        return float(E[np.argmin(np.abs(np.log(flood_rate(c, E)) - np.log(122.5)))])

    assert sw(a) == pytest.approx(13.5, abs=0.3)
    assert sw(b) == pytest.approx(13.5 / NXE1716_DOSE_SCALE_CALIBRATION, abs=0.5)


def test_preset_geometry_and_optics_follow_the_thesis():
    c = nxe1716_config()
    assert (c.period_nm, c.line_width_nm, c.na) == (44.0, 22.0, 0.33)
    assert (c.illumination_shape, c.sigma, c.sigma_inner, c.pole_opening_deg) == (
        "dipole",
        0.9,
        0.62,
        90.0,
    )
    assert (c.resist_thickness_nm, c.peb_t_bake) == (35.0, 60.0)
    assert nxe1716_config(dose_mj_cm2=5.0).dose_mj_cm2 == 5.0


def test_two_curve_quencher_fit_reproduces_both_curves():
    """NXE1716 (high quencher) and NXE1717 (half the quencher) with shared k
    and a 2:1 quencher ratio, through the chain's quenching PEB step
    (log Fortsetzung 29): rms in log10 R <= 0.08 for both curves.
    """
    from euvsimulator.presets import NXE1716_QUENCHER_FIT as F
    from euvsimulator.presets import flood_rate_quenched

    d = load_nxe1716_anchor()
    c16 = np.array(d["authors_mack_fit_E_R"])
    c17 = np.array(d["nxe1717_low_quencher"]["authors_mack_fit_E_R"])
    p17 = d["nxe1717_low_quencher"]["plateaus_nm_per_s"]
    cfg16 = nxe1716_config(explicit_quencher=True)
    cfg17 = nxe1716_config(
        explicit_quencher=True,
        mack_n=F["mack_n_1717"],
        quencher_density_per_nm3=F["q_rel_1717"] * 0.2,
        mack_R_max=p17["R_max"],
        mack_R_min=p17["R_min"],
    )
    assert cfg16.quencher_density_per_nm3 == pytest.approx(2 * cfg17.quencher_density_per_nm3)
    for cfg, curve in ((cfg16, c16), (cfg17, c17)):
        model = flood_rate_quenched(cfg, curve[:, 0])
        rms = float(np.sqrt(np.mean((np.log10(model) - np.log10(curve[:, 1])) ** 2)))
        assert rms <= 0.08, rms
    # the quencher shifts the high-quencher switch to higher dose, as in the data
    E = np.linspace(2.0, 30.0, 2000)
    sw16 = float(E[np.argmin(np.abs(np.log(flood_rate_quenched(cfg16, E)) - np.log(122.5)))])
    sw17 = float(
        E[np.argmin(np.abs(np.log(flood_rate_quenched(cfg17, E)) - np.log(p17["R_max"] / 2)))]
    )
    assert sw16 > sw17 + 1.5


def test_two_curve_quencher_fit_through_the_concurrent_peb():
    """The same curve pair through the reaction-diffusion PEB (C2, log
    Fortsetzung 39): rms <= 0.08 for both curves; the quencher loading is
    Q/PAG = 0.36 there (0.13 with the analytical PEB).
    """
    from euvsimulator.presets import NXE1716_QUENCHER_FIT_PDE as F
    from euvsimulator.presets import flood_rate_pde

    d = load_nxe1716_anchor()
    c16 = np.array(d["authors_mack_fit_E_R"])
    c17 = np.array(d["nxe1717_low_quencher"]["authors_mack_fit_E_R"])
    p17 = d["nxe1717_low_quencher"]["plateaus_nm_per_s"]
    cfg16 = nxe1716_config(explicit_quencher=True, peb_model="reaction_diffusion")
    cfg17 = nxe1716_config(
        explicit_quencher=True,
        peb_model="reaction_diffusion",
        mack_n=F["mack_n_1717"],
        quencher_density_per_nm3=F["q_rel_1717"] * 0.2,
        mack_R_max=p17["R_max"],
        mack_R_min=p17["R_min"],
    )
    assert cfg16.quencher_density_per_nm3 == pytest.approx(0.0727, abs=1e-3)
    assert cfg16.acid_base_quench_rate_nm3_per_s == 1.2
    for cfg, curve in ((cfg16, c16), (cfg17, c17)):
        model = flood_rate_pde(cfg, curve[:, 0])
        rms = float(np.sqrt(np.mean((np.log10(model) - np.log10(curve[:, 1])) ** 2)))
        assert rms <= 0.08, rms
