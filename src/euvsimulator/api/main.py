"""FastAPI application for the euvsimulator REST API.

Endpoints
---------
- ``GET  /``                — Browser GUI (single page, no external assets)
- ``GET  /health``          — Service health check
- ``GET  /presets``         — Named starting configurations with provenance
- ``GET  /fields``          — Every SimulationConfig field with group, label, help
- ``POST /simulate``        — Run a full simulation pipeline (preset + overrides)
- ``GET  /materials``       — List available materials in the CXRO database
- ``POST /materials/nk``    — Retrieve refractive index for a given element/energy

``POST /simulate`` is a plain ``def`` endpoint on purpose: FastAPI runs it in
its threadpool, so a long pipeline run does not block the event loop and the
GUI's health polling keeps working while a simulation is computing.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from euvsimulator import __version__
from euvsimulator.api.fields import (
    GROUPS,
    PRESETS,
    config_as_dict,
    field_catalogue,
    physics_errors,
    resolve_config,
)
from euvsimulator.api.schemas import (
    FieldCatalogueResponse,
    HealthResponse,
    MaterialElement,
    MaterialListResponse,
    NkRequest,
    NkResponse,
    PresetInfo,
    PresetListResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationResult,
)
from euvsimulator.materials import _ELEMENT_TABLE, get_cxro_table
from euvsimulator.pipeline import AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2
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


@app.post("/simulate", response_model=SimulationResponse, tags=["simulation"])
def run_simulation(req: SimulationRequest) -> SimulationResponse:
    """Execute a full EUV lithography simulation pipeline.

    Starts from ``preset`` (default: the pipeline defaults), applies the
    ``config`` overrides, checks the physical constraints and runs:
    1. Mask diffraction (thin mask by default, RCWA optional)
    2. Aerial image formation (Abbe imaging)
    3. Resist: intensity threshold, or Dill exposure + PEB + development
    4. CD extraction + NILS (+ LER/LWR with photon shot noise enabled)

    Sync endpoint: FastAPI executes it in the threadpool (see module docstring).
    """
    preset_key = req.preset or "default"
    if preset_key not in PRESETS:
        raise HTTPException(status_code=422, detail=f"unknown preset '{preset_key}'")
    overrides = cast(BaseModel, req.config).model_dump(exclude_unset=True)
    try:
        cfg = resolve_config(preset_key, overrides)
    except ValueError as exc:  # the dataclass's own __post_init__ checks
        raise HTTPException(status_code=422, detail=str(exc))
    errors = physics_errors(cfg)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    try:
        result = run_pipeline(cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    aerial = result.aerial_image
    centre = aerial.shape[0] // 2
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
    if cfg.enable_stochastic:
        results.append(
            SimulationResult(stage="resist", metric="ler_1sigma", value=result.ler_nm, unit="nm")
        )
        results.append(
            SimulationResult(stage="resist", metric="lwr_1sigma", value=result.lwr_nm, unit="nm")
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
        notes.append(
            "LER/LWR are 1σ of the simulated edge/width; no SEM bias is added (measured values "
            "from CD-SEM carry one, e.g. imec biased/unbiased ≈ 1.66)."
        )

    return SimulationResponse(
        status="completed",
        preset=preset_key,
        config=config_as_dict(cfg),
        results=results,
        raw=raw,
        notes=notes,
    )


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
