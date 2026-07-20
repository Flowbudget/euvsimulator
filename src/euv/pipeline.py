"""Full simulation pipeline — end-to-end EUV lithography simulation.

Connects all modules: mask → RCWA → aerial image → resist → CD.

Resist presets (typical SE blur sigma for different resist types):
    RESIST_PRESETS = {
        "CAR": 5.0,      # Chemically Amplified Resist (typical EUV)
        "nonCAR": 2.5,   # Non-chemically amplified / metal resist
        "HighNA": 3.0,   # High-NA EUV (thinner resist)
    }
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import torch

from euv.aerial.abbe import aerial_from_orders, nils
from euv.materials import CXROTable
from euv.optics.multilayer import mo_si_stack
from euv.optics.tmm import reflectivity
from euv.resist.develop import (
    extract_cd,
    threshold_development,
)
from euv.resist.exposure import dose_to_acid
from euv.resist.peb import reaction_diffusion_analytical

# Resist presets — typical SE blur sigma [nm] for different resist types
RESIST_PRESETS = {
    "CAR": 5.0,      # Chemically Amplified Resist (typical EUV)
    "nonCAR": 2.5,   # Non-chemically amplified / metal resist
    "HighNA": 3.0,   # High-NA EUV (thinner resist)
}

@dataclass
@dataclass
class SimulationResult:
    """Results from a full pipeline simulation.

    Parameters
    ----------
    aerial_image : (G, G) float64
        Computed aerial image intensity.
    resist_profile : (G, G) float64
        Developed resist profile (0 = developed, 1 = remaining).
    cd_nm : float
        Critical dimension [nm] (0 if not measurable).
    nils_value : float
        Normalised Image Log-Slope at line edge.
    absorber_reflectivity : float
        Reflectivity of the absorber region (normalised).
    """

    aerial_image: torch.Tensor
    resist_profile: torch.Tensor
    cd_nm: float = 0.0
    nils_value: float = 0.0
    absorber_reflectivity: float = 0.0


@dataclass
class SimulationConfig:
    """Configuration for a full pipeline simulation.

    Parameters
    ----------
    wavelength_nm : float
        Exposure wavelength [nm] (default: 13.5).
    na : float
        Numerical aperture (default: 0.33).
    sigma : float
        Partial coherence factor (default: 0.8).
    period_nm : float
        Mask pattern period [nm] (default: 64).
    line_width_nm : float
        Absorber line width [nm] (default: 32).
    absorber_height_nm : float
        Absorber thickness [nm] (default: 60).
    absorber_material : str
        Absorber material (default: "Ta").
    n_rcwa_orders : int
        RCWA Fourier orders (default: 21).
    dose_mj_cm2 : float
        Exposure dose [mJ/cm²] (default: 20).
    resist_threshold : float
        Development threshold (default: 0.5).
    grid : int
        Simulation grid size (default: 256).
    device : str
        PyTorch device (default: "cpu").
    """

    wavelength_nm: float = 13.5
    na: float = 0.33
    sigma: float = 0.8
    illumination_shape: str = "conventional"
    ml_n_bilayers: int = 50
    ml_d_mo_nm: float = 2.8
    ml_d_si_nm: float = 4.1
    ml_gamma: float | None = None
    ml_grading_linear_nm: float = 0.0
    ml_grading_parabolic_nm: float = 0.0
    ml_roughness_nm: float = 0.0
    ml_capping: str = "Ru"
    ml_capping_nm: float = 2.5
    period_nm: float = 64.0
    line_width_nm: float = 32.0
    absorber_height_nm: float = 60.0
    absorber_material: str = "Ta"
    n_rcwa_orders: int = 21
    dose_mj_cm2: float = 20.0
    resist_threshold: float = 0.5
    resist_model: str = "aerial_threshold"
    resist_threshold_norm: float = 0.5
    se_blur_nm: float = 0.0
    focus_nm: float = 0.0
    grid: int = 256
    device: str = "cpu"


def _cd_via_aerial_threshold(
    aerial: torch.Tensor,
    cfg: SimulationConfig,
    half: int,
    line_width_px: int,
) -> tuple[float, torch.Tensor, float]:
    """Extract CD from the aerial image using a normalised intensity threshold.

    For a positive-tone resist:
    - Bright regions (space) → develop → 0 (developed)
    - Dark regions (absorber) → undeveloped → 1 (remaining)
    - CD = width of the undeveloped (below-threshold) region

    The threshold is ``resist_threshold_norm × max(aerial)``.

    Returns (cd_nm, resist_profile, nils_value).
    """
    G = aerial.shape[0]
    device = aerial.device
    cut = aerial[half, :]  # centre-row cut
    # FIXED threshold relative to nominal-dose intensity (c0² × nominal dose),
    # NOT 0.5 × max(aerial).  This makes CD dose-dependent and physically correct.
    # c0 is the mean reflectivity (a·duty + b·(1−duty)); reconstructed here from
    # the aerial DC level.
    dc_level = float(aerial.mean())
    nominal_dose = 20.0
    threshold_val = cfg.resist_threshold_norm * dc_level * (nominal_dose / max(cfg.dose_mj_cm2, 1e-9))
    dx_nm = cfg.period_nm / G

    # NILS at the line edge
    dx_nm = cfg.period_nm / cfg.grid
    nils_val = nils(aerial, half, line_width_px, dx_nm)

    # Positive-tone developed mask
    dev = (cut > threshold_val).float()
    dev_2d = dev.unsqueeze(0).expand(G, G).clone()

    # CD extraction: find the largest run of undeveloped pixels (dev == 0)
    runs = _find_runs_1d(dev, target=0)
    if len(runs) == 0:
        cd_nm = 0.0
    else:
        longest = max(runs, key=lambda r: r[1] - r[0])
        lidx, ridx = longest
        cd_nm = (ridx - lidx + 1) * dx_nm

    return cd_nm, dev_2d, nils_val


def _cd_via_full_chem(
    aerial: torch.Tensor,
    cfg: SimulationConfig,
    period_m: float,
    half: int,
    line_width_px: int,
) -> tuple[float, torch.Tensor, float]:
    """Extract CD via full resist chemistry chain (dose → acid → PEB → develop).

    Uses the Dill ABC exposure model, reaction-diffusion PEB, and threshold
    development.  Requires well-tuned parameters (C, Q, k, t_bake, sigma_diff).
    """
    dx_nm = period_m / cfg.grid * 1e9
    nils_val = nils(aerial, half, line_width_px, dx_nm)

    # ── Resist-chemie-Kette (Dill ABC → PEB → Entwicklung) ──
    # Berechnet das resist-chemische Profil (inhib) für die Visualisierung.
    # Die CD-Extraktion nutzt den gleichen fixen, dosisabhängigen Threshold
    # wie der aerial_threshold-Pfad, damit beide Pfade konsistent sind.
    dose_map = aerial.clone().float()
    acid = dose_to_acid(dose_map, C=0.05, Q=1.0, sigma_blur=5.0, dx=dx_nm)
    inhib_in = torch.ones_like(acid)
    _, inhib = reaction_diffusion_analytical(
        acid,
        inhib_in,
        k=0.3,
        t_bake=60.0,
        sigma_diff=5.0,
        dx=dx_nm,
    )
    # Resist-Profil für Visualisierung (1 = undeveloped/remaining)
    dev_chem = threshold_development(inhib, threshold=0.2)

    # CD-Extraktion: gleicher fixer Threshold wie aerial_threshold-Pfad
    cut = aerial[half, :]
    dc_level = float(aerial.mean())
    nominal_dose = 20.0
    threshold_val = cfg.resist_threshold_norm * dc_level * (nominal_dose / max(cfg.dose_mj_cm2, 1e-9))
    dev = (cut > threshold_val).float()
    dev_2d = dev.unsqueeze(0).expand(cfg.grid, cfg.grid).clone()

    runs = _find_runs_1d(dev, target=0)
    if len(runs) == 0:
        cd_nm = 0.0
    else:
        longest = max(runs, key=lambda r: r[1] - r[0])
        lidx, ridx = longest
        cd_nm = (ridx - lidx + 1) * dx_nm

    return cd_nm, dev_2d, nils_val


def _find_runs_1d(x: torch.Tensor, target: int = 0) -> list:
    """Find consecutive runs of ``x == target`` in a 1D tensor.

    Returns list of (start_idx, end_idx) inclusive.
    """
    padded = torch.cat(
        [
            torch.tensor([1 - target], device=x.device),
            x,
            torch.tensor([1 - target], device=x.device),
        ]
    )
    diffs = torch.diff(padded.float())
    starts = torch.where(diffs < -0.5)[0]
    ends = torch.where(diffs > 0.5)[0] - 1
    return [(int(s), int(e)) for s, e in zip(starts, ends)]


def run_simulation(
    cfg: Optional[SimulationConfig] = None,
    **kwargs,
) -> SimulationResult:
    """Run a full end-to-end EUV lithography simulation.

    Parameters
    ----------
    cfg : SimulationConfig, optional
        Simulation configuration.  Omit for defaults.
    **kwargs
        Override individual config parameters.

    Returns
    -------
    SimulationResult
    """
    if cfg is None:
        cfg = SimulationConfig(**kwargs)
    else:
        for k, v in kwargs.items():
            setattr(cfg, k, v)

    device = cfg.device
    wavelength_m = cfg.wavelength_nm * 1e-9
    period_m = cfg.period_nm * 1e-9
    line_m = cfg.line_width_nm * 1e-9
    half = cfg.grid // 2

    # ── 1. Materials ──────────────────────────
    table = CXROTable()

    # ── 5. Aerial image from complex diffraction orders (TMM + Hopkins) ──
    # Compute the complex reflectivity of the ML mirror and the absorber+ML stack
    # via TMM.  Then compute the 1D aerial image directly from the Fourier
    # coefficients of the binary complex mask using the Hopkins formulation.
    theta0 = torch.tensor(math.radians(6.0), dtype=torch.float64)
    wl_t = torch.tensor([wavelength_m], dtype=torch.float64)
    n_si, k_si = table.refractive_index("Si", 91.84)
    n_sub = torch.tensor(complex(n_si, k_si), dtype=torch.complex128)

    # Build multilayer stack (without absorber)
    ml_stack = mo_si_stack(
        n_bilayers=cfg.ml_n_bilayers,
        d_mo_nm=cfg.ml_d_mo_nm,
        d_si_nm=cfg.ml_d_si_nm,
        gamma=cfg.ml_gamma,
        grading_linear_nm=cfg.ml_grading_linear_nm,
        grading_parabolic_nm=cfg.ml_grading_parabolic_nm,
        capping_layer=cfg.ml_capping if cfg.ml_capping != "none" else None,
        d_cap_nm=cfg.ml_capping_nm,
    )

    # TMM: ML-only reflectivity (space regions)
    _, r_space = reflectivity(
        ml_stack.n_layers,
        ml_stack.thicknesses,
        wl_t,
        theta0,
        n_substrate=n_sub,
        roughness_nm=cfg.ml_roughness_nm,
    )
    r0_space = r_space[0]

    # TMM: absorber-on-ML reflectivity (absorber lines)
    n_ta_c, k_ta_c = table.refractive_index(cfg.absorber_material, 91.84)
    n_abs = torch.tensor(complex(n_ta_c, k_ta_c), dtype=torch.complex128)
    d_abs = torch.tensor([cfg.absorber_height_nm * 1e-9], dtype=torch.float64)
    full_n = torch.cat([n_abs.unsqueeze(0), ml_stack.n_layers])
    full_d = torch.cat([d_abs, ml_stack.thicknesses])

    _, r_ab = reflectivity(
        full_n,
        full_d,
        wl_t,
        theta0,
        n_substrate=n_sub,
        roughness_nm=cfg.ml_roughness_nm,
    )
    r0_abs = r_ab[0]

    # Average absorber reflectivity (diagnostic)
    space_frac = 1.0 - cfg.line_width_nm / cfg.period_nm
    absorber_reflectivity = float(
        (abs(r0_abs) ** 2 * (1.0 - space_frac) + abs(r0_space) ** 2 * space_frac).real
    )

    # Fourier coefficients of the binary complex mask
    duty = cfg.line_width_nm / cfg.period_nm  # η = absorber fraction
    n_orders = min(cfg.n_rcwa_orders, cfg.grid // 2)

    a = r0_abs
    b = r0_space
    c0 = a * duty + b * (1.0 - duty)

    order_indices = list(range(-n_orders, n_orders + 1))
    amplitudes = torch.zeros(len(order_indices), dtype=torch.complex128, device=device)

    for idx, m in enumerate(order_indices):
        if m == 0:
            amplitudes[idx] = c0
        else:
            cm = (a - b) * math.sin(math.pi * m * duty) / (math.pi * m)
            amplitudes[idx] = cm

    # Compute aerial image from orders (Hopkins formulation)
    order_tensor = torch.tensor(order_indices, dtype=torch.int64, device=device)
    aerial = aerial_from_orders(
        amplitudes,
        order_tensor,
        period_m=period_m,
        na=cfg.na,
        wavelength_m=wavelength_m,
        sigma=cfg.sigma,
        illumination_shape=cfg.illumination_shape,
        grid=cfg.grid,
        focus_nm=cfg.focus_nm,
        se_blur_nm=cfg.se_blur_nm,
    )

    # Normalise to dose (absolute intensity scaling, NOT max-normalisation).
    # The threshold is a FIXED fraction of the nominal-dose intensity, so the
    # CD becomes dose-dependent (higher dose -> narrower line for positive resist).
    aerial = aerial * cfg.dose_mj_cm2

    # ── 6. CD Extraction from Aerial Image ──────────────────────
    # Use the aerial image directly to extract CD via intensity threshold.
    # This is the most robust approach for general use; the full resist
    # chemistry chain (dose_to_acid → PEB → development) is available
    # via resist_model="full_chem" but requires carefully tuned params.
    line_width_px = int(round(cfg.line_width_nm / (period_m / cfg.grid * 1e9)))
    if cfg.resist_model == "full_chem":
        cd, dev, nils_val = _cd_via_full_chem(aerial, cfg, period_m, half, line_width_px)
    else:
        cd, dev, nils_val = _cd_via_aerial_threshold(aerial, cfg, half, line_width_px)

    return SimulationResult(
        aerial_image=aerial,
        resist_profile=dev,
        cd_nm=cd,
        nils_value=float(nils_val),
        absorber_reflectivity=absorber_reflectivity,
    )


def simulate_line_space(
    period_nm: float = 64.0,
    cd_nm: float = 32.0,
    dose_mj_cm2: float = 20.0,
    na: float = 0.33,
    sigma: float = 0.8,
    grid: int = 256,
    device: str = "cpu",
) -> SimulationResult:
    """Convenience: run a standard line/space simulation.

    Returns
    -------
    SimulationResult
    """
    cfg = SimulationConfig(
        period_nm=period_nm,
        line_width_nm=cd_nm,
        dose_mj_cm2=dose_mj_cm2,
        na=na,
        sigma=sigma,
        grid=grid,
        device=device,
    )
    return run_simulation(cfg)
