"""Tests for the full simulation pipeline."""

from euvsimulator.pipeline import SimulationConfig, run_simulation, simulate_line_space


class TestPipeline:
    def test_run_simulation_defaults(self):
        result = run_simulation()
        assert result.aerial_image is not None
        assert result.resist_profile is not None
        assert result.aerial_image.shape == (256, 256)
        assert 0.0 <= result.absorber_reflectivity <= 1.0

    def test_simulate_line_space(self):
        result = simulate_line_space(period_nm=64, cd_nm=32, grid=128)
        assert result.aerial_image.shape == (128, 128)
        assert result.cd_nm >= 0

    def test_kwargs_override(self):
        result = run_simulation(grid=64, period_nm=128, line_width_nm=64)
        assert result.aerial_image.shape == (64, 64)

    def test_resist_profile_binary(self):
        result = run_simulation(grid=64, dose_mj_cm2=5.0)
        vals = result.resist_profile.unique()
        assert all(v.item() in (0.0, 1.0) for v in vals)

    def test_nils_realistic(self):
        """NILS with realistic SE blur (10nm) should be in literature range ~1.5-4.0."""
        result = run_simulation(grid=128, se_blur_nm=10.0, resist_model="full_chem")
        # For 64nm pitch, 32nm line, NA=0.33, sigma=0.8 with SE blur
        # NILS should be in realistic range (literature: ~2-3 for k1≈0.78)
        assert 1.5 <= result.nils_value <= 4.0, (
            f"NILS={result.nils_value:.3f} not in realistic range"
        )


class TestPolarizationAveraging:
    """P1 regression: unpolarized TE/TM must average after aerial reconstruction."""

    def test_rcwa_pipeline_runs(self):
        """use_rcwa=True runs without error and produces plausible results."""
        cfg = SimulationConfig(
            period_nm=48,
            line_width_nm=24,
            dose_mj_cm2=20,
            grid=64,
            use_rcwa=True,
        )
        result = run_simulation(cfg)
        assert result.aerial_image is not None
        assert result.aerial_image.shape == (64, 64)
        assert result.aerial_image.min() >= 0, "Negative intensities"
        assert result.cd_nm > 0, "CD should be positive"
        assert 0.0 <= result.absorber_reflectivity <= 1.0

    def test_thin_mask_path_unchanged(self):
        """The non-RCWA thin-mask path is unaffected by the averaging fix."""
        result = run_simulation(grid=64, dose_mj_cm2=20)
        assert not result.aerial_image.isnan().any()
        assert result.aerial_image.min() >= 0

    def test_intensity_avg_vs_field_avg_differ(self):
        """Prove analytically that intensity and field averaging give different
        results for TE orders ≠ TM orders on a real EUV mask."""
        import torch
        from euvsimulator.mask3d.geometry import (
            build_permittivity_profile,
            standard_euv_mask,
        )
        from euvsimulator.mask3d.rcwa_torch import RCWA1D, RCWAConfig
        from euvsimulator.aerial.abbe import aerial_from_orders
        from euvsimulator.pipeline import SimulationConfig

        cfg = SimulationConfig(
            period_nm=48, line_width_nm=24, dose_mj_cm2=20,
            grid=64, use_rcwa=True,
        )
        period_m = cfg.period_nm * 1e-9
        wavelength_m = cfg.wavelength_nm * 1e-9
        mask = standard_euv_mask(
            absorber=cfg.absorber_material,
            absorber_thickness_nm=cfg.absorber_height_nm,
            capping="Ru", capping_thickness_nm=2.5,
            n_bilayers=cfg.ml_n_bilayers,
            period_nm=cfg.period_nm,
            line_width_nm=cfg.line_width_nm,
            energy_eV=91.84,
        )
        eps_profile, thicknesses, eps_sub = build_permittivity_profile(mask, n_samples=1024)

        solver = RCWA1D(RCWAConfig(wavelength=wavelength_m, n_orders=cfg.n_rcwa_orders, theta=6.0, polarization="TE"))
        orders_te = solver.solve(eps_profile, thicknesses, period_m)
        solver_tm = RCWA1D(RCWAConfig(wavelength=wavelength_m, n_orders=cfg.n_rcwa_orders, theta=6.0, polarization="TM"))
        orders_tm = solver_tm.solve(eps_profile, thicknesses, period_m)

        order_indices = solver.m.tolist()
        order_t = torch.tensor(order_indices, dtype=torch.int64)

        # Intensity average (physically correct)
        aerial_te = aerial_from_orders(orders_te, order_t, period_m, cfg.na, wavelength_m, cfg.sigma, grid=cfg.grid)
        aerial_tm = aerial_from_orders(orders_tm, order_t, period_m, cfg.na, wavelength_m, cfg.sigma, grid=cfg.grid)
        aerial_intensity = (aerial_te + aerial_tm) / 2.0

        # Field average (the old bug)
        orders_field = (orders_te + orders_tm) / 2.0
        aerial_field = aerial_from_orders(orders_field, order_t, period_m, cfg.na, wavelength_m, cfg.sigma, grid=cfg.grid)

        max_diff = (aerial_field - aerial_intensity).abs().max().item()
        assert max_diff > 1e-14, (
            f"Intensity and field averages should differ, got max_diff={max_diff:.2e}. "
            "This suggests TE ≈ TM."
        )

        # Verify analytic bound: diff = -|r_TE - r_TM|²/4
        orders_diff = orders_te - orders_tm
        bound = (orders_diff.abs()**2 / 4).sum().item()
        assert max_diff <= bound, (
            f"Difference {max_diff:.2e} exceeds bound {bound:.2e}"
        )
