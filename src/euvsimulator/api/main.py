"""FastAPI application for the euvsimulator REST API.

Endpoints
---------
- ``GET  /``                — Browser GUI (single page, no external assets)
- ``GET  /health``          — Service health check
- ``GET  /presets``         — Named starting configurations with provenance
- ``GET  /fields``          — Every SimulationConfig field with group, label, help
- ``POST /simulate``        — Run a full simulation pipeline (preset + overrides), blocking
- ``POST /jobs``            — Start a background job (simulate, process_window, bands)
- ``GET  /jobs/{id}``       — Progress, partial and final results of a job
- ``DELETE /jobs/{id}``     — Cancel a job (cooperative, at the next realisation/cell)
- ``GET  /jobs/{id}/export.csv`` — Profiles / matrices of a finished job as CSV
- ``POST /estimate``        — Peak-memory estimate of a configuration
- ``GET  /materials``       — List available materials in the CXRO database
- ``POST /materials/nk``    — Retrieve refractive index for a given element/energy

``POST /simulate`` is a plain ``def`` endpoint on purpose: FastAPI runs it in
its threadpool, so a long pipeline run does not block the event loop and the
GUI's health polling keeps working while a simulation is computing.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from euvsimulator import __version__
from euvsimulator.api.estimate import estimate as estimate_run
from euvsimulator.api.fields import (
    GROUPS,
    PRESETS,
    config_as_dict,
    field_catalogue,
    physics_errors,
    resolve_config,
)
from euvsimulator.api.jobs import REGISTRY
from euvsimulator.api.schemas import (
    EstimateRequest,
    EstimateResponse,
    FieldCatalogueResponse,
    HealthResponse,
    JobListResponse,
    JobRequest,
    JobStatus,
    MaterialElement,
    MaterialListResponse,
    NkRequest,
    NkResponse,
    PresetInfo,
    PresetListResponse,
    SimulationRequest,
    SimulationResponse,
)
from euvsimulator.api.tasks import (
    bands_task,
    process_window_task,
    simulate_task,
    simulation_payload,
)
from euvsimulator.materials import _ELEMENT_TABLE, get_cxro_table
from euvsimulator.pipeline import SimulationConfig
from euvsimulator.pipeline import run_simulation as run_pipeline

# ──────────────────────────────────────────────
# App instance
# ──────────────────────────────────────────────

app = FastAPI(
    title="euvsimulator — Open Source EUV Lithography Simulator",
    description="REST API for simulating EUV lithography at 13.5 nm.",
    version=__version__,
    license_info={"name": "Apache-2.0"},
)


# ──────────────────────────────────────────────
# Static files (Web UI dashboard)
# ──────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _asset_stamp() -> str:
    """Short content hash of the GUI assets, used as their cache-busting query string.

    A browser then never pairs a new page with a cached old stylesheet or
    script, also between releases (the package version alone would not change
    while the files do).
    """
    h = hashlib.sha256()
    for name in ("app.js", "style.css"):
        with open(os.path.join(STATIC_DIR, name), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:12]


@app.get("/", include_in_schema=False)
async def serve_gui() -> HTMLResponse:
    """Serve the single-page browser GUI (asset links carry a content hash)."""
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as fh:
        html = fh.read().replace("__VERSION__", _asset_stamp())
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.get("/simulate", include_in_schema=False)
async def redirect_old_simulate_page() -> RedirectResponse:
    """The former separate simulation page now lives at ``/``."""
    return RedirectResponse(url="/", status_code=307)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _list_available_elements() -> List[Dict[str, Any]]:
    """Return metadata for every element available in the CXRO database."""
    cxro = get_cxro_table()
    elements: List[Dict[str, Any]] = []
    for symbol in sorted(_ELEMENT_TABLE):
        if cxro.has_element(symbol):
            z, mass, density = _ELEMENT_TABLE[symbol]
            elements.append(
                {
                    "symbol": symbol,
                    "z": z,
                    "atomic_mass_g_mol": mass,
                    "density_g_cm3": density,
                }
            )
    return elements


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Return service status and version."""
    return HealthResponse(status="ok", version=__version__)


@app.get("/presets", response_model=PresetListResponse, tags=["simulation"])
async def list_presets() -> PresetListResponse:
    """Named starting configurations (defaults and the two anchors) with provenance."""
    return PresetListResponse(
        presets=[
            PresetInfo(
                key=p.key,
                label=p.label,
                summary=p.summary,
                provenance=p.provenance,
                config=config_as_dict(p.factory()),
            )
            for p in PRESETS.values()
        ]
    )


@app.get("/fields", response_model=FieldCatalogueResponse, tags=["simulation"])
async def list_fields() -> FieldCatalogueResponse:
    """Every ``SimulationConfig`` field with type, default, group, label and help."""
    return FieldCatalogueResponse(groups=GROUPS, fields=field_catalogue())  # type: ignore[arg-type]


def _resolve_or_422(preset: Optional[str], overrides_model: Any) -> tuple[str, SimulationConfig]:
    """Preset + overrides -> validated SimulationConfig, or HTTP 422."""
    preset_key = preset or "default"
    if preset_key not in PRESETS:
        raise HTTPException(status_code=422, detail=f"unknown preset '{preset_key}'")
    overrides = cast(BaseModel, overrides_model).model_dump(exclude_unset=True)
    try:
        cfg = resolve_config(preset_key, overrides)
    except ValueError as exc:  # the dataclass's own __post_init__ checks
        raise HTTPException(status_code=422, detail=str(exc))
    errors = physics_errors(cfg)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    return preset_key, cfg


@app.post("/simulate", response_model=SimulationResponse, tags=["simulation"])
def run_simulation(req: SimulationRequest) -> SimulationResponse:
    """Execute a full EUV lithography simulation pipeline (blocking call).

    Starts from ``preset`` (default: the pipeline defaults), applies the
    ``config`` overrides, checks the physical constraints and runs:
    1. Mask diffraction (thin mask by default, RCWA optional)
    2. Aerial image formation (Abbe imaging)
    3. Resist: intensity threshold, or Dill exposure + PEB + development
    4. CD extraction + NILS (+ LER/LWR with photon shot noise enabled)

    Sync endpoint: FastAPI executes it in the threadpool (see module docstring).
    For long runs use ``POST /jobs`` and poll.
    """
    preset_key, cfg = _resolve_or_422(req.preset, req.config)
    try:
        result = run_pipeline(cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return SimulationResponse(**simulation_payload(cfg, result, preset_key))


# ──────────────────────────────────────────────
# Background jobs
# ──────────────────────────────────────────────


@app.post("/jobs", response_model=JobStatus, status_code=202, tags=["jobs"])
async def start_job(req: JobRequest) -> JobStatus:
    """Start a background job and return its status (poll ``GET /jobs/{id}``).

    ``kind``: ``simulate`` (one run; progress per stochastic realisation),
    ``process_window`` (CD over the dose × focus grid in ``process_window``),
    ``bands`` (``euv calibrate --bands`` on the resolved configuration).
    """
    preset_key, cfg = _resolve_or_422(req.preset, req.config)
    request = req.model_dump(exclude_unset=True)
    if req.kind == "simulate":
        task = simulate_task(cfg, preset_key)
    elif req.kind == "process_window":
        p = req.process_window
        doses = [
            p.dose_start + (p.dose_end - p.dose_start) * i / (p.dose_steps - 1)
            for i in range(p.dose_steps)
        ]
        focuses = [
            p.focus_start + (p.focus_end - p.focus_start) * i / (p.focus_steps - 1)
            for i in range(p.focus_steps)
        ]
        task = process_window_task(
            cfg, preset_key, doses=doses, focuses=focuses, tolerance=p.tolerance
        )
    elif req.kind == "bands":
        if cfg.resist_model != "full_chem":
            raise HTTPException(status_code=422, detail="bands need resist_model = full_chem")
        b = req.bands
        task = bands_task(
            cfg, preset_key, rows=b.rows, seeds=b.seeds, dose_lo=b.dose_lo, dose_hi=b.dose_hi
        )
    else:
        raise HTTPException(status_code=422, detail=f"unknown job kind '{req.kind}'")
    job = REGISTRY.submit(req.kind, request, task)
    return JobStatus(**job.snapshot())


@app.get("/jobs", response_model=JobListResponse, tags=["jobs"])
async def list_jobs() -> JobListResponse:
    """All jobs of this server process, oldest first (results omitted)."""
    return JobListResponse(
        jobs=[JobStatus(**{**j.snapshot(), "result": None, "partial": {}}) for j in REGISTRY.list()]
    )


@app.get("/jobs/{job_id}", response_model=JobStatus, tags=["jobs"])
async def get_job(job_id: str) -> JobStatus:
    """Status, progress, partial and (when done) final result of a job."""
    job = REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such job")
    return JobStatus(**job.snapshot())


@app.delete("/jobs/{job_id}", response_model=JobStatus, tags=["jobs"])
async def cancel_job(job_id: str) -> JobStatus:
    """Ask a job to stop; it ends at the next realisation / grid cell."""
    job = REGISTRY.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such job")
    return JobStatus(**job.snapshot())


@app.get("/jobs/{job_id}/export.csv", response_class=PlainTextResponse, tags=["jobs"])
async def export_job_csv(job_id: str) -> PlainTextResponse:
    """CSV of a finished job: profiles (simulate), CD matrix (process_window)
    or the corner values (bands). Line 1 names the preset and the kind.
    """
    job = REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such job")
    if job.status != "done" or job.result is None:
        raise HTTPException(status_code=409, detail=f"job is {job.status}")
    text = _job_csv(job.kind, job.result)
    return PlainTextResponse(
        text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="euvsimulator_{job.kind}_{job_id}.csv"'
        },
    )


def _job_csv(kind: str, r: Dict[str, Any]) -> str:
    lines = [f"# euvsimulator {__version__}, kind={kind}, preset={r.get('preset')}"]
    if kind == "simulate":
        raw = r["raw"]
        period = r["config"]["period_nm"]
        n = len(raw["aerial_profile_nm"])
        for m in r["results"]:
            lines.append(f"# {m['metric']} = {m['value']} {m['unit']}".rstrip())
        lines.append("position_nm,local_dose_mj_cm2,developed")
        for i, (a, d) in enumerate(zip(raw["aerial_profile_nm"], raw["resist_profile"])):
            x = -period / 2 + period * i / (n - 1)
            lines.append(f"{x:.4f},{a:.6g},{d:g}")
    elif kind == "process_window":
        lines.append(
            f"# target_cd_nm = {r['target_cd_nm']}, tolerance = {r['tolerance']}, "
            f"depth_of_focus_nm = {r['depth_of_focus_nm']}, "
            f"exposure_latitude_pct = {r['exposure_latitude_pct']}"
        )
        lines.append("focus_nm\\dose_mj_cm2," + ",".join(f"{d:g}" for d in r["doses"]))
        for j, f in enumerate(r["focuses"]):
            row = [r["cd_matrix"][i][j] for i in range(len(r["doses"]))]
            lines.append(f"{f:g}," + ",".join("" if v is None else f"{v:.4f}" for v in row))
    else:  # bands
        lines.append("quantity,corner,value")
        for k, v in r["dose_to_size_mj_cm2"].items():
            lines.append(f"dose_to_size_mj_cm2,{k},{v}")
        for k, v in r["lwr_3sigma_nm_at_analytical_d2s"].items():
            lines.append(f"lwr_3sigma_nm,{k},{v}")
    return "\n".join(lines) + "\n"


@app.post("/estimate", response_model=EstimateResponse, tags=["jobs"])
async def estimate_endpoint(req: EstimateRequest) -> EstimateResponse:
    """Peak-memory estimate of one run of this configuration (no size limits,
    just the number, ±30 %; see api/estimate.py).
    """
    preset_key = req.preset or "default"
    if preset_key not in PRESETS:
        raise HTTPException(status_code=422, detail=f"unknown preset '{preset_key}'")
    overrides = cast(BaseModel, req.config).model_dump(exclude_unset=True)
    try:
        cfg = resolve_config(preset_key, overrides)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return EstimateResponse(**estimate_run(cfg), physics_errors=physics_errors(cfg))


@app.get("/materials", response_model=MaterialListResponse, tags=["materials"])
async def list_materials() -> MaterialListResponse:
    """Return all elements for which CXRO optical-constants data is available.

    The CXRO database covers atomic scattering factors f₁, f₂ for Z = 1–92.
    Run ``scripts/download_cxro.py`` to populate the data directory.
    """
    raw = _list_available_elements()
    return MaterialListResponse(
        count=len(raw),
        elements=[MaterialElement(**e) for e in raw],
    )


@app.post("/materials/nk", response_model=NkResponse, tags=["materials"])
async def refractive_index(req: NkRequest) -> NkResponse:
    """Compute the complex refractive index *n* + i*k for an element.

    Uses CXRO/Henke atomic scattering factors f₁, f₂ and the standard
    density for the element (or a user-supplied override).

    Raises ``404`` if the element is not in the CXRO database (CSV not
    downloaded) and ``422`` if the energy falls outside the tabulated range.
    """
    cxro = get_cxro_table()

    # Check the element exists in our table
    if req.symbol not in _ELEMENT_TABLE:
        raise HTTPException(
            status_code=404,
            detail=f"Element '{req.symbol}' not found in the element table (Z = 1–92).",
        )

    # Check CXRO data exists
    if not cxro.has_element(req.symbol):
        raise HTTPException(
            status_code=404,
            detail=(
                f"CXRO data for '{req.symbol}' is not available. "
                f"Run ``python scripts/download_cxro.py`` first."
            ),
        )

    try:
        mat = cxro.get_material(symbol=req.symbol, energy_eV=req.energy_eV)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # If density override is given, recompute n,k with that density
    if req.density_g_cm3 is not None:
        n, k = cxro.refractive_index(
            symbol=req.symbol,
            energy_eV=req.energy_eV,
            density_g_cm3=req.density_g_cm3,
        )
    else:
        n, k = mat.n, mat.k

    eps = complex(n, k) ** 2

    return NkResponse(
        symbol=req.symbol,
        energy_eV=req.energy_eV,
        wavelength_nm=mat.wavelength_nm,
        n=n,
        k=k,
        delta=1.0 - n,
        density=req.density_g_cm3 if req.density_g_cm3 is not None else mat.density,
        absorption_length_nm=(
            mat.wavelength_nm / (4.0 * 3.141592653589793 * k) if k > 0 else float("inf")
        ),
        epsilon_real=eps.real,
        epsilon_imag=eps.imag,
    )


# ──────────────────────────────────────────────
# Direct entry
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("euvsimulator.api.main:app", host="127.0.0.1", port=8000, log_level="info")
