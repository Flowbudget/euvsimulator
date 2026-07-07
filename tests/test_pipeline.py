"""Tests for the full simulation pipeline."""

from euv.pipeline import run_simulation, simulate_line_space


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

    def test_nils_positive(self):
        result = run_simulation(grid=64)
        assert result.nils_value >= 0
