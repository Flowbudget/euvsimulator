"""Tests for the etch bias module (euv.etch.bias)."""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.etch.bias import (
    _disk_kernel,
    _gaussian_kernel_2d,
    apply_bias_to_aerial,
    empirical_cd_bias,
    etch_bias_from_formula,
    isotropic_bias,
)

# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────


def _make_square_contour(size: int = 64, square_size: int = 16) -> torch.Tensor:
    """Create a binary contour with a central square."""
    contour = torch.zeros(size, size, dtype=torch.float32)
    lo = size // 2 - square_size // 2
    hi = lo + square_size
    contour[lo:hi, lo:hi] = 1.0
    return contour


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────


class TestIsotropicBias:
    def test_positive_bias_expands_feature(self):
        """Positive bias (dilation) should increase the number of 1-pixels."""
        contour = _make_square_contour(64, 16)
        n_before = int(contour.sum().item())
        biased = isotropic_bias(contour, bias_nm=10.0, pixel_size_nm=1.0)
        n_after = int(biased.sum().item())
        assert n_after > n_before, (
            f"Positive bias should expand the feature; {n_before} → {n_after}"
        )

    def test_negative_bias_erodes_feature(self):
        """Negative bias (erosion) should decrease the number of 1-pixels."""
        contour = _make_square_contour(64, 16)
        n_before = int(contour.sum().item())
        biased = isotropic_bias(contour, bias_nm=-5.0, pixel_size_nm=1.0)
        n_after = int(biased.sum().item())
        assert n_after < n_before, (
            f"Negative bias should shrink the feature; {n_before} → {n_after}"
        )

    def test_output_shape_matches_input(self):
        """Output tensor has the same shape as the input."""
        contour = _make_square_contour(64, 16)
        biased = isotropic_bias(contour, bias_nm=5.0, pixel_size_nm=1.0)
        assert biased.shape == contour.shape

    def test_output_is_binary(self):
        """Output contains only 0 and 1 values."""
        contour = _make_square_contour(64, 16)
        biased = isotropic_bias(contour, bias_nm=5.0, pixel_size_nm=1.0)
        unique = set(biased.unique().tolist())
        assert unique.issubset({0.0, 1.0})

    def test_zero_bias_is_identity(self):
        """Zero bias returns the original contour unchanged."""
        contour = _make_square_contour(64, 16)
        biased = isotropic_bias(contour, bias_nm=0.0, pixel_size_nm=1.0)
        assert torch.allclose(biased, contour)

    def test_3d_input_preserved(self):
        """3D input (1, H, W) returns 3D output."""
        contour = _make_square_contour(64, 16).unsqueeze(0)
        biased = isotropic_bias(contour, bias_nm=5.0, pixel_size_nm=1.0)
        assert biased.ndim == 3
        assert biased.shape == contour.shape


class TestEmpiricalCDBias:
    def test_positive_bias_from_default_params(self):
        """Default parameters produce a positive bias for typical AR."""
        # CD_in = 30 nm, AR = 3 (depth 90 / width 30)
        cd_out = empirical_cd_bias(30.0, 3.0)
        # Bias = 2.0 * 3.0^(-0.5) ≈ 1.155, so cd_out ≈ 31.155
        assert cd_out > 30.0, f"Expected CD increase, got {cd_out}"

    def test_high_aspect_ratio_reduces_bias(self):
        """Higher AR yields smaller bias (inverse RIE lag)."""
        cd1 = empirical_cd_bias(30.0, 1.0)
        cd2 = empirical_cd_bias(30.0, 5.0)
        # Bias decreases with increasing AR when b < 0
        # For AR=1: bias = 2.0 * 1.0^(-0.5) = 2.0
        # For AR=5: bias = 2.0 * 5.0^(-0.5) ≈ 0.89
        # CD = 30 + bias, so cd1 > cd2
        assert cd1 > cd2, f"Expected cd1 ({cd1}) > cd2 ({cd2})"

    def test_custom_parameters(self):
        """Custom parameters override defaults."""
        cd_out = empirical_cd_bias(40.0, 2.0, parameters={"a": 5.0, "b": -0.3, "c": 2.0})
        # Expected: 40 + 5.0 * 2.0^(-0.3) + 2.0 = 40 + 5.0 * 0.812 + 2.0 = 46.06
        expected = 40.0 + 5.0 * (2.0**-0.3) + 2.0
        assert abs(cd_out - expected) < 0.1, f"Expected ~{expected:.2f}, got {cd_out}"

    def test_output_never_negative(self):
        """Output is clamped to at least 1 nm."""
        cd_out = empirical_cd_bias(0.5, 10.0, parameters={"a": -100.0, "b": 0.0, "c": 0.0})
        assert cd_out >= 1.0

    def test_returns_float(self):
        """Returns a plain Python float."""
        cd_out = empirical_cd_bias(30.0, 2.0)
        assert isinstance(cd_out, float)


class TestEtchBiasFromFormula:
    def test_cf4_produces_nonzero_bias(self):
        """CF4 chemistry returns a non-zero bias."""
        bias = etch_bias_from_formula(cd_nm=32.0, pitch_nm=64.0, depth_nm=60.0, chemistry="cf4")
        assert bias != 0.0, "CF4 bias should be non-zero"

    def test_unknown_chemistry_raises(self):
        """Unknown chemistry raises ValueError."""
        with pytest.raises(ValueError, match="Unknown chemistry"):
            etch_bias_from_formula(32.0, 64.0, 60.0, chemistry="unknown_chem")

    def test_chemistry_is_case_insensitive(self):
        """Chemistry names are case-insensitive."""
        bias_upper = etch_bias_from_formula(32.0, 64.0, 60.0, chemistry="CF4")
        bias_lower = etch_bias_from_formula(32.0, 64.0, 60.0, chemistry="cf4")
        assert bias_upper == bias_lower

    def test_all_chemistries_produce_float(self):
        """All supported chemistries return a finite float."""
        for chem in ["cf4", "sf6", "cl2", "hbr", "chf3"]:
            bias = etch_bias_from_formula(cd_nm=32.0, pitch_nm=64.0, depth_nm=60.0, chemistry=chem)
            assert isinstance(bias, float), f"{chem}: expected float, got {type(bias)}"
            assert math.isfinite(bias), f"{chem}: bias is not finite ({bias})"

    def test_small_feature_larger_bias_than_large(self):
        """Smaller features typically have larger bias (inverse RIE lag)."""
        bias_small = etch_bias_from_formula(
            cd_nm=16.0, pitch_nm=32.0, depth_nm=60.0, chemistry="cf4"
        )
        bias_large = etch_bias_from_formula(
            cd_nm=64.0, pitch_nm=128.0, depth_nm=60.0, chemistry="cf4"
        )
        assert bias_small != bias_large, "Bias should differ with feature size"


class TestSingularInputs:
    def test_formula_zero_depth_raises_for_negative_ar_exponent(self):
        """Depth 0 means AR 0, where AR**d with d < 0 diverges (was ZeroDivisionError)."""
        for chem in ("cf4", "cl2", "chf3"):
            with pytest.raises(ValueError, match="depth_nm = 0"):
                etch_bias_from_formula(32.0, 64.0, 0.0, chemistry=chem)

    def test_formula_zero_depth_finite_for_positive_ar_exponent(self):
        """sf6 and hbr have d > 0, so depth 0 stays a finite number as before."""
        bias_sf6 = etch_bias_from_formula(32.0, 64.0, 0.0, chemistry="sf6")
        bias_hbr = etch_bias_from_formula(32.0, 64.0, 0.0, chemistry="hbr")
        assert bias_sf6 == pytest.approx(1.5606601717798214, rel=1e-12)
        assert bias_hbr == pytest.approx(-0.75, rel=1e-12)

    def test_formula_rejects_nonpositive_cd_and_negative_depth(self):
        """A CD <= 0 raised ZeroDivisionError or gave a complex number; depth < 0 too."""
        with pytest.raises(ValueError, match="cd_nm"):
            etch_bias_from_formula(0.0, 64.0, 60.0, chemistry="cf4")
        with pytest.raises(ValueError, match="cd_nm"):
            etch_bias_from_formula(-32.0, 64.0, 60.0, chemistry="cf4")
        with pytest.raises(ValueError, match="depth_nm"):
            etch_bias_from_formula(32.0, 64.0, -60.0, chemistry="hbr")

    def test_empirical_zero_or_negative_aspect_ratio(self):
        """AR 0 with b < 0 diverges, AR < 0 is complex; AR 0 with b >= 0 stays valid."""
        with pytest.raises(ValueError, match="aspect_ratio"):
            empirical_cd_bias(32.0, 0.0)
        with pytest.raises(ValueError, match="aspect_ratio"):
            empirical_cd_bias(32.0, -1.0)
        cd_out = empirical_cd_bias(32.0, 0.0, parameters={"a": 2.0, "b": 0.5, "c": 0.0})
        assert cd_out == 32.0


class TestApplyBiasToAerial:
    def test_output_shape_matches_input(self):
        """Output has the same shape as the input aerial image."""
        aerial = torch.ones(64, 64, dtype=torch.float32) * 0.5
        biased = apply_bias_to_aerial(aerial, bias_nm=8.0, pixel_size_nm=1.0)
        assert biased.shape == aerial.shape

    def test_negligible_bias_returns_clone(self):
        """Very small bias (sigma < 0.5 px) returns a clone."""
        aerial = torch.ones(64, 64, dtype=torch.float32)
        biased = apply_bias_to_aerial(aerial, bias_nm=0.01, pixel_size_nm=1.0)
        assert torch.allclose(biased, aerial)

    def test_large_bias_blurs_image(self):
        """Large bias produces a blurred (smoother) image."""
        # Create a sharp step edge
        aerial = torch.zeros(64, 64, dtype=torch.float32)
        aerial[:, 32:] = 1.0
        biased = apply_bias_to_aerial(aerial, bias_nm=20.0, pixel_size_nm=1.0)
        # The edge should now be smooth — values between 0 and 1 at the boundary
        edge_col = 32
        mid_values = biased[:, edge_col]
        assert mid_values.min() > 0.0, "Edge should be blurred (no zero at boundary)"
        assert mid_values.max() < 1.0, "Edge should be blurred (no pure 1 at boundary)"

    def test_3d_input_preserved(self):
        """3D input (1, H, W) returns 3D output."""
        aerial = torch.ones(1, 64, 64, dtype=torch.float32)
        biased = apply_bias_to_aerial(aerial, bias_nm=8.0, pixel_size_nm=1.0)
        assert biased.ndim == 3

    def test_dtype_preserved(self):
        """Output dtype matches input dtype."""
        aerial = torch.ones(64, 64, dtype=torch.float64)
        biased = apply_bias_to_aerial(aerial, bias_nm=8.0, pixel_size_nm=1.0)
        assert biased.dtype == aerial.dtype


# ──────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────


class TestInternalHelpers:
    def test_disk_kernel_properties(self):
        """Disk kernel is square, odd-sized, and binary."""
        kernel = _disk_kernel(7)
        assert kernel.shape == (1, 1, 7, 7)
        # Binary: values are 0 or 1 (unnormalised)
        assert set(kernel.unique().tolist()).issubset({0.0, 1.0})
        # At least half the kernel should be inside the disk
        assert float(kernel.sum()) > 20.0

    def test_gaussian_kernel_normalised(self):
        """Gaussian kernel sums to 1."""
        kernel = _gaussian_kernel_2d(sigma=2.0)
        assert abs(float(kernel.sum()) - 1.0) < 1e-6


class TestPeriodicBoundary:
    def test_uniform_aerial_stays_uniform(self):
        """A flat image stays flat under the periodic blur (zero padding gave min 0.284)."""
        biased = apply_bias_to_aerial(torch.ones(64, 64), bias_nm=12.0, pixel_size_nm=1.0)
        assert torch.allclose(biased, torch.ones(64, 64), atol=1e-6)

    def test_zero_padding_still_available(self):
        """periodic=False reproduces the former zero-padded result."""
        biased = apply_bias_to_aerial(
            torch.ones(64, 64), bias_nm=12.0, pixel_size_nm=1.0, periodic=False
        )
        assert float(biased.min()) == pytest.approx(0.2844, abs=1e-3)
        assert float(biased.max()) == pytest.approx(1.0, abs=1e-5)

    def test_feature_wrapping_across_border(self):
        """Erosion and dilation are duals for a line that wraps across the array edge."""
        contour = torch.zeros(64, 64)
        contour[:, 0:10] = 1.0
        contour[:, 54:64] = 1.0  # one 20-px line, split by the periodic boundary
        grown = isotropic_bias(contour, bias_nm=2.0, pixel_size_nm=1.0)
        shrunk = isotropic_bias(contour, bias_nm=-2.0, pixel_size_nm=1.0)
        assert int(grown[32].sum()) == 24
        assert int(shrunk[32].sum()) == 16
        shrunk_zero = isotropic_bias(contour, bias_nm=-2.0, pixel_size_nm=1.0, periodic=False)
        assert int(shrunk_zero[32].sum()) == 12

    def test_shift_equivariance(self):
        """Rolling the input rolls the output: the array edge is not a special place."""
        img = torch.zeros(48, 40)
        img[0:12, 30:40] = 1.0
        img[20:34, 0:9] = 1.0
        img[40:48, 14:26] = 1.0
        shift = (7, 11)
        for bias in (3.0, -3.0):
            a = torch.roll(isotropic_bias(img, bias, 1.0), shift, (0, 1))
            b = isotropic_bias(torch.roll(img, shift, (0, 1)), bias, 1.0)
            assert torch.equal(a, b), f"bias {bias}"
        gen = torch.Generator().manual_seed(0)
        aerial = torch.rand(48, 40, dtype=torch.float64, generator=gen)
        a = torch.roll(apply_bias_to_aerial(aerial, 10.0, 1.0), shift, (0, 1))
        b = apply_bias_to_aerial(torch.roll(aerial, shift, (0, 1)), 10.0, 1.0)
        assert torch.allclose(a, b, atol=1e-12)

    def test_kernel_larger_than_image(self):
        """Kernel (61 px) wider than the 8-px array: the blur still conserves the mean.

        Tolerance 1e-6: _gaussian_kernel_2d normalises in float32 before the cast.
        """
        gen = torch.Generator().manual_seed(1)
        aerial = torch.rand(8, 8, dtype=torch.float64, generator=gen)
        biased = apply_bias_to_aerial(aerial, bias_nm=20.0, pixel_size_nm=1.0)
        assert biased.shape == (8, 8)
        assert float(biased.mean()) == pytest.approx(float(aerial.mean()), rel=1e-6)
        flat = apply_bias_to_aerial(torch.ones(8, 8, dtype=torch.float64), 20.0, 1.0)
        assert torch.allclose(flat, torch.ones(8, 8, dtype=torch.float64), atol=1e-6)

    @pytest.mark.skipif(
        not (torch.cuda.is_available() or torch.backends.mps.is_available()),
        reason="needs a CUDA or MPS device",
    )
    def test_aerial_on_accelerator(self):
        """The blur kernel follows the image device (the old default device='cpu' raised)."""
        dev = "cuda" if torch.cuda.is_available() else "mps"
        # explicit float32: MPS cannot hold float64, and the process default
        # may be float64 (several test modules set it at import)
        aerial = torch.ones(32, 32, device=dev, dtype=torch.float32)
        biased = apply_bias_to_aerial(aerial, bias_nm=8.0, pixel_size_nm=1.0)
        assert biased.device.type == dev
        # cuDNN (CUDA, float32, possibly TF32) accumulates the 625-tap sum with
        # ~3e-5 error; CPU float32 stays at 1e-7. 1e-4 is the realistic
        # device-independent bound for a uniform image.
        assert torch.allclose(biased.cpu(), torch.ones(32, 32, dtype=torch.float32), atol=1e-4)
