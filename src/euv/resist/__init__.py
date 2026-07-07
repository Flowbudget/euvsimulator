"""Resist process simulation — exposure, PEB, and development.

The resist module models the three core steps of chemically amplified
EUV lithography resist processing:

1. **Exposure** — EUV photon absorption, photoacid generation via the
   Dill ABC model, and secondary-electron blur modelled as a Gaussian PSF.

2. **Post-exposure bake (PEB)** — reaction-diffusion of photoacid,
   including deprotection reaction kinetics with finite-difference or
   analytical solution.

3. **Development** — Mack (enhanced) dissolution-rate model, surface
   advancement for threshold development, and critical-dimension (CD)
   extraction from the developed resist profile.

All models are implemented in PyTorch and are fully differentiable, making
them suitable not only for forward simulation but also for gradient-based
inverse design / source-mask optimisation (SMO) workflows.

Submodules
----------
exposure
    EUV exposure model (Dill ABC + SE blur + dose-to-acid map).
peb
    Post-exposure bake (reaction-diffusion + deprotection kinetics).
develop
    Development model (Mack dissolution, surface advancement, CD
    extraction).
"""

from __future__ import annotations

from euv.resist.exposure import (
    dill_abc_exposure,
    dose_to_acid,
    gaussian_se_blur,
)
from euv.resist.peb import (
    reaction_diffusion_adi,
    reaction_diffusion_analytical,
    deprotection_fd,
    deprotection_analytical,
)
from euv.resist.develop import (
    MackModel,
    threshold_development,
    extract_cd,
    surface_advancement_level_set,
)

__all__ = [
    # exposure
    "dill_abc_exposure",
    "gaussian_se_blur",
    "dose_to_acid",
    # peb
    "reaction_diffusion_adi",
    "reaction_diffusion_analytical",
    "deprotection_fd",
    "deprotection_analytical",
    # develop
    "MackModel",
    "threshold_development",
    "surface_advancement_level_set",
    "extract_cd",
]