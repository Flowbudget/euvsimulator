"""Mask geometry builder — absorber stacks, multilayer substrate, and
permittivity conversion utilities for the RCWA solver.

Provides:

- :func:`absorber_stack` — build the full mask cross-section
  (capping layer + absorber + multilayer substrate)
- :func:`mask_permittivity` — convert a mask description to a
  permittivity profile at a given wavelength
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import torch


@dataclass
class MaskLayer:
    """A single layer in the mask stack.

    Parameters
    ----------
    material : str
        Material symbol (e.g. ``"Ta"``, ``"Ru"``, ``"Mo"``, ``"Si"``).
    thickness_nm : float
        Layer thickness in nanometres.
    nk : complex
        Complex refractive index n + ik at the simulation wavelength.
    etched : bool
        True if this layer is patterned (absorber), False if blanket.
    """

    material: str
    thickness_nm: float
    nk: complex
    etched: bool = False


@dataclass
class MaskStack:
    """Complete EUV mask description.

    Consists of a top absorber region (patterned) and a bottom
    multilayer mirror (blanket).

    Parameters
    ----------
    absorber_layers : list of MaskLayer
        Patterned layers (Ta absorber, Ru capping, etc.) from top down.
    multilayer_bilayers : int
        Number of Mo/Si bilayers in the mirror.
    d_mo_nm : float
        Mo layer thickness in nm.
    d_si_nm : float
        Si layer thickness in nm.
    substrate_nk : complex
        Substrate complex refractive index.
    period_nm : float
        Mask pattern period [nm] — for the grating region.
    line_width_nm : float
        Absorber line width [nm] — for the grating region.
    """

    absorber_layers: List[MaskLayer]
    multilayer_bilayers: int = 40
    d_mo_nm: float = 2.8
    d_si_nm: float = 4.1
    substrate_nk: complex = complex(0.999, 0.00183)
    period_nm: float = 64.0
    line_width_nm: float = 32.0

    @property
    def total_absorber_thickness_nm(self) -> float:
        """Total thickness of all absorber layers [nm]."""
        return sum(layer.thickness_nm for layer in self.absorber_layers)

    @property
    def pitch_nm(self) -> float:
        """Grating pitch [nm] (alias for ``period_nm``)."""
        return self.period_nm


def standard_euv_mask(
    absorber: str = "Ta",
    absorber_thickness_nm: float = 60.0,
    capping: str = "Ru",
    capping_thickness_nm: float = 2.5,
    n_bilayers: int = 40,
    period_nm: float = 64.0,
    line_width_nm: float = 32.0,
    energy_eV: float = 91.84,
) -> MaskStack:
    """Build a standard EUV mask stack.

    Parameters
    ----------
    absorber : str
        Absorber material (default: ``"Ta"``).
    absorber_thickness_nm : float
        Absorber thickness [nm] (default: 60).
    capping : str
        Capping layer material (default: ``"Ru"``).
    capping_thickness_nm : float
        Capping layer thickness [nm] (default: 2.5).
    n_bilayers : int
        Number of Mo/Si bilayers (default: 40).
    period_nm : float
        Pattern period [nm] (default: 64 → 32 nm L/S).
    line_width_nm : float
        Line width [nm] (default: 32 → 1:1 duty cycle).
    energy_eV : float
        Photon energy for refractive indices (default: 91.84).

    Returns
    -------
    MaskStack
    """
    from euv.materials import CXROTable

    table = CXROTable()

    def _nk(sym: str) -> complex:
        n, k = table.refractive_index(sym, energy_eV)
        return complex(n, k)

    layers = [
        MaskLayer(
            material=capping, thickness_nm=capping_thickness_nm, nk=_nk(capping), etched=True
        ),
        MaskLayer(
            material=absorber, thickness_nm=absorber_thickness_nm, nk=_nk(absorber), etched=True
        ),
    ]

    return MaskStack(
        absorber_layers=layers,
        multilayer_bilayers=n_bilayers,
        substrate_nk=_nk("Si"),
        period_nm=period_nm,
        line_width_nm=line_width_nm,
    )


def build_permittivity_profile(
    stack: MaskStack,
    n_samples: int = 1024,
    device: str = "cpu",
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build the permittivity profile and layer thicknesses for RCWA.

    For the absorber region, the permittivity is a binary grating
    (line = absorber+cap, space = vacuum+cap).  For the substrate
    region (multilayer), it's a blanket mirror described by the
    effective permittivity of the Mo/Si stack.

    Parameters
    ----------
    stack : MaskStack
    n_samples : int
        Spatial samples per period.
    device : str

    Returns
    -------
    eps_profile : (n_samples,) complex128
        Permittivity sampled over one period at the absorber height.
    layer_thicknesses : (1,) float64 [m]
        Absorber layer thicknesses.
    substrate_eps : () complex128
        Effective permittivity of the multilayer substrate (blanket).
    """
    period_m = stack.period_nm * 1e-9
    line_m = stack.line_width_nm * 1e-9

    # Permittivity of line and space materials
    # Line: absorber + capping layers
    space_eps = complex(1.0, 0.0)  # vacuum
    abs_eps = stack.absorber_layers[-1].nk  # absorber material
    cap_eps = stack.absorber_layers[0].nk if stack.absorber_layers else abs_eps

    # Effective line permittivity (absorber dominates)
    line_eps = abs_eps

    x = torch.linspace(0, period_m, n_samples, device=device)
    half_line = line_m / 2.0
    mask = (x >= period_m / 2 - half_line) & (x <= period_m / 2 + half_line)

    eps = torch.full_like(x, space_eps, dtype=torch.complex128)
    eps[mask] = complex(line_eps)

    # Effective substrate permittivity (weighted average Mo/Si)
    n_mo, k_mo = 0.9238, 0.00637
    n_si, k_si = 0.999, 0.00183
    d_mo, d_si = stack.d_mo_nm, stack.d_si_nm
    eps_mo = complex(n_mo - k_mo * 1j) ** 2
    eps_si = complex(n_si - k_si * 1j) ** 2
    eps_sub = (eps_mo * d_mo + eps_si * d_si) / (d_mo + d_si)

    thicknesses = torch.tensor(
        [sum(l.thickness_nm for l in stack.absorber_layers) * 1e-9],
        dtype=torch.float64,
        device=device,
    )

    return eps, thicknesses, torch.tensor(eps_sub, dtype=torch.complex128, device=device)
