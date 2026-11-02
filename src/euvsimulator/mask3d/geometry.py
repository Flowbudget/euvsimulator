"""Mask geometry builder — absorber stacks, multilayer substrate, and
permittivity conversion utilities for the RCWA solver.

Provides:

- :func:`standard_euv_mask` — build a mask description (etched absorber,
  blanket capping layer, Mo/Si multilayer parameters)
- :func:`build_permittivity_profile` — convert a mask description to the
  permittivity profile of the absorber grating for the RCWA solver
- :func:`line_fill_fraction` — cell-averaged sampling of a periodic line on
  the grid the RCWA Fourier transform assumes

Only etched layers (etched=True) form the RCWA grating. Blanket layers such
as the Ru capping layer lie under the absorber, on top of the multilayer; in
the RCWA model they belong to the multilayer stack (for example
mo_si_stack(capping_layer="Ru") passed to RCWA1D.solve as ml_stack), as in
run_simulation with use_rcwa=True.
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
        True if this layer is patterned (part of the absorber grating),
        False if blanket (e.g. the Ru capping layer on the multilayer).
        Only etched layers enter :func:`build_permittivity_profile`.
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
        Layers above the multilayer mirror, from top down. Layers with
        etched=True form the patterned absorber grating; layers with
        etched=False (e.g. the Ru capping layer under the absorber) are
        blanket and are not part of the grating.
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
        """Total thickness of the etched (absorber) layers [nm].

        Blanket layers (etched=False, e.g. the capping layer) are not
        counted. This is the grating height that
        :func:`build_permittivity_profile` returns.
        """
        return sum(layer.thickness_nm for layer in self.absorber_layers if layer.etched)

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

    absorber_layers is [absorber, capping] from top down: the absorber is
    etched (etched=True) and forms the grating; the capping layer lies under
    it, on the Mo/Si multilayer, and is blanket (etched=False).
    :func:`build_permittivity_profile` therefore returns an absorber-only
    grating (60 nm by default). Model the capping layer in the multilayer
    stack (mo_si_stack(capping_layer=...) passed as ml_stack), as
    run_simulation does. Up to v2.2.1 the cap was listed first and etched,
    which gave a 62.5 nm grating with the absorber permittivity throughout.

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
        Photon energy for refractive indices. Default is 91.84 eV
        (corresponding to 13.5 nm wavelength via E = hc/λ).
        Use the derived energy from wavelength for consistency.

    Returns
    -------
    MaskStack
    """
    from euvsimulator.materials import CXROTable

    table = CXROTable()

    def _nk(sym: str) -> complex:
        n, k = table.refractive_index(sym, energy_eV)
        return complex(n, k)

    # Top down: the etched absorber, then the blanket capping layer that
    # lies under it, on the multilayer.
    layers = [
        MaskLayer(
            material=absorber, thickness_nm=absorber_thickness_nm, nk=_nk(absorber), etched=True
        ),
        MaskLayer(
            material=capping, thickness_nm=capping_thickness_nm, nk=_nk(capping), etched=False
        ),
    ]

    return MaskStack(
        absorber_layers=layers,
        multilayer_bilayers=n_bilayers,
        substrate_nk=_nk("Si"),
        period_nm=period_nm,
        line_width_nm=line_width_nm,
    )


def line_fill_fraction(
    n_samples: int,
    duty: float,
    device: str | torch.device = "cpu",
) -> torch.Tensor:
    """Fraction of each sample cell covered by a line centred in the period.

    Sample ``k`` sits at ``x_k = k * P / n_samples`` -- the position the
    FFT of :func:`~euvsimulator.mask3d.rcwa_torch.permittivity_toeplitz`
    gives it -- and stands for the cell of width ``P / n_samples`` around
    that position. The line ``|x - P/2| <= duty * P / 2`` repeats with the
    period. A cell cut by an edge gets the covered fraction, so a profile
    ``eps_space + (eps_line - eps_space) * fraction`` has the exact duty
    cycle (zero-order Fourier coefficient) for every ``n_samples`` and is
    exactly symmetric about ``P/2``: its Fourier coefficients are real up
    to the phase ``(-1)^m`` of the centre.

    Parameters
    ----------
    n_samples : int
        Samples per period.
    duty : float
        Line width / period, in [0, 1].
    device : str or torch.device
        Device of the returned tensor.

    Returns
    -------
    fraction : (n_samples,) float64
        Covered fraction of each cell, in [0, 1].

    Notes
    -----
    Until 2026-10 the profile builders sampled the closed interval
    ``linspace(0, P, n_samples)``, spacing ``P / (n_samples - 1)``, and kept
    the samples with ``|x - P/2| <= w/2``. The FFT reads the samples at
    spacing ``P / n_samples``, so the line shrank by ``(n - 1) / n``, its
    width was quantised to whole samples (duty 0.3: 18 of 64 samples
    instead of 19.2, 306 of 1024 instead of 307.2) and its centre sat half
    a sample before ``P/2``. Binary samples centred exactly at ``P/2`` can only
    form an odd number of samples, which would be one sample off at
    duty 0.5; the area-weighted edge cells avoid that. For the inverse
    rule (TM) an edge cell holds the inverse of the mixed permittivity
    instead of the mixed inverse, a second-order difference in one cell
    per edge.
    """
    n = int(n_samples)
    half = 0.5 * float(duty) * n  # half line width [samples]
    k = torch.arange(n, dtype=torch.float64, device=device)
    dist = (k - 0.5 * n).abs()  # distance to the line centre [samples], <= n/2

    def covered(d: torch.Tensor) -> torch.Tensor:
        # overlap of the cell [d - 1/2, d + 1/2] with the line [-half, half]
        lo = torch.clamp(d - 0.5, min=-half)
        hi = torch.clamp(d + 0.5, max=half)
        return (hi - lo).clamp(min=0.0)

    # the line itself and its periodic image one period away
    return (covered(dist) + covered(n - dist)).clamp(max=1.0)


def build_permittivity_profile(
    stack: MaskStack,
    n_samples: int = 1024,
    device: str = "cpu",
    energy_eV: float | None = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build the permittivity profile and layer thicknesses for RCWA.

    For the absorber region, the permittivity is a binary grating
    (line = absorber, space = vacuum), centred at P/2 and sampled as
    described in :func:`line_fill_fraction`: a sample whose cell an edge
    cuts holds the area-weighted mixture, so the duty cycle and the
    centre are exact for every ``n_samples``. Only the etched layers
    (etched=True) form the grating; they must all have the same
    refractive index, because the RCWA solver takes one profile.
    Blanket layers (etched=False, e.g. the Ru capping layer) are not
    part of the grating and are ignored here; model them in the
    multilayer stack (ml_stack), as run_simulation does. For the
    substrate region (multilayer), it's a blanket mirror described by
    the effective permittivity of the Mo/Si stack.

    Parameters
    ----------
    stack : MaskStack
    n_samples : int
        Spatial samples per period.
    device : str
    energy_eV : float, optional
        Photon energy for the Mo/Si constants of the effective substrate
        permittivity. Defaults to ``constants.EUV_ENERGY_EV`` (13.5 nm).

    Returns
    -------
    eps_profile : (n_samples,) complex128
        Permittivity over one period at the absorber height; sample k
        at x_k = k * P / n_samples.
    layer_thicknesses : (1,) float64 [m]
        Grating height: total thickness of the etched layers.
    substrate_eps : () complex128
        Thickness-weighted average Mo/Si permittivity -- a homogeneous
        stand-in for the multilayer, NOT its Bragg response. The pipeline
        does not use it (it passes the real ML stack as an order-diagonal
        TMM operator to the RCWA solver); it is kept for callers that want
        a bulk-substrate approximation. Constants come from the CXRO table
        (previously hard-coded Mo/Si n,k literals).

    Raises
    ------
    ValueError
        If no layer is etched, or if the etched layers have different
        refractive indices.
    """
    # Permittivity of line and space materials.
    # Line: the etched (absorber) layers only. Blanket layers (etched=False,
    # e.g. the Ru cap) are not part of the grating; they belong to the
    # multilayer stack. Up to v2.2.1 the permittivity came from
    # absorber_layers[-1] and the height from ALL layers, so a Ru cap in the
    # list became 2.5 nm of extra absorber in the lines (62.5 nm grating).
    # Note: abs_nk is the complex refractive index n+ik.
    # The RCWA solver expects permittivity epsilon = (n+ik)^2.
    grating_layers = [layer for layer in stack.absorber_layers if layer.etched]
    if not grating_layers:
        raise ValueError(
            "build_permittivity_profile: no layer has etched=True; the absorber "
            "grating needs at least one patterned layer (MaskLayer(..., etched=True))"
        )
    abs_nk = complex(grating_layers[0].nk)  # absorber material (n+ik)
    for layer in grating_layers[1:]:
        if complex(layer.nk) != abs_nk:
            raise ValueError(
                "build_permittivity_profile: the etched layers have different "
                "refractive indices ("
                + ", ".join(f"{g.material}={complex(g.nk)}" for g in grating_layers)
                + "); the single-profile RCWA grating cannot represent a "
                "multi-material absorber"
            )
    space_eps = complex(1.0, 0.0)  # vacuum
    line_eps = complex(abs_nk.real, abs_nk.imag) ** 2  # (n+ik)^2 = permittivity

    # Line centred at P/2, sampled where the FFT reads it (line_fill_fraction).
    frac = line_fill_fraction(n_samples, stack.line_width_nm / stack.period_nm, device=device)
    eps = space_eps * (1.0 - frac) + line_eps * frac

    # Effective substrate permittivity (thickness-weighted average Mo/Si),
    # optical constants from the CXRO table at the requested energy.
    from euvsimulator.constants import EUV_ENERGY_EV
    from euvsimulator.materials import CXROTable

    table = CXROTable()
    e_ev = EUV_ENERGY_EV if energy_eV is None else float(energy_eV)
    n_mo, k_mo = table.refractive_index("Mo", e_ev)
    n_si, k_si = table.refractive_index("Si", e_ev)
    d_mo, d_si = stack.d_mo_nm, stack.d_si_nm
    eps_mo = complex(n_mo + k_mo * 1j) ** 2
    eps_si = complex(n_si + k_si * 1j) ** 2
    eps_sub = (eps_mo * d_mo + eps_si * d_si) / (d_mo + d_si)

    thicknesses = torch.tensor(
        [sum(layer.thickness_nm for layer in grating_layers) * 1e-9],
        dtype=torch.float64,
        device=device,
    )

    return eps, thicknesses, torch.tensor(eps_sub, dtype=torch.complex128, device=device)
