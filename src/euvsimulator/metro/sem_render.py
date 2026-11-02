"""SEM-image rendering from binary contours for visual verification.

Functions
---------
render_sem
    Rasterise a contour into a simulated SEM image.
add_shot_noise
    Apply Poisson (shot) noise to an SEM image.
add_edge_roughness
    Perturb a contour with LER/LWR.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import torch

# ═══════════════════════════════════════════════════════════════════
# SEM rendering
# ═══════════════════════════════════════════════════════════════════


def render_sem(
    contour: List[Tuple[float, float]],
    pixel_size_nm: float,
    image_size_nm: Tuple[float, float] = (1000.0, 1000.0),
    blur_sigma_nm: float = 3.0,
    noise_sigma: float = 0.05,
    device: str = "cpu",
) -> torch.Tensor:
    """Render a simulated SEM image from a contour list.

    The contour is rasterised onto a pixel grid by filling the polygon
    and applying a Gaussian blur (beam-spot convolution) plus additive
    Gaussian noise.

    Parameters
    ----------
    contour : list of (float, float)
        List of (x, y) points defining the feature contour [nm].
    pixel_size_nm : float
        Output pixel size [nm/pixel].
    image_size_nm : tuple of float
        Physical size of the output image (width, height) in nm.
        Default ``(1000, 1000)``.
    blur_sigma_nm : float
        Gaussian blur sigma in nm (beam-spot size).  Default 3.0.
    noise_sigma : float
        Standard deviation of additive Gaussian noise (fraction of max
        intensity).  Default 0.05.
    device : str
        Torch device.  Default ``'cpu'``.

    Returns
    -------
    sem_image : torch.Tensor
        2D float tensor ``(H, W)`` with values in ``[0, 1]``.
    """
    W_nm, H_nm = image_size_nm
    W_px = int(round(W_nm / pixel_size_nm))
    H_px = int(round(H_nm / pixel_size_nm))

    if len(contour) < 3:
        # Too few points for a polygon — return blank
        return torch.zeros((H_px, W_px), device=device)

    # Create base image
    image = torch.zeros((H_px, W_px), dtype=torch.float32, device=device)

    # Rasterise the polygon — point-in-polygon test for each pixel.
    # We use a winding-number / ray-casting approach (pure PyTorch).
    contour_t = torch.tensor(contour, dtype=torch.float32, device=device)
    # Convert contour coordinates to pixel indices
    contour_px = contour_t / pixel_size_nm

    # Build pixel grid
    y_grid, x_grid = torch.meshgrid(
        torch.arange(H_px, device=device, dtype=torch.float32),
        torch.arange(W_px, device=device, dtype=torch.float32),
        indexing="ij",
    )

    # Point-in-polygon via ray casting (horizontal ray to the right)
    n_pts = len(contour_px)
    inside = torch.zeros_like(x_grid, dtype=torch.bool)

    for i in range(n_pts):
        x1, y1 = contour_px[i]
        x2, y2 = contour_px[(i + 1) % n_pts]

        # Only consider edges that straddle the y-range
        y_min, y_max = min(y1, y2), max(y1, y2)

        # Mask: pixel y is between y1 and y2
        mask_y = (y_grid >= y_min) & (y_grid < y_max)

        if not mask_y.any():
            continue

        # Compute x-intersection of the horizontal ray at y with this edge
        if abs(y2 - y1) < 1e-12:
            continue  # horizontal edge — skip

        x_int = x1 + (y_grid - y1) * (x2 - x1) / (y2 - y1)

        # Ray hits: x_int > pixel_x (ray to the right)
        hit = (x_int > x_grid) & mask_y
        inside = inside ^ hit  # XOR (toggle on each crossing)

    image[inside] = 1.0

    # Gaussian blur (beam-spot convolution) — apply via separable
    # convolution with a truncated Gaussian kernel
    if blur_sigma_nm > 0:
        sigma_px = blur_sigma_nm / pixel_size_nm
        radius = int(max(1, round(4.0 * sigma_px)))
        kernel_size = 2 * radius + 1

        kernel_1d = torch.exp(
            -(torch.arange(-radius, radius + 1, device=device, dtype=torch.float32) ** 2)
            / (2.0 * sigma_px**2)
        )
        kernel_1d = kernel_1d / kernel_1d.sum()

        # Separable convolution
        image = _convolve_2d_separable(image, kernel_1d)

    # Additive Gaussian noise
    if noise_sigma > 0:
        noise = torch.randn_like(image) * noise_sigma
        image = image + noise

    # Clamp to [0, 1]
    image = torch.clamp(image, 0.0, 1.0)

    return image


def _convolve_2d_separable(
    image: torch.Tensor,
    kernel_1d: torch.Tensor,
) -> torch.Tensor:
    """2D separable convolution using unfold (padding='same')."""
    k = len(kernel_1d)
    pad = k // 2

    # Add batch and channel dims for conv2d
    img = image.unsqueeze(0).unsqueeze(0)  # (1, 1, H, W)

    # Convolve along columns (W dim)
    img = torch.nn.functional.pad(img, (pad, pad, 0, 0), mode="reflect")
    img = torch.nn.functional.conv2d(
        img,
        kernel_1d.view(1, 1, 1, -1),
        padding=0,
    )

    # Convolve along rows (H dim)
    img = torch.nn.functional.pad(img, (0, 0, pad, pad), mode="reflect")
    img = torch.nn.functional.conv2d(
        img,
        kernel_1d.view(1, 1, -1, 1),
        padding=0,
    )

    return img.squeeze()  # back to (H, W)


# ═══════════════════════════════════════════════════════════════════
# Shot noise (Poisson)
# ═══════════════════════════════════════════════════════════════════


def add_shot_noise(
    image: torch.Tensor,
    dose_factor: float = 1.0,
) -> torch.Tensor:
    """Apply Poisson (shot) noise to an SEM image.

    Shot noise scales with the square root of the signal intensity.
    The noise-added image is::

        I_noisy = Poisson(I · K) / K

    where *K* is a scaling factor proportional to *dose_factor*.

    Parameters
    ----------
    image : torch.Tensor
        Input image with values in ``[0, 1]``.
    dose_factor : float
        Electron-dose scaling factor.  Higher values = lower relative
        noise.  Default 1.0.

    Returns
    -------
    noisy : torch.Tensor
        Noisy image with same shape, clamped to ``[0, 1]``.
    """
    # A higher dose_factor means more electrons → less relative noise.
    # Scale so that at dose_factor=1, the max photon count is ~100.
    scale = 100.0 * max(dose_factor, 0.01)
    scaled = image * scale
    noisy = torch.poisson(scaled)
    noisy = noisy / scale
    return torch.clamp(noisy, 0.0, 1.0)


# ═══════════════════════════════════════════════════════════════════
# Edge roughness
# ═══════════════════════════════════════════════════════════════════


def add_edge_roughness(
    contour: List[Tuple[float, float]],
    ler_nm: float = 2.0,
    lwr_nm: float = 2.0,
    rng_seed: Optional[int] = None,
) -> List[Tuple[float, float]]:
    """Perturb a contour with Line-Edge Roughness (LER) and
    Line-Width Roughness (LWR).

    Points at the same position along the long axis of the feature
    (principal axis of the contour points) share two independent
    Gaussian draws a and b, which pairs opposite edges of a line.  The
    width term 0.5 * lwr_nm * b acts along the local normal (both edges
    move outward, or both inward); the placement term
    sqrt(ler_nm^2 - lwr_nm^2 / 4) * a acts perpendicular to the long
    axis (both edges shift the same way).  For a straight line each edge
    then has standard deviation ler_nm and the width has standard
    deviation lwr_nm; independent edges correspond to
    lwr_nm = sqrt(2) * ler_nm.  The noise is white along the axis (one
    draw per median point spacing).  Earlier versions added independent
    noise N(0, ler_nm^2) + 0.5 * N(0, lwr_nm^2) per point, so the edge
    standard deviation was sqrt(ler_nm^2 + lwr_nm^2 / 4) and the width
    standard deviation was not lwr_nm.

    Parameters
    ----------
    contour : list of (float, float)
        Original contour points [nm].
    ler_nm : float
        Standard deviation (1 sigma) of each edge position [nm].
        Default 2.0.
    lwr_nm : float
        Standard deviation (1 sigma) of the local line width [nm],
        0 <= lwr_nm <= 2 * ler_nm.  Default 2.0.
    rng_seed : int, optional
        Seed for a local random generator; the global torch RNG is not
        touched.  None draws from the global torch RNG.

    Returns
    -------
    roughened_contour : list of (float, float)
        Perturbed contour coordinates [nm].

    Raises
    ------
    ValueError
        If ler_nm or lwr_nm is negative, or lwr_nm > 2 * ler_nm.
    """
    if ler_nm < 0 or lwr_nm < 0:
        raise ValueError(f"ler_nm and lwr_nm must be >= 0, got {ler_nm} and {lwr_nm}")
    if lwr_nm > 2.0 * ler_nm:
        raise ValueError(
            f"lwr_nm ({lwr_nm}) cannot exceed 2 * ler_nm ({2.0 * ler_nm}): the width "
            "is the difference of two edges with standard deviation ler_nm each"
        )
    if len(contour) < 3:
        return contour

    pts = torch.tensor(contour, dtype=torch.float32)
    n = len(pts)

    # Local generator, so that a seed does not reset the caller's global RNG.
    gen: Optional[torch.Generator] = None
    if rng_seed is not None:
        gen = torch.Generator().manual_seed(rng_seed)

    # Compute local normals via finite differences
    # tangent = (x_{i+1} - x_{i-1}, y_{i+1} - y_{i-1})
    t_x = torch.roll(pts[:, 0], shifts=-1) - torch.roll(pts[:, 0], shifts=1)
    t_y = torch.roll(pts[:, 1], shifts=-1) - torch.roll(pts[:, 1], shifts=1)

    # Normalise
    norm_t = torch.sqrt(t_x**2 + t_y**2).clamp(min=1e-12)
    # Normal = (-t_y / |t|, t_x / |t|)   (rotate tangent 90° CCW)
    n_x = -t_y / norm_t
    n_y = t_x / norm_t

    # This normal points inward everywhere (counter-clockwise contour) or
    # outward everywhere (clockwise); either way both edges of a line get
    # the same sign, which is all the width term needs.

    # Long axis = principal axis of the points; s = position along it.
    centred = pts - pts.mean(dim=0)
    _, evecs = torch.linalg.eigh(centred.T @ centred)
    axis = evecs[:, -1]
    perp_x = -axis[1]
    perp_y = axis[0]
    s = centred @ axis

    # One bin per median point spacing; opposite edges share a bin.
    seg = torch.linalg.vector_norm(torch.roll(pts, shifts=-1, dims=0) - pts, dim=1)
    seg = seg[seg > 0]
    if seg.numel() == 0:
        return contour
    h = float(seg.median())
    _, bins = torch.unique(torch.round((s - s.min()) / h), return_inverse=True)
    n_bins = int(bins.max()) + 1

    a = torch.randn(n_bins, generator=gen)  # placement, same shift on both edges
    b = torch.randn(n_bins, generator=gen)  # width, both edges outward or inward
    sigma_place = math.sqrt(max(ler_nm * ler_nm - 0.25 * lwr_nm * lwr_nm, 0.0))
    d_width = 0.5 * lwr_nm * b[bins]
    d_place = sigma_place * a[bins]

    new_pts = pts.clone()
    new_pts[:, 0] = pts[:, 0] + d_width * n_x + d_place * perp_x
    new_pts[:, 1] = pts[:, 1] + d_width * n_y + d_place * perp_y

    return [(float(new_pts[i, 0]), float(new_pts[i, 1])) for i in range(n)]
