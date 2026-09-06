"""Memory estimate for a simulation, shown in the GUI instead of a size limit.

The software has no artificial limits on grid, rows, layers or
realisations; what it can do instead is tell the user roughly what a run
will need. The model below was fitted to the peak resident set size of
``run_simulation`` measured on an Apple M1 (macOS, torch CPU, float64) on
2026-09-06 for eleven configurations (grid 128–512, rows 512–4096, 1–3
realisations, 21 and 41 depth layers; scratch script ``mem_probe.py`` in the
work log, Fortsetzung 46). It reproduces those measurements within about
±30 %, which is what the GUI states. Dominant terms:

- depth-resolved 3-D stack of the deterministic full-chemistry chain:
  ~330 B per voxel × layers × grid²;
- the stochastic chain's y-tile (``_noisy_depth_map``, 1024 rows + halo):
  ~250 B per voxel × layers × min(rows, 1024) × grid;
- 2-D fields kept per realisation for the LER estimator:
  ~170 B per pixel × rows × grid × realisations;
- everything else (aerial image, mask, torch runtime): ~55 MB above the
  interpreter's baseline, independent of the grid up to 512.
"""

from __future__ import annotations

from typing import Any, Dict

from euvsimulator.pipeline import SimulationConfig

BYTES_BASE = 55e6
BYTES_PER_VOXEL_STACK = 330.0
BYTES_PER_VOXEL_TILE = 250.0
BYTES_PER_PIXEL_2D = 170.0
TILE_ROWS = 1024  # pipeline._noisy_depth_map(tile_rows=1024)
RELATIVE_UNCERTAINTY = 0.3


def estimate_memory_bytes(cfg: SimulationConfig) -> float:
    """Peak memory of one ``run_simulation`` call above the interpreter baseline."""
    g = float(cfg.grid)
    total = BYTES_BASE
    if cfg.resist_model == "full_chem":
        layers = float(cfg.n_develop_layers)
        total += BYTES_PER_VOXEL_STACK * layers * g * g
        if cfg.enable_stochastic:
            rows = float(cfg.stochastic_ler_grid_y)
            total += BYTES_PER_VOXEL_TILE * layers * min(rows, float(TILE_ROWS)) * g
            total += BYTES_PER_PIXEL_2D * rows * g * float(cfg.stochastic_n_realisations)
    return total


def estimate(cfg: SimulationConfig, runs: int = 1) -> Dict[str, Any]:
    """Estimate for the GUI: bytes, a human-readable size and the caveat."""
    per_run = estimate_memory_bytes(cfg)
    return {
        "memory_bytes": per_run,
        "memory_text": _human(per_run),
        "relative_uncertainty": RELATIVE_UNCERTAINTY,
        "runs": runs,
        "note": (
            "Peak memory of one run above the Python baseline, from a model fitted to "
            "measurements on an Apple M1 (±30 %). Sequential runs reuse the memory."
        ),
    }


def _human(n: float) -> str:
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if n < 1000.0 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "kB") else f"{n:.1f} {unit}"
        n /= 1000.0
    return f"{n:.1f} TB"
