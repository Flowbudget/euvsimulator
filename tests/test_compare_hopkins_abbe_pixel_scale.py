"""Regression tests: pixel scale in ``compare_hopkins_abbe``.

``compute_tcc`` has no pixel argument: it lays the pupil out with radius G/2
FFT pixels, which is a pixel pitch of lambda/(2 NA).  ``abbe_image`` honours
its ``period_m`` (the pixel pitch).  ``compare_hopkins_abbe`` defaulted to
``period_m=1e-6``, for which the Abbe pupil covers the whole grid, so a default
call compared a filtered Hopkins image with an unfiltered Abbe image (relative
error 4.4 % conventional, 2.4 % dipole; 22-26 % at a 5 nm pixel).
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.aerial.hopkins import compare_hopkins_abbe
from euvsimulator.aerial.pupil import circular_pupil, pupil_grid
from euvsimulator.aerial.source import conventional, dipole_x

G = 24
NA = 0.33


def _thin_mask() -> torch.Tensor:
    """Centred 3-pixel dark line on a bright background (as in test_hopkins.py)."""
    mask = torch.ones(G, G, dtype=torch.float64)
    mask[G // 2 - 1 : G // 2 + 2, :] = 0.0
    return mask


SOURCES = {
    "conventional": lambda: conventional(G, sigma=0.8),
    "dipole": lambda: dipole_x(G, sigma=0.15, sigma_out=0.7, separation=0.55),
}


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_default_call_compares_like_with_like(name):
    """Without period_m both methods use the pixel lambda/(2 NA) and agree within 2 %."""
    fx, fy, _ = pupil_grid(G, na=NA)
    result = compare_hopkins_abbe(
        _thin_mask(), SOURCES[name](), circular_pupil(G, na=NA), fx, fy, na=NA, grid=G
    )
    assert result["relative_error"] < 0.02
    explicit = compare_hopkins_abbe(
        _thin_mask(),
        SOURCES[name](),
        circular_pupil(G, na=NA),
        fx,
        fy,
        na=NA,
        grid=G,
        period_m=13.5e-9 / (2 * NA),
    )
    assert torch.equal(result["abbe_aerial"], explicit["abbe_aerial"])
    assert torch.equal(result["hopkins_aerial"], explicit["hopkins_aerial"])


@pytest.mark.parametrize("period_m", [1e-6, 64e-9, 5e-9])
def test_other_pixel_is_rejected(period_m):
    """compute_tcc only knows the pixel lambda/(2 NA); any other value cannot compare."""
    fx, fy, _ = pupil_grid(G, na=NA)
    with pytest.raises(ValueError, match="pixel"):
        compare_hopkins_abbe(
            _thin_mask(),
            conventional(G, sigma=0.8),
            circular_pupil(G, na=NA),
            fx,
            fy,
            na=NA,
            grid=G,
            period_m=period_m,
        )
