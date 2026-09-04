"""Gaussian blur on periodic fields: exact for any kernel size.

Until 2026-09-04 the kernel was clamped to the image size, so a PEB blur
wider than one pitch was silently truncated at ~1σ (MTF 0.12 instead of
0.018 for σ = 19.9 nm on the 44 nm / 256 px grid). These tests pin the
analytic modulation transfer of a Gaussian on a periodic grid,
MTF(f) = exp(−2π²σ²f²), for σ from well below to well above the period,
plus mass conservation and single-row fields.
"""

import math

import pytest
import torch

from euvsimulator.resist.exposure import gaussian_se_blur

torch.set_default_dtype(torch.float64)


@pytest.mark.parametrize("sigma", [1.0, 5.0, 7.0, 10.0, 14.0, 19.9, 40.0])
@pytest.mark.parametrize("rows", [256, 1])
def test_periodic_gaussian_mtf_is_analytic(sigma, rows):
    P, W = 44.0, 256
    dx = P / W
    x = torch.arange(W) * dx
    f = torch.cos(2 * math.pi * x / P).view(1, W).expand(rows, W).clone()
    out = gaussian_se_blur(f, sigma=sigma, dx=dx)
    mtf_num = float(out[0].abs().max())
    mtf_exact = math.exp(-2 * math.pi**2 * sigma**2 / P**2)
    # Discrete, 4σ-truncated kernel vs continuous Gaussian: 3e-3 relative
    # (truncation + sampling), or 2e-5 absolute where the MTF is below the
    # kernel's truncation ripple (σ >> P).
    assert mtf_num == pytest.approx(mtf_exact, rel=3e-3, abs=2e-5)


@pytest.mark.parametrize("sigma", [0.5, 6.0, 30.0])
def test_blur_conserves_mass_and_is_nonnegative(sigma):
    torch.manual_seed(0)
    f = torch.rand(64, 128)
    out = gaussian_se_blur(f, sigma=sigma, dx=0.25)
    assert float(out.sum()) == pytest.approx(float(f.sum()), rel=1e-12)
    assert float(out.min()) >= -1e-12


def test_single_row_field_blurs_along_x():
    """A (1, W) field must be blurred along x exactly like one row of a
    (H, W) field; previously the kernel was clamped to min(H, W) = 1."""
    W, dx, sigma = 201, 0.25, 4.0
    f1 = torch.zeros(1, W)
    f1[0, W // 2] = 1.0
    fH = f1.expand(16, W).clone()
    o1 = gaussian_se_blur(f1, sigma=sigma, dx=dx)
    oH = gaussian_se_blur(fH, sigma=sigma, dx=dx)
    assert torch.allclose(o1[0], oH[0], atol=1e-12)
    xc = (torch.arange(W) - W // 2) * dx
    sx = math.sqrt(float((o1[0] * xc**2).sum() / o1[0].sum()))
    assert sx == pytest.approx(sigma, rel=0.02)


def test_fft_and_direct_paths_agree():
    torch.manual_seed(1)
    f = torch.rand(96, 96)
    direct = gaussian_se_blur(f, sigma=3.0, dx=1.0)             # kernel 19 px -> direct
    fft = gaussian_se_blur(f, sigma=3.0, dx=1.0, kernel_size=65)  # forced FFT path, same sigma
    # A 65-tap kernel contains the 19-tap one plus negligible 3σ+ tails.
    assert float((direct - fft).abs().max()) < 1e-4 * float(f.max())
