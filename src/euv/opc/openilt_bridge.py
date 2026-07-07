"""OpenILT integration bridge — differentiable EUV forward model for ILT.

This module wraps the OpEnUV simulation pipeline as a differentiable
``torch.nn.Module`` so that OpenILT (or any gradient-based OPC loop)
can backpropagate through the mask → aerial → resist chain.

Usage
-----
The bridge is an **optional** dependency path — OpenILT itself is not
required to use OpEnUV.  When OpenILT is installed::

    from euv.opc.openilt_bridge import EUVForwardModel
    model = EUVForwardModel(target=target_contour)
    optimized_mask = model.optimize(initial_mask, iterations=100)

Reference
---------
OpenILT: https://github.com/OpenOPC/openilt
"""

from __future__ import annotations

from typing import Callable, Optional

import torch


class EUVForwardModel(torch.nn.Module):
    """Differentiable EUV forward model for inverse lithography (ILT).

    Wraps the OpEnUV simulation so that gradients flow from the resist
    contour back through development → PEB → exposure → aerial image
    → mask diffraction.

    Parameters
    ----------
    target : torch.Tensor
        Target binary resist contour ``(H, W)`` in {0, 1}.
    pipeline_fn : callable, optional
        A function ``mask_params → resist_contour`` compatible with
        ``euv.pipeline.run_simulation``.  Defaults to ``None`` (use
        the built-in forward pass).
    loss_fn : callable, optional
        Loss function between predicted and target resist.
        Default: mean-squared error.
    device : str
        PyTorch device.  Default ``"cpu"``.

    Examples
    --------
    >>> import torch
    >>> from euv.opc.openilt_bridge import EUVForwardModel
    >>> target = torch.zeros(64, 64)
    >>> target[:, 20:44] = 1.0  # 24 nm line in 64 nm pitch
    >>> model = EUVForwardModel(target=target)
    >>> mask_init = torch.sigmoid(torch.randn(64, 64) * 0.5)
    >>> result = model.optimize(mask_init, iterations=20)
    """

    def __init__(
        self,
        target: torch.Tensor,
        pipeline_fn: Optional[Callable] = None,
        loss_fn: Optional[Callable] = None,
        device: str = "cpu",
    ):
        super().__init__()
        self.target = target.to(device)
        self.device = device
        self._pipeline_fn = pipeline_fn
        self._loss_fn = loss_fn or torch.nn.functional.mse_loss

        # Cache the last simulation result
        self._last_result = None

    def forward(self, mask_params: torch.Tensor) -> torch.Tensor:
        """Run the differentiable EUV simulation.

        Parameters
        ----------
        mask_params : torch.Tensor
            Relaxed mask parameters ``(H, W)`` in ℝ (will be sigmoid-clipped
            to [0, 1] internally).  Values near 0 = absorber, 1 = clear.

        Returns
        -------
        resist_contour : torch.Tensor
            Binary-like resist contour ``(H, W)`` on [0, 1].
        """
        # Relax mask to [0, 1]
        mask = torch.sigmoid(mask_params)

        if self._pipeline_fn is not None:
            result = self._pipeline_fn(mask)
        else:
            result = self._default_forward(mask)

        self._last_result = result
        return result

    def _default_forward(self, mask: torch.Tensor) -> torch.Tensor:
        """Built-in differentiable forward pass.

        Uses a simplified but differentiable path:
        mask → FFT → pupil filter → aerial → sigmoid resist.
        This is a thin-mask approximation (Kirchhoff) for fast ILT
        iterations.  For rigorous M3D, provide a custom ``pipeline_fn``.
        """
        from euv.aerial.abbe import abbe_image
        from euv.aerial.pupil import pupil_grid
        from euv.aerial.source import conventional

        H, W = mask.shape
        grid = max(H, W)

        # Pad to square grid
        padded = torch.zeros(grid, grid, device=self.device)
        y0, x0 = (grid - H) // 2, (grid - W) // 2
        padded[y0 : y0 + H, x0 : x0 + W] = mask

        # Mask FFT
        mask_fft = torch.fft.fft2(padded.to(torch.complex128))
        mask_fft = torch.fft.fftshift(mask_fft)

        # Source + pupil
        source = conventional(grid, sigma=0.8, device=self.device)
        fx, fy, inside = pupil_grid(grid, na=0.33, device=self.device)
        pupil = inside.to(torch.float64).to(torch.complex128)

        # Abbe imaging
        aerial = abbe_image(mask_fft, source, fx, fy, pupil, na=0.33)
        aerial = aerial / (aerial.max() + 1e-12)

        # Simplified resist: sigmoid with threshold
        resist = torch.sigmoid(10.0 * (aerial - 0.3))

        # Crop back to original size
        return resist[y0 : y0 + H, x0 : x0 + W]

    def loss(self, resist_contour: torch.Tensor) -> torch.Tensor:
        """Compute the ILT loss between predicted and target resist.

        Parameters
        ----------
        resist_contour : torch.Tensor
            Predicted resist contour from ``forward()``.

        Returns
        -------
        loss : torch.Tensor
            Scalar loss value (differentiable).
        """
        return self._loss_fn(resist_contour, self.target)

    def optimize(
        self,
        initial_mask: torch.Tensor,
        iterations: int = 100,
        lr: float = 0.05,
        report_every: int = 10,
    ) -> torch.Tensor:
        """Run a gradient-descent ILT optimisation loop.

        Parameters
        ----------
        initial_mask : torch.Tensor
            Initial mask parameters ``(H, W)``.
        iterations : int
            Number of gradient descent steps.  Default 100.
        lr : float
            Learning rate.  Default 0.05.
        report_every : int
            Log loss every N iterations.  Default 10.

        Returns
        -------
        optimized_mask : torch.Tensor
            Binary mask in {0, 1} after optimisation.
        """
        mask = initial_mask.clone().to(self.device).requires_grad_(True)
        optimiser = torch.optim.Adam([mask], lr=lr)

        for it in range(iterations):
            optimiser.zero_grad()
            resist = self.forward(mask)
            loss_val = self.loss(resist)
            loss_val.backward()
            optimiser.step()

            if (it + 1) % report_every == 0:
                print(f"  ILT iter {it + 1:4d}/{iterations}: loss = {loss_val.item():.6e}")

        return torch.sigmoid(mask).detach()


def run_ilt(
    target_contour: torch.Tensor,
    initial_mask: Optional[torch.Tensor] = None,
    iterations: int = 100,
    lr: float = 0.05,
    verbose: bool = True,
) -> torch.Tensor:
    """Convenience function: run ILT on a target contour.

    Parameters
    ----------
    target_contour : torch.Tensor
        Target resist contour ``(H, W)``.
    initial_mask : torch.Tensor, optional
        Initial mask guess.  Default: random.
    iterations : int
        Number of ILT iterations.  Default 100.
    lr : float
        Learning rate.  Default 0.05.
    verbose : bool
        Print progress.

    Returns
    -------
    mask : torch.Tensor
        Optimised binary mask.
    """
    H, W = target_contour.shape
    model = EUVForwardModel(target=target_contour)

    if initial_mask is None:
        initial_mask = torch.sigmoid(torch.randn(H, W) * 0.3)

    if verbose:
        print(f"Running ILT: {iterations} iterations, lr={lr}, device={model.device}")
        print(f"  Target shape: {target_contour.shape}")

    return model.optimize(
        initial_mask, iterations=iterations, lr=lr, report_every=10 if verbose else iterations + 1
    )
