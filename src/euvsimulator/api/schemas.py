"""Pydantic v2 schemas for the euvsimulator REST API.

Defines request/response models for all endpoints, relying on the
established project types in ``euvsimulator.materials`` and ``euvsimulator.constants``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from euvsimulator.api.fields import PipelineOverrides

# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response from ``GET /health``."""

    status: str = Field("ok", description="Service status")
    version: str = Field(..., description="euvsimulator version string")


# ──────────────────────────────────────────────
# Simulation
# ──────────────────────────────────────────────


class SimulationRequest(BaseModel):
    """Request body for ``POST /simulate``.

    ``preset`` names a starting configuration (``GET /presets``); ``config``
    holds any subset of ``pipeline.SimulationConfig`` fields to override
    (``GET /fields`` lists them). Unknown field names are rejected.
    """

    preset: Optional[str] = Field(
        None, description="Preset key from GET /presets; None = the pipeline defaults"
    )
    config: PipelineOverrides = Field(  # type: ignore[valid-type]
        default_factory=PipelineOverrides,
        description="SimulationConfig field overrides (only the fields given are changed)",
    )


class SimulationResult(BaseModel):
    """Individual result from a simulation output stage."""

    stage: str = Field(..., description="Pipeline stage name (e.g. aerial, resist)")
    metric: str = Field(..., description="Metric name (e.g. nils, cd, lwr)")
    value: float = Field(..., description="Computed value")
    unit: str = Field(..., description="Unit of the value")


class SimulationResponse(BaseModel):
    """Response from ``POST /simulate``."""

    status: str = Field("completed", description="Simulation status")
    preset: str = Field(..., description="Preset the run started from")
    config: Dict[str, Any] = Field(..., description="The full resolved SimulationConfig")
    results: List[SimulationResult] = Field(
        default_factory=list, description="Pipeline output metrics"
    )
    raw: Optional[Dict[str, Any]] = Field(None, description="Profiles and auxiliary data")
    notes: List[str] = Field(default_factory=list, description="Provenance and caveats")


# ──────────────────────────────────────────────
# Presets and field catalogue
# ──────────────────────────────────────────────


class PresetInfo(BaseModel):
    """One named starting configuration."""

    key: str
    label: str
    summary: str
    provenance: str
    config: Dict[str, Any] = Field(..., description="The preset's full SimulationConfig")


class PresetListResponse(BaseModel):
    """Response from ``GET /presets``."""

    presets: List[PresetInfo]


class FieldInfo(BaseModel):
    """One SimulationConfig field as the GUI renders it."""

    name: str
    type: str = Field(..., description="float, int, bool, str or pair")
    nullable: bool
    default: Any = None
    group: str
    label: str
    unit: str
    help: str
    choices: Optional[List[str]] = None
    head: bool = Field(..., description="Shown open at the top of the GUI")


class FieldCatalogueResponse(BaseModel):
    """Response from ``GET /fields``."""

    groups: Dict[str, str] = Field(..., description="Group key -> display title, in order")
    fields: List[FieldInfo]


# ──────────────────────────────────────────────
# Materials
# ──────────────────────────────────────────────


class MaterialElement(BaseModel):
    """Lightweight descriptor of an element available in the CXRO database."""

    symbol: str = Field(..., description="Chemical symbol (e.g. Mo, Si)")
    z: int = Field(..., description="Atomic number")
    atomic_mass_g_mol: float = Field(..., description="Atomic mass [g/mol]")
    density_g_cm3: float = Field(..., description="Standard density [g/cm³]")


class MaterialListResponse(BaseModel):
    """Response from ``GET /materials``."""

    count: int = Field(..., description="Number of available materials")
    elements: List[MaterialElement] = Field(..., description="Available elements with CXRO data")


class NkRequest(BaseModel):
    """Request body for ``POST /materials/nk``."""

    symbol: str = Field(
        ..., min_length=1, max_length=4, description="Chemical symbol (e.g. Mo, Si)"
    )
    energy_eV: float = Field(
        91.84,
        gt=0,
        description=(
            "Photon energy [eV]. Default is 91.84 eV (corresponding to 13.5 nm wavelength via E ="
            " hc/λ)."
        ),
    )
    density_g_cm3: Optional[float] = Field(
        None, gt=0, description="Override density [g/cm³]; uses standard if omitted"
    )


class NkResponse(BaseModel):
    """Response from ``POST /materials/nk`` — refractive-index result."""

    symbol: str = Field(..., description="Chemical symbol")
    energy_eV: float = Field(..., description="Photon energy [eV]")
    wavelength_nm: float = Field(..., description="Corresponding wavelength [nm]")
    n: float = Field(..., description="Real part of refractive index")
    k: float = Field(..., description="Imaginary part (extinction coefficient)")
    delta: float = Field(..., description="Refractive index decrement δ = 1 − n")
    density: float = Field(..., description="Density used for the calculation [g/cm³]")
    absorption_length_nm: float = Field(..., description="1/e absorption length [nm]")
    epsilon_real: float = Field(..., description="Real part of complex permittivity ε = (n + ik)²")
    epsilon_imag: float = Field(..., description="Imaginary part of complex permittivity")
