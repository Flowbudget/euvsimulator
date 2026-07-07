"""LPP tin-plasma source model for EUV lithography.

Submodules
----------
plasma
    Parametric LPP Sn-plasma source: spectral emission, angular
    distribution, in-band power calibration.
spectrum
    Spectral weighting, in-band efficiency fraction, dose-to-wafer
    mapping (photons / nm²).
"""

from __future__ import annotations

from euv.source.plasma import LPPPlasmaSource
from euv.source.spectrum import (
    dose_to_wafer,
    in_band_efficiency,
    photons_per_nm2,
)

__all__ = [
    "LPPPlasmaSource",
    "dose_to_wafer",
    "in_band_efficiency",
    "photons_per_nm2",
]
