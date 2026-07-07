"""GPU Acceleration Layer — device management, VRAM budgeting, chunked
processing, and mixed-precision helpers for OpEnUV.

The ``accel`` package decouples simulation code from hardware details,
providing transparent fallback between CPU and GPU, memory-aware
workload sizing, and precision policies that maximise throughput on
consumer GPUs.

Submodules
----------
device
    Device selection, introspection, and default dtype management.
vram_budget
    Analytical VRAM estimators for RCWA and Abbe imaging, plus OOM
    pre-checks and a human-readable budget report.
chunked
    Chunked (source-point) Abbe summation and layer-wise RCWA for
    fitting large problems into available memory.
mixed_precision
    Context-aware dtype switching: ``complex64`` vs ``complex128``,
    ``float32`` vs ``float64``, with per-operation policy
    recommendations.
"""

from __future__ import annotations
