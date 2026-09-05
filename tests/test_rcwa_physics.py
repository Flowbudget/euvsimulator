"""Physical invariants of the 1D RCWA solver (mask3d/rcwa_torch.py).

All checks are against exact results or conservation laws -- no reference
numbers from other RCWA codes:

1. Redheffer star product: cascading two interfaces through an arbitrary
   intermediate mode basis over zero thickness equals the direct interface.
2. Homogeneous layer: RCWA == TMM for TE and TM; R + T == 1.
3. Zero-thickness grating layer: Fresnel reflection of the bare interface.
4. Effective-medium limit (P << λ): TE -> ⟨ε⟩ slab, TM -> ⟨1/ε⟩⁻¹ slab.
5. Lossless grating: energy conservation Σ R + Σ T = 1 for TE and TM.
6. Empty grating over the Mo/Si multilayer: 0th order equals the TMM
   reflection coefficient in magnitude AND phase for TE and TM.

Items 1, 4, 5 and the TM part of 6 failed before 2026-09-04 (swapped
resolvents in the star product; Laurent-rule TM formulation with inverted
admittances; E-field instead of H-field reflection coefficient in the TM
multilayer operator) -- see docs/claude_code_arbeitslog.md "Fortsetzung 13".
"""

import math

import pytest
import torch

from euvsimulator.constants import HC_EV_NM
from euvsimulator.mask3d.rcwa_torch import (
    RCWA1D,
    RCWAConfig,
    binary_grating_profile,
)
from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity

WL, PERIOD, THETA, N_SUB = 300e-9, 200e-9, 10.0, 1.5


def _solve_with_S(pol, M, prof, d, period=PERIOD, wl=WL, theta=THETA, n_sub=N_SUB, ml_stack=None):
    """Run the solver and also return the total S-matrix and k-vectors."""
    s = RCWA1D(RCWAConfig(wavelength=wl, n_orders=M, theta=theta, polarization=pol))
    captured = {}
    orig_star = RCWA1D._redheffer_star_matrix

    def spy(a, b):
        out = orig_star(a, b)
        captured["S"] = out
        return out

    RCWA1D._redheffer_star_matrix = staticmethod(spy)
    try:
        o = s.solve(
            prof,
            torch.tensor([d]),
            period,
            n_incident=torch.tensor([1 + 0j, 1 + 0j]),
            n_substrate=torch.tensor([n_sub + 0j, n_sub + 0j]),
            ml_stack=ml_stack,
        )
    finally:
        RCWA1D._redheffer_star_matrix = staticmethod(orig_star)
    k0 = 2 * math.pi / wl
    kx = k0 * math.sin(math.radians(theta)) - s.m * 2 * math.pi / period
    return s, o, captured["S"], k0, kx


def _efficiencies(pol, M, prof, d):
    s, o, S, k0, kx = _solve_with_S(pol, M, prof, d)
    kzi = torch.sqrt(k0**2 - kx**2 + 0j)
    kzs = torch.sqrt((N_SUB * k0) ** 2 - kx**2 + 0j)
    inc = torch.zeros(s.M, dtype=torch.complex128)
    inc[s.M // 2] = 1.0
    t = S[1, 0] @ inc
    kz0 = kzi[s.M // 2].real
    if pol == "TE":  # E_y amplitudes
        R = float((abs(o) ** 2 * kzi.real / kz0).sum())
        T = float((abs(t) ** 2 * kzs.real / kz0).sum())
    else:  # H_y amplitudes: power ∝ |H|² Re(kz)/ε
        R = float((abs(o) ** 2 * kzi.real / kz0).sum())
        T = float((abs(t) ** 2 * (kzs.real / N_SUB**2) / kz0).sum())
    return R, T


def _tmm(n_layer, d, te, theta=THETA, wl=WL, n_sub=N_SUB):
    R, r = reflectivity(
        torch.tensor([n_layer + 0j], dtype=torch.complex128),
        torch.tensor([d], dtype=torch.float64),
        torch.tensor([wl], dtype=torch.float64),
        torch.tensor(math.radians(theta), dtype=torch.float64),
        n_substrate=torch.tensor(n_sub + 0j, dtype=torch.complex128),
        te=te,
    )
    return float(R[0]), r[0]


# ── 1. Star product ─────────────────────────────────────────────


def test_star_product_is_basis_independent():
    torch.manual_seed(2)
    M = 5
    I = torch.eye(M, dtype=torch.complex128)

    def direct(Wa, Va, Wb, Vb):
        L = torch.cat([torch.cat([Wa, -Wb], 1), torch.cat([-Va, -Vb], 1)], 0)
        rhs = torch.cat([torch.cat([-Wa, -Va], 0), torch.cat([Wb, -Vb], 0)], 1)
        X = torch.linalg.solve(L, rhs)
        S = torch.zeros(2, 2, M, M, dtype=torch.complex128)
        S[0, 0], S[0, 1], S[1, 0], S[1, 1] = X[:M, :M], X[:M, M:], X[M:, :M], X[M:, M:]
        return S

    W = torch.randn(M, M, dtype=torch.complex128)
    V = torch.randn(M, M, dtype=torch.complex128)
    Ya = torch.diag(torch.rand(M, dtype=torch.complex128) + 0.5)
    Yb = torch.diag(torch.rand(M, dtype=torch.complex128) + 0.5)
    S = RCWA1D._redheffer_star_matrix(direct(I, Ya, W, V), direct(W, V, I, Yb))
    S_ab = direct(I, Ya, I, Yb)
    for i in (0, 1):
        for j in (0, 1):
            assert float((S[i, j] - S_ab[i, j]).abs().max()) < 1e-10


# ── 2. Homogeneous layer == TMM ─────────────────────────────────


@pytest.mark.parametrize("pol, te", [("TE", True), ("TM", False)])
def test_homogeneous_layer_matches_tmm(pol, te):
    slab = torch.full((2048,), 2.25 + 0j, dtype=torch.complex128)
    R, T = _efficiencies(pol, 11, slab, 150e-9)
    R_tmm, _ = _tmm(1.5, 150e-9, te)
    assert R == pytest.approx(R_tmm, rel=1e-8)
    assert R + T == pytest.approx(1.0, abs=1e-9)


# ── 3. Zero-thickness grating -> Fresnel ────────────────────────


@pytest.mark.parametrize("pol, te", [("TE", True), ("TM", False)])
def test_zero_thickness_grating_gives_fresnel(pol, te):
    prof = binary_grating_profile(PERIOD, 100e-9, 2.25 + 0j, 1 + 0j, n_samples=2048)
    R, T = _efficiencies(pol, 21, prof, 1e-12)
    R_fresnel, _ = _tmm(1.0, 1e-12, te)
    assert R == pytest.approx(R_fresnel, rel=1e-6)
    assert R + T == pytest.approx(1.0, abs=1e-8)


# ── 4. Effective-medium limit ──────────────────────────────────


def test_effective_medium_limit():
    P = 20e-9
    prof = binary_grating_profile(P, 10e-9, 2.25 + 0j, 1 + 0j, n_samples=2048)
    eps_par = 0.5 * (2.25 + 1.0)
    eps_perp = 1.0 / (0.5 * (1 / 2.25 + 1.0))
    s, o_te, *_ = _solve_with_S("TE", 21, prof, 150e-9, period=P, theta=0.5)
    s, o_tm, *_ = _solve_with_S("TM", 21, prof, 150e-9, period=P, theta=0.5)
    R_te = float(abs(o_te[s.M // 2]) ** 2)
    R_tm = float(abs(o_tm[s.M // 2]) ** 2)
    R_te_ref, _ = _tmm(math.sqrt(eps_par), 150e-9, True, theta=0.5)
    R_tm_ref, _ = _tmm(math.sqrt(eps_perp), 150e-9, False, theta=0.5)
    # Sub-wavelength lamellar grating: the zeroth-order response tends to the
    # anisotropic effective medium as P/λ -> 0; at P/λ = 1/15 the residual is
    # of order (P/λ)² ≈ 0.4 %. TE and TM differ by a factor 1.6 in R, so a
    # 3 % tolerance discriminates the two sharply.
    assert R_te == pytest.approx(R_te_ref, rel=0.03)
    assert R_tm == pytest.approx(R_tm_ref, rel=0.03)


# ── 5. Energy conservation ─────────────────────────────────────


@pytest.mark.parametrize("pol", ["TE", "TM"])
@pytest.mark.parametrize("M", [11, 41])
def test_lossless_grating_conserves_energy(pol, M):
    prof = binary_grating_profile(PERIOD, 100e-9, 2.25 + 0j, 1 + 0j, n_samples=2048)
    R, T = _efficiencies(pol, M, prof, 150e-9)
    assert R + T == pytest.approx(1.0, abs=2e-6)


# ── 6. Multilayer operator: magnitude and phase ─────────────────


@pytest.mark.parametrize("pol, te", [("TE", True), ("TM", False)])
def test_empty_grating_over_multilayer_matches_tmm_with_phase(pol, te):
    table = CXROTable()
    energy = HC_EV_NM / 13.5
    n_si, k_si = table.refractive_index("Si", energy)
    ml = mo_si_stack(n_bilayers=50, d_mo_nm=2.8, d_si_nm=4.1, capping_layer="Ru", d_cap_nm=2.5)
    d = 60e-9
    s = RCWA1D(RCWAConfig(wavelength=13.5e-9, n_orders=11, theta=6.0, polarization=pol))
    o = s.solve(
        torch.ones(1024, dtype=torch.complex128),
        torch.tensor([d]),
        176e-9,
        n_incident=torch.tensor([1 + 0j, 1 + 0j]),
        ml_stack=ml,
    )
    _, r = reflectivity(
        ml.n_layers,
        ml.thicknesses,
        torch.tensor([13.5e-9], dtype=torch.float64),
        torch.tensor(math.radians(6.0), dtype=torch.float64),
        n_substrate=torch.tensor(complex(n_si, k_si), dtype=torch.complex128),
        te=te,
    )
    # Reference: TMM coefficient (E-field for TM -> H-field is −r), propagated
    # up through the 60 nm vacuum gap to the RCWA reference plane.
    kz = 2 * math.pi / 13.5e-9 * math.cos(math.radians(6.0))
    r_ref = (r[0] if te else -r[0]) * complex(math.cos(2 * kz * d), math.sin(2 * kz * d))
    r0 = o[s.M // 2]
    assert abs(r0) ** 2 == pytest.approx(abs(r_ref) ** 2, rel=1e-6)
    # Phase agreement to 1e-5 rad (0.0006°); the residual ~2e-6 rad is the
    # round-off of propagating 2·kz·d ≈ 55 rad through two independent code
    # paths (eigen-decomposition vs. closed-form TMM).
    dphi = math.atan2((r0 * r_ref.conj()).imag, (r0 * r_ref.conj()).real)
    assert abs(dphi) < 1e-5
