"""Mixed-precision helpers for GPU memory reduction.

Provides dtype conversion utilities and a policy engine that
recommends the appropriate precision for each operation based on
the available VRAM.
"""

from __future__ import annotations

from typing import Dict

import torch


def autocast_complex(tensor: torch.Tensor) -> torch.Tensor:
    """Downcast a complex tensor to ``complex64`` if it is currently
    ``complex128`` and the precision loss is acceptable.

    Parameters
    ----------
    tensor : torch.Tensor
        Input tensor.  Passed through unchanged if it is not complex
        or already ``complex64``.

    Returns
    -------
    torch.Tensor
        ``complex64`` tensor if the input was ``complex128``,
        otherwise the original tensor.
    """
    if tensor.is_complex() and tensor.dtype == torch.complex128:
        return tensor.to(torch.complex64)
    return tensor


def real_only(complex_tensor: torch.Tensor) -> torch.Tensor:
    """Return the real component of a complex tensor, halving its
    memory footprint.

    Useful for storing intermediate results when only the magnitude
    (not the phase) is needed, e.g. the accumulated aerial image
    intensity.

    Parameters
    ----------
    complex_tensor : torch.Tensor
        Complex-valued input tensor.

    Returns
    -------
    torch.Tensor
        Real part as a ``float64`` (or ``float32``) tensor.
    """
    return complex_tensor.real


def precision_policy(vram_gb: float = 14) -> Dict[str, torch.dtype]:
    """Recommend a dtype per operation based on the available VRAM.

    The policy balances numerical accuracy against memory footprint:

    - **Low VRAM** (< 6 GiB): use ``complex64`` / ``float32``
      everywhere.
    - **Mid VRAM** (6–12 GiB): use ``complex64`` for intermediate
      buffers, ``float64`` for accumulation.
    - **High VRAM** (≥ 12 GiB): use ``complex128`` / ``float64``
      for full double-precision accuracy.

    Parameters
    ----------
    vram_gb : float
        Available GPU memory in GiB (default 14).

    Returns
    -------
    dict
        Keys:
        - ``spectrum`` — dtype for the mask diffraction spectrum.
        - ``pupil`` — dtype for the pupil transmission.
        - ``image`` — dtype for the accumulated aerial image.
        - ``rcwa_eigen`` — dtype for the RCWA eigenvalue solve.
    """
    if vram_gb < 6:
        return {
            "spectrum": torch.complex64,
            "pupil": torch.complex64,
            "image": torch.float32,
            "rcwa_eigen": torch.complex64,
        }
    if vram_gb < 12:
        return {
            "spectrum": torch.complex64,
            "pupil": torch.complex64,
            "image": torch.float64,  # accumulate in double
            "rcwa_eigen": torch.complex64,
        }
    return {
        "spectrum": torch.complex128,
        "pupil": torch.complex128,
        "image": torch.float64,
        "rcwa_eigen": torch.complex128,
    }
