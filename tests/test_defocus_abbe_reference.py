"""Defocus in the TCC and the aerial image against an independent Abbe source sum.

For a source point s (NA-normalised) the diffraction order m passes the
pupil at rho = s + f_m with f_m = m·λ/(Λ·NA) and picks up the paraxial
defocus phase W = -π·z·NA²·|rho|²/λ.  The reference below averages over a
uniform source grid (step 0.01, independent of the 256-point TCC grid in
the code) and uses only NumPy, no euvsimulator code.

Before the 2026-10 fix the code applied W(f_m), the s = 0 value, to every
source point.  Measured with that code: conventional σ 0.8, 64 nm pitch,
100 nm defocus gave contrast 0.479 instead of 0.581; the scanner dipole
0.62/0.90 90° at 36 nm pitch and 50 nm defocus gave 0.056 instead of 0.768.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from euvsimulator.aerial.abbe import _compute_tcc_matrix, aerial_from_orders

LAM_NM = 13.5
NA = 0.33
ORDERS = list(range(-5, 6))

# (name, period_nm, aerial_from_orders / _compute_tcc_matrix keywords)
CASES = {
    "conventional": (64.0, {"sigma": 0.8}),
    "dipole": (
        36.0,
        {
            "sigma": 0.90,
            "illumination_shape": "dipole",
            "sigma_inner": 0.62,
            "pole_opening_deg": 90.0,
        },
    ),
}


def _source_points(name: str, step: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Uniform source grid; the dipole poles are the annulus sectors within ±45° of the x axis."""
    g = np.arange(-1.0, 1.0 + 1e-12, step)
    sx, sy = np.meshgrid(g, g, indexing="ij")
    sx, sy = sx.ravel(), sy.ravel()
    r2 = sx**2 + sy**2
    if name == "conventional":
        keep = r2 <= 0.8**2
    else:
        keep = (np.abs(sx) >= np.abs(sy)) & (r2 <= 0.90**2) & (r2 >= 0.62**2)
    return sx[keep], sy[keep]


def _pupil_rows(orders: list[int], period_nm: float, focus_nm: float, name: str) -> np.ndarray:
    """Row i: circ(|s + f_i|) * exp(i W(s + f_i)) at every source point s."""
    sx, sy = _source_points(name)
    f = np.asarray(orders, dtype=float) * LAM_NM / (period_nm * NA)
    rho2 = (sx[None, :] + f[:, None]) ** 2 + sy[None, :] ** 2
    phase = np.exp(-1j * math.pi * focus_nm * NA**2 * rho2 / LAM_NM)
    return np.where(rho2 <= 1.0, phase, 0.0)


def _thin_mask(orders: list[int], a: float = 0.05, b: float = 0.8, duty: float = 0.5) -> np.ndarray:
    """Fourier coefficients of a line/space mask: amplitude a on the line, b in the space."""
    out = []
    for m in orders:
        if m == 0:
            out.append(a * duty + b * (1.0 - duty))
        else:
            out.append((a - b) * math.sin(math.pi * m * duty) / (math.pi * m))
    return np.array(out, dtype=complex)


def _reference_image(name: str, focus_nm: float, n_x: int = 2048) -> np.ndarray:
    """Abbe sum: mean over source points of |Σ_m a_m P_m(s) e^{i2πmx/Λ}|² on a fine x grid."""
    period_nm, _ = CASES[name]
    amps = _thin_mask(ORDERS)
    rows = _pupil_rows(ORDERS, period_nm, focus_nm, name) * amps[:, None]
    xs = np.arange(n_x) * period_nm / n_x
    waves = np.exp(2j * math.pi * np.outer(ORDERS, xs) / period_nm)
    field = rows.T @ waves  # (source points, x)
    return (np.abs(field) ** 2).mean(axis=0)


@pytest.mark.parametrize("focus_nm", [0.0, 50.0, -100.0])
@pytest.mark.parametrize("name", ["conventional", "dipole"])
def test_tcc_matches_abbe_reference(name: str, focus_nm: float) -> None:
    """TCC(i, j) = <P_i(s) P_j(s)*>_s with the defocus phase taken at s + f_i."""
    period_nm, kw = CASES[name]
    orders = [-2, -1, 0, 1, 2]
    rows = _pupil_rows(orders, period_nm, focus_nm, name)
    ref = rows @ rows.conj().T / rows.shape[1]
    tcc = _compute_tcc_matrix(
        torch.tensor(orders, dtype=torch.int64),
        na=NA,
        wavelength_m=LAM_NM * 1e-9,
        period_m=period_nm * 1e-9,
        focus_nm=focus_nm,
        **kw,
    ).numpy()
    assert np.abs(tcc - ref).max() < 0.01


@pytest.mark.parametrize(
    ("name", "focus_nm"),
    [("conventional", 0.0), ("conventional", 100.0), ("dipole", 0.0), ("dipole", 50.0)],
)
def test_image_matches_abbe_reference(name: str, focus_nm: float) -> None:
    """Image maximum and minimum agree with the Abbe sum (independent of the x sampling)."""
    period_nm, kw = CASES[name]
    img = aerial_from_orders(
        torch.tensor(_thin_mask(ORDERS), dtype=torch.complex128),
        torch.tensor(ORDERS, dtype=torch.int64),
        period_m=period_nm * 1e-9,
        na=NA,
        wavelength_m=LAM_NM * 1e-9,
        grid=64,
        focus_nm=focus_nm,
        **kw,
    )[0].numpy()
    ref = _reference_image(name, focus_nm)
    assert abs(img.max() - ref.max()) < 0.004
    assert abs(img.min() - ref.min()) < 0.004


def test_coherent_limit_is_per_order_phase() -> None:
    """With sigma = 0 only the on-axis point remains: TCC(i, j) = e^{i(φ_i - φ_j)}.

    φ_m = -π·z·m²·λ/Λ² is the defocus phase of order m at s = 0.
    """
    orders = [-2, -1, 0, 1, 2]
    period_nm, focus_nm = 48.0, 50.0
    phi = np.array([-math.pi * focus_nm * m**2 * LAM_NM / period_nm**2 for m in orders])
    # Orders outside the pupil (|m| lambda / (period NA) > 1, here m = +-2) do not
    # pass: pupil test of the coherent limit (TCC = P(f_i) conj(P(f_j))).
    inside = np.array([abs(m) * LAM_NM / (period_nm * NA) <= 1.0 for m in orders], dtype=float)
    expected = np.outer(inside, inside) * np.exp(1j * (phi[:, None] - phi[None, :]))
    tcc = _compute_tcc_matrix(
        torch.tensor(orders, dtype=torch.int64),
        sigma=0.0,
        na=NA,
        wavelength_m=LAM_NM * 1e-9,
        period_m=period_nm * 1e-9,
        focus_nm=focus_nm,
    ).numpy()
    assert np.abs(tcc - expected).max() < 1e-12


def test_symmetric_mask_is_symmetric_through_focus() -> None:
    """A real, symmetric thin mask with a point-symmetric source images I(+z) = I(-z)."""
    amps = torch.tensor(_thin_mask(ORDERS), dtype=torch.complex128)
    idx = torch.tensor(ORDERS, dtype=torch.int64)
    common = {
        "period_m": 64e-9,
        "na": NA,
        "wavelength_m": LAM_NM * 1e-9,
        "sigma": 0.8,
        "grid": 64,
    }
    plus = aerial_from_orders(amps, idx, **common, focus_nm=60.0)
    minus = aerial_from_orders(amps, idx, **common, focus_nm=-60.0)
    assert (plus - minus).abs().max().item() < 1e-10
