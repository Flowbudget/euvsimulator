"""The tasks a background job can run: one simulation, a process window, the
structural uncertainty bands. Each builds its result from the pipeline
output in the same JSON shape the synchronous ``POST /simulate`` returns.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional

import numpy as np

from euvsimulator.api.fields import PRESETS, config_as_dict
from euvsimulator.api.jobs import Job
from euvsimulator.calibrate.bands import structural_bands
from euvsimulator.metro.process_window import process_window as pw_metrics
from euvsimulator.pipeline import (
    AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2,
    SimulationCancelledError,
    SimulationConfig,
    SimulationResult,
    run_simulation,
)

SEM_BIAS_NOTE = (
    "LER/LWR are 1σ of the simulated edge/width; no SEM bias is added (measured values "
    "from CD-SEM carry one, e.g. imec biased/unbiased ≈ 1.66)."
)


def simulation_payload(
    cfg: SimulationConfig, result: SimulationResult, preset_key: str
) -> Dict[str, Any]:
    """Results, profiles and notes of one run (shared by /simulate and the jobs)."""
    aerial = result.aerial_image
    centre = aerial.shape[0] // 2
    i_max = float(aerial.max())
    i_min = float(aerial.min())
    results: List[Dict[str, Any]] = [
        {"stage": "aerial", "metric": "nils", "value": result.nils_value, "unit": ""},
        {"stage": "resist", "metric": "cd", "value": result.cd_nm, "unit": "nm"},
        {
            "stage": "aerial",
            "metric": "contrast",
            "value": (i_max - i_min) / (i_max + i_min + 1e-12) * 100,
            "unit": "%",
        },
    ]
    if cfg.enable_stochastic:
        results.append(
            {"stage": "resist", "metric": "ler_1sigma", "value": result.ler_nm, "unit": "nm"}
        )
        results.append(
            {"stage": "resist", "metric": "lwr_1sigma", "value": result.lwr_nm, "unit": "nm"}
        )

    raw: Dict[str, Any] = {
        "aerial_profile_nm": aerial[centre, :].tolist(),
        "aerial_shape": list(aerial.shape),
        # 1 = developed (dissolved through the film), 0 = resist remaining
        "resist_profile": result.resist_profile[centre, :].tolist(),
        "absorber_reflectivity": result.absorber_reflectivity,
        "grid": cfg.grid,
    }
    if cfg.resist_model == "aerial_threshold":
        # Same expression as pipeline._cd_via_aerial_threshold, so the plotted
        # threshold line is the one the CD was actually extracted at.
        raw["threshold_intensity"] = (
            cfg.resist_threshold_norm
            * float(aerial.mean())
            * (AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2 / max(cfg.dose_mj_cm2, 1e-9))
        )
    if cfg.enable_stochastic and result.ler_metadata:
        raw["ler_metadata"] = {
            k: v for k, v in result.ler_metadata.items() if isinstance(v, (int, float, str, bool))
        }

    notes = [PRESETS[preset_key].provenance]
    if cfg.enable_stochastic:
        notes.append(SEM_BIAS_NOTE)
    return {
        "status": "completed",
        "preset": preset_key,
        "config": config_as_dict(cfg),
        "results": results,
        "raw": raw,
        "notes": notes,
    }


# ── task: one simulation ─────────────────────────────────────────────────


def simulate_task(cfg: SimulationConfig, preset_key: str):
    """Task function for ``kind="simulate"``."""

    def task(job: Job) -> Dict[str, Any]:
        job.report(0.0, "running the pipeline")
        result = run_simulation(cfg, progress=job.progress_hook())
        return simulation_payload(cfg, result, preset_key)

    return task


# ── task: process window ─────────────────────────────────────────────────


def process_window_task(
    cfg: SimulationConfig,
    preset_key: str,
    *,
    doses: List[float],
    focuses: List[float],
    tolerance: float,
):
    """Task function for ``kind="process_window"``: CD over dose × focus.

    Same loop as ``euv process-window``; DoF and EL come from
    ``metro.process_window`` (single definition of both metrics).
    """

    def task(job: Job) -> Dict[str, Any]:
        n_total = len(doses) * len(focuses)
        cd = np.full((len(doses), len(focuses)), np.nan)
        nils = np.full((len(doses), len(focuses)), np.nan)
        k = 0
        for i, d in enumerate(doses):
            for j, f in enumerate(focuses):
                if job.cancel_requested:
                    raise SimulationCancelledError("cancelled")
                job.report(
                    k / n_total,
                    f"dose {d:g} mJ/cm², focus {f:g} nm ({k + 1} of {n_total})",
                    {"cd_matrix": _tolist(cd), "nils_matrix": _tolist(nils)},
                )
                r = run_simulation(dataclasses.replace(cfg, dose_mj_cm2=d, focus_nm=f))
                cd[i, j] = r.cd_nm
                nils[i, j] = r.nils_value
                k += 1
        target = cfg.line_width_nm
        metrics = pw_metrics(
            cd.T, list(doses), list(focuses), target_cd=target, tolerance=tolerance
        )
        return {
            "status": "completed",
            "preset": preset_key,
            "config": config_as_dict(cfg),
            "target_cd_nm": target,
            "tolerance": tolerance,
            "doses": list(doses),
            "focuses": list(focuses),
            "cd_matrix": _tolist(cd),
            "nils_matrix": _tolist(nils),
            "depth_of_focus_nm": float(metrics["dof_nm"]),
            "exposure_latitude_pct": float(metrics["el_pct"]),
            "notes": [
                PRESETS[preset_key].provenance,
                f"CD in spec = {target:g} nm ± {tolerance * 100:g} %; exposure latitude = "
                "(dose_max − dose_min)/dose_best at best focus, depth of focus = in-spec "
                "focus range at best dose (metro.process_window).",
            ],
        }

    return task


# ── task: structural bands ───────────────────────────────────────────────


def bands_task(
    cfg: SimulationConfig,
    preset_key: str,
    *,
    rows: int,
    seeds: List[int],
    dose_lo: float,
    dose_hi: float,
):
    """Task function for ``kind="bands"``: ``calibrate.bands.structural_bands``
    on the resolved configuration (both PEB laws × both dissolution cells).
    """
    base = config_as_dict(cfg)
    if base.get("ler_passband_nm") is not None:
        base["ler_passband_nm"] = tuple(base["ler_passband_nm"])
    for key in (
        "resist_model",
        "grid",
        "enable_stochastic",
        "stochastic_n_realisations",
        "stochastic_ler_grid_y",
        "stochastic_seed",
        "peb_model",
        "dose_mj_cm2",
        "development_stochasticity",
        "dissolution_cell_nm",
    ):
        base.pop(key, None)

    def task(job: Job) -> Dict[str, Any]:
        def progress(fraction: float, label: str) -> bool:
            job.report(fraction, label)
            return not job.cancel_requested

        out = structural_bands(
            base,
            target_cd_nm=cfg.line_width_nm,
            dose_lo=dose_lo,
            dose_hi=dose_hi,
            grid=cfg.grid,
            rows=rows,
            seeds=tuple(seeds),
            progress=progress,
        )
        out.update(
            {
                "status": "completed",
                "preset": preset_key,
                "config": config_as_dict(cfg),
                "target_cd_nm": cfg.line_width_nm,
                "provenance": PRESETS[preset_key].provenance,
            }
        )
        return out

    return task


def _tolist(a: np.ndarray) -> List[List[Optional[float]]]:
    return [[None if np.isnan(v) else float(v) for v in row] for row in a]
