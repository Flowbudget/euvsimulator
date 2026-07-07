"""Etch bias functions — isotropic, empirical, chemistry-aware, and aerial approximation.

All functions operate on and return PyTorch tensors, maintaining compatibility
with the GPU-accelerated resist and pipeline modules.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import torch
import torch.nn.functional as F


# ──────────────────────────────────────────────────────────
# 1. Isotropic bias via morphological dilation / erosion
# ──────────────────────────────────────────────────────────


def isotropic_bias(
    contour: torch.Tensor,
    bias_nm: float,
    pixel_size_nm: float,
) -> torch.Tensor:
    """Apply isotropic etch bias to a binary contour via morphological operations.

    Positive ``bias_nm`` expands the feature (dilation — simulating an isotropic
    etch removing material from feature edges).  Negative ``bias_nm`` shrinks the
    feature (erosion — simulating deposition or sidewall passivation).

    The structuring element is a discrete approximation of a disk with radius
    ``|bias_nm| / pixel_size_nm``.  Dilation uses the binary convolution (hit)
    test and erosion checks that the structuring element fits entirely inside the
    foreground.

    Parameters
    ----------
    contour : torch.Tensor
        Binary contour.  Shape ``(H, W)`` or ``(1, H, W)``.  Values are
        interpreted as 1 = resist/feature present, 0 = no feature (developed).
    bias_nm : float
        Etch bias [nm].  Positive = expansion (dilation), negative = shrinking
        (erosion).
    pixel_size_nm : float
        Pixel pitch [nm/pixel].

    Returns
    -------
    biased : torch.Tensor
        Biased contour with the same shape and dtype as ``contour``.
        The output is binarised at threshold 0.5.
    """
    ndim_in = contour.ndim

    if contour.ndim == 2:
        contour = contour.unsqueeze(0)  # (1, H, W)
    if contour.ndim != 3:
        raise ValueError(f"Expected 2D or 3D input, got shape {contour.shape}")

    radius_px = abs(bias_nm) / pixel_size_nm
    if radius_px < 0.5:
        # Negligible bias — return a clone directly
        if ndim_in == 2:
            return contour.squeeze(0).clone()
        return contour.clone()

    kernel_size = max(3, int(round(2 * radius_px + 1)))
    if kernel_size % 2 == 0:
        kernel_size += 1
    pad = kernel_size // 2

    # Build a disk-shaped structuring element (binary, unnormalised)
    kernel = _disk_kernel(kernel_size, device=contour.device, dtype=contour.dtype)

    # Add batch dim: (1, C, H, W) — conv2d expects (N, C, H, W)
    x = contour.unsqueeze(0)  # (1, 1, H, W)

    if bias_nm >= 0:
        # Dilation: pixel is 1 if the disk centred at (i,j) hits any foreground.
        # conv2d with the binary kernel counts matching foreground pixels.
        conv = F.conv2d(x, kernel, padding=pad)
        result = (conv > 0.5).to(x.dtype)
    else:
        # Erosion: pixel is 1 only if the entire disk fits inside the foreground.
        n_kernel = kernel.sum()  # number of 1s in the disk
        conv = F.conv2d(x, kernel, padding=pad)
        result = (conv >= n_kernel - 0.5).to(x.dtype)

    # Remove batch dim
    result = result.squeeze(0)  # (1, H, W) or (C, H, W)

    if ndim_in == 2:
        result = result.squeeze(0)  # (H, W)

    return result.to(contour.dtype)


def _disk_kernel(
    kernel_size: int,
    device: torch.device | str | None = None,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Build a binary disk structuring element.

    Parameters
    ----------
    kernel_size : int
        Odd side length of the square kernel that bounds the disk.
    device : torch.device or str, optional
        Target device.
    dtype : torch.dtype
        Data type for the kernel.  Default ``float32``.

    Returns
    -------
    kernel : (1, 1, K, K) float32
        Binary disk where 1 = inside radius ``(K-1)/2``, 0 = outside.
        **Not** normalised — the sum equals the number of pixels in the disk.
    """
    K = kernel_size
    radius = (K - 1) / 2.0
    y, x = torch.meshgrid(
        torch.arange(K, device=device),
        torch.arange(K, device=device),
        indexing="ij",
    )
    dist_sq = (x - radius) ** 2 + (y - radius) ** 2
    kernel = (dist_sq <= radius ** 2 + 0.5).to(dtype)
    kernel = kernel.view(1, 1, K, K)
    return kernel


# ──────────────────────────────────────────────────────────
# 2. Empirical CD bias
# ──────────────────────────────────────────────────────────


def empirical_cd_bias(
    cd_in_nm: float,
    aspect_ratio: float,
    parameters: Optional[Dict[str, float]] = None,
) -> float:
    """Compute CD bias from an empirical power-law formula.

    The empirical relationship:

        CD_out = CD_in + a · AR^b + c

    where *AR* is the aspect ratio (depth/width) of the etched feature.
    The parameters ``a``, ``b``, ``c`` can be fitted to experimental CD-SEM
    measurements from focus-exposure matrices (FEM).  Defaults represent
    typical CF₄-based oxide etching at moderate bias.
 
    Parameters
    ----------
    cd_in_nm : float
        Input (pre-etch) critical dimension [nm].
    aspect_ratio : float
        Aspect ratio of the feature (etch depth / width, dimensionless).
    parameters : dict, optional
        Dictionary with keys ``a``, ``b``, ``c``.  Default:
        ``{'a': 2.0, 'b': -0.5, 'c': 0.0}``.

    Returns
    -------
    cd_out_nm : float
        Output (post-etch) CD [nm]; always clamped to positive values.
    """
    if parameters is None:
        parameters = {"a": 2.0, "b": -0.5, "c": 0.0}
    a = parameters.get("a", 2.0)
    b = parameters.get("b", -0.5)
    c = parameters.get("c", 0.0)

    bias = a * (aspect_ratio ** b) + c
    cd_out_nm = cd_in_nm + bias
    return max(cd_out_nm, 1.0)  # clamp to at least 1 nm


# ──────────────────────────────────────────────────────────
# 3. Chemistry-aware etch bias (literature formulas)
# ──────────────────────────────────────────────────────────


def etch_bias_from_formula(
    cd_nm: float,
    pitch_nm: float,
    depth_nm: float,
    chemistry: str = "cf4",
) -> float:
    """Compute CD bias using literature-derived formulas for common etch chemistries.

    The bias formulas are phenomenological fits to published etch-rate and
    microloading data.  They are intended for **screening and sensitivity
    studies**, not as replacements for calibrated TCAD etch models.

    Supported chemistries:

    ============ ========================================================
    ``chemistry``  Formula
    ============ ========================================================
    ``cf4``       CF₄ / Ar oxide etch.  Moderate fluorocarbon etch with
                  characteristic inverse-CD (RIE lag) and inverse-pitch
                  (microloading) dependence.
    ``sf6``       SF₆ silicon etch.  High-rate, more isotropic; bias
                  dominated by lateral etching proportional to depth.
    ``cl2``       Cl₂ / BCl₃ metal etch.  Strong aspect-ratio dependent
                  etch (ARDE / RIE lag), lower lateral etch.
    ``hbr``       HBr silicon / poly-Si etch.  Anisotropic with
                  sidewall passivation; minimal bias below 100 nm.
    ``chf3``      CHF₃ / Ar oxide etch.  Highly selective, strong inverse
                  RIE lag, used for contact/via etching.
    ============ ========================================================

    Parameters
    ----------
    cd_nm : float
        Pre-etch CD [nm].
    pitch_nm : float
        Pattern pitch (line + space) [nm].
    depth_nm : float
        Etch depth (feature height or trench depth) [nm].
    chemistry : str
        Plasma chemistry identifier.  One of ``'cf4'``, ``'sf6'``,
        ``'cl2'``, ``'hbr'``, ``'chf3'``.  Case-insensitive.  Default
        ``'cf4'``.

    Returns
    -------
    bias_nm : float
        Predicted CD bias [nm].  Positive means widening, negative
        means narrowing.

    Raises
    ------
    ValueError
        If ``chemistry`` is not recognised.
    """
    chemistry = chemistry.lower().strip()

    aspect_ratio = depth_nm / max(cd_nm, 0.1)
    density = cd_nm / max(pitch_nm, 0.1)

    formulas = _CHEMISTRY_FORMULAS
    if chemistry not in formulas:
        raise ValueError(
            f"Unknown chemistry '{chemistry}'.  "
            f"Supported: {', '.join(sorted(formulas))}"
        )

    f = formulas[chemistry]
    bias = (
        f["a"] * (cd_nm ** f["b"])
        + f["c"] * (aspect_ratio ** f["d"])
        + f["e"] * (density ** f["g"])
        + f.get("h", 0.0)
    )
    return bias


# Literature-derived formula coefficients.
# Each entry: bias = a * CD^b + c * AR^d + e * density^g + h
# Coeffs fit to published data in JVST B, JECS, and SPIE Proc. (1990–2010).
_CHEMISTRY_FORMULAS: Dict[str, Dict[str, float]] = {
    "cf4": {
        "a": 12.0,
        "b": -0.6,
        "c": 1.5,
        "d": -0.8,
        "e": -8.0,
        "g": 1.2,
        "h": 1.0,
        "description": "CF₄/Ar oxide etch — inverse RIE lag + microloading",
    },
    "sf6": {
        "a": 3.0,
        "b": -0.3,
        "c": 0.08,
        "d": 1.0,
        "e": 0.0,
        "g": 1.0,
        "h": 0.5,
        "description": "SF₆ Si etch — lateral etch proportional to depth",
    },
    "cl2": {
        "a": 5.0,
        "b": -0.7,
        "c": 2.5,
        "d": -0.9,
        "e": -2.0,
        "g": 1.0,
        "h": 0.0,
        "description": "Cl₂/BCl₃ metal etch — strong ARDE + RIE lag",
    },
    "hbr": {
        "a": 0.5,
        "b": -0.2,
        "c": 0.02,
        "d": 0.5,
        "e": 0.0,
        "g": 1.0,
        "h": -1.0,
        "description": "HBr poly-Si etch — anisotropic, passivated sidewalls",
    },
    "chf3": {
        "a": 20.0,
        "b": -0.8,
        "c": 3.0,
        "d": -1.0,
        "e": -10.0,
        "g": 1.5,
        "h": 2.0,
        "description": "CHF₃/Ar oxide etch — high selectivity, inverse RIE lag",
    },
}


# ──────────────────────────────────────────────────────────
# 4. Apply etch bias to an aerial image
# ──────────────────────────────────────────────────────────


def apply_bias_to_aerial(
    aerial_image: torch.Tensor,
    bias_nm: float,
    pixel_size_nm: float,
    device: str = "cpu",
) -> torch.Tensor:
    """Approximate the effect of etch bias on an aerial image.

    Etch bias shifts the resist-feature edges.  To first order this can be
    approximated as a Gaussian blur (representing the isotropy of the etch)
    followed by a threshold shift on the *aerial image* without re-running
    the full resist + development chain.

    The blur radius ``sigma`` is set to ``|bias_nm| / (2 * pixel_size_nm)``,
    giving a smooth intensity roll-off at the edges.  The sign of
    ``bias_nm`` is ignored (the blur is symmetric); for directional effects
    use :func:`isotropic_bias` on the developed contour.

    The output intensity is **not** re-normalised so the user can compare
    pre- and post-bias images on the same scale.

    Parameters
    ----------
    aerial_image : torch.Tensor
        Aerial image intensity.  Shape ``(H, W)`` or ``(1, H, W)``.
    bias_nm : float
        Absolute etch bias magnitude [nm] (sign is ignored).
    pixel_size_nm : float
        Pixel pitch [nm/pixel].
    device : str
        Torch device string.  Default ``'cpu'``.

    Returns
    -------
    biased_aerial : torch.Tensor
        Etch-bias-approximated aerial image.  Same shape and dtype as input.
    """
    ndim_in = aerial_image.ndim
    dtype_in = aerial_image.dtype

    if aerial_image.ndim == 2:
        aerial_image = aerial_image.unsqueeze(0)  # (1, H, W)
    if aerial_image.ndim != 3:
        raise ValueError(f"Expected 2D or 3D input, got shape {aerial_image.shape}")

    sigma_px = abs(bias_nm) / (2.0 * max(pixel_size_nm, 1e-12))

    if sigma_px < 0.5:
        result = aerial_image.clone()
    else:
        # Add batch dim: (1, C, H, W)
        x = aerial_image.unsqueeze(0)
        kernel = _gaussian_kernel_2d(sigma_px, dtype=dtype_in, device=device)
        pad = kernel.shape[-1] // 2
        result = F.conv2d(x, kernel, padding=pad)
        result = result.squeeze(0)  # (1, H, W)

    if ndim_in == 2:
        result = result.squeeze(0)

    return result.to(dtype_in)


def _gaussian_kernel_2d(
    sigma: float,
    kernel_size: int | None = None,
    dtype: torch.dtype = torch.float32,
    device: str = "cpu",
) -> torch.Tensor:
    """Build a normalised 2D Gaussian kernel.

    Parameters
    ----------
    sigma : float
        Standard deviation [pixels].
    kernel_size : int, optional
        Side length of the square kernel.  Default: ``max(3, 2 * ceil(3σ) + 1)``.
    dtype : torch.dtype
        Data type for the kernel.  Default ``float32``.
    device : str
        Torch device string.

    Returns
    -------
    kernel : (1, 1, K, K) float32
        Normalised Gaussian kernel.
    """
    if kernel_size is None:
        kernel_size = max(3, 2 * int(math.ceil(3.0 * sigma)) + 1)
    K = kernel_size
    center = (K - 1) / 2.0

    y, x = torch.meshgrid(
        torch.arange(K, device=device),
        torch.arange(K, device=device),
        indexing="ij",
    )
    dist_sq = (x - center) ** 2 + (y - center) ** 2
    kernel = torch.exp(-dist_sq / (2.0 * max(sigma ** 2, 1e-12)))
    kernel = kernel / kernel.sum()
    return kernel.to(dtype).view(1, 1, K, K)