"""Regression guard: grating profiles must be sampled where the FFT reads them.

permittivity_toeplitz (and its 2D counterpart) take sample k at
x_k = k * P / N. Until 2026-10 the profile builders sampled the closed
interval linspace(0, P, N) instead (spacing P / (N - 1)) and kept the samples
with |x - P/2| <= w/2: the line was stretched by N / (N - 1), its width was
rounded to whole samples (duty 0.3: 18 of 64 samples = 0.281, 306 of 1024 =
0.2988) and its centre sat half a sample left of P/2.
"""

import math

import pytest
import torch

from euvsimulator.mask3d.geometry import MaskLayer, MaskStack, build_permittivity_profile
from euvsimulator.mask3d.rcwa2d import contact_hole_profile, rectangular_island_profile
from euvsimulator.mask3d.rcwa_torch import binary_grating_profile

EPS_LINE = 0.88 + 0.07j
EPS_SPACE = 1.0 + 0.0j


def _analytic(duty, m):
    """Fourier coefficient of the line |x - P/2| <= duty*P/2 (period P)."""
    d_eps = EPS_LINE - EPS_SPACE
    if m == 0:
        return EPS_SPACE + d_eps * duty
    return d_eps * math.sin(math.pi * m * duty) / (math.pi * m) * (-1) ** m


def _coefficients(eps):
    n = eps.shape[0]
    return torch.fft.fft(eps) / n


@pytest.mark.parametrize("n", [64, 1024])
@pytest.mark.parametrize("duty", [0.3, 0.5, 0.123])
def test_binary_grating_profile_has_the_exact_fourier_coefficients(n, duty):
    period = 64e-9
    eps = binary_grating_profile(period, duty * period, EPS_LINE, EPS_SPACE, n_samples=n)
    c = _coefficients(eps)
    assert complex(c[0]) == pytest.approx(_analytic(duty, 0), abs=1e-12)
    d_eps = abs(EPS_LINE - EPS_SPACE)
    for m in range(1, 6):
        # cell averaging leaves only the sinc(m/N) roll-off and the aliases
        tol = 4e-3 * d_eps if n == 64 else 1e-5 * d_eps
        assert abs(complex(c[m]) - _analytic(duty, m)) < tol, (m, complex(c[m]))
        assert abs(complex(c[-m]) - _analytic(duty, -m)) < tol, (-m, complex(c[-m]))


def test_build_permittivity_profile_duty_and_centre():
    """The pipeline's mask (64/32 nm wafer, 4x) and a duty-0.3 mask."""
    nk = complex(0.94, 0.035)
    for period_nm, line_nm in ((256.0, 128.0), (256.0, 76.8)):
        stack = MaskStack(
            absorber_layers=[MaskLayer(material="Ta", thickness_nm=60.0, nk=nk, etched=True)],
            period_nm=period_nm,
            line_width_nm=line_nm,
        )
        for n in (64, 1024):
            eps, _, _ = build_permittivity_profile(stack, n_samples=n)
            frac = ((eps - 1.0) / (nk**2 - 1.0)).real
            assert float(frac.sum()) == pytest.approx(n * line_nm / period_nm, abs=1e-9)
            # symmetric about sample n/2 = x = P/2, the FFT position of P/2
            j = torch.arange(1, n // 2)
            assert torch.equal(eps[n // 2 + j], eps[n // 2 - j])
            assert complex(eps[n // 2]) == nk**2


def test_rectangular_island_profile_area_and_centre():
    px, py, wx, wy, n = 128e-9, 64e-9, 40e-9, 19.2e-9, 64
    eps = rectangular_island_profile(px, py, wx, wy, 2.0 + 0.0j, 1.0 + 0.0j, n, n)
    frac = (eps - 1.0).real
    assert float(frac.sum()) == pytest.approx(n * n * (wx / px) * (wy / py), abs=1e-9)
    j = torch.arange(1, n // 2)
    assert torch.equal(eps[n // 2 + j, :], eps[n // 2 - j, :])
    assert torch.equal(eps[:, n // 2 + j], eps[:, n // 2 - j])


def test_contact_hole_profile_is_centred_on_the_fft_grid():
    p, r, n = 128e-9, 30e-9, 64
    eps = contact_hole_profile(p, p, r, 1.0 + 0.0j, 2.0 + 0.0j, n, n)
    j = torch.arange(1, n // 2)
    assert torch.equal(eps[n // 2 + j, :], eps[n // 2 - j, :])
    assert torch.equal(eps[:, n // 2 + j], eps[:, n // 2 - j])
    hole = int((eps.real < 1.5).sum())
    # binary raster: the area is quantised, not stretched by n / (n - 1)
    assert hole == pytest.approx(math.pi * r**2 / (p / n) ** 2, rel=0.02)
