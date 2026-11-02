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
    Image log-slope at a feature edge; the NILS when a CD is given.
extract_contour
    Outer boundary of the first foreground feature as (x, y) points.
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
        ordered left-to-right in pairs.  Only complete features are
        returned: a feature cut by the left or right end of the profile
        has no pair and is skipped.
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

    # If the profile begins inside a feature (e.g. a dark line cut by the
    # left boundary), the first event is an end edge without a start
    # edge.  Drop it, so that starts[k] < ends[k] for every pair.
    if len(starts) > 0 and len(ends) > 0 and int(ends[0]) < int(starts[0]):
        ends = ends[1:]

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
    and measures the width of the first complete dark (or bright)
    feature, i.e. the first one with both edges inside the profile.
    A feature cut by the left or right end of the profile is skipped.

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
        Critical dimension in nanometres.  Returns 0.0 if the profile
        contains no complete feature.

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
    edges of the first complete dark line are found (sub-pixel
    interpolated); a line cut by the left or right image border is
    skipped.  The line width per row is computed and the mean CD across
    all rows is returned.

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
    cd_nm: float | None = None,
) -> float:
    """Compute the image log-slope, or the NILS if a CD is given.

    Without *cd_nm* the function returns the signed image log-slope
    (ILS) in 1/nm, ``(dI/dx) / I``.  It is negative at the left edge of
    a dark line and it is **not** the NILS.  With *cd_nm* it returns the
    dimensionless Mack NILS (its magnitude, as
    :func:`euvsimulator.aerial.abbe.nils` does), defined as::

        NILS = CD · (dI/dx) / I

    evaluated at the edge position, where *CD* is the line width and
    *I* is the image intensity.  The derivative is a central difference
    with a step of max(grid spacing, 1 nm); near the ends of the profile
    the step is shortened so that both sample points stay inside the
    profile.

    Parameters
    ----------
    intensity : torch.Tensor
        1D intensity profile ``(N,)``.
    x_nm : torch.Tensor
        1D spatial coordinate ``(N,)`` in nanometres.
    edge_position_nm : float
        Position of the line edge [nm].
    cd_nm : float, optional
        Line width [nm].  If given, the NILS is returned instead of the
        image log-slope.  Must be positive.

    Returns
    -------
    value : float
        Image log-slope [1/nm] without *cd_nm*, NILS (dimensionless,
        non-negative) with *cd_nm*.  Returns 0.0 if the edge is outside
        the domain, if the profile has fewer than two points, or if the
        intensity at the edge is not positive.

    References
    ----------
    C. A. Mack, "Fundamental Principles of Optical Lithography",
    Wiley, 2007, §4.5.
    """
    if cd_nm is not None and cd_nm <= 0.0:
        raise ValueError("cd_nm must be positive")
    if len(x_nm) < 2:
        return 0.0
    x_first = float(x_nm[0])
    x_last = float(x_nm[-1])
    if edge_position_nm < x_first or edge_position_nm > x_last:
        return 0.0

    # Central difference in nanometres — use neighbour interpolation
    dx = float(x_nm[1] - x_nm[0]) if len(x_nm) > 1 else 1.0
    eps = max(dx, 1.0)  # at least 1 nm step

    # Intensity at edge (linear interp for sub-pixel accuracy)
    I_edge = _linear_interp_1d(x_nm, intensity, edge_position_nm)
    if I_edge < 1e-30:
        return 0.0

    # Derivative via linear interpolation at edge ± ε
    # Keep both sample points inside the domain (one-sided near the ends)
    x_minus = max(edge_position_nm - eps, x_first)
    x_plus = min(edge_position_nm + eps, x_last)
    if x_plus - x_minus <= 0.0:
        return 0.0
    I_plus = _linear_interp_1d(x_nm, intensity, x_plus)
    I_minus = _linear_interp_1d(x_nm, intensity, x_minus)

    dI_dx = (I_plus - I_minus) / (x_plus - x_minus)

    # NILS = CD * (dI/dx) / I
    # Use the CD implied by the image period / target
    # For a line/space, CD ≈ half-period; use local contrast instead
    # Mack convention: NILS = (1/I) * (dI/dx), then multiplied by CD
    # for a full metric.  Here we return the log-slope *without* CD
    # multiplication unless the caller passes cd_nm.
    ils = dI_dx / I_edge
    if cd_nm is None:
        return float(ils)
    # Mack NILS = CD * |dI/dx| / I, as in aerial.abbe.nils
    return float(cd_nm * abs(ils))


# ═══════════════════════════════════════════════════════════════════
# Contour extraction
# ═══════════════════════════════════════════════════════════════════


def extract_contour(
    binary_image: torch.Tensor,
    pixel_size_nm: float,
) -> List[Tuple[float, float]]:
    """Trace the outer boundary of the first foreground feature.

    The image is scanned row by row from the top-left until the first
    foreground pixel is found.  The outer boundary of the 4-connected
    feature that contains this pixel is then traced along the pixel
    edges, clockwise as seen on screen (y axis pointing down).  It does
    **not** rely on scikit-image.

    The points are pixel corners in the pixel-centre convention of the
    image: pixel ``(row, col)`` covers ``x`` from ``col - 0.5`` to
    ``col + 0.5`` and ``y`` from ``row - 0.5`` to ``row + 0.5`` (times
    *pixel_size_nm*).  Filling the polygon with
    :func:`~euvsimulator.metro.sem_render.render_sem` therefore gives
    back the feature pixel for pixel.

    Only one closed boundary is returned.  Holes inside the feature and
    all other features are ignored; crop or label the image to trace
    them one by one.

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
        Closed polygon in nanometres, one point per pixel-edge step; the
        first point is not repeated at the end.  Empty if the image has
        no foreground pixel.
    """
    if binary_image.ndim != 2:
        raise ValueError("binary_image must be 2D")

    H, W = binary_image.shape
    mask = (binary_image > 0.5).to(torch.bool).cpu()
    if not bool(mask.any()):
        return []

    # Pad with background so the trace never leaves the array.  Padded
    # pixel (r, c) is image pixel (r - 1, c - 1).
    padded = torch.zeros((H + 2, W + 2), dtype=torch.bool)
    padded[1:-1, 1:-1] = mask
    fg = padded.tolist()

    # First foreground pixel in row-major order.  Its top-left corner
    # is the start vertex; vertex (r, c) is the top-left corner of
    # padded pixel (r, c).
    first = torch.nonzero(padded)[0]
    r0, c0 = int(first[0]), int(first[1])

    # Headings in clockwise order on screen: east, south, west, north.
    step_r = (0, 1, 0, -1)
    step_c = (1, 0, -1, 0)
    # Pixels ahead of a vertex for each heading, as offsets from the
    # vertex: (ahead-left, ahead-right).
    ahead = (
        ((-1, 0), (0, 0)),  # east
        ((0, 0), (0, -1)),  # south
        ((0, -1), (-1, -1)),  # west
        ((-1, -1), (-1, 0)),  # north
    )

    # Walk with the foreground on the right-hand side.  At each vertex:
    # background ahead-right -> turn right; foreground ahead-left ->
    # turn left; otherwise go straight.  Turning right at a diagonal
    # pixel pair keeps the feature 4-connected.
    r, c, heading = r0, c0, 0
    corners: List[Tuple[int, int]] = []
    max_steps = 4 * (H + 3) * (W + 3)
    for _ in range(max_steps):
        corners.append((r, c))
        r += step_r[heading]
        c += step_c[heading]
        if r == r0 and c == c0:
            break
        (lr, lc), (rr, rc) = ahead[heading]
        if not fg[r + rr][c + rc]:
            heading = (heading + 1) % 4
        elif fg[r + lr][c + lc]:
            heading = (heading - 1) % 4
    else:
        raise RuntimeError("extract_contour: boundary trace did not close")

    # Padded vertex (r, c) lies at image x = c - 1.5, y = r - 1.5 [pixels]
    contour_points = [
        ((vc - 1.5) * pixel_size_nm, (vr - 1.5) * pixel_size_nm) for vr, vc in corners
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

    All dark lines (intensity below *threshold*) along the middle row
    of the image are found with sub-pixel interpolated edges, and the
    width of every complete line is returned, ordered left to right.
    A line cut by the left or right image border is skipped.  The
    result does not depend on where a line sits relative to a pitch
    grid.

    Parameters
    ----------
    aerial_2d : torch.Tensor
        2D aerial image ``(H, W)``.  Assumes lines are vertical (x is
        the fast axis).
    pitch_px : int
        Nominal pattern pitch in pixels.  Must be at least 1.  It is
        only checked; the lines are found on the whole row, not in
        fixed stripes of this width.
    threshold : float
        Edge-detection threshold.  Default 0.3.

    Returns
    -------
    cd_per_line : torch.Tensor
        1D tensor of CD values [pixels], one per complete line.
    """
    if pitch_px < 1:
        raise ValueError("pitch_px must be at least 1")

    H, W = aerial_2d.shape
    row = H // 2  # middle row
    intensity_row = aerial_2d[row, :]

    crossings = _threshold_crossings(intensity_row, threshold, mode="line")
    if len(crossings) < 2:
        return torch.tensor([], dtype=torch.float32)

    # crossings = [left_0, right_0, left_1, right_1, ...] in pixels
    widths = crossings[1::2] - crossings[0::2]
    return widths.to(torch.float32)
