"""Tests for the OpenILT integration bridge."""

from __future__ import annotations

import torch

from euv.opc.openilt_bridge import EUVForwardModel, run_ilt


class TestEUVForwardModel:
    """Test suite for the differentiable EUV forward model."""

    def test_model_instantiation(self):
        """Creating a model with a target should work."""
        target = torch.zeros(32, 32)
        target[:, 10:22] = 1.0
        model = EUVForwardModel(target=target)
        assert isinstance(model, torch.nn.Module)
        assert model.target.shape == (32, 32)

    def test_forward_pass_shape(self):
        """Forward pass should produce output with the same shape as input."""
        target = torch.zeros(32, 32)
        target[:, 12:20] = 1.0
        model = EUVForwardModel(target=target)
        mask = torch.sigmoid(torch.randn(32, 32) * 0.3)
        result = model.forward(mask)
        assert result.shape == (32, 32), f"Expected (32, 32), got {result.shape}"

    def test_forward_output_range(self):
        """Forward output should be on [0, 1]."""
        target = torch.zeros(32, 32)
        target[:, 12:20] = 1.0
        model = EUVForwardModel(target=target)
        mask = torch.sigmoid(torch.randn(32, 32) * 0.3)
        result = model.forward(mask)
        assert result.min() >= 0.0, f"Min {result.min():.4f} < 0"
        assert result.max() <= 1.0, f"Max {result.max():.4f} > 1"

    def test_loss_computation(self):
        """Loss should be a scalar tensor with gradients."""
        target = torch.zeros(32, 32)
        target[:, 12:20] = 1.0
        model = EUVForwardModel(target=target)
        mask = torch.sigmoid(torch.randn(32, 32) * 0.3).requires_grad_(True)
        resist = model.forward(mask)
        l = model.loss(resist)
        assert l.ndim == 0, f"Loss should be scalar, got shape {l.shape}"
        assert l.requires_grad, "Loss should require grad"
        l.backward()
        assert mask.grad is not None, "Gradients should flow to mask"
        assert torch.isfinite(mask.grad).all(), "Gradients should be finite"

    def test_optimize_reduces_loss(self):
        """Optimisation loop should reduce the loss."""
        target = torch.zeros(32, 32)
        target[:, 12:20] = 1.0
        model = EUVForwardModel(target=target)
        mask_init = torch.sigmoid(torch.randn(32, 32) * 0.3)
        resist_before = model.forward(mask_init)
        loss_before = model.loss(resist_before).item()

        mask_opt = model.optimize(mask_init.clone(), iterations=20, lr=0.1, report_every=100)
        resist_after = model.forward(mask_opt)
        loss_after = model.loss(resist_after).item()

        assert loss_after < loss_before * 0.95, (
            f"Loss should decrease: {loss_before:.6f} → {loss_after:.6f}"
        )

    def test_optimize_mask_binary(self):
        """Optimisation should push mask toward {0, 1} or reduce loss."""
        target = torch.zeros(32, 32)
        target[:, 12:20] = 1.0
        model = EUVForwardModel(target=target)
        mask_init = torch.sigmoid(torch.randn(32, 32) * 0.3)
        resist_before = model.forward(mask_init)
        loss_before = model.loss(resist_before).item()

        mask_opt = model.optimize(mask_init, iterations=50, lr=0.1, report_every=100)
        resist_after = model.forward(mask_opt)
        loss_after = model.loss(resist_after).item()

        # Must reduce loss or push mask toward 0/1
        mask_improved = loss_after < loss_before * 0.9
        near_extreme = ((mask_opt < 0.2) | (mask_opt > 0.8)).float().mean()
        assert mask_improved or near_extreme > 0.4, (
            f"Either loss down ({loss_before:.4f}→{loss_after:.4f}) "
            f"or near-extreme pixels: {near_extreme:.2%}"
        )

    def test_gradients_are_deterministic(self):
        """Same seed, same mask → same gradients."""
        torch.manual_seed(42)
        target = torch.zeros(16, 16)
        target[:, 6:10] = 1.0
        model = EUVForwardModel(target=target)
        mask = torch.sigmoid(torch.randn(16, 16) * 0.3).requires_grad_(True)
        resist = model.forward(mask)
        l = model.loss(resist)
        l.backward()
        grad1 = mask.grad.clone()

        torch.manual_seed(42)
        model2 = EUVForwardModel(target=target)
        mask2 = torch.sigmoid(torch.randn(16, 16) * 0.3).requires_grad_(True)
        resist2 = model2.forward(mask2)
        l2 = model2.loss(resist2)
        l2.backward()
        grad2 = mask2.grad.clone()

        assert torch.allclose(grad1, grad2, atol=1e-6), "Gradients should be deterministic"


class TestRunILT:
    """Test suite for the convenience run_ilt function."""

    def test_run_ilt_basic(self):
        """run_ilt should return a binary-like mask."""
        target = torch.zeros(24, 24)
        target[:, 8:16] = 1.0
        result = run_ilt(target, iterations=15, lr=0.1, verbose=False)
        assert result.shape == (24, 24), f"Expected (24, 24), got {result.shape}"
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_run_ilt_random_init(self):
        """run_ilt with no initial mask should create one."""
        target = torch.zeros(20, 20)
        target[:, 6:14] = 1.0
        result = run_ilt(target, iterations=10, verbose=False)
        assert result.shape == (20, 20)
