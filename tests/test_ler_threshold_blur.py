"""Regression guard: ler_lwr_estimate thresholded unblurred Poisson counts.

The noisy acid of poisson_shot_noise is the acid count times a constant; at
EUV doses a 1 nm pixel holds a fraction of an acid to a few acids, so
``noisy > develop_threshold`` without the secondary-electron blur asked
whether a pixel caught enough acids, and the integer-pixel edges were pixel
noise -- the construction that was fixed in rms_scaling_check (B1.11). Now the
noisy acid is blurred with the SE PSF (se_blur_nm, default 2.5 nm), the
threshold is applied to the blurred field and the edges are sub-pixel.

Photon statistics: with the acid map fixed and the dose raised 16x, the mean
edge stays where it is and the edge noise falls 4x (LER ~ dose^-1/2).
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.stochastic import ler_lwr_estimate


def _line_acid() -> torch.Tensor:
    x = torch.arange(64, dtype=torch.float64) - 31.5
    row = 0.05 + 0.45 * (1.0 - torch.exp(-(x**2) / 200.0))  # line centred, edges at ~12.7 nm
    return row.expand(64, 64).clone()  # the line runs along the rows


def _estimate(dose_scale: float, **kw) -> dict:
    acid = _line_acid()
    rng = torch.Generator().manual_seed(12345)
    return ler_lwr_estimate(
        acid,
        dose=dose_scale * acid / 0.5,
        develop_threshold=0.3,
        shot_noise_rng=rng,
        dx_nm=1.0,
        n_realisations=8,
        average=True,
        **kw,
    )


def test_ler_follows_photon_statistics():
    low, high = _estimate(80.0), _estimate(1280.0)
    ratio = low["ler"] / high["ler"]
    assert 2.8 < ratio < 5.7, ratio  # 16x dose -> 4x lower LER
    assert 0.6 < low["ler"] < 2.5
    assert high["ler"] < 0.6  # sub-pixel edges
    assert 1.1 < low["lwr"] / low["ler"] < 1.8  # independent edges: sqrt(2)


def test_se_blur_is_a_parameter_and_zero_disables_it():
    blurred = _estimate(1280.0)
    sharper = _estimate(1280.0, se_blur_nm=0.0)
    assert sharper["ler"] > blurred["ler"]
    assert _estimate(1280.0, se_blur_nm=2.5)["ler"] == pytest.approx(blurred["ler"], rel=1e-12)
