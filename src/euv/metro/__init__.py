"""CD metrology and process-window analysis for EUV lithography.

This module provides high-precision critical-dimension (CD) extraction,
Normalised Image Log-Slope (NILS) computation, process-window (Bossung)
analysis, and SEM-image rendering for verification of simulated EUV
lithography profiles.

It is designed as the proper metrology replacement for the basic
:func:`~euv.resist.develop.extract_cd` function, offering:

- Sub-pixel interpolated threshold crossing for 1D line-cuts.
- 2D edge detection with line-edge roughness (LER) characterisation.
- NILS computation at feature edges.
- Binary contour extraction without scikit-image dependency.
- Dose-focus (Bossung) matrix generation and process-window metrics.
- Simulated SEM image rendering with shot noise and edge roughness.

Submodules
----------
cd
    Critical-dimension extraction from aerial/resist profiles.
process_window
    Dose-focus matrices, Bossung plots, and process-window metrics.
sem_render
    Simulated SEM-image generation for visual verification.

References
----------
C. A. Mack, "Fundamental Principles of Optical Lithography",
    Wiley, 2007.
C. A. Mack, "The Natural and Forced Resolution of a Lithographic
    Process", Proc. SPIE 1674, 1992.
B. J. Lin, "The k₁ factor and the depth of focus", Microelectronic
    Engineering 6, 31–36 (1987).
"""

from __future__ import annotations

from euv.metro.cd import (
    compute_nils,
    extract_cd_1d,
    extract_cd_2d,
    extract_contour,
    extract_multiple_lines,
)
from euv.metro.process_window import (
    dose_matrix,
    plot_bossung,
    process_window,
    pw_metrics,
)
from euv.metro.sem_render import (
    add_edge_roughness,
    add_shot_noise,
    render_sem,
)

__all__ = [
    # cd
    "extract_cd_1d",
    "extract_cd_2d",
    "compute_nils",
    "extract_contour",
    "extract_multiple_lines",
    # process_window
    "dose_matrix",
    "process_window",
    "plot_bossung",
    "pw_metrics",
    # sem_render
    "render_sem",
    "add_shot_noise",
    "add_edge_roughness",
]