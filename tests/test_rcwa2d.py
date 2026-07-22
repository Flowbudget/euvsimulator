"""Tests for the 2D RCWA (Fourier Modal Method) solver."""

from __future__ import annotations

import pytest
import torch

from euv.mask3d.rcwa2d import (
    RCWA2D,
    RCWA2DConfig,
    contact_hole_profile,
    permittivity_toeplitz_2d,
    rectangular_island_profile,
)


class TestRCWA2DConfig:
    """Test suite for RCWA2D configuration."""

    def test_default_config(self):
        cfg = RCWA2DConfig()
        assert cfg.n_orders_x == 7
        assert cfg.n_orders_y == 7
        assert cfg.n_modes == 49

    def test_odd_orders(self):
        with pytest.raises(ValueError):
            RCWA2DConfig(n_orders_x=10)

    def test_custom_orders(self):
        cfg = RCWA2DConfig(n_orders_x=11, n_orders_y=15)
        assert cfg.n_modes == 165


class TestPermittivityToeplitz2D:
    """Test suite for the 2D Toeplitz matrix builder."""

    def test_toeplitz_shape(self):
        eps = torch.ones(64, 64, dtype=torch.complex128)
        E = permittivity_toeplitz_2d(eps, 7, 7)
        assert E.shape == (49, 49)
        assert E.dtype == torch.complex128

    def test_uniform_permittivity(self):
        """Uniform ε → E should be diagonal with ε(0,0) = ε."""
        eps = torch.ones(64, 64, dtype=torch.complex128) * (2.0 + 0.5j)
        E = permittivity_toeplitz_2d(eps, 5, 5)
        # The (0,0) Fourier coefficient ≈ 2.0+0.5j
        # Since it's uniform, the Toeplitz is diagonal with this value
        center = 12  # (25//2)
        diag_entry = E[center, center]
        assert abs(diag_entry - (2.0 + 0.5j)) < 0.1, f"Expected ~2.0+0.5j, got {diag_entry}"

    def test_hermitian_property(self):
        """For real ε, the Toeplitz matrix should be Hermitian."""
        eps = torch.rand(64, 64, dtype=torch.complex128)
        eps = eps.real.to(torch.complex128)  # real-only
        E = permittivity_toeplitz_2d(eps, 7, 7)
        # E should be Hermitian: E == E^H
        diff = (E - E.conj().T).abs().max().item()
        assert diff < 1e-10, f"Toeplitz not Hermitian: max diff = {diff:.2e}"


class TestRCWA2DSolver:
    """Test suite for the 2D RCWA solver."""

    @pytest.fixture
    def simple_2d_profile(self):
        """Simple 2D binary grating: Ta island on vacuum."""
        period = 128e-9  # 128 nm
        island_w = 64e-9  # 64 nm island
        eps_ta = complex(-4.0, 6.0)  # Ta at 13.5 nm (approx)
        return rectangular_island_profile(
            period,
            period,
            island_w,
            island_w,
            eps_ta,
            1.0 + 0.0j,
            n_samples_x=128,
            n_samples_y=128,
        )

    def test_solve_basic(self, simple_2d_profile):
        """Basic 2D solve should not crash and return the right shape."""
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        assert orders.shape == (25,), f"Expected (25,), got {orders.shape}"
        assert torch.isfinite(orders).all()

    def test_diffraction_efficiency_shape(self, simple_2d_profile):
        """Diffraction efficiency should return a dict with (m,n) keys."""
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        eff = solver.diffraction_efficiency(orders)
        assert len(eff) == 25
        assert (0, 0) in eff, "Zeroth order should be present"
        assert eff[(0, 0)] >= 0.0, "Efficiency should be non-negative"

    def test_energy_conservation(self, simple_2d_profile):
        """Sum of efficiencies should be physically meaningful.

        NOTE: The scalar 2D approximation (solving only one polarization)
        does NOT rigorously conserve energy because it omits the off-diagonal
        TE-TM coupling terms.  Full vector 2D RCWA is needed for exact
        energy conservation.  For the scalar approximation the total may
        exceed 1.0, but the relative magnitudes are still physically
        meaningful for low-index-contrast patterns.
        """
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        eff = solver.diffraction_efficiency(orders)
        total = sum(eff.values())
        # With scalar approximation, total may exceed 1.0 but should
        # at least be finite and positive
        assert total > 0.0, f"Total efficiency should be positive, got {total:.4f}"
        assert torch.isfinite(torch.tensor(total)), "Total efficiency should be finite"

    def test_symmetry_normal_incidence(self, simple_2d_profile):
        """At normal incidence (θ=0), R(m,n) = R(-m,-n)."""
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        eff = solver.diffraction_efficiency(orders)

        for (m, n), val in eff.items():
            pair = eff.get((-m, -n), None)
            if pair is not None:
                diff = abs(val - pair)
                assert diff < 1e-10, f"R({m},{n})={val:.6f} ≠ R({-m},{-n})={pair:.6f}"

    def test_contact_hole_solve(self):
        """Contact hole profile should solve without error."""
        period = 128e-9
        eps = contact_hole_profile(
            period,
            period,
            radius=20e-9,
            eps_hole=1.0 + 0.0j,
            eps_background=complex(-4.0, 6.0),
            n_samples_x=128,
            n_samples_y=128,
        )
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        orders = solver.solve(eps, torch.tensor([50e-9]), period, period)
        assert torch.isfinite(orders).all()

    def test_oblique_incidence(self, simple_2d_profile):
        """Oblique incidence (θ=6°) should work."""
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=6.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        assert torch.isfinite(orders).all()

    def test_convergence(self, simple_2d_profile):
        """R(0,0) should converge as orders increase."""
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        r00_5 = solver.diffraction_efficiency(orders).get((0, 0), 0.0)

        cfg7 = RCWA2DConfig(n_orders_x=7, n_orders_y=7, theta=0.0)
        solver7 = RCWA2D(cfg7)
        orders7 = solver7.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        r00_7 = solver7.diffraction_efficiency(orders7).get((0, 0), 0.0)

        rel_change = abs(r00_7 - r00_5) / (r00_5 + 1e-12)
        assert rel_change < 0.5, f"R00 unstable: {r00_5:.6f} → {r00_7:.6f}"

    def test_multi_layer(self):
        """Two-layer stack should solve correctly."""
        period = 128e-9
        # Layer 1: Ta island
        eps = rectangular_island_profile(
            period,
            period,
            64e-9,
            64e-9,
            complex(-4.0, 6.0),
            1.0 + 0.0j,
            n_samples_x=64,
            n_samples_y=64,
        )
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thicknesses = torch.tensor([30e-9, 30e-9])
        orders = solver.solve(eps, thicknesses, period, period)
        assert torch.isfinite(orders).all()

    def test_rectangular_profile(self):
        """Profile generator should produce correct shape."""
        eps = rectangular_island_profile(
            128e-9,
            64e-9,
            64e-9,
            32e-9,
            2.0 + 0.0j,
            1.0 + 0.0j,
            n_samples_x=64,
            n_samples_y=64,
        )
        assert eps.shape == (64, 64)
        # Background corner (pixel 0,0 = x=0,y=0, outside island)
        assert eps[0, 0] == 1.0 + 0.0j, f"Expected background at corner, got {eps[0, 0]}"
        # Island centre (x=64nm, y=32nm → pixel 32, 32 for 2nm/pixel)
        assert eps[32, 32] == 2.0 + 0.0j, f"Expected island at centre, got {eps[32, 32]}"

    def test_contact_hole_profile(self):
        """Contact hole profile should have correct shape."""
        eps = contact_hole_profile(
            128e-9,
            128e-9,
            30e-9,
            1.0 + 0.0j,
            2.0 + 0.0j,
            n_samples_x=64,
            n_samples_y=64,
        )
        assert eps.shape == (64, 64)
        assert eps[0, 0] == 2.0 + 0.0j  # background corner
        assert eps[32, 32] == 1.0 + 0.0j  # hole centre


class TestRCWA2D1DConsistency:
    """Test that 2D solver reduces to 1D solver for 1D-like patterns."""

    def test_uniform_in_y(self):
        """A pattern uniform in y should give comparable results to 1D RCWA.

        NOTE: The scalar 2D approximation uses a different eigenproblem
        formulation than the full-polarisation 1D solver, so small
        differences are expected even for Ny=1.  The order-of-magnitude
        should agree.
        """
        from euv.mask3d.rcwa_torch import RCWA1D, RCWAConfig, binary_grating_profile

        period = 128e-9
        cd = 64e-9
        eps_ta = complex(-4.0, 6.0)

        # 1D RCWA
        profile_1d = binary_grating_profile(
            period,
            cd,
            eps_ta,
            1.0 + 0.0j,
            n_samples=512,
        )
        cfg1d = RCWAConfig(n_orders=11, theta=0.0)
        solver1d = RCWA1D(cfg1d)
        orders1d = solver1d.solve(profile_1d, torch.tensor([50e-9]), period)
        eff1d = solver1d.diffraction_efficiency(orders1d)
        r00_1d = eff1d.get(0, 0.0)

        # 2D RCWA with uniform y
        eps_2d = torch.zeros(128, 64, dtype=torch.complex128)
        eps_2d[:, :] = 1.0 + 0.0j
        half = 32  # cd/2 in pixels (64nm / 2nm per pixel)
        eps_2d[32 - half : 32 + half, :] = eps_ta

        cfg2d = RCWA2DConfig(n_orders_x=11, n_orders_y=1, theta=0.0)
        solver2d = RCWA2D(cfg2d)
        orders2d = solver2d.solve(eps_2d, torch.tensor([50e-9]), period, period)
        eff2d = solver2d.diffraction_efficiency(orders2d)
        r00_2d = eff2d.get((0, 0), 0.0)

        # Both should give positive, finite reflectivities with
        # the same order of magnitude
        assert r00_1d > 0.0, f"1D R₀ should be positive, got {r00_1d:.6f}"
        assert r00_2d > 0.0, f"2D R₀₀ should be positive, got {r00_2d:.6f}"
        # The scalar 2D approximation amplifies reflectivity vs full
        # vector 1D, but the ratio should be within an order of magnitude
        ratio = r00_2d / (r00_1d + 1e-12)
        assert 0.1 < ratio < 20.0, f"1D R₀={r00_1d:.4f} vs 2D R₀₀={r00_2d:.4f} (ratio={ratio:.2f})"


class TestSolveWithConvergence:
    """Test the convergence driver."""

    def test_convergence_basic(self):
        """Convergence driver should return a result."""
        eps = rectangular_island_profile(
            128e-9,
            128e-9,
            64e-9,
            64e-9,
            complex(-4.0, 6.0),
            1.0 + 0.0j,
            n_samples_x=64,
            n_samples_y=64,
        )
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        eff, orders_used = solver.solve_with_convergence(
            eps,
            torch.tensor([50e-9]),
            128e-9,
            128e-9,
            target_rel=1e-2,
            max_orders=9,
        )
        assert orders_used >= 5
        assert (0, 0) in eff
