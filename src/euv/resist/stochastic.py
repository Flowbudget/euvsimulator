"""
Stochastic resist model — Poisson shot noise, LER / LWR extraction.

Theory
------
In EUV lithography at 13.5 nm (91.84 eV / photon), the photon flux is
intrinsically limited.  The discrete nature of photon absorption and
subsequent photoacid generation introduces **shot noise** — stochastic
fluctuations that manifest as:

1. **Line-edge roughness (LER)** — random deviations of the developed
   resist edge from its nominal position, characterised by the RMS
   displacement perpendicular to the edge.

2. **Line-width roughness (LWR)** — random variation in the width of a
   developed feature, measured from multiple line cuts along its length.

Under Poisson statistics, the relative uncertainty in the number of
absorbed photons N scales as:

    σ_N / μ_N ∝ 1 / √(N)  ∝ 1 / √(dose)

so both LER and LWR exhibit **1/√(dose) scaling** — a hallmark prediction
verified experimentally across EUV resists.

This module provides:

- ``PoissonShotNoise`` — overlays Poisson-distributed shot noise on acid
  concentration maps.
- ``extract_ler`` — extracts LER (1σ) from a developed binary contour by
  measuring edge-position deviations.
- ``extract_lwr`` — extracts LWR (1σ) from multiple line-width
  measurements along a developed feature.
- ``ler_lwr_estimate`` — convenience function that computes both LER and
  LWR from a noisy acid map and a developed contour.
- ``rms_scaling_check`` — verifies the  1 / √(dose)  scaling law.

All operations are implemented in PyTorch.

References
----------
R.L. Brainard et al., "Shot noise and LER in EUV photoresists",
    Proc. SPIE 5376, 74–85 (2004).

G.M. Gallatin, "Resist blur and line-edge roughness",
    Proc. SPIE 5753, 38–53 (2005).

P.P. Naulleau et al., "The role of photon shot noise in the
    lithographic performance of EUV resists",
    J. Vac. Sci. Technol. B 24(3), 1300–1304 (2006).
"""

from __future__ import annotations

import torch
from typing import Tuple, Optional


# ──────────────────────────────────────────────
# Poisson shot-noise overlay
# ──────────────────────────────────────────────


def poisson_shot_noise(
    acid: torch.Tensor,
    dose: torch.Tensor | None = None,
    quantum_efficiency: float = 0.04,
    photon_energy_eV: float = 91.84,
    dose_to_energy_factor: float = 6.24e15,
    voxel_area_cm2: float = 1e-14,
    return_photon_count: bool = False,
    rng: torch.Generator | None = None,
) -> torch.Tensor | Tuple[torch.Tensor, torch.Tensor]:
    """Overlay Poisson shot noise on a photoacid concentration map.

    The deterministic acid concentration is interpreted as the *mean*
    of a Poisson process.  A noisy realisation is drawn from:

        N_acid ~ Poisson(λ),   where λ = acid · scale

    where *scale* converts the continuous acid concentration to a
    discrete molecule count per voxel.  The result is then scaled back
    to the original units so the output can be compared directly with
    the noise-free input.

    Optionally, the mean photon count per voxel is computed from the
    incident dose via:

        N_ph = dose [mJ/cm²] × voxel_area [cm²] / E_ph [mJ]

    and the acid count is λ = quantum_efficiency × N_ph.  When *dose*
    is not provided, *acid* is used directly as the Poisson rate
    parameter (after converting it to a discrete count by a normalising
    factor derived from *quantum_efficiency*).

    Parameters
    ----------
    acid : torch.Tensor
        Deterministic (mean) acid concentration.  Any shape.
    dose : torch.Tensor, optional
        Incident EUV dose map [mJ/cm²].  Same shape as *acid*.
        When provided, the mean photon count is computed from the dose
        and the Poisson rate is set to Q × N_ph, where N_ph is the
        number of absorbed photons in each voxel, so the shot-noise
        magnitude correctly reflects the number of photons actually
        absorbed.
    quantum_efficiency : float
        Average number of acid molecules generated per absorbed EUV
        photon.  Typical EUV CAR values: 0.02–0.10.  Default 0.04.
    photon_energy_eV : float
        EUV photon energy in eV.  Default 91.84 (13.5 nm).
    dose_to_energy_factor : float
        Conversion factor: 1 mJ/cm² corresponds to this many eV/cm².
        Default 6.24e15 (from 1 mJ = 6.24e15 eV).
    voxel_area_cm2 : float
        Area of each grid voxel in cm².  Default 1e-14 (corresponds to
        1 nm × 1 nm pixels).  This converts the areal photon flux
        (photons/cm²) to a per-voxel count.
    return_photon_count : bool
        If ``True``, also return the mean photon-per-voxel tensor.
    rng : torch.Generator, optional
        Random number generator for reproducibility.

    Returns
    -------
    noisy_acid : torch.Tensor
        Acid concentration with shot noise.  Same shape as *acid*.
    photon_count : torch.Tensor, optional
        Mean number of absorbed photons per voxel.  Only returned when
        *return_photon_count* is ``True``.

    Notes
    -----
    The Poisson sampling is done via ``torch.poisson``.  The result is
    a true stochastic realisation — call repeatedly to obtain different
    noise instances.
    """
    if dose is not None:
        # Number of EUV photons absorbed per voxel:
        #   N_ph = dose [mJ/cm²] × voxel_area [cm²] × dose_to_energy_factor
        #          [eV per mJ/cm²] / photon_energy_eV
        #        = dose × voxel_area_cm2 × dose_to_energy_factor / photon_energy_eV
        photons_per_voxel = (
            dose * voxel_area_cm2 * dose_to_energy_factor / photon_energy_eV
        )
        lam = photons_per_voxel * quantum_efficiency
    else:
        # Use acid directly as the Poisson rate, scaled to a useful
        # range.  Without a separate dose field we cannot know the
        # absolute photon count, so we scale the acid map to a
        # reasonable mean count range.
        lam = acid * 100.0  # heuristic scale factor
        photons_per_voxel = None

    # Ensure lam is non-negative (clamp to zero)
    lam = torch.clamp(lam, min=0.0)

    # Sample Poisson: torch.poisson draws from Pois(λ) for each
    # element.  The result is a *count* (integer-valued).
    noisy_count = torch.poisson(lam, generator=rng)

    # Rescale back to the original concentration units.
    if dose is not None:
        noisy_acid = noisy_count / (photons_per_voxel.clamp(min=1e-30))
        noisy_acid = noisy_acid * quantum_efficiency
    else:
        noisy_acid = noisy_count / 100.0

    if return_photon_count and photons_per_voxel is not None:
        return noisy_acid, photons_per_voxel
    elif return_photon_count:
        # Return estimated counts even without dose input
        return noisy_acid, (lam / quantum_efficiency).detach()
    return noisy_acid


def _generate_photon_shot_noise(
    acid: torch.Tensor,
    dose: torch.Tensor,
    quantum_efficiency: float = 0.04,
    photon_energy_eV: float = 91.84,
    dose_to_energy_factor: float = 6.24e15,
    voxel_area_cm2: float = 1e-14,
    rng: torch.Generator | None = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Low-level Poisson sampling returning both count and rate.

    This is the core Poisson engine used internally by
    :func:`poisson_shot_noise` when a dose map is provided.  It is
    exposed for advanced users who need direct access to the raw
    discrete counts.

    Parameters
    ----------
    acid : torch.Tensor
        Deterministic acid concentration.  Any shape.
    dose : torch.Tensor
        EUV dose map [mJ/cm²].  Same shape as *acid*.
    quantum_efficiency : float
        Acid molecules per absorbed photon.  Default 0.04.
    photon_energy_eV : float
        EUV photon energy [eV].  Default 91.84.
    dose_to_energy_factor : float
        eV per mJ/cm².  Default 6.24e15.
    voxel_area_cm2 : float
        Area of each grid voxel in cm².  Default 1e-14.
    rng : torch.Generator, optional
        RNG for reproducibility.

    Returns
    -------
    noisy_acid : torch.Tensor
        Shot-noise-corrupted acid concentration.  Same shape as *acid*.
    photons_per_voxel : torch.Tensor
        Mean photon count per voxel.
    """
    photons_per_voxel = (
        dose * voxel_area_cm2 * dose_to_energy_factor / photon_energy_eV
    )
    lam = photons_per_voxel * quantum_efficiency
    lam = torch.clamp(lam, min=0.0)
    noisy_count = torch.poisson(lam, generator=rng)
    noisy_acid = noisy_count / photons_per_voxel.clamp(min=1e-30)
    noisy_acid = noisy_acid * quantum_efficiency
    return noisy_acid, photons_per_voxel


# ──────────────────────────────────────────────
# LER extraction from developed contours
# ──────────────────────────────────────────────


def extract_edges(
    developed: torch.Tensor,
    threshold: float = 0.5,
    dx: float = 1.0,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Extract left and right edges from a developed binary contour.

    The *developed* tensor is a 2D binary mask (``H × W``) where 1
    indicates developed (dissolved) and 0 indicates undeveloped
    (remaining resist).  For each row, the left edge is the first
    *undeveloped* pixel (0 → 1 transition) and the right edge is the
    last undeveloped pixel (1 → 0 transition), measured from the
    leftmost side of the feature.

    Parameters
    ----------
    developed : torch.Tensor
        2D developed binary mask.  Shape ``(H, W)``.  Values should
        be 0 (undeveloped) or 1 (developed).
    threshold : float
        Binarisation threshold.  Default 0.5.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.

    Returns
    -------
    left_edge : torch.Tensor
        Left-edge positions [nm].  Shape ``(H,)``.  ``NaN`` for rows
        where no edge is detected.
    right_edge : torch.Tensor
        Right-edge positions [nm].  Shape ``(H,)``.  ``NaN`` for rows
        where no edge is detected.
    """
    if developed.ndim != 2:
        raise ValueError(f"Expected 2D tensor, got {developed.ndim}D")

    H, W = developed.shape

    # Binarise
    binary = (developed > threshold).float()  # 1 = developed

    # For a positive-tone line, the remaining resist (CD bar) is
    # the region where binary == 0 (undeveloped).
    # We find the leftmost and rightmost undeveloped pixel per row.
    # Invert: 1 = undeveloped (the line feature)
    undeveloped = 1.0 - binary  # 1 = resist remaining

    # Left edge: first undeveloped pixel in each row
    # Right edge: last undeveloped pixel in each row
    # Use argmax on the undeveloped mask (returns first True index)
    left_idx = torch.argmax(undeveloped, dim=1)  # (H,)

    # Right edge: argmax on the reversed undeveloped mask
    rev = undeveloped.flip(dims=[1])
    right_idx_rev = torch.argmax(rev, dim=1)
    right_idx = W - 1 - right_idx_rev  # (H,)

    # Where there is no undeveloped pixel, argmax returns 0
    # which is indistinguishable from a valid left edge at col 0.
    # Check if any undeveloped pixel exists in each row.
    has_feature = undeveloped.sum(dim=1) > 0.5  # (H,) bool

    # Convert to nm
    left_edge = left_idx.float() * dx
    right_edge = right_idx.float() * dx

    # Set NaN for rows without a feature
    left_edge[~has_feature] = float("nan")
    right_edge[~has_feature] = float("nan")

    return left_edge, right_edge


def extract_ler(
    developed: torch.Tensor,
    threshold: float = 0.5,
    dx: float = 1.0,
    edge: str = "both",
) -> float:
    """Extract line-edge roughness (LER) from a developed contour.

    LER is defined as the RMS deviation of an edge from its mean
    position along the length of the feature:

        LER = √(⟨(x(z) − ⟨x⟩)²⟩)

    where *x(z)* is the edge position at row *z* and ⟨x⟩ is the mean
    edge position.

    Parameters
    ----------
    developed : torch.Tensor
        2D binary developed mask.  Shape ``(H, W)``.
    threshold : float
        Binarisation threshold.  Default 0.5.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.
    edge : str
        Which edge to measure.  ``"left"``, ``"right"``, or
        ``"both"`` (default).  When ``"both"``, the combined LER is
        the RMS of the left and right edge deviations averaged.

    Returns
    -------
    ler : float
        Line-edge roughness [nm] (1σ).

    See Also
    --------
    extract_edges : Low-level edge extraction used internally.
    extract_lwr : Line-width roughness extraction.
    """
    left_edge, right_edge = extract_edges(developed, threshold, dx)

    # Remove NaN rows
    finite_mask = ~(torch.isnan(left_edge) | torch.isnan(right_edge))
    if finite_mask.sum() < 3:
        return float("nan")

    left_finite = left_edge[finite_mask]
    right_finite = right_edge[finite_mask]

    if edge == "left":
        deviations = left_finite - left_finite.mean()
        return float(torch.sqrt((deviations ** 2).mean()))
    elif edge == "right":
        deviations = right_finite - right_finite.mean()
        return float(torch.sqrt((deviations ** 2).mean()))
    else:  # "both"
        # Combine left and right deviations
        left_dev = left_finite - left_finite.mean()
        right_dev = right_finite - right_finite.mean()
        all_dev = torch.cat([left_dev, right_dev])
        return float(torch.sqrt((all_dev ** 2).mean()))


# ──────────────────────────────────────────────
# LWR extraction from multiple line cuts
# ──────────────────────────────────────────────


def extract_lwr(
    developed: torch.Tensor,
    threshold: float = 0.5,
    dx: float = 1.0,
) -> float:
    r"""Extract line-width roughness (LWR) from a developed contour.

    LWR is defined as the standard deviation of the line width (CD)
    measured at multiple positions along the feature:

        LWR = σ(CD(z))  =  √(⟨(CD(z) − ⟨CD⟩)²⟩)

    where CD(z) = right_edge(z) − left_edge(z).

    For a resist line, the LWR and LER are related by
    LWR ≈ √(2) × LER when the two edges fluctuate independently.

    Parameters
    ----------
    developed : torch.Tensor
        2D binary developed mask.  Shape ``(H, W)``.
    threshold : float
        Binarisation threshold.  Default 0.5.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.

    Returns
    -------
    lwr : float
        Line-width roughness [nm] (1σ).

    See Also
    --------
    extract_edges : Low-level edge extraction.
    extract_ler : LER extraction (edge roughness).
    """
    left_edge, right_edge = extract_edges(developed, threshold, dx)

    # Line width per row
    width = right_edge - left_edge

    # Remove NaN
    finite = ~torch.isnan(width)
    if finite.sum() < 3:
        return float("nan")

    width_finite = width[finite]
    lwr_val = float(torch.std(width_finite, unbiased=False))
    return lwr_val


# ──────────────────────────────────────────────
# Combined LER + LWR estimate
# ──────────────────────────────────────────────


def ler_lwr_estimate(
    acid: torch.Tensor,
    dose: torch.Tensor | None = None,
    develop_threshold: float = 0.3,
    quantum_efficiency: float = 0.04,
    shot_noise_rng: torch.Generator | None = None,
    dx: float = 1.0,
    n_realisations: int = 1,
    average: bool = True,
) -> dict:
    """Compute LER and LWR from a stochastic resist realisation.

    This is a convenience pipeline:

        1. Apply Poisson shot noise to the deterministic acid map.
        2. Binarise via threshold development.
        3. Extract LER and LWR from the developed contour.

    When *n_realisations* > 1, multiple independent noise realisations
    are drawn and the LER/LWR are averaged across them.

    Parameters
    ----------
    acid : torch.Tensor
        Deterministic acid concentration.  2D ``(H, W)``.
    dose : torch.Tensor, optional
        EUV dose map [mJ/cm²].  Same shape as *acid*.  Needed for
        physically accurate shot-noise scaling.  When ``None``, the
        acid map is used heuristically.
    develop_threshold : float
        Development threshold on acid concentration.  Default 0.3.
    quantum_efficiency : float
        Acid molecules per absorbed photon.  Default 0.04.
    shot_noise_rng : torch.Generator, optional
        RNG for Poisson sampling.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.
    n_realisations : int
        Number of independent noise realisations.  Default 1.
    average : bool
        If ``True`` (default), return the mean LER/LWR across all
        realisations.  If ``False``, return lists of per-realisations
        values.

    Returns
    -------
    result : dict
        Keys:

        - ``"ler"`` — LER [nm] (scalar or list).
        - ``"lwr"`` — LWR [nm] (scalar or list).
        - ``"mean_acid"`` — mean acid concentration in the feature
          region (scalar).
        - ``"mean_dose"`` — mean dose in the feature region, or
          ``None`` if *dose* was not provided.
    """
    ler_vals = []
    lwr_vals = []

    for _ in range(n_realisations):
        # Apply shot noise
        noisy = poisson_shot_noise(
            acid, dose=dose,
            quantum_efficiency=quantum_efficiency,
            rng=shot_noise_rng,
        )

        # Threshold development
        developed = (noisy > develop_threshold).float()

        # Extract LER/LWR
        ler = extract_ler(developed, dx=dx)
        lwr = extract_lwr(developed, dx=dx)
        ler_vals.append(ler)
        lwr_vals.append(lwr)

    # Baseline statistics
    if dose is not None:
        mean_dose = float(dose[dose > 0].mean()) if (dose > 0).any() else 0.0
    else:
        mean_dose = None
    mean_acid = float(acid[acid > 0].mean()) if (acid > 0).any() else 0.0

    result: dict = {"mean_acid": mean_acid, "mean_dose": mean_dose}

    if average and n_realisations > 1:
        result["ler"] = float(torch.tensor(ler_vals).nanmean())
        result["lwr"] = float(torch.tensor(lwr_vals).nanmean())
    elif n_realisations == 1:
        result["ler"] = ler_vals[0]
        result["lwr"] = lwr_vals[0]
    else:
        result["ler"] = ler_vals
        result["lwr"] = lwr_vals

    return result


# ──────────────────────────────────────────────
# 1 / √(dose) scaling verification
# ──────────────────────────────────────────────


def rms_scaling_check(
    base_acid: torch.Tensor,
    dose_levels: torch.Tensor,
    n_realisations: int = 10,
    develop_threshold: float = 0.3,
    quantum_efficiency: float = 0.04,
    dx: float = 1.0,
    seed: int = 42,
) -> dict:
    r"""Verify the  1 / √(dose)  LER scaling law.

    For each dose level in *dose_levels*, the base acid map is scaled
    linearly (acid ∝ dose) to represent the deterministic acid at that
    dose, then Poisson shot noise is applied, LER/LWR are extracted,
    and the results are averaged across *n_realisations*.

    The theoretical prediction is:

        LER(dose) ∝ LER₀ · √(dose₀ / dose)  =  LER₀ / √(dose / dose₀)

    i.e. LER · √(dose) ≈ constant for a given resist system.

    Parameters
    ----------
    base_acid : torch.Tensor
        Reference acid concentration map at a reference dose.
        2D ``(H, W)``.
    dose_levels : torch.Tensor
        1D tensor of dose values [mJ/cm²] to test.
    n_realisations : int
        Number of stochastic realisations per dose level.  Default 10.
    develop_threshold : float
        Development threshold.  Default 0.3.
    quantum_efficiency : float
        Acid molecules per absorbed photon.  Default 0.04.
    dx : float
        Grid spacing [nm/pixel].  Default 1.0.
    seed : int
        RNG seed for reproducibility.  Default 42.

    Returns
    -------
    result : dict
        Keys:

        - ``"dose_levels"`` — the input *dose_levels* tensor.
        - ``"ler"`` — LER at each dose level [nm], shape
          ``(len(dose_levels),)``.
        - ``"lwr"`` — LWR at each dose level [nm], same shape.
        - ``"ler_sqrt_dose"`` — LER × √(dose) product — should be
          approximately constant.
        - ``"lwr_sqrt_dose"`` — LWR × √(dose) product.
        - ``"theoretical_exponent"`` — the exponent *α* from a
          power-law fit LER ∝ dose⁻ᵅ.  Should be close to 0.5.
        - ``"fit_dose_exponent"`` — exponent from power-law fit to
          LER vs dose.
    """
    device = base_acid.device
    ler_vals = torch.zeros(len(dose_levels), device=device)
    lwr_vals = torch.zeros(len(dose_levels), device=device)

    for i, d in enumerate(dose_levels):
        # Scale acid proportionally to dose
        # Assume base_acid corresponds to dose_levels[0] or a reference
        ref_dose = float(dose_levels.max())
        acid_scaled = base_acid * (float(d) / ref_dose)

        # Create a dose map tensor of the same shape
        dose_map = torch.full_like(base_acid, float(d))

        # Run multiple realisations
        ler_i = []
        lwr_i = []
        for _ in range(n_realisations):
            rng = torch.Generator(device=device).manual_seed(seed + i * n_realisations + _)
            noisy = poisson_shot_noise(
                acid_scaled, dose=dose_map,
                quantum_efficiency=quantum_efficiency,
                rng=rng,
            )
            developed = (noisy > develop_threshold).float()
            ler_i.append(extract_ler(developed, dx=dx))
            lwr_i.append(extract_lwr(developed, dx=dx))

        ler_vals[i] = torch.tensor(ler_i, device=device).nanmean()
        lwr_vals[i] = torch.tensor(lwr_i, device=device).nanmean()

    # Product LER × √(dose) — should be constant
    sqrt_dose = torch.sqrt(dose_levels)
    ler_sqrt_dose = ler_vals * sqrt_dose
    lwr_sqrt_dose = lwr_vals * sqrt_dose

    # Power-law fit: log10(LER) = α · log10(dose) + β
    # => α ≈ -0.5 for 1/√(dose)
    finite = (ler_vals > 0) & (dose_levels > 0)
    if finite.sum() >= 3:
        log_dose = torch.log10(dose_levels[finite])
        log_ler = torch.log10(ler_vals[finite])
        A = torch.stack([log_dose, torch.ones_like(log_dose)], dim=1)
        coeffs, *_ = torch.linalg.lstsq(A, log_ler.unsqueeze(1))
        exponent = float(coeffs[0, 0])
    else:
        exponent = float("nan")

    return {
        "dose_levels": dose_levels,
        "ler": ler_vals,
        "lwr": lwr_vals,
        "ler_sqrt_dose": ler_sqrt_dose,
        "lwr_sqrt_dose": lwr_sqrt_dose,
        "fit_dose_exponent": exponent,
        "theoretical_exponent": -0.5,
    }