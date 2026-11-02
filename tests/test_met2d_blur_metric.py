"""met2d_config validates blur_metric (plan pipeline-1, step 2).

Until 2026-10 every value other than exactly "contact" (e.g. "Contact")
silently selected the corner metric (sigma 14.78 nm instead of 10.11 nm).
"""

import pytest

from euvsimulator.presets import (
    MET2D_BLUR_CONTACT_SIGMA_NM,
    MET2D_BLUR_CORNER_SIGMA_NM,
    met2d_config,
)


@pytest.mark.parametrize("bad", ["Contact", "corners", "fwhm", ""])
def test_unknown_blur_metric_is_rejected(bad):
    with pytest.raises(ValueError, match="blur_metric must be"):
        met2d_config(blur_metric=bad)


def test_known_blur_metrics_are_unchanged():
    assert met2d_config().peb_sigma_diff == MET2D_BLUR_CONTACT_SIGMA_NM
    assert met2d_config(blur_metric="contact").peb_sigma_diff == MET2D_BLUR_CONTACT_SIGMA_NM
    assert met2d_config(blur_metric="corner").peb_sigma_diff == MET2D_BLUR_CORNER_SIGMA_NM
