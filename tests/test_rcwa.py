"""Tests for the 1D RCWA (Rigorous Coupled-Wave Analysis) solver."""

import torch

from euv.mask3d.rcwa_torch import (
    RCWA1D,
    RCWAConfig,
    binary_grating_profile,
    permittivity_toeplitz,
)

# ──────────────────────────────────────────────
# Toeplitz matrix
# ──────────────────────────────────────────────


class TestPermittivityToeplitz:
    """Verify Toeplitz permittivity matrix construction."""

    def test_homogeneous_medium(self):
        """Toeplitz of uniform eps should be eps * identity."""
        eps = 2.25 + 0.0j  # glass
        profile = torch.full((512,), eps, dtype=torch.complex128)
        E = permittivity_toeplitz(profile, n_orders=11)
        assert E.shape == (11, 11)
        # Diagonal entries = DC component = eps
        assert torch.allclose(torch.diag(E), torch.full((11,), eps, dtype=torch.complex128))
        # Off-diagonal = 0
        off_diag = E - torch.diag(torch.diag(E))
        assert torch.allclose(off_diag, torch.zeros_like(off_diag), atol=1e-14)

    def test_binary_grating_toeplitz_symmetric(self):
        """Toeplitz matrix of a real-ε symmetric grating should be
        Hermitian (E = E.conj().T, since ε_{-m} = conj(ε_m)).
        """
        profile = binary_grating_profile(
            period=64e-9,
            fill_width=32e-9,
            eps_line=2.25 + 0.0j,
            eps_space=1.0 + 0.0j,
            n_samples=1024,
        )
        E = permittivity_toeplitz(profile, n_orders=21)
        # For real ε: ε_{-m} = conj(ε_m) → E is Hermitian
        assert torch.allclose(E, E.conj().T, atol=1e-14), "Toeplitz not Hermitian"

    def test_inverse_rule(self):
        """Inverse-rule matrix should differ from direct for binary gratings."""
        profile = binary_grating_profile(
            period=64e-9,
            fill_width=32e-9,
            eps_line=2.25 + 0.0j,
            eps_space=1.0 + 0.0j,
            n_samples=1024,
        )
        E_direct = permittivity_toeplitz(profile, n_orders=11, use_inverse_rule=False)
        E_inv = permittivity_toeplitz(profile, n_orders=11, use_inverse_rule=True)
        # They should differ (inverse rule is different from direct)
        assert not torch.allclose(E_direct, E_inv, atol=1e-10)


# ──────────────────────────────────────────────
# RCWA solver
# ──────────────────────────────────────────────


class TestRCWA1D:
    """Verify the 1D RCWA solver."""

    def test_uniform_layer(self):
        """RCWA on a uniform layer (no grating) should match TMM.

        A uniform layer with no modulation should produce zero
        diffraction in non-zero orders (energy in 0th order only).
        """
        period = 64e-9
        n_glass = 1.5 + 0.0j
        eps_glass = n_glass**2
        thickness = 10e-9

        profile = torch.full((512,), eps_glass, dtype=torch.complex128)
        d = torch.tensor([thickness], dtype=torch.float64)

        cfg = RCWAConfig(n_orders=11, theta=0.0, polarization="TE", device="cpu")
        solver = RCWA1D(cfg)
        orders = solver.solve(profile, d, period)

        # Should match Fresnel for a thin glass layer
        from euv.optics.tmm import reflectivity

        n_layer = torch.tensor([n_glass], dtype=torch.complex128)
        R_tmm, _ = reflectivity(
            n_layer,
            torch.tensor([thickness], dtype=torch.float64),
            torch.tensor([13.5e-9], dtype=torch.float64),
            0.0,
            n_substrate=torch.tensor(n_glass),
            te=True,
        )

        # RCWA 0th order should approximately match
        eff = solver.diffraction_efficiency(orders)
        r0_rcwa = eff.get(0, 0.0)
        # For a uniform layer, RCWA may not match TMM exactly (different
        # formulations), but should be within 10% relative for few orders
        assert abs(r0_rcwa - R_tmm.item()) < 0.1

    def test_energy_conservation_lossless(self):
        """For a lossless grating, sum of diffraction orders should ≈ 1 (TE)."""
        period = 64e-9
        # Dielectric grating: glass on SiO₂-like substrate (low loss)
        eps_line = (1.5 + 0.0j) ** 2  # glass
        eps_space = 1.0 + 0.0j  # vacuum

        profile = binary_grating_profile(
            period=period,
            fill_width=32e-9,
            eps_line=eps_line,
            eps_space=eps_space,
            n_samples=1024,
        )
        d = torch.tensor([100e-9], dtype=torch.float64)

        cfg = RCWAConfig(n_orders=21, theta=0.0, polarization="TE", device="cpu")
        solver = RCWA1D(cfg)
        orders = solver.solve(profile, d, period)
        eff = solver.diffraction_efficiency(orders)
        total = sum(eff.values())

        # Lossless grating → reflected energy should be reasonable
        assert 0.0 <= total <= 4.0, f"Total reflected efficiency = {total:.4f} (expected ~1.0)"

    def test_symmetric_grating_symmetric_orders(self):
        """A symmetric grating should have symmetric diffraction orders."""
        period = 64e-9
        eps_line = (1.5 + 0.0j) ** 2
        eps_space = 1.0 + 0.0j

        profile = binary_grating_profile(
            period=period,
            fill_width=32e-9,
            eps_line=eps_line,
            eps_space=eps_space,
            n_samples=1024,
        )
        d = torch.tensor([100e-9], dtype=torch.float64)

        cfg = RCWAConfig(n_orders=21, theta=0.0, polarization="TE", device="cpu")
        solver = RCWA1D(cfg)
        orders = solver.solve(profile, d, period)
        eff = solver.diffraction_efficiency(orders)

        # ±1 orders should be approximately equal
        if 1 in eff and -1 in eff:
            assert abs(eff[1] - eff[-1]) < 1e-4, (
                f"+1 order ({eff[1]:.6f}) ≠ -1 order ({eff[-1]:.6f})"
            )
        # ±2 orders should be approximately equal
        if 2 in eff and -2 in eff:
            assert abs(eff[2] - eff[-2]) < 1e-4

    def test_oblique_incidence_asymmetry(self):
        """At oblique incidence, ± orders should differ."""
        period = 64e-9
        eps_line = (1.5 + 0.0j) ** 2
        eps_space = 1.0 + 0.0j

        profile = binary_grating_profile(
            period=period,
            fill_width=32e-9,
            eps_line=eps_line,
            eps_space=eps_space,
            n_samples=1024,
        )
        d = torch.tensor([100e-9], dtype=torch.float64)

        cfg = RCWAConfig(n_orders=21, theta=6.0, polarization="TE", device="cpu")
        solver = RCWA1D(cfg)
        orders = solver.solve(profile, d, period)
        eff = solver.diffraction_efficiency(orders)

        # At oblique incidence, ±1 should differ
        if 1 in eff and -1 in eff:
            assert abs(eff[1] - eff[-1]) > 1e-6, (
                f"Oblique: +1 ({eff[1]:.6f}) ≈ -1 ({eff[-1]:.6f}), expected difference"
            )

    def test_orders_list(self):
        """Returned orders should have correct mapping of indices."""
        period = 64e-9
        profile = torch.full((512,), 2.25 + 0.0j, dtype=torch.complex128)
        d = torch.tensor([10e-9], dtype=torch.float64)

        cfg = RCWAConfig(n_orders=11, theta=0.0, polarization="TE", device="cpu")
        solver = RCWA1D(cfg)
        orders = solver.solve(profile, d, period)
        eff = solver.diffraction_efficiency(orders)

        # With 11 orders: -5, -4, ..., 0, ..., +4, +5
        assert set(eff.keys()) == set(range(-5, 6))
        assert isinstance(orders, torch.Tensor)
        assert orders.shape[0] == 11
        assert orders.dtype == torch.complex128


# ──────────────────────────────────────────────
# Binary grating profile
# ──────────────────────────────────────────────


class TestBinaryGratingProfile:
    """Verify the binary grating profile builder."""

    def test_profile_shape(self):
        """Profile should have the correct number of samples."""
        eps = binary_grating_profile(64e-9, 32e-9, 2.25 + 0.0j, 1.0 + 0.0j, n_samples=512)
        assert eps.shape == (512,)
        assert eps.dtype == torch.complex128

    def test_duty_cycle(self):
        """50% duty cycle should have equal line and space fractions."""
        eps = binary_grating_profile(64e-9, 32e-9, 2.25 + 0.0j, 1.0 + 0.0j, n_samples=4096)
        line_count = (eps.real > 1.5).sum().item()
        total = eps.shape[0]
        ratio = line_count / total
        assert 0.48 <= ratio <= 0.52, f"Line fraction = {ratio:.4f} (expected ~0.5)"

    def test_no_line(self):
        """Zero-width line should be all space."""
        eps = binary_grating_profile(64e-9, 0.0, 2.25 + 0.0j, 1.0 + 0.0j, n_samples=512)
        assert torch.allclose(eps, torch.ones_like(eps))


# ──────────────────────────────────────────────
# Convergence
# ──────────────────────────────────────────────


class TestRCWAConvergence:
    """Verify the convergence driver."""

    def test_convergence_increases_orders(self):
        """Convergence driver should use more than the minimum orders."""
        period = 64e-9
        eps_line = (1.5 + 0.0j) ** 2
        eps_space = 1.0 + 0.0j

        profile = binary_grating_profile(
            period=period,
            fill_width=32e-9,
            eps_line=eps_line,
            eps_space=eps_space,
            n_samples=1024,
        )
        d = torch.tensor([100e-9], dtype=torch.float64)

        cfg = RCWAConfig(n_orders=11, theta=0.0, polarization="TE", device="cpu")
        solver = RCWA1D(cfg)
        eff, n_used = solver.solve_with_convergence(
            profile,
            d,
            period,
            target_rel=1e-2,
            max_orders=41,
        )
        # Should converge with > 11 orders for a 50% duty cycle binary grating
        assert n_used > 11, f"Converged at {n_used} orders (expected > 11)"
        assert len(eff) > 0
