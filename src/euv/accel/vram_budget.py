"""Analytical VRAM estimators for RCWA and Abbe imaging.

All formulas are based on the dominant tensor allocations for each
kernel.  Use these estimates to pre-check whether a configuration
will fit on the target GPU before launching the solver.
"""

from __future__ import annotations

import math
from typing import Optional


def estimate_rcma_vram(
    n_orders: int,
    n_layers: int,
    dtype_bytes: int = 16,
) -> int:
    """Estimate the GPU memory required for an RCWA solve.

    Dominant allocation: the per-layer eigenproblem in the Fourier
    modal method.  The eigenvalue matrix has shape ``(M, M)`` where
    ``M = 2 * n_orders + 1``, and the S-matrix cascade stores a
    handful of ``(M, M)`` matrices per layer.

    Parameters
    ----------
    n_orders : int
        Number of Fourier orders (positive integer, :math:`M = 2n+1`).
    n_layers : int
        Number of vertical layers in the mask stack.
    dtype_bytes : int
        Bytes per complex element (default 16 for ``complex128``).

    Returns
    -------
    int
        Estimated memory in bytes.
    """
    M = 2 * n_orders + 1
    # Per layer: eigenvalue matrix A (M×M), eigenvectors W (M×M),
    # eigenvalues q² (M,), S-matrix cascade (a few M×M).
    # Rough rule: 4 × M² per layer.
    bytes_per_layer = 4 * M * M * dtype_bytes
    total = n_layers * bytes_per_layer

    # Additional overhead for the profile and Toeplitz matrices
    overhead = 128 * 1024 * 1024  # 128 MB safety margin
    return total + overhead


def estimate_abbe_vram(
    grid_size: int,
    n_source_points: int,
    dtype_bytes: int = 8,
) -> int:
    """Estimate the GPU memory for a full Abbe aerial-image solve.

    The dominant memory comes from the intermediate coherent images
    accumulated over source points (each image is ``grid_size ×
    grid_size × dtype_bytes``).

    Parameters
    ----------
    grid_size : int
        Pixel grid dimension (``G × G``).
    n_source_points : int
        Number of non-zero illumination source points.
    dtype_bytes : int
        Bytes per element of the accumulated image (default 8 for
        ``float64``).

    Returns
    -------
    int
        Estimated memory in bytes.
    """
    # Per source point: shifted spectrum (G×G complex128), filtered
    # (G×G complex128), IFFT (G×G complex128), intensity (G×G float64).
    # The accumulation buffer is G×G float64.
    # Roughly 4 × G² × 16 + G² × 8 bytes per iteration,
    # but we estimate total peak as the sum of one iteration's working
    # set plus the accumulation buffer.
    gb_per_source = 4 * grid_size * grid_size * 16  # 4 complex buffers
    acc_buf = grid_size * grid_size * 8  # float64 accumulator
    peak = gb_per_source + acc_buf
    # Overhead: pupil, source, coordinate grids
    overhead = 64 * 1024 * 1024  # 64 MB
    return peak + overhead


def max_harmonics_for_vram(
    vram_budget_gb: float = 14,
    n_layers: int = 12,
) -> int:
    """Return the maximum number of Fourier orders (:math:`M`) that fit
    in *vram_budget_gb*.

    Uses the RCWA estimate (dominant memory scales as
    :math:`M^2`).  Walks upward from ``M = 3`` until the budget is
    exceeded.

    Parameters
    ----------
    vram_budget_gb : float
        Available GPU memory in GiB (default 14 — typical consumer
        card with 16 GB physical and ~2 GB reserved by the OS).
    n_layers : int
        Number of RCWA layers (default 12).

    Returns
    -------
    int
        Maximum odd *M* (number of Fourier orders) that fits.
    """
    budget_bytes = int(vram_budget_gb * (1024**3))

    # RCWA orders: M = 2 * n_orders + 1, so n_orders = (M-1)//2
    # We search for the largest odd M that fits.
    lo, hi = 3, 3
    # Exponential probe
    while estimate_rcma_vram((hi - 1) // 2, n_layers) <= budget_bytes:
        hi *= 2
        if hi > 2000:  # safety cap
            break

    best = 3
    while lo <= hi:
        mid = (lo + hi) // 2
        M = mid if mid % 2 == 1 else mid + 1  # ensure odd
        n_orders = (M - 1) // 2
        if estimate_rcma_vram(n_orders, n_layers) <= budget_bytes:
            best = M
            lo = M + 2
        else:
            hi = M - 2
    return best


def check_oom(total_bytes: int, vram_gb: float = 14) -> None:
    """Raise :class:`MemoryError` if *total_bytes* exceeds the VRAM
    budget.

    Parameters
    ----------
    total_bytes : int
        Estimated memory requirement in bytes.
    vram_gb : float
        Available VRAM in GiB (default 14).

    Raises
    ------
    MemoryError
        If the estimated memory exceeds the budget.
    """
    budget = vram_gb * (1024**3)
    if total_bytes > budget:
        used_gb = total_bytes / (1024**3)
        raise MemoryError(
            f"Estimated memory {used_gb:.2f} GiB exceeds "
            f"budget of {vram_gb:.1f} GiB.  Reduce problem size "
            "(e.g. fewer Fourier orders, fewer layers, or smaller "
            "grid) or switch to chunked processing."
        )


def vram_report() -> str:
    """Return a formatted string with VRAM estimates for common
    OpEnUV configurations.

    The report tabulates the RCWA and Abbe memory footprints
    across a range of typical problem sizes so the user can
    quickly gauge hardware requirements.

    Returns
    -------
    str
    """
    lines = [
        "=" * 72,
        "  OpEnUV — VRAM Budget Report",
        "=" * 72,
        "",
        "  RCWA estimates (complex128, 12 layers):",
        "  " + "-" * 50,
        f"    {'Orders':>8}  {'M':>5}  {'Est. VRAM':>12}",
        "    " + "-" * 30,
    ]
    for n_orders in [11, 15, 21, 31, 41, 51]:
        M = 2 * n_orders + 1
        est = estimate_rcma_vram(n_orders, n_layers=12)
        est_gb = est / (1024**3)
        lines.append(f"    {n_orders:>8}  {M:>5}  {est_gb:>10.2f} GiB")

    lines += [
        "",
        "  Abbe estimates (complex128, float64 accumulator):",
        "  " + "-" * 50,
        f"    {'Grid':>8}  {'Src pts':>8}  {'Est. VRAM':>12}",
        "    " + "-" * 30,
    ]
    for grid in [128, 256, 512, 1024]:
        for n_src in [100, 500]:
            est = estimate_abbe_vram(grid, n_src)
            est_gb = est / (1024**3)
            lines.append(f"    {grid:>4}²  {n_src:>8}  {est_gb:>10.2f} GiB")

    lines += [
        "",
        "  Max Fourier orders (M) for 14 GiB budget:",
        f"    M_max = {max_harmonics_for_vram(14)}",
        "=" * 72,
    ]
    return "\n".join(lines)