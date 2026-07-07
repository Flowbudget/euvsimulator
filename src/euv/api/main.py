"""
FastAPI application for the OpEnUV REST API.

Endpoints
---------
- ``GET  /health``          — Service health check
- ``POST /simulate``        — Run a full simulation pipeline
- ``GET  /materials``       — List available materials in the CXRO database
- ``POST /materials/nk``    — Retrieve refractive index for a given element/energy
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from euv import __version__
from euv.api.schemas import (
    HealthResponse,
    MaterialElement,
    MaterialListResponse,
    NkRequest,
    NkResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationResult,
)
from euv.materials import _ELEMENT_TABLE, get_cxro_table

# ──────────────────────────────────────────────
# App instance
# ──────────────────────────────────────────────

app = FastAPI(
    title="OpEnUV — Open Source EUV Lithography Simulator",
    description="REST API for simulating EUV lithography at 13.5 nm.",
    version=__version__,
    license_info={"name": "Apache-2.0"},
)


# ──────────────────────────────────────────────
# Static files (Web UI dashboard)
# ──────────────────────────────────────────────

import os as _os

STATIC_DIR = _os.path.join(_os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard() -> FileResponse:
    """Serve the OpEnUV web dashboard."""
    return FileResponse(_os.path.join(STATIC_DIR, "index.html"), media_type="text/html")


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


@app.post("/simulate", response_model=SimulationResponse, tags=["simulation"])
async def run_simulation(req: SimulationRequest) -> SimulationResponse:
    """Execute a full EUV lithography simulation pipeline.

    The simulation proceeds through:
    1. Aerial image formation (Abbe/Hopkins imaging)
    2. Mask-3D RCWA diffraction
    3. Resist exposure and development (CAR or MOR)

    .. note::

        The full pipeline integration is planned for Sprint 6; this endpoint
        currently returns validated configuration and placeholder metrics.
    """
    cfg = req.config

    # ── Placeholder: real pipeline will wire up aerial → mask → resist ── #
    # For now, return the validated config and a stub result.
    results: List[SimulationResult] = [
        SimulationResult(
            stage="aerial",
            metric="nils",
            value=2.15,
            unit="1",
        ),
        SimulationResult(
            stage="resist",
            metric="cd",
            value=cfg.mask.cd_nm,
            unit="nm",
        ),
    ]

    return SimulationResponse(
        status="completed",
        config=cfg,
        results=results,
        raw=None,
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
        absorption_length_nm=mat.wavelength_nm / (4.0 * 3.141592653589793 * k) if k > 0 else float("inf"),
        epsilon_real=eps.real,
        epsilon_imag=eps.imag,
    )


# ──────────────────────────────────────────────
# Direct entry
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("euv.api.main:app", host="0.0.0.0", port=8000, log_level="info")