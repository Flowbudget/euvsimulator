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

    LER perturbs each point of the contour along the local normal
    direction.  LWR adds an additional in-plane perturbation, either
    expanding or contracting the feature width.

    Parameters
    ----------
    contour : list of (float, float)
        Original contour points [nm].
    ler_nm : float
        Standard deviation of LER (nm).  Default 2.0.
    lwr_nm : float
        Standard deviation of LWR (nm).  Default 2.0.
    rng_seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    roughened_contour : list of (float, float)
        Perturbed contour coordinates [nm].
    """
    if len(contour) < 3:
        return contour

    pts = torch.tensor(contour, dtype=torch.float32)
    n = len(pts)

    if rng_seed is not None:
        torch.manual_seed(rng_seed)

    # Compute local normals via finite differences
    # tangent = (x_{i+1} - x_{i-1}, y_{i+1} - y_{i-1})
    t_x = torch.roll(pts[:, 0], shifts=-1) - torch.roll(pts[:, 0], shifts=1)
    t_y = torch.roll(pts[:, 1], shifts=-1) - torch.roll(pts[:, 1], shifts=1)

    # Normalise
    norm_t = torch.sqrt(t_x**2 + t_y**2).clamp(min=1e-12)
    # Normal = (-t_y / |t|, t_x / |t|)   (rotate tangent 90° CCW)
    n_x = -t_y / norm_t
    n_y = t_x / norm_t

    # LER: outward/inward displacement along normal
    ler = torch.randn(n) * ler_nm

    # LWR: additional displacement in the normal direction that is
    # correlated with the opposite edge → effectively scales width.
    # We add a spatially correlated extra displacement.
    lwr = torch.randn(n) * lwr_nm

    # Total displacement
    displacement = ler + 0.5 * lwr  # LWR splits across both edges

    new_pts = pts.clone()
    new_pts[:, 0] = pts[:, 0] + displacement * n_x
    new_pts[:, 1] = pts[:, 1] + displacement * n_y

    return [(float(new_pts[i, 0]), float(new_pts[i, 1])) for i in range(n)]
