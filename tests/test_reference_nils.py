"""Regression test: OpEnUV NILS vs independent reference model.

The reference model (reference_model.py) is a pure numpy/scipy implementation
of Hopkins imaging with correct TCC (2*J1/x) and SE blur. It uses no OpEnUV code.

This test ensures OpEnUV's aerial image + NILS computation stays physically correct.
"""

import numpy as np
import torch
from scipy.special import j1

from euv.aerial.abbe import aerial_from_orders, nils


# ---- Reference implementation (copied from reference_model.py) ----
def mask_amplitudes_ref(period_nm, line_frac, r_space, r_abs, n_orders):
    m = np.arange(-n_orders, n_orders + 1)
    a = np.zeros(len(m), dtype=complex)
    duty = line_frac
    for i, mi in enumerate(m):
        if mi == 0:
            a[i] = r_abs * duty + r_space * (1.0 - duty)
        else:
            a[i] = (r_abs - r_space) * np.sin(np.pi * mi * duty) / (np.pi * mi)
    return m, a


def tcc_ref(mi, mj, sigma, na, wavelength_nm, period_nm):
    dm = abs(mi - mj)
    if dm == 0:
        return 1.0
    x = np.pi * sigma * na * dm * wavelength_nm / period_nm
    return 2.0 * j1(x) / x


def aerial_image_ref(
    m_orders,
    a_coeffs,
    period_nm,
    sigma,
    na,
    wavelength_nm,
    grid,
    dose_mj_cm2=1.0,
    sigma_blur_nm=0.0,
):
    period_m = period_nm * 1e-9
    x = np.linspace(-period_m / 2, period_m / 2, grid)

    max_order = int(np.floor(na * period_nm / wavelength_nm))
    pupil_mask = np.abs(m_orders) <= max_order
    m_orders_p = m_orders[pupil_mask]
    a_coeffs_p = a_coeffs[pupil_mask]

    coherence_orders = sigma * na * period_nm / wavelength_nm

    max_dm = len(m_orders_p) - 1
    tcc_cache = {
        dm: tcc_ref(0, dm, sigma, na, wavelength_nm, period_nm) for dm in range(max_dm + 1)
    }

    a1 = np.zeros(grid, dtype=complex)
    for i, mi in enumerate(m_orders_p):
        for j, mj in enumerate(m_orders_p):
            dm = abs(mi - mj)
            if dm > coherence_orders + 1e-12:
                continue
            tc = tcc_cache[dm]
            if tc == 0.0:
                continue
            phase = 2 * np.pi * (mi - mj) * x / period_m
            a1 += a_coeffs_p[i] * np.conj(a_coeffs_p[j]) * tc * np.exp(1j * phase)

    I = np.real(a1 * np.conj(a1)) * dose_mj_cm2
    I2 = np.tile(I, (grid, 1))

    if sigma_blur_nm > 0:
        from scipy.signal import convolve2d

        dx = period_nm / grid
        sigma_px = sigma_blur_nm / dx
        radius = max(1, int(3 * sigma_px + 0.5))
        g = np.arange(-radius, radius + 1, dtype=float)
        g = np.exp(-0.5 * (g / sigma_px) ** 2)
        g /= g.sum()
        col = g[:, None]
        row = g[None, :]
        k = np.outer(col, row)
        I2 = convolve2d(I2, k, mode="same", boundary="symm")
    return I2


def nils_from_image_ref(aerial, period_nm, grid, threshold_frac=0.5):
    half = grid // 2
    cut = aerial[half, :]
    Imin, Imax = cut.min(), cut.max()
    thr = Imin + threshold_frac * (Imax - Imin)
    dx_nm = period_nm / grid
    dIdx = np.gradient(cut, dx_nm)
    edge_idx = int(np.argmax(np.abs(dIdx)))
    slope = dIdx[edge_idx]
    Iedge = cut[edge_idx]
    if Iedge < 1e-12:
        return 0.0
    nils_slope = abs(slope) / Iedge
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
        cd = (longest[1] - longest[0] + 1) * dx_nm
    else:
        cd = 0.0
    return nils_slope * cd


# ---- Common test parameters ----
COMMON = dict(
    period_nm=64.0,
    na=0.33,
    wavelength_nm=13.5,
    sigma=0.8,
    grid=256,
    dose_mj_cm2=1.0,
    r_space=0.70 + 0.0j,
    r_abs=0.05 + 0.0j,
    duty=0.5,
    n_orders=21,
)


def build_orders():
    m_np, a_np = mask_amplitudes_ref(
        COMMON["period_nm"], COMMON["duty"], COMMON["r_space"], COMMON["r_abs"], COMMON["n_orders"]
    )
    # Apply pupil cutoff (same as OpEnUV)
    max_order = int(np.floor(COMMON["na"] * COMMON["period_nm"] / COMMON["wavelength_nm"]))
    mask = np.abs(m_np) <= max_order
    m_p = m_np[mask]
    a_p = a_np[mask]
    # Torch tensors for OpEnUV
    orders_complex = torch.tensor(a_p, dtype=torch.complex128)
    order_indices = torch.tensor(m_p, dtype=torch.int64)
    return m_p, a_p, orders_complex, order_indices


def test_nils_blur_zero():
    """NILS without SE blur should match reference (high, ~5.4)."""
    m_p, a_p, orders_complex, order_indices = build_orders()

    # OpEnUV
    ae = aerial_from_orders(
        orders_complex,
        order_indices,
        period_m=COMMON["period_nm"] * 1e-9,
        na=COMMON["na"],
        wavelength_m=COMMON["wavelength_nm"] * 1e-9,
        sigma=COMMON["sigma"],
        grid=COMMON["grid"],
        se_blur_nm=0.0,
    )
    dx_nm = COMMON["period_nm"] / COMMON["grid"]
    half = COMMON["grid"] // 2
    n_op = nils(ae, half, 128, dx_nm)

    # Reference
    Iref = aerial_image_ref(
        m_p,
        a_p,
        COMMON["period_nm"],
        COMMON["sigma"],
        COMMON["na"],
        COMMON["wavelength_nm"],
        COMMON["grid"],
        dose_mj_cm2=COMMON["dose_mj_cm2"],
        sigma_blur_nm=0.0,
    )
    n_ref = nils_from_image_ref(Iref, COMMON["period_nm"], COMMON["grid"])

    diff = abs(n_op - n_ref)
    assert diff < 0.3, f"NILS mismatch: OpEnUV={n_op:.3f}, Ref={n_ref:.3f}, diff={diff:.3f}"


def test_nils_blur_10nm():
    """NILS with 10 nm SE blur should match reference (realistic, ~2.7)."""
    m_p, a_p, orders_complex, order_indices = build_orders()

    # OpEnUV
    ae = aerial_from_orders(
        orders_complex,
        order_indices,
        period_m=COMMON["period_nm"] * 1e-9,
        na=COMMON["na"],
        wavelength_m=COMMON["wavelength_nm"] * 1e-9,
        sigma=COMMON["sigma"],
        grid=COMMON["grid"],
        se_blur_nm=10.0,
    )
    dx_nm = COMMON["period_nm"] / COMMON["grid"]
    half = COMMON["grid"] // 2
    n_op = nils(ae, half, 128, dx_nm)

    # Reference
    Iref = aerial_image_ref(
        m_p,
        a_p,
        COMMON["period_nm"],
        COMMON["sigma"],
        COMMON["na"],
        COMMON["wavelength_nm"],
        COMMON["grid"],
        dose_mj_cm2=COMMON["dose_mj_cm2"],
        sigma_blur_nm=10.0,
    )
    n_ref = nils_from_image_ref(Iref, COMMON["period_nm"], COMMON["grid"])

    diff = abs(n_op - n_ref)
    assert diff < 0.3, f"NILS mismatch: OpEnUV={n_op:.3f}, Ref={n_ref:.3f}, diff={diff:.3f}"


def test_nils_realistic_range():
    """NILS with CAR-typical SE blur (10 nm) should be in realistic range 1.5–4.0."""
    m_p, a_p, orders_complex, order_indices = build_orders()

    ae = aerial_from_orders(
        orders_complex,
        order_indices,
        period_m=COMMON["period_nm"] * 1e-9,
        na=COMMON["na"],
        wavelength_m=COMMON["wavelength_nm"] * 1e-9,
        sigma=COMMON["sigma"],
        grid=COMMON["grid"],
        se_blur_nm=10.0,
    )
    dx_nm = COMMON["period_nm"] / COMMON["grid"]
    half = COMMON["grid"] // 2
    n_op = nils(ae, half, 128, dx_nm)

    assert 1.5 <= n_op <= 4.0, f"NILS {n_op:.3f} not in realistic range [1.5, 4.0]"


if __name__ == "__main__":
    test_nils_blur_zero()
    print("test_nils_blur_zero PASSED")
    test_nils_blur_10nm()
    print("test_nils_blur_10nm PASSED")
    test_nils_realistic_range()
    print("test_nils_realistic_range PASSED")
    print("ALL TESTS PASSED")
