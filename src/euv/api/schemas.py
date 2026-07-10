"""Pydantic v2 schemas for the OpEnUV REST API.

Defines request/response models for all endpoints, relying on the
established project types in ``euv.materials`` and ``euv.constants``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response from ``GET /health``."""

    status: str = Field("ok", description="Service status")
    version: str = Field(..., description="OpEnUV version string")


# ──────────────────────────────────────────────
# Simulation
# ──────────────────────────────────────────────


class AerialImageConfig(BaseModel):
    """Parameters for aerial-image formation."""

    na: float = Field(0.33, ge=0.1, le=0.7, description="Numerical aperture")
    reduction_ratio: str = Field("4x", description="Projection reduction (4x or 8x)")
    illumination_sigma: float = Field(0.8, ge=0.0, le=1.0, description="Coherence factor σ")
    illumination_shape: str = Field(
        "conventional", description="Source shape (conventional, annular, dipole, quasar)"
    )
    inner_sigma: Optional[float] = Field(None, ge=0.0, le=1.0, description="Annular inner σ")
    outer_sigma: Optional[float] = Field(None, ge=0.0, le=1.0, description="Annular outer σ")
    zernike_coeffs: Optional[List[float]] = Field(
        None, description="Fringe Zernike coefficients (Noll-indexed)"
    )
    focus_nm: float = Field(0.0, ge=-500, le=500, description="Defocus [nm]")


class MaskConfig(BaseModel):
    """Parameters for the reflective EUV mask and multilayer mirror."""

    layout: str = Field(
        "linespace", description="Layout type: linespace, contact_array, or gds_path"
    )
    pitch_nm: float = Field(40.0, gt=0, description="Feature pitch [nm]")
    cd_nm: float = Field(18.0, gt=0, description="Critical dimension [nm]")
    absorber_material: str = Field("Ta", description="Absorber element symbol")
    absorber_height_nm: float = Field(50.0, gt=0, description="Absorber height [nm]")
    capping_material: str = Field("Ru", description="Capping layer element symbol")
    capping_height_nm: float = Field(2.5, gt=0, description="Capping layer height [nm]")
    multilayer_pairs: int = Field(40, ge=1, description="Number of Mo/Si bilayer pairs")
    gds_path: Optional[str] = Field(None, description="Path to GDSII file (when layout=gds_path)")
    # Multilayer parameters
    ml_d_mo_nm: float = Field(2.8, gt=0, description="Mo layer thickness [nm]")
    ml_d_si_nm: float = Field(4.1, gt=0, description="Si layer thickness [nm]")
    ml_gamma: Optional[float] = Field(
        None, ge=0.2, le=0.6, description="Mo fraction gamma = d_Mo/(d_Mo+d_Si)"
    )
    ml_grading_linear_nm: float = Field(0.0, ge=0, description="Linear period grading [nm]")
    ml_grading_parabolic_nm: float = Field(0.0, ge=0, description="Parabolic period grading [nm]")
    ml_roughness_nm: float = Field(0.0, ge=0, description="RMS interface roughness [nm]")


class ResistConfig(BaseModel):
    """Parameters for the resist model."""

    resist_type: str = Field("CAR", description="Resist type: CAR or MOR")
    thickness_nm: float = Field(30.0, gt=0, description="Resist thickness [nm]")
    acid_diffusion_length_nm: float = Field(
        5.0, ge=0, description="Acid diffusion length (CAR) [nm]"
    )
    development_time_s: float = Field(30.0, gt=0, description="Development time [s]")
    dose_mJ_cm2: float = Field(20.0, gt=0, description="Exposure dose [mJ/cm²]")
    resist_model: str = Field(
        "aerial_threshold",
        description="Resist model: 'aerial_threshold' (fast, robust) or 'full_chem' (Dill + PEB + develop)",
    )
    threshold_norm: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Normalised intensity threshold for aerial_threshold model (0-1 fraction of max)",
    )


class SimulationConfig(BaseModel):
    """Top-level simulation configuration."""

    aerial: AerialImageConfig = Field(default_factory=AerialImageConfig)
    mask: MaskConfig = Field(default_factory=MaskConfig)
    resist: ResistConfig = Field(default_factory=ResistConfig)


class SimulationRequest(BaseModel):
    """Request body for ``POST /simulate``."""

    config: SimulationConfig = Field(
        default_factory=SimulationConfig, description="Full simulation configuration"
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
    config: SimulationConfig = Field(..., description="Config used for the simulation")
    results: List[SimulationResult] = Field(
        default_factory=list, description="Pipeline output metrics"
    )
    raw: Optional[Dict[str, Any]] = Field(None, description="Optional raw output data")


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
    energy_eV: float = Field(91.84, gt=0, description="Photon energy [eV]")
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
