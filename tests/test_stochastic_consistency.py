"""One chemistry for both chains: the deterministic full_chem result must be
the large-number limit of the sampled-molecule (exposure_stochasticity) chain.

Before 2026-09-04 the deterministic chain had no quencher at all while the
stochastic chain applied one per grid voxel where it was effectively inert,
so the stochastic CD never converged to the deterministic one (audit A4,
arbeitslog "Fortsetzung 10" §5). Both chains now run
resist/peb.py::reaction_diffusion_with_quenching (diffuse, then react) on
either the mean field or a Poisson/Binomial sample of it.

The stochastic chain carries TWO noise sources: photon shot noise (always on
with enable_stochastic=True) and the molecular-count noise. The large-number
limit of the molecules removes only the second, so the invariant is tested
with the photon sampler replaced by its own mean (E[D_eff] = blur(dose), see
photon_deposition_shot_noise): then rho_PAG -> inf must reproduce the
deterministic CD to within a pixel, with and without quencher.

Invariants (no calibrated numbers):
1. rho_PAG -> inf (photon noise off): realisation mean line width ->
   deterministic CD, with and without quencher.
2. rho_PAG -> inf (photon noise on): molecular-count LWR -> photon-only LWR.
3. quencher_density = 0 makes the shared PEB step identical to plain
   diffusion + deprotection.
"""

import math

import pytest
import torch

import euvsimulator.pipeline as P
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.exposure import gaussian_se_blur

PITCH, LW = 44.0, 22.0
DX = PITCH / 256


def _cfg(**kw):
    base = dict(resist_model="full_chem", period_nm=PITCH, line_width_nm=LW, se_blur_nm=5.0,
                grid=256)
    base.update(kw)
    return SimulationConfig(**base)


def _stoch(rho, q_ratio, dose, seed=42, rows=1024):
    return run_simulation(_cfg(dose_mj_cm2=dose, enable_stochastic=True, stochastic_seed=seed,
                               stochastic_n_realisations=1, stochastic_ler_grid_y=rows,
                               exposure_stochasticity=True, pag_density_per_nm3=rho,
                               quencher_density_per_nm3=rho * q_ratio))


@pytest.fixture
def photon_noise_off(monkeypatch):
    """Replace the photon sampler by its expectation value."""

    def mean_field(dose, se_blur_nm, dx_nm=1.0, **kw):
        return gaussian_se_blur(dose, sigma=se_blur_nm, dx=dx_nm) if se_blur_nm > 0 else dose

    monkeypatch.setattr(P, "photon_deposition_shot_noise", mean_field)


@pytest.mark.parametrize("q_ratio, dose", [(0.0, 7.0), (0.25, 21.0)])
def test_large_number_limit_recovers_deterministic_cd(photon_noise_off, q_ratio, dose):
    """Dose chosen near dose-to-size of each chemistry (measured 6.6 / 21.2
    mJ/cm² at 44 nm pitch without / with Mack-2011 quencher loading)."""
    det = run_simulation(_cfg(dose_mj_cm2=dose, quencher_density_per_nm3=0.2 * q_ratio)).cd_nm
    assert det > 0.0
    cds = {}
    for rho in (0.2, 20.0, 2000.0):
        cds[rho] = _stoch(rho, q_ratio, dose).ler_metadata["stochastic_cd_nm"]
        assert math.isfinite(cds[rho])
    # Converged: within one pixel of the deterministic CD (cd_nm itself is
    # pixel-quantised), and monotonically closer than the sparse case.
    assert abs(cds[2000.0] - det) <= DX, f"det {det:.2f}, stochastic {cds}"
    assert abs(cds[2000.0] - det) <= abs(cds[0.2] - det) + 1e-9


def test_large_number_limit_has_no_roughness_without_photon_noise(photon_noise_off):
    r = _stoch(2000.0, 0.0, 7.0)
    assert r.lwr_nm < 0.1 * DX  # only residual sub-pixel interpolation noise


def test_molecular_noise_vanishes_to_photon_floor():
    photon_only = run_simulation(_cfg(dose_mj_cm2=7.0, enable_stochastic=True, stochastic_seed=42,
                                      stochastic_n_realisations=1, stochastic_ler_grid_y=1024,
                                      exposure_stochasticity=False)).lwr_nm
    dense = _stoch(2000.0, 0.0, 7.0).lwr_nm
    sparse = _stoch(0.2, 0.0, 7.0).lwr_nm
    assert sparse > dense  # finite molecule count adds roughness
    # At 2000 molecules/nm^3 the count noise is negligible against the
    # photon noise: same seed, same photon draw -> within 10 %.
    assert dense == pytest.approx(photon_only, rel=0.10)


def test_quencher_free_default_is_no_op_for_the_peb_step():
    """With quencher_density = 0 the shared PEB step reduces to the plain
    diffusion + deprotection of reaction_diffusion_analytical."""
    from euvsimulator.resist.peb import reaction_diffusion_analytical, reaction_diffusion_with_quenching

    acid = torch.rand(3, 32, 32, dtype=torch.float64) * 0.5
    inhib = torch.ones_like(acid)
    _, m_ref = reaction_diffusion_analytical(acid, inhib, D=3.3, k=0.0723, t_bake=60.0, dx=0.25)
    _, _, m_new = reaction_diffusion_with_quenching(
        acid, torch.zeros_like(acid), inhib, D=3.3, k=0.0723, quench_rate=15.0, t_bake=60.0,
        dx=0.25, pag_density=0.2,
    )
    assert torch.allclose(m_ref, m_new, atol=1e-12)
