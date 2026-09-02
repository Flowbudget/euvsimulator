"""Regression test: euvsimulator NILS vs independent reference model.

The reference model (reference_model.py) is a pure numpy/scipy implementation
of Hopkins imaging with correct TCC (2*J1/x) and SE blur. It uses no euvsimulator code.

This test ensures euvsimulator's aerial image + NILS computation stays physically correct.
"""

import numpy as np
import torch
from scipy.special import j1

from euvsimulator.aerial.abbe import aerial_from_orders, nils


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


def exact_tcc_ref(mi, mj, sigma, na, wavelength_nm, period_nm, grid=256):
    """Exact TCC via 2D source-pupil overlap (numpy reference, P1-1)."""
    wavelength_m = wavelength_nm * 1e-9
    period_m = period_nm * 1e-9

    f = np.linspace(-2.0, 2.0, grid)
    FX, FY = np.meshgrid(f, f)

    S = (FX**2 + FY**2 <= sigma**2).astype(float)
    S_sum = S.sum()
    if S_sum < 1e-30:
        return 1.0  # coherent limit

    fi = mi * wavelength_m / (period_m * na)
    fj = mj * wavelength_m / (period_m * na)

    Pi = ((FX + fi)**2 + FY**2 <= 1.0).astype(float)
    Pj = ((FX + fj)**2 + FY**2 <= 1.0).astype(float)

    return float((S * Pi * Pj).sum() / S_sum)


def tcc_ref(mi, mj, sigma, na, wavelength_nm, period_nm):
    """TCC reference — uses exact source-pupil overlap (P1-1, 2026-09-01).
    
    Replaced Bessel J1 approximation with exact 2D overlap integral.
    """
    return exact_tcc_ref(mi, mj, sigma, na, wavelength_nm, period_nm)


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

    # Precompute full TCC matrix (exact source-pupil overlap, P1-1)
    n_p = len(m_orders_p)
    tcc_matrix = np.zeros((n_p, n_p))
    for i, mi in enumerate(m_orders_p):
        for j, mj in enumerate(m_orders_p):
            tcc_matrix[i, j] = exact_tcc_ref(mi, mj, sigma, na, wavelength_nm, period_nm)

    a1 = np.zeros(grid, dtype=complex)
    for i, mi in enumerate(m_orders_p):
        for j, mj in enumerate(m_orders_p):
            tc = tcc_matrix[i, j]
            if tc == 0.0:
                continue
            phase = 2 * np.pi * (mi - mj) * x / period_m
            a1 += a_coeffs_p[i] * np.conj(a_coeffs_p[j]) * tc * np.exp(1j * phase)

    # The Hopkins double-sum is already the (real, Hermitian) intensity.
    # The (i,j)+(j,i) pairs carry conjugate phases that cancel the
    # imaginary part, so taking .real() is exact (P0 fix, 2026-08-31).
    I = np.real(a1) * dose_mj_cm2
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


def nils_from_image_ref(aerial, period_nm, grid, threshold=None):
    """Independent Mack NILS (numpy). Does not import euvsimulator.nils.

    NILS = CD * |dI/dx| / I_edge at linear threshold crossings.
    Left and right edges averaged. Default threshold = 0.5 * mean(cut),
    matching aerial_threshold Optical-CD at nominal dose.
    """
    half = grid // 2
    cut = np.asarray(aerial[half, :], dtype=float)
    G = cut.size
    dx_nm = period_nm / grid
    if G < 2:
        return 0.0
    if threshold is None:
        thr = 0.5 * float(cut.mean())
    else:
        thr = float(threshold)
    if thr <= 1e-30:
        return 0.0
    crossings = []
    for i in range(G - 1):
        a = float(cut[i])
        b = float(cut[i + 1])
        if (a - thr) * (b - thr) > 0.0:
            continue
        denom = b - a
        if abs(denom) < 1e-30:
            continue
        t = (thr - a) / denom
        if t < 0.0 or t > 1.0:
            continue
        crossings.append((i + t, denom / dx_nm))
    if len(crossings) < 2:
        return 0.0
    best_width = -1.0
    best = None
    for k in range(len(crossings) - 1):
        x0, s0 = crossings[k]
        x1, s1 = crossings[k + 1]
        mid = int(round(0.5 * (x0 + x1)))
        mid = min(G - 1, max(0, mid))
        if cut[mid] >= thr:
            continue
        width = x1 - x0
        if width > best_width:
            best_width = width
            best = (s0, s1)
    if best is None or best_width <= 0.0:
        return 0.0
    cd = best_width * dx_nm
    return 0.5 * (cd * abs(best[0]) / thr + cd * abs(best[1]) / thr)


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
    # Apply pupil cutoff (same as euvsimulator)
    max_order = int(np.floor(COMMON["na"] * COMMON["period_nm"] / COMMON["wavelength_nm"]))
    mask = np.abs(m_np) <= max_order
    m_p = m_np[mask]
    a_p = a_np[mask]
    # Torch tensors for euvsimulator
    orders_complex = torch.tensor(a_p, dtype=torch.complex128)
    order_indices = torch.tensor(m_p, dtype=torch.int64)
    return m_p, a_p, orders_complex, order_indices


def test_nils_blur_zero():
    """NILS without SE blur should match reference (~2.7)."""
    m_p, a_p, orders_complex, order_indices = build_orders()

    # euvsimulator
    ae = aerial_from_orders(
        orders_complex,
        order_indices,
        period_m=COMMON["period_nm"] * 1e-9,
        na=COMMON["na"],
        wavelength_m=COMMON["wavelength_nm"] * 1e-9,
        sigma=COMMON["sigma"],
        grid=COMMON["grid"],
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
    assert diff < 0.3, f"NILS mismatch: euvsimulator={n_op:.3f}, Ref={n_ref:.3f}, diff={diff:.3f}"


def test_nils_blur_10nm():
    """NILS with 10 nm SE blur should match reference (realistic, ~2.7)."""
    m_p, a_p, orders_complex, order_indices = build_orders()

    # euvsimulator
    ae = aerial_from_orders(
        orders_complex,
        order_indices,
        period_m=COMMON["period_nm"] * 1e-9,
        na=COMMON["na"],
        wavelength_m=COMMON["wavelength_nm"] * 1e-9,
        sigma=COMMON["sigma"],
        grid=COMMON["grid"],
    )
    # Apply SE blur in the resist exposure step (as it should be)
    from euvsimulator.resist.exposure import gaussian_se_blur
    dx_nm = COMMON["period_nm"] / COMMON["grid"]
    ae = gaussian_se_blur(ae, sigma=10.0, dx=dx_nm)
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
    assert diff < 0.3, f"NILS mismatch: euvsimulator={n_op:.3f}, Ref={n_ref:.3f}, diff={diff:.3f}"


def test_nils_blur_reduces_nils():
    """SE blur must lower Mack NILS relative to the unblurred image.

    The previous 1.5–4.0 'literature range' was calibrated to the old
    (Imin+Imax)/2 + argmax|dI/dx| heuristic and is not a Mack-NILS bound.
    """
    m_p, a_p, orders_complex, order_indices = build_orders()

    ae = aerial_from_orders(
        orders_complex,
        order_indices,
        period_m=COMMON["period_nm"] * 1e-9,
        na=COMMON["na"],
        wavelength_m=COMMON["wavelength_nm"] * 1e-9,
        sigma=COMMON["sigma"],
        grid=COMMON["grid"],
    )
    from euvsimulator.resist.exposure import gaussian_se_blur

    dx_nm = COMMON["period_nm"] / COMMON["grid"]
    half = COMMON["grid"] // 2
    n_noblur = nils(ae, half, 128, dx_nm)
    ae_blur = gaussian_se_blur(ae, sigma=10.0, dx=dx_nm)
    n_blur = nils(ae_blur, half, 128, dx_nm)
    assert n_blur > 0.0, f"blurred NILS vanished: {n_blur:.3f}"
    assert n_blur < n_noblur, (
        f"SE blur should reduce NILS: blur={n_blur:.3f} vs none={n_noblur:.3f}"
    )


if __name__ == "__main__":
    test_nils_blur_zero()
    print("test_nils_blur_zero PASSED")
    test_nils_blur_10nm()
    print("test_nils_blur_10nm PASSED")
    test_nils_blur_reduces_nils()
    print("test_nils_blur_reduces_nils PASSED")
    print("ALL TESTS PASSED")
