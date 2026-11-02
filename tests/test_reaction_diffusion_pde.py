"""Concurrent reaction-diffusion PEB (Kang/NIST 2009 Eqs. 1-3).

Zero-parameter anchor: the NIST bilayer diffusion lengths of Table 2 (JSR
EUV resist, PEB 90 C / 900 s, PAG 2 wt% -> 0.035 nm^-3, quencher 60 mol% of
the PAG, all PAG converted, solubility switch at deprotection 0.14):
measured 76 / 56 / 36 / 23 nm for no quencher / quencher in the acid layer /
in the receiving layer / in both; NIST's own model with their Table 1
predicts 79 / 59 / 30 / 23 nm. Table 1 (checked against the original
2026-09-25): kP 1.6 nm^3/s, kT 0.026 1/s, DH 4.2 nm^2/s, kQ 1.6 ± 1.0 nm^3/s,
DQ 7.3 ± 3.0 nm^2/s.  (The log of 2026-09-06 said kQ is not listed there; it
is.)  The chain default kQ = 1.2 nm^3/s with DQ = DH was chosen on cases 3
and 4, and lies inside the measured kQ range.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.peb import reaction_diffusion_pde

PAG = 0.024 / 412.0 * 6.02214076e23 * 1e-21  # nm^-3
Q0 = 0.6 * PAG
KP, KT, DH, KQ = 1.6, 0.026, 4.2, 1.2
DX = 0.5


def _bilayer(
    q_top: float,
    q_bottom: float,
    kq: float = KQ,
    dq: float | None = None,
) -> float:
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
        quench_rate=kq,
        t_bake=900.0,
        dx=DX,
        pag_density=PAG,
        dt=2.0,
        D_quencher=dq,
    )
    phi = 1.0 - M[0, 0]
    beyond = x[(x >= 800.0) & (phi >= 0.14)]
    return float(beyond.max() - 800.0 + DX) if beyond.numel() else 0.0


@pytest.mark.parametrize(
    "q_top, q_bottom, nist_model",
    [(0.0, 0.0, 79.0), (Q0, 0.0, 59.0), (0.0, Q0, 30.0), (Q0, Q0, 23.0)],
)
def test_same_equations_and_parameters_reproduce_nists_model(q_top, q_bottom, nist_model):
    """Zero-parameter implementation check: with the full Table 1 set (kQ 1.6,
    DQ 7.3) the chain solves NIST's equations and must land on NIST's own
    predictions.  Measured 2026-09-25: 84 / 63 / 28.5 / 21.5 nm (+6 %, +7 %,
    -5 %, -7 %; dt-converged).
    """
    ld = _bilayer(q_top, q_bottom, kq=1.6, dq=7.3)
    assert ld == pytest.approx(nist_model, rel=0.10), ld


@pytest.mark.parametrize(
    "q_top, q_bottom, measured",
    [(0.0, 0.0, 76.0), (Q0, 0.0, 56.0), (0.0, Q0, 36.0), (Q0, Q0, 23.0)],
)
def test_nist_bilayer_diffusion_lengths(q_top, q_bottom, measured):
    """Chain defaults (kQ 1.2, DQ = DH) against the measurement: 84 / 68.5 /
    31.5 / 25.5 nm, i.e. +11 %, +22 %, -12.5 %, +11 %.  One tolerance for all
    four cases (NIST's own model deviates up to -17 %); the former per-case
    tolerances 15/30/25/25 % each sat just above the deviation of its case.
    """
    ld = _bilayer(q_top, q_bottom)
    assert ld == pytest.approx(measured, rel=0.25), ld


def test_quencher_in_the_receiving_layer_shortens_the_reach():
    """Quencher below the interface consumes the arriving acid: 31.5 against
    84 nm.  (The former name also claimed a first-order loss "would not"; that
    half was never tested.)
    """
    assert _bilayer(0.0, Q0) < 0.6 * _bilayer(0.0, 0.0)


def _flood_error(step: float) -> float:
    """|M - M_exact| for uniform fields, where the PDE reduces to the ODE
    dphi/dt = k h (1-phi), dh/dt = -k_trap h phi (reference: RK4, dt 5e-4,
    self-consistent to 1e-15).
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
        dt=step,
    )

    def rhs(p: float, a: float) -> tuple[float, float]:
        return 2.0 * a * (1 - p), -0.5 * a * p

    phi, hh, dt = 0.0, 0.3, 5e-4
    for _ in range(int(round(10.0 / dt))):
        k1 = rhs(phi, hh)
        k2 = rhs(phi + dt / 2 * k1[0], hh + dt / 2 * k1[1])
        k3 = rhs(phi + dt / 2 * k2[0], hh + dt / 2 * k2[1])
        k4 = rhs(phi + dt * k3[0], hh + dt * k3[1])
        phi += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        hh += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
    return abs(float(M.mean()) - (1 - phi))


def test_uniform_flood_reduces_to_the_ode():
    """Measured error 1.1e-5 at dt 0.05.  The former reference (explicit
    Euler, dt 1e-4) had an error of its own of 5.6e-6, and the bound 2e-3
    would also have passed dt 0.5 (1.2e-3).
    """
    assert _flood_error(0.05) < 3e-5


def test_splitting_is_second_order_in_time():
    """Halving dt quarters the error: 4.6e-5 (dt 0.1) / 1.1e-5 (dt 0.05) = 4.0."""
    ratio = _flood_error(0.1) / _flood_error(0.05)
    assert 3.0 < ratio < 5.0, ratio
