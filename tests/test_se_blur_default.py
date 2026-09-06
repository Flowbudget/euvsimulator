"""Secondary-electron blur default (plan stage A3, 2026-09-06).

Source: Thackeray et al., J. Photopolym. Sci. Technol. 23(5) 631 (2010),
Eq. (8): measured EUV total blur 11.5 nm = 9.7 (acid reaction-diffusion)
(+) 4.3 (radius of gyration) (+) 2.5 (EUV-specific) (+) 3.7 (unexplained),
in quadrature. The chain carries the acid term (9.4 nm from D and t_eff) and
the 2.5 nm SE term; it has no radius-of-gyration model.

The zero-blur case is kept as a documented failure mode: with se_blur = 0 the
photon-deposition model is white per-pixel Poisson noise, so on a fine grid
almost every pixel is empty and the few occupied ones carry hundreds of
mJ/cm² -- the Dill law saturates there and the mean acid collapses.
"""

from __future__ import annotations

import math
import warnings

import pytest
import torch

from euvsimulator.pipeline import DEFAULT_SE_BLUR_NM, RESIST_PRESETS, SimulationConfig
from euvsimulator.resist.stochastic import photon_deposition_shot_noise


def test_default_is_thackerays_euv_specific_term():
    assert DEFAULT_SE_BLUR_NM == 2.5
    assert SimulationConfig().se_blur_nm == DEFAULT_SE_BLUR_NM
    assert RESIST_PRESETS["CAR"] == DEFAULT_SE_BLUR_NM


def test_total_blur_of_the_chain_against_thackeray():
    """Acid (+) SE in quadrature: 9.4 (+) 2.5 = 9.7 nm, i.e. Thackeray's acid +
    electron part (9.7 (+) 2.5 = 10.0 nm) within 5 %; the missing 4.3 nm Rg and
    3.7 nm unexplained terms are why the chain's 9.7 is below their 11.5 total.
    """
    cfg = SimulationConfig()
    t_eff = cfg.peb_acid_lifetime_s * (1.0 - math.exp(-cfg.peb_t_bake / cfg.peb_acid_lifetime_s))
    sigma_acid = math.sqrt(2.0 * cfg.peb_D * t_eff)
    total = math.hypot(sigma_acid, cfg.se_blur_nm)
    assert sigma_acid == pytest.approx(9.4, abs=0.1)
    assert total == pytest.approx(math.hypot(9.7, 2.5), rel=0.05)
    assert total < 11.5


def _noise_field(se_blur_nm: float, dx_nm: float = 0.172, dose: float = 1.65) -> torch.Tensor:
    g = torch.Generator().manual_seed(1)
    return photon_deposition_shot_noise(
        torch.full((256, 256), dose),
        se_blur_nm=se_blur_nm,
        dx_nm=dx_nm,
        photon_energy_eV=91.84,
        dose_to_energy_factor=6.241509074e15,
        absorption=0.2,
        rng=g,
    )


def test_zero_blur_is_white_per_pixel_noise_that_saturates_the_dill_law():
    d0 = _noise_field(0.0)
    # 0.007 photons per 0.172 nm pixel: > 99 % empty, spikes of ~250 mJ/cm²
    assert float((d0 == 0).float().mean()) > 0.99
    assert float(d0.max()) > 100.0
    # mean acid from the spikes is far below the mean-field value
    c = SimulationConfig().dill_C
    acid_spiky = float((1.0 - torch.exp(-c * d0)).mean())
    acid_mean_field = 1.0 - math.exp(-c * float(d0.mean()))
    assert acid_spiky < 0.5 * acid_mean_field


def test_default_blur_keeps_the_noise_in_the_linear_dill_regime():
    d = _noise_field(DEFAULT_SE_BLUR_NM)
    assert float(d.std() / d.mean()) < 0.3
    assert float(d.max()) * SimulationConfig().dill_C < 0.1  # C*E << 1 everywhere


def test_stochastic_full_chem_with_zero_blur_warns():
    with pytest.warns(UserWarning, match="se_blur_nm = 0"):
        SimulationConfig(resist_model="full_chem", enable_stochastic=True, se_blur_nm=0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        SimulationConfig(resist_model="full_chem", enable_stochastic=True)
        SimulationConfig(se_blur_nm=0.0)  # deterministic: no warning


def test_negative_blur_is_rejected():
    with pytest.raises(ValueError):
        SimulationConfig(se_blur_nm=-1.0)
