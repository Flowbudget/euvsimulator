"""Aerial image formation — partially coherent imaging.

Submodules
----------
abbe
    Abbe's method: sum over illumination source points for the
    physically correct aerial image with mask-3D corrections.
hopkins
    Hopkins/TCC method: precomputed transmission cross coefficient
    for accelerated O(N² log N) imaging via sum of coherent systems
    (SOCS).  Thin-mask approximation suitable for OPC loops.
pupil
    Projection pupil: numerical aperture, anamorphic (4×/8× for
    High-NA EUV), Zernike aberrations, flare.
source
    Illumination source shapes: conventional (disk), annular,
    dipole (XY), quasar (CQuad), and custom free-form.
"""

from __future__ import annotations
