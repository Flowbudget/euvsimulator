"""Exposure-dose convention: dose_mj_cm2 is the wafer dose in a clear area.

Invariants pinned here (found missing 2026-09-04, audit A2):

1. An absorber-free mask (open frame) exposes the resist to exactly
   ``dose_mj_cm2`` -- Mack, "Inside PROLITH" (1997), ch. 9: E is "the
   intensity in a large clear area times the exposure time" and the
   resist sees E·I(x) with I normalised to that clear area.
2. Mirror losses (interface roughness, bilayer count) change the mirror's
   clear-field reflectivity but NOT the open-frame resist dose -- a scanner
   calibrates dose at the wafer.
3. The photon count that drives shot noise follows from the same dose
   scale: N = D · A_voxel · (6.2415e15 eV per mJ) / E_photon.
4. The RCWA path agrees with the thin-mask path on the open frame to
   within the RCWA/TMM cross-validation accuracy.

These are pure invariants of the dose scale: they contain no calibrated
number and must hold for any multilayer, wavelength or grid.
"""

import math

import pytest
import torch

from euvsimulator.constants import HC_EV_NM
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.stochastic import photon_deposition_shot_noise

OPEN_FRAME_LW_NM = 1e-6  # effectively zero absorber width


def _open_frame(dose, **kw):
    return run_simulation(
        SimulationConfig(
            period_nm=64.0, line_width_nm=OPEN_FRAME_LW_NM, dose_mj_cm2=dose,
            grid=128, **kw,
        )
    )


def test_open_frame_delivers_nominal_dose():
    for dose in (1.0, 12.5, 30.0):
        r = _open_frame(dose)
        row = r.aerial_image[r.aerial_image.shape[0] // 2]
        assert float(row.max()) == pytest.approx(dose, rel=1e-6)
        assert float(row.min()) == pytest.approx(dose, rel=1e-6)


def test_clear_field_reflectivity_is_reported_and_physical():
    r = _open_frame(1.0)
    # Mo/Si at 13.5 nm, 6 deg: ideal-interface peak reflectivity is in the
    # 0.6-0.75 range for any realistic stack; anything else means the
    # normalisation divided by something that is not the mirror.
    assert 0.55 < r.clear_field_reflectivity < 0.80
    # Mask-level intensity is recoverable.
    mask_level = r.aerial_image * r.clear_field_reflectivity
    assert float(mask_level.max()) == pytest.approx(r.clear_field_reflectivity, rel=1e-6)


def test_open_frame_dose_independent_of_mirror_losses():
    ideal = _open_frame(20.0, ml_roughness_nm=0.0)
    rough = _open_frame(20.0, ml_roughness_nm=0.7)
    assert rough.clear_field_reflectivity < ideal.clear_field_reflectivity
    assert float(rough.aerial_image.max()) == pytest.approx(20.0, rel=1e-6)
    assert float(ideal.aerial_image.max()) == pytest.approx(20.0, rel=1e-6)

    few = _open_frame(20.0, ml_n_bilayers=20)
    assert few.clear_field_reflectivity < ideal.clear_field_reflectivity
    assert float(few.aerial_image.max()) == pytest.approx(20.0, rel=1e-6)


def test_open_frame_photon_count_matches_dose_scale():
    dose = 15.0
    r = _open_frame(dose)
    dx_nm = 64.0 / 128
    energy_eV = HC_EV_NM / 13.5
    expected_per_voxel = dose * (dx_nm * dx_nm * 1e-14) * 6.241509074e15 / energy_eV
    # Mean of the Poisson-sampled effective dose must equal the dose; the
    # sampled photon count per voxel must equal the analytic expectation.
    rng = torch.Generator().manual_seed(7)
    d_eff = photon_deposition_shot_noise(
        r.aerial_image, se_blur_nm=0.0, dx_nm=dx_nm, photon_energy_eV=energy_eV, rng=rng
    )
    n_sampled = d_eff * (dx_nm * dx_nm * 1e-14) * 6.241509074e15 / energy_eV
    n_pix = n_sampled.numel()
    assert float(n_sampled.mean()) == pytest.approx(
        expected_per_voxel, rel=4.0 / math.sqrt(n_pix * expected_per_voxel)
    )


def test_rcwa_open_frame_matches_thin_mask():
    thin = _open_frame(10.0, use_rcwa=False)
    rcwa = _open_frame(10.0, use_rcwa=True, n_rcwa_orders=11)
    # RCWA with an empty grating reproduces the bare mirror: the Fourier
    # truncation of a uniform profile is exact, and the RCWA<->TMM cross-
    # check gives |r0|^2 identical to 5 digits (0.64697 TE / 0.63938 TM at
    # 6 deg, default stack). Before 2026-09-04 this read 0.692 x 10 because
    # the pipeline mislabelled the RCWA orders by one (floor division).
    assert float(rcwa.aerial_image.max()) == pytest.approx(10.0, rel=1e-4)
    assert float(rcwa.aerial_image.min()) == pytest.approx(10.0, rel=1e-4)
    assert float(thin.aerial_image.max()) == pytest.approx(10.0, rel=1e-6)


def test_rcwa_runs_at_mask_scale(monkeypatch):
    """The RCWA must see the physical (demagnified-by-M) mask.

    Two checks on the solver call the pipeline actually makes:
    1. the grating period handed to RCWA is M × the wafer period;
    2. the ±1-order intensity asymmetry is of shadowing size. At wafer
       scale the ±1 orders of a 64 nm grating hit the Mo/Si mirror at
       +18°/−6°, where its reflectivity is 0.08 vs 0.65, giving a 10.8×
       asymmetry; at mask scale (±1 at +9°/+3°, inside the Bragg
       acceptance) it is ≈1.2×. A bound of 2 separates the two regimes by
       a factor of 5 on either side and is not a calibrated number.
    Note: the aerial image itself is NOT mirror-symmetric at 6° chief-ray
    angle -- absorber shadowing shifts the pattern -- so image symmetry
    must not be used as the invariant.
    """
    from euvsimulator.mask3d.rcwa_torch import RCWA1D

    calls = []
    real_solve = RCWA1D.solve

    def spy(self, eps_profile, thicknesses, period, *args, **kwargs):
        orders = real_solve(self, eps_profile, thicknesses, period, *args, **kwargs)
        calls.append((self.cfg.polarization, float(period), self.m.tolist(), orders.detach().clone()))
        return orders

    monkeypatch.setattr(RCWA1D, "solve", spy)
    cfg = SimulationConfig(period_nm=64.0, line_width_nm=32.0, dose_mj_cm2=20.0,
                           grid=128, use_rcwa=True, n_rcwa_orders=11)
    run_simulation(cfg)
    assert len(calls) == 2  # TE and TM
    for pol, period, m, orders in calls:
        assert period == pytest.approx(64e-9 * cfg.mask_demagnification, rel=1e-12)
        i0 = m.index(0)
        r_plus = float(abs(orders[i0 + 1]) ** 2)
        r_minus = float(abs(orders[i0 - 1]) ** 2)
        assert 0.5 < r_plus / r_minus < 2.0, f"{pol}: ±1 asymmetry {r_plus / r_minus:.2f}"


def test_zero_reflectivity_mirror_is_rejected(monkeypatch):
    """A mirror with no clear-field reflectivity cannot define a dose scale.

    No physically buildable Mo/Si stack reaches |r|^2 <= 1e-12, so the guard
    is exercised by substituting a zero-reflectivity TMM result.
    """
    import euvsimulator.pipeline as P

    real_reflectivity = P.reflectivity

    def dead_mirror(*args, **kwargs):
        R, r = real_reflectivity(*args, **kwargs)
        return torch.zeros_like(R), torch.zeros_like(r)

    monkeypatch.setattr(P, "reflectivity", dead_mirror)
    with pytest.raises(ValueError, match="clear-field reflectivity"):
        run_simulation(SimulationConfig(grid=64))
