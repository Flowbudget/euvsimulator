"""Regression tests: pixel scale of ``abbe_image``.

``abbe_image`` reads ``period_m`` as the PIXEL pitch of the mask grid: the FFT
spacing is ``1 / (period_m * G)`` and the pupil has a radius of
``NA / lambda * period_m * G`` FFT pixels.  Its docstring called the argument
the mask period, and the default ``period_m=64e-9`` (also in ``chunked_abbe``)
is a 64 nm pixel, for which the pupil is larger than the grid: a default call
did not filter the mask at all, and a caller who passed the pattern period got
the same silent all-pass.
"""

from __future__ import annotations

import warnings

import pytest
import torch

from euvsimulator.accel.chunked import chunked_abbe
from euvsimulator.aerial.abbe import abbe_image
from euvsimulator.aerial.pupil import pupil_grid
from euvsimulator.aerial.source import conventional

LAM = 13.5e-9


def _pupil(G: int, na: float):
    fx, fy, inside = pupil_grid(G, na=na)
    return fx, fy, inside.to(torch.complex128)


def _spectrum(mask: torch.Tensor) -> torch.Tensor:
    """Centred spectrum, as abbe_image expects."""
    return torch.fft.fftshift(torch.fft.fft2(mask.to(torch.complex128)))


def _contrast(img: torch.Tensor) -> float:
    return float((img.max() - img.min()) / (img.max() + img.min()))


def _checkerboard(G: int) -> torch.Tensor:
    i = torch.arange(G)
    return ((i[:, None] + i[None, :]) % 2).to(torch.float64)


def _lines(G: int, pitch_px: int) -> torch.Tensor:
    i = torch.arange(G)
    row = ((i % pitch_px) < pitch_px // 2).to(torch.float64)
    return row[:, None].expand(G, G).clone()


@pytest.mark.parametrize("fn", [abbe_image, chunked_abbe], ids=["abbe_image", "chunked_abbe"])
def test_default_call_filters_beyond_cutoff(fn):
    """The default pixel is lambda/(2 NA), so the optics filter.

    A 2-pixel checkerboard has its first harmonic at |f| = sqrt(2) NA/lambda on
    that grid, beyond the cut-off (1 + sigma) NA/lambda for sigma = 0.3: only
    the zero order passes and the image is flat.  With the former 64 nm default
    pixel the pupil covered the whole grid and the checkerboard was imaged with
    contrast 1.
    """
    G, na = 64, 0.33
    fx, fy, pupil = _pupil(G, na)
    img = fn(_spectrum(_checkerboard(G)), conventional(G, sigma=0.3), fx, fy, pupil, na=na)
    assert float(img.mean()) == pytest.approx(0.25, rel=1e-9)  # zero order 0.5, squared
    assert _contrast(img) < 1e-9


def test_default_pixel_is_lambda_over_2na():
    """Default period_m equals the pupil_grid() scale: bit-identical to the explicit value."""
    G, na = 32, 0.33
    fx, fy, pupil = _pupil(G, na)
    spec = _spectrum(_lines(G, 8))
    src = conventional(G, sigma=0.8)
    default = abbe_image(spec, src, fx, fy, pupil, na=na)
    explicit = abbe_image(spec, src, fx, fy, pupil, na=na, period_m=LAM / (2 * na))
    assert torch.equal(default, explicit)


def test_na_sets_resolution_limit_at_physical_pixel():
    """period_m is the pixel pitch: at 5 nm pixels the NA sets the resolution limit.

    The smallest pitch a line/space can have and still be imaged is
    lambda / (NA (1 + sigma)): 22.7 nm at NA 0.33 and 13.6 nm at NA 0.55 for
    sigma = 0.8.  A 20 nm pitch is therefore flat at NA 0.33 and resolved at
    NA 0.55; a 40 nm pitch is resolved at NA 0.33.
    """
    G, pixel = 64, 5e-9
    src = conventional(G, sigma=0.8)

    def contrast(pitch_px: int, na: float) -> float:
        fx, fy, pupil = _pupil(G, na)
        img = abbe_image(_spectrum(_lines(G, pitch_px)), src, fx, fy, pupil, na=na, period_m=pixel)
        return _contrast(img)

    assert contrast(4, 0.33) < 1e-9  # 20 nm pitch, below the NA 0.33 limit
    assert contrast(4, 0.55) > 0.1  # 20 nm pitch, above the NA 0.55 limit
    assert contrast(8, 0.33) > 0.1  # 40 nm pitch, above the NA 0.33 limit


def test_pixel_larger_than_nyquist_warns():
    """Passing a pixel above lambda/(2 NA) (e.g. the pattern period) warns: no filtering."""
    G, na = 64, 0.33
    fx, fy, pupil = _pupil(G, na)
    spec = _spectrum(_lines(G, 8))
    src = conventional(G, sigma=0.8)
    with pytest.warns(UserWarning, match="pixel pitch"):
        abbe_image(spec, src, fx, fy, pupil, na=na, period_m=64e-9)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        abbe_image(spec, src, fx, fy, pupil, na=na)
        abbe_image(spec, src, fx, fy, pupil, na=na, period_m=5e-9)
