"""Wafer-CD data structures and parameter fitting for resist-model calibration.

This module implements the core calibration loop: given measured CD data from
a focus-exposure matrix (FEM) and a simulation pipeline, find the resist-model
parameters that minimise the RMSE between simulation and measurement.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize

# ──────────────────────────────────────────────────────────
# Data container
# ──────────────────────────────────────────────────────────


@dataclass
class WaferCDData:
    """Wafer CD measurements from a focus-exposure matrix (FEM).

    Parameters
    ----------
    dose_values : (D,) ndarray
        Exposure dose values [mJ/cm²] — one per row of the CD matrix.
    focus_values : (F,) ndarray
        Focus offset values [nm] — one per column of the CD matrix.
    cd_matrix_nm : (D, F) ndarray
        Measured CD values [nm] at each (dose, focus) combination.

    Notes
    -----
    The CD matrix rows correspond to increasing dose, and columns to
    increasing focus (Bossung plot convention).
    """

    dose_values: np.ndarray
    focus_values: np.ndarray
    cd_matrix_nm: np.ndarray

    def __post_init__(self) -> None:
        """Validate shapes and units."""
        self.dose_values = np.asarray(self.dose_values, dtype=float)
        self.focus_values = np.asarray(self.focus_values, dtype=float)
        self.cd_matrix_nm = np.asarray(self.cd_matrix_nm, dtype=float)
        D = len(self.dose_values)
        F = len(self.focus_values)
        if self.cd_matrix_nm.shape != (D, F):
            raise ValueError(
                f"cd_matrix_nm shape {self.cd_matrix_nm.shape} does not match (dose={D}, focus={F})"
            )

    @property
    def n_dose(self) -> int:
        """Number of dose rows."""
        return len(self.dose_values)

    @property
    def n_focus(self) -> int:
        """Number of focus columns."""
        return len(self.focus_values)

    def flatten(self) -> Tuple[np.ndarray, np.ndarray]:
        """Flatten the FEM data for least-squares fitting.

        Returns
        -------
        x : (N, 2) ndarray
            Array of (dose, focus) pairs for each measurement.
        y : (N,) ndarray
            Corresponding CD measurements [nm].
        """
        D, F = self.cd_matrix_nm.shape
        doses = np.broadcast_to(self.dose_values[:, None], (D, F))
        foci = np.broadcast_to(self.focus_values[None, :], (D, F))
        x = np.column_stack([doses.ravel(), foci.ravel()])
        y = self.cd_matrix_nm.ravel()
        return x, y


# ──────────────────────────────────────────────────────────
# Objective function
# ──────────────────────────────────────────────────────────


def objective_resist(
    params: np.ndarray,
    data: WaferCDData,
    pipeline_fn: Callable,
    param_names: List[str],
) -> float:
    """RMSE objective for resist-model parameter fitting.

    Evaluates the pipeline at every (dose, focus) FEM point using the current
    parameter set and returns the root-mean-square error against measured CD.

    Parameters
    ----------
    params : (P,) ndarray
        Parameter values in the order specified by ``param_names``.
    data : WaferCDData
        Measured FEM wafer data.
    pipeline_fn : Callable
        A callable ``pipeline_fn(dose, focus, **param_dict) -> cd_nm`` that
        runs the simulation pipeline and returns a single CD value [nm].
    param_names : list of str
        Ordered list of parameter names corresponding to ``params``.

    Returns
    -------
    rmse : float
        Root-mean-square error [nm].
    """
    param_dict = dict(zip(param_names, params))
    D, F = data.cd_matrix_nm.shape
    sim_cd = np.zeros((D, F), dtype=float)

    for i in range(D):
        dose = float(data.dose_values[i])
        for j in range(F):
            focus = float(data.focus_values[j])
            try:
                cd = float(pipeline_fn(dose=dose, focus=focus, **param_dict))
            except Exception as exc:
                warnings.warn(f"Pipeline failed at (dose={dose}, focus={focus}): {exc}")
                cd = 0.0
            sim_cd[i, j] = cd

    residuals = sim_cd.ravel() - data.cd_matrix_nm.ravel()
    rmse = float(np.sqrt(np.mean(residuals**2)))
    return rmse


# ──────────────────────────────────────────────────────────
# Parameter fitting
# ──────────────────────────────────────────────────────────


def fit_resist_params(
    data: WaferCDData,
    initial_params: Dict[str, float],
    pipeline_fn: Callable,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    method: str = "Nelder-Mead",
    options: Optional[Dict] = None,
) -> Dict[str, object]:
    """Fit resist-model parameters to measured FEM CD data.

    Uses :func:`scipy.optimize.minimize` to minimise the RMSE between simulated
    and measured CD over the focus-exposure matrix.

    Parameters
    ----------
    data : WaferCDData
        Measured FEM wafer data.
    initial_params : dict
        Initial guess for the parameters to fit.  Keys are parameter names,
        values are starting values.  All keys are fitted.
    pipeline_fn : Callable
        A callable ``pipeline_fn(dose, focus, **param_dict) -> cd_nm`` that
        runs the simulation pipeline.
    bounds : dict of str -> (float, float), optional
        Bounds for each fitted parameter, e.g. ``{'R_max': (10, 500)}``.
        Parameters not in ``bounds`` are unbounded.
    method : str
        SciPy minimisation method.  Default ``'Nelder-Mead'`` (gradient-free,
        robust for noisy objectives).  For gradient-based methods use
        ``'L-BFGS-B'`` or ``'SLSQP'``.
    options : dict, optional
        Options passed to ``scipy.optimize.minimize`` (e.g. ``{'maxiter': 500}``).

    Returns
    -------
    result : dict
        Dictionary with keys:

        - ``'fitted_params'`` — dict of fitted parameter names → fitted values
        - ``'rmse'`` — final RMSE [nm]
        - ``'success'`` — whether optimiser converged
        - ``'message'`` — optimiser termination message
        - ``'n_iter'`` — number of iterations
        - ``'nfev'`` — number of function evaluations
    """
    param_names = list(initial_params.keys())
    x0 = np.array([initial_params[name] for name in param_names], dtype=float)

    # Build bounds array in scipy format
    scipy_bounds: Optional[List[Tuple[float, float]]] = None
    if bounds is not None:
        scipy_bounds = []
        for name in param_names:
            if name in bounds:
                scipy_bounds.append((bounds[name][0], bounds[name][1]))
            else:
                scipy_bounds.append((None, None))  # unbounded

    if options is None:
        options = {"maxiter": 1000, "xatol": 1e-4, "fatol": 1e-4}

    def _objective(p: np.ndarray) -> float:
        return objective_resist(p, data, pipeline_fn, param_names)

    result = minimize(
        _objective,
        x0,
        method=method,
        bounds=scipy_bounds,
        options=options,
    )

    fitted_values = result.x
    fitted_dict = dict(zip(param_names, fitted_values.tolist()))

    return {
        "fitted_params": fitted_dict,
        "rmse": float(result.fun),
        "success": bool(result.success),
        "message": str(result.message),
        "n_iter": int(result.nit) if hasattr(result, "nit") else -1,
        "nfev": int(result.nfev) if hasattr(result, "nfev") else -1,
    }


# ──────────────────────────────────────────────────────────
# Bootstrap uncertainty quantification
# ──────────────────────────────────────────────────────────


def bootstrap_fit(
    data: WaferCDData,
    pipeline_fn: Callable,
    initial_params: Dict[str, float],
    n_samples: int = 100,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    method: str = "Nelder-Mead",
    ci_percentile: float = 95.0,
    seed: Optional[int] = None,
) -> Dict[str, object]:
    """Bootstrap estimation of parameter confidence intervals.

    Resamples the CD matrix (rows = dose conditions) with replacement and
    refits the parameters on each bootstrap sample to produce empirical
    distributions from which percentile-based confidence intervals are
    derived.

    Parameters
    ----------
    data : WaferCDData
        Measured FEM wafer data.
    pipeline_fn : Callable
        Simulation pipeline function.
    initial_params : dict
        Initial parameter guess.
    n_samples : int
        Number of bootstrap resamples.  Default 100.
    bounds : dict, optional
        Parameter bounds (same format as :func:`fit_resist_params`).
    method : str
        Optimisation method.  Default ``'Nelder-Mead'``.
    ci_percentile : float
        Confidence level for interval [%].  Default 95.0.
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    result : dict
        Dictionary with keys:

        - ``'param_names'`` — list of fitted parameter names
        - ``'fitted_on_original'`` — dict of params fitted to original data
        - ``'bootstrap_samples'`` — (n_samples, P) ndarray of fitted parameter
          values from each bootstrap replica
        - ``'ci_lower'`` — dict of lower confidence bounds (one per param)
        - ``'ci_upper'`` — dict of upper confidence bounds (one per param)
        - ``'ci_level'`` — confidence level used
    """
    rng = np.random.default_rng(seed)
    D, F = data.cd_matrix_nm.shape

    # Fit on original data first
    orig_fit = fit_resist_params(data, initial_params, pipeline_fn, bounds=bounds, method=method)
    param_names = list(initial_params.keys())
    n_params = len(param_names)
    boot_samples = np.zeros((n_samples, n_params), dtype=float)

    for s in range(n_samples):
        # Resample rows (dose conditions) with replacement
        row_indices = rng.integers(0, D, size=D)
        boot_dose = data.dose_values[row_indices]
        boot_cd = data.cd_matrix_nm[row_indices, :]  # (D, F)

        boot_data = WaferCDData(
            dose_values=boot_dose,
            focus_values=data.focus_values,
            cd_matrix_nm=boot_cd,
        )

        try:
            fit_result = fit_resist_params(
                boot_data,
                initial_params,
                pipeline_fn,
                bounds=bounds,
                method=method,
            )
            if fit_result["success"]:
                vals = [fit_result["fitted_params"][name] for name in param_names]
                boot_samples[s, :] = vals
            else:
                boot_samples[s, :] = np.nan
        except Exception:
            boot_samples[s, :] = np.nan

    # Drop failed runs
    valid = ~np.any(np.isnan(boot_samples), axis=1)
    valid_samples = boot_samples[valid]

    if len(valid_samples) < max(10, n_samples // 4):
        warnings.warn(
            f"Only {len(valid_samples)} / {n_samples} bootstrap runs succeeded; "
            f"confidence intervals may be unreliable."
        )

    # Percentile confidence intervals
    alpha = (100.0 - ci_percentile) / 2.0
    ci_lower_pct = alpha
    ci_upper_pct = 100.0 - alpha

    ci_lower = {}
    ci_upper = {}
    for idx, name in enumerate(param_names):
        vals = valid_samples[:, idx]
        if len(vals) > 0:
            ci_lower[name] = float(np.percentile(vals, ci_lower_pct))
            ci_upper[name] = float(np.percentile(vals, ci_upper_pct))
        else:
            ci_lower[name] = float("nan")
            ci_upper[name] = float("nan")

    return {
        "param_names": param_names,
        "fitted_on_original": orig_fit["fitted_params"],
        "bootstrap_samples": boot_samples,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "ci_level": ci_percentile,
    }


# ──────────────────────────────────────────────────────────
# Synthetic calibration test
# ──────────────────────────────────────────────────────────


def calibrate_on_synthetic(
    target_params: Dict[str, float],
    pipeline_fn: Callable,
    noise_std: float = 1.0,
    dose_values: Optional[np.ndarray] = None,
    focus_values: Optional[np.ndarray] = None,
    seed: Optional[int] = None,
) -> Dict[str, object]:
    """Test that the calibration can recover known parameters.

    Generates a synthetic FEM data set from known target parameters, adds
    Gaussian measurement noise, then runs the fitting procedure and reports
    the relative error between fitted and target parameters.

    Parameters
    ----------
    target_params : dict
        Known "true" parameter values used to generate synthetic data.
    pipeline_fn : Callable
        Simulation pipeline function (the same one used in calibration).
    noise_std : float
        Standard deviation of Gaussian measurement noise [nm].  Default 1.0.
    dose_values : (D,) ndarray, optional
        Dose grid [mJ/cm²].  Default: ``np.linspace(12, 28, 5)``.
    focus_values : (F,) ndarray, optional
        Focus grid [nm].  Default: ``np.linspace(-60, 60, 5)``.
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    result : dict
        Dictionary with keys:

        - ``'target_params'`` — the known true parameters
        - ``'fitted_params'`` — parameters recovered by calibration
        - ``'relative_error'`` — dict of relative error per parameter (frac)
        - ``'rmse'`` — RMSE of the fit [nm]
        - ``'noise_std_used'`` — noise level applied
        - ``'n_dose'``, ``'n_focus'`` — grid dimensions
    """
    rng = np.random.default_rng(seed)

    if dose_values is None:
        dose_values = np.linspace(12.0, 28.0, 5)
    if focus_values is None:
        focus_values = np.linspace(-60.0, 60.0, 5)

    D = len(dose_values)
    F = len(focus_values)
    cd_sim = np.zeros((D, F), dtype=float)

    # Generate synthetic CD data from target parameters
    for i in range(D):
        dose = float(dose_values[i])
        for j in range(F):
            focus = float(focus_values[j])
            try:
                cd_sim[i, j] = float(pipeline_fn(dose=dose, focus=focus, **target_params))
            except Exception as exc:
                warnings.warn(f"Pipeline failed at (dose={dose}, focus={focus}): {exc}")
                cd_sim[i, j] = 0.0

    # Add Gaussian noise
    cd_noisy = cd_sim + rng.normal(0.0, noise_std, size=cd_sim.shape)

    data = WaferCDData(
        dose_values=dose_values,
        focus_values=focus_values,
        cd_matrix_nm=cd_noisy,
    )

    # Fit: use target params as initial guess with small perturbation
    initial_guess = {k: v * (1.0 + 0.05 * rng.uniform(-1, 1)) for k, v in target_params.items()}

    fit_result = fit_resist_params(data, initial_guess, pipeline_fn)

    fitted = fit_result["fitted_params"]

    # Relative errors
    rel_errors = {}
    for key in target_params:
        target = target_params[key]
        fitted_val = fitted.get(key, target)
        rel_errors[key] = abs(fitted_val - target) / max(abs(target), 1e-12)

    return {
        "target_params": target_params,
        "fitted_params": fitted,
        "relative_error": rel_errors,
        "rmse": fit_result["rmse"],
        "noise_std_used": noise_std,
        "n_dose": D,
        "n_focus": F,
    }
