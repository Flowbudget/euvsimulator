"""Chunked processing kernels for GPU memory-limited simulations.

Processes large problems — many source points (Abbe) or many RCWA
layers — in batches, accumulating intermediate results on the GPU
without exceeding the VRAM budget.
"""

from __future__ import annotations

import torch

from euv.aerial.abbe import abbe_image


def chunked_abbe(
    mask_fft: torch.Tensor,
    source_points: torch.Tensor,
    fx: torch.Tensor,
    fy: torch.Tensor,
    pupil: torch.Tensor,
    na: float = 0.33,
    chunk_size: int = 32,
    period_m: float = 64e-9,
    wavelength_m: float = 13.5e-9,
) -> torch.Tensor:
    """Compute the aerial image via chunked Abbe summation.

    Iterates over source points in chunks of *chunk_size*, computing
    the partial coherent image for each chunk and accumulating into
    the final result.  This trades a small loop overhead for a
    significantly reduced peak GPU memory footprint.

    For each chunk, the source tensor is zeroed everywhere except for
    the chunk's source points, and ``abbe_image`` runs on that masked
    source.  Results are summed across chunks.

    Parameters
    ----------
    mask_fft : (G, G) complex128
        2D FFT of the mask transmission.
    source_points : (Sx, Sy) float64
        Full illumination source intensity distribution.
    fx, fy : (G, G) float64
        Normalised frequency coordinates from ``pupil_grid()``.
    pupil : (G, G) complex128 or float64
        Pupil transmission function.
    na : float
        Numerical aperture.
    chunk_size : int
        Maximum number of source points to process per chunk
        (default 32).  Lower values reduce peak memory but increase
        Python loop overhead.

    Returns
    -------
    aerial : (G, G) float64
        Normalised aerial image intensity, matching the output of
        ``abbe_image`` run on the full source (within numerical
        precision).
    """
    G = mask_fft.shape[0]
    device = mask_fft.device
    dtype = source_points.dtype

    # Identify all non-zero source point indices
    src_mask = source_points > 0
    src_indices = torch.nonzero(src_mask)  # (n_src, 2)
    n_src = src_indices.shape[0]

    if n_src == 0:
        return torch.zeros(G, G, dtype=torch.float64, device=device)

    # Extract source weights at non-zero positions
    weights = source_points[src_mask]  # (n_src,)

    aerial = torch.zeros(G, G, dtype=torch.float64, device=device)

    for start in range(0, n_src, chunk_size):
        end = min(start + chunk_size, n_src)
        chunk_indices = src_indices[start:end]

        # Build a source tensor that is zero everywhere except the
        # chunk's source points.  This is the simplest approach and
        # matches the abbe_image interface exactly.
        chunk_source = torch.zeros_like(source_points)
        # Set the chunk's source points
        chunk_source[chunk_indices[:, 0], chunk_indices[:, 1]] = weights[start:end]

        # Compute partial aerial image for this chunk
        partial = abbe_image(
            mask_fft, chunk_source, fx, fy, pupil, na, period_m=period_m, wavelength_m=wavelength_m
        )
        aerial = aerial + partial

    return aerial


def chunked_rcwa(
    geometry_profile: torch.Tensor,
    chunk_size_mb: int = 500,
) -> torch.Tensor:
    """Process RCWA layers in chunks to stay within a memory budget.

    .. note::

       This is a placeholder implementation.  The full RCWA chunked
       solver will cascade per-layer S-matrices in groups rather than
       all at once.  Currently returns the input unchanged to
       validate the API contract.

    Parameters
    ----------
    geometry_profile : (N, ...) complex128
        Permittivity profile through the mask stack, with the first
        dimension indexing the vertical layer.
    chunk_size_mb : int
        Target memory budget per chunk in megabytes (default 500).

    Returns
    -------
    torch.Tensor
        The input profile (placeholder — full chunked RCWA to be
        implemented in a future release).
    """
    _ = chunk_size_mb  # reserved for future use
    return geometry_profile
