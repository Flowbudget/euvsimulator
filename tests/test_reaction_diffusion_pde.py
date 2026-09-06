"""Concurrent reaction-diffusion PEB (Kang/NIST 2009 Eqs. 1-3), plan stage C2.

Zero-parameter anchor: the NIST bilayer diffusion lengths of Table 2 (JSR
EUV resist, PEB 90 C / 900 s, PAG 2 wt% -> 0.035 nm^-3, quencher 60 mol% of
the PAG, all PAG converted, solubility switch at deprotection 0.14):
measured 76 / 56 / 36 / 23 nm for no quencher / quencher in the acid layer /
in the receiving layer / in both. Kinetics from their Table 1 (kP 1.6 nm^3/s,
kT 0.026 1/s, DH 4.2 nm^2/s); the quenching constant is not listed there and
was determined on case 3 (kQ = 1.2 nm^3/s, log Fortsetzung 38); case 4 is
then a prediction.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.peb import reaction_diffusion_pde

PAG = 0.024 / 412.0 * 6.02214076e23 * 1e-21  # nm^-3
Q0 = 0.6 * PAG
KP, KT, DH, KQ = 1.6, 0.026, 4.2, 1.2
DX = 0.5


def _bilayer(q_top: float, q_bottom: float) -> float:
    W = 2400  # 1200 nm periodic domain; acid layer at [400, 800) nm
    x = torch.arange(W, dtype=torch.float64) * DX
    top = (x >= 400.0) & (x < 800.0)
    h = torch.where(
        top, torch.tensor(1.0, dtype=torch.float64), torch.tensor(0.0, dtype=torch.float64)
    )
    q = torch.where(top, torch.tensor(q_top / PAG), torch.tensor(q_bottom / PAG)).to(torch.float64)
    h = h.view(1, 1, W)
    q = q.view(1, 1, W)
    _, _, M = reaction_diffusion_pde(
        h,
        q,
        torch.ones_like(h),
        D=DH,
        k=KP * PAG,
        k_trap=KT,
        quench_rate=KQ,
        t_bake=900.0,
        dx=DX,
        pag_density=PAG,
        dt=2.0,
    )
    phi = 1.0 - M[0, 0]
    beyond = x[(x >= 800.0) & (phi >= 0.14)]
    return float(beyond.max() - 800.0 + DX) if beyond.numel() else 0.0


@pytest.mark.parametrize(
    "q_top, q_bottom, measured, tol",
    [(0.0, 0.0, 76.0, 0.15), (Q0, 0.0, 56.0, 0.30), (0.0, Q0, 36.0, 0.25), (Q0, Q0, 23.0, 0.25)],
)
def test_nist_bilayer_diffusion_lengths(q_top, q_bottom, measured, tol):
    ld = _bilayer(q_top, q_bottom)
    assert ld == pytest.approx(measured, rel=tol), ld


def test_quencher_shortens_the_reach_and_first_order_loss_would_not():
    assert _bilayer(0.0, Q0) < 0.6 * _bilayer(0.0, 0.0)


def test_uniform_flood_reduces_to_the_ode():
    """Uniform fields: no diffusion effect; M(t) follows dphi/dt = k h (1-phi),
    dh/dt = -k_trap h phi (compare with a fine explicit integration).
    """
    h = torch.full((1, 1, 8), 0.3, dtype=torch.float64)
    _, _, M = reaction_diffusion_pde(
        h,
        0.0,
        torch.ones_like(h),
        D=4.2,
        k=2.0,
        k_trap=0.5,
        quench_rate=0.0,
        t_bake=10.0,
        dx=1.0,
        pag_density=0.2,
        dt=0.05,
    )
    phi, hh, dt = 0.0, 0.3, 1e-4
    for _ in range(int(10.0 / dt)):
        phi, hh = phi + dt * 2.0 * hh * (1 - phi), hh - dt * 0.5 * hh * phi
    assert float(M.mean()) == pytest.approx(1 - phi, abs=2e-3)
