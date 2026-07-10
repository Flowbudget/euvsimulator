"""Hopkins Transmission Cross Coefficient (TCC) method for partially coherent
aerial image formation.

The TCC is pre-computed once for a given source + pupil.  Thereafter any mask
can be imaged in O(N² log N) via a sum of coherent systems (SOCS), skipping
the per-source-point loop of Abbe summation.

Reference
---------
H. H. Hopkins, "On the diffraction theory of optical images",
Proc. R. Soc. Lond. A 217, 408-432 (1953).

For EUV with mask-3D (M3D) corrections, the thin-mask assumption behind
Hopkins is an *approximation* — Abbe's method is the physically honest
approach.  However, for OPC loops where speed dominates, the Hopkins/TCC
accelerator provides large iteration-count savings.
"""

from __future__ import annotations

from typing import Dict, Tuple

import torch

from euv.aerial.abbe import abbe_image

# ── TCC construction ──────────────────────────────────────────────────


def compute_tcc(
    source: torch.Tensor,
    pupil: torch.Tensor,
    na: float = 0.33,
    grid: int = 64,
    sigma: float = 0.8,
) -> torch.Tensor:
    r"""Compute the Transmission Cross Coefficient matrix.

    The TCC is defined as the overlap integral of the source, pupil, and
    complex-conjugate pupil over the illumination cone [Hopkins 1953]_:

    .. math::

        T(f', f'') = \iint S(f) \, P(f + f') \, P^*(f + f'')\, d^2f

    where *S* is the source intensity, *P* the pupil, and *f*, *f'*, *f''*
    are 2D frequency vectors.  The discrete approximation requires
    :math:`G^2 \times G^2` storage, i.e. O(G⁴).

    Parameters
    ----------
    source : (G, G) float64
        Normalised illumination source intensity (sum = 1).
    pupil : (G, G) complex128 or float64
        Pupil transmission (may include aberrations).
    na : float
        Numerical aperture.
    grid : int
        Pixel grid size *G*.
    sigma : float
        Partial coherence factor (used only for fallback when *source*
        is not explicitly given).

    Returns
    -------
    tcc : (G², G²) complex128
        The TCC matrix: each row/column index corresponds to a flattened
        2D frequency coordinate.

    Notes
    -----
    CPU-only.  The TCC is assembled via a single batched matrix product
    instead of per-pixel outer loops for efficiency:

        TCC = P_s · diag(w) · P_sᴴ

    where *P_s* columns are the pupil shifted by each source point and
    *w* are the source weights.
    """
    G = grid
    device = source.device

    source = source.cpu()
    pupil = pupil.cpu().to(torch.complex128)

    # Threshold very small source values
    src_thresh = source > 1e-12
    src_indices = torch.nonzero(src_thresh)
    n_src = src_indices.shape[0]

    if n_src == 0:
        return torch.zeros(G * G, G * G, dtype=torch.complex128, device=device)

    half = G // 2

    # Flattened index map: (i, j) → i * G + j  (row-major)
    n_freqs = G * G

    # Each source pixel (α, β) defines a shift of the pupil.
    # In normalised σ-space the source pixel at (sx, sy) ∈ [-1, 1]²
    # corresponds to a frequency shift α = sx·NA, β = sy·NA.
    # On the G×G grid spanning ±NA, the pixel offset is:
    #   di = round(α / (2·NA/G)) = round(sx · G/2)
    src_norm = (src_indices - half).float() / half  # (n_src, 2) ∈ [-1, 1]
    shifts_px = torch.round(src_norm * (G / 2)).long()  # (n_src, 2)

    source_weights = source[src_indices[:, 0], src_indices[:, 1]]  # (n_src,)

    # Build shifted-pupil matrix P_s : (G², n_src)
    P_shifted = torch.zeros(n_freqs, n_src, dtype=torch.complex128, device=device)

    for s_idx in range(n_src):
        di, dj = shifts_px[s_idx, 0].item(), shifts_px[s_idx, 1].item()
        pupil_roll = torch.roll(pupil, shifts=(-di, -dj), dims=(0, 1))
        P_shifted[:, s_idx] = pupil_roll.reshape(-1)

    # TCC = P_s · diag(w) · P_sᴴ
    #     = (P_s · sqrt_diag(w)) · (P_s · sqrt_diag(w))ᴴ
    sqrt_w = source_weights.sqrt().to(torch.complex128)
    P_weighted = P_shifted * sqrt_w[None, :]  # (G², n_src)

    # Batched matrix multiply: C = A @ Aᴴ
    tcc = P_weighted @ P_weighted.conj().T  # (G², G²)

    return tcc


# ── SOCS decomposition ────────────────────────────────────────────────


def tcc_soc_decomposition(
    tcc: torch.Tensor,
    n_kernels: int = 64,
) -> torch.Tensor:
    r"""Sum of Coherent Systems (SOCS) decomposition of the TCC.

    The TCC is Hermitian positive semi-definite, so the eigenvalue
    decomposition yields the SOCS representation:

    .. math::

        T(f', f'') \approx \sum_{k=1}^{N} \lambda_k \, \Phi_k(f') \,
        \Phi_k^*(f'')

    where :math:`\lambda_k` are the :math:`N` largest eigenvalues and
    :math:`\Phi_k` the corresponding eigenfunctions (the SOCS kernels).
    Each kernel is reshaped to a 2D (G, G) grid.

    Parameters
    ----------
    tcc : (G², G²) complex128
        The TCC matrix (Hermitian).
    n_kernels : int
        Number of retained SOCS kernels.

    Returns
    -------
    kernels : (n_kernels, G, G) complex128
        SOCS kernels (the eigenfunctions) ordered by descending eigenvalue.
        Each kernel is weighted by :math:`\sqrt{\lambda_k}` and reshaped
        to the 2D pupil grid.
    """
    G = int(round(tcc.shape[0] ** 0.5))
    assert G * G == tcc.shape[0], "TCC must be (G², G²)"

    # Eigenvalue decomposition of the Hermitian matrix
    try:
        eigenvalues, eigenvectors = torch.linalg.eigh(tcc)
    except RuntimeError:
        # Force Hermitian symmetry and retry
        tcc_sym = 0.5 * (tcc + tcc.mH)
        eigenvalues, eigenvectors = torch.linalg.eigh(tcc_sym)

    # eigh returns ascending order; reverse to get descending
    eigenvalues = eigenvalues.flip(0)
    eigenvectors = eigenvectors.flip(1)

    # Keep top N kernels
    n_keep = min(n_kernels, G * G)

    # Weighted kernels: k_k = sqrt(λ_k) · Φ_k  →  (G, G)
    lam_top = eigenvalues[:n_keep]
    evec_top = eigenvectors[:, :n_keep]  # (G², n_keep)

    # sqrt(λ) * Φ  for λ > 0
    sqrt_lam = lam_top.sqrt().to(torch.complex128)
    kernel_1d = evec_top * sqrt_lam[None, :]  # (G², n_keep)

    # Reshape to (n_keep, G, G)
    kernels = kernel_1d.T.reshape(n_keep, G, G).contiguous()

    return kernels


# ── Aerial image from SOCS kernels ────────────────────────────────────


def hopkins_aerial(
    mask_fft: torch.Tensor,
    kernels: torch.Tensor,
) -> torch.Tensor:
    r"""Compute the aerial image via SOCS sum.

    The aerial image from the SOCS decomposition is:

    .. math::

        I(x, y) = \sum_{k=1}^{N} \left|
            \mathcal{F}^{-1}\left[ O(f) \, \Phi_k(f) \right]
        \right|^2

    where *O* is the mask diffraction spectrum and :math:`\Phi_k` are the
    SOCS kernels.

    Parameters
    ----------
    mask_fft : (G, G) complex128
        2D FFT of the mask transmission (centred, zero-frequency at
        G//2, G//2).
    kernels : (N, G, G) complex128
        SOCS kernels from ``tcc_soc_decomposition``.

    Returns
    -------
    aerial : (G, G) float64
        Normalised aerial image intensity.
    """
    N = kernels.shape[0]
    G = kernels.shape[1]
    device = mask_fft.device

    aerial = torch.zeros(G, G, dtype=torch.float64, device=device)

    for k in range(N):
        filtered = mask_fft * kernels[k]
        coherent = torch.fft.ifft2(torch.fft.ifftshift(filtered))
        aerial = aerial + (coherent * coherent.conj()).real

    return aerial


# ── Comparison: Hopkins vs. Abbe ──────────────────────────────────────


def compare_hopkins_abbe(
    mask: torch.Tensor,
    source: torch.Tensor,
    pupil: torch.Tensor,
    fx: torch.Tensor,
    fy: torch.Tensor,
    na: float = 0.33,
    grid: int = 64,
    period_m: float = 1e-6,
    wavelength_m: float = 13.5e-9,
) -> Dict[str, torch.Tensor]:
    """Compare Hopkins/TCC aerial image with the Abbe reference.

    Parameters
    ----------
    mask : (G, G) float64 or complex128
        Real-space mask transmission (before FFT).
    source : (G, G) float64
        Illumination source.
    pupil : (G, G) complex128 or float64
        Pupil transmission.
    fx, fy : (G, G) float64
        Normalised frequency coordinates from ``pupil_grid()``.
    na : float
        Numerical aperture.
    grid : int
        Pixel grid size.

    Returns
    -------
    result : dict with keys:
        hopkins_aerial : (G, G) float64
        abbe_aerial : (G, G) float64
        difference : (G, G) float64  (hopkins - abbe)
        mae : float  (mean absolute error)
        rmse : float  (root mean square error)
        max_error : float
        relative_error : float  (rms / rms(abbe))
    """
    mask_fft = torch.fft.fft2(mask)

    # Abbe reference
    abbe_img = abbe_image(
        mask_fft, source, fx, fy, pupil, na=na, period_m=period_m, wavelength_m=wavelength_m
    )

    abbe_rms = (abbe_img**2).mean().sqrt().item()
    if abbe_rms < 1e-30:
        abbe_rms = 1.0  # avoid division by zero

    # Hopkins TCC
    tcc = compute_tcc(source, pupil, na=na, grid=grid)
    n_kernels = min(grid * grid, 64)
    kernels = tcc_soc_decomposition(tcc, n_kernels=n_kernels)
    hopkins_img = hopkins_aerial(mask_fft, kernels)

    # Error metrics
    diff = hopkins_img - abbe_img
    mae = diff.abs().mean().item()
    rmse = (diff**2).mean().sqrt().item()
    max_err = diff.abs().max().item()
    rel_err = rmse / abbe_rms if abbe_rms > 0 else 0.0

    return {
        "hopkins_aerial": hopkins_img,
        "abbe_aerial": abbe_img,
        "difference": diff,
        "mae": mae,
        "rmse": rmse,
        "max_error": max_err,
        "relative_error": rel_err,
    }


# ── Internal helpers ──────────────────────────────────────────────────


def _meshgrid_mf(grid: int, device: str) -> Tuple[torch.Tensor, torch.Tensor]:
    """Return (fy, fx) normalised coordinates in MF (row-major) order.

    Returns indices in the order used by PyTorch's meshgrid with
    ``indexing="ij"``: the first dimension is row (y) and the second
    is column (x).
    """
    x = torch.linspace(-1.0, 1.0, grid, device=device)
    y = torch.linspace(-1.0, 1.0, grid, device=device)
    fy, fx = torch.meshgrid(y, x, indexing="ij")
    return fy, fx
