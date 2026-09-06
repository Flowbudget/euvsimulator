"""Field catalogue, request model and presets for the REST API / browser GUI.

The API exposes ``pipeline.SimulationConfig`` field by field, with no second
schema to drift from it:

- :data:`FIELDS` documents every dataclass field (group, label, unit, help,
  choices) -- ``tests/test_api_fields.py`` asserts the two sets are identical.
- :func:`overrides_model` builds the pydantic request model from the dataclass
  itself (types and defaults come from ``dataclasses.fields``).
- :func:`physics_errors` lists the physical constraints a resolved config
  violates; there are no cosmetic limits (grid, rows, seeds are unbounded).
- :data:`PRESETS` are the named starting points (default resist and the two
  anchors), each with an honest provenance text.
"""

from __future__ import annotations

import dataclasses
import typing
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, create_model

from euvsimulator.pipeline import SimulationConfig
from euvsimulator.presets import (
    NXE1716_DOSE_SCALE_CALIBRATION,
    met2d_config,
    nxe1716_config,
)

# ──────────────────────────────────────────────
# Groups (display order) and head fields
# ──────────────────────────────────────────────

GROUPS: Dict[str, str] = {
    "optics": "Optics and source",
    "mask": "Mask",
    "multilayer": "Multilayer mirror",
    "exposure": "Resist exposure (Dill)",
    "peb": "Post-exposure bake",
    "development": "Development (Mack)",
    "stochastic": "Stochastics and roughness",
    "numerics": "Numerics",
}

# Shown open at the top of the GUI; everything else sits in its collapsed group.
HEAD_FIELDS = (
    "period_nm",
    "line_width_nm",
    "na",
    "illumination_shape",
    "dose_mj_cm2",
    "resist_model",
)


def _f(
    group: str,
    label: str,
    help: str,
    unit: str = "",
    choices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {"group": group, "label": label, "unit": unit, "help": help, "choices": choices}


# Every SimulationConfig field; texts follow the CLI help and the dataclass notes.
FIELDS: Dict[str, Dict[str, Any]] = {
    # optics
    "wavelength_nm": _f("optics", "Wavelength", "EUV wavelength", "nm"),
    "na": _f(
        "optics",
        "NA",
        "Numerical aperture, 0 < NA < 1; isomorphic pupil (the anamorphic "
        "high-NA pupil in aerial/pupil.py is not wired into the pipeline)",
    ),
    "sigma": _f(
        "optics",
        "Outer σ",
        "Partial-coherence factor of the source (outer radius, source inside the pupil)",
    ),
    "illumination_shape": _f(
        "optics",
        "Illumination",
        "Source shape; dipole/quasar with an inner σ become the "
        "scanner-style annular sectors (e.g. imec dipole 90X: σ 0.62/0.90, 90°)",
        choices=["conventional", "annular", "dipole", "dipole_y", "quasar"],
    ),
    "sigma_inner": _f(
        "optics",
        "Inner σ",
        "Inner radius for annular and scanner-style multipole "
        "sources (< outer σ); empty = the built-in geometry of the shape",
    ),
    "pole_opening_deg": _f(
        "optics",
        "Pole opening",
        "Opening angle of each pole for dipole/quasar with an inner σ; empty = 90",
        "°",
    ),
    "focus_nm": _f("optics", "Defocus", "Defocus at the wafer", "nm"),
    # mask
    "period_nm": _f("mask", "Pitch", "Line/space period at the wafer", "nm"),
    "line_width_nm": _f(
        "mask",
        "Line width",
        "Target line width (must be smaller than the pitch); the CD is measured against it",
        "nm",
    ),
    "absorber_material": _f(
        "mask", "Absorber", "Absorber element symbol (any element with CXRO data)"
    ),
    "absorber_height_nm": _f("mask", "Absorber height", "Absorber thickness", "nm"),
    "absorber_taper_deg": _f(
        "mask",
        "Sidewall angle",
        "Absorber sidewall angle from horizontal (90 = vertical); RCWA path",
        "°",
    ),
    "mask_undercut_nm": _f(
        "mask", "Undercut", "Absorber undercut at the multilayer interface; RCWA path", "nm"
    ),
    "mask_demagnification": _f(
        "mask",
        "Demagnification",
        "Projection demagnification of the "
        "RCWA path (4 = NXE/EXE isotropic); the thin-mask path is "
        "scale-free",
    ),
    "use_rcwa": _f(
        "mask",
        "Rigorous mask (RCWA)",
        "Full RCWA mask diffraction instead of the thin-mask analytic model (slower)",
    ),
    # multilayer
    "ml_n_bilayers": _f("multilayer", "Mo/Si bilayers", "Number of Mo/Si bilayer pairs"),
    "ml_d_mo_nm": _f("multilayer", "Mo thickness", "Mo layer thickness", "nm"),
    "ml_d_si_nm": _f("multilayer", "Si thickness", "Si layer thickness", "nm"),
    "ml_gamma": _f(
        "multilayer", "Γ", "Mo fraction d_Mo/(d_Mo+d_Si); empty = use the two thicknesses"
    ),
    "ml_grading_linear_nm": _f(
        "multilayer", "Linear grading", "Linear period grading through the stack", "nm"
    ),
    "ml_grading_parabolic_nm": _f(
        "multilayer", "Parabolic grading", "Parabolic period grading through the stack", "nm"
    ),
    "ml_roughness_nm": _f(
        "multilayer", "Interface roughness", "RMS interface roughness (Névot–Croce damping)", "nm"
    ),
    "ml_capping": _f("multilayer", "Capping layer", "Capping layer element symbol"),
    "ml_capping_nm": _f("multilayer", "Capping thickness", "Capping layer thickness", "nm"),
    # exposure
    "dose_mj_cm2": _f(
        "exposure", "Dose", "Exposure dose at the wafer (clear-field convention)", "mJ/cm²"
    ),
    "resist_model": _f(
        "exposure",
        "Resist model",
        "aerial_threshold: intensity threshold on the image (fast); "
        "full_chem: Dill exposure + PEB + development",
        choices=["aerial_threshold", "full_chem"],
    ),
    "resist_threshold_norm": _f(
        "exposure",
        "Threshold",
        "aerial_threshold only: fraction of the clear-field mean at the 20 mJ/cm² reference dose",
    ),
    "dill_A": _f("exposure", "Dill A", "Bleachable absorption coefficient; EUV CARs: ≪ B", "1/µm"),
    "dill_B": _f(
        "exposure",
        "Dill B",
        "Non-bleachable absorption coefficient; default from the "
        "PHS/35 % tBOC composition via CXRO f2 (measured EUV CARs 4.3–5.2)",
        "1/µm",
    ),
    "dill_C": _f(
        "exposure",
        "Dill C",
        "Photo-rate constant, acid = G0·(1−exp(−C·E)); default = "
        "LBNL base titration for MET-2D; includes the PAG quantum efficiency",
        "cm²/mJ",
    ),
    "se_blur_nm": _f(
        "exposure",
        "Secondary-electron blur",
        "Gaussian σ of the electron blur "
        "(Thackeray 2010); 0 = none (white per-pixel photon noise, not "
        "recommended with stochastics)",
        "nm",
    ),
    "resist_thickness_nm": _f("exposure", "Film thickness", "Resist film thickness", "nm"),
    # peb
    "peb_model": _f(
        "peb",
        "PEB model",
        "analytical: diffuse → neutralise → deprotect with an acid lifetime; "
        "reaction_diffusion: concurrent PDE (Kang/NIST 2009) with acid trapping",
        choices=["analytical", "reaction_diffusion"],
    ),
    "peb_temperature_c": _f(
        "peb",
        "PEB temperature",
        "Sets k and the acid lifetime from "
        "Yamamoto 2011 Polymer A kinetics (80–140 °C); empty = use the "
        "explicit values below",
        "°C",
    ),
    "peb_t_bake": _f("peb", "Bake time", "PEB duration", "s"),
    "peb_k": _f(
        "peb",
        "Deprotection rate k",
        "Rate constant per unit relative acid at the PEB "
        "temperature (default from Yamamoto 2011 Fig. 3)",
        "1/s",
    ),
    "peb_acid_lifetime_s": _f(
        "peb",
        "Acid lifetime τ",
        "First-order acid loss during the bake (analytical model); empty = no loss",
        "s",
    ),
    "peb_D": _f(
        "peb", "Acid diffusivity", "Diffusion length √(2·D·t_eff); default Kang 2010", "nm²/s"
    ),
    "peb_sigma_diff": _f(
        "peb",
        "Diffusion σ (override)",
        "Sets the PEB blur directly and "
        "bypasses D and t; the MET-2D anchor uses the measured 10.1 nm",
        "nm",
    ),
    "peb_k_trap_per_s": _f(
        "peb",
        "Trapping rate",
        "reaction_diffusion only: acid trapping rate (fit of the NIST law to Yamamoto Fig. 3)",
        "1/s",
    ),
    "peb_D_quencher": _f(
        "peb", "Quencher diffusivity", "reaction_diffusion only; empty = same as the acid", "nm²/s"
    ),
    "pag_density_per_nm3": _f(
        "peb",
        "PAG density",
        "Initial photo-acid generator density (Mack, Biafore & Smith 2011)",
        "1/nm³",
    ),
    "quencher_density_per_nm3": _f(
        "peb",
        "Quencher density",
        "Initial base density; 0 = the quencher-free Yamamoto 2011 chemistry",
        "1/nm³",
    ),
    "acid_base_quench_rate_nm3_per_s": _f(
        "peb",
        "Quench rate k_Q",
        "Acid–base neutralisation rate constant (NIST bilayer: 1.0–1.5)",
        "nm³/s",
    ),
    # development
    "mack_R_max": _f("development", "R_max", "Maximum dissolution rate", "nm/s"),
    "mack_R_min": _f("development", "R_min", "Minimum dissolution rate", "nm/s"),
    "mack_n": _f("development", "n", "Dissolution selectivity (contrast), n > 1"),
    "mack_M_th": _f("development", "M_th", "Threshold inhibitor concentration (0–1)"),
    "develop_time_s": _f("development", "Development time", "Immersion time in the developer", "s"),
    "development_model": _f(
        "development",
        "Front model",
        "eikonal: isotropic first-arrival front per row (physical); "
        "eikonal3d: rows coupled (use with dissolution-cell noise, 8× cost); column: vertical "
        "time-of-flight approximation, no lateral development",
        choices=["eikonal", "eikonal3d", "column"],
    ),
    # stochastic
    "enable_stochastic": _f(
        "stochastic",
        "Photon shot noise",
        "Sample photon shot noise and extract LER/LWR (one run per realisation)",
    ),
    "stochastic_n_realisations": _f(
        "stochastic", "Realisations", "Independent noise realisations to average"
    ),
    "stochastic_seed": _f("stochastic", "Seed", "RNG seed; empty = random"),
    "stochastic_ler_grid_y": _f(
        "stochastic",
        "Rows along the line",
        "Length of the simulated line in grid rows (the y extent for the roughness statistics)",
    ),
    "stochastic_ler_estimator": _f(
        "stochastic",
        "LER estimator",
        "large_n: RMS edge position over all rows, reported "
        "with the effective number of independent rows n_eff and the correlation length; "
        "legacy: the earlier per-row estimator",
        choices=["large_n", "legacy"],
    ),
    "ler_passband_nm": _f(
        "stochastic",
        "Metrology passband",
        "[p_min, p_max] spatial periods "
        "kept before the roughness statistics; empty = full simulated band "
        "(Anderson 10–834, imec 10.8–5500)",
        "nm",
    ),
    "exposure_stochasticity": _f(
        "stochastic",
        "Discrete PAG/quencher",
        "Sample discrete PAG and quencher populations instead of mean-field acid",
    ),
    "development_stochasticity": _f(
        "stochastic",
        "Dissolution-cell noise",
        "Per-cell fluctuation of the blocked-site count (Rg-sized cells); stochastic chain only",
    ),
    "blocked_site_density_per_nm3": _f(
        "stochastic",
        "Blocked-site density",
        "Density of blocking groups for the cell noise",
        "1/nm³",
    ),
    "dissolution_cell_nm": _f(
        "stochastic",
        "Dissolution cell",
        "Cell edge for the noise above; 4.3 nm = polymer radius of gyration (Thackeray 2010)",
        "nm",
    ),
    # numerics
    "grid": _f(
        "numerics", "Grid", "Samples per period in x (and pupil grid); cost ∝ grid², unbounded"
    ),
    "n_rcwa_orders": _f("numerics", "RCWA orders", "Fourier orders of the RCWA mask solver"),
    "n_develop_layers": _f(
        "numerics",
        "Depth layers",
        "Layers through the film for the resolved "
        "exposure/PEB/development chain (numerical resolution)",
    ),
    "device": _f("numerics", "Device", "PyTorch device: auto, cpu or cuda"),
}


# ──────────────────────────────────────────────
# Request model generated from the dataclass
# ──────────────────────────────────────────────


def _dataclass_types() -> Dict[str, Any]:
    return typing.get_type_hints(SimulationConfig)


def overrides_model() -> type[BaseModel]:
    """Pydantic model with every ``SimulationConfig`` field optional (unset = keep preset)."""
    hints = _dataclass_types()
    spec: Dict[str, Any] = {}
    for f in dataclasses.fields(SimulationConfig):
        spec[f.name] = (Optional[hints[f.name]], None)
    return create_model("PipelineOverrides", __config__=ConfigDict(extra="forbid"), **spec)


PipelineOverrides = overrides_model()


def field_catalogue() -> List[Dict[str, Any]]:
    """Catalogue rows in dataclass order: name, type, default, group, label, unit, help, ..."""
    hints = _dataclass_types()
    rows: List[Dict[str, Any]] = []
    for f in dataclasses.fields(SimulationConfig):
        info = FIELDS[f.name]
        hint = hints[f.name]
        base = typing.get_args(hint) or (hint,)
        nullable = type(None) in base
        core = [t for t in base if t is not type(None)]
        if core and typing.get_origin(core[0]) is tuple:
            kind = "pair"
        else:
            kind = {float: "float", int: "int", bool: "bool", str: "str"}.get(core[0], "str")
        rows.append(
            {
                "name": f.name,
                "type": kind,
                "nullable": nullable,
                "default": f.default if f.default is not dataclasses.MISSING else None,
                "group": info["group"],
                "label": info["label"],
                "unit": info["unit"],
                "help": info["help"],
                "choices": info["choices"],
                "head": f.name in HEAD_FIELDS,
            }
        )
    return rows


# ──────────────────────────────────────────────
# Physical constraints (no cosmetic limits)
# ──────────────────────────────────────────────


def physics_errors(cfg: SimulationConfig) -> List[str]:
    """Physical constraints a resolved configuration violates (empty = fine).

    Only physics and the domain of the model equations are checked here;
    numerical size parameters (grid, rows, realisations) are unbounded.
    """
    e: List[str] = []

    def pos(name: str, strict: bool = True) -> None:
        v = getattr(cfg, name)
        if v is None:
            return
        if (v <= 0) if strict else (v < 0):
            e.append(f"{name} must be {'>' if strict else '>='} 0")

    if not (0.0 < cfg.na < 1.0):
        e.append("na must be between 0 and 1 (vacuum)")
    if not (0.0 < cfg.sigma <= 1.0):
        e.append("sigma must be in (0, 1] (source inside the pupil)")
    if cfg.sigma_inner is not None and not (0.0 <= cfg.sigma_inner < cfg.sigma):
        e.append("sigma_inner must be >= 0 and smaller than sigma")
    if cfg.pole_opening_deg is not None and not (0.0 < cfg.pole_opening_deg <= 180.0):
        e.append("pole_opening_deg must be in (0, 180]")
    if cfg.illumination_shape not in FIELDS["illumination_shape"]["choices"]:
        e.append("illumination_shape unknown")
    pos("wavelength_nm")
    pos("period_nm")
    if not (0.0 < cfg.line_width_nm < cfg.period_nm):
        e.append("line_width_nm must be between 0 and period_nm")
    if not cfg.absorber_material.strip():
        e.append("absorber_material missing")
    pos("absorber_height_nm")
    if not (0.0 < cfg.absorber_taper_deg < 180.0):
        e.append("absorber_taper_deg must be between 0 and 180")
    pos("mask_undercut_nm", strict=False)
    pos("mask_demagnification")
    if cfg.ml_n_bilayers < 0:
        e.append("ml_n_bilayers must be >= 0")
    pos("ml_d_mo_nm")
    pos("ml_d_si_nm")
    if cfg.ml_gamma is not None and not (0.0 < cfg.ml_gamma < 1.0):
        e.append("ml_gamma must be between 0 and 1")
    pos("ml_grading_linear_nm", strict=False)
    pos("ml_grading_parabolic_nm", strict=False)
    pos("ml_roughness_nm", strict=False)
    if not cfg.ml_capping.strip():
        e.append("ml_capping missing")
    pos("ml_capping_nm", strict=False)
    pos("dose_mj_cm2")
    if cfg.resist_model not in FIELDS["resist_model"]["choices"]:
        e.append("resist_model unknown")
    if not (0.0 < cfg.resist_threshold_norm < 1.0):
        e.append("resist_threshold_norm must be between 0 and 1")
    pos("dill_A", strict=False)
    pos("dill_B")
    pos("dill_C")
    pos("se_blur_nm", strict=False)
    pos("resist_thickness_nm")
    if cfg.peb_model not in FIELDS["peb_model"]["choices"]:
        e.append("peb_model unknown")
    pos("peb_t_bake")
    pos("peb_k")
    pos("peb_acid_lifetime_s")
    pos("peb_D", strict=False)
    pos("peb_sigma_diff", strict=False)
    pos("peb_k_trap_per_s", strict=False)
    pos("peb_D_quencher", strict=False)
    pos("pag_density_per_nm3")
    pos("quencher_density_per_nm3", strict=False)
    pos("acid_base_quench_rate_nm3_per_s", strict=False)
    pos("mack_R_max")
    pos("mack_R_min", strict=False)
    if not cfg.mack_n > 1.0:
        e.append("mack_n must be > 1 (Mack rate law)")
    if not (0.0 < cfg.mack_M_th < 1.0):
        e.append("mack_M_th must be between 0 and 1")
    pos("develop_time_s")
    if cfg.development_model not in FIELDS["development_model"]["choices"]:
        e.append("development_model unknown")
    if cfg.stochastic_n_realisations < 1:
        e.append("stochastic_n_realisations must be >= 1")
    if cfg.stochastic_ler_grid_y < 1:
        e.append("stochastic_ler_grid_y must be >= 1")
    if cfg.stochastic_ler_estimator not in FIELDS["stochastic_ler_estimator"]["choices"]:
        e.append("stochastic_ler_estimator unknown")
    if cfg.ler_passband_nm is not None:
        lo, hi = cfg.ler_passband_nm
        if not (0.0 < lo < hi):
            e.append("ler_passband_nm must satisfy 0 < p_min < p_max")
    pos("blocked_site_density_per_nm3")
    pos("dissolution_cell_nm")
    if cfg.grid < 4:
        e.append("grid must be >= 4 (numerical minimum)")
    if cfg.n_rcwa_orders < 1:
        e.append("n_rcwa_orders must be >= 1")
    if cfg.n_develop_layers < 2:
        e.append("n_develop_layers must be >= 2")
    return e


# ──────────────────────────────────────────────
# Presets
# ──────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class Preset:
    """A named starting configuration with its provenance."""

    key: str
    label: str
    summary: str
    provenance: str
    factory: Callable[[], SimulationConfig]


PRESETS: Dict[str, Preset] = {
    "default": Preset(
        key="default",
        label="Default resist (documented parameters)",
        summary="64 nm pitch, NA 0.33 conventional σ 0.8; the pipeline defaults.",
        provenance=(
            "Every default has a source in docs/physics.md (Yamamoto 2011 kinetics, LBNL Dill C, "
            "Kang 2010 diffusivity, Thackeray 2010 blur). Assembled from several resists, so its "
            "full-chemistry dose-to-size (about 1–3 mJ/cm²) is not a prediction for any real "
            "resist."
        ),
        factory=SimulationConfig,
    ),
    "nxe1716": Preset(
        key="nxe1716",
        label="NXE1716 anchor (imec, prediction)",
        summary="22 nm lines at 44 nm pitch, NXE:3300B dipole 90X (σ 0.62/0.90), 35 nm film.",
        provenance=(
            "Mack parameters and deprotection rate from the Vesters 2017 dissolution-rate curve, "
            "the rest generic (Vesters 2017/2019). The chain predicts a dose-to-size of about "
            "19.7 mJ/cm² where the wafer measured 11.0 mJ/cm² (LWR 6.7 nm 3σ, SEM-biased); "
            "this preset shows the prediction, not a fit."
        ),
        factory=nxe1716_config,
    ),
    "nxe1716_calibrated": Preset(
        key="nxe1716_calibrated",
        label="NXE1716 anchor (dose calibrated ×1.79)",
        summary="Same as the NXE1716 anchor, deprotection rate scaled to print at 11.0 mJ/cm².",
        provenance=(
            f"peb_k multiplied by {NXE1716_DOSE_SCALE_CALIBRATION:.3f} so the chain prints 22 nm "
            "at the measured 11.0 mJ/cm². This is a calibration to the wafer, not physics; the "
            "missing factor is structural (see docs/physics.md, NXE1716 section)."
        ),
        factory=lambda: nxe1716_config(calibrated_dose_scale=True),
    ),
    "met2d": Preset(
        key="met2d",
        label="MET-2D / XP 5271 anchor (Berkeley MET)",
        summary="50 nm 1:1 lines, NA 0.30 annular σ 0.35–0.55, 80 nm film, PEB 120 °C / 90 s.",
        provenance=(
            "Mack parameters and Dill B from Sekiguchi 2011, Dill C from LBNL, PEB blur set "
            "directly from the measured deprotection blur (Anderson & Naulleau 2008, 23.8 nm "
            "width → σ 10.1 nm). The deprotection rate is not sourced for this resist, so the "
            "dose scale is not predicted (measured E-size 12.5 mJ/cm²); measured LER 6.7 nm in "
            "the 10–834 nm band, SEM bias unknown."
        ),
        factory=met2d_config,
    ),
}


def config_as_dict(cfg: SimulationConfig) -> Dict[str, Any]:
    """Flat, JSON-friendly view of a configuration (tuples become lists)."""
    out = dataclasses.asdict(cfg)
    for k, v in out.items():
        if isinstance(v, tuple):
            out[k] = list(v)
    return out


def resolve_config(preset: Optional[str], overrides: Dict[str, Any]) -> SimulationConfig:
    """Preset (or the defaults) with the given field overrides applied.

    Raises ``KeyError`` for an unknown preset and ``ValueError`` (from the
    dataclass) for values its own ``__post_init__`` rejects.
    """
    base = PRESETS[preset or "default"].factory()
    fixed = dict(overrides)
    if "ler_passband_nm" in fixed and fixed["ler_passband_nm"] is not None:
        fixed["ler_passband_nm"] = tuple(fixed["ler_passband_nm"])
    return dataclasses.replace(base, **fixed) if fixed else base
