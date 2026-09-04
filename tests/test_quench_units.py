"""Acid-base quenching: k_Q [nm³/s] acts on number densities; on relative
concentrations h = H/G0, q = Q/G0 the rate is k_Q·G0 [1/s].

Mack, Biafore & Smith 2011 (Proc. SPIE 7972, 797202) give the baseline as
k_Q = 15 nm³/s, G0 = 0.2 nm⁻³ and state the converted value explicitly:
"k_Q·G0 = 3 s⁻¹". Before 2026-09-04 the unconverted 15 was used as the
relative-concentration rate (5× too fast; audit A4).
"""

import math

import pytest
import torch

from euvsimulator.resist.peb import _reaction_limited_quench, reaction_diffusion_with_quenching


def test_relative_rate_is_kq_times_g0():
    """For an acid excess d = h0 - q0 the minor species (quencher) decays
    with exponent d·(k_Q·G0)·t; check the closed form against that with
    G0 = 0.2, k_Q = 15 -> 3 s^-1, over a bake short enough not to saturate."""
    h0 = torch.full((8, 8), 0.60)
    q0 = torch.full((8, 8), 0.25)
    kq, g0, t = 15.0, 0.2, 0.5  # nm^3/s, nm^-3, s
    # Route through the public function with no diffusion (D=0) so only the
    # kinetics act; k=0 keeps the inhibitor untouched.
    _, q_final, _ = reaction_diffusion_with_quenching(
        h0, q0, torch.ones_like(h0), D=0.0, k=0.0, quench_rate=kq, t_bake=t,
        sigma_diff=None, dx=1.0, pag_density=g0,
    )
    # Closed form of dq/dt = -r*h*q with h - q = d conserved:
    d = 0.60 - 0.25
    r = kq * g0
    expected = 0.25 * d * math.exp(-d * r * t) / (0.60 - 0.25 * math.exp(-d * r * t))
    assert float(q_final.mean()) == pytest.approx(expected, rel=1e-5)
    # And it must NOT equal the unconverted (5x faster) kinetics.
    wrong = 0.25 * d * math.exp(-d * kq * t) / (0.60 - 0.25 * math.exp(-d * kq * t))
    assert abs(float(q_final.mean()) - wrong) > 10 * abs(float(q_final.mean()) - expected)


def test_pag_density_is_required():
    h0 = torch.full((4, 4), 0.5)
    with pytest.raises(ValueError, match="pag_density"):
        reaction_diffusion_with_quenching(
            h0, h0 * 0.5, torch.ones_like(h0), D=0.0, k=0.0, quench_rate=15.0, t_bake=1.0
        )


def test_closed_form_conserves_difference():
    """h - q is conserved by the bimolecular reaction for both signs; with
    an excess of either species the minor one is consumed exponentially,
    while for h0 == q0 second-order kinetics decay only as 1/(1 + h0·r·t)."""
    h0 = torch.tensor([0.6, 0.2, 0.3])
    q0 = torch.tensor([0.25, 0.4, 0.3])
    r, t = 3.0, 60.0
    h, q = _reaction_limited_quench(h0, q0, rate=r, t=t)
    assert torch.allclose(h - q, h0 - q0, atol=1e-6)
    assert float(torch.minimum(h, q)[:2].max()) < 1e-6  # excess cases: minor consumed
    assert float(h[2]) == pytest.approx(0.3 / (1.0 + 0.3 * r * t), rel=1e-6)  # equal case
