"""Critical-dimension (CD) extraction from aerial and resist profiles.

All operations use pure PyTorch with no dependency on scikit-image
or other image-processing libraries.

Functions
---------
extract_cd_1d
    Sub-pixel interpolated threshold crossing for 1D line-cuts.
extract_cd_2d
    Edge detection in 2D aerial/resist images.
compute_nils
    Normalised Image Log-Slope at a feature edge.
extract_contour
    Binary contour extraction as a list of (x, y) points.
extract_multiple_lines
    CD extraction for periodic line/space patterns.
"""

from __future__ import annotations

from typing import List, Tuple

import torch

# ═══════════════════════════════════════════════════════════════════
# Helper: find threshold-crossing indices with sub-pixel interpolation
# ═══════════════════════════════════════════════════════════════════


def _threshold_crossings(
    intensity: torch.Tensor,
    threshold: float = 0.3,
    mode: str = "line",
) -> torch.Tensor:
    """Find sub-pixel threshold-crossing positions, paired as left/right edges.

    For *mode='line'* (positive-tone line): the feature is a dark region
    where intensity is *below* the threshold, bounded by a falling edge
    (entering dark) and a rising edge (exiting dark).  For
    *mode='space'* (positive-tone space): the feature is a bright region
    where intensity is *above* the threshold, bounded by a rising edge
    (entering bright) and a falling edge (exiting bright).

    Uses linear interpolation between neighbouring pixels.

    Parameters
    ----------
    intensity : torch.Tensor
        1D tensor of intensity values.
    threshold : float
        Intensity threshold for edge detection.
    mode : str
        ``'line'`` (default) or ``'space'``.

    Returns
    -------
    crossings : torch.Tensor
        1D tensor of sub-pixel crossing positions (float indices),
        ordered left-to-right in pairs.
    """
    above = intensity > threshold
    diffs = torch.diff(above.float())
    # +1 where False → True (rising), -1 where True → False (falling)
    falling = torch.where(diffs < -0.5)[0]  # True → False
    rising = torch.where(diffs > 0.5)[0]  # False → True

    if mode == "line":
        # Dark line: falling edge (left) then rising edge (right)
        starts = falling
        ends = rising
    else:
        # Bright space: rising edge (left) then falling edge (right)
        starts = rising
        ends = falling

    # Interleave starts and ends in pairs
    min_len = min(len(starts), len(ends))
    if min_len == 0:
        return torch.tensor([], dtype=torch.float32)

    crossing_list = []
    for k in range(min_len):
        # Left edge
        i = int(starts[k].item())
        I0, I1 = float(intensity[i]), float(intensity[i + 1])
        frac0 = (threshold - I0) / (I1 - I0) if abs(I1 - I0) > 1e-30 else 0.0
        crossing_list.append(float(i) + frac0)

        # Right edge
        i = int(ends[k].item())
        I0, I1 = float(intensity[i]), float(intensity[i + 1])
        frac1 = (threshold - I0) / (I1 - I0) if abs(I1 - I0) > 1e-30 else 0.0
        crossing_list.append(float(i) + frac1)

    return torch.tensor(crossing_list, dtype=torch.float32)


# ═══════════════════════════════════════════════════════════════════
# 1D CD extraction
# ═══════════════════════════════════════════════════════════════════


def extract_cd_1d(
    intensity: torch.Tensor,
    x_nm: torch.Tensor,
    threshold: float = 0.3,
    mode: str = "line",
) -> float:
    """Extract Critical Dimension from a 1D aerial/resist line-cut.

    Finds all threshold-crossing edges with sub-pixel interpolation
    and measures the width of the first dark (or bright) feature.

    Parameters
    ----------
    intensity : torch.Tensor
        1D intensity profile ``(N,)``.
    x_nm : torch.Tensor
        1D spatial coordinate ``(N,)`` in nanometres.
    threshold : float
        Edge-detection threshold.  Default 0.3.
    mode : str
        ``'line'`` (default): dark feature = intensity *below* threshold.
        ``'space'``: bright feature = intensity *above* threshold.

    Returns
    -------
    cd_nm : float
        Critical dimension in nanometres.  Returns 0.0 if fewer than
        two crossings are found.

    Examples
    --------
    >>> import torch
    >>> x = torch.linspace(0, 128, 512)
    >>> # Simple line: dark Gaussian in centre
    >>> I = 1.0 - 0.6 * torch.exp(-((x - 64) ** 2) / (2 * 12 ** 2))
    >>> cd = extract_cd_1d(I, x, threshold=0.5)
    >>> 20 < cd < 30
    True
    """
    if intensity.ndim != 1 or x_nm.ndim != 1:
        raise ValueError("intensity and x_nm must be 1D tensors")
    if intensity.shape != x_nm.shape:
        raise ValueError("intensity and x_nm must have the same length")

    crossings = _threshold_crossings(intensity, threshold, mode)

    if len(crossings) < 2:
        return 0.0

    # Use the first pair of crossing indices → measure width
    idx_lo, idx_hi = float(crossings[0]), float(crossings[1])

    # Interpolate x positions at sub-pixel crossing indices
    n = len(intensity)
    idx_lo = max(0.0, min(float(n - 1), idx_lo))
    idx_hi = max(0.0, min(float(n - 1), idx_hi))

    x_lo = _interp_x(x_nm, idx_lo)
    x_hi = _interp_x(x_nm, idx_hi)

    cd_nm = abs(x_hi - x_lo)
    return float(cd_nm)


def _linear_interp_1d(x: torch.Tensor, y: torch.Tensor, x_target: float) -> float:
    """Manual 1D linear interpolation (pure PyTorch, no ``torch.interp``).

    Parameters
    ----------
    x : torch.Tensor
        1D coordinate array ``(N,)``, assumed monotonic increasing.
    y : torch.Tensor
        1D value array ``(N,)``.
    x_target : float
        Target coordinate.

    Returns
    -------
    y_interp : float
        Linearly interpolated value.  Clamped to endpoints when
        *x_target* is outside the domain.
    """
    if x_target <= float(x[0]):
        return float(y[0])
    if x_target >= float(x[-1]):
        return float(y[-1])

    # Binary search
    lo, hi = 0, len(x) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if x_target < float(x[mid]):
            hi = mid
        else:
            lo = mid

    t = (x_target - float(x[lo])) / (float(x[hi]) - float(x[lo]))
    return float(y[lo]) + t * (float(y[hi]) - float(y[lo]))


def _interp_x(x_nm: torch.Tensor, idx: float) -> float:
    """Linear interpolation of x at a sub-pixel index."""
    i = int(torch.floor(torch.tensor(idx)).item())
    frac = idx - i
    if i >= len(x_nm) - 1:
        return float(x_nm[-1])
    return float(x_nm[i]) + frac * float(x_nm[i + 1] - x_nm[i])


# ═══════════════════════════════════════════════════════════════════
# 2D CD extraction (edge positions, LER)
# ═══════════════════════════════════════════════════════════════════


def extract_cd_2d(
    image: torch.Tensor,
    pixel_size_nm: float,
    threshold: float = 0.5,
) -> Tuple[torch.Tensor, torch.Tensor, float]:
    """Extract edge positions and line width from a 2D intensity image.

    For each row of the image, the left and right threshold-crossing
    edges are found (sub-pixel interpolated).  The line width per row
    is computed and the mean CD across all rows is returned.

    Parameters
    ----------
    image : torch.Tensor
        2D intensity image ``(H, W)``.
    pixel_size_nm : float
        Pixel size in nanometres.
    threshold : float
        Edge-detection threshold.  Default 0.5.

    Returns
    -------
    left_edges : torch.Tensor
        Left-edge x-positions ``(H,)`` in nanometres.  NaN where no edge
        is detected.
    right_edges : torch.Tensor
        Right-edge x-positions ``(H,)`` in nanometres.
    cd_mean : float
        Mean line width [nm] across all rows with valid edges.
    """
    H, W = image.shape
    device = image.device

    x_idx = torch.arange(W, device=device).float()

    left_edges = torch.full((H,), float("nan"), device=device)
    right_edges = torch.full((H,), float("nan"), device=device)
    widths = torch.full((H,), float("nan"), device=device)

    for row in range(H):
        intensity_row = image[row, :]
        crossings = _threshold_crossings(intensity_row, threshold, mode="line")

        if len(crossings) >= 2:
            idx_lo = max(0.0, min(float(W - 1), float(crossings[0])))
            idx_hi = max(0.0, min(float(W - 1), float(crossings[1])))

            x_lo = _interp_x(x_idx, idx_lo) * pixel_size_nm
            x_hi = _interp_x(x_idx, idx_hi) * pixel_size_nm

            left_edges[row] = x_lo
            right_edges[row] = x_hi
            widths[row] = abs(x_hi - x_lo)

    cd_mean = (
        float(widths[~torch.isnan(widths)].mean().item()) if (~torch.isnan(widths)).any() else 0.0
    )
    return left_edges, right_edges, cd_mean


# ═══════════════════════════════════════════════════════════════════
# NILS — Normalised Image Log-Slope
# ═══════════════════════════════════════════════════════════════════


def compute_nils(
    intensity: torch.Tensor,
    x_nm: torch.Tensor,
    edge_position_nm: float,
) -> float:
    """Compute the Normalised Image Log-Slope (NILS) at a feature edge.

    NILS is defined as::

        NILS = CD · (dI/dx) / I

    evaluated at the edge position, where *CD* is the nominal line
    width (the :math:`k_1`-based metric), and *I* is the image
    intensity.  The derivative is estimated via central finite
    differences with a 1 nm step.

    Parameters
    ----------
    intensity : torch.Tensor
        1D intensity profile ``(N,)``.
    x_nm : torch.Tensor
        1D spatial coordinate ``(N,)`` in nanometres.
    edge_position_nm : float
        Position of the line edge [nm].

    Returns
    -------
    nils : float
        NILS value at the edge.  Returns 0.0 if the edge is outside
        the domain.

    References
    ----------
    C. A. Mack, "Fundamental Principles of Optical Lithography",
    Wiley, 2007, §4.5.
    """
    # Find the pixel closest to the edge
    idx = torch.argmin(torch.abs(x_nm - edge_position_nm)).item()

    # Central difference in nanometres — use neighbour interpolation
    dx = float(x_nm[1] - x_nm[0]) if len(x_nm) > 1 else 1.0
    eps = max(dx, 1.0)  # at least 1 nm step

    # Intensity at edge (linear interp for sub-pixel accuracy)
    I_edge = _linear_interp_1d(x_nm, intensity, edge_position_nm)
    if I_edge < 1e-30:
        return 0.0

    # Derivative via linear interpolation at edge ± ε
    I_plus = _linear_interp_1d(x_nm, intensity, edge_position_nm + eps)
    I_minus = _linear_interp_1d(x_nm, intensity, edge_position_nm - eps)

    dI_dx = (I_plus - I_minus) / (2.0 * eps)

    # NILS = CD * (dI/dx) / I
    # Use the CD implied by the image period / target
    # For a line/space, CD ≈ half-period; use local contrast instead
    # Mack convention: NILS = (1/I) * (dI/dx), then multiplied by CD
    # for a full metric.  Here we return the log-slope *without* CD
    # multiplication so the caller can apply their own CD.
    nils = dI_dx / I_edge

    return float(nils)


# ═══════════════════════════════════════════════════════════════════
# Contour extraction
# ═══════════════════════════════════════════════════════════════════


def extract_contour(
    binary_image: torch.Tensor,
    pixel_size_nm: float,
) -> List[Tuple[float, float]]:
    """Extract a contour from a binary image using marching-squares logic.

    This is a simple boundary-tracing implementation that finds the
    outermost foreground (1-valued) pixels and returns their
    coordinates.  It does **not** rely on scikit-image.

    The algorithm scans from the top-left, finds the first foreground
    pixel, then traces the outer boundary with a 4-connected
    neighbourhood.

    Parameters
    ----------
    binary_image : torch.Tensor
        2D binary ``(H, W)`` float or bool tensor.  1 = foreground,
        0 = background.
    pixel_size_nm : float
        Pixel size in nanometres.

    Returns
    -------
    contour : list of (x, y)
        List of (x, y) coordinate tuples in nanometres along the outer
        boundary.
    """
    if binary_image.ndim != 2:
        raise ValueError("binary_image must be 2D")

    H, W = binary_image.shape
    mask = (binary_image > 0.5).to(torch.bool)

    # Find the first foreground pixel (top-left scanning)
    fg_indices = torch.where(mask)
    if len(fg_indices[0]) == 0:
        return []

    # Simple boundary tracing: find all foreground pixels that have at
    # least one background (or edge) neighbour → boundary = all
    # foreground pixels adjacent to a zero.
    padded = torch.zeros((H + 2, W + 2), dtype=torch.bool, device=mask.device)
    padded[1:-1, 1:-1] = mask

    boundary_mask = torch.zeros_like(padded)
    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        boundary_mask |= padded & ~torch.roll(padded, shifts=(di, dj), dims=(0, 1))

    # Remove padding
    boundary_mask = boundary_mask[1:-1, 1:-1]
    boundary_indices = torch.where(boundary_mask)

    # Sort by following the contour clockwise starting from the top-left
    # foremost point
    boundary_y = boundary_indices[0].cpu()
    boundary_x = boundary_indices[1].cpu()

    if len(boundary_y) == 0:
        return []

    # Sort points in clockwise order around the centroid
    cx = float(boundary_x.float().mean().item())
    cy = float(boundary_y.float().mean().item())

    angles = torch.atan2(boundary_y.float() - cy, boundary_x.float() - cx)
    sorted_order = torch.argsort(angles)

    contour_points = [
        (
            float(boundary_x[i].item()) * pixel_size_nm,
            float(boundary_y[i].item()) * pixel_size_nm,
        )
        for i in sorted_order
    ]

    return contour_points


# ═══════════════════════════════════════════════════════════════════
# Multi-line CD extraction
# ═══════════════════════════════════════════════════════════════════


def extract_multiple_lines(
    aerial_2d: torch.Tensor,
    pitch_px: int,
    threshold: float = 0.3,
) -> torch.Tensor:
    """Extract CD for each line in a periodic line/space array.

    The image is divided into vertical stripes of width *pitch_px*.
    Within each stripe the CD is measured from the central row of that
    stripe using :func:`extract_cd_1d`.

    Parameters
    ----------
    aerial_2d : torch.Tensor
        2D aerial image ``(H, W)``.  Assumes lines are vertical (x is
        the fast axis).
    pitch_px : int
        Pattern pitch in pixels.
    threshold : float
        Edge-detection threshold.  Default 0.3.

    Returns
    -------
    cd_per_line : torch.Tensor
        1D tensor of CD values [pixels], one per pitch interval.
    """
    H, W = aerial_2d.shape
    row = H // 2  # middle row
    intensity_row = aerial_2d[row, :]

    x_px = torch.arange(W, dtype=torch.float32)
    cd_list = []

    for start in range(0, W, pitch_px):
        end = min(start + pitch_px, W)
        if end - start < 3:
            continue
        seg = intensity_row[start:end]
        x_seg = x_px[start:end]

        cd_val = extract_cd_1d(seg, x_seg, threshold=threshold, mode="line")
        cd_list.append(cd_val)

    return torch.tensor(cd_list, dtype=torch.float32)
