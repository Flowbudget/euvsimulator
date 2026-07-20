# ──────────────────────────────────────────────
# Validation tests: OpEnUV NILS vs. Reference Model
# ──────────────────────────────────────────────

import math

# ──────────────────────────────────────────────
# Reference Model (independent numpy/scipy implementation)
# ──────────────────────────────────────────────
import numpy as np
import pytest
import torch
from scipy.special import j1 as sp_j1

from euv.aerial.abbe import aerial_from_orders
from euv.aerial.abbe import nils as op_nils
from euv.pipeline import RESIST_PRESETS, SimulationConfig, run_simulation


def reference_aerial_image(
    amplitudes: np.ndarray,
    order_indices: np.ndarray,
    period_m: float,
    na: float,
    wavelength_m: float,
    sigma: float,
    grid: int = 256,
    se_blur_nm: float = 0.0,
) -> np.ndarray:
    """
    Independent reference implementation of aerial image from diffraction orders.

    Implements Hopkins formulation:
        I(x) = Σ_i Σ_j a_i · a_j* · TCC(i,j) · exp(i·2π·(m_i-m_j)·x/Λ)

    TCC for circular source (Hopkins 1953):
        TCC(i,j) = 2·J₁(x) / x,  x = π·σ·NA·|m_i-m_j|·λ/Λ

    Same pupil/coherence cutoffs as OpEnUV.
    """
    G = grid
    x_pos = np.linspace(-period_m / 2, period_m / 2, G)

    # Pupil cutoff
    max_order = int(np.floor(na * period_m / wavelength_m))

    # Coherence area
    coherence_orders = sigma * na * period_m / wavelength_m

    M = len(amplitudes)
    aerial_1d = np.zeros(G, dtype=np.complex128)

    for i in range(M):
        mi = int(order_indices[i])
        ai = amplitudes[i]
        if abs(ai) < 1e-15:
            continue
        if abs(mi) > max_order:
            continue

        for j in range(M):
            mj = int(order_indices[j])
            aj = amplitudes[j]
            if abs(aj) < 1e-15:
                continue
            if abs(mj) > max_order:
                continue

            dm = abs(mi - mj)
            if dm > coherence_orders + 1e-12:
                continue

            # TCC: 2*J1(x)/x for circular source
            if dm == 0:
                tcc = 1.0
            else:
                x = math.pi * sigma * na * dm * wavelength_m / period_m
                tcc = 2.0 * sp_j1(x) / x

            phase = 2.0 * math.pi * (mi - mj) * x_pos / period_m
            aerial_1d += ai * np.conj(aj) * tcc * np.exp(1j * phase)

    # I = |Σ|²
    aerial_1d = (aerial_1d * np.conj(aerial_1d)).real

    # 2D replication
    aerial = aerial_1d[None, :].repeat(G, axis=0).copy()

    # SE blur (Gaussian, separable) - match PyTorch's F.pad reflect
    if se_blur_nm > 0.0:
        dx = period_m / G * 1e9  # nm/pixel
        sigma_px = se_blur_nm / dx
        if sigma_px >= 1e-6:
            radius = max(1, int(3.0 * sigma_px + 0.5))
            g = np.arange(-radius, radius + 1, dtype=np.float64)
            g = np.exp(-0.5 * (g / sigma_px) ** 2)
            g = g / g.sum()
            from scipy.signal import convolve2d

            k = np.outer(g[:, None], g[None, :])
            aerial = convolve2d(aerial, k, mode="same", boundary="symm")

    return aerial


def reference_nils(aerial: np.ndarray, line_center: int, line_width_px: int, dx_nm: float) -> float:
    """Reference NILS implementation matching OpEnUV's new method."""
    G = aerial.shape[0]
    cut = aerial[line_center, :]
    Imin, Imax = cut.min(), cut.max()
    if Imax <= Imin + 1e-12:
        return 0.0

    # gradient (per nm)
    dIdx = np.gradient(cut, dx_nm)

    # steepest point (absolute value)
    edge_idx = int(np.argmax(np.abs(dIdx)))
    slope = dIdx[edge_idx]
    Iedge = cut[edge_idx]
    if Iedge < 1e-12:
        return 0.0

    nils_slope = abs(slope) / Iedge  # per nm

    # measured CD: width of below-median region
    thr = (Imin + Imax) / 2.0
    below = cut < thr
    runs = []
    start = None
    for i, b in enumerate(below):
        if b and start is None:
            start = i
        elif not b and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(below) - 1))

    if runs:
        longest = max(runs, key=lambda r: r[1] - r[0])
        cd_nm = (longest[1] - longest[0] + 1) * dx_nm
    else:
        cd_nm = line_width_px * dx_nm

    return nils_slope * cd_nm


# ──────────────────────────────────────────────
# Validation Tests
# ──────────────────────────────────────────────


def test_nils_blur_zero_matches_reference():
    """NILS with no SE blur: OpEnUV matches reference model (diff < 0.3)."""
    period_m = 64e-9
    wavelength_m = 13.5e-9
    na = 0.33
    sigma = 0.8
    grid = 256

    # Fourier coefficients for binary mask (32nm line / 64nm pitch)
    duty = 0.5
    n_orders = 21
    order_indices = np.arange(-n_orders, n_orders + 1, dtype=np.int64)

    # TMM reflectivities (Mo/Si stack @ 6°)
    r_space = complex(0.5602816506420832, 0.5771115841886296)
    r_abs = complex(-0.08038053358768138, -0.07996446551329976)

    c0 = r_abs * duty + r_space * (1 - duty)
    amplitudes = np.zeros(len(order_indices), dtype=np.complex128)
    for idx, m in enumerate(order_indices):
        if m == 0:
            amplitudes[idx] = c0
        else:
            amplitudes[idx] = (r_abs - r_space) * np.sin(math.pi * m * duty) / (math.pi * m)

    # OpEnUV
    order_tensor = torch.tensor(order_indices, dtype=torch.int64)
    amp_tensor = torch.tensor(amplitudes, dtype=torch.complex128)
    aerial_op = aerial_from_orders(
        amp_tensor,
        order_tensor,
        period_m=period_m,
        na=na,
        wavelength_m=wavelength_m,
        sigma=sigma,
        grid=grid,
        se_blur_nm=0.0,
    )

    half = grid // 2
    line_width_px = int(round(32 / (period_m / grid * 1e9)))
    dx_nm = period_m / grid * 1e9

    nils_op = op_nils(aerial_op, half, line_width_px, dx_nm)

    # Reference
    aerial_ref = reference_aerial_image(
        amplitudes, order_indices, period_m, na, wavelength_m, sigma, grid=grid, se_blur_nm=0.0
    )
    nils_ref = reference_nils(aerial_ref, half, line_width_px, dx_nm)

    diff = abs(nils_op - nils_ref)
    print(f"\nBlur=0nm: OpEnUV={nils_op:.4f}, Ref={nils_ref:.4f}, Diff={diff:.4f}")
    assert diff < 0.3, f"NILS mismatch: OpEnUV={nils_op:.4f}, Ref={nils_ref:.4f}, diff={diff:.4f}"


def test_nils_blur_10nm_matches_reference():
    """NILS with 10nm SE blur: OpEnUV matches reference model (diff < 0.3)."""
    period_m = 64e-9
    wavelength_m = 13.5e-9
    na = 0.33
    sigma = 0.8
    grid = 256

    duty = 0.5
    n_orders = 21
    order_indices = np.arange(-n_orders, n_orders + 1, dtype=np.int64)

    r_space = complex(0.5602816506420832, 0.5771115841886296)
    r_abs = complex(-0.08038053358768138, -0.07996446551329976)

    c0 = r_abs * duty + r_space * (1 - duty)
    amplitudes = np.zeros(len(order_indices), dtype=np.complex128)
    for idx, m in enumerate(order_indices):
        if m == 0:
            amplitudes[idx] = c0
        else:
            amplitudes[idx] = (r_abs - r_space) * np.sin(math.pi * m * duty) / (math.pi * m)

    # OpEnUV
    order_tensor = torch.tensor(order_indices, dtype=torch.int64)
    amp_tensor = torch.tensor(amplitudes, dtype=torch.complex128)
    aerial_op = aerial_from_orders(
        amp_tensor,
        order_tensor,
        period_m=period_m,
        na=na,
        wavelength_m=wavelength_m,
        sigma=sigma,
        grid=grid,
        se_blur_nm=10.0,
    )

    half = grid // 2
    line_width_px = int(round(32 / (period_m / grid * 1e9)))
    dx_nm = period_m / grid * 1e9

    nils_op = op_nils(aerial_op, half, line_width_px, dx_nm)

    # Reference
    aerial_ref = reference_aerial_image(
        amplitudes, order_indices, period_m, na, wavelength_m, sigma, grid=grid, se_blur_nm=10.0
    )
    nils_ref = reference_nils(aerial_ref, half, line_width_px, dx_nm)

    diff = abs(nils_op - nils_ref)
    print(f"\nBlur=10nm: OpEnUV={nils_op:.4f}, Ref={nils_ref:.4f}, Diff={diff:.4f}")
    assert diff < 0.3, f"NILS mismatch: OpEnUV={nils_op:.4f}, Ref={nils_ref:.4f}, diff={diff:.4f}"


def test_nils_realistic_range():
    """With realistic SE blur (10nm), NILS should be in realistic range 1.5–4.0."""
    period_m = 64e-9
    wavelength_m = 13.5e-9
    na = 0.33
    sigma = 0.8
    grid = 256

    duty = 0.5
    n_orders = 21
    order_indices = np.arange(-n_orders, n_orders + 1, dtype=np.int64)

    r_space = complex(0.5602816506420832, 0.5771115841886296)
    r_abs = complex(-0.08038053358768138, -0.07996446551329976)

    c0 = r_abs * duty + r_space * (1 - duty)
    amplitudes = np.zeros(len(order_indices), dtype=np.complex128)
    for idx, m in enumerate(order_indices):
        if m == 0:
            amplitudes[idx] = c0
        else:
            amplitudes[idx] = (r_abs - r_space) * np.sin(math.pi * m * duty) / (math.pi * m)

    order_tensor = torch.tensor(order_indices, dtype=torch.int64)
    amp_tensor = torch.tensor(amplitudes, dtype=torch.complex128)
    aerial_op = aerial_from_orders(
        amp_tensor,
        order_tensor,
        period_m=period_m,
        na=na,
        wavelength_m=wavelength_m,
        sigma=sigma,
        grid=grid,
        se_blur_nm=10.0,
    )

    half = grid // 2
    line_width_px = int(round(32 / (period_m / grid * 1e9)))
    dx_nm = period_m / grid * 1e9

    nils_op = op_nils(aerial_op, half, line_width_px, dx_nm)

    # Literature for k1≈0.78, σ=0.8: NILS ~ 2-3
    assert 1.5 <= nils_op <= 4.0, f"NILS={nils_op:.3f} outside realistic range [1.5, 4.0]"


# ──────────────────────────────────────────────
# Integration test: full pipeline with SE blur
# ──────────────────────────────────────────────


def test_pipeline_with_se_blur():
    """Full pipeline run_simulation with se_blur_nm produces sensible NILS."""
    cfg = SimulationConfig(
        se_blur_nm=10.0,
        grid=256,
        dose_mj_cm2=20.0,
    )
    result = run_simulation(cfg)

    # NILS should be realistic (not 8.8)
    assert (
        1.5 <= result.nils_value <= 4.0
    ), f"Pipeline NILS={result.nils_value:.3f} outside realistic range"

    # CD should be measurable
    assert result.cd_nm > 0, f"CD={result.cd_nm:.2f} not measurable"


def test_pipeline_car_preset():
    """CAR preset (5nm blur) produces realistic NILS."""
    cfg = SimulationConfig(
        se_blur_nm=RESIST_PRESETS["CAR"],
        grid=256,
        dose_mj_cm2=20.0,
    )
    result = run_simulation(cfg)

    # CAR blur=5nm should give NILS ~ 4-5 (higher than 10nm blur)
    assert (
        2.0 <= result.nils_value <= 6.0
    ), f"CAR preset NILS={result.nils_value:.3f} outside expected range"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
