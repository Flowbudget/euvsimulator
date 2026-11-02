"""Tests for the 2D RCWA (Fourier Modal Method) solver."""

from __future__ import annotations

import pytest
import torch

from euvsimulator.mask3d.rcwa2d import (
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
        """A passive structure reflects at most the incident power.

        The scalar model omits TE-TM coupling, but it conserves the flux of
        its own scalar field; with power-weighted efficiencies the total of a
        lossy structure is therefore below 1.
        """
        cfg = RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=0.0)
        solver = RCWA2D(cfg)
        thickness = torch.tensor([50e-9])
        orders = solver.solve(simple_2d_profile, thickness, 128e-9, 128e-9)
        eff = solver.diffraction_efficiency(orders)
        total = sum(eff.values())
        assert 0.0 < total <= 1.0 + 1e-10, f"Total efficiency {total:.6f} outside (0, 1]"

    @pytest.mark.parametrize("theta", [0.0, 6.0])
    def test_lossless_pattern_on_mirror_reflects_everything(self, theta):
        """Lossless 2D pattern on a lossless mirror (n = 10i): sum R = 1.

        Guards both the propagation sign of the eigenproblem and the branch
        choice of q; the latter lost 5.5e-4 at normal incidence before
        2026-09-25.
        """
        eps = torch.ones(64, 64, dtype=torch.complex128)
        eps[16:48, 20:44] = 2.25
        solver = RCWA2D(RCWA2DConfig(n_orders_x=7, n_orders_y=7, theta=theta))
        mirror = torch.tensor([10j, 10j], dtype=torch.complex128)
        orders = solver.solve(
            eps, torch.tensor([40e-9], dtype=torch.float64), 64e-9, 64e-9, n_substrate=mirror
        )
        total = sum(solver.diffraction_efficiency(orders).values())
        assert total == pytest.approx(1.0, abs=1e-9)

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

    def test_vacuum_layer_is_transparent(self):
        """A layer of vacuum in vacuum reflects nothing (was R00 = 1)."""
        eps = torch.ones(32, 32, dtype=torch.complex128)
        solver = RCWA2D(RCWA2DConfig(n_orders_x=5, n_orders_y=5))
        orders = solver.solve(eps, torch.tensor([50e-9]), 128e-9, 128e-9)
        assert solver.diffraction_efficiency(orders)[(0, 0)] < 1e-20

    def test_homogeneous_slab_matches_airy(self):
        """Homogeneous slab (eps 2.25, 50 nm, 6 deg, TE) against the Airy formula."""
        import cmath
        import math

        lam, d, th, n = 13.5e-9, 50e-9, math.radians(6.0), 1.5
        k0 = 2 * math.pi / lam
        kx = k0 * math.sin(th)
        kz0 = cmath.sqrt(k0**2 - kx**2)
        kz1 = cmath.sqrt((n * k0) ** 2 - kx**2)
        r01 = (kz0 - kz1) / (kz0 + kz1)
        ph = cmath.exp(2j * kz1 * d)
        r_airy = abs((r01 - r01 * ph) / (1 - r01 * r01 * ph)) ** 2

        eps = torch.full((32, 32), 2.25 + 0j, dtype=torch.complex128)
        solver = RCWA2D(RCWA2DConfig(n_orders_x=5, n_orders_y=5, theta=6.0))
        orders = solver.solve(eps, torch.tensor([d], dtype=torch.float64), 128e-9, 128e-9)
        assert solver.diffraction_efficiency(orders)[(0, 0)] == pytest.approx(r_airy, rel=1e-10)

    def test_uniform_in_y(self):
        """A pattern uniform in y must reproduce the 1D TE solver exactly.

        With the former operator Kx² + Ky² − ε both solvers differed by a
        factor 11.9 for eps = −4+6i and by 6600 for real Ta.
        """
        from euvsimulator.mask3d.rcwa_torch import RCWA1D, RCWAConfig

        period = 128e-9
        cd = 64e-9
        eps_ta = complex(0.915, 0.065)  # Ta at 13.5 nm, n = 0.9567 + 0.0340i

        # 2D profile uniform in y: 64 nm Ta line in a 128 nm period (1 nm per sample)
        eps_2d = torch.ones(128, 64, dtype=torch.complex128)
        eps_2d[0 : int(round(cd / 1e-9)), :] = eps_ta

        # 1D RCWA on the very same x samples (a different sampling of the step
        # changes the Fourier coefficients at the 1e-5 level)
        cfg1d = RCWAConfig(n_orders=11, theta=0.0)
        solver1d = RCWA1D(cfg1d)
        orders1d = solver1d.solve(eps_2d[:, 0].clone(), torch.tensor([50e-9]), period)
        eff1d = solver1d.diffraction_efficiency(orders1d)
        r00_1d = eff1d.get(0, 0.0)

        cfg2d = RCWA2DConfig(n_orders_x=11, n_orders_y=1, theta=0.0)
        solver2d = RCWA2D(cfg2d)
        orders2d = solver2d.solve(eps_2d, torch.tensor([50e-9]), period, period)
        eff2d = solver2d.diffraction_efficiency(orders2d)
        r00_2d = eff2d.get((0, 0), 0.0)

        # A y-invariant structure at phi = 0 is exactly the 1D TE problem.
        assert r00_2d == pytest.approx(r00_1d, rel=1e-9)


class TestSolveWithConvergence:
    """Test the convergence driver."""

    def test_convergence_basic(self):
        """Convergence driver returns a result; 9 orders are not enough for
        this island, which the driver now reports with a warning.
        """
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
        with pytest.warns(UserWarning, match="did not converge"):
            eff, orders_used = solver.solve_with_convergence(
                eps,
                torch.tensor([50e-9]),
                128e-9,
                128e-9,
                target_rel=1e-2,
                max_orders=9,
            )
        assert orders_used == 9
        assert (0, 0) in eff
