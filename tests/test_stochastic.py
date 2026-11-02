"""Comprehensive tests for the stochastic resist module — shot noise, LER, LWR.

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

import euvsimulator.resist.stochastic as stochastic
from euvsimulator.resist.exposure import gaussian_se_blur
from euvsimulator.resist.stochastic import (
    extract_edges,
    extract_ler,
    extract_lwr,
    ler_lwr_estimate,
    poisson_shot_noise,
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
    """64×64 acid map with a vertical high-acid stripe in the centre.

    Columns are x (``indexing="xy"``, as in developed_line); with "ij"
    (before 2026-10-03) the stripe ran along the rows.  High acid in the
    centre develops, so this is a trench, not a resist line: use
    resist_line_acid for edge measurements.
    """
    x = torch.linspace(-32, 32, 64, device=device)
    X, _ = torch.meshgrid(x, x, indexing="xy")
    # Gaussian acid profile ~ 20 nm wide stripe at centre
    acid = 0.5 * torch.exp(-0.5 * (X / 8.0) ** 2)
    return acid


@pytest.fixture
def line_dose(device: torch.device) -> torch.Tensor:
    """64×64 dose map for the line_acid stripe [mJ/cm²], columns are x."""
    x = torch.linspace(-32, 32, 64, device=device)
    X, _ = torch.meshgrid(x, x, indexing="xy")
    dose = 20.0 * torch.exp(-0.5 * (X / 8.0) ** 2)
    return dose


@pytest.fixture
def resist_line_acid() -> torch.Tensor:
    """256 rows × 64 px acid map of a resist LINE: low acid in the centre,
    high in the spaces, so every row crosses two edges (1 nm pixels).
    """
    x = torch.arange(64, dtype=torch.float64)
    profile = 1.0 - torch.exp(-(((x - 32.0) / 10.0) ** 2))
    return profile.unsqueeze(0).expand(256, 64).clone()


@pytest.fixture
def resist_line_dose(resist_line_acid: torch.Tensor) -> torch.Tensor:
    """Dose map [mJ/cm²] with the pattern of resist_line_acid, peak 20
    (linear regime: acid ∝ dose, as in rms_scaling_check).
    """
    return 20.0 * resist_line_acid


@pytest.fixture
def developed_line(device: torch.device) -> torch.Tensor:
    """64×64 developed binary mask — vertical line, width ~6 px.

    Columns are x (``indexing="xy"``), so each row crosses the line as
    extract_edges expects; with "ij" (before 2026-09-25) the line ran along
    the rows and every edge sat at the image border.
    """
    x = torch.linspace(-32, 32, 64, device=device)
    X, _ = torch.meshgrid(x, x, indexing="xy")
    # line of width 6 pixels centred at x=0
    developed = (X.abs() > 3.5).float()  # 1 = developed (outside), 0 = resist
    return developed


@pytest.fixture
def developed_rough_line(device: torch.device) -> torch.Tensor:
    """64×64 developed mask with a rough edge for LER/LWR measurement."""
    x = torch.linspace(-32, 32, 64, device=device)
    X, Y_grid = torch.meshgrid(x, x, indexing="xy")  # columns x, rows y
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
        # |x| <= 3.5 on linspace(-32, 32, 64): resist in columns 29..34
        assert finite.all()
        assert torch.equal(left_f, torch.full_like(left_f, 29.0))
        assert torch.equal(right_f, torch.full_like(right_f, 34.0))

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
        assert ler == pytest.approx(0.0, abs=1e-12)

    def test_rough_line_positive_ler(self, developed_rough_line: torch.Tensor):
        """Sinusoidal edge of amplitude 2 px: LER = rms = 2/√2 px (measured
        1.46 px, the excess is pixel quantisation).
        """
        ler = extract_ler(developed_rough_line)
        assert ler == pytest.approx(2.0 / math.sqrt(2.0), rel=0.1)

    def test_left_edge_ler(self, developed_rough_line: torch.Tensor):
        """Left-edge LER is positive for a rough left edge."""
        ler = extract_ler(developed_rough_line, edge="left")
        assert ler == pytest.approx(2.0 / math.sqrt(2.0), rel=0.1)

    def test_right_edge_ler(self, developed_rough_line: torch.Tensor):
        """Right-edge LER is positive for a rough right edge."""
        ler = extract_ler(developed_rough_line, edge="right")
        assert ler == pytest.approx(2.0 / math.sqrt(2.0), rel=0.1)

    def test_ler_dx_scaling(self, developed_rough_line: torch.Tensor):
        """LER scales linearly with dx."""
        ler_1 = extract_ler(developed_rough_line, dx=1.0)
        ler_2 = extract_ler(developed_rough_line, dx=2.0)
        assert ler_2 == pytest.approx(2.0 * ler_1, rel=1e-12)

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
        """Sub-pixel edges are differentiable w.r.t. the intensity field.

        The integer edge index (argmax) carries no gradient; the linear
        interpolation of the threshold crossing does.  The former version
        used an "ij" field (the step ran along the rows) and asserted
        ``left.requires_grad or not mask.requires_grad``, which is always true.
        """
        x = torch.linspace(-16, 16, 32, device=device, dtype=torch.float64)
        X, _ = torch.meshgrid(x, x, indexing="xy")  # columns x
        intensity = torch.sigmoid(10.0 * (X.abs() - 4.0))  # ≈step but smooth
        developed = intensity.detach()

        left, right = extract_edges(developed)
        assert not left.requires_grad
        assert torch.equal(left, torch.full_like(left, 12.0))
        assert torch.equal(right, torch.full_like(right, 19.0))

        intensity.requires_grad_(True)
        left, right = extract_edges(developed, intensity=intensity)
        assert left.requires_grad and right.requires_grad
        assert torch.autograd.gradcheck(
            lambda field: extract_edges(developed, intensity=field), (intensity,)
        )

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
        """Mirror-image edges (fully anti-correlated): LWR = 2 × LER exactly.

        Independent edges would give √2 (see TestRMSScaling.test_lwr_also_scales).
        """
        ler = extract_ler(developed_rough_line, edge="both")
        lwr_val = extract_lwr(developed_rough_line)
        assert lwr_val == pytest.approx(2.0 * ler, rel=1e-9)

    def test_all_developed_nan(self, device: torch.device):
        """All-developed → LWR = NaN."""
        all_dev = torch.ones((32, 32), device=device)
        lwr = extract_lwr(all_dev)
        assert math.isnan(lwr)


# ──────────────────────────────────────────────
# 5. Combined LER/LWR estimate
# ──────────────────────────────────────────────


# Small-noise regime of TestRMSScaling (0.2 acids per photon, 5 nm SE blur).
_SMALL_NOISE = dict(quantum_efficiency=0.2, se_blur_nm=5.0, n_realisations=10)


def _linearised_ler(
    resist_line_acid: torch.Tensor,
    dose_peak: float,
    quantum_efficiency: float,
    se_blur_nm: float,
    threshold: float,
) -> float:
    """Linearised 1σ edge noise [nm] of the SE-blurred shot-noise acid field.

    Independent of ler_lwr_estimate: per 1 nm pixel the acid count is
    Poisson with mean D·k·p (k acids per mJ/cm² and nm², p the acid
    pattern), rescaled to p, so Var = p / (D·k).  The blur with kernel g
    gives Var_b = (g² ∗ p) / (D·k), and g² ∗ p = Σg² · blur_{σ/√2}(p) for a
    Gaussian g.  The edge moves by sd_b / |slope| at the threshold crossing
    of the blurred mean (left edge, 1 nm pixels).
    """
    k = 1e-14 * 6.241509074e15 / 91.84 * quantum_efficiency
    field = resist_line_acid[:64].clone()
    delta = torch.zeros_like(field)
    delta[32, 32] = 1.0
    sum_g2 = float((gaussian_se_blur(delta, sigma=se_blur_nm) ** 2).sum())
    mean = gaussian_se_blur(field, sigma=se_blur_nm)[0]
    var = gaussian_se_blur(field, sigma=se_blur_nm / math.sqrt(2.0))[0] * sum_g2
    var = var / (dose_peak * k)
    i = int(torch.nonzero(mean <= threshold)[0])
    frac = float((threshold - mean[i - 1]) / (mean[i] - mean[i - 1]))
    sd = math.sqrt(float(var[i - 1] + frac * (var[i] - var[i - 1])))
    return sd / float(mean[i - 1] - mean[i])


class TestLERLWREstimate:
    """ler_lwr_estimate on a resist line (low acid in the line).

    Before 2026-10-03 these tests used line_acid with indexing="ij" (no edge
    in any row, and a trench rather than a line) and asserted only types or
    ``is not None``.  That hid B1.12: the function thresholded the unblurred
    Poisson counts, so "noisy > 0.3" meant "at least one acid in this pixel",
    the edges sat at the image border and LER grew with dose (exponent +1.1).
    """

    def test_basic_run(
        self,
        resist_line_acid: torch.Tensor,
        resist_line_dose: torch.Tensor,
        rng: torch.Generator,
    ):
        """Default parameters: LER of the linearised shot-noise magnitude.

        Linearised 1.18 nm, measured 1.24 nm (seed 42, one realisation).
        """
        result = ler_lwr_estimate(resist_line_acid, dose=resist_line_dose, shot_noise_rng=rng)
        for key in ("ler", "lwr", "mean_acid", "mean_dose"):
            assert key in result
        expected = _linearised_ler(resist_line_acid, 20.0, 0.04, 2.5, 0.3)
        assert result["ler"] == pytest.approx(expected, rel=0.25)
        assert result["ler"] < result["lwr"] < 2.0 * result["ler"]

    def test_with_dose(self, resist_line_acid: torch.Tensor, resist_line_dose: torch.Tensor):
        """mean_dose and mean_acid are the means over the positive pixels."""
        rng = torch.Generator(device=resist_line_acid.device).manual_seed(42)
        result = ler_lwr_estimate(resist_line_acid, dose=resist_line_dose, shot_noise_rng=rng)
        positive = resist_line_dose > 0
        assert result["mean_dose"] == pytest.approx(float(resist_line_dose[positive].mean()))
        assert result["mean_acid"] == pytest.approx(float(resist_line_acid[positive].mean()))

    def test_without_dose(self, resist_line_acid: torch.Tensor):
        """Heuristic path without a dose map: mean_dose is None, finite LER."""
        rng = torch.Generator(device=resist_line_acid.device).manual_seed(42)
        result = ler_lwr_estimate(resist_line_acid, dose=None, shot_noise_rng=rng)
        assert result["mean_dose"] is None
        assert 0.0 < result["ler"] < 0.5  # 100 acids per unit acid and pixel

    def test_multiple_realisations(
        self, resist_line_acid: torch.Tensor, resist_line_dose: torch.Tensor
    ):
        """average=True returns the mean of the per-realisation values."""
        kwargs = dict(dose=resist_line_dose, n_realisations=5)
        listed = ler_lwr_estimate(
            resist_line_acid,
            average=False,
            shot_noise_rng=torch.Generator().manual_seed(42),
            **kwargs,
        )
        averaged = ler_lwr_estimate(
            resist_line_acid,
            average=True,
            shot_noise_rng=torch.Generator().manual_seed(42),
            **kwargs,
        )
        assert isinstance(averaged["ler"], float)
        assert averaged["ler"] == pytest.approx(sum(listed["ler"]) / 5, rel=1e-6)
        assert averaged["lwr"] == pytest.approx(sum(listed["lwr"]) / 5, rel=1e-6)

    def test_multiple_realisations_list(
        self, resist_line_acid: torch.Tensor, resist_line_dose: torch.Tensor
    ):
        """average=False returns one finite value per independent realisation."""
        rng = torch.Generator(device=resist_line_acid.device).manual_seed(42)
        result = ler_lwr_estimate(
            resist_line_acid,
            dose=resist_line_dose,
            n_realisations=5,
            average=False,
            shot_noise_rng=rng,
        )
        assert isinstance(result["ler"], list) and isinstance(result["lwr"], list)
        assert len(result["ler"]) == 5 and len(result["lwr"]) == 5
        assert all(math.isfinite(v) and v > 0 for v in result["ler"] + result["lwr"])
        assert len(set(result["ler"])) == 5

    def test_ler_matches_linearised_shot_noise(
        self, resist_line_acid: torch.Tensor, resist_line_dose: torch.Tensor
    ):
        """Small-noise regime: LER = sd(blurred acid) / |slope| at the crossing.

        Measured 0.381 nm against the linearised 0.405 nm (seed 42).
        """
        rng = torch.Generator().manual_seed(42)
        result = ler_lwr_estimate(
            resist_line_acid, dose=resist_line_dose, shot_noise_rng=rng, **_SMALL_NOISE
        )
        expected = _linearised_ler(resist_line_acid, 20.0, 0.2, 5.0, 0.3)
        assert result["ler"] == pytest.approx(expected, rel=0.15)

    def test_mean_edges_at_blurred_threshold_crossing(
        self,
        resist_line_acid: torch.Tensor,
        resist_line_dose: torch.Tensor,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Edges lie inside the frame, where the SE-blurred acid crosses the
        absolute threshold: 27.21 / 36.79 nm, measured 27.17 / 36.83 nm.

        The former function put them at the image border (0.8 / 62.3 nm).
        """
        captured: list[tuple[torch.Tensor, torch.Tensor]] = []
        original = stochastic.extract_edges

        def recording(*args, **kwargs):
            edges = original(*args, **kwargs)
            captured.append(edges)
            return edges

        monkeypatch.setattr(stochastic, "extract_edges", recording)
        rng = torch.Generator().manual_seed(42)
        ler_lwr_estimate(
            resist_line_acid, dose=resist_line_dose, shot_noise_rng=rng, **_SMALL_NOISE
        )
        left = torch.cat([edges[0] for edges in captured])
        right = torch.cat([edges[1] for edges in captured])
        assert not (left.isnan().any() or right.isnan().any())

        mean = gaussian_se_blur(resist_line_acid, sigma=5.0)[0]
        i = int(torch.nonzero(mean <= 0.3)[0])
        crossing = (i - 1) + float((0.3 - mean[i - 1]) / (mean[i] - mean[i - 1]))
        # the profile is symmetric about x = 32 with period 64
        assert float(left.mean()) == pytest.approx(crossing, abs=0.3)
        assert float(right.mean()) == pytest.approx(64.0 - crossing, abs=0.3)

    @pytest.mark.parametrize("seed", [0, 42])
    def test_ler_falls_with_dose(self, resist_line_acid: torch.Tensor, seed: int):
        """Fixed acid, rising dose: LER falls strictly, exponent -0.5 ± 0.1.

        Measured -0.478 (seed 0) and -0.498 (seed 42); before the fix +1.1.
        """
        doses = [10.0, 20.0, 40.0, 80.0]
        ler = []
        for d in doses:
            rng = torch.Generator().manual_seed(seed)
            result = ler_lwr_estimate(
                resist_line_acid,
                dose=d * resist_line_acid,
                develop_threshold=0.5,
                shot_noise_rng=rng,
                **_SMALL_NOISE,
            )
            ler.append(result["ler"])
        assert all(b < a for a, b in zip(ler, ler[1:])), ler
        design = torch.tensor([[math.log10(d), 1.0] for d in doses], dtype=torch.float64)
        log_ler = torch.tensor([[math.log10(v)] for v in ler], dtype=torch.float64)
        exponent = float(torch.linalg.lstsq(design, log_ler).solution[0, 0])
        assert -0.6 <= exponent <= -0.4, (exponent, ler)

    def test_develop_threshold_effect(
        self, resist_line_acid: torch.Tensor, resist_line_dose: torch.Tensor
    ):
        """A higher threshold sits where the acid noise is larger: LER rises.

        Linearised ratio LER(0.6) / LER(0.3) = 1.21, measured 1.26 (seed 42).
        """
        ler = {}
        for threshold in (0.3, 0.6):
            rng = torch.Generator().manual_seed(42)
            ler[threshold] = ler_lwr_estimate(
                resist_line_acid,
                dose=resist_line_dose,
                develop_threshold=threshold,
                shot_noise_rng=rng,
                **_SMALL_NOISE,
            )["ler"]
        expected = _linearised_ler(resist_line_acid, 20.0, 0.2, 5.0, 0.6) / _linearised_ler(
            resist_line_acid, 20.0, 0.2, 5.0, 0.3
        )
        ratio = ler[0.6] / ler[0.3]
        assert ratio > 1.1, ler
        assert ratio == pytest.approx(expected, rel=0.15)

    def test_lwr_about_sqrt2_ler(
        self, resist_line_acid: torch.Tensor, resist_line_dose: torch.Tensor
    ):
        """Edges 17 nm apart fluctuate almost independently: LWR ≈ √2 × LER."""
        rng = torch.Generator().manual_seed(42)
        result = ler_lwr_estimate(
            resist_line_acid,
            dose=resist_line_dose,
            develop_threshold=0.5,
            shot_noise_rng=rng,
            **_SMALL_NOISE,
        )
        ratio = result["lwr"] / result["ler"]
        assert 1.2 < ratio < 1.65, ratio


# ──────────────────────────────────────────────
# 6. 1/√(dose) RMS scaling verification
# ──────────────────────────────────────────────


# Small-noise regime (0.2 acids per incident photon, 5 nm SE blur, as in
# notebook 05): the edge noise is small against the image slope, so the
# linearised shot-noise law LER ∝ dose^-1/2 applies.  Measured 2026-09-25 over
# seeds 0-7: exponent -0.53 ... -0.56.  With 0.04 and 2.5 nm the edge noise at
# 10 mJ/cm² is ~3.7 nm and the exponent steepens to about -0.75.
_SCALING = dict(n_realisations=10, develop_threshold=0.5, quantum_efficiency=0.2, se_blur_nm=5.0)
_DOSES = torch.tensor([10.0, 20.0, 40.0, 80.0])


class TestRMSScaling:
    def test_basic_run(self, resist_line_acid: torch.Tensor):
        """Scaling check runs and returns one value per dose."""
        result = rms_scaling_check(resist_line_acid, _DOSES, seed=42, **_SCALING)
        for key in ("dose_levels", "ler", "lwr", "ler_sqrt_dose", "fit_dose_exponent"):
            assert key in result
        assert result["ler"].shape == _DOSES.shape

    def test_ler_decreases_with_dose(self, resist_line_acid: torch.Tensor):
        """LER falls strictly from 10 to 80 mJ/cm²."""
        ler = rms_scaling_check(resist_line_acid, _DOSES, seed=42, **_SCALING)["ler"]
        assert bool((ler[1:] < ler[:-1]).all()), ler.tolist()

    def test_ler_sqrt_dose_approximately_constant(self, resist_line_acid: torch.Tensor):
        """LER × √dose stays within 15 % of its mean."""
        product = rms_scaling_check(resist_line_acid, _DOSES, seed=42, **_SCALING)["ler_sqrt_dose"]
        deviations = (product - product.mean()).abs() / product.mean()
        assert bool((deviations < 0.15).all()), deviations.tolist()

    @pytest.mark.parametrize("seed", [0, 42])
    def test_fit_exponent_near_neg_half(self, resist_line_acid: torch.Tensor, seed: int):
        """Power-law exponent -0.5 ± 0.1 (the former version skipped its
        assert whenever fewer than three doses were fitted, i.e. always).
        """
        exponent = rms_scaling_check(resist_line_acid, _DOSES, seed=seed, **_SCALING)[
            "fit_dose_exponent"
        ]
        assert -0.6 <= exponent <= -0.4, f"Exponent {exponent:.3f} not near -0.5"

    def test_lwr_also_scales(self, resist_line_acid: torch.Tensor):
        """LWR falls with dose and is ~√2 × LER (independent edges)."""
        result = rms_scaling_check(resist_line_acid, _DOSES, seed=42, **_SCALING)
        lwr, ler = result["lwr"], result["ler"]
        assert bool((lwr[1:] < lwr[:-1]).all()), lwr.tolist()
        ratio = lwr / ler
        assert bool(((ratio > 1.2) & (ratio < 1.65)).all()), ratio.tolist()


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
        self,
        resist_line_acid: torch.Tensor,
        resist_line_dose: torch.Tensor,
        device: torch.device,
    ):
        """Same seed across different generator objects produces same result,
        another seed a different one (the former test ran on line_acid, whose
        LER is 0 for a trench, so any two runs agreed).
        """
        results = [
            ler_lwr_estimate(
                resist_line_acid,
                dose=resist_line_dose,
                shot_noise_rng=torch.Generator(device=device).manual_seed(seed),
            )
            for seed in (777, 777, 778)
        ]
        assert math.isfinite(results[0]["ler"]) and results[0]["ler"] > 0
        assert results[0]["ler"] == pytest.approx(results[1]["ler"], abs=1e-10)
        assert results[0]["lwr"] == pytest.approx(results[1]["lwr"], abs=1e-10)
        assert results[2]["ler"] != pytest.approx(results[0]["ler"], abs=1e-10)

    def test_photon_count_consistent(
        self, line_acid: torch.Tensor, line_dose: torch.Tensor, device: torch.device
    ):
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


# ──────────────────────────────────────────────
# 9. Sub-pixel edge interpolation (Step 4)
# ──────────────────────────────────────────────


class TestSubPixelInterpolation:
    def test_intensity_shape_mismatch_raises(self, device: torch.device):
        """Intensity with wrong shape raises ValueError."""
        developed = torch.zeros((32, 32), device=device)
        bad = torch.zeros((16, 16), device=device)
        with pytest.raises(ValueError, match="intensity shape"):
            extract_edges(developed, intensity=bad)

    def test_smooth_ramp_gives_fractional_edge(self, device: torch.device):
        """A smooth falling ramp crossing 0.5 gives the exact crossing.

        intensity = 0.8 -> 0.2 over 64 pixels; developed = intensity > 0.5.
        The undeveloped region starts where the ramp crosses 0.5, which is
        at pixel coordinate 31.5 (linear interpolation, exact).
        """
        W = 64
        x = torch.linspace(0.8, 0.2, W, device=device)  # falling ramp
        developed = (x > 0.5).float().unsqueeze(0).expand(8, W)
        intensity = x.unsqueeze(0).expand(8, W)
        left, _ = extract_edges(developed, threshold=0.5, dx=1.0, intensity=intensity)
        # crossing: x(k) = 0.8 - 0.6*k/63 = 0.5  ->  k = 31.5
        assert torch.allclose(left, torch.full_like(left, 31.5), atol=1e-6), (
            f"left edge {left[0].item():.6f} != 31.5"
        )

    def test_step_function_no_intensity_keeps_integer(self, device: torch.device):
        """Without intensity, edges stay at integer pixels (legacy)."""
        W = 32
        developed = torch.ones((8, W), device=device)
        developed[:, 8:24] = 0.0  # line (undeveloped) in the middle
        left, right = extract_edges(developed, threshold=0.5, dx=1.0)
        assert torch.allclose(left, torch.full_like(left, 8.0))
        assert torch.allclose(right, torch.full_like(right, 23.0))

    def test_subpixel_edge_between_integer_values(self, device: torch.device):
        """Crossing between two pixels interpolates linearly."""
        # Row: developed = [1, 0, 1] (undeveloped cell at index 1).
        # intensity = [0.4, 0.6, 0.4] crosses 0.5 at 0.5 (left) and 1.5 (right).
        developed = torch.tensor([[1.0, 0.0, 1.0]] * 4, device=device)
        intensity = torch.tensor([[0.4, 0.6, 0.4]] * 4, device=device)
        left, right = extract_edges(developed, threshold=0.5, dx=1.0, intensity=intensity)
        # left edge: crossing between 0 (0.4) and 1 (0.6):
        #   frac = (0.5-0.4)/(0.6-0.4) = 0.5 -> position 0.5
        assert torch.allclose(left, torch.full_like(left, 0.5), atol=1e-6)
        # right edge: crossing between 1 (0.6) and 2 (0.4):
        #   frac = (0.5-0.6)/(0.4-0.6) = 0.5 -> position 1.5
        assert torch.allclose(right, torch.full_like(right, 1.5), atol=1e-6)

    def test_perfect_step_subpixel_is_midpoint(self, device: torch.device):
        """Perfect step: sub-pixel edge sits at the pixel boundary (0.5)."""
        W = 64
        dev = torch.zeros((16, W), device=device)
        dev[:, 32:] = 1.0  # developed right of boundary
        intensity = torch.zeros((16, W), device=device)
        intensity[:, 32:] = 1.0  # perfect step at boundary 31/32
        _, right = extract_edges(dev, threshold=0.5, dx=1.0, intensity=intensity)
        # crossing between 31 (0.0) and 32 (1.0): frac=(0.5-0)/(1-0)=0.5
        # position = 31 + 0.5 = 31.5
        assert torch.allclose(right, torch.full_like(right, 31.5), atol=1e-6), (
            f"right edge {right[0].item():.6f} != 31.5"
        )

    def test_subpixel_reduces_grid_quantisation(self, device: torch.device):
        """Sub-pixel LER of a rough line matches the imposed edge modulation;
        the integer-pixel LER carries the quantisation error.

        Columns are x (``indexing="xy"``); the former "ij" field ran the line
        along the rows and only ``> 0`` was asserted.  Measured: exact
        1.3812 px, sub-pixel 1.3880 (+0.5 %), integer 1.4623 (+5.9 %).
        """
        x = torch.linspace(-32, 32, 64, device=device)
        X, Y = torch.meshgrid(x, x, indexing="xy")
        roughness_amp = 2.0
        edge_mod = roughness_amp * torch.sin(2 * torch.pi * Y / 16.0)
        intensity = torch.sigmoid(2.0 * (X.abs() + edge_mod - 4.0))
        developed = (intensity > 0.5).float()
        ler_int = extract_ler(developed, dx=1.0, intensity=intensity)
        ler_legacy = extract_ler(developed, dx=1.0)
        # Both edges move by edge_mod; in pixels of 64/63 x-units.
        shift_px = edge_mod[:, 0].double() * 63.0 / 64.0
        exact = float(torch.sqrt(((shift_px - shift_px.mean()) ** 2).mean()))
        assert ler_int == pytest.approx(exact, rel=0.03)
        assert abs(ler_int - exact) < abs(ler_legacy - exact)

    def test_legacy_path_unchanged(self, device: torch.device):
        """Calls without intensity give integer-pixel edges (first and last
        undeveloped pixel), within one pixel of the sub-pixel edges.
        """
        x = torch.linspace(-32, 32, 64, device=device)
        X, Y = torch.meshgrid(x, x, indexing="xy")
        roughness_amp = 2.0
        edge_mod = roughness_amp * torch.sin(2 * torch.pi * Y / 16.0)
        intensity = torch.sigmoid(2.0 * (X.abs() + edge_mod - 4.0))
        developed = (intensity > 0.5).float()
        l1, r1 = extract_edges(developed, threshold=0.5, dx=1.0)
        l2, r2 = extract_edges(developed, threshold=0.5, dx=1.0, intensity=None)
        assert torch.allclose(l1, l2, equal_nan=True)
        assert torch.allclose(r1, r2, equal_nan=True)
        resist = developed < 0.5
        cols = torch.arange(64, dtype=l1.dtype).expand(64, 64)
        assert torch.equal(l1, torch.where(resist, cols, 64.0).amin(dim=1))
        assert torch.equal(r1, torch.where(resist, cols, -1.0).amax(dim=1))
        ls, rs = extract_edges(developed, threshold=0.5, dx=1.0, intensity=intensity)
        assert bool(((l1 - ls).abs() <= 1.0).all() and ((r1 - rs).abs() <= 1.0).all())
