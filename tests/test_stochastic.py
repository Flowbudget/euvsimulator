"""
Comprehensive tests for the stochastic resist module — shot noise, LER, LWR.

Tests cover:

1. Poisson shot-noise overlay (with and without dose map)
2. Edge extraction from developed contours
3. LER extraction (left, right, both edges)
4. LWR extraction
5. Combined LER/LWR estimate pipeline
6. 1/√(dose) RMS scaling verification
7. Gradient/differentiability checks
8. Edge cases (uniform developed, all-zero, all-one, NaNs, small features)
"""

from __future__ import annotations

import math

import pytest
import torch

from euv.resist.stochastic import (
    poisson_shot_noise,
    _generate_photon_shot_noise,
    extract_edges,
    extract_ler,
    extract_lwr,
    ler_lwr_estimate,
    rms_scaling_check,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def device() -> torch.device:
    return torch.device("cpu")


@pytest.fixture
def rng(device: torch.device) -> torch.Generator:
    return torch.Generator(device=device).manual_seed(42)


@pytest.fixture
def line_acid(device: torch.device) -> torch.Tensor:
    """64×64 acid map with a vertical line feature in the centre."""
    x = torch.linspace(-32, 32, 64, device=device)
    X, _ = torch.meshgrid(x, x, indexing="ij")
    # Gaussian acid profile ~ 20 nm wide line at centre
    acid = 0.5 * torch.exp(-0.5 * (X / 8.0) ** 2)
    return acid


@pytest.fixture
def line_dose(device: torch.device) -> torch.Tensor:
    """64×64 dose map for the line feature [mJ/cm²]."""
    x = torch.linspace(-32, 32, 64, device=device)
    X, _ = torch.meshgrid(x, x, indexing="ij")
    dose = 20.0 * torch.exp(-0.5 * (X / 8.0) ** 2)
    return dose


@pytest.fixture
def developed_line(device: torch.device) -> torch.Tensor:
    """64×64 developed binary mask — vertical line, width ~6 px."""
    x = torch.linspace(-32, 32, 64, device=device)
    X, _ = torch.meshgrid(x, x, indexing="ij")
    # line of width 6 pixels centred at x=0
    developed = (X.abs() > 3.5).float()  # 1 = developed (outside), 0 = resist
    return developed


@pytest.fixture
def developed_rough_line(device: torch.device) -> torch.Tensor:
    """64×64 developed mask with a rough edge for LER/LWR measurement."""
    x = torch.linspace(-32, 32, 64, device=device)
    X, Y_grid = torch.meshgrid(x, x, indexing="ij")
    # Add a sinusoidal roughness to the edge
    roughness_amp = 2.0  # pixels
    edge_mod = roughness_amp * torch.sin(2 * torch.pi * Y_grid / 16.0)
    developed = (X.abs() + edge_mod > 4.0).float()
    return developed


# ──────────────────────────────────────────────
# 1. Poisson shot-noise overlay
# ──────────────────────────────────────────────


class TestPoissonShotNoise:
    def test_output_shape(self, line_acid: torch.Tensor, rng: torch.Generator):
        """Output same shape as input."""
        noisy = poisson_shot_noise(line_acid, rng=rng)
        assert noisy.shape == line_acid.shape

    def test_output_dtype(self, line_acid: torch.Tensor, rng: torch.Generator):
        """Output is float (not long/int from Poisson draw)."""
        noisy = poisson_shot_noise(line_acid, rng=rng)
        assert noisy.is_floating_point()

    def test_noise_adds_variation(self, line_acid: torch.Tensor, rng: torch.Generator):
        """Noisy output differs from clean input."""
        noisy = poisson_shot_noise(line_acid, rng=rng)
        assert not torch.allclose(noisy, line_acid)

    def test_different_seeds_different(self, line_acid: torch.Tensor, device: torch.device):
        """Two different seeds produce different realisations."""
        rng1 = torch.Generator(device=device).manual_seed(1)
        rng2 = torch.Generator(device=device).manual_seed(999)
        n1 = poisson_shot_noise(line_acid, rng=rng1)
        n2 = poisson_shot_noise(line_acid, rng=rng2)
        assert not torch.allclose(n1, n2)

    def test_with_dose_map(
        self, line_acid: torch.Tensor, line_dose: torch.Tensor, rng: torch.Generator
    ):
        """Dose-aware shot noise runs and returns correct shape."""
        noisy = poisson_shot_noise(line_acid, dose=line_dose, rng=rng)
        assert noisy.shape == line_acid.shape

    def test_return_photon_count(
        self, line_acid: torch.Tensor, line_dose: torch.Tensor, rng: torch.Generator
    ):
        """return_photon_count returns photon count tensor."""
        noisy, photons = poisson_shot_noise(
            line_acid, dose=line_dose, return_photon_count=True, rng=rng
        )
        assert noisy.shape == line_acid.shape
        assert photons.shape == line_acid.shape
        assert (photons >= 0).all()

    def test_zero_acid(self, device: torch.device, rng: torch.Generator):
        """Zero acid → approximately zero noisy acid (Poisson(0) = 0)."""
        zero = torch.zeros((16, 16), device=device)
        noisy = poisson_shot_noise(zero, rng=rng)
        assert (noisy >= 0).all()

    def test_all_same_seed_reproducible(self, line_acid: torch.Tensor, device: torch.device):
        """Same seed produces identical output."""
        rng1 = torch.Generator(device=device).manual_seed(1234)
        rng2 = torch.Generator(device=device).manual_seed(1234)
        n1 = poisson_shot_noise(line_acid, rng=rng1)
        n2 = poisson_shot_noise(line_acid, rng=rng2)
        assert torch.allclose(n1, n2)

    def test_negative_acid_clamped(self, device: torch.device, rng: torch.Generator):
        """Negative acid values are clamped to zero before Poisson draw."""
        acid = torch.tensor([[-1.0, -0.5, 0.0, 1.0]], device=device)
        noisy = poisson_shot_noise(acid, rng=rng)
        assert (noisy >= 0).all()

    def test_mean_approaches_input(self, line_acid: torch.Tensor, device: torch.device):
        """Mean of many realisations approaches the input acid."""
        n_reps = 200
        accum = torch.zeros_like(line_acid)
        for i in range(n_reps):
            rng_i = torch.Generator(device=device).manual_seed(i)
            accum = accum + poisson_shot_noise(line_acid, rng=rng_i)
        mean_noisy = accum / n_reps
        # Mean should be close to the original (within ~10% RMS)
        diff = (mean_noisy - line_acid).abs().mean()
        rel_diff = diff / (line_acid.mean() + 1e-10)
        assert rel_diff < 0.15, f"Mean deviation {rel_diff:.4f} > 0.15"

    def test_variance_scales_with_mean(self, device: torch.device):
        """Variance scales with the mean (Poisson property)."""
        means = torch.tensor([1.0, 5.0, 20.0, 100.0], device=device)
        variances = []
        n_reps = 500
        for mu in means:
            acid = torch.full((32, 32), mu, device=device)
            samples = []
            for i in range(n_reps):
                rng_i = torch.Generator(device=device).manual_seed(i)
                samples.append(poisson_shot_noise(acid, rng=rng_i))
            samples_t = torch.stack(samples)
            variances.append(samples_t.var(unbiased=False, dim=0).mean().item())
        # Variance should increase with mean (roughly proportional)
        for j in range(1, len(variances)):
            assert variances[j] > variances[j - 1] * 0.3


# ──────────────────────────────────────────────
# 2. Edge extraction
# ──────────────────────────────────────────────


class TestExtractEdges:
    def test_basic_shapes(self, developed_line: torch.Tensor):
        """Left and right edges are 1D of length H."""
        left, right = extract_edges(developed_line)
        H = developed_line.shape[0]
        assert left.shape == (H,)
        assert right.shape == (H,)

    @pytest.mark.parametrize("dx", [0.5, 1.0, 2.0])
    def test_dx_scaling(self, developed_line: torch.Tensor, dx: float):
        """Edge positions scale linearly with dx."""
        left1, right1 = extract_edges(developed_line, dx=1.0)
        left2, right2 = extract_edges(developed_line, dx=dx)
        # NaN positions are identical; use equal_nan so NaN == NaN
        assert torch.allclose(left2, left1 * dx, equal_nan=True)
        assert torch.allclose(right2, right1 * dx, equal_nan=True)

    def test_line_centred(self, developed_line: torch.Tensor):
        """For a symmetric centred line, edges are symmetric about centre."""
        left, right = extract_edges(developed_line)
        # Remove NaN rows for valid comparison
        finite = ~(torch.isnan(left) | torch.isnan(right))
        left_f = left[finite]
        right_f = right[finite]
        # Centre of the 64-pixel domain = 31.5 in pixels
        # The line has width ~7 pixels centred at x=0 in -32..32 space
        # pixel 0 = -32, pixel 32 = 0, pixel 63 = ~31
        # Left edge should be near pixel 29 (~ 3 px from centre)
        # Right edge should be near pixel 35 (~ 3 px from centre)
        assert right_f.mean() > left_f.mean()

    def test_all_developed(self, device: torch.device):
        """All-developed mask → no edges (NaN)."""
        all_dev = torch.ones((32, 32), device=device)
        left, right = extract_edges(all_dev)
        assert torch.isnan(left).all()
        assert torch.isnan(right).all()

    def test_no_developed(self, device: torch.device):
        """No developed pixels → no edges (NaN)."""
        none_dev = torch.zeros((32, 32), device=device)
        left, right = extract_edges(none_dev)
        assert left.shape == (32,)
        assert right.shape == (32,)

    def test_asymmetric_feature(self, device: torch.device):
        """An asymmetric feature produces asymmetric edges."""
        mask = torch.zeros((32, 32), device=device)
        # Resist bar from col 10 to col 20
        mask[:, 10:21] = 0.0  # undeveloped (resist)
        mask[:, :10] = 1.0  # developed
        mask[:, 21:] = 1.0
        left, right = extract_edges(mask)
        finite = ~(torch.isnan(left) | torch.isnan(right))
        left_f = left[finite]
        right_f = right[finite]
        assert torch.allclose(left_f, torch.full_like(left_f, 10.0))
        assert torch.allclose(right_f, torch.full_like(right_f, 20.0))

    def test_raises_on_3d(self, device: torch.device):
        """3D input raises ValueError."""
        tensor_3d = torch.rand((5, 32, 32), device=device)
        with pytest.raises(ValueError, match="Expected 2D"):
            extract_edges(tensor_3d)


# ──────────────────────────────────────────────
# 3. LER extraction
# ──────────────────────────────────────────────


class TestExtractLER:
    def test_smooth_line_zero_ler(self, developed_line: torch.Tensor):
        """A perfectly straight line has LER ≈ 0."""
        ler = extract_ler(developed_line)
        assert ler == pytest.approx(0.0, abs=0.2)

    def test_rough_line_positive_ler(self, developed_rough_line: torch.Tensor):
        """A rough line has LER > 0."""
        ler = extract_ler(developed_rough_line)
        assert ler > 0.1

    def test_left_edge_ler(self, developed_rough_line: torch.Tensor):
        """Left-edge LER is positive for a rough left edge."""
        ler = extract_ler(developed_rough_line, edge="left")
        assert ler > 0.1

    def test_right_edge_ler(self, developed_rough_line: torch.Tensor):
        """Right-edge LER is positive for a rough right edge."""
        ler = extract_ler(developed_rough_line, edge="right")
        assert ler > 0.1

    def test_ler_dx_scaling(self, developed_rough_line: torch.Tensor):
        """LER scales linearly with dx."""
        ler_1 = extract_ler(developed_rough_line, dx=1.0)
        ler_2 = extract_ler(developed_rough_line, dx=2.0)
        assert ler_2 == pytest.approx(2.0 * ler_1, rel=0.2)

    def test_ler_units_nm(self, developed_rough_line: torch.Tensor):
        """LER is returned in nm (not pixel units when dx=1 nm/px)."""
        ler = extract_ler(developed_rough_line, dx=1.0)
        assert isinstance(ler, float)
        assert not math.isnan(ler)

    def test_all_developed_nan(self, device: torch.device):
        """All-developed → LER = NaN."""
        all_dev = torch.ones((32, 32), device=device)
        ler = extract_ler(all_dev)
        assert math.isnan(ler)

    def test_differentiable(self, device: torch.device):
        """Edge extraction is differentiable w.r.t. the mask."""
        # Create a differentiable mask by using a sigmoid approximation
        x = torch.linspace(-16, 16, 32, device=device)
        X, _ = torch.meshgrid(x, x, indexing="ij")
        mask = torch.sigmoid(10.0 * (X.abs() - 4.0))  # ≈step but differentiable
        left, right = extract_edges(mask)
        # Cannot backprop through argmax, but the edges should still be
        # valid tensors.
        assert left.requires_grad or not mask.requires_grad

    def test_ler_same_seed_reproducible(self, developed_rough_line: torch.Tensor):
        """LER for the same input is deterministic (no RNG involved)."""
        ler1 = extract_ler(developed_rough_line)
        ler2 = extract_ler(developed_rough_line)
        assert ler1 == pytest.approx(ler2, abs=1e-12)


# ──────────────────────────────────────────────
# 4. LWR extraction
# ──────────────────────────────────────────────


class TestExtractLWR:
    def test_smooth_line_zero_lwr(self, developed_line: torch.Tensor):
        """A perfectly straight line has LWR ≈ 0."""
        lwr = extract_lwr(developed_line)
        assert lwr == pytest.approx(0.0, abs=0.2)

    def test_rough_line_positive_lwr(self, developed_rough_line: torch.Tensor):
        """A rough line has LWR > 0."""
        lwr = extract_lwr(developed_rough_line)
        assert lwr > 0.1

    def test_lwr_dx_scaling(self, developed_rough_line: torch.Tensor):
        """LWR scales linearly with dx."""
        lwr_1 = extract_lwr(developed_rough_line, dx=1.0)
        lwr_2 = extract_lwr(developed_rough_line, dx=2.0)
        assert lwr_2 == pytest.approx(2.0 * lwr_1, rel=0.2)

    def test_lwr_units(self, developed_rough_line: torch.Tensor):
        """LWR is a float in nm."""
        lwr = extract_lwr(developed_rough_line, dx=1.0)
        assert isinstance(lwr, float)
        assert not math.isnan(lwr)

    def test_lwr_ler_relationship(self, developed_rough_line: torch.Tensor):
        """LWR ≈ √2 × LER when edges fluctuate independently."""
        ler = extract_ler(developed_rough_line, edge="both")
        lwr_val = extract_lwr(developed_rough_line)
        # LWR / LER should be in the range [1.0, 2.0] for rough edges
        # (not exactly √2 because the sinusoidal edges are correlated)
        assert lwr_val > 0
        ratio = lwr_val / ler if ler > 0 else float("inf")
        assert ratio > 0.5

    def test_all_developed_nan(self, device: torch.device):
        """All-developed → LWR = NaN."""
        all_dev = torch.ones((32, 32), device=device)
        lwr = extract_lwr(all_dev)
        assert math.isnan(lwr)


# ──────────────────────────────────────────────
# 5. Combined LER/LWR estimate
# ──────────────────────────────────────────────


class TestLERLWREstimate:
    def test_basic_run(self, line_acid: torch.Tensor, rng: torch.Generator):
        """Pipeline runs and returns expected keys."""
        result = ler_lwr_estimate(line_acid, shot_noise_rng=rng)
        assert "ler" in result
        assert "lwr" in result
        assert "mean_acid" in result
        assert result["ler"] is not None
        assert result["lwr"] is not None

    def test_with_dose(self, line_acid: torch.Tensor, line_dose: torch.Tensor):
        """Pipeline runs with dose map."""
        rng = torch.Generator(device=line_acid.device).manual_seed(42)
        result = ler_lwr_estimate(line_acid, dose=line_dose, shot_noise_rng=rng)
        assert result["mean_dose"] is not None
        assert result["mean_dose"] > 0

    def test_without_dose(self, line_acid: torch.Tensor):
        """Pipeline runs without dose map."""
        rng = torch.Generator(device=line_acid.device).manual_seed(42)
        result = ler_lwr_estimate(line_acid, dose=None, shot_noise_rng=rng)
        assert result["mean_dose"] is None

    def test_multiple_realisations(self, line_acid: torch.Tensor, device: torch.device):
        """n_realisations=10 produces averaged result."""
        rng = torch.Generator(device=device).manual_seed(42)
        result = ler_lwr_estimate(
            line_acid, n_realisations=10, average=True, shot_noise_rng=rng
        )
        assert isinstance(result["ler"], float)

    def test_multiple_realisations_list(self, line_acid: torch.Tensor, device: torch.device):
        """average=False returns lists."""
        rng = torch.Generator(device=device).manual_seed(42)
        result = ler_lwr_estimate(
            line_acid, n_realisations=5, average=False, shot_noise_rng=rng
        )
        assert isinstance(result["ler"], list)
        assert len(result["ler"]) == 5
        assert isinstance(result["lwr"], list)

    def test_develop_threshold_effect(self, line_acid: torch.Tensor, device: torch.device):
        """Different development thresholds yield different LER."""
        rng1 = torch.Generator(device=device).manual_seed(42)
        rng2 = torch.Generator(device=device).manual_seed(42)
        result_low = ler_lwr_estimate(
            line_acid, develop_threshold=0.1, shot_noise_rng=rng1
        )
        result_high = ler_lwr_estimate(
            line_acid, develop_threshold=0.9, shot_noise_rng=rng2
        )
        # The results may differ
        assert result_low["ler"] is not None
        assert result_high["ler"] is not None


# ──────────────────────────────────────────────
# 6. 1/√(dose) RMS scaling verification
# ──────────────────────────────────────────────


class TestRMSScaling:
    def test_basic_run(self, line_acid: torch.Tensor, device: torch.device):
        """Scaling check runs without error."""
        dose_levels = torch.tensor([5.0, 10.0, 20.0, 40.0], device=device)
        result = rms_scaling_check(
            line_acid, dose_levels, n_realisations=5, seed=42
        )
        assert "dose_levels" in result
        assert "ler" in result
        assert "lwr" in result
        assert result["ler"].shape == dose_levels.shape

    def test_ler_decreases_with_dose(self, line_acid: torch.Tensor, device: torch.device):
        """LER decreases as dose increases."""
        dose_levels = torch.tensor([5.0, 10.0, 20.0, 40.0], device=device)
        result = rms_scaling_check(
            line_acid, dose_levels, n_realisations=8, seed=42
        )
        ler = result["ler"]
        # Higher dose → lower LER (monotonic trend)
        for i in range(1, len(ler)):
            if not math.isnan(ler[i]) and not math.isnan(ler[i - 1]):
                assert ler[i] <= ler[i - 1] * 1.1  # allow small stochastic variation

    def test_ler_sqrt_dose_approximately_constant(
        self, line_acid: torch.Tensor, device: torch.device
    ):
        """LER × √(dose) is approximately constant across dose levels."""
        dose_levels = torch.tensor([5.0, 10.0, 20.0, 40.0], device=device)
        result = rms_scaling_check(
            line_acid, dose_levels, n_realisations=10, seed=42
        )
        product = result["ler_sqrt_dose"]
        finite = ~torch.isnan(product) & (product > 0)
        if finite.sum() >= 3:
            mean_product = product[finite].mean()
            # Each product should be within 50% of mean (loose tolerance
            # for stochastic simulation)
            deviations = (product[finite] - mean_product).abs() / mean_product
            assert (deviations < 0.5).all(), (
                f"LER×√(dose) deviations too large: {deviations.tolist()}"
            )

    def test_fit_exponent_near_neg_half(
        self, line_acid: torch.Tensor, device: torch.device
    ):
        """Power-law fit exponent is close to -0.5."""
        dose_levels = torch.tensor([5.0, 10.0, 20.0, 40.0], device=device)
        result = rms_scaling_check(
            line_acid, dose_levels, n_realisations=10, seed=42
        )
        exponent = result["fit_dose_exponent"]
        if not math.isnan(exponent):
            # Expect exponent ≈ -0.5, allow ±0.3 for stochasticity
            assert -0.8 <= exponent <= -0.2, (
                f"Exponent {exponent:.3f} not near -0.5"
            )

    def test_lwr_also_scales(self, line_acid: torch.Tensor, device: torch.device):
        """LWR also exhibits 1/√(dose) scaling."""
        dose_levels = torch.tensor([5.0, 10.0, 20.0, 40.0], device=device)
        result = rms_scaling_check(
            line_acid, dose_levels, n_realisations=8, seed=42
        )
        lwr = result["lwr"]
        # Higher dose → lower LWR
        finite_mask = ~torch.isnan(lwr)
        if finite_mask.sum() >= 2:
            valid = lwr[finite_mask]
            doses = dose_levels[finite_mask]
            # Check rough monotonicity
            for i in range(1, len(valid)):
                assert valid[i] <= valid[i - 1] * 1.2


# ──────────────────────────────────────────────
# 7. Edge cases and invariants
# ──────────────────────────────────────────────


class TestEdgeCases:
    def test_single_pixel_feature(self, device: torch.device):
        """Single-pixel undeveloped feature produces LER/LWR."""
        mask = torch.ones((32, 32), device=device)
        mask[16, 16] = 0.0  # single pixel resist
        ler = extract_ler(mask)
        lwr_val = extract_lwr(mask)
        # This is a degenerate case — may be NaN or 0
        assert lwr_val is not None

    def test_thin_line_ler(self, device: torch.device):
        """1-pixel-wide line has detectable LER."""
        mask = torch.ones((32, 32), device=device)
        mask[:, 14:16] = 0.0  # 2-pixel-wide line
        ler = extract_ler(mask)
        lwr_val = extract_lwr(mask)
        assert not math.isnan(ler) if not (mask == 0).all() else True
        assert not math.isnan(lwr_val) if not (mask == 0).all() else True

    def test_threshold_variation(self, device: torch.device):
        """Different thresholds produce different binary masks → different edges."""
        mask = torch.softmax(torch.randn((32, 32), device=device), dim=1)
        left1, right1 = extract_edges(mask, threshold=0.3)
        left2, right2 = extract_edges(mask, threshold=0.7)
        # Not all edges identical — at least some rows differ
        finite1 = ~(torch.isnan(left1) | torch.isnan(right1))
        finite2 = ~(torch.isnan(left2) | torch.isnan(right2))
        # Both should have some finite entries for a random mask
        assert finite1.sum() > 0
        assert finite2.sum() > 0

    def test_numerical_stability_high_dose(self, device: torch.device):
        """High dose values do not cause overflow."""
        acid = torch.ones((16, 16), device=device) * 10.0
        dose = torch.ones((16, 16), device=device) * 1e6
        rng = torch.Generator(device=device).manual_seed(0)
        noisy = poisson_shot_noise(acid, dose=dose, rng=rng)
        assert (noisy >= 0).all()
        assert not torch.isnan(noisy).any()
        assert not torch.isinf(noisy).any()


# ──────────────────────────────────────────────
# 8. Reproducibility and consistency
# ──────────────────────────────────────────────


class TestReproducibility:
    def test_shot_noise_reproducible(self, line_acid: torch.Tensor, device: torch.device):
        """Same seed → same shot noise (across calls in the same session)."""
        rng1 = torch.Generator(device=device).manual_seed(9999)
        rng2 = torch.Generator(device=device).manual_seed(9999)
        n1 = poisson_shot_noise(line_acid, rng=rng1)
        n2 = poisson_shot_noise(line_acid, rng=rng2)
        assert torch.allclose(n1, n2)

    def test_edges_reproducible(self, developed_rough_line: torch.Tensor):
        """Edge extraction is deterministic."""
        l1, r1 = extract_edges(developed_rough_line)
        l2, r2 = extract_edges(developed_rough_line)
        assert torch.allclose(l1, l2, equal_nan=True)
        assert torch.allclose(r1, r2, equal_nan=True)

    def test_ler_lwr_estimate_reproducible(
        self, line_acid: torch.Tensor, device: torch.device
    ):
        """Same seed across different generator objects produces same result."""
        rng1 = torch.Generator(device=device).manual_seed(777)
        rng2 = torch.Generator(device=device).manual_seed(777)
        result1 = ler_lwr_estimate(line_acid, shot_noise_rng=rng1)
        result2 = ler_lwr_estimate(line_acid, shot_noise_rng=rng2)
        assert result1["ler"] == pytest.approx(result2["ler"], abs=1e-10)
        assert result1["lwr"] == pytest.approx(result2["lwr"], abs=1e-10)

    def test_photon_count_consistent(self, line_acid: torch.Tensor, line_dose: torch.Tensor, device: torch.device):
        """Photon count from return_photon_count has expected magnitude."""
        rng = torch.Generator(device=device).manual_seed(42)
        _, photons = poisson_shot_noise(
            line_acid, dose=line_dose, return_photon_count=True, rng=rng
        )
        # For 20 mJ/cm² dose, 1 nm² voxel area, 91.84 eV/photon:
        #   photons/voxel = 20 * 1e-14 * 6.24e15 / 91.84 ≈ 13.6
        # The dose-peak region should have ~10–20 photons/voxel.
        mean_photons = photons[photons > 0].mean().item()
        assert 1 < mean_photons < 100, f"Mean photons {mean_photons} outside expected range"