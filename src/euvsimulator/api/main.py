"""FastAPI application for the euvsimulator REST API.

Endpoints
---------
- ``GET  /``                — Browser GUI (single page, no external assets)
- ``GET  /health``          — Service health check
- ``POST /simulate``        — Run a full simulation pipeline
- ``GET  /materials``       — List available materials in the CXRO database
- ``POST /materials/nk``    — Retrieve refractive index for a given element/energy

``POST /simulate`` is a plain ``def`` endpoint on purpose: FastAPI runs it in
its threadpool, so a long pipeline run does not block the event loop and the
GUI's health polling keeps working while a simulation is computing.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from euvsimulator import __version__
from euvsimulator.api.schemas import (
    HealthResponse,
    MaterialElement,
    MaterialListResponse,
    NkRequest,
    NkResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationResult,
)
from euvsimulator.api.schemas import SimulationConfig as SimulationConfigSchema
from euvsimulator.materials import _ELEMENT_TABLE, get_cxro_table
from euvsimulator.pipeline import AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2
from euvsimulator.pipeline import SimulationConfig as PipelineConfig
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


@app.get("/", include_in_schema=False)
async def serve_gui() -> HTMLResponse:
    """Serve the single-page browser GUI.

    The asset links carry the package version as a query string so a browser
    never pairs a new page with a cached old stylesheet or script.
    """
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as fh:
        html = fh.read().replace("__VERSION__", __version__)
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


def pipeline_config_from_request(cfg_api: SimulationConfigSchema) -> PipelineConfig:
    """Map the API schema onto ``pipeline.SimulationConfig`` (one field each, nothing dropped)."""
    return PipelineConfig(
        na=cfg_api.aerial.na,
        sigma=cfg_api.aerial.illumination_sigma,
        illumination_shape=cfg_api.aerial.illumination_shape,
        sigma_inner=cfg_api.aerial.inner_sigma,
        pole_opening_deg=cfg_api.aerial.pole_opening_deg,
        focus_nm=cfg_api.aerial.focus_nm,
        period_nm=cfg_api.mask.pitch_nm,
        line_width_nm=cfg_api.mask.cd_nm,
        absorber_material=cfg_api.mask.absorber_material,
        absorber_height_nm=cfg_api.mask.absorber_height_nm,
        ml_n_bilayers=cfg_api.mask.multilayer_pairs,
        ml_d_mo_nm=cfg_api.mask.ml_d_mo_nm,
        ml_d_si_nm=cfg_api.mask.ml_d_si_nm,
        ml_gamma=cfg_api.mask.ml_gamma,
        ml_grading_linear_nm=cfg_api.mask.ml_grading_linear_nm,
        ml_grading_parabolic_nm=cfg_api.mask.ml_grading_parabolic_nm,
        ml_roughness_nm=cfg_api.mask.ml_roughness_nm,
        ml_capping=cfg_api.mask.capping_material,
        ml_capping_nm=cfg_api.mask.capping_height_nm,
        dose_mj_cm2=cfg_api.resist.dose_mJ_cm2,
        resist_model=cfg_api.resist.resist_model,
        resist_threshold_norm=cfg_api.resist.threshold_norm,
        resist_thickness_nm=cfg_api.resist.thickness_nm,
        develop_time_s=cfg_api.resist.development_time_s,
    )


@app.post("/simulate", response_model=SimulationResponse, tags=["simulation"])
def run_simulation(req: SimulationRequest) -> SimulationResponse:
    """Execute a full EUV lithography simulation pipeline.

    The simulation proceeds through:
    1. Mask diffraction (thin mask by default, RCWA optional in the pipeline)
    2. Aerial image formation (Abbe imaging)
    3. Resist: intensity threshold, or Dill exposure + PEB + development
    4. CD extraction + NILS computation

    Sync endpoint: FastAPI executes it in the threadpool (see module docstring).
    """
    cfg_api = req.config
    pipe_cfg = pipeline_config_from_request(cfg_api)

    try:
        result = run_pipeline(pipe_cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    aerial = result.aerial_image
    centre = aerial.shape[0] // 2
    aerial_profile = aerial[centre, :].tolist()
    resist_profile = result.resist_profile[centre, :].tolist()
    i_max = float(aerial.max())
    i_min = float(aerial.min())

    results: List[SimulationResult] = [
        SimulationResult(stage="aerial", metric="nils", value=result.nils_value, unit=""),
        SimulationResult(stage="resist", metric="cd", value=result.cd_nm, unit="nm"),
        SimulationResult(
            stage="aerial",
            metric="contrast",
            value=(i_max - i_min) / (i_max + i_min + 1e-12) * 100,
            unit="%",
        ),
    ]

    raw: Dict[str, Any] = {
        "aerial_profile_nm": aerial_profile,
        "aerial_shape": list(aerial.shape),
        # 1 = developed (dissolved through the film), 0 = resist remaining
        "resist_profile": resist_profile,
        "absorber_reflectivity": result.absorber_reflectivity,
        "grid": pipe_cfg.grid,
    }
    if pipe_cfg.resist_model == "aerial_threshold":
        # Same expression as pipeline._cd_via_aerial_threshold, so the plotted
        # threshold line is the one the CD was actually extracted at.
        raw["threshold_intensity"] = (
            pipe_cfg.resist_threshold_norm
            * float(aerial.mean())
            * (AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2 / max(pipe_cfg.dose_mj_cm2, 1e-9))
        )

    return SimulationResponse(status="completed", config=cfg_api, results=results, raw=raw)


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

    uvicorn.run("euvsimulator.api.main:app", host="0.0.0.0", port=8000, log_level="info")
