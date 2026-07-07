"""Calibration pipeline — wafer-CD data, least-squares fitting, uncertainty quantification.

The calibration module bridges the gap between simulated lithography and
measured wafer data.  It provides tools for fitting resist-model parameters
from focus-exposure matrix (FEM) CD-SEM measurements, quantifying parameter
uncertainty via bootstrap resampling, and validating that the calibration
procedure can recover known parameters from synthetic data.

Key capabilities:

1. **WaferCDData** — a dataclass that encapsulates dose rows, focus columns,
   and the measured CD matrix from an FEM wafer.

2. **Objective function** — root-mean-square error (RMSE) between simulated
   CD (via a user-supplied ``pipeline_fn``) and measured CD data.

3. **Parameter fitting** — least-squares minimisation using
   :func:`scipy.optimize.minimize` with support for bounded parameters,
   user-specified initial guesses, and optional gradient computation.

4. **Uncertainty quantification** — bootstrap resampling over the CD matrix
   to estimate confidence intervals on the fitted parameters (percentile
   method).

5. **Synthetic validation** — ``calibrate_on_synthetic`` generates a known
   parameter set, runs the pipeline to produce synthetic CD data (with
   controllable Gaussian noise), then verifies that the fitting procedure
   recovers the target parameters within a specified tolerance.

All CD data is in nanometres; the pipeline function is expected to accept a
dose value and a focus value and return a CD in nanometres.

References
----------
C. A. Mack, "Calibration of lithography simulation models", Proc. SPIE
5754, 117–128 (2005).

A. Erdmann et al., "International SEMATECH lithography model calibration
and verification project", J. Micro/Nanolith. MEMS MOEMS 5, 023005 (2006).
"""

from __future__ import annotations

from euv.calibrate.wafer_fit import (
    WaferCDData,
    bootstrap_fit,
    calibrate_on_synthetic,
    fit_resist_params,
    objective_resist,
)

__all__ = [
    "WaferCDData",
    "fit_resist_params",
    "objective_resist",
    "bootstrap_fit",
    "calibrate_on_synthetic",
]