"""Etch bias simulation — isotropic bias, empirical CD bias, chemistry-aware bias.

The etch module models the critical-dimension (CD) change that occurs during
plasma etching steps in EUV lithography patterning.  Etch bias converts the
latent (developer-out) resist profile into the final etched feature by
applying systematic dimensional shifts that depend on feature geometry (CD,
pitch, aspect ratio), etch chemistry, and the resist profile itself.

Four levels of etch bias modelling are provided:

1. **Isotropic bias** — morphological dilation (positive bias) or erosion
   (negative bias) of a binary contour via PyTorch operations.  Suitable for
   quick estimates where the etch is largely isotropic.

2. **Empirical CD bias** — a parametric formula relating the CD change to
   the input CD and aspect ratio:

       CD_out = CD_in + a · AR^b + c

   with typical parameters calibrated from published etch data.

3. **Chemistry-aware bias** — literature-derived bias formulas for
   different plasma chemistries (CF₄, SF₆, Cl₂, etc.), parameterised by
   CD, pitch, and etch depth.

4. **Aerial-image bias approximation** — applies a Gaussian-like convolution
   to an aerial image to approximate the effect of etch bias on the
   intensity distribution, as a fast proxy before running the full resist and
   development chain.

All operations use PyTorch tensors to maintain compatibility with the
existing :mod:`euv.resist` module and the GPU-accelerated simulation
pipeline.

References
----------
C. J. Mogab, "The loading effect in plasma etching", J. Electrochem. Soc.
124, 1262–1268 (1977).

R. A. Gottscho, C. W. Jurgensen, D. J. Vitkavage, "Microscopic uniformity
in plasma etching", J. Vac. Sci. Technol. B 10, 2133–2143 (1992).

J. W. Coburn, H. F. Winters, "Plasma etching—a discussion of mechanisms",
J. Vac. Sci. Technol. 16, 391–403 (1979).
"""

from __future__ import annotations

from euv.etch.bias import (
    apply_bias_to_aerial,
    empirical_cd_bias,
    etch_bias_from_formula,
    isotropic_bias,
)

__all__ = [
    "isotropic_bias",
    "empirical_cd_bias",
    "etch_bias_from_formula",
    "apply_bias_to_aerial",
]