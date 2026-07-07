"""Tests for the GPU Acceleration Layer (``euv.accel``) module.

All tests must pass on CPU (no GPU available in CI).
"""

from __future__ import annotations

import pytest
import torch

from euv.accel.device import device_info, select_device, set_default_dtype
from euv.accel.mixed_precision import (
    autocast_complex,
    precision_policy,
    real_only,
)
from euv.accel.vram_budget import (
    check_oom,
    estimate_abbe_vram,
    estimate_rcma_vram,
    max_harmonics_for_vram,
    vram_report,
)

# ──────────────────────────────────────────────
# Device selection
# ──────────────────────────────────────────────


class TestDeviceSelection:
    """select_device and device_info must work correctly on CPU."""

    def test_select_device_cpu(self):
        """select_device returns cpu when no GPU."""
        dev = select_device(prefer_gpu=True)
        assert isinstance(dev, torch.device)
        assert dev.type in ("cpu", "cuda")

    def test_device_info_cpu(self):
        """device_info returns expected keys on CPU."""
        info = device_info(torch.device("cpu"))
        assert info["name"] == "cpu"
        assert info["vram_gb"] == 0.0
        assert info["compute_capability"] is None

    def test_set_default_dtype(self):
        """set_default_dtype does not raise."""
        set_default_dtype(torch.complex128, torch.float64)
        # Restore to avoid side-effects on other tests
        torch.set_default_dtype(torch.float64)


# ──────────────────────────────────────────────
# VRAM budget estimators
# ──────────────────────────────────────────────


class TestVramBudget:
    """Verify analytical estimators and OOM guard."""

    def test_vram_estimate_rcma(self):
        """RCWA estimate scales with M² = (2n+1)²."""
        # Compare n_orders = 11 (M=23) vs n_orders = 21 (M=43)
        # Ratio: (43² / 23²) ≈ 3.49
        est_11 = estimate_rcma_vram(11, n_layers=12)
        est_21 = estimate_rcma_vram(21, n_layers=12)
        # Account for the 128 MB overhead in the ratio
        overhead = 128 * 1024 * 1024
        adjusted_21 = est_21 - overhead
        adjusted_11 = est_11 - overhead
        ratio = adjusted_21 / adjusted_11 if adjusted_11 > 0 else float("inf")
        expected_ratio = (43**2) / (23**2)
        assert ratio == pytest.approx(
            expected_ratio, rel=0.05
        ), f"Expected M² scaling ratio ~{expected_ratio:.3f}, got {ratio:.3f}"

    def test_vram_estimate_abbe(self):
        """Abbe estimate returns a positive integer."""
        est = estimate_abbe_vram(grid_size=256, n_source_points=200)
        assert isinstance(est, int)
        assert est > 0

    def test_max_harmonics_reasonable(self):
        """max_harmonics_for_vram returns at least 11 on 14 GiB."""
        M = max_harmonics_for_vram(vram_budget_gb=14, n_layers=12)
        assert isinstance(M, int)
        assert M >= 11, f"Expected M >= 11, got {M}"
        # Must be odd
        assert M % 2 == 1, f"Expected odd M, got {M}"

    def test_vram_report_nonempty(self):
        """vram_report returns a non-empty formatted string."""
        report = vram_report()
        assert isinstance(report, str)
        assert len(report) > 100
        assert "RCWA estimates" in report
        assert "Abbe estimates" in report

    def test_oom_raises(self):
        """check_oom raises MemoryError when budget is exceeded."""
        with pytest.raises(MemoryError, match="exceeds"):
            check_oom(total_bytes=20 * 1024**3, vram_gb=14)  # 20 GiB > 14 GiB

    def test_oom_passes(self):
        """check_oom does not raise when under budget."""
        # Should not raise
        check_oom(total_bytes=8 * 1024**3, vram_gb=14)  # 8 GiB < 14 GiB


# ──────────────────────────────────────────────
# Mixed precision
# ──────────────────────────────────────────────


class TestMixedPrecision:
    """autocast_complex, real_only, and precision_policy."""

    def test_autocast_complex_downcasts(self):
        """autocast_complex downcasts complex128 -> complex64."""
        t = torch.randn(4, 4, dtype=torch.complex128)
        result = autocast_complex(t)
        assert result.dtype == torch.complex64

    def test_autocast_complex_passthrough(self):
        """autocast_complex passes complex64 unchanged."""
        t = torch.randn(4, 4, dtype=torch.complex64)
        result = autocast_complex(t)
        assert result.dtype == torch.complex64
        # Should be the same object if already complex64
        assert result.data_ptr() == t.data_ptr()

    def test_autocast_complex_real_passthrough(self):
        """autocast_complex passes real tensors unchanged."""
        t = torch.randn(4, 4, dtype=torch.float64)
        result = autocast_complex(t)
        assert result.dtype == torch.float64
        assert result.data_ptr() == t.data_ptr()

    def test_real_only_halves_memory(self):
        """real_only extracts the real component."""
        t = torch.randn(4, 4, dtype=torch.complex128)
        result = real_only(t)
        assert result.dtype == torch.float64
        assert result.shape == t.shape
        # Verify values
        assert torch.allclose(result, t.real)

    def test_precision_policy_high_vram(self):
        """precision_policy returns complex128 for >=12 GiB."""
        policy = precision_policy(vram_gb=16)
        assert policy["spectrum"] == torch.complex128
        assert policy["pupil"] == torch.complex128
        assert policy["image"] == torch.float64

    def test_precision_policy_mid_vram(self):
        """precision_policy returns mixed precision for 6–12 GiB."""
        policy = precision_policy(vram_gb=8)
        assert policy["spectrum"] == torch.complex64
        assert policy["image"] == torch.float64  # accumulate in double

    def test_precision_policy_low_vram(self):
        """precision_policy returns complex64 for <6 GiB."""
        policy = precision_policy(vram_gb=4)
        assert policy["spectrum"] == torch.complex64
        assert policy["image"] == torch.float32


# ──────────────────────────────────────────────
# Chunked Abbe
# ──────────────────────────────────────────────


class TestChunkedAbbe:
    """chunked_abbe must match full abbe_image within numerical
    precision on CPU.
    """

    def test_chunked_matches_full(self):
        """chunked_abbe matches abbe_image within 1e-10 on CPU."""
        from euv.accel.chunked import chunked_abbe
        from euv.aerial.abbe import abbe_image
        from euv.aerial.pupil import pupil_grid

        G = 32
        na = 0.33
        device = torch.device("cpu")

        # Frequency grid
        fx, fy, _ = pupil_grid(G, na=na, device=device)

        # Simple circular pupil
        pupil = ((fx**2 + fy**2) <= na**2).to(torch.complex128)

        # Mask: a simple test pattern — single centred slit → sinc spectrum
        mask = torch.zeros(G, G, dtype=torch.complex128, device=device)
        slit_width = G // 4
        center = G // 2
        mask[
            center - slit_width // 2 : center + slit_width // 2,
            center - slit_width // 2 : center + slit_width // 2,
        ] = 1.0
        mask_fft = torch.fft.fft2(torch.fft.fftshift(mask))

        # Illumination source: a few bright points
        source = torch.zeros(G, G, dtype=torch.float64, device=device)
        source[G // 2, G // 2] = 0.5  # on-axis
        source[G // 2 + 3, G // 2 - 2] = 0.3
        source[G // 2 - 4, G // 2 + 1] = 0.2

        # Full Abbe
        full = abbe_image(mask_fft, source, fx, fy, pupil, na)

        # Chunked Abbe with small chunks
        chunked = chunked_abbe(mask_fft, source, fx, fy, pupil, na, chunk_size=1)

        assert torch.allclose(
            full, chunked, atol=1e-10
        ), f"Max diff: {(full - chunked).abs().max().item():.2e}"

    def test_chunked_empty_source(self):
        """chunked_abbe handles empty source gracefully."""
        from euv.accel.chunked import chunked_abbe
        from euv.aerial.pupil import pupil_grid

        G = 16
        na = 0.33
        device = torch.device("cpu")
        fx, fy, _ = pupil_grid(G, na=na, device=device)
        pupil = ((fx**2 + fy**2) <= na**2).to(torch.complex128)
        mask_fft = torch.fft.fft2(torch.fft.fftshift(torch.randn(G, G, dtype=torch.complex128)))
        source = torch.zeros(G, G, dtype=torch.float64, device=device)

        result = chunked_abbe(mask_fft, source, fx, fy, pupil, na)
        assert result.shape == (G, G)
        assert result.sum() == 0.0
