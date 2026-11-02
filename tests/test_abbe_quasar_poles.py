"""Legacy quasar poles sit on the diagonals (45/135/225/315 deg).

Until 2026-10 the legacy quasar branch of _compute_tcc_matrix rotated the
coordinates by 30 deg, which put the four poles at 15/105/195/285 deg.
The reference below builds the intended source independently: four discs of
radius 0.2*sigma centred at (+-0.3*sigma, +-0.3*sigma), clipped to sigma.
"""

import torch

from euvsimulator.aerial.abbe import _compute_tcc_matrix

LAM = 13.5e-9
NA = 0.33


def _reference_quasar_tcc(orders, sigma, period_m, grid=256):
    f = torch.linspace(-2.0, 2.0, grid, dtype=torch.float64)
    fx, fy = torch.meshgrid(f, f, indexing="ij")
    h = 0.3 * sigma
    rp = 0.2 * sigma
    src = torch.zeros_like(fx, dtype=torch.bool)
    for cx, cy in ((h, h), (h, -h), (-h, h), (-h, -h)):
        src = src | ((fx - cx) ** 2 + (fy - cy) ** 2 <= rp**2)
    src = (src & (fx**2 + fy**2 <= sigma**2)).to(torch.float64)
    pupils = []
    for m in orders:
        fm = m * LAM / (period_m * NA)
        pupils.append(((fx + fm) ** 2 + fy**2 <= 1.0).to(torch.float64))
    n = len(orders)
    out = torch.zeros(n, n, dtype=torch.float64)
    for i in range(n):
        for j in range(n):
            out[i, j] = (src * pupils[i] * pupils[j]).sum() / src.sum()
    return out


def test_legacy_quasar_matches_diagonal_reference():
    orders = [-2, -1, 0, 1, 2]
    for period_m in (36e-9, 64e-9):
        tcc = _compute_tcc_matrix(
            torch.tensor(orders, dtype=torch.int64),
            sigma=0.8,
            na=NA,
            wavelength_m=LAM,
            period_m=period_m,
            illumination_shape="quasar",
        )
        ref = _reference_quasar_tcc(orders, 0.8, period_m)
        assert (tcc.real - ref).abs().max().item() < 1e-12, period_m
        assert tcc.imag.abs().max().item() == 0.0


def test_legacy_quasar_order_coupling_value():
    """TCC(0,+1) at P=36 nm, NA 0.33, sigma 0.8: 0.3815 (was 0.2829 with the 30 deg rotation)."""
    tcc = _compute_tcc_matrix(
        torch.tensor([-1, 0, 1], dtype=torch.int64),
        sigma=0.8,
        na=NA,
        wavelength_m=LAM,
        period_m=36e-9,
        illumination_shape="quasar",
    )
    val = tcc[1, 2].real.item()
    assert abs(val - 0.3815) < 1e-3, val
    assert abs(val - 0.2829) > 0.05, val
