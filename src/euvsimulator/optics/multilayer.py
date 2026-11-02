"""Builder for Mo/Si EUV multilayer mirror stacks.

A standard EUV multilayer mirror consists of 40–60 Mo/Si bilayers
(period ~6.9 nm) deposited on a Si substrate, capped with a thin
protective layer (Ru, Si₃N₄, …).  The period is chosen to produce
constructive interference at 13.5 nm near the chief-ray angle of
incidence (≈ 6° for the NXE scanner).

This module provides:

- ``MoSiStack`` — convenience builder that returns the refractive
  indices and thicknesses arrays needed by :mod:`euvsimulator.optics.tmm`.
- ``interdiffusion_correction`` - replaces every internal interface by
  an intermediate-index layer of thickness 2*sigma, carved out of the
  two neighbouring layers so that the bilayer period is preserved.
  To second order in k_z*sigma this reproduces the Debye-Waller /
  Nevot-Croce damping exp(-2 k_z^2 sigma^2) of each interface
  reflection.  The analytic Nevot-Croce factor itself is applied by
  ``tmm.reflectivity(..., roughness_nm=sigma)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import torch

from euvsimulator.materials import CXROTable

# Default CXRO table for refractive indices
_default_table = CXROTable()


# ──────────────────────────────────────────────
# Material optical constants at EUV wavelength
# ──────────────────────────────────────────────


def _nk(
    symbol: str,
    energy_eV: float = 91.84,
    table: CXROTable | None = None,
) -> complex:
    """Complex refractive index *n* + i*k for a material at a given energy.

    Parameters
    ----------
    symbol : str
        Chemical symbol.
    energy_eV : float
        Photon energy in eV. Default is 91.84 eV
        (corresponding to 13.5 nm wavelength via E = hc/λ).
        Use the derived energy from wavelength for consistency.
    table : CXROTable, optional
        CXRO table instance. Uses the default singleton if omitted.

    Returns
    -------
    nk : complex
        n + i*k
    """
    t = table or _default_table
    n, k = t.refractive_index(symbol, energy_eV)
    return complex(n, k)


# ──────────────────────────────────────────────
# Mo/Si stack builder
# ──────────────────────────────────────────────


@dataclass
class MultilayerStack:
    """A complete multilayer mirror stack description.

    Parameters
    ----------
    n_layers : (N,) complex128 tensor
        Complex refractive indices of each layer (top → bottom).
    thicknesses : (N,) float64 tensor [m]
        Physical thickness of each layer.
    symbols : list of str
        Material symbol per layer (for reference / plotting).
    description : str
        Human-readable description of the stack.
    n_substrate : () complex128 tensor or None
        Complex refractive index of the substrate below the last layer.
        The substrate is not one of the layers: pass this as
        ``n_substrate`` to :func:`euvsimulator.optics.tmm.reflectivity`.
        None if the builder did not set it.
    """

    n_layers: torch.Tensor
    thicknesses: torch.Tensor
    symbols: List[str]
    description: str = ""
    n_substrate: torch.Tensor | None = None

    @property
    def N(self) -> int:
        """Number of layers in the stack."""
        return self.n_layers.shape[0]

    @property
    def total_thickness_m(self) -> float:
        """Total physical thickness of the stack [m]."""
        return float(self.thicknesses.sum().item())

    @property
    def period_nm(self) -> float:
        """Bilayer period [nm] of the bottom bilayer (the last two layers).

        A capping layer on top does not enter.  Meaningful for periodic
        stacks only; for a graded stack this is the bottom period.
        """
        if self.N >= 2:
            return float(self.thicknesses[-2:].sum().item()) * 1e9
        return 0.0


def mo_si_stack(
    n_bilayers: int = 50,
    d_mo_nm: float = 2.8,
    d_si_nm: float = 4.1,
    capping_layer: str | None = "Ru",
    d_cap_nm: float = 2.5,
    substrate: str = "Si",
    energy_eV: float = 91.84,
    table: CXROTable | None = None,
    gamma: float | None = None,
    grading_linear_nm: float = 0.0,
    grading_parabolic_nm: float = 0.0,
) -> MultilayerStack:
    """Build a standard Mo/Si multilayer mirror stack.

    The standard EUV multilayer alternates Mo (high electron density)
    and Si (low electron density) layers.  The bilayer period is
    approximately λ/(2 cos θ) ≈ 6.9 nm for λ = 13.5 nm at θ = 6°.

    SOURCE STATUS of the default d_mo_nm/d_si_nm/n_bilayers/capping values
    (checked 2026-09-04): the
    bilayer PERIOD (d_mo_nm + d_si_nm = 6.9 nm) is directly verifiable by
    the Bragg relation above -- computed independently here: d = λ /
    (2 sin θ_grazing) with θ_grazing = 90° - 6° gives 6.787 nm in the
    vacuum approximation, 1.66% below this codebase's 6.9 nm, consistent
    with the expected small correction from the multilayer's own
    refractive index (n slightly < 1 for EUV, not accounted for in the
    vacuum formula) -- so the PERIOD is physically consistent, not an
    arbitrary number.
    However, the individual Mo/Si SPLIT (Γ = d_Mo/(d_Mo+d_Si) ≈ 0.406),
    n_bilayers=50, and the Ru capping layer/thickness are NOT derivable
    from the Bragg condition alone (that only fixes the period, not how
    it is divided between the two materials, nor the number of periods
    needed for a given reflectivity target) -- these are real-EUV-mirror
    engineering choices, in the same range reported across the published
    EUV multilayer-mirror literature generally (a web search 2026-09-04
    found several papers/patents citing near-identical Mo/2.8-2.9nm,
    Si/4.1-4.2nm, ~40-60 bilayers, ~2nm Ru cap figures), but this project
    has NOT verified and pinned one specific primary citation for this
    exact numeric combination -- unlike dill_A/B/C/mack_* (Yamamoto et
    al. 2011, primary-source re-verified) or the CXRO n,k data (Henke,
    Gullikson & Davis 1993), these four multilayer-geometry defaults
    should be treated as physically-reasonable engineering defaults, not
    as literature-cited values, until a specific source is found and
    verified by directly reading it (not just an AI web-search summary).

    Parameters
    ----------
    n_bilayers : int
        Number of Mo/Si bilayers (default: 50).
    d_mo_nm : float
        Molybdenum layer thickness in nm (default: 2.8).
    d_si_nm : float
        Silicon layer thickness in nm (default: 4.1).
    capping_layer : str or None
        Capping layer material symbol (default: "Ru").  None = no cap.
    d_cap_nm : float
        Capping layer thickness in nm (default: 2.5).
    substrate : str
        Substrate material symbol (default: "Si").  It is not added as a
        layer; its index at *energy_eV* is returned as
        ``MultilayerStack.n_substrate``, which callers pass to the TMM
        as ``n_substrate``.
    energy_eV : float
        Photon energy in eV. Default is 91.84 eV
        (corresponding to 13.5 nm wavelength via E = hc/λ).
        Use the derived energy from wavelength for consistency.
    table : CXROTable, optional
        CXRO table instance.  Uses the default singleton if omitted.
    gamma : float, optional
        Mo fraction of the bilayer, gamma = d_Mo / (d_Mo + d_Si), with
        0 < gamma < 1.  When set, the bilayer period d_mo_nm + d_si_nm
        is kept and split as d_Mo = gamma * period, d_Si = period - d_Mo,
        so the Bragg peak stays where the two thicknesses put it; the
        individual d_mo_nm and d_si_nm values are then overridden.
    grading_linear_nm : float
        Linear period grading [nm]: each bilayer period increases by
        this amount from top to bottom.  Positive = thicker at bottom.
    grading_parabolic_nm : float
        Parabolic period grading amplitude [nm].  The period at the
        centre of the stack is nominal; top and bottom periods are
        wider by this amount.  Typical: 0.0 to 0.15 nm.  Bilayer i
        (0 = top) gets grading_parabolic_nm * (2 z - 1)**2 with
        z = i / (n_bilayers - 1); a single bilayer counts as the centre.

    Returns
    -------
    MultilayerStack
        Refractive indices, thicknesses, and symbols for the full stack
        (top → bottom), **without** the substrate as a layer; the
        substrate index is in ``n_substrate``.
    """
    t = table or _default_table

    # Build layer list: top → bottom (without substrate)
    symbols: List[str] = []
    thicknesses_nm: List[float] = []

    # Handle gamma override: keep the period d_mo_nm + d_si_nm (it sets the
    # Bragg peak) and split it as gamma = d_Mo / (d_Mo + d_Si).
    d_mo = d_mo_nm
    d_si = d_si_nm
    if gamma is not None:
        if not (0.0 < gamma < 1.0):
            raise ValueError(f"gamma must be between 0 and 1 (exclusive), got {gamma}")
        period = d_mo_nm + d_si_nm
        d_mo = gamma * period
        d_si = period - d_mo

    # Capping layer (top)
    if capping_layer and d_cap_nm > 0:
        symbols.append(capping_layer)
        thicknesses_nm.append(d_cap_nm)

    # Mo/Si bilayers with optional period grading
    # Grading profile: period(z) = d0 + linear * z + parabolic * (2 z - 1)**2
    # where z = i / (N - 1) runs from 0 (top bilayer) to 1 (bottom bilayer)
    # Linear grading: period increases linearly from top to bottom
    # Parabolic grading: nominal period at the centre, +parabolic at top and bottom
    period0 = d_mo + d_si
    for i in range(n_bilayers):
        z = i / max(n_bilayers - 1, 1)  # 0 (top) to 1 (bottom)
        u = 2.0 * z - 1.0 if n_bilayers > 1 else 0.0  # -1 (top), 0 (centre), +1 (bottom)
        # Grading profile
        grad = grading_linear_nm * z + grading_parabolic_nm * u * u
        p_i = period0 + grad
        mo_i = d_mo + (d_mo / period0) * grad
        si_i = p_i - mo_i

        # Si on top of each bilayer: the stack is Si-terminated, so a cap
        # lies on Si and the bottom Mo layer on the substrate.  Ru-capped
        # mask blanks are Ru on the last Si layer (Yan et al., JVST B 25,
        # 1859, 2007, doi:10.1116/1.2799963: "Ru cap ... deposited onto a
        # Si-terminated, 50 pair Mo/Si ML"; van Setten et al., Proc. SPIE 7545,
        # 754503, 2010, doi:10.1117/12.864251: "The Ru-capped multilayer is
        # Si-terminated").
        # Up to v2.2.1 each bilayer was Mo then Si, which put the cap on Mo
        # and gave R = 0.647 instead of 0.732 for the default stack.
        symbols.append("Si")
        thicknesses_nm.append(si_i)
        symbols.append("Mo")
        thicknesses_nm.append(mo_i)

    # Compute refractive indices from CXRO
    nk_list: List[complex] = []
    for sym in symbols:
        nk_list.append(_nk(sym, energy_eV, t))

    n_layers = torch.tensor(nk_list, dtype=torch.complex128)
    thicknesses = torch.tensor(thicknesses_nm, dtype=torch.float64) * 1e-9  # m
    # The substrate is not a layer; the TMM takes its index separately.
    n_substrate = torch.tensor(_nk(substrate, energy_eV, t), dtype=torch.complex128)

    desc = (
        f"{capping_layer or 'none'}-capped Mo/Si × {n_bilayers} "
        f"({d_mo:.1f}/{d_si:.1f} nm) on {substrate}"
    )

    return MultilayerStack(
        n_layers=n_layers,
        thicknesses=thicknesses,
        symbols=symbols,
        description=desc,
        n_substrate=n_substrate,
    )


# ──────────────────────────────────────────────
# Interdiffusion / interface roughness correction
# ──────────────────────────────────────────────


def interdiffusion_correction(
    n_layers: torch.Tensor,
    thicknesses: torch.Tensor,
    sigma_nm: float = 0.5,
    n_interdiffused: complex | None = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Model interdiffusion / roughness by an intermediate layer per interface.

    Every internal interface (between layer i and layer i+1 of the given
    arrays) is replaced by a layer of thickness 2*sigma.  Half of it
    (sigma) is taken from the bottom of layer i and half from the top of
    layer i+1, so every bilayer period and the total thickness stay
    unchanged and the Bragg condition is preserved.  The top interface
    (incident medium -> layer 0) and the bottom interface (last layer ->
    substrate) are not modified.

    With the default intermediate index (the mean of the two neighbours)
    each interface reflection splits into two half steps 2*sigma apart.
    Its amplitude is reduced by cos(2 k_z sigma), which agrees with the
    Debye-Waller / Nevot-Croce factor exp(-2 k_z^2 sigma^2) to second
    order in k_z*sigma.  Example: 50 uncapped Mo/Si bilayers, 13.5 nm,
    6 deg, TE, sigma = 0.5 nm: R at 13.5 nm drops from 0.735 to 0.686,
    close to 0.681 from ``tmm.reflectivity(..., roughness_nm=0.5)``.

    Parameters
    ----------
    n_layers : (N,) complex128 tensor
        Refractive indices of the ideal stack.
    thicknesses : (N,) float64 tensor [m]
        Layer thicknesses.
    sigma_nm : float
        RMS interface width in nm (default: 0.5).  Must be >= 0.  Each
        inserted layer is 2*sigma thick.
    n_interdiffused : complex or None
        Refractive index of every inserted layer.  None (default) uses
        the mean of the two neighbouring indices at each interface.
        Pass a value (e.g. a MoSi2 index) to override it.

    Returns
    -------
    n_corrected : (2N-1,) complex128 tensor
        Refractive indices with one intermediate layer inserted after
        every layer except the last.
    d_corrected : (2N-1,) float64 tensor [m]
        Corresponding thicknesses; their sum equals ``thicknesses.sum()``.

    Raises
    ------
    ValueError
        If sigma_nm < 0, or if a layer is thinner than what it gives up
        (sigma for the first and the last layer, 2*sigma for all others).
    """
    if sigma_nm < 0.0:
        raise ValueError(f"sigma_nm must be >= 0, got {sigma_nm}")
    n_total = int(n_layers.shape[0])
    if n_total < 2:
        return n_layers.clone(), thicknesses.clone()

    w_iface = 2.0 * sigma_nm * 1e-9  # thickness of each inserted layer [m]
    # Each internal interface takes sigma (= w_iface / 2) from both
    # neighbours: the first and the last layer have one internal
    # interface, every other layer has two.
    sides = torch.full((n_total,), 2.0, dtype=torch.float64, device=thicknesses.device)
    sides[0] = 1.0
    sides[-1] = 1.0
    d_kept = thicknesses.to(torch.float64) - sides * (0.5 * w_iface)
    if bool((d_kept < 0.0).any()):
        raise ValueError(
            f"sigma_nm={sigma_nm} is too large: a layer is thinner than the "
            "material it has to give up to its interdiffused interfaces"
        )

    corrected_n: List[torch.Tensor] = []
    corrected_d: List[torch.Tensor] = []
    for i in range(n_total):
        corrected_n.append(n_layers[i].reshape(1).to(torch.complex128))
        corrected_d.append(d_kept[i].reshape(1))
        # Insert the intermediate layer after this layer (except the last)
        if i < n_total - 1:
            if n_interdiffused is None:
                n_mid = 0.5 * (n_layers[i] + n_layers[i + 1])
            else:
                n_mid = torch.tensor(
                    n_interdiffused, dtype=torch.complex128, device=n_layers.device
                )
            corrected_n.append(n_mid.reshape(1).to(torch.complex128))
            corrected_d.append(
                torch.tensor([w_iface], dtype=torch.float64, device=thicknesses.device)
            )

    return torch.cat(corrected_n), torch.cat(corrected_d)


# ──────────────────────────────────────────────
# Material dictionary (convenience for lookups)
# ──────────────────────────────────────────────


def default_materials(
    energy_eV: float = 91.84,
    table: CXROTable | None = None,
) -> Dict[str, complex]:
    """Refractive indices of common EUV mirror materials.

    Parameters
    ----------
    energy_eV : float
        Photon energy in eV (default: 91.84).
    table : CXROTable, optional
        CXRO table instance.

    Returns
    -------
    materials : dict of {symbol: complex}
        n + i*k per material.
    """
    symbols = ["Mo", "Si", "Ru", "Ta", "C", "B4C", "Si3N4", "SiO2"]
    result: Dict[str, complex] = {}
    for sym in symbols:
        try:
            result[sym] = _nk(sym, energy_eV, table)
        except KeyError:
            # Some compound symbols may not be in CXRO
            result[sym] = complex(1.0, 0.0)
    return result
