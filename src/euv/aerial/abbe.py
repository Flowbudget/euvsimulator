"""Abbe's method for partially coherent aerial image formation.

Abbe summation computes the aerial image as a weighted sum of
coherent images from each illumination source point.  This is the
physically honest approach for EUV with mask-3D corrections, where
the thin-mask (Hopkins) approximation breaks down.

For each source point *s* with intensity *I_s* and direction
*(α_s, β_s)*, the coherent image is::

    J_s(x, y) = | ℱ⁻¹[ P(fx, fy) · O(fx − α_s, fy − β_s) ] |²

where *P* is the pupil function and *O* is the mask diffraction
spectrum.  The total aerial image is::

    J(x, y) = Σ_s I_s · J_s(x, y)   /   Σ_s I_s

"""

from __future__ import annotations

import torch


def abbe_image(
    mask_fft: torch.Tensor,
    source: torch.Tensor,
    fx: torch.Tensor,
    fy: torch.Tensor,
    pupil: torch.Tensor,
    na: float = 0.33,
) -> torch.Tensor:
    """Compute the aerial image via Abbe summation over source points.

    Parameters
    ----------
    mask_fft : (G, G) complex128
        2D FFT of the mask transmission (centred, zero-frequency
        at G//2, G//2).
    source : (Sx, Sy) float64
        Illumination source intensity distribution.  Must be defined
        on the same grid as the pupil.  Normalised (sum = 1).
    fx, fy : (G, G) float64
        Normalised frequency coordinates from ``pupil_grid()``.
    pupil : (G, G) complex128 or float64
        Pupil transmission function (amplitude + phase).
    na : float
        Numerical aperture.

    Returns
    -------
    aerial : (G, G) float64
        Normalised aerial image intensity.
    """
    G = mask_fft.shape[0]
    device = mask_fft.device

    # Identify non-zero source points
    src_mask = source > 0
    src_indices = torch.nonzero(src_mask)  # (n_src, 2)

    if src_indices.shape[0] == 0:
        return torch.zeros(G, G, dtype=torch.float64, device=device)

    # Frequency step in the mask FFT (normalised)
    dfx = fx[1, 0].item() - fx[0, 0].item()
    dfy = fy[0, 1].item() - fy[0, 0].item()

    # Convert source indices to frequency shifts
    # Source coordinates are in sigma-space: sx, sy ∈ [-1, 1] → shift = sigma * NA / (df * ...)
    # Map: source pixel → (shift_x, shift_y) in FFT pixels
    half = G // 2
    sx_vals = (src_indices[:, 0].float() - half) / half  # [-1, 1]
    sy_vals = (src_indices[:, 1].float() - half) / half

    # Frequency shift per source point: α = σ_x · NA, β = σ_y · NA
    # In units of the FFT frequency grid
    shift_i = torch.round(sx_vals * na / (dfx * na)).long()  # ≈ G/2 * sx
    shift_j = torch.round(sy_vals * na / (dfy * na)).long()

    # Actually for the simple case where the FFT grid covers ±NA,
    # a shift in source sigma is directly a cyclic shift of the spectrum
    # Let's use a simpler approach: roll the spectrum by source-pixel offset

    aerial = torch.zeros(G, G, dtype=torch.float64, device=device)

    for idx in range(src_indices.shape[0]):
        si = src_indices[idx, 0].item()
        sj = src_indices[idx, 1].item()
        weight = source[si, sj].item()

        # Shift mask spectrum by source point position (in pupil coordinates)
        # For a mask on a G×G grid, the frequency coordinate of pixel (i,j)
        # is fx[i,j] = na * (2i/G - 1) (for conventional grid)
        # A source point at (α, β) shifts the spectrum by (−α, −β)
        di = int(round((si - half) / half * (G / 2)))
        dj = int(round((sj - half) / half * (G / 2)))

        shifted = torch.roll(mask_fft, shifts=(-di, -dj), dims=(0, 1))

        # Apply pupil
        filtered = shifted * pupil

        # IFFT → coherent image
        coherent = torch.fft.ifft2(torch.fft.ifftshift(filtered))
        intensity = (coherent * coherent.conj()).real

        aerial = aerial + weight * intensity

    return aerial


def nils(
    aerial: torch.Tensor,
    line_center: int,
    line_width_px: int,
) -> float:
    """Normalised Image Log-Slope at the line edge.

    NILS = CD · d(log I) / dx  evaluated at the nominal line edge.
    Higher NILS → better resist contrast.

    Parameters
    ----------
    aerial : (G, G) float64
        Aerial image intensity.
    line_center : int
        Pixel index of the line centre.
    line_width_px : int
        Line width in pixels (CD).

    Returns
    -------
    nils_value : float
    """
    G = aerial.shape[0]
    # Horizontal cut through the line centre
    cut = aerial[line_center, :].float()

    # Edge positions (left and right)
    left = line_center - line_width_px // 2
    right = line_center + line_width_px // 2

    # Guard against out-of-bounds
    left = max(1, left)
    right = min(G - 2, right)

    # Numerical derivative at the left edge
    dIdx_left = (cut[left + 1] - cut[left - 1]) / 2.0
    # Numerical derivative at the right edge
    dIdx_right = (cut[right + 1] - cut[right - 1]) / 2.0

    if cut[left] <= 0 or cut[right] <= 0:
        return 0.0

    nils_left = cut[left].item() / dIdx_left.item() if dIdx_left != 0 else 0.0
    nils_right = cut[right].item() / dIdx_right.item() if dIdx_right != 0 else 0.0

    cd_pixels = float(line_width_px)
    return abs(cd_pixels * (nils_left + nils_right) / 2.0)
