"""Full simulation pipeline — end-to-end EUV lithography simulation.

Connects all modules: mask → RCWA → aerial image → resist → CD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch

from euv.aerial.abbe import abbe_image, nils
from euv.aerial.pupil import circular_pupil, pupil_grid
from euv.aerial.source import conventional
from euv.mask3d.rcwa_torch import RCWA1D, RCWAConfig, binary_grating_profile
from euv.materials import CXROTable
from euv.resist.develop import (
    MackModel,
    extract_cd,
    threshold_development,
)
from euv.resist.exposure import dose_to_acid
from euv.resist.peb import reaction_diffusion_analytical


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
    period_nm: float = 64.0
    line_width_nm: float = 32.0
    absorber_height_nm: float = 60.0
    absorber_material: str = "Ta"
    n_rcwa_orders: int = 21
    dose_mj_cm2: float = 20.0
    resist_threshold: float = 0.5
    grid: int = 256
    device: str = "cpu"


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
    n_ta, k_ta = table.refractive_index(cfg.absorber_material, 91.84)
    eps_line = complex(n_ta, k_ta) ** 2
    eps_space = 1.0 + 0.0j  # vacuum

    # ── 2. RCWA: compute mask reflectivity ────
    profile = binary_grating_profile(
        period=period_m,
        fill_width=line_m,
        eps_line=eps_line,
        eps_space=eps_space,
        n_samples=max(1024, cfg.n_rcwa_orders * 20),
        device=device,
    )
    thicknesses = torch.tensor(
        [cfg.absorber_height_nm * 1e-9], dtype=torch.float64, device=device
    )

    rcwa_cfg = RCWAConfig(
        wavelength=wavelength_m,
        n_orders=cfg.n_rcwa_orders,
        theta=6.0,
        polarization="TE",
        device=device,
    )
    solver = RCWA1D(rcwa_cfg)
    orders = solver.solve(profile, thicknesses, period_m)
    eff = solver.diffraction_efficiency(orders)
    absorber_reflectivity = sum(eff.values())

    # ── 3. Illumination source ────────────────
    source = conventional(cfg.grid, sigma=cfg.sigma, device=device)

    # ── 4. Pupil ──────────────────────────────
    fx, fy, inside_pupil = pupil_grid(cfg.grid, na=cfg.na, device=device)
    pupil = inside_pupil.to(torch.float64).to(torch.complex128)

    # ── 5. Mask FFT ────────────────────────────
    # Build a simple mask transmission: line/space
    x = torch.linspace(-period_m / 2, period_m / 2, cfg.grid, device=device)
    half_line = line_m / 2
    mask_transmission = torch.ones(cfg.grid, cfg.grid, dtype=torch.complex128, device=device)
    # Vertical absorber lines in the centre
    for i in range(cfg.grid):
        xi = x[i].item()
        if abs(xi) <= half_line:
            mask_transmission[:, i] = 0.0  # absorber = dark

    mask_fft = torch.fft.fft2(mask_transmission)
    mask_fft = torch.fft.fftshift(mask_fft)

    # ── 6. Aerial image ───────────────────────
    aerial = abbe_image(mask_fft, source, fx, fy, pupil, na=cfg.na)

    # Normalise to dose
    aerial = aerial * cfg.dose_mj_cm2 / (aerial.max() + 1e-12)

    # NILS at the line edge
    nils_val = nils(aerial, half, cfg.line_width_nm / (period_m / cfg.grid))

    # ── 7. Resist ─────────────────────────────
    dose_map = aerial.clone().float()
    acid = dose_to_acid(dose_map, C=0.05, Q=0.3, sigma_blur=5.0)
    inhib_in = torch.ones_like(acid)
    _, inhib = reaction_diffusion_analytical(acid, inhib_in, k=0.3, t_bake=60.0)

    dev = threshold_development(inhib, threshold=cfg.resist_threshold)

    # CD extraction
    dx_nm = period_m / cfg.grid * 1e9
    cd = extract_cd(dev, dx=float(dx_nm))

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