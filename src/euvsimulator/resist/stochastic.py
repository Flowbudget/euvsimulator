"""Stochastic resist model — Poisson shot noise, LER / LWR extraction.

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
  LWR from a noisy, SE-blurred acid map and its developed contour.
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

import math
from typing import Tuple

import torch

# ──────────────────────────────────────────────
# Poisson shot-noise overlay
# ──────────────────────────────────────────────


def poisson_shot_noise(
    acid: torch.Tensor,
    dose: torch.Tensor | None = None,
    quantum_efficiency: float = 0.04,
    photon_energy_eV: float = 91.84,
    dose_to_energy_factor: float = 6.241509074e15,
    voxel_area_cm2: float | None = None,
    dx_nm: float = 1.0,
    dy_nm: float | None = None,
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
        EUV photon energy in eV.  Default 91.84 eV
        (corresponding to 13.5 nm wavelength via E = hc/λ).
        Use the derived energy from wavelength for consistency.
    dose_to_energy_factor : float
        Conversion factor: 1 mJ/cm² corresponds to this many eV/cm².
        Default 6.241509074e15 (exact: 1e-3 J / 1.602176634e-19 J/eV).
    voxel_area_cm2 : float, optional
        Area of each grid voxel in cm².  If not provided, computed from
        dx_nm and dy_nm as (dx_nm * dy_nm * 1e-14).
        Default None → computed from dx_nm, dy_nm.
    dx_nm : float
        Pixel spacing in x direction [nm].  Default 1.0.
    dy_nm : float, optional
        Pixel spacing in y direction [nm].  If None, assumed equal to dx_nm.
        Default None.
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
    # Compute voxel area from dx, dy if not provided
    if voxel_area_cm2 is None:
        dy = dy_nm if dy_nm is not None else dx_nm
        voxel_area_cm2 = dx_nm * dy * 1e-14  # (nm * nm) * 1e-14 = cm²

    if dose is not None:
        # Number of EUV photons absorbed per voxel:
        #   N_ph = dose [mJ/cm²] × voxel_area [cm²] × dose_to_energy_factor
        #          [eV per mJ/cm²] / photon_energy_eV
        #        = dose × voxel_area_cm2 × dose_to_energy_factor / photon_energy_eV
        photons_per_voxel = dose * voxel_area_cm2 * dose_to_energy_factor / photon_energy_eV
        lam = photons_per_voxel * quantum_efficiency
    else:
        # Legacy heuristic fallback (for backward compatibility only).
        # Pipeline should always provide dose map.
        lam = acid * 100.0  # heuristic scale factor
        photons_per_voxel = None

    # Ensure lam is non-negative (clamp to zero) - handle NaN too
    lam = torch.nan_to_num(lam, nan=0.0, posinf=0.0, neginf=0.0)
    lam = torch.clamp(lam, min=0.0)

    # Sample Poisson: torch.poisson draws from Pois(λ) for each
    # element.  The result is a *count* (integer-valued).
    noisy_count = torch.poisson(lam, generator=rng)

    # Rescale back to the original concentration units.
    if dose is not None:
        # photons_per_voxel already computed above
        assert photons_per_voxel is not None
        mean_acid_count = photons_per_voxel * quantum_efficiency
        # Rescale Poisson count to match deterministic acid concentration.
        # Deterministic acid concentration is in `acid` tensor.
        # Mean acid molecule count = photons_per_voxel * QE.
        # noisy_acid = acid * (noisy_count / mean_acid_count)
        noisy_acid = acid * (noisy_count / mean_acid_count.clamp(min=1e-30))
    else:
        # Legacy heuristic fallback (for backward compatibility only).
        # Pipeline should always provide dose map.
        noisy_acid = noisy_count / 100.0

    if return_photon_count and photons_per_voxel is not None:
        return noisy_acid, photons_per_voxel
    elif return_photon_count:
        # Return estimated counts even without dose input
        return noisy_acid, (lam / quantum_efficiency).detach()
    return noisy_acid


# ──────────────────────────────────────────────
# Event-based photon deposition with SE-PSF
# (physically clean shot-noise model — Step 1 of the 2026-08
#  stochastic physics design)
# ──────────────────────────────────────────────


def photon_deposition_shot_noise(
    dose: torch.Tensor,
    se_blur_nm: float,
    dx_nm: float = 1.0,
    dy_nm: float | None = None,
    photon_energy_eV: float = 91.84014696703977,
    dose_to_energy_factor: float = 6.241509074e15,
    absorption: float = 1.0,
    seed: int | None = None,
    rng: torch.Generator | None = None,
) -> torch.Tensor:
    """Event-based photon shot noise with secondary-electron PSF.

    This is the physically clean shot-noise model described in the
    2026-08 stochastic physics design (Step 1):

        1. Mean photon count per voxel:
               N_bar(x) = dose(x) * A_voxel * f / E_photon * absorption
        2. Discrete photon events:
               N(x) ~ Poisson(N_bar(x))
        3. Energy deposition via SE-PSF (Gaussian blur):
               E_dep(x) = PSF_sigma * N(x)
               E_bar(x) = PSF_sigma * N_bar(x)
        4. Effective noisy dose (spatially correlated):
               D_eff(x) = blur(dose)(x) * E_dep(x) / E_bar(x)
           with blur the same SE-PSF.  Since E[E_dep] = E_bar, the
           mean is E[D_eff] = blur(dose), not dose: the SE-PSF
           transports the deposited energy (equal to dose only for
           se_blur_nm <= 0 or a uniform dose map).

    The SE-PSF correlates the noise over the physical SE blur length
    sigma = *se_blur_nm* and makes the relative noise amplitude
    grid-invariant (the voxel area cancels in sigma_rel^2).

    Parameters
    ----------
    dose : torch.Tensor
        Deterministic dose map [mJ/cm²].  Shape ``(H, W)``.
    se_blur_nm : float
        Secondary-electron blur sigma [nm].  ``<= 0`` disables the
        PSF (white Poisson noise, E_dep = N, E_bar = N_bar).
    dx_nm : float
        Grid spacing in x [nm/pixel].  Default 1.0.
    dy_nm : float, optional
        Grid spacing in y [nm/pixel].  If None, assumed equal to
        *dx_nm*.  Default None.
    photon_energy_eV : float
        EUV photon energy [eV].  Default 91.84014696703977
        (13.5 nm via E = hc/lambda).
    dose_to_energy_factor : float
        eV per (mJ/cm²).  Default 6.241509074e15 (exact).
    absorption : float
        Fraction of incident photons absorbed (eta_abs).  Default
        1.0 (all photons absorbed).  Physically 0 < absorption <= 1.
    seed : int, optional
        RNG seed for reproducible Poisson draws.  Ignored when
        *rng* is provided.  Default None: the fresh generator is
        seeded from a non-deterministic source (Generator.seed()),
        so repeated calls give independent realisations.
    rng : torch.Generator, optional
        Explicit RNG.  Takes precedence over *seed*.  Default None.

    Returns
    -------
    d_eff : torch.Tensor
        Effective noisy dose [mJ/cm²].  Same shape as *dose*.
        E[D_eff] = blur(dose), the SE-blurred dose (equal to *dose*
        only for se_blur_nm <= 0 or a uniform dose map); spatially
        correlated over sigma = *se_blur_nm*.
    """
    # 1. Mean photon count per voxel
    dy = dy_nm if dy_nm is not None else dx_nm
    voxel_area_cm2 = dx_nm * dy * 1e-14  # (nm * nm) * 1e-14 = cm²
    n_bar = dose * voxel_area_cm2 * dose_to_energy_factor / photon_energy_eV * absorption
    n_bar = torch.clamp(n_bar, min=0.0)  # physical: no negative counts

    # 2. Discrete Poisson photon events
    if rng is None:
        rng = torch.Generator(device=dose.device)
        if seed is not None:
            rng.manual_seed(seed)
        else:
            # A fresh torch.Generator starts from a fixed default seed
            # (67280421310721); seed it non-deterministically.
            rng.seed()
    n_events = torch.poisson(n_bar, generator=rng)  # integer counts

    # 3./4. SE-PSF energy deposition (or identity for se_blur <= 0)
    from euvsimulator.resist.exposure import gaussian_se_blur

    if se_blur_nm > 0:
        e_dep = gaussian_se_blur(n_events.to(dose.dtype), sigma=se_blur_nm, dx=dx_nm)
        e_bar = gaussian_se_blur(n_bar, sigma=se_blur_nm, dx=dx_nm)
    else:
        e_dep = n_events.to(dose.dtype)
        e_bar = n_bar

    # 5. Effective noisy dose (numerical guard against div-by-zero)
    # Option-C SE-blur path consistency: the mean
    # energy density is blur(dose) (SE-PSF transport), so the ratio
    # e_dep/e_bar is centred on blur(dose), not on the raw dose.
    # Algebraically d_eff == blur(N)*E_ph/(A_voxel*f) (A1 == A2).
    # For se_blur_nm <= 0, gaussian_se_blur returns dose unchanged.
    blur_dose = gaussian_se_blur(dose, sigma=se_blur_nm, dx=dx_nm)
    d_eff = blur_dose * e_dep / e_bar.clamp(min=1e-30)

    return d_eff


# ──────────────────────────────────────────────
# LER extraction from developed contours
# ──────────────────────────────────────────────


def extract_edges(
    developed: torch.Tensor,
    threshold: float = 0.5,
    dx: float = 1.0,
    intensity: torch.Tensor | None = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Extract left and right edges from a developed binary contour.

    The *developed* tensor is a 2D binary mask (``H × W``) where 1
    indicates developed (dissolved) and 0 indicates undeveloped
    (remaining resist).  For each row, the left edge is the first
    *undeveloped* pixel (0 → 1 transition) and the right edge is the
    last undeveloped pixel (1 → 0 transition), measured from the
    leftmost side of the feature.

    If *intensity* (a continuous field, e.g. acid concentration) is
    provided, the edge position is refined by LINEAR INTERPOLATION of
    the threshold crossing between the two neighbouring pixels.  This
    removes the integer-pixel quantisation of the edge position
    (sub-pixel resolution).  When *intensity* is None, the edge is
    placed at the integer pixel index (legacy behaviour).

    The rows are treated as periodic (one line per period).  If the
    line straddles the array boundary -- resist in both the first and
    the last column of most rows that have a developed pixel -- all
    rows are rolled by one common shift so that they start in the
    space, at the column developed in most rows, and the edges are
    measured there.  The positions are then unwrapped: measured from
    column 0 but continuing past ``W * dx``, so ``right - left`` is
    the line width.  Any other field is measured exactly as without
    this step.

    Parameters
    ----------
    developed : torch.Tensor
        2D developed binary mask.  Shape ``(H, W)``.  Values should
        be 0 (undeveloped) or 1 (developed).
    threshold : float
        Binarisation threshold.  Default 0.5.  Also the level at
        which the *intensity* crossing is interpolated.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.
    intensity : torch.Tensor, optional
        Continuous field with the same shape as *developed*
        (e.g. acid concentration).  The threshold crossing of this
        field defines the sub-pixel edge position.  Default None
        (integer-pixel edges, legacy behaviour).

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
    if intensity is not None and intensity.shape != developed.shape:
        raise ValueError(
            f"intensity shape {tuple(intensity.shape)} does not match "
            f"developed shape {tuple(developed.shape)}"
        )

    H, W = developed.shape

    # Binarise
    binary = (developed > threshold).float()  # 1 = developed

    # Periodic rows. A line across the array boundary gives columns 0 and
    # W-1 as its edges in every row (the RCWA mask line until 2026-10:
    # LER = LWR = 0, line width about the pitch). When the line
    # straddles the boundary -- resist in both column 0 and column W-1 of
    # most rows that have a developed pixel -- roll all rows by one common
    # shift (positions stay comparable between rows) so that they start in
    # the space, at the column developed in most rows, and append that
    # column once more at the end, so a line ending in the last rolled
    # column keeps its developed neighbour for the sub-pixel crossing.
    # Isolated wrapping rows (resist residue at both ends of a row whose
    # line lies inside the array) keep the measurement they had before:
    # rolling would only move their mis-measured edge (the stochastic
    # regression pins contain such rows, 18 of 4096 at grid 256).
    shift = 0
    has_space = binary.sum(dim=1) > 0.5
    wraps = (binary[:, 0] < 0.5) & (binary[:, -1] < 0.5) & has_space
    if 2 * int(wraps.sum()) > int(has_space.sum()):
        shift = int(torch.argmax(binary.sum(dim=0)))
    if shift:
        binary = torch.roll(binary, -shift, dims=1)
        binary = torch.cat([binary, binary[:, :1]], dim=1)
        if intensity is not None:
            intensity = torch.roll(intensity, -shift, dims=1)
            intensity = torch.cat([intensity, intensity[:, :1]], dim=1)
        W = W + 1

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

    if intensity is not None:
        # Sub-pixel refinement: linearly interpolate the threshold
        # crossing of the continuous field between the two pixels
        # bracketing each edge.
        I = intensity
        work_dtype = I.dtype

        # --- left edge: crossing between left_idx-1 (developed,
        #     I > threshold) and left_idx (undeveloped, I <= threshold)
        left_pos = left_idx.to(work_dtype)
        valid_left = has_feature & (left_idx > 0)
        if valid_left.any():
            rows = torch.nonzero(valid_left).flatten()
            i = left_idx[rows]
            a = I[rows, i - 1]  # developed neighbour
            b = I[rows, i]  # undeveloped pixel
            denom = b - a
            frac = torch.where(
                denom.abs() > 1e-12,
                (threshold - a) / denom,
                torch.full_like(denom, 0.5),
            )
            frac = frac.clamp(0.0, 1.0)
            left_pos[rows] = (i - 1).to(work_dtype) + frac

        # --- right edge: crossing between right_idx (undeveloped,
        #     I <= threshold) and right_idx+1 (developed, I > threshold)
        right_pos = right_idx.to(work_dtype)
        valid_right = has_feature & (right_idx < W - 1)
        if valid_right.any():
            rows = torch.nonzero(valid_right).flatten()
            i = right_idx[rows]
            a = I[rows, i]  # undeveloped pixel
            b = I[rows, i + 1]  # developed neighbour
            denom = b - a
            frac = torch.where(
                denom.abs() > 1e-12,
                (threshold - a) / denom,
                torch.full_like(denom, 0.5),
            )
            frac = frac.clamp(0.0, 1.0)
            right_pos[rows] = i.to(work_dtype) + frac

        left_edge = left_pos * dx
        right_edge = right_pos * dx
    else:
        # Legacy: integer-pixel edge positions
        left_edge = left_idx.float() * dx
        right_edge = right_idx.float() * dx
    if shift:
        # back to the input's column frame, unwrapped (see the docstring)
        left_edge = left_edge + shift * dx
        right_edge = right_edge + shift * dx

    # Set NaN for rows without a feature
    left_edge[~has_feature] = float("nan")
    right_edge[~has_feature] = float("nan")

    return left_edge, right_edge


def residue_island_fraction(developed: torch.Tensor, threshold: float = 0.5) -> float:
    """Fraction of rows with resist in more than one separate segment.

    :func:`extract_edges` takes the first and the last resist pixel of a row,
    so resist residue detached from the line (an island in the space) counts
    as line and widens it. With development-cell noise this happens in
    32-85 % of the rows of the MET-2D and NXE1716 anchors; without noise in
    none. This diagnostic reports that share; it does
    not change the edges, CD or LER.

    The rows are periodic: resist in the first and the last column is one
    segment. A row without resist, or with resist everywhere, has no island.

    Parameters
    ----------
    developed : torch.Tensor
        2D field ``(H, W)``, developed (dissolved) where ``> threshold``.
    threshold : float
        Binarisation threshold, the one passed to :func:`extract_edges`.

    Returns
    -------
    float
        Share of the ``H`` rows with two or more resist segments.
    """
    if developed.ndim != 2:
        raise ValueError(f"Expected 2D tensor, got {developed.ndim}D")
    resist = developed <= threshold  # True = resist remains
    # A segment starts where resist follows a developed pixel (periodic).
    starts = resist & ~torch.roll(resist, 1, dims=1)
    n_segments = starts.sum(dim=1)
    return float((n_segments >= 2).double().mean()) if resist.shape[0] else float("nan")


def extract_ler(
    developed: torch.Tensor,
    threshold: float = 0.5,
    dx: float = 1.0,
    edge: str = "both",
    intensity: torch.Tensor | None = None,
    passband_nm: tuple[float, float] | None = None,
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
        Binarisation threshold.  Default 0.5.  Also the level at
        which the *intensity* crossing is interpolated.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.
    edge : str
        Which edge to measure.  "left", "right", or
        "both" (default).  When "both", the combined LER is
        the RMS of the left and right edge deviations averaged.
    intensity : torch.Tensor, optional
        Continuous field with the same shape as *developed*
        (e.g. acid concentration).  When provided, sub-pixel edge
        positions are computed by linear interpolation of the
        threshold crossing (removes integer-pixel quantisation).
        Default None (legacy integer-pixel edges).
    passband_nm : tuple of float, optional
        Metrology passband (p_min, p_max) [nm] applied to each edge
        profile with bandlimit_along_rows before the RMS, as in
        extract_lwr and ler_estimate.  Default None (full simulated
        band, unchanged behaviour).

    Returns
    -------
    ler : float
        Line-edge roughness [nm] (1σ).

    See Also
    --------
    extract_edges : Low-level edge extraction used internally.
    extract_lwr : Line-width roughness extraction.
    """
    left_edge, right_edge = extract_edges(developed, threshold, dx, intensity)

    # Remove NaN rows
    finite_mask = ~(torch.isnan(left_edge) | torch.isnan(right_edge))
    if finite_mask.sum() < 3:
        return float("nan")

    left_finite = left_edge[finite_mask]
    right_finite = right_edge[finite_mask]
    if passband_nm is not None:
        left_finite = bandlimit_along_rows(left_finite, dx, passband_nm)
        right_finite = bandlimit_along_rows(right_finite, dx, passband_nm)

    if edge == "left":
        deviations = left_finite - left_finite.mean()
        return float(torch.sqrt((deviations**2).mean()))
    elif edge == "right":
        deviations = right_finite - right_finite.mean()
        return float(torch.sqrt((deviations**2).mean()))
    else:  # "both"
        # Combine left and right deviations
        left_dev = left_finite - left_finite.mean()
        right_dev = right_finite - right_finite.mean()
        all_dev = torch.cat([left_dev, right_dev])
        return float(torch.sqrt((all_dev**2).mean()))


# ──────────────────────────────────────────────
# Correlation-aware LER estimator
# ──────────────────────────────────────────────


class LEREstimate:
    """Correlation-aware LER estimate with full statistical metadata.

    Attributes
    ----------
    ler_nm : float
        Point estimate of the edge-fluctuation RMS [nm].
    n_rows : int
        Number of physical rows (y-samples) used per realization.
    n_eff : float
        Effective number of independent rows (correlation-corrected).
    l_int_px : float
        Integral correlation length [pixels].
    l_int_nm : float
        Integral correlation length [nm].
    estimator : str
        "large_n" (primary) or "corr_corrected" (control estimator).
    seed_count : int
        Number of independent realizations used.
    uncertainty_nm : float
        Standard error of the mean over independent realizations
        (NaN when only one realization is provided).
    ci95_low_nm / ci95_high_nm : float
        Approximate 95 % CI of the mean (mean ± 1.96·SE).
    rho_truncation : int
        Fixed truncation rule: first lag k ≥ 1 with rho(k) < 0.05,
        capped at 200 px (chosen before looking at results).
    disclaimer : str
        Standard scientific disclaimer.
    """

    def __init__(
        self,
        ler_nm: float,
        n_rows: int,
        n_eff: float,
        l_int_px: float,
        l_int_nm: float,
        estimator: str,
        seed_count: int,
        uncertainty_nm: float,
        ci95_low_nm: float,
        ci95_high_nm: float,
        rho_truncation: int,
    ):
        self.ler_nm = float(ler_nm)
        self.n_rows = int(n_rows)
        self.n_eff = float(n_eff)
        self.l_int_px = float(l_int_px)
        self.l_int_nm = float(l_int_nm)
        self.estimator = estimator
        self.seed_count = int(seed_count)
        self.uncertainty_nm = float(uncertainty_nm)
        self.ci95_low_nm = float(ci95_low_nm)
        self.ci95_high_nm = float(ci95_high_nm)
        self.rho_truncation = int(rho_truncation)
        self.disclaimer = (
            "Schätzung der Kantenfluktuations-Std für diese "
            "Modellkonfiguration; kein experimentell validierter Wert."
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"LEREstimate(ler_nm={self.ler_nm:.6f}, n_rows={self.n_rows}, "
            f"n_eff={self.n_eff:.1f}, l_int_nm={self.l_int_nm:.2f}, "
            f"estimator='{self.estimator}', seed_count={self.seed_count})"
        )


def _autocorrelation(x: torch.Tensor, kmax: int) -> torch.Tensor:
    """Empirical autocorrelation rho(k) of a stationary sequence.

    rho(k) = <(x[i]-mu)(x[i+k]-mu)> / <(x[i]-mu)^2>, pooled over lags.
    """
    n = x.shape[0]
    xc = x - x.mean()
    c0 = (xc * xc).mean()
    if c0 <= 0:
        return torch.zeros(kmax + 1, dtype=x.dtype, device=x.device)
    k_eff = min(kmax, n - 1)
    out = torch.empty(k_eff + 1, dtype=x.dtype, device=x.device)
    out[0] = 1.0
    for k in range(1, k_eff + 1):
        out[k] = (xc[: n - k] * xc[k:]).mean() / c0
    if k_eff < kmax:
        pad = torch.zeros(kmax - k_eff, dtype=x.dtype, device=x.device)
        out = torch.cat([out, pad])
    return out


def _ler_rms(positions: torch.Tensor) -> float:
    """RMS deviation from the mean (same definition as extract_ler)."""
    dev = positions - positions.mean()
    return float(torch.sqrt((dev**2).mean()))


def ler_estimate(
    developed,
    threshold: float = 0.3,
    dx: float = 0.25,
    edge: str = "both",
    intensity=None,
    estimator: str = "large_n",
    rho_truncation: int | None = None,
    seed_count: int | None = None,
    passband_nm: tuple[float, float] | None = None,
) -> LEREstimate:
    """Correlation-aware LER estimator.

    Primary estimator: ``"large_n"`` — RMS of the edge position over all
    rows (identical observable definition to ``extract_ler``), reported
    together with the effective number of independent rows ``n_eff`` and
    the integral correlation length ``l_int``.  For statistically
    defensible absolute values the field must provide ``n_eff >= 30``
    (derived from the measured correlation, not hard-coded).

    Control estimator: ``estimator="corr_corrected"`` — the same RMS value
    corrected by the empirical autocorrelation bias factor
    ``E[s^2] = sigma^2 * (1 - 2*sum_k (1-k/N) rho(k) / (N-1))``.
    It is a CONTROL method only and never replaces the primary value.

    ``developed`` may be a single 2D tensor or a sequence of 2D tensors
    (independent realizations / seeds).  ``intensity`` follows the same
    convention.  When several realizations are supplied, ``ler_nm`` is
    the mean over realizations and ``uncertainty_nm`` / CI are the SE
    and approximate 95 % CI of that mean (variation over independent
    seeds — the primary uncertainty source).  Autocorrelation is pooled
    over realizations.

    Fixed truncation rule (chosen before inspecting results):
    first lag k >= 1 with rho(k) < 0.05, capped at 200 px.

    Legacy ``extract_ler`` is untouched; this function is additive.
    """
    if estimator not in ("large_n", "corr_corrected"):
        raise ValueError(f"estimator must be 'large_n' or 'corr_corrected', got {estimator!r}")

    is_seq = isinstance(developed, (list, tuple))
    fields = developed if is_seq else [developed]
    inten = intensity if intensity is not None else [None] * len(fields)
    if is_seq and intensity is not None and len(intensity) != len(fields):
        raise ValueError("intensity sequence length must match developed sequence length")
    if not is_seq:
        inten = [intensity]

    if rho_truncation is None:
        rho_truncation = 200  # cap; actual truncation found from rho < 0.05

    n_rows = int(fields[0].shape[0])
    all_rhos = []
    ler_per_real = []
    k_trunc_final = rho_truncation

    for dev, intens in zip(fields, inten):
        left, right = extract_edges(dev, threshold, dx, intens)
        finite = ~(torch.isnan(left) | torch.isnan(right))
        if finite.sum() < 3:
            ler_per_real.append(float("nan"))
            continue
        lf, rf = left[finite], right[finite]
        if passband_nm is not None:
            lf = bandlimit_along_rows(lf, dx, passband_nm)
            rf = bandlimit_along_rows(rf, dx, passband_nm)

        # per-edge autocorrelation (pooled over edges for "both")
        kmax = min(rho_truncation, n_rows - 1)
        rho_l = _autocorrelation(lf, kmax)
        if edge == "both":
            rho_r = _autocorrelation(rf, kmax)
            rho = 0.5 * (rho_l + rho_r)
        elif edge == "left":
            rho = rho_l
        elif edge == "right":
            rho = _autocorrelation(rf, kmax)
        else:
            raise ValueError(f"edge must be 'left', 'right' or 'both', got {edge!r}")
        all_rhos.append(rho)

        # LER (same observable as extract_ler)
        if edge == "both":
            dev_l = lf - lf.mean()
            dev_r = rf - rf.mean()
            pos = torch.cat([dev_l, dev_r])
            ler = _ler_rms(pos)
        elif edge == "left":
            ler = _ler_rms(lf)
        else:
            ler = _ler_rms(rf)

        if estimator == "corr_corrected":
            # bias factor for E[s^2], s^2 = unbiased sample variance
            S = 0.0
            N = n_rows
            for k in range(1, len(rho)):
                S += (1.0 - k / N) * float(rho[k])
            bias = 1.0 - 2.0 * S / (N - 1)
            bias = max(bias, 1e-6)
            # RMS^2 = (N-1)/N * s^2  ->  sigma^2 = RMS^2 * N/(N-1) / bias
            ler = ler * math.sqrt(N / (N - 1) / bias)
        ler_per_real.append(ler)

    # pooled autocorrelation + truncation (fixed rule: first k with rho<0.05)
    rho_pooled = torch.stack(all_rhos).mean(dim=0) if all_rhos else torch.zeros(rho_truncation + 1)
    k_trunc = rho_truncation
    for k in range(1, len(rho_pooled)):
        if float(rho_pooled[k]) < 0.05:
            k_trunc = k
            break
    l_int = 0.5 + float(rho_pooled[1:k_trunc].sum()) if k_trunc > 1 else 0.5
    neff = n_rows / (
        1.0
        + 2.0
        * sum((1.0 - k / n_rows) * float(rho_pooled[k]) for k in range(1, min(k_trunc, n_rows)))
    )

    vals = torch.tensor([v for v in ler_per_real if not math.isnan(v)], dtype=torch.float64)
    if vals.numel() == 0:
        # No realization had a measurable edge (e.g. the field is fully
        # developed or fully undeveloped in every realization -- a real,
        # reachable configuration, not a numerical error). Consistent with
        # extract_lwr()'s own NaN convention for the identical "no edge
        # found" case (see its own `return float("nan")`, called at the
        # same pipeline.py call site just above this one), and with the
        # per-realization math.isnan(v) filtering a few lines above: report
        # NaN rather than raising, so a caller sweeping a parameter across
        # a resist's resolution window (e.g. a dose or dill_C sweep that
        # legitimately runs into fully-cleared or fully-unresolved points)
        # gets a well-formed, filterable result instead of an uncaught
        # exception aborting the whole run. Found and fixed 2026-09-04
        # while repairing notebooks/05_stochastics.ipynb, whose (then dill_Q, now dill_C)
        # sweep hits exactly this case at its upper end.
        return LEREstimate(
            ler_nm=float("nan"),
            n_rows=n_rows,
            n_eff=neff,
            l_int_px=l_int,
            l_int_nm=l_int * dx,
            estimator=estimator,
            seed_count=int(seed_count) if seed_count is not None else 0,
            uncertainty_nm=float("nan"),
            ci95_low_nm=float("nan"),
            ci95_high_nm=float("nan"),
            rho_truncation=k_trunc,
        )
    ler_mean = float(vals.mean())
    n_seed = int(vals.numel()) if seed_count is None else seed_count
    if vals.numel() > 1:
        se = float(vals.std(unbiased=True) / math.sqrt(vals.numel()))
        ci_low, ci_high = ler_mean - 1.96 * se, ler_mean + 1.96 * se
    else:
        se, ci_low, ci_high = float("nan"), float("nan"), float("nan")

    return LEREstimate(
        ler_nm=ler_mean,
        n_rows=n_rows,
        n_eff=neff,
        l_int_px=l_int,
        l_int_nm=l_int * dx,
        estimator=estimator,
        seed_count=n_seed,
        uncertainty_nm=se,
        ci95_low_nm=ci_low,
        ci95_high_nm=ci_high,
        rho_truncation=k_trunc,
    )


# ──────────────────────────────────────────────
# LWR extraction from multiple line cuts
# ──────────────────────────────────────────────


def bandlimit_along_rows(x: torch.Tensor, dx: float, passband_nm: tuple[float, float] | None):
    """Keep only the spatial periods p_min <= p <= p_max of a row sequence.

    Roughness measurements are band-limited by the metrology (pixel size,
    image height, noise cut-off): Anderson & Naulleau 2008 evaluate periods
    10-834 nm, imec's CD-SEM protocol in Vesters 2019 has 5.38 nm pixels in y
    and 5.5 um images. A simulated edge on a 0.2-0.4 nm grid carries power at
    periods no measurement sees; a fair comparison applies the same band
    FFT along the (periodic) row axis; the mean is
    always removed. ``None`` returns the input unchanged.
    """
    if passband_nm is None:
        return x
    p_min, p_max = passband_nm
    n = x.shape[0]
    if n < 4:
        return x - x.mean()
    spec = torch.fft.rfft(x - x.mean())
    freq = torch.fft.rfftfreq(n, d=dx, dtype=torch.float64)  # cycles per nm
    keep = torch.zeros_like(freq, dtype=torch.bool)
    nonzero = freq > 0
    period = torch.where(nonzero, 1.0 / freq.clamp(min=1e-30), torch.full_like(freq, float("inf")))
    keep = nonzero & (period >= p_min) & (period <= p_max)
    spec = torch.where(keep, spec, torch.zeros_like(spec))
    return torch.fft.irfft(spec, n=n)


def extract_lwr(
    developed: torch.Tensor,
    threshold: float = 0.5,
    dx: float = 1.0,
    intensity: torch.Tensor | None = None,
    passband_nm: tuple[float, float] | None = None,
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
        Binarisation threshold.  Default 0.5.  Also the level at
        which the *intensity* crossing is interpolated.
    dx : float
        Lateral grid spacing [nm/pixel].  Default 1.0.
    intensity : torch.Tensor, optional
        Continuous field with the same shape as *developed*
        (e.g. acid concentration).  When provided, sub-pixel edge
        positions are computed by linear interpolation of the
        threshold crossing (removes integer-pixel quantisation).
        Default None (legacy integer-pixel edges).

    Returns
    -------
    lwr : float
        Line-width roughness [nm] (1σ).

    See Also
    --------
    extract_edges : Low-level edge extraction.
    extract_ler : LER extraction (edge roughness).
    """
    left_edge, right_edge = extract_edges(developed, threshold, dx, intensity)

    # Line width per row
    width = right_edge - left_edge

    # Remove NaN
    finite = ~torch.isnan(width)
    if finite.sum() < 3:
        return float("nan")
    if passband_nm is not None:
        width = bandlimit_along_rows(width[finite], dx, passband_nm)
        finite = torch.ones_like(width, dtype=torch.bool)

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
    photon_energy_eV: float = 91.84,
    dose_to_energy_factor: float = 6.241509074e15,
    shot_noise_rng: torch.Generator | None = None,
    dx_nm: float = 1.0,
    dy_nm: float | None = None,
    n_realisations: int = 1,
    average: bool = True,
    se_blur_nm: float = 2.5,
) -> dict:
    """Compute LER and LWR from a stochastic resist realisation.

    This is a convenience pipeline:

        1. Apply Poisson shot noise to the deterministic acid map.
        2. Blur the noisy acid with the secondary-electron kernel
           (*se_blur_nm*).
        3. Develop where the blurred acid exceeds *develop_threshold*.
        4. Extract LER and LWR with sub-pixel edges (linear interpolation
           of the threshold crossing of the blurred acid).

    *acid* must describe a resist LINE along the rows: low acid in the
    line, high acid in the spaces, so that each row crosses two edges.

    When *n_realisations* > 1, multiple independent noise realisations
    are drawn and the LER/LWR are averaged across them.

    Corrected 2026-10 (as rms_scaling_check on 2026-09-25):
    the unblurred noisy acid is the acid COUNT per pixel times a constant,
    and at EUV doses a 1 nm pixel holds a fraction of an acid to a few, so
    thresholding it only asked whether a pixel caught enough acids and the
    integer-pixel edges were pixel noise (LER rose with dose).

    Parameters
    ----------
    acid : torch.Tensor
        Deterministic acid concentration.  2D ``(H, W)``.
    dose : torch.Tensor, optional
        EUV dose map [mJ/cm²].  Same shape as *acid*.  Needed for
        physically accurate shot-noise scaling.  When ``None``, the
        acid map is used heuristically (legacy fallback).
    develop_threshold : float
        Development threshold on the SE-blurred acid concentration, in
        the units of *acid* (an absolute level: with the acid map fixed,
        a higher dose only lowers the noise and the mean edge stays put).
        Default 0.3.
    quantum_efficiency : float
        Acid molecules per absorbed photon.  Default 0.04.
    photon_energy_eV : float
        EUV photon energy in eV.  Default 91.84 eV
        (corresponding to 13.5 nm wavelength via E = hc/λ).
        Use the derived energy from wavelength for consistency.
    dose_to_energy_factor : float
        Conversion factor: 1 mJ/cm² corresponds to this many eV/cm².
        Default 6.241509074e15 (exact).
    shot_noise_rng : torch.Generator, optional
        RNG for Poisson sampling.
    dx_nm : float
        Pixel spacing in x direction [nm].  Default 1.0.
    dy_nm : float, optional
        Pixel spacing in y direction [nm].  If None, assumed equal to dx_nm.
        Default None.
    n_realisations : int
        Number of independent noise realisations.  Default 1.
    average : bool
        If ``True`` (default), return the mean LER/LWR across all
        realisations.  If ``False``, return lists of per-realisations
        values.
    se_blur_nm : float
        Secondary-electron blur σ [nm] applied to the noisy acid.  Default
        2.5 (the project default, Thackeray 2010).  0 disables the blur;
        the edges are then dominated by single-pixel noise.

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
    from euvsimulator.resist.exposure import gaussian_se_blur

    ler_vals = []
    lwr_vals = []

    for _ in range(n_realisations):
        # Apply shot noise
        noisy = poisson_shot_noise(
            acid,
            dose=dose,
            quantum_efficiency=quantum_efficiency,
            photon_energy_eV=photon_energy_eV,
            dose_to_energy_factor=dose_to_energy_factor,
            dx_nm=dx_nm,
            dy_nm=dy_nm,
            rng=shot_noise_rng,
        )

        # SE blur, then threshold development of the blurred acid with
        # sub-pixel edges (extract_* binarise at the same threshold)
        assert isinstance(noisy, torch.Tensor)
        blurred = gaussian_se_blur(noisy, sigma=se_blur_nm, dx=dx_nm)
        ler = extract_ler(blurred, threshold=develop_threshold, dx=dx_nm, intensity=blurred)
        lwr = extract_lwr(blurred, threshold=develop_threshold, dx=dx_nm, intensity=blurred)
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
    photon_energy_eV: float = 91.84,
    dose_to_energy_factor: float = 6.241509074e15,
    dx_nm: float = 1.0,
    dy_nm: float | None = None,
    seed: int = 42,
    se_blur_nm: float = 2.5,
) -> dict:
    r"""Verify the  1 / √(dose)  LER scaling law.

    For each dose level in *dose_levels*, the base acid map is scaled
    linearly (acid ∝ dose) to represent the deterministic acid at that
    dose, then Poisson shot noise is applied, the result is blurred with
    the secondary-electron kernel (*se_blur_nm*), thresholded at the fixed
    fraction *develop_threshold* of the blurred deterministic maximum, and
    LER/LWR are extracted with sub-pixel edges and averaged across
    *n_realisations*.  Because the threshold scales with the dose, the mean
    edge does not move and only the photon statistics change -- the
    condition under which LER ∝ dose^-1/2 holds.

    *base_acid* must describe a resist LINE along the rows: low acid in the
    line, high acid in the spaces, so that each row crosses two edges.

    Corrected 2026-09-25.  Before, the threshold was a fixed absolute
    value: the rescaled noisy acid equals the Poisson count times a
    dose-independent constant, so ``noisy > develop_threshold`` only asked
    "at least one acid in this pixel", and without blur the edges were
    pixel noise.  The function returned exponents between +0.5 and +2.6.

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
        Development threshold as a fraction of the blurred deterministic
        acid maximum at each dose.  Default 0.3.
    quantum_efficiency : float
        Acid molecules per absorbed photon.  Default 0.04.
    photon_energy_eV : float
        Photon energy [eV], used to convert dose to photon count.
        Default 91.84 (13.5 nm EUV).
    dose_to_energy_factor : float
        Conversion factor from dose [mJ/cm²] to photon energy density
        [eV/nm²].  Default matches ``photon_deposition_shot_noise``'s
        own convention.
    dx_nm : float
        Grid spacing in x [nm/pixel].  Default 1.0. (Corrected 2026-09-04:
        this docstring previously said ``dx``, not matching the actual
        parameter name ``dx_nm`` -- found while repairing
        notebooks/05_stochastics.ipynb, which called this function with
        the stale ``dx=`` keyword and raised TypeError.)
    dy_nm : float, optional
        Grid spacing in y [nm/pixel].  Defaults to ``dx_nm`` if not given.
    seed : int
        RNG seed for reproducibility.  Default 42.
    se_blur_nm : float
        Secondary-electron blur σ [nm] applied to the noisy acid.  Default
        2.5 (the project default).  0 disables the blur; the edges are then
        dominated by single-pixel noise.

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
    from euvsimulator.resist.exposure import gaussian_se_blur

    device = base_acid.device
    # one float dtype for doses and results (float32 doses with float64
    # results, or the reverse, broke the least-squares fit below)
    dose_levels = dose_levels.to(device=device, dtype=torch.float64)
    ler_vals = torch.zeros(len(dose_levels), device=device, dtype=torch.float64)
    lwr_vals = torch.zeros(len(dose_levels), device=device, dtype=torch.float64)
    ref_dose = float(dose_levels.max())

    for i, d in enumerate(dose_levels):
        # Deterministic acid at this dose (linear regime) and the local dose
        # map with the same spatial pattern, peaking at d.
        acid_scaled = base_acid * (float(d) / ref_dose)
        dose_map = acid_scaled / acid_scaled.max() * float(d)
        det_blur = gaussian_se_blur(acid_scaled, sigma=se_blur_nm, dx=dx_nm)
        threshold = develop_threshold * float(det_blur.max())

        ler_i = []
        lwr_i = []
        for k in range(n_realisations):
            rng = torch.Generator(device=device).manual_seed(seed + i * n_realisations + k)
            noisy = poisson_shot_noise(
                acid_scaled,
                dose=dose_map,
                quantum_efficiency=quantum_efficiency,
                photon_energy_eV=photon_energy_eV,
                dose_to_energy_factor=dose_to_energy_factor,
                dx_nm=dx_nm,
                dy_nm=dy_nm,
                rng=rng,
            )
            assert isinstance(noisy, torch.Tensor)
            blurred = gaussian_se_blur(noisy, sigma=se_blur_nm, dx=dx_nm)
            ler_i.append(extract_ler(blurred, threshold=threshold, dx=dx_nm, intensity=blurred))
            lwr_i.append(extract_lwr(blurred, threshold=threshold, dx=dx_nm, intensity=blurred))

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
