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
# PEB blur for these tests: 7 nm (sigma_tot ≈ 8.6 nm with the 5 nm SE blur),
# the regime in which the 22 nm line at 44 nm pitch prints. With the
# default 19.9 nm the exact Gaussian (kernel no longer clamped since
# 2026-09-04) leaves 1.8 % contrast at the pitch frequency and no line
# prints at any dose -- an invariant cannot be tested on a non-existent
# edge. This is a choice of operating point, not a physics parameter.
SIGMA_PEB = 7.0


def _cfg(**kw):
    base = dict(resist_model="full_chem", period_nm=PITCH, line_width_nm=LW, se_blur_nm=5.0,
                grid=256, peb_sigma_diff=SIGMA_PEB)
    base.update(kw)
    return SimulationConfig(**base)


def _dose_to_size(q_density, lo=1.0, hi=80.0, iters=16):
    """Deterministic dose at which CD == LW (bisection; CD falls with dose)."""
    f = lambda d: run_simulation(_cfg(dose_mj_cm2=d, quencher_density_per_nm3=q_density)).cd_nm
    assert f(lo) >= LW >= f(hi), "no dose window for this chemistry"
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if f(mid) > LW:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


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


@pytest.mark.parametrize("q_ratio", [0.0, 0.25])
def test_large_number_limit_recovers_deterministic_cd(photon_noise_off, q_ratio):
    """At the dose-to-size of each chemistry (without / with Mack-2011
    quencher loading), found by bisection so the test follows the model."""
    dose = _dose_to_size(0.2 * q_ratio)
    det = run_simulation(_cfg(dose_mj_cm2=dose, quencher_density_per_nm3=0.2 * q_ratio)).cd_nm
    assert det > 0.0
    cds = {}
    for rho in (0.2, 20.0, 2000.0):
        cds[rho] = _stoch(rho, q_ratio, dose).ler_metadata["stochastic_cd_nm"]
        assert math.isfinite(cds[rho])
    # Converged: the deterministic cd_nm is pixel-quantised (integer-pixel
    # run length of the binarised middle row, ±0.5 px per edge), the
    # stochastic width is a sub-pixel crossing -> agree to 1.5 px; and the
    # dense realisation is closer than the sparse one.
    assert abs(cds[2000.0] - det) <= 1.5 * DX, f"det {det:.2f}, stochastic {cds}"
    assert abs(cds[2000.0] - det) <= abs(cds[0.2] - det) + 1e-9


def test_molecular_noise_scales_as_inverse_sqrt_density(photon_noise_off):
    """With the photon sampler replaced by its mean, the only noise left is
    the molecular count: LWR ∝ ρ^(−1/2) (Poisson/Binomial counting). Measured
    2026-09-05 at this operating point (rho_scaling.py): 2.55 / 0.56 / 0.23 /
    0.088 / 0.017 nm for ρ = 0.2 … 2000 nm⁻³, i.e. ×150 over four decades
    (√10⁴ = 100). An earlier version asserted "no roughness" below 0.1 px at
    ρ = 2000 and passed by 0.0002 nm -- the residual is physics, not
    interpolation noise, so the invariant is the scaling, not a floor."""
    dose = _dose_to_size(0.0)
    lwr = {rho: _stoch(rho, 0.0, dose).lwr_nm for rho in (0.2, 20.0, 2000.0)}
    assert lwr[0.2] > lwr[20.0] > lwr[2000.0] > 0.0, lwr
    # two decades of density -> one decade of LWR (factor 10), allow 2x either way
    assert 5.0 < lwr[0.2] / lwr[20.0] < 20.0, lwr
    assert 5.0 < lwr[20.0] / lwr[2000.0] < 20.0, lwr


def test_molecular_noise_vanishes_to_photon_floor():
    """With photon noise on and the same seed, the dense-molecule chain must
    reproduce the photon-only chain (same photon draw, count noise 0.02 nm
    against a ~10 nm photon LWR at this operating point). The sparse chain
    adds only ~2.5 nm in quadrature (+3 %), below the estimator's own
    scatter at n_eff ≈ 9, so no ordering is asserted with photon noise on --
    the molecular part is tested with the photon sampler off above."""
    dose = _dose_to_size(0.0)
    photon_only = run_simulation(_cfg(dose_mj_cm2=dose, enable_stochastic=True, stochastic_seed=42,
                                      stochastic_n_realisations=1, stochastic_ler_grid_y=1024,
                                      exposure_stochasticity=False)).lwr_nm
    dense = _stoch(2000.0, 0.0, dose).lwr_nm
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
