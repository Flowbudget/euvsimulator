"""Device selection, introspection, and default dtype management.

Provides a single source of truth for which hardware (CPU / CUDA GPU)
simulation kernels run on, and what precision the tensor operations
use by default.
"""

from __future__ import annotations

from typing import Dict

import torch


def select_device(prefer_gpu: bool = True) -> torch.device:
    """Return the best available device.

    Parameters
    ----------
    prefer_gpu : bool
        If ``True`` (default) and a CUDA-capable GPU is available,
        returns ``device(type='cuda')``.  Otherwise returns
        ``device(type='cpu')``.

    Returns
    -------
    torch.device
    """
    if prefer_gpu and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def device_info(device: torch.device) -> Dict[str, object]:
    """Return a dictionary of hardware properties for *device*.

    Parameters
    ----------
    device : torch.device

    Returns
    -------
    dict
        Keys:
        - ``name`` — device name string (e.g. ``"NVIDIA A100"`` or ``"cpu"``).
        - ``vram_gb`` — total GPU memory in GiB, or 0.0 for CPU.
        - ``compute_capability`` — CUDA compute capability ``(major, minor)``
          tuple, or ``None`` for CPU.
    """
    if device.type == "cuda":
        idx = device.index if device.index is not None else 0
        name = torch.cuda.get_device_name(idx)
        vram_gb = torch.cuda.get_device_properties(idx).total_mem / (1024**3)
        cap = torch.cuda.get_device_capability(idx)
        return {
            "name": name,
            "vram_gb": round(vram_gb, 2),
            "compute_capability": cap,
        }
    return {
        "name": "cpu",
        "vram_gb": 0.0,
        "compute_capability": None,
    }


def set_default_dtype(
    complex_dtype: torch.dtype = torch.complex128,
    real_dtype: torch.dtype = torch.float64,
) -> None:
    """Set PyTorch's default floating-point and complex dtypes.

    Call this once at the start of a simulation to establish the
    precision regime for the entire module.

    Parameters
    ----------
    complex_dtype : torch.dtype
        Default complex type (e.g. ``torch.complex128`` or
        ``torch.complex64``).
    real_dtype : torch.dtype
        Default real type (e.g. ``torch.float64`` or ``torch.float32``).
    """
    torch.set_default_dtype(real_dtype)
    # torch does not have a global set_default_complex_dtype in older
    # versions; instead we ensure the default dtype is set correctly
    # and rely on complex tensors being constructed explicitly.
    _ = complex_dtype  # kept for API symmetry / future use
