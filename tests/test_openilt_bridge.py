"""Tests for the OpenILT integration bridge.

The built-in forward pass is thin-mask Abbe imaging (NA 0.33, sigma 0.8,
13.5 nm) on the target's pixel grid.  Grids here use 2-4 nm pixels so that the
pupil spans more than one FFT pixel; at 1 nm on 32 px only the zero frequency
passes (the model warns).  Until 2026-09-25 the pixel size was fixed at 64 nm,
so nothing was filtered, and the optimised mask was evaluated through a second
sigmoid.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.opc.openilt_bridge import EUVForwardModel, run_ilt


def _line_target(grid: int, lo: int, hi: int) -> torch.Tensor:
    target = torch.zeros(grid, grid)
    target[:, lo:hi] = 1.0
    return target


class TestEUVForwardModel:
    """Test suite for the differentiable EUV forward model."""

    def test_model_instantiation(self):
        """Creating a model with a target should work."""
        model = EUVForwardModel(target=_line_target(32, 10, 22), pixel_nm=2.0)
        assert isinstance(model, torch.nn.Module)
        assert model.target.shape == (32, 32)

    def test_forward_pass_shape_and_range(self):
        """Forward maps (H, W) logits to a resist contour on [0, 1]."""
        torch.manual_seed(0)
        model = EUVForwardModel(target=_line_target(32, 8, 24), pixel_nm=2.0)
        result = model.forward(torch.randn(32, 32) * 0.3)
        assert result.shape == (32, 32)
        assert result.min() >= 0.0 and result.max() <= 1.0

    def test_resolution_limit(self):
        """A 64 nm pitch prints, an 8 nm pitch (beyond (1+σ)·NA/λ) does not."""
        grid = 64
        x = torch.arange(grid)
        model = EUVForwardModel(target=torch.zeros(grid, grid), pixel_nm=1.0)

        def resist_range(pitch_px: int) -> float:
            mask = ((x % pitch_px) < pitch_px // 2).double().unsqueeze(0).expand(grid, grid)
            r = model.resist_from_mask(mask.clone())
            return (r.max() - r.min()).item()

        assert resist_range(64) > 0.5  # measured 0.94
        assert resist_range(8) < 1e-6  # measured 0: uniform image

    def test_under_resolved_grid_warns(self):
        model = EUVForwardModel(target=_line_target(32, 12, 20), pixel_nm=1.0)
        with pytest.warns(UserWarning, match="under-resolved"):
            model.forward(torch.zeros(32, 32))

    def test_loss_computation(self):
        """Loss is a scalar with finite gradients on the mask parameters."""
        torch.manual_seed(0)
        model = EUVForwardModel(target=_line_target(32, 8, 24), pixel_nm=2.0)
        params = (torch.randn(32, 32) * 0.3).requires_grad_(True)
        loss = model.loss(model.forward(params))
        assert loss.ndim == 0 and loss.requires_grad
        loss.backward()
        assert params.grad is not None and torch.isfinite(params.grad).all()

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_optimize_reduces_loss(self, seed):
        """20 Adam steps cut the loss of the returned mask at least in half.

        Measured 0.50 -> 0.08-0.09.  The mask is evaluated with
        resist_from_mask, i.e. without a second sigmoid.
        """
        torch.manual_seed(seed)
        model = EUVForwardModel(target=_line_target(32, 8, 24), pixel_nm=2.0)
        params = torch.randn(32, 32) * 0.3
        loss_before = model.loss(model.forward(params)).item()

        mask_opt = model.optimize(params.clone(), iterations=20, lr=0.1, report_every=100)
        loss_after = model.loss(model.resist_from_mask(mask_opt)).item()

        assert 0.0 <= mask_opt.min() and mask_opt.max() <= 1.0
        assert loss_after < 0.5 * loss_before, f"{loss_before:.4f} -> {loss_after:.4f}"

    def test_gradients_are_deterministic(self):
        """Same seed, same mask → same gradients."""
        grads = []
        for _ in range(2):
            torch.manual_seed(42)
            model = EUVForwardModel(target=_line_target(16, 4, 12), pixel_nm=4.0)
            params = (torch.randn(16, 16) * 0.3).requires_grad_(True)
            model.loss(model.forward(params)).backward()
            grads.append(params.grad.clone())
        assert torch.equal(grads[0], grads[1])


class TestRunILT:
    """Test suite for the convenience run_ilt function."""

    def test_run_ilt_basic(self):
        """run_ilt returns a continuous mask on [0, 1] that fits the target."""
        torch.manual_seed(0)
        target = _line_target(16, 4, 12)
        mask = run_ilt(target, iterations=15, lr=0.1, verbose=False, pixel_nm=4.0)
        assert mask.shape == (16, 16)
        assert mask.min() >= 0.0 and mask.max() <= 1.0
        model = EUVForwardModel(target=target, pixel_nm=4.0)
        assert model.loss(model.resist_from_mask(mask)).item() < 0.3

    def test_run_ilt_random_init(self):
        """run_ilt with no initial mask should create one."""
        torch.manual_seed(1)
        result = run_ilt(_line_target(16, 4, 12), iterations=10, verbose=False, pixel_nm=4.0)
        assert result.shape == (16, 16)
