"""aerial_from_orders samples one period with pitch P/G (endpoint excluded).

Until 2026-10 the sample positions were linspace(-P/2, P/2, G): pitch
P/(G-1), the last sample a copy of the first, every length in nm low by
(G-1)/G, and a line moved across the array boundary changed CD and NILS
(G=64: CD 24.72 centred vs 25.29 at the boundary).
"""

import math

import torch

from euvsimulator.aerial.abbe import aerial_from_orders
from euvsimulator.pipeline import SimulationConfig, _cd_via_aerial_threshold

KW = dict(period_m=64e-9, na=0.33, wavelength_m=13.5e-9, sigma=0.8)


def _line_orders(duty=0.5, n=21, r_abs=0.05, r_space=0.70):
    idx = torch.arange(-n, n + 1, dtype=torch.int64)
    amps = []
    for m in range(-n, n + 1):
        if m == 0:
            amps.append(complex(r_abs * duty + r_space * (1.0 - duty)))
        else:
            amps.append(complex((r_abs - r_space) * math.sin(math.pi * m * duty) / (math.pi * m)))
    return torch.tensor(amps, dtype=torch.complex128), idx


def test_samples_sit_at_minus_half_period_plus_k_pitch():
    """Orders +-1 with amplitude 0.5 (coherent) give I(x) = cos^2(2 pi x / P)."""
    G = 64
    P = 64e-9
    idx = torch.tensor([-1, 0, 1], dtype=torch.int64)
    orders = torch.tensor([0.5, 0.0, 0.5], dtype=torch.complex128)
    a = aerial_from_orders(
        orders, idx, period_m=P, na=0.33, wavelength_m=13.5e-9, sigma=0.0, grid=G
    )
    x = -P / 2 + P * torch.arange(G, dtype=torch.float64) / G
    expected = torch.cos(2 * math.pi * x / P) ** 2
    assert (a[0] - expected).abs().max().item() < 1e-12


def test_cd_and_nils_do_not_depend_on_line_position():
    """Moving the line by half a period (orders times (-1)^m) keeps CD and NILS."""
    orders, idx = _line_orders()
    sign = torch.tensor([(-1.0) ** int(m) for m in idx], dtype=torch.complex128)
    for G in (64, 256):
        cfg = SimulationConfig(grid=G, dose_mj_cm2=20.0)
        a_centre = aerial_from_orders(orders, idx, grid=G, **KW)
        a_edge = aerial_from_orders(orders * sign, idx, grid=G, **KW)
        cd_c, _, nils_c = _cd_via_aerial_threshold(a_centre, cfg, G // 2, G // 2)
        cd_e, _, nils_e = _cd_via_aerial_threshold(a_edge, cfg, G // 2, G // 2)
        assert cd_c > 20.0, (G, cd_c)
        assert abs(cd_c - cd_e) < 1e-9, (G, cd_c, cd_e)
        assert abs(nils_c - nils_e) < 1e-9, (G, nils_c, nils_e)


def test_edge_between_last_and_first_sample_is_found():
    """A line edge inside the segment from sample G-1 to sample 0 is a crossing.

    The line is moved so that its left edge sits half a pixel before x = +P/2.
    Without the (G-1, 0) pair in the crossing loops only one edge is found
    and CD and NILS collapse to 0.
    """
    G = 64
    p_nm = 64.0
    dx = p_nm / G
    orders, idx = _line_orders()
    cfg = SimulationConfig(grid=G, dose_mj_cm2=20.0)
    a0 = aerial_from_orders(orders, idx, grid=G, **KW)
    cd0, _, nils0 = _cd_via_aerial_threshold(a0, cfg, G // 2, G // 2)
    shift_nm = p_nm / 2 - dx / 2 + cd0 / 2
    phase = torch.exp(-2j * math.pi * idx.to(torch.float64) * shift_nm / p_nm)
    a1 = aerial_from_orders(orders * phase, idx, grid=G, **KW)
    cd1, _, nils1 = _cd_via_aerial_threshold(a1, cfg, G // 2, G // 2)
    assert abs(cd1 - cd0) < 0.05, (cd0, cd1)
    assert abs(nils1 - nils0) < 0.05 * nils0, (nils0, nils1)
