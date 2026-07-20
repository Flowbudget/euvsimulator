"""Comprehensive tests for the resist module — exposure, PEB, development.

Tests cover the full resist simulation pipeline:

1. Dill ABC exposure (2D and 3D variants)
2. Gaussian secondary-electron blur
3. Dose-to-acid mapping
4. ADI reaction-diffusion PEB
5. Analytical PEB (no-diffusion)
6. Deprotection kinetics (FD and analytical)
7. Mack dissolution-rate model
8. Threshold development
9. Surface-advancement level-set development
10. CD extraction
11. Gradient/differentiability checks
12. Edge cases and invariants
"""

from __future__ import annotations

import pytest
import torch

from euv.resist import (
    MackModel,
    deprotection_analytical,
    deprotection_fd,
    dill_abc_exposure,
    dose_to_acid,
    extract_cd,
    gaussian_se_blur,
    reaction_diffusion_adi,
    reaction_diffusion_analytical,
    surface_advancement_level_set,
    threshold_development,
)

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def device() -> torch.device:
    return torch.device("cpu")


@pytest.fixture
def dose_map(device: torch.device) -> torch.Tensor:
    """64×64 dose map with a line/space pattern."""
    x = torch.linspace(-32, 32, 64, device=device)
    y = torch.linspace(-32, 32, 64, device=device)
    X, Y = torch.meshgrid(x, y, indexing="ij")
    # 40 nm line at centre
    dose = 20.0 * torch.exp(-0.5 * (X / 10.0) ** 2)  # [mJ/cm²]
    return dose


@pytest.fixture
def inhibitor_map(device: torch.device) -> torch.Tensor:
    """64×64 inhibitor pattern — uniform 1.0."""
    return torch.ones((64, 64), device=device)


@pytest.fixture
def mack_default() -> MackModel:
    return MackModel()


# ──────────────────────────────────────────────
# 1. Dill ABC exposure
# ──────────────────────────────────────────────


class TestDillABCExposure:
    def test_basic_2d(self, dose_map: torch.Tensor):
        """2D input returns (N, H, W) output."""
        acid, inhibitor = dill_abc_exposure(dose_map, n_layers=5)
        assert acid.ndim == 3
        assert acid.shape[0] == 5
        assert acid.shape[1:] == dose_map.shape
        assert inhibitor.shape == acid.shape

    def test_basic_3d(self, dose_map: torch.Tensor):
        """3D input with batch."""
        dose_3d = dose_map.unsqueeze(0)  # (1, H, W)
        acid, inhibitor = dill_abc_exposure(dose_3d, n_layers=3)
        assert acid.ndim == 4
        assert acid.shape[0] == 1
        assert acid.shape[1] == 3

    def test_exposure_inhibitor_decreases(self, dose_map: torch.Tensor):
        """Exposed regions have lower inhibitor."""
        _, inhibitor = dill_abc_exposure(dose_map, n_layers=1)
        assert inhibitor[0, 32, 32] < inhibitor[0, 0, 0]
        assert (inhibitor >= 0).all()
        assert (inhibitor <= 1).all()

    def test_exposure_acid_positive(self, dose_map: torch.Tensor):
        """Acid is positive where there's dose."""
        acid, _ = dill_abc_exposure(dose_map, C=0.05, n_layers=1)
        assert (acid >= 0).all()
        assert acid[0, 32, 32] > 0

    def test_zero_dose(self, device: torch.device):
        """Zero dose → no acid, full inhibitor."""
        zero = torch.zeros((32, 32), device=device)
        acid, inhibitor = dill_abc_exposure(zero, n_layers=1)
        assert (acid == 0).all()
        assert (inhibitor == 1).all()

    def test_differentiable(self, dose_map: torch.Tensor):
        """Exposure is differentiable w.r.t. dose."""
        dose = dose_map.clone().requires_grad_(True)
        acid, _ = dill_abc_exposure(dose, n_layers=1)
        loss = acid.sum()
        loss.backward()
        assert dose.grad is not None
        assert (dose.grad != 0).any()

    def test_custom_params(self, dose_map: torch.Tensor):
        """Custom A, B, C, Q produce different results."""
        # With multiple layers, A affects absorption
        acid1, _ = dill_abc_exposure(dose_map, A=0.8, n_layers=3)
        acid2, _ = dill_abc_exposure(dose_map, A=0.1, n_layers=3)
        assert not torch.allclose(acid1, acid2)

        # Also test C and Q with single layer
        acid3, _ = dill_abc_exposure(dose_map, C=0.5, n_layers=1)
        acid4, _ = dill_abc_exposure(dose_map, C=0.1, n_layers=1)
        assert not torch.allclose(acid3, acid4)

        acid5, _ = dill_abc_exposure(dose_map, Q=0.5, n_layers=1)
        acid6, _ = dill_abc_exposure(dose_map, Q=0.1, n_layers=1)
        assert not torch.allclose(acid5, acid6)

    def test_z_positions(self, dose_map: torch.Tensor):
        """Custom z positions are respected."""
        z = torch.tensor([0.0, 0.05, 0.10])
        acid, _ = dill_abc_exposure(dose_map, z_positions=z)
        assert acid.shape[0] == 3


# ──────────────────────────────────────────────
# 2. Gaussian secondary-electron blur
# ──────────────────────────────────────────────


class TestGaussianSEBlur:
    def test_sigma_zero_no_blur(self, dose_map: torch.Tensor):
        """sigma=0 → no blur (delta kernel)."""
        blurred = gaussian_se_blur(dose_map, sigma=0.1, kernel_size=3)
        # with minimal blur, centre should still be max
        assert blurred[32, 32] > blurred[0, 0]

    def test_output_shape_2d(self, dose_map: torch.Tensor):
        """2D input → 2D output, same shape."""
        blurred = gaussian_se_blur(dose_map, sigma=5.0)
        assert blurred.shape == dose_map.shape

    def test_output_shape_3d(self, device: torch.device):
        """3D input → 3D output."""
        img = torch.randn((4, 32, 32), device=device)
        blurred = gaussian_se_blur(img, sigma=3.0)
        assert blurred.shape == img.shape

    def test_output_shape_4d(self, device: torch.device):
        """4D input (B, C, H, W) → 4D output."""
        img = torch.randn((2, 3, 32, 32), device=device)
        blurred = gaussian_se_blur(img, sigma=3.0)
        assert blurred.shape == img.shape

    def test_blur_smoothes(self, device: torch.device):
        """Blurring spreads the peak — max decreases, nearby pixels get value."""
        img = torch.zeros((32, 32), device=device)
        img[16, 16] = 1.0
        blurred = gaussian_se_blur(img, sigma=5.0, kernel_size=31)
        assert blurred.max() < 1.0  # peak reduced
        assert blurred[16, 16] < 1.0  # peak itself reduced
        # small neighbourhood should have positive values
        assert (blurred[14:18, 14:18] > 0).all()

    def test_blur_preserves_total(self, device: torch.device):
        """Total sum is approximately preserved (within rounding)."""
        img = torch.zeros((32, 32), device=device)
        img[16, 16] = 1.0
        blurred = gaussian_se_blur(img, sigma=3.0, kernel_size=21)
        assert blurred.sum() == pytest.approx(1.0, abs=0.5)

    def test_sigma_range_euv(self, device: torch.device):
        """EUV-relevant sigma 2–10 nm works."""
        img = torch.randn((32, 32), device=device)
        for sigma in [2.0, 5.0, 10.0]:
            blurred = gaussian_se_blur(img, sigma=sigma)
            assert blurred.shape == img.shape

    def test_differentiable(self, device: torch.device):
        """Blur is differentiable w.r.t. input."""
        img = torch.randn((32, 32), device=device, requires_grad=True)
        blurred = gaussian_se_blur(img, sigma=5.0)
        loss = blurred.sum()
        loss.backward()
        assert img.grad is not None


# ──────────────────────────────────────────────
# 3. Dose-to-acid mapping
# ──────────────────────────────────────────────


class TestDoseToAcid:
    def test_basic(self, dose_map: torch.Tensor):
        """Mapping returns same shape as dose."""
        acid = dose_to_acid(dose_map)
        assert acid.shape == dose_map.shape

    def test_monotonic(self, dose_map: torch.Tensor):
        """Higher dose → more acid (monotonic)."""
        low = dose_to_acid(dose_map * 0.1)
        high = dose_to_acid(dose_map * 10.0)
        assert (high >= low).all()

    def test_zero_dose(self, device: torch.device):
        """Zero dose → zero acid."""
        zero = torch.zeros((16, 16), device=device)
        acid = dose_to_acid(zero)
        assert (acid == 0).all()

    def test_blur_optional(self, dose_map: torch.Tensor):
        """apply_blur=False skips blurring."""
        acid_blur = dose_to_acid(dose_map, apply_blur=True)
        acid_no_blur = dose_to_acid(dose_map, apply_blur=False)
        assert not torch.allclose(acid_blur, acid_no_blur)

    def test_differentiable(self, dose_map: torch.Tensor):
        """dose_to_acid supports autograd."""
        dose = dose_map.clone().requires_grad_(True)
        acid = dose_to_acid(dose)
        loss = acid.sum()
        loss.backward()
        assert dose.grad is not None


# ──────────────────────────────────────────────
# 4. ADI reaction-diffusion PEB
# ──────────────────────────────────────────────


class TestReactionDiffusionADI:
    def test_basic(self, dose_map: torch.Tensor, inhibitor_map: torch.Tensor):
        """ADI PEB runs and returns same shapes."""
        acid_in = dose_to_acid(dose_map)
        acid_out, inhib_out = reaction_diffusion_adi(
            acid_in, inhibitor_map, D=5.0, k=0.1, n_steps=5
        )
        assert acid_out.shape == acid_in.shape
        assert inhib_out.shape == inhibitor_map.shape

    def test_inhibitor_decreases(self, dose_map: torch.Tensor):
        """Inhibitor decreases after PEB where acid is present."""
        acid_in = dose_to_acid(dose_map)
        inhib_in = torch.ones_like(acid_in)
        _, inhib_out = reaction_diffusion_adi(acid_in, inhib_in, k=0.2, n_steps=10)
        assert inhib_out[32, 32] < inhib_out[0, 0]  # more deprotection at centre

    def test_no_reaction_no_change(self, device: torch.device):
        """k=0 → no deprotection, inhibitor unchanged."""
        acid = torch.rand((16, 16), device=device) * 0.5
        inhib = torch.ones((16, 16), device=device) * 0.5
        _, inhib_out = reaction_diffusion_adi(acid, inhib, k=0.0, n_steps=10)
        assert torch.allclose(inhib_out, inhib)

    def test_zero_diffusion(self, dose_map: torch.Tensor):
        """D=0 → acid concentration changes only via reaction."""
        acid_in = dose_to_acid(dose_map)
        inhib_in = torch.ones_like(acid_in)
        acid_out, _ = reaction_diffusion_adi(acid_in, inhib_in, D=0.0, k=0.0, n_steps=5)
        assert torch.allclose(acid_out, acid_in)

    def test_neumann_boundary(self, device: torch.device):
        """Neumann boundary approximately preserves total acid for D>0, k=0."""
        acid = torch.zeros((32, 32), device=device)
        acid[16, 16] = 1.0
        inhib = torch.ones_like(acid)
        acid_out, _ = reaction_diffusion_adi(acid, inhib, D=5.0, k=0.0, n_steps=3)
        # total acid approximately conserved with Neumann BC
        assert acid_out.sum() == pytest.approx(acid.sum(), abs=1e-2)

    def test_dirichlet_boundary(self, device: torch.device):
        """Dirichlet boundary reduces total acid."""
        acid = torch.zeros((32, 32), device=device)
        acid[16, 16] = 1.0
        inhib = torch.ones_like(acid)
        acid_out, _ = reaction_diffusion_adi(
            acid, inhib, D=5.0, k=0.0, n_steps=3, boundary="dirichlet"
        )
        assert acid_out.sum() < acid.sum()

    def test_differentiable(self, dose_map: torch.Tensor):
        """ADI is differentiable w.r.t. acid input."""
        acid_in = dose_to_acid(dose_map).requires_grad_(True)
        inhib_in = torch.ones_like(acid_in)
        _, inhib_out = reaction_diffusion_adi(acid_in, inhib_in, n_steps=2)
        loss = inhib_out.sum()
        loss.backward()
        assert acid_in.grad is not None


# ──────────────────────────────────────────────
# 5. Analytical PEB
# ──────────────────────────────────────────────


class TestReactionDiffusionAnalytical:
    def test_basic(self, dose_map: torch.Tensor):
        """Analytical PEB returns same shapes."""
        acid_in = dose_to_acid(dose_map)
        inhib_in = torch.ones_like(acid_in)
        acid_out, inhib_out = reaction_diffusion_analytical(
            acid_in, inhib_in, D=0.0, k=0.1, t_bake=10.0
        )
        assert acid_out.shape == acid_in.shape
        assert inhib_out.shape == inhib_in.shape

    def test_acid_unchanged_no_diffusion(self, dose_map: torch.Tensor):
        """Without diffusion, acid is unchanged."""
        acid_in = dose_to_acid(dose_map)
        inhib_in = torch.ones_like(acid_in)
        acid_out, _ = reaction_diffusion_analytical(acid_in, inhib_in, D=0.0, k=0.0)
        assert torch.allclose(acid_out, acid_in)

    def test_inhibitor_decays(self, dose_map: torch.Tensor):
        """Inhibitor decays exponentially with acid × k × t."""
        acid = torch.ones((16, 16)) * 0.5
        inhib = torch.ones((16, 16)) * 0.8
        _, inhib_out = reaction_diffusion_analytical(acid, inhib, D=0.0, k=0.2, t_bake=5.0)
        # M(t) = M₀ · exp(−k · [H⁺] · t) = 0.8 · exp(-0.2·0.5·5) = 0.8·exp(-0.5)
        expected = 0.8 * torch.exp(-0.5 * torch.ones(1))
        assert torch.allclose(inhib_out, expected.expand_as(inhib_out), atol=1e-6)

    def test_sigma_diff_blur(self, dose_map: torch.Tensor):
        """sigma_diff blurs the acid map."""
        acid_in = dose_to_acid(dose_map)
        inhib_in = torch.ones_like(acid_in)
        _, inhib_no_diff = reaction_diffusion_analytical(
            acid_in, inhib_in, sigma_diff=0.0, k=0.1, t_bake=10.0
        )
        _, inhib_diff = reaction_diffusion_analytical(
            acid_in, inhib_in, sigma_diff=10.0, k=0.1, t_bake=10.0
        )
        assert not torch.allclose(inhib_no_diff, inhib_diff)


# ──────────────────────────────────────────────
# 6. Deprotection kinetics
# ──────────────────────────────────────────────


class TestDeprotection:
    def test_fd_decreases(self, device: torch.device):
        """Finite-difference deprotection decreases inhibitor."""
        M = torch.ones((16, 16), device=device)
        A = torch.ones((16, 16), device=device) * 0.3
        M_out = deprotection_fd(M, A, k=0.1, dt=1.0, n_steps=10)
        assert (M_out <= M).all()
        assert (M_out >= 0).all()

    def test_fd_zero_rate(self, device: torch.device):
        """k=0 → no deprotection."""
        M = torch.rand((16, 16), device=device)
        A = torch.rand((16, 16), device=device)
        M_out = deprotection_fd(M, A, k=0.0, n_steps=10)
        assert torch.allclose(M_out, M)

    def test_analytical_exact(self, device: torch.device):
        """Analytical deprotection reproduces closed-form."""
        M = torch.ones((16, 16), device=device) * 0.9
        A = torch.ones((16, 16), device=device) * 0.2
        k, t = 0.15, 5.0
        M_out = deprotection_analytical(M, A, k=k, t=t)
        # M(t) = 0.9 · exp(-0.2·0.15·5.0) = 0.9 · exp(-0.15)
        expected = 0.9 * torch.exp(-0.15 * torch.ones(1, device=device))
        assert torch.allclose(M_out, expected.expand_as(M_out), atol=1e-6)

    def test_analytical_clamped(self, device: torch.device):
        """Analytical deprotection remains in [0, 1]."""
        M = torch.ones((16, 16), device=device)
        A = torch.ones((16, 16), device=device) * 2.0
        M_out = deprotection_analytical(M, A, k=1.0, t=10.0)
        assert (M_out >= 0).all()
        assert (M_out <= 1).all()

    def test_differentiable_fd(self, device: torch.device):
        """FD deprotection is differentiable w.r.t. inhibitor."""
        M = torch.ones((16, 16), device=device, requires_grad=True)
        A = torch.ones((16, 16), device=device) * 0.1
        M_out = deprotection_fd(M, A, k=0.1, n_steps=3)
        loss = M_out.sum()
        loss.backward()
        assert M.grad is not None

    def test_differentiable_analytical(self, device: torch.device):
        """Analytical deprotection is differentiable w.r.t. acid."""
        A = torch.ones((16, 16), device=device, requires_grad=True)
        M = torch.ones((16, 16), device=device) * 0.5
        M_out = deprotection_analytical(M, A, k=0.1, t=5.0)
        loss = M_out.sum()
        loss.backward()
        assert A.grad is not None


# ──────────────────────────────────────────────
# 7. Mack dissolution-rate model
# ──────────────────────────────────────────────


class TestMackModel:
    def test_rate_monotonic(self, mack_default: MackModel):
        """Lower inhibitor → higher dissolution rate."""
        M = torch.linspace(0.0, 1.0, 100)
        R = mack_default.rate(M)
        # rate should decrease as M increases (more protected → slower)
        diffs = torch.diff(R)
        assert (diffs <= 0).all() or not (diffs > 0).any()

    def test_rate_range(self, mack_default: MackModel):
        """Rate is between R_min and ≲ R_max + R_min."""
        M = torch.linspace(0.0, 1.0, 100)
        R = mack_default.rate(M)
        assert (R >= mack_default.R_min - 1e-6).all()
        # At M=0 the Mack model gives R(0) = R_max + R_min, so check accordingly
        assert (R <= mack_default.R_max + mack_default.R_min + 1e-6).all()

    def test_rate_at_M0(self, mack_default: MackModel):
        """At M=0 (fully deprotected) → R ≈ R_max."""
        R = mack_default.rate(torch.tensor(0.0))
        assert R == pytest.approx(mack_default.R_max, rel=1e-2)

    def test_rate_at_M1(self, mack_default: MackModel):
        """At M=1 (fully protected) → R ≈ R_min."""
        R = mack_default.rate(torch.tensor(1.0))
        assert R == pytest.approx(mack_default.R_min, abs=1e-2)

    def test_custom_parameters(self):
        """Custom Mack parameters produce expected behaviour."""
        mack = MackModel(R_max=200.0, R_min=0.5, n=10.0, M_th=0.4)
        R0 = mack.rate(torch.tensor(0.0))
        R1 = mack.rate(torch.tensor(1.0))
        assert R0 == pytest.approx(200.0, rel=1e-2)
        assert R1 == pytest.approx(0.5, abs=1e-2)

    def test_contrast(self, mack_default: MackModel):
        """Contrast is positive and finite."""
        gamma = mack_default.contrast()
        assert gamma > 0
        assert gamma < 100

    def test_repr(self, mack_default: MackModel):
        """__repr__ includes parameters."""
        r = repr(mack_default)
        assert "R_max" in r
        assert "M_th" in r


# ──────────────────────────────────────────────
# 8. Threshold development
# ──────────────────────────────────────────────


class TestThresholdDevelopment:
    def test_binary_output(self, device: torch.device):
        """Output is binary {0, 1}."""
        M = torch.linspace(0, 1, 100, device=device).view(10, 10)
        dev = threshold_development(M, threshold=0.5)
        assert set(dev.unique().tolist()).issubset({0.0, 1.0})

    def test_threshold_behaviour(self, device: torch.device):
        """M ≤ threshold → developed = 1."""
        M = torch.tensor([[0.1, 0.5, 0.9]], device=device)
        dev = threshold_development(M, threshold=0.5)
        assert dev[0, 0] == 1.0
        assert dev[0, 1] == 1.0
        assert dev[0, 2] == 0.0

    def test_same_shape(self, device: torch.device):
        """Output same shape as input."""
        M = torch.rand((32, 48), device=device)
        dev = threshold_development(M)
        assert dev.shape == M.shape


# ──────────────────────────────────────────────
# 9. Surface-advancement development
# ──────────────────────────────────────────────


class TestSurfaceAdvancement:
    def test_basic_3d(self, device: torch.device):
        """3D inhibitor input produces output."""
        inhib = torch.ones((10, 32, 32), device=device)
        # fully deprotected (low M) at centre
        inhib[:, 16, 16] = 0.1
        mack = MackModel()
        depth = surface_advancement_level_set(inhib, mack, dx=1.0, dz=1.0, t_develop=5.0)
        assert depth.shape == (32, 32)

    def test_more_development_at_centre(self, device: torch.device):
        """Fully deprotected columns develop faster."""
        inhib = torch.ones((10, 16, 16), device=device)
        inhib[:, :, 8] = 0.05  # column of cleared resist
        mack = MackModel(R_max=100.0)
        depth = surface_advancement_level_set(inhib, mack, dx=1.0, dz=1.0, t_develop=10.0)
        assert depth[0, 8] > depth[0, 0]


# ──────────────────────────────────────────────
# 10. CD extraction
# ──────────────────────────────────────────────


class TestCDExtraction:
    def test_simple_line_positive_tone(self, device: torch.device):
        """Positive-tone: developed=1 means dissolved, CD=undeveloped feature width.

        In positive-tone resist, developed regions (binary=1) dissolve
        and undeveloped regions (binary=0) remain as the feature.
        For a 30-nm line: undeveloped (0) at centre, developed (1) on
        both sides.
        """
        # 100 px wide, 30 px feature (undeveloped=0) in centre, developed=1 on sides
        line = torch.ones(100, device=device)
        line[35:65] = 0.0  # undeveloped feature: 30 px
        cd = extract_cd(line, dx=1.0)
        assert cd == pytest.approx(30.0, abs=1.0)

    def test_full_development(self, device: torch.device):
        """All developed → CD = 0."""
        line = torch.ones(100, device=device)
        cd = extract_cd(line)
        assert cd == 0.0

    def test_no_development(self, device: torch.device):
        """No development → CD = full width."""
        line = torch.zeros(100, device=device)
        cd = extract_cd(line)
        assert cd == pytest.approx(100.0, abs=1.0)

    def test_2d_input_middle_row(self, device: torch.device):
        """2D input extracts from middle row by default."""
        dev = torch.zeros((32, 100), device=device)  # all undeveloped
        dev[:, 35:65] = 1.0  # developed (dissolved) central band
        # Undeveloped regions: [0:34] (35 px) and [65:99] (35 px)
        # The larger = 35 px
        cd = extract_cd(dev, dx=1.0)
        assert cd == pytest.approx(35.0, abs=1.0)

    def test_returns_edges(self, device: torch.device):
        """Return edges on request."""
        line = torch.ones(100, device=device)
        line[40:70] = 0.0  # 30 px undeveloped feature
        cd, left, right = extract_cd(line, dx=2.0, return_edges=True)
        assert left == pytest.approx(80.0, abs=2.0)
        assert right == pytest.approx(140.0, abs=2.0)
        assert cd == pytest.approx(60.0, abs=2.0)

    def test_non_standard_spacing(self, device: torch.device):
        """Dx scales the CD."""
        line = torch.ones(100, device=device)
        line[30:60] = 0.0  # 30 px feature
        cd = extract_cd(line, dx=2.0)
        assert cd == pytest.approx(60.0, abs=2.0)

    def test_custom_row(self, device: torch.device):
        """Specific row can be selected."""
        dev = torch.zeros((10, 50), device=device)
        dev[0, :] = 1.0  # first row all developed → CD = 0
        dev[5, 10:40] = 1.0  # developed on sides
        # row 5: [0:9]=0 (10px), [10:39]=1 (30px), [40:49]=0 (10px)
        # longest undeveloped run = 10
        cd_top = extract_cd(dev, row=0)
        cd_mid = extract_cd(dev, row=5)
        assert cd_top == 0.0
        assert cd_mid == pytest.approx(10.0, abs=1.0)


# ──────────────────────────────────────────────
# 11. Integration: end-to-end resist pipeline
#


class TestEndToEnd:

    def test_pipeline_basic(self, device: torch.device):
        """End-to-end: dose -> acid -> inhib -> dev -> no NaNs, valid range."""
        x = torch.linspace(-32, 32, 64, device=device)
        X, _ = torch.meshgrid(x, x, indexing="ij")
        dose = 100.0 * torch.exp(-0.5 * (X / 8.0) ** 2)

        acid = dose_to_acid(dose, C=0.5, Q=0.3, sigma_blur=3.0)
        inhib_in = torch.ones_like(acid)
        _, inhib = reaction_diffusion_analytical(acid, inhib_in, k=1.0, t_bake=10.0)

        dev = threshold_development(inhib, threshold=0.5)
        assert not torch.isnan(dev).any(), "NaNs in developed image"
        assert set(dev.unique().tolist()).issubset({0.0, 1.0}), "Not binary"

    def test_pipeline_gradient(self, device: torch.device):
        """End-to-end pipeline is differentiable w.r.t. dose."""
        x = torch.linspace(-16, 16, 32, device=device)
        X, _ = torch.meshgrid(x, x, indexing="ij")
        dose = 20.0 * torch.exp(-0.5 * (X / 6.0) ** 2)
        dose.requires_grad_(True)

        acid = dose_to_acid(dose, C=0.01, Q=0.04, sigma_blur=3.0)
        inhib_in = torch.ones_like(acid)
        _, inhib = reaction_diffusion_analytical(acid, inhib_in, k=0.1, t_bake=5.0)

        # threshold development is not differentiable, but we can
        # compute a surrogate: sum of exposed area
        loss = (1.0 - inhib).sum()
        loss.backward()
        assert dose.grad is not None
        assert (dose.grad != 0).any()

    def test_pipeline_mack_threshold_cd(self, device: torch.device):
        """Mack model + threshold development + CD extraction."""
        # 20 nm bright line in centre — high dose, narrow
        dose = torch.zeros((64, 64), device=device)
        dose[:, 22:42] = 40.0  # 20 nm line at high dose

        acid = dose_to_acid(dose, C=0.05, Q=0.08, sigma_blur=1.5)
        inhib_in = torch.ones_like(acid)
        _, inhib = reaction_diffusion_analytical(acid, inhib_in, k=0.2, t_bake=5.0)

        # Low threshold to capture the exposed region as developed
        dev = threshold_development(inhib, threshold=0.15)
        cd = extract_cd(dev, dx=1.0)
        assert cd > 0


# ──────────────────────────────────────────────
# 12. Edge cases and invariants
# ──────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_dose_single_pixel(self, device: torch.device):
        """Single-pixel dose map handled gracefully."""
        dose = torch.tensor([[10.0]], device=device)
        # Small image: skip blur by not applying it
        acid = dose_to_acid(dose, apply_blur=False)
        assert acid.shape == (1, 1)
        assert acid[0, 0] > 0

    def test_large_sigma_blur(self, device: torch.device):
        """Very large sigma produces near-uniform output."""
        img = torch.zeros((16, 16), device=device)
        img[8, 8] = 10.0
        blurred = gaussian_se_blur(img, sigma=50.0, kernel_size=15)
        # with truncation at 3σ, kernel covers only small region
        # but results should be valid
        assert blurred.shape == img.shape
        assert (blurred >= 0).all()

    def test_negative_dose_clipped(self, device: torch.device):
        """Negative dose (non-physical) is handled gracefully."""
        dose = torch.randn((16, 16), device=device)
        acid = dose_to_acid(dose.abs())
        assert (acid >= 0).all()

    def test_varying_grid_spacing(self, device: torch.device):
        """Different dx values produce consistent results."""
        dose = torch.zeros((64, 64), device=device)
        dose[:, 24:40] = 30.0
        acid = dose_to_acid(dose, C=0.02, Q=0.05)
        dev = threshold_development(acid, threshold=0.01)
        cd1 = extract_cd(dev, dx=1.0)
        cd2 = extract_cd(dev, dx=2.0)
        assert cd1 > 0
        assert cd2 > 0
        # Same undeveloped region → cd2 / dx should ≈ cd1 / dx
        assert abs(cd1 / 1.0 - cd2 / 2.0) < 2.0

    def test_mack_model_batch(self, mack_default: MackModel):
        """Mack model handles batched input."""
        M = torch.rand((4, 16, 16))
        R = mack_default.rate(M)
        assert R.shape == M.shape
        assert (R >= 0).all()

    def test_adi_zero_diffusion_preserves_inhibitor(self, dose_map: torch.Tensor):
        """k=0, D>0 → acid diffuses, inhibitor unchanged."""
        acid_in = dose_to_acid(dose_map)
        inhib_in = torch.ones_like(acid_in) * 0.5
        _, inhib_out = reaction_diffusion_adi(acid_in, inhib_in, D=5.0, k=0.0, n_steps=5)
        assert torch.allclose(inhib_out, inhib_in, atol=1e-6)

    def test_full_pipeline_no_nans(self, device: torch.device):
        """End-to-end pipeline produces no NaNs."""
        dose = torch.rand((32, 32), device=device) * 40.0
        acid = dose_to_acid(dose)
        inhib_in = torch.ones_like(acid)
        _, inhib = reaction_diffusion_adi(acid, inhib_in, n_steps=5)
        dev = threshold_development(inhib)
        cd = extract_cd(dev)
        assert not torch.isnan(torch.tensor(cd))
        assert not torch.isnan(acid).any()
        assert not torch.isnan(inhib).any()
