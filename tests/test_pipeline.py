"""Tests for the full simulation pipeline."""

import pytest
import torch

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
        """NILS at dose-to-size with 10 nm SE blur lies in the band 1.5-4.0.

        full_chem reports NILS at the edge the chemistry prints (2026-09-04),
        so the test runs at the dose that prints the 32 nm target: 1.314
        mJ/cm² gives CD 32.0 nm and NILS 2.27 (bisection, 2026-10-03; it was
        1.348 mJ/cm² and NILS 2.37 before the sampling and thin-mask phase
        fixes of 2026-10).  The
        former version used 1.1 mJ/cm² (CD 50.6 nm on the 64 nm pitch, a line
        filling 79 % of the pitch) and its docstring named 4.0 mJ/cm², where
        nothing prints.  The band 1.5-4.0 is a plausibility range, not a
        sourced value.
        """
        result = run_simulation(
            grid=128,
            se_blur_nm=10.0,
            resist_model="full_chem",
            dose_mj_cm2=1.314,
            peb_sigma_diff=7.0,
        )
        assert result.cd_nm == pytest.approx(33.0, abs=1.0)  # 32.0 before 2.3.0
        assert 1.5 <= result.nils_value <= 4.0, (
            f"NILS={result.nils_value:.3f} not in realistic range"
        )


class TestConfigThreshold:
    """P0-1 regression: CLI --threshold must control resist_threshold_norm."""

    def test_default_threshold_unchanged(self):
        """Default benchmark must remain unchanged (CD=[sub-pixel] ~26.70, NILS=4.5018).

        27.62 / 4.9685 before the aerial image was sampled with pitch P/G (2026-10),
        27.67 / 5.0330 before the thin mask used one phase reference plane (A5, 2026-10).
        """
        result = run_simulation()
        assert abs(result.cd_nm - 27.29) < 0.01, f"Default CD changed: {result.cd_nm}"
        assert abs(result.nils_value - 4.8309) < 0.001, f"Default NILS changed: {result.nils_value}"

    def test_threshold_0_3_changes_cd(self):
        """resist_threshold_norm=0.3 must produce different CD from default."""
        r_default = run_simulation()
        r_0_3 = run_simulation(SimulationConfig(resist_threshold_norm=0.3))
        assert abs(r_0_3.cd_nm - r_default.cd_nm) > 0.01, (
            "threshold=0.3 must change CD, got same as default"
        )

    def test_threshold_0_3_narrows_the_line(self):
        """resist_threshold_norm=0.3 (what CLI --threshold 0.3 sets) narrows the line.

        A lower threshold develops more of the dim region, so the resist line
        gets narrower: 20.85 nm against 26.70 nm (2026-10-03; 22.28 against
        27.67 nm before the A5 phase reference).  The comparison is against the
        default run itself: a fixed bound such as "< 27.0" stopped telling the
        two apart once the default CD fell below it.  (The former comment said
        "wider line"; the assertion was right, the comment was not.  The test
        does not call the CLI.)
        """
        r = run_simulation(SimulationConfig(resist_threshold_norm=0.3))
        r_default = run_simulation()
        assert r.cd_nm < r_default.cd_nm - 2.0, (
            f"threshold=0.3 should narrow the line by > 2 nm: {r.cd_nm} vs {r_default.cd_nm}"
        )

    def test_full_chem_threshold_unchanged(self):
        """full_chem ignores resist_threshold_norm entirely: CD comes from the
        chemistry and, since 2026-09-04, NILS is measured at the printed edge
        (a previous version of this test asserted the opposite -- that NILS
        followed the aerial_threshold model's reference level, which had no
        meaning for the chemistry chain).
        """
        kw = dict(resist_model="full_chem", dose_mj_cm2=1.1, peb_sigma_diff=7.0, grid=128)
        r_default = run_simulation(SimulationConfig(**kw))
        r_norm = run_simulation(SimulationConfig(resist_threshold_norm=0.3, **kw))
        assert r_default.cd_nm > 0
        assert r_norm.cd_nm == r_default.cd_nm
        assert r_norm.nils_value == r_default.nils_value


class TestConfigDose:
    """P0-2 regression: dose <= 0 must raise ValueError."""

    def test_dose_20_ok(self):
        """Standard dose works."""
        r = run_simulation(SimulationConfig(dose_mj_cm2=20.0))
        assert r.cd_nm > 0

    def test_dose_1_ok(self):
        """Low but positive dose runs; nothing develops, CD is the pitch.

        The aerial_threshold level scales as 20/dose, so at 1 mJ/cm² it lies
        above the image maximum: no threshold crossing and no developed pixel.
        The positive-tone line then fills the whole period (CD = 64 nm, as
        full_chem reports); CD = 0 is reserved for a fully cleared period.
        Until 2026-10 this case returned 0.
        """
        r = run_simulation(SimulationConfig(dose_mj_cm2=1.0))
        assert r.cd_nm == 64.0
        assert float(r.resist_profile.sum()) == 0.0  # nothing developed

    def test_dose_1e_12_ok(self):
        """Very small positive dose is allowed (physically marginal but > 0); CD = pitch."""
        r = run_simulation(SimulationConfig(dose_mj_cm2=1e-12))
        assert r.cd_nm == 64.0

    def test_dose_0_raises(self):
        """dose=0 must raise ValueError."""
        with pytest.raises(ValueError, match="dose_mj_cm2 must be > 0"):
            SimulationConfig(dose_mj_cm2=0.0)

    def test_dose_neg_0_raises(self):
        """dose=-0.0 must raise ValueError."""
        with pytest.raises(ValueError, match="dose_mj_cm2 must be > 0"):
            SimulationConfig(dose_mj_cm2=-0.0)

    def test_dose_negative_raises(self):
        """Negative dose must raise ValueError."""
        with pytest.raises(ValueError, match="dose_mj_cm2 must be > 0"):
            SimulationConfig(dose_mj_cm2=-1.0)
        with pytest.raises(ValueError, match="dose_mj_cm2 must be > 0"):
            SimulationConfig(dose_mj_cm2=-100.0)


class TestConfigIlluminationShape:
    """P1 regression: unknown illumination_shape must raise ValueError."""

    def test_conventional_works(self):
        """Default illumination shape works."""
        r = run_simulation(SimulationConfig(illumination_shape="conventional"))
        assert abs(r.cd_nm - 27.29) < 0.01

    def test_all_valid_shapes_work(self):
        """Every supported shape runs without error."""
        for shape in ("conventional", "annular", "dipole", "dipole_x", "dipole_y", "quasar"):
            r = run_simulation(SimulationConfig(illumination_shape=shape))
            assert r.cd_nm > 0, f"{shape}: CD should be positive"

    def test_case_insensitive(self):
        """Case variations of valid shapes are accepted (code calls .lower())."""
        for shape in ("Conventional", "DIPOLE", "Annular", "Quasar"):
            # Use _compute_tcc_matrix directly (fast path)
            import torch

            from euvsimulator.aerial.abbe import _compute_tcc_matrix

            orders = torch.tensor([-1, 0, 1], dtype=torch.int64)
            kw = dict(sigma=0.8, na=0.33, wavelength_m=13.5e-9, period_m=64e-9, grid=64)
            tcc = _compute_tcc_matrix(orders, **kw, illumination_shape=shape)
            ref = _compute_tcc_matrix(orders, **kw, illumination_shape=shape.lower())
            assert torch.equal(tcc, ref), shape

    def test_unknown_shape_raises(self):
        """Unknown illumination_shape must raise ValueError with supported list."""
        with pytest.raises(ValueError, match="Unknown illumination_shape"):
            run_simulation(SimulationConfig(illumination_shape="INVALID"))

    def test_multiple_unknown_shapes_raise(self):
        """Various unknown shapes all raise ValueError."""
        for shape in ("INVALID", "custom", "hexapole", "quadrupole", "unknown"):
            with pytest.raises(ValueError, match="Unknown illumination_shape"):
                run_simulation(SimulationConfig(illumination_shape=shape))

    def test_error_message_lists_supported(self):
        """Error message lists supported shapes for user guidance."""
        with pytest.raises(ValueError) as exc:
            run_simulation(SimulationConfig(illumination_shape="INVALID"))
        msg = str(exc.value)
        assert "supported" in msg.lower() or "Supported" in msg
        assert "conventional" in msg


class TestConfigOrderCutoff:
    """P2 regression: sigma>0 must extend order range beyond on-axis max_order."""

    def test_sigma0_period40_unchanged(self):
        """sigma=0 must use on-axis cutoff (no source shift)."""
        r = run_simulation(SimulationConfig(period_nm=40, line_width_nm=20, sigma=0.0, grid=256))
        assert r.cd_nm == 0.0, f"sigma=0 period=40 should give CD=0, got {r.cd_nm}"

    def test_sigma08_period40_now_has_cd(self):
        """sigma=0.8, period=40 must produce CD>0 (source shift enables order 1)."""
        r = run_simulation(SimulationConfig(period_nm=40, line_width_nm=20, sigma=0.8, grid=256))
        assert r.cd_nm > 0.0, f"sigma=0.8 period=40 should have CD>0, got {r.cd_nm}"

    def test_sigma08_period32_cd_positive(self):
        """Very small period benefits from source shift at sigma>0."""
        r = run_simulation(SimulationConfig(period_nm=32, line_width_nm=16, sigma=0.8, grid=256))
        assert r.cd_nm > 0.0, f"sigma=0.8 period=32 should have CD>0, got {r.cd_nm}"

    def test_benchmark_unchanged(self):
        """Standard benchmark must remain unchanged after order cutoff fix."""
        r = run_simulation()
        assert abs(r.cd_nm - 27.29) < 0.01, f"Default CD changed: {r.cd_nm}"
        assert abs(r.nils_value - 4.8309) < 0.001, f"Default NILS changed: {r.nils_value}"

    def test_sigma1_period64_works(self):
        """sigma=1.0 at period=64 runs and produces CD>0."""
        r = run_simulation(SimulationConfig(sigma=1.0))
        assert r.cd_nm > 0, f"sigma=1.0 period=64 should produce CD>0, got {r.cd_nm}"

    def test_sigma_continuity(self):
        """CD vs sigma is continuous at period=40 (was a discrete 0 -> 14 nm jump).

        Measured 12.39 / 12.34 / 12.04 nm at sigma 0.3 / 0.5 / 0.8.
        """
        cds = [
            run_simulation(
                SimulationConfig(period_nm=40, line_width_nm=20, sigma=s, grid=256)
            ).cd_nm
            for s in (0.3, 0.5, 0.8)
        ]
        assert all(cd > 10.0 for cd in cds), cds
        assert all(abs(b - a) < 1.0 for a, b in zip(cds, cds[1:])), cds


class TestConfigSubPixelCD:
    """P2 fix: CD uses sub-pixel threshold crossings (not integer pixel runs)."""

    def test_benchmark_subpixel_cd(self):
        """Standard benchmark CD = ~26.70 nm (sub-pixel, not an integer pixel count)."""
        r = run_simulation()
        assert abs(r.cd_nm - 27.29) < 0.01, f"CD = {r.cd_nm:.4f}, expected ~27.29"
        assert abs(r.nils_value - 4.8309) < 0.001, f"NILS changed: {r.nils_value}"

    def test_cd_not_quantized_to_pixels(self):
        """CD at grid=256 must NOT be an exact integer multiple of dx."""
        r = run_simulation()
        dx_nm = 64.0 / 256
        cd_px = r.cd_nm / dx_nm
        # Sub-pixel CD should not be an exact integer pixel count
        assert abs(cd_px - round(cd_px)) > 0.001, (
            f"CD={r.cd_nm:.4f} nm = {cd_px:.2f} px — appears quantized"
        )

    def test_grid_convergence_monotonic(self):
        """CD rises monotonically with the grid and is converged at grid 256.

        Measured 26.7034 / 26.7051 / 26.7053 / 26.7054 nm at 256-2048 (steps
        0.0017 / 0.0002 / 0.0001 nm; 2026-10-03, with the A5 phase reference;
        27.6683 / 27.6697 / 27.6701 / 27.6702 before it).  Before the aerial image was sampled with
        pitch P/G (2026-10) the values were 27.6229 / 27.6472 / 27.6587 /
        27.6645 nm: a first-order (G-1)/G bias of 0.04 nm at grid 256.
        """
        cd_vals = [run_simulation(SimulationConfig(grid=g)).cd_nm for g in (256, 512, 1024, 2048)]
        steps = [b - a for a, b in zip(cd_vals, cd_vals[1:])]
        assert all(st > 0 for st in steps), f"CD not monotonic: {cd_vals}"
        assert cd_vals[-1] - cd_vals[0] < 0.005, f"CD not converged at grid 256: {cd_vals}"

    def test_subpixel_cd_small_period(self):
        """period=40, sigma=0.8: CD must be >0 (P2 order-cutoff fix still active)."""
        r = run_simulation(SimulationConfig(period_nm=40, line_width_nm=20, sigma=0.8, grid=256))
        assert r.cd_nm > 10.0, f"CD should be >10 nm, got {r.cd_nm}"

    def test_subpixel_cd_asymmetric(self):
        """period=64, duty=0.3 produces consistent sub-pixel CD ~18.33 nm (19.06 before A5)."""
        r = run_simulation(SimulationConfig(period_nm=64, line_width_nm=19.2, grid=256))
        # CD should be ~18.33 nm (sub-pixel) and not quantized
        assert 17.8 < r.cd_nm < 18.8, f"CD out of range: {r.cd_nm}"

    def test_nils_unchanged_by_cd_fix(self):
        """NILS must be unchanged — uses its own sub-pixel logic independently."""
        r = run_simulation()
        assert abs(r.nils_value - 4.8309) < 0.001


class TestOrderBoundaryInvariant:
    """P2 invariant: no Fourier order beyond ceil((1+σ)·NA·Λ/λ) has non-zero TCC."""

    @staticmethod
    def _check_shape_order_boundary(shape, sigma, period_nm, eps=1e-6):
        import math

        from euvsimulator.aerial.abbe import _compute_tcc_matrix

        lam = 13.5e-9
        NA = 0.33
        period_m = period_nm * 1e-9
        max_order = int(math.floor(NA * period_m / lam))
        if sigma > 0:
            max_order = int(math.ceil((1.0 + sigma) * NA * period_m / lam))
        probe = max_order + 10
        orders = torch.tensor(list(range(-probe, probe + 1)), dtype=torch.int64)
        tcc = _compute_tcc_matrix(
            orders,
            sigma=sigma,
            na=NA,
            wavelength_m=lam,
            period_m=period_m,
            grid=256,
            illumination_shape=shape,
        )
        diag = tcc.diag().real
        violations = [
            (int(m), float(diag[idx]))
            for idx, m in enumerate(orders)
            if abs(int(m)) > max_order and float(diag[idx]) > eps
        ]
        return max_order, violations

    def test_order_boundary_conventional(self):
        mo, v = self._check_shape_order_boundary("conventional", 0.8, 40)
        assert len(v) == 0, f"Orders > {mo} have non-zero TCC: {v}"

    def test_order_boundary_annular(self):
        mo, v = self._check_shape_order_boundary("annular", 0.8, 40)
        assert len(v) == 0, f"Orders > {mo} have non-zero TCC: {v}"

    def test_order_boundary_dipole_x(self):
        mo, v = self._check_shape_order_boundary("dipole_x", 0.8, 40)
        assert len(v) == 0, f"Orders > {mo} have non-zero TCC: {v}"

    def test_order_boundary_dipole_y(self):
        mo, v = self._check_shape_order_boundary("dipole_y", 0.8, 40)
        assert len(v) == 0, f"Orders > {mo} have non-zero TCC: {v}"

    def test_order_boundary_quasar(self):
        mo, v = self._check_shape_order_boundary("quasar", 0.8, 40)
        assert len(v) == 0, f"Orders > {mo} have non-zero TCC: {v}"

    def test_order_boundary_sigma_high(self):
        for s in ["conventional", "annular", "dipole_x", "dipole_y", "quasar"]:
            mo, v = self._check_shape_order_boundary(s, 1.0, 32)
            assert len(v) == 0, f"{s}: Orders > {mo} have non-zero TCC: {v}"

    def test_order_boundary_large_period(self):
        for s in ["conventional", "annular", "dipole_x", "dipole_y", "quasar"]:
            mo, v = self._check_shape_order_boundary(s, 0.8, 128)
            assert len(v) == 0, f"{s}: Orders > {mo} have non-zero TCC: {v}"


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

    def test_pipeline_reconstructs_te_and_tm_separately(self, monkeypatch):
        """The pipeline itself images TE and TM orders separately and averages
        the intensities (the old bug averaged the fields first).

        Recorded 2026-09-25: two calls of aerial_from_orders with 21 orders
        each, max |r_TE - r_TM| = 0.72 against max |r_TE| = 0.37.
        """
        import euvsimulator.pipeline as pipeline_module

        calls = []
        original = pipeline_module.aerial_from_orders

        def recording(orders, *args, **kwargs):
            calls.append(orders.detach().clone())
            return original(orders, *args, **kwargs)

        monkeypatch.setattr(pipeline_module, "aerial_from_orders", recording)
        run_simulation(
            SimulationConfig(period_nm=48, line_width_nm=24, dose_mj_cm2=20, grid=64, use_rcwa=True)
        )
        assert len(calls) == 2
        te, tm = calls
        assert (te - tm).abs().max().item() > 0.1 * te.abs().max().item()

    def test_intensity_avg_vs_field_avg_differ(self):
        """Prove analytically that intensity and field averaging give different
        results for TE orders ≠ TM orders on a real EUV mask.
        """
        import torch

        from euvsimulator.aerial.abbe import aerial_from_orders
        from euvsimulator.mask3d.geometry import (
            build_permittivity_profile,
            standard_euv_mask,
        )
        from euvsimulator.mask3d.rcwa_torch import RCWA1D, RCWAConfig
        from euvsimulator.pipeline import SimulationConfig

        cfg = SimulationConfig(
            period_nm=48,
            line_width_nm=24,
            dose_mj_cm2=20,
            grid=64,
            use_rcwa=True,
        )
        period_m = cfg.period_nm * 1e-9
        wavelength_m = cfg.wavelength_nm * 1e-9
        mask = standard_euv_mask(
            absorber=cfg.absorber_material,
            absorber_thickness_nm=cfg.absorber_height_nm,
            capping="Ru",
            capping_thickness_nm=2.5,
            n_bilayers=cfg.ml_n_bilayers,
            period_nm=cfg.period_nm,
            line_width_nm=cfg.line_width_nm,
            energy_eV=91.84,
        )
        eps_profile, thicknesses, eps_sub = build_permittivity_profile(mask, n_samples=1024)

        solver = RCWA1D(
            RCWAConfig(
                wavelength=wavelength_m, n_orders=cfg.n_rcwa_orders, theta=6.0, polarization="TE"
            )
        )
        orders_te = solver.solve(eps_profile, thicknesses, period_m)
        solver_tm = RCWA1D(
            RCWAConfig(
                wavelength=wavelength_m, n_orders=cfg.n_rcwa_orders, theta=6.0, polarization="TM"
            )
        )
        orders_tm = solver_tm.solve(eps_profile, thicknesses, period_m)

        order_indices = solver.m.tolist()
        order_t = torch.tensor(order_indices, dtype=torch.int64)

        # Intensity average (physically correct)
        aerial_te = aerial_from_orders(
            orders_te, order_t, period_m, cfg.na, wavelength_m, cfg.sigma, grid=cfg.grid
        )
        aerial_tm = aerial_from_orders(
            orders_tm, order_t, period_m, cfg.na, wavelength_m, cfg.sigma, grid=cfg.grid
        )
        aerial_intensity = (aerial_te + aerial_tm) / 2.0

        # Field average (the old bug)
        orders_field = (orders_te + orders_tm) / 2.0
        aerial_field = aerial_from_orders(
            orders_field, order_t, period_m, cfg.na, wavelength_m, cfg.sigma, grid=cfg.grid
        )

        max_diff = (aerial_field - aerial_intensity).abs().max().item()
        assert max_diff > 1e-14, (
            f"Intensity and field averages should differ, got max_diff={max_diff:.2e}. "
            "This suggests TE ≈ TM."
        )

        # Analytic bound. Per order, |(a+b)/2|² − (|a|²+|b|²)/2 = −|a−b|²/4.
        # Through the Hopkins double sum the pointwise difference is
        #   −(1/4) Σ_ij Δ_i Δ_j* TCC_ij e^{i2π(m_i−m_j)x/Λ},  Δ = r_TE − r_TM,
        # whose magnitude is bounded (|TCC_ij| ≤ 1) by (Σ_i |Δ_i|)²/4 -- NOT by
        # Σ_i |Δ_i|²/4, which a previous version of this test used; that
        # tighter "bound" only held while TE ≈ TM and was violated by 8 % once
        # the TM solver was corrected (2026-09-04).
        orders_diff = orders_te - orders_tm
        bound = (orders_diff.abs().sum() ** 2 / 4).item()
        assert max_diff <= bound, f"Difference {max_diff:.2e} exceeds bound {bound:.2e}"


def test_order_11_reaches_the_pupil_at_260_nm_but_not_at_230_nm():
    """Backs the pupil criterion |m| <= floor((1 + sigma)·NA·P/λ) of the RCWA
    order count: at NA 0.33, sigma 0.8 adding |m| = 11 changes the thin-mask
    image at 260 nm wafer pitch and leaves it unchanged at 230 nm.
    """

    def image(period_nm, n):
        cfg = SimulationConfig(
            period_nm=period_nm,
            line_width_nm=period_nm / 2,
            grid=64,
            device="cpu",
            n_rcwa_orders=n,
        )
        return run_simulation(cfg).aerial_image

    a10, a11 = image(230.0, 10), image(230.0, 11)
    assert float((a10 - a11).abs().max() / a11.abs().max()) < 1e-12
    a10, a11 = image(260.0, 10), image(260.0, 11)
    assert float((a10 - a11).abs().max() / a11.abs().max()) > 1e-6


def test_rcwa_retains_every_order_the_pupil_accepts(monkeypatch):
    """n_rcwa_orders is the largest |m| on the thin-mask path but the total
    order count on the RCWA path. At 260 nm wafer pitch (NA 0.33, sigma 0.8)
    the pupil accepts |m| <= 11; the default 21 RCWA orders (|m| <= 10)
    silently dropped that order while the thin-mask image kept it. The RCWA
    now retains -11..11 and warns; at 64 nm nothing changes (2026-10-02).
    """
    import warnings

    from euvsimulator.mask3d.rcwa_torch import RCWA1D

    seen = []
    real_solve = RCWA1D.solve

    def spy(self, *args, **kwargs):
        seen.append(self.m.tolist())
        return real_solve(self, *args, **kwargs)

    monkeypatch.setattr(RCWA1D, "solve", spy)
    with pytest.warns(UserWarning, match="n_rcwa_orders=21"):
        run_simulation(
            SimulationConfig(
                period_nm=260.0,
                line_width_nm=130.0,
                grid=64,
                device="cpu",
                use_rcwa=True,
                n_rcwa_orders=21,
            )
        )
    assert len(seen) == 2  # TE and TM
    assert all(min(m) == -11 and max(m) == 11 for m in seen)

    seen.clear()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run_simulation(
            SimulationConfig(
                period_nm=64.0,
                line_width_nm=32.0,
                grid=64,
                device="cpu",
                use_rcwa=True,
                n_rcwa_orders=21,
            )
        )
    assert not any("n_rcwa_orders" in str(w.message) for w in caught)
    assert len(seen) == 2
    assert all(min(m) == -10 and max(m) == 10 for m in seen)
