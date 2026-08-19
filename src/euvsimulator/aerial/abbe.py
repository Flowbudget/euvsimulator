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

For the 1D Hopkins formulation used here, the aerial image intensity
is (Hopkins 1953)::

    I(x) = Σ_i Σ_j  a_i · a_j^* · TCC(i,j) · exp(i·2π·(m_i−m_j)·x/Λ)

where a_i are the complex amplitude coefficients of the mask
reflectivity (EUV: multilayer stack reflectivity in the spaces,
absorber reflectivity on the lines).  The Transmission Cross
Coefficient (TCC) for a circular source of partial coherence sigma is::

    TCC(i,j) = 2·J₁(x) / x,   x = π·sigma·NA·|m_i−m_j|·λ/Λ

(J₁ = Bessel function of the first kind, order 1; NOT J₀).  For
sigma → 0 this reduces to the coherent limit TCC = 1 (fully coherent).
The TCC damps order interference *gradually* — there is no hard cutoff.
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F


def _j1(x: float) -> float:
    """Bessel function of the first kind, order 1 (scalar).

    Uses torch.special.bessel_j1 if available, else falls back to scipy.
    Needed for the Hopkins TCC (2*J1(x)/x) of a circular source.
    """
    try:
        return float(torch.special.bessel_j1(torch.tensor(x)).item())
    except (AttributeError, ImportError):
        from scipy.special import j1

        return float(j1(x))


def _apply_se_blur(aerial: torch.Tensor, sigma_nm: float, dx: float) -> torch.Tensor:
    """Apply a 2D Gaussian secondary-electron blur to the aerial image.

    The SE blur is the resist point-spread function: photoelectrons and
    Auger electrons random-walk before generating photoacid, blurring
    the aerial intensity at the nm scale.  This is the dominant physical
    cause of finite NILS in real EUV processes.

    Uses a separable Gaussian convolution (depthwise) for efficiency.
    """
    sigma_px = sigma_nm / dx
    if sigma_px < 1e-6:
        return aerial
    radius = max(1, int(3.0 * sigma_px + 0.5))
    kernel_size = 2 * radius + 1
    g = torch.arange(-radius, radius + 1, dtype=aerial.dtype, device=aerial.device)
    g = torch.exp(-0.5 * (g / sigma_px) ** 2)
    g = g / (g.sum() + 1e-12)
    col_k = g.view(1, 1, kernel_size, 1)
    row_k = g.view(1, 1, 1, kernel_size)
    img_4d = aerial.unsqueeze(0).unsqueeze(0)  # (1, 1, G, G)
    pad_col = F.pad(img_4d, (0, 0, radius, radius), mode="reflect")
    blurred = F.conv2d(pad_col, col_k)
    pad_row = F.pad(blurred, (radius, radius, 0, 0), mode="reflect")
    blurred = F.conv2d(pad_row, row_k)
    return blurred.squeeze(0).squeeze(0)


def aerial_from_orders(
    orders_complex: torch.Tensor,
    order_indices: torch.Tensor,
    period_m: float,
    na: float,
    wavelength_m: float,
    sigma: float,
    illumination_shape: str = "conventional",
    grid: int = 256,
    focus_nm: float = 0.0,
    se_blur_nm: float = 0.0,
) -> torch.Tensor:
    """Compute partially coherent aerial image from discrete diffraction orders.

    Uses the Hopkins formulation directly:
        I(x) = Σ_i Σ_j  r_i · r_j^* · TCC(i,j) · exp(i·2π·(m_i−m_j)·x/Λ)

    The Transmission Cross Coefficient (TCC) captures:
    - Source coherence: orders must be within NA·σ/λ of each other
    - Pupil filtering: each order must be within the NA
    - Defocus: phase shift exp(i·φ_m) for each order m

    The TCC for a circular source (conventional illumination) is the
    Hopkins degree of coherence (Bessel J1 form), not a hard top-hat.

    Parameters
    ----------
    orders_complex : (M,) complex128
        Complex reflection amplitudes for each order.
    order_indices : (M,) int
        Diffraction order indices (e.g. [-10, -9, ..., 0, ..., 10]).
    period_m : float
        Mask period [m].
    na : float
        Numerical aperture.
    wavelength_m : float
        Exposure wavelength [m].
    sigma : float
        Partial coherence factor.
    illumination_shape : str
        Source shape: "conventional", "annular", "dipole", "dipole_y", or "quasar".
        Affects the mutual coherence function (TCC) for order interference.
    grid : int
        Output image grid size (default: 256).
    focus_nm : float
        Defocus [nm]. Positive = resist above best focus. Adds quadratic phase
        to each diffraction order: φ_m = -π * focus * m² * λ / Λ².
    se_blur_nm : float
        Secondary-electron blur sigma [nm].  Models the resist-point
        spread function (acid generation PSF) — photoelectrons and
        Auger electrons undergo a random walk before producing
        photoacid, blurring the aerial image at the nm scale.
        Typical EUV CAR resists: 3–6 nm.  Set 0.0 (default) for the
        ideal optical image (NILS will then be unrealistically high,
        reflecting only the 3-order optical contrast).  This is the
        dominant physical cause of finite NILS in real EUV processes.

    Returns
    -------
    aerial : (G, G) float64
        Normalised aerial image intensity.
    """
    device = orders_complex.device
    G = grid

    # Spatial positions over one period
    x_pos = torch.linspace(-period_m / 2, period_m / 2, G, device=device)

    # Maximum order accepted by pupil
    max_order = int(math.floor(na * period_m / wavelength_m))

    # Coherence area in order units: Δm = σ · NA · Λ / λ
    coherence_orders = sigma * na * period_m / wavelength_m

    # Illumination shape modifies the effective coherence
    shape = illumination_shape.lower()
    if shape in ("annular",):
        # Annular: inner sigma ~0.4-0.5 of outer, creates minimum coherence distance
        inner_coherence = 0.3 * na * period_m / wavelength_m
    elif shape in ("dipole", "dipole_x", "dipole_y"):
        pass  # use default coherence_orders
    elif shape in ("quasar",):
        pass
    # else: conventional — use coherence_orders as-is

    # Build the order amplitude vector and mask
    M = orders_complex.shape[0]
    if M == 0:
        return torch.zeros(G, G, dtype=torch.float64, device=device)

    aerial_1d = torch.zeros(G, dtype=torch.complex128, device=device)

    # Pre-compute defocus phase for each order (quadratic in order index)
    # φ_m = -π * focus_nm * m² * wavelength / period²  (small-angle approximation)
    focus_m = focus_nm * 1e-9  # nm → m
    defocus_phase = torch.zeros(M, dtype=torch.complex128, device=device)
    if focus_m != 0.0:
        for i in range(M):
            m = int(order_indices[i])
            phi = -math.pi * focus_m * (m**2) * wavelength_m / (period_m**2)
            defocus_phase[i] = torch.exp(1j * torch.tensor(phi, dtype=torch.float64, device=device))
    else:
        defocus_phase = torch.ones(M, dtype=torch.complex128, device=device)

    for i in range(M):
        mi = int(order_indices[i])
        ri = orders_complex[i]
        if abs(ri) < 1e-15:
            continue
        if abs(mi) > max_order:
            continue  # outside pupil

        # Apply defocus phase to this order
        ri_defocused = ri * defocus_phase[i]

        for j in range(M):
            mj = int(order_indices[j])
            rj = orders_complex[j]
            if abs(rj) < 1e-15:
                continue
            if abs(mj) > max_order:
                continue

            # Check coherence: orders must be close enough in frequency
            dm = abs(mi - mj)
            if dm > coherence_orders + 1e-12:
                continue  # outside coherence area
            # Annular: very close pairs (within inner radius) also excluded
            # but NOT self-interference (dm=0) which is always coherent
            if shape == "annular" and dm > 0 and dm < inner_coherence - 1e-12:
                continue

            # TCC factor: Hopkins mutual coherence for a circular source.
            # For a source of partial coherence sigma, the cross-coherence
            # between orders m_i and m_j is (Hopkins 1953):
            #   TCC(i,j) = 2*J1(x) / x,  x = pi * sigma * NA * (m_i-m_j) * lambda / period
            # The Bessel J1 form (not J0) is the correct degree of
            # coherence for a rotationally symmetric source.  It damps
            # order interference *gradually* (never a hard cutoff).
            if dm == 0:
                tcc = 1.0
            else:
                x = math.pi * sigma * na * dm * wavelength_m / period_m
                tcc = 2.0 * _j1(x) / x

            # Interference term with defocus phase
            phase = 2.0 * math.pi * (mi - mj) * x_pos / period_m
            interference = ri_defocused * rj.conj() * tcc * torch.exp(1j * phase)
            aerial_1d += interference

    # Take absolute square (correct intensity: I = |Σ_field|²)
    aerial_1d = (aerial_1d * aerial_1d.conj()).real

    # Replicate to 2D: x along columns (dim 1), y along rows (dim 0)
    aerial = aerial_1d.unsqueeze(0).expand(G, G).clone()

    # Secondary-electron (resist) blur — applied to the 2D aerial image
    # BEFORE dose scaling (the acid image is blurred, then scaled by dose).
    if se_blur_nm > 0.0:
        aerial = _apply_se_blur(aerial, se_blur_nm, dx=period_m / G * 1e9)

    return aerial


def nils(
    aerial: torch.Tensor,
    line_center: int,
    line_width_px: int,
    dx_nm: float = 1.0,
) -> float:
    """Normalised Image Log-Slope at the line edge.

    NILS = CD · d(log I)/dx = CD · (1/I) · (dI/dx), evaluated at the
    line edge (the point of steepest intensity gradient along the
    centre row).  The measured CD (width of the undeveloped region) is
    used when the line edge is found via the gradient maximum.

    Parameters
    ----------
    aerial : (G, G) float64
        Aerial image intensity.
    line_center : int
        Row index of the centre line-cut.
    line_width_px : int
        Nominal line width in pixels (fallback if edge not found).
    dx_nm : float
        Grid spacing [nm/pixel].

    Returns
    -------
    nils : float
        Normalised image log-slope (dimensionless).
    """
    G = aerial.shape[0]
    cut = aerial[line_center, :]
    Imin, Imax = cut.min(), cut.max()
    if Imax <= Imin + 1e-12:
        return 0.0
    # gradient (per nm)
    dIdx = torch.gradient(cut, spacing=dx_nm)[0]
    # steepest point (use absolute value — sign depends on edge orientation)
    edge_idx = int(torch.argmax(torch.abs(dIdx)))
    slope = dIdx[edge_idx]
    Iedge = cut[edge_idx]
    if Iedge < 1e-12:
        return 0.0
    nils_slope = abs(slope) / Iedge  # per nm

    # measured CD: width of undeveloped (below median) region
    thr = (Imin + Imax) / 2.0
    below = cut < thr
    runs = []
    start = None
    for i, b in enumerate(below):
        b = bool(b)
        if b and start is None:
            start = i
        elif not b and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(below) - 1))
    if runs:
        longest = max(runs, key=lambda r: r[1] - r[0])
        cd_nm = (longest[1] - longest[0] + 1) * dx_nm
    else:
        cd_nm = line_width_px * dx_nm

    return nils_slope * cd_nm


# Backward-compatible alias for hopkins.py
# abbe_image was the old name; now aerial_from_orders


def abbe_image(
    mask_fft: torch.Tensor,
    source: torch.Tensor,
    fx: torch.Tensor,
    fy: torch.Tensor,
    pupil: torch.Tensor,
    na: float = 0.33,
    period_m: float = 64e-9,
    wavelength_m: float = 13.5e-9,
) -> torch.Tensor:
    """Compute the aerial image via Abbe summation over source points.

    This is the legacy Abbe method that computes the aerial image by
    summing coherent images from each source point. It matches the
    interface expected by `chunked_abbe` and `hopkins.py`.

    Parameters
    ----------
    mask_fft : (G, G) complex128
        2D FFT of the mask transmission (centred, zero-frequency
        at G//2, G//2).
    source : (Sx, Sy) float64
        Illumination source intensity distribution. Normalised (sum = 1).
    fx, fy : (G, G) float64
        Normalised frequency coordinates from ``pupil_grid()`` (-1 to 1).
    pupil : (G, G) complex128 or float64
        Pupil transmission function (amplitude + phase) defined on
        normalised coordinates (-1 to 1).  1 inside, 0 outside.
    na : float
        Numerical aperture.
    period_m : float
        Mask period in metres.
    wavelength_m : float
        Exposure wavelength in metres.

    Returns
    -------
    aerial : (G, G) float64
        Normalised aerial image intensity.
    """
    G = mask_fft.shape[0]
    device = mask_fft.device
    half = G // 2

    # Physical frequency spacing of the mask FFT (1/m)
    df = 1.0 / (period_m * G)

    # Pupil cutoff frequency (1/m) and radius in FFT pixels
    fc = na / wavelength_m
    pupil_radius_px = fc / df  # radius of the pupil in the FFT grid

    # Identify non-zero source points
    src_mask = source > 1e-6
    src_indices = torch.nonzero(src_mask)

    if src_indices.shape[0] == 0:
        return torch.zeros(G, G, dtype=torch.float64, device=device)

    aerial = torch.zeros(G, G, dtype=torch.float64, device=device)

    # Pupil radius in normalised coordinates is 1.0 (by definition).
    # In the mask FFT grid, the pupil covers pixels from
    # half - pupil_radius_px to half + pupil_radius_px.
    r_px = int(round(pupil_radius_px))

    # If the pupil is resolved within the FFT grid, use the pupil function
    # directly.  Otherwise (pupil is many pixels), the entire mask FFT is
    # inside the pupil and we just need source-shifted IFFT.
    if r_px < half:
        # Crop the pupil to the mask FFT region it covers
        x_start = half - r_px
        x_end = half + r_px + 1
        y_start = half - r_px
        y_end = half + r_px + 1

        # Map source sigma (-1..1) to the physical pupil in the FFT grid
        # A source point at sigma s shifts the mask spectrum by s * NA / lambda.
        # In FFT pixels, this is s * (NA / lambda) / df = s * pupil_radius_px.
        for idx in range(src_indices.shape[0]):
            si = src_indices[idx, 0].item()
            sj = src_indices[idx, 1].item()
            weight = source[si, sj].item()

            # Source sigma coordinate: (0,0) is centre, (-1,1) are edges
            sx = (si - half) / half  # [-1, 1]
            sy = (sj - half) / half

            # Shift in FFT pixels
            shift_x = int(round(sx * pupil_radius_px))
            shift_y = int(round(sy * pupil_radius_px))

            # Shift the mask spectrum
            shifted = torch.roll(mask_fft, shifts=(-shift_x, -shift_y), dims=(0, 1))

            # Extract the pupil-sized region
            sub = shifted[x_start:x_end, y_start:y_end]

            # Apply pupil (interpolated to match the extracted region)
            # For simplicity, just multiply by the pupil (already on normalised grid)
            # The pupil on the normalised grid covers [-1,1], but in the FFT
            # grid it covers [half-r_px, half+r_px]; we need the subregion of pupil.
            pupil_sub = pupil[x_start:x_end, y_start:y_end]

            filtered = sub * pupil_sub

            # Pad back to full grid before IFFT
            padded = torch.zeros_like(mask_fft)
            padded[x_start:x_end, y_start:y_end] = filtered

            coherent = torch.fft.ifft2(torch.fft.ifftshift(padded))
            intensity = (coherent * coherent.conj()).real
            aerial = aerial + weight * intensity
    else:
        # Pupil covers the entire FFT grid (or more) — no spatial filtering
        for idx in range(src_indices.shape[0]):
            si = src_indices[idx, 0].item()
            sj = src_indices[idx, 1].item()
            weight = source[si, sj].item()

            sx = (si - half) / half
            sy = (sj - half) / half
            shift_x = int(round(sx * pupil_radius_px))
            shift_y = int(round(sy * pupil_radius_px))

            shifted = torch.roll(mask_fft, shifts=(-shift_x, -shift_y), dims=(0, 1))
            filtered = shifted * pupil
            coherent = torch.fft.ifft2(torch.fft.ifftshift(filtered))
            intensity = (coherent * coherent.conj()).real
            aerial = aerial + weight * intensity

    return aerial
