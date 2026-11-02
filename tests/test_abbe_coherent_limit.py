"""An empty integration source (tiny sigma) is the on-axis coherent limit.

For 0 < sigma < ~0.011 the 256-point source grid holds no point, and until
2026-10 _compute_tcc_matrix returned TCC = 1 for every pair, also for orders
outside the pupil. aerial_from_orders admits one extra order for sigma > 0
(ceil((1 + sigma) NA P / lambda)), so at P = 64 nm the order |m| = 2
(|f_2| = 1.278 > 1) entered at full strength and the image jumped
(Imax 0.7187 instead of 0.9272 in the finding's example).
"""

import math

import torch

from euvsimulator.aerial.abbe import _compute_tcc_matrix, aerial_from_orders

KW = dict(period_m=64e-9, na=0.33, wavelength_m=13.5e-9, grid=256)


def _binary_line_orders(duty=0.35, n=3):
    idx = torch.arange(-n, n + 1, dtype=torch.int64)
    amps = []
    for m in range(-n, n + 1):
        if m == 0:
            amps.append(complex(1.0 - duty, 0.0))
        else:
            amps.append(complex(-math.sin(math.pi * m * duty) / (math.pi * m), 0.0))
    return torch.tensor(amps, dtype=torch.complex128), idx


def test_empty_source_tcc_applies_the_pupil():
    idx = torch.tensor([-2, -1, 0, 1, 2], dtype=torch.int64)
    tcc = _compute_tcc_matrix(idx, sigma=0.005, na=0.33, wavelength_m=13.5e-9, period_m=64e-9)
    inside = torch.tensor([0.0, 1.0, 1.0, 1.0, 0.0], dtype=torch.float64)
    assert torch.equal(tcc.real, torch.outer(inside, inside))
    assert tcc.imag.abs().max().item() == 0.0


def test_tiny_sigma_image_equals_sigma_zero_image():
    orders, idx = _binary_line_orders()
    ref = aerial_from_orders(orders, idx, sigma=0.0, **KW)
    for s in (0.005, 0.0105, 0.012):
        a = aerial_from_orders(orders, idx, sigma=s, **KW)
        assert (a - ref).abs().max().item() < 1e-12, s
