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
Coefficient TCC(i, j) is evaluated as the exact source–pupil overlap
integral ∬ S(f) P(f + f_i) P*(f + f_j) d²f / ∬ S d²f on a 2D frequency
grid (``_compute_tcc_matrix``), for conventional, annular, dipole and
quasar sources.  (For a conventional disk source and orders both inside
the pupil this reduces to the classical 2·J₁(x)/x form; the numerical
overlap additionally accounts for the pupil edge, which the closed form
does not.)  The TCC damps order interference *gradually* — there is no
hard cutoff.  Scalar, thin-mask formulation: no polarisation, no
obliquity factors, no chief-ray-angle shadowing in this path (mask-3D
effects require ``use_rcwa=True``).
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

    Returns
    -------
    aerial : (G, G) float64
        Normalised aerial image intensity.
    """
    device = orders_complex.device
    G = grid

    # Spatial positions over one period
    x_pos = torch.linspace(-period_m / 2, period_m / 2, G, device=device)

    # Maximum order accepted by the pupil.
    # For on-axis (sigma=0): |m| <= NA * period / wavelength
    # For partially-coherent illumination (sigma>0), source shift extends
    # the effective range:
    #   |m| <= (1+sigma) * NA * period / wavelength
    # Orders beyond this have TCC=0 and make no contribution.
    # See _compute_tcc_matrix() for the source-pupil overlap integral.
    max_order = int(math.floor(na * period_m / wavelength_m))
    if sigma > 0.0:
        max_order = int(math.ceil((1.0 + sigma) * na * period_m / wavelength_m))

    # Build the order amplitude vector and mask
    M = orders_complex.shape[0]
    if M == 0:
        return torch.zeros(G, G, dtype=torch.float64, device=device)

    aerial_1d = torch.zeros(G, dtype=torch.complex128, device=device)

    # Pre-compute the TCC matrix via exact 2D source-pupil overlap (P1-1 fix)
    tcc_matrix = _compute_tcc_matrix(
        order_indices, sigma, na, wavelength_m, period_m, device=device,
        illumination_shape=illumination_shape,  # P1-3: pass shape to TCC
    )

    # Pre-compute defocus phase for each order (quadratic in order index)
    # φ_m = -π * focus_nm * m² * wavelength / period²  (small-angle approximation)
    # The defocus phase is applied symmetrically to BOTH orders in the
    # Hopkins double-sum (P1-Defocus fix, 2026-09-01):
    #   I = Σ_i Σ_j (a_i·e^{iφ_i}) · (a_j·e^{iφ_j})* · TCC_ij · e^{i·2π·(m_i−m_j)·x/Λ}
    focus_m = focus_nm * 1e-9  # nm → m
    defocus_phase = torch.zeros(M, dtype=torch.complex128, device=device)
    if focus_m != 0.0:
        for i in range(M):
            m = int(order_indices[i])
            phi = -math.pi * focus_m * (m**2) * wavelength_m / (period_m**2)
            defocus_phase[i] = torch.exp(1j * torch.tensor(phi, dtype=torch.float64, device=device))
    else:
        defocus_phase = torch.ones(M, dtype=torch.complex128, device=device)

    # Apply defocus phase to all orders (P1-Defocus fix)
    orders_defocused = orders_complex * defocus_phase

    for i in range(M):
        mi = int(order_indices[i])
        ri = orders_defocused[i]
        if abs(ri) < 1e-15:
            continue
        if abs(mi) > max_order:
            continue  # outside pupil

        for j in range(M):
            mj = int(order_indices[j])
            rj = orders_defocused[j]
            if abs(rj) < 1e-15:
                continue
            if abs(mj) > max_order:
                continue  # outside pupil

            # TCC factor: exact 2D source-pupil overlap integral (P1-1 fix).
            tcc = tcc_matrix[i, j]

            # Interference term with defocus phase.
            # Both orders carry the defocus phase, so the combined
            # phase is φ_i - φ_j, which preserves Hermitian symmetry.
            phase = 2.0 * math.pi * (mi - mj) * x_pos / period_m
            interference = ri * rj.conj() * tcc * torch.exp(1j * phase)
            aerial_1d += interference

    # The Hopkins double-sum is already the (real, Hermitian) intensity:
    # I(x) = Σ_i Σ_j r_i conj(r_j) TCC(i,j) exp(i 2π (m_i-m_j) x/Λ).
    # The (i,j)+(j,i) pairs carry conjugate phases that cancel the
    # imaginary part, so taking .real() is exact (P0 fix, 2026-08-31).
    aerial_1d = aerial_1d.real

    # Replicate to 2D: x along columns (dim 1), y along rows (dim 0)
    aerial = aerial_1d.unsqueeze(0).expand(G, G).clone()

    return aerial


def nils(
    aerial: torch.Tensor,
    line_center: int,
    line_width_px: int,
    dx_nm: float = 1.0,
    threshold: float | None = None,
) -> float:
    """Mack NILS at the printed intensity-threshold edges.

    NILS = CD · |dI/dx| / I_edge, evaluated at the crossings of
    ``threshold`` (Mack 2007 §4.5).  CD is the distance between the
    two interpolated edges of the longest below-threshold run.
    Left and right edge NILS are averaged.

    Parameters
    ----------
    aerial : (G, G) float64
        Aerial image intensity.
    line_center : int
        Row index of the centre line-cut.
    line_width_px : int
        Unused except as a last-resort fallback if no edge is found.
    dx_nm : float
        Grid spacing [nm/pixel].
    threshold : float, optional
        Intensity threshold of the printed edge.  If omitted, defaults
        to ``0.5 * mean(cut)``, which matches the default aerial_threshold
        Optical-CD at nominal dose=20 mJ/cm².  Callers that already
        computed a CD threshold MUST pass it — do not rely on this
        default for a non-default resist_threshold_norm or dose.

    Returns
    -------
    nils : float
        Mean Mack NILS of the two printed edges (dimensionless).
    """
    cut = aerial[line_center, :].to(dtype=torch.float64)
    G = int(cut.shape[0])
    if G < 2 or dx_nm <= 0.0:
        return 0.0

    Imin = float(cut.min())
    Imax = float(cut.max())
    if Imax <= Imin + 1e-12:
        return 0.0

    if threshold is None:
        thr = 0.5 * float(cut.mean())
    else:
        thr = float(threshold)

    if thr <= 1e-30:
        return 0.0

    # Linear-interpolated crossings between adjacent samples.
    # The slope on that segment is exact for piecewise-linear I(x).
    crossings: list[tuple[float, float]] = []
    for i in range(G - 1):
        a = float(cut[i])
        b = float(cut[i + 1])
        da = a - thr
        db = b - thr
        if da == 0.0 and db == 0.0:
            continue
        if da * db > 0.0:
            continue
        denom = b - a
        if abs(denom) < 1e-30:
            continue
        t = (thr - a) / denom
        if t < 0.0 or t > 1.0:
            continue
        x_px = i + t
        slope_per_nm = denom / dx_nm
        crossings.append((x_px, slope_per_nm))

    if len(crossings) < 2:
        return 0.0

    # Pair crossings and keep the longest below-threshold span.
    # The profile is periodic, so the below-threshold run that "wins" may
    # straddle the array boundary (e.g. when the line sits at the mask
    # edge rather than the centre).  This must mirror the wrap-around
    # pairing in pipeline._cd_via_aerial_threshold() exactly — otherwise
    # NILS and CD can silently disagree about which run is the printed
    # line, and NILS returns 0.0 whenever the wrap-around run is the only
    # valid (below-threshold) one (confirmed via the default --use-rcwa
    # CLI benchmark, where nils() previously returned 0.0 while CD was
    # computed correctly at ~26.18 nm).
    best: tuple[float, float, float, float] | None = None
    best_width = -1.0
    n_cross = len(crossings)
    for k in range(n_cross):
        x0, s0 = crossings[k]
        x1, s1 = crossings[(k + 1) % n_cross]
        if k == n_cross - 1:
            x1 = x1 + G  # wrap around periodic boundary
        mid_px = 0.5 * (x0 + x1)
        if mid_px > G:
            mid_px = mid_px - G
        i_mid = min(G - 1, max(0, int(round(mid_px))))
        if float(cut[i_mid]) >= thr:
            continue
        width = x1 - x0
        if width > best_width:
            best_width = width
            best = (x0, s0, x1, s1)

    if best is None:
        return 0.0

    cd_nm = best_width * dx_nm
    if cd_nm <= 0.0:
        return 0.0

    _, slope_left, _, slope_right = best
    nils_left = cd_nm * abs(slope_left) / thr
    nils_right = cd_nm * abs(slope_right) / thr
    return 0.5 * (nils_left + nils_right)


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


# ──────────────────────────────────────────────
# P1-1: Exact TCC via 2D source-pupil overlap
# ──────────────────────────────────────────────


def _compute_tcc_matrix(
    order_indices: torch.Tensor,
    sigma: float,
    na: float,
    wavelength_m: float,
    period_m: float,
    grid: int = 256,
    device: torch.device | None = None,
    illumination_shape: str = "conventional",
) -> torch.Tensor:
    """Compute the exact TCC matrix via 2D source-pupil overlap integral.

    TCC(i,j) = int int S(fx,fy) P(fx+fi,fy) P*(fx+fj,fy) dfx dfy
               / int int S dfx dfy

    where S is the source intensity distribution (determined by
    illumination_shape), P is the pupil (unit disk), and
    fi = mi * lambda / (period * NA) is the normalized spatial frequency
    of order mi.

    Supported illumination shapes:
    - "conventional": uniform disk of radius sigma
    - "annular": ring from sigma_inner to sigma
    - "dipole_x" / "dipole": two poles on the x-axis
    - "dipole_y": two poles on the y-axis
    - "quasar": four poles (quadrupole)

    Parameters
    ----------
    order_indices : (M,) int64
        Diffraction order indices.
    sigma : float
        Partial coherence factor (outer source radius in pupil-normalized units).
    na : float
        Numerical aperture.
    wavelength_m : float [m]
        Free-space wavelength.
    period_m : float [m]
        Mask period.
    grid : int
        Integration grid size (default: 256 -> 256x256).
    device : torch.device, optional
    illumination_shape : str
        Source shape (default: "conventional").

    Returns
    -------
    TCC : (M, M) complex128
        Transmission Cross Coefficient matrix.
    """
    M = order_indices.shape[0]
    if device is None:
        device = torch.device("cpu")

    f = torch.linspace(-2.0, 2.0, grid, device=device, dtype=torch.float64)
    FX, FY = torch.meshgrid(f, f, indexing="ij")
    r2 = FX**2 + FY**2

    # Build source mask for the requested illumination shape
    shape = illumination_shape.lower()
    if shape == "annular":
        sigma_inner = 0.3 * sigma
        S = ((r2 <= sigma**2) & (r2 >= sigma_inner**2)).to(torch.float64)
    elif shape in ("dipole", "dipole_x"):
        pole_sigma = 0.2 * sigma
        half = 0.3 * sigma  # separation/2
        pole_r = (FX - half) ** 2 + FY**2 <= pole_sigma**2
        pole_l = (FX + half) ** 2 + FY**2 <= pole_sigma**2
        S = ((pole_r | pole_l) & (r2 <= sigma**2)).to(torch.float64)
    elif shape == "dipole_y":
        pole_sigma = 0.2 * sigma
        half = 0.3 * sigma
        pole_u = FX**2 + (FY - half) ** 2 <= pole_sigma**2
        pole_d = FX**2 + (FY + half) ** 2 <= pole_sigma**2
        S = ((pole_u | pole_d) & (r2 <= sigma**2)).to(torch.float64)
    elif shape == "quasar":
        pole_sigma = 0.2 * sigma
        half = 0.3 * sigma
        angle = torch.tensor(math.pi / 6.0, device=device)  # 30 deg
        ca, sa = torch.cos(angle), torch.sin(angle)
        # Four rotated poles
        poles = torch.zeros(grid, grid, dtype=torch.bool, device=device)
        for cx, cy in [(half, half), (half, -half), (-half, half), (-half, -half)]:
            # Rotate coordinates
            rx = FX * ca - FY * sa - cx
            ry = FX * sa + FY * ca - cy
            poles = poles | (rx**2 + ry**2 <= pole_sigma**2)
        S = (poles & (r2 <= sigma**2)).to(torch.float64)
    elif shape == "conventional":
        S = (r2 <= sigma**2).to(torch.float64)
    else:
        supported = ["conventional", "annular", "dipole", "dipole_x", "dipole_y", "quasar"]
        raise ValueError(
            f"Unknown illumination_shape {illumination_shape!r}. "
            f"Supported shapes: {supported}"
        )

    S_sum = S.sum()
    if S_sum < 1e-30:
        # Coherent limit: TCC = 1 for all pairs
        return torch.ones(M, M, dtype=torch.complex128, device=device)

    f_ord = order_indices.to(torch.float64) * wavelength_m / (period_m * na)

    P_shifted = torch.zeros(M, grid, grid, dtype=torch.float64, device=device)
    for i, fi in enumerate(f_ord):
        P_shifted[i] = ((FX + fi) ** 2 + FY**2 <= 1.0).to(torch.float64)

    S_weighted = S.reshape(-1)
    P_flat = P_shifted.reshape(M, -1)

    TCC = (P_flat * S_weighted[None, :]) @ P_flat.T
    TCC = TCC / S_sum

    return TCC.to(torch.complex128)
