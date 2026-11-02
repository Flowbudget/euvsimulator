"""Mask 3D simulation — Rigorous Coupled-Wave Analysis (RCWA).

Submodules
----------
rcwa_torch
    Full 1D RCWA solver in PyTorch (TE + TM polarisation) with
    S-matrix cascade, convergence driver, and autograd support.
rcwa2d
    2D RCWA solver for crossed gratings (contact holes, SRAM, etc.)
    with 2D Fourier expansion and S-matrix cascade.
geometry
    Mask stack builder: absorber profiles, multilayer substrate,
    and conversion to permittivity Fourier coefficients.
"""

from __future__ import annotations
