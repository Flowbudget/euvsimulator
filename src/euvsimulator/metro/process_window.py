"""Process-window and Bossung analysis for EUV lithography.

The process window defines the range of exposure dose and focus
settings over which the printed Critical Dimension (CD) stays within
a specified tolerance of the target value.

Functions
---------
dose_matrix
    Run a dose-focus sweep to produce a Bossung CD matrix.
process_window
    Compute Depth of Focus (DoF) and Exposure Latitude (EL) from a
    Bossung matrix.
plot_bossung
    ASCII-table visualisation of a Bossung CD matrix.
pw_metrics
    Detailed process-window metrics including max NILS.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

# ═══════════════════════════════════════════════════════════════════
# Dose-focus matrix (Bossung)
# ═══════════════════════════════════════════════════════════════════


def dose_matrix(
    pipeline_fn: Callable,
    doses: List[float],
    focuses: List[float],
    target_cd: float = 32.0,
    tolerance: float = 0.1,
) -> np.ndarray:
    """Run a dose-focus sweep and return the Bossung CD matrix.

    Parameters
    ----------
    pipeline_fn : Callable
        Function ``fn(dose_mj_cm2, focus_nm)`` (called positionally) that returns a dict
        with key ``'cd_nm'`` (float).  Typically the project's
        ``euvsimulator.pipeline.run_simulation`` wrapped to accept focus.
    doses : list of float
        Dose values [mJ/cm²].
    focuses : list of float
        Focus offset values [nm].
    target_cd : float
        Target CD [nm].  Default 32.0.
    tolerance : float
        Fractional CD tolerance.  Default 0.1 (±10 %).

    Returns
    -------
    cd_matrix : np.ndarray
        2D array ``(N_focus, N_dose)`` of measured CD [nm].
    """
    Nf = len(focuses)
    Nd = len(doses)
    cd_matrix = np.full((Nf, Nd), np.nan)

    # Positional call: the callback may name its parameters freely. Errors propagate: until
    # 2026-09-11 every exception (including a TypeError from a callback named ``(dose, focus)``,
    # which the keyword call triggered) became NaN without a warning, and notebook 04 reported
    # DoF = EL = 0 for a whole NA sweep. A point that does not print returns a CD (0 or the
    # pitch), not an exception, so nothing legitimate is lost.
    for i, f in enumerate(focuses):
        for j, d in enumerate(doses):
            result = pipeline_fn(d, f)
            cd_matrix[i, j] = (
                float(result["cd_nm"]) if isinstance(result, dict) else float(result.cd_nm)
            )

    return cd_matrix


# ═══════════════════════════════════════════════════════════════════
# Process window extraction
# ═══════════════════════════════════════════════════════════════════


def _require_ascending(name: str, values: List[float]) -> None:
    """Raise ValueError unless *values* is strictly ascending.

    DoF and EL are differences between the ends of an in-spec run along the
    grid; a descending axis made them negative (EL) or forced them to 0 (DoF,
    through the ``focus_spacing > 0`` guard) without any warning, and a
    repeated value makes the axis ambiguous.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size > 1 and not bool(np.all(np.diff(arr) > 0)):
        raise ValueError(f"{name} must be strictly ascending, got {list(values)}")


def _run_around(mask: np.ndarray, anchor: int) -> Optional[Tuple[int, int]]:
    """First and last index of the contiguous True run that contains *anchor*.

    If ``mask[anchor]`` is False, the longest run is returned instead (the
    first one on ties); ``None`` if the mask has no True entry.  A process
    window cannot span an out-of-spec gap, so first-to-last over the whole
    mask would overstate DoF and EL.
    """
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return None
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]]))
    if mask[anchor]:
        k = int(np.searchsorted(ends, anchor))
    else:
        k = int(np.argmax(ends - starts))
    return int(starts[k]), int(ends[k])


def process_window(
    cd_matrix: np.ndarray,
    doses: List[float],
    focuses: List[float],
    target_cd: float = 32.0,
    tolerance: float = 0.1,
) -> Dict[str, float]:
    """Extract Depth of Focus (DoF) and Exposure Latitude (EL) from a
    Bossung CD matrix.

    The in-spec window is defined as all dose-focus pairs where the
    measured CD is within ``target_cd · (1 ± tolerance)``.  DoF and EL are
    the contiguous in-spec runs through the best point; an out-of-spec gap
    ends the window (before 2026-09-25 the first-to-last in-spec span was
    reported, bridging gaps).

    Parameters
    ----------
    cd_matrix : np.ndarray
        2D array ``(N_focus, N_dose)`` of measured CD [nm].
    doses : list of float
        Dose values [mJ/cm²] corresponding to columns, strictly ascending.
    focuses : list of float
        Focus values [nm] corresponding to rows, strictly ascending.
    target_cd : float
        Target CD [nm].  Default 32.0.
    tolerance : float
        Fractional CD tolerance.  Default 0.1 (±10 %).

    Returns
    -------
    pw : dict
        Keys:
        - ``'dof_nm'`` — Depth of Focus [nm] at best dose.
        - ``'el_pct'`` — Exposure Latitude [%] at best focus.
        - ``'best_dose'`` — Dose [mJ/cm²] closest to target CD at
          best focus.
        - ``'best_focus'`` — Focus [nm] with CD closest to target.

    Raises
    ------
    ValueError
        If *doses* or *focuses* is not strictly ascending.
    """
    _require_ascending("doses", doses)
    _require_ascending("focuses", focuses)
    cd_low = target_cd * (1.0 - tolerance)
    cd_high = target_cd * (1.0 + tolerance)

    Nf, Nd = cd_matrix.shape
    in_spec = (cd_matrix >= cd_low) & (cd_matrix <= cd_high) & (~np.isnan(cd_matrix))

    # Best focus: find the focus row where the CD is closest to target
    # averaged across all dose values.
    best_focus_idx = 0
    best_dose_idx = 0
    min_dev = float("inf")

    for i in range(Nf):
        row = cd_matrix[i, :]
        valid = ~np.isnan(row)
        if not valid.any():
            continue
        # Deviation at the central dose column for this focus row
        mid_j = Nd // 2
        dev = abs(float(row[mid_j]) - target_cd) if valid[mid_j] else float("inf")
        if dev < min_dev:
            min_dev = dev
            best_focus_idx = i

    # Now at the best focus row, find the dose closest to target
    best_row = cd_matrix[best_focus_idx, :]
    best_dose_idx = int(np.nanargmin(np.abs(best_row - target_cd)))
    best_focus = focuses[best_focus_idx]
    best_dose = doses[best_dose_idx]

    # DoF at best dose: number of focus rows in-spec at best dose col
    dof_nm = 0.0
    focus_spacing = (focuses[-1] - focuses[0]) / (Nf - 1) if Nf > 1 else 0.0
    if focus_spacing > 0:
        run = _run_around(in_spec[:, best_dose_idx], best_focus_idx)
        if run is not None:
            dof_nm = (run[1] - run[0]) * focus_spacing

    # EL at best focus: dose range in-spec at best focus row divided
    # by best dose × 100
    el_pct = 0.0
    if best_dose > 0:
        run = _run_around(in_spec[best_focus_idx, :], best_dose_idx)
        if run is not None:
            el_pct = (doses[run[1]] - doses[run[0]]) / best_dose * 100.0

    return {
        "dof_nm": float(dof_nm),
        "el_pct": float(el_pct),
        "best_dose": float(best_dose),
        "best_focus": float(best_focus),
    }


# ═══════════════════════════════════════════════════════════════════
# Bossung ASCII table
# ═══════════════════════════════════════════════════════════════════


def plot_bossung(
    cd_matrix: np.ndarray,
    doses: List[float],
    focuses: List[float],
) -> None:
    """Print an ASCII-table visualisation of the Bossung CD matrix.

    Parameters
    ----------
    cd_matrix : np.ndarray
        2D array ``(N_focus, N_dose)`` of measured CD [nm].
    doses : list of float
        Dose values [mJ/cm²].
    focuses : list of float
        Focus values [nm].
    """
    Nf, Nd = cd_matrix.shape

    # Header row
    header = "Focus (nm)  | " + "  ".join(f"D={d:6.2f}" for d in doses)
    print(header)
    print("-" * len(header))

    for i in range(Nf):
        row_vals = []
        for j in range(Nd):
            val = cd_matrix[i, j]
            if np.isnan(val):
                row_vals.append("   NaN  ")
            else:
                row_vals.append(f"{val:7.2f}")
        print(f"{focuses[i]:+8.1f}   | " + " ".join(row_vals))

    print(f"\nBest focus: {focuses[Nf // 2]:+.1f} nm (centre row)")


# ═══════════════════════════════════════════════════════════════════
# Process-window metrics
# ═══════════════════════════════════════════════════════════════════


def pw_metrics(
    cd_matrix: np.ndarray,
    target_cd: float,
    tolerance: float,
    nils_matrix: Optional[np.ndarray] = None,
    doses: Optional[List[float]] = None,
    focuses: Optional[List[float]] = None,
) -> Dict[str, float]:
    """Compute detailed process-window metrics from a Bossung CD matrix.

    Parameters
    ----------
    cd_matrix : np.ndarray
        2D array ``(N_focus, N_dose)`` of measured CD [nm].
    target_cd : float
        Target CD [nm].
    tolerance : float
        Fractional CD tolerance (e.g. 0.1 for ±10 %).
    nils_matrix : np.ndarray, optional
        Optional 2D array of same shape with NILS values at each
        dose-focus condition.
    doses, focuses : list of float, optional
        The dose [mJ/cm²] and focus [nm] grids of the matrix, strictly
        ascending. Required for the physical DoF/EL values; without them only
        grid-index counts can be reported (a previous version returned those
        counts under the physical keys ``dof_nm``/``el_pct`` -- fixed 2026-09-04).

    Returns
    -------
    metrics : dict
        Keys:
        - ``'dof_nm'`` — Depth of Focus [nm] at best dose (NaN if *focuses*
          not given): the contiguous in-spec focus run through the best
          point.  The best point is the in-spec CD closest to target; exact
          ties go to the candidate with the largest window.  This differs
          from :func:`process_window`, which fixes best focus on the central
          dose column, so the two can report different windows.
        - ``'el_pct'`` — Exposure Latitude [%] at best focus (NaN if *doses*
          not given).
        - ``'dof_steps'``, ``'el_steps'`` — the same windows as numbers of
          in-spec grid steps (always available).
        - ``'max_nils'`` — Maximum NILS in the in-spec region (NaN if
          *nils_matrix* not provided).
        - ``'min_nils'`` — Minimum NILS in the in-spec region.
        - ``'n_in_spec'`` — Number of dose-focus points within spec.

    Raises
    ------
    ValueError
        If *doses* or *focuses* is given and not strictly ascending.
    """
    if doses is not None:
        _require_ascending("doses", doses)
    if focuses is not None:
        _require_ascending("focuses", focuses)
    cd_low = target_cd * (1.0 - tolerance)
    cd_high = target_cd * (1.0 + tolerance)

    Nf, Nd = cd_matrix.shape
    in_spec = (cd_matrix >= cd_low) & (cd_matrix <= cd_high) & (~np.isnan(cd_matrix))
    n_in_spec = int(in_spec.sum())

    def windows(f: int, d: int) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        return _run_around(in_spec[:, d], f), _run_around(in_spec[f, :], d)

    def steps(run: Optional[Tuple[int, int]]) -> int:
        return 0 if run is None else run[1] - run[0]

    # Best point: in-spec CD closest to target.  Exact ties (synthetic data,
    # pixel-quantised stochastic CDs) go to the candidate with the largest
    # contiguous window instead of the first one in row order.
    deviations = np.where(in_spec, np.abs(cd_matrix - target_cd), np.inf)
    best_focus_idx, best_dose_idx = 0, 0
    if np.isfinite(deviations).any():
        dmin = float(np.min(deviations))
        cands = np.argwhere(deviations <= dmin + 1e-9)
        best_size = -1
        for f, d in cands:
            dof_run, el_run = windows(int(f), int(d))
            size = steps(dof_run) + steps(el_run)
            if size > best_size:
                best_size, best_focus_idx, best_dose_idx = size, int(f), int(d)

    dof_run, el_run = windows(best_focus_idx, best_dose_idx) if n_in_spec > 0 else (None, None)
    dof_steps = steps(dof_run)
    el_steps = steps(el_run)

    dof_nm = float("nan")
    el_pct = float("nan")
    if focuses is not None and len(focuses) == Nf and dof_run is not None and dof_steps > 0:
        dof_nm = float(focuses[dof_run[1]] - focuses[dof_run[0]])
    if doses is not None and len(doses) == Nd and el_run is not None and el_steps > 0:
        best_dose = float(doses[best_dose_idx])
        if best_dose > 0:
            el_pct = float(doses[el_run[1]] - doses[el_run[0]]) / best_dose * 100.0

    # NILS metrics
    max_nils = float("nan")
    min_nils = float("nan")
    if nils_matrix is not None and nils_matrix.shape == cd_matrix.shape:
        in_spec_nils = nils_matrix[in_spec]
        if len(in_spec_nils) > 0:
            max_nils = float(in_spec_nils.max())
            min_nils = float(in_spec_nils.min())

    return {
        "dof_nm": dof_nm,
        "el_pct": el_pct,
        "dof_steps": dof_steps,
        "el_steps": el_steps,
        "max_nils": max_nils,
        "min_nils": min_nils,
        "n_in_spec": n_in_spec,
    }
