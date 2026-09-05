"""Exposure shot noise must be driven by ABSORBED, not incident, photons.

Physics: acid is generated only where a photon is absorbed (Mack, Biafore &
Smith 2011, "Stochastic exposure kinetics of EUV photoresists"); the number
of absorbed photons in a resist column is Poisson with mean
N_inc · (1 − e^{−α t}). For the 50 nm default film that is 19.9 % of the
incident photons with the composition-derived α = 4.44 µm⁻¹ (2026-09-05); with
the former default 1.06 µm⁻¹ it was 5.2 %. Counting incident photons instead
(the behaviour before 2026-09-04, audit A1) under-estimated the relative noise
by √(1/0.052) ≈ 4.4× before the resist nonlinearity acted on it.

Invariants pinned here are grid-free and contain no calibrated number.
"""

import math

import pytest
import torch

from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.stochastic import photon_deposition_shot_noise


def _relative_noise(absorption, n_inc=200.0, n=200_000, seed=3):
    """Relative RMS of D_eff/dose for a uniform field with n_inc incident
    photons per voxel and the given absorbed fraction (no SE blur).
    """
    dose = torch.full((n,), 1.0, dtype=torch.float64)
    dx = math.sqrt(n_inc * 91.84 / (6.241509074e15 * 1e-14))  # nm, so that N_inc = n_inc
    rng = torch.Generator().manual_seed(seed)
    d = photon_deposition_shot_noise(
        dose, se_blur_nm=0.0, dx_nm=dx, photon_energy_eV=91.84, absorption=absorption, rng=rng
    )
    return float(d.std() / d.mean()), float(d.mean())


def test_relative_noise_scales_with_absorbed_fraction():
    for eta in (1.0, 0.25, 0.05):
        rel, mean = _relative_noise(eta)
        n_abs = 200.0 * eta
        assert mean == pytest.approx(1.0, rel=0.02)  # unbiased
        assert rel == pytest.approx(1.0 / math.sqrt(n_abs), rel=0.05)


def test_pipeline_passes_absorbed_fraction(monkeypatch):
    """The full_chem stochastic path must hand 1 − exp(−(A+B)·t) to the
    photon sampler -- the same Beer-Lambert coefficient the depth-resolved
    exposure uses -- not the sampler's default of 1.0.
    """
    import euvsimulator.pipeline as P

    seen = []
    real = P.photon_deposition_shot_noise

    def spy(dose, **kw):
        seen.append(kw.get("absorption", "MISSING"))
        return real(dose, **kw)

    monkeypatch.setattr(P, "photon_deposition_shot_noise", spy)
    cfg = SimulationConfig(
        resist_model="full_chem",
        enable_stochastic=True,
        stochastic_seed=1,
        stochastic_n_realisations=1,
        stochastic_ler_grid_y=256,
        grid=64,
        dill_A=0.2,
        dill_B=1.5,
        resist_thickness_nm=40.0,
    )
    run_simulation(cfg)
    expected = 1.0 - math.exp(-(0.2 + 1.5) * 0.040)
    assert seen and all(a == pytest.approx(expected, rel=1e-12) for a in seen)
    assert 0.0 < expected < 1.0


def test_absorbed_fraction_uses_same_coefficient_as_depth_profile():
    """Consistency: the fraction absorbed over the film equals what the
    depth-resolved Beer-Lambert dose profile loses between top and bottom.
    """
    from euvsimulator.resist.exposure import dill_abc_exposure

    A, B, t_um = 0.1, 1.06, 0.05
    dose = torch.full((4, 4), 10.0, dtype=torch.float64)
    _, inhib = dill_abc_exposure(dose, A=A, B=B, C=1e-9, thickness=t_um, n_layers=2)
    # inhib = exp(-C·dose_z); with tiny C, 1 - inhib ≈ C·dose_z, so the
    # top/bottom ratio of (1 - inhib) is the transmitted fraction.
    top, bottom = float(1 - inhib[0, 0, 0]), float(1 - inhib[1, 0, 0])
    transmitted = bottom / top
    assert 1.0 - transmitted == pytest.approx(1.0 - math.exp(-(A + B) * t_um), rel=1e-6)
