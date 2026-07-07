"""Mask 3D simulation — Rigorous Coupled-Wave Analysis (RCWA).

Submodules
----------
rcwa_torch
    Full 1D RCWA solver in PyTorch (TE + TM polarisation) with
    S-matrix cascade, convergence driver, and autograd support.
geometry
    Mask stack builder: absorber profiles, multilayer substrate,
    and conversion to permittivity Fourier coefficients.
"""

from __future__ import annotations