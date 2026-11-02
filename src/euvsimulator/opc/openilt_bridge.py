"""OpenILT integration bridge — differentiable EUV forward model for ILT.

This module wraps the euvsimulator simulation pipeline as a differentiable
``torch.nn.Module`` so that OpenILT (or any gradient-based OPC loop)
can backpropagate through the mask → aerial → resist chain.

Usage
-----
The bridge is an **optional** dependency path — OpenILT itself is not
required to use euvsimulator.  When OpenILT is installed::

    from euvsimulator.opc.openilt_bridge import EUVForwardModel
    model = EUVForwardModel(target=target_contour)
    optimized_mask = model.optimize(initial_mask, iterations=100)

Reference
---------
OpenILT: https://github.com/OpenOPC/openilt
"""

from __future__ import annotations

import warnings
from typing import Callable, Optional

import torch


class EUVForwardModel(torch.nn.Module):
    """Differentiable EUV forward model for inverse lithography (ILT).

    The built-in forward pass is thin-mask Abbe imaging followed by a sigmoid
    threshold resist, so gradients flow resist → aerial image → mask.  (A
    full development → PEB → exposure chain needs a custom *pipeline_fn*.)

    Parameters
    ----------
    target : torch.Tensor
        Target binary resist contour ``(H, W)`` in {0, 1}.
    pipeline_fn : callable, optional
        A function ``mask_params → resist_contour`` compatible with
        ``euvsimulator.pipeline.run_simulation``.  Defaults to ``None`` (use
        the built-in forward pass).
    loss_fn : callable, optional
        Loss function between predicted and target resist.
        Default: mean-squared error.
    device : str
        PyTorch device.  Default ``"cpu"``.
    pixel_nm : float
        Wafer-scale pixel size of *target* and the mask [nm].  Default 1.0.
        Sets the optical scale: the pupil passes spatial frequencies up to
        NA/λ, source points shift by up to σ·NA/λ.
    na, sigma, wavelength_nm : float
        Numerical aperture (0.33), conventional partial coherence (0.8) and
        wavelength (13.5 nm) of the built-in forward pass.

    Examples
    --------
    >>> import torch
    >>> from euvsimulator.opc.openilt_bridge import EUVForwardModel
    >>> target = torch.zeros(64, 64)
    >>> target[:, 20:44] = 1.0  # 24 nm line in 64 nm pitch
    >>> model = EUVForwardModel(target=target)
    >>> params_init = torch.randn(64, 64) * 0.5  # mask parameters (logits)
    >>> mask = model.optimize(params_init, iterations=20)  # continuous mask on [0, 1]
    """

    def __init__(
        self,
        target: torch.Tensor,
        pipeline_fn: Optional[Callable] = None,
        loss_fn: Optional[Callable] = None,
        device: str = "cpu",
        pixel_nm: float = 1.0,
        na: float = 0.33,
        sigma: float = 0.8,
        wavelength_nm: float = 13.5,
    ):
        super().__init__()
        self.target = target.to(device)
        self.device = device
        self.pixel_nm = pixel_nm
        self.na = na
        self.sigma = sigma
        self.wavelength_nm = wavelength_nm
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
        return self.resist_from_mask(torch.sigmoid(mask_params))

    def resist_from_mask(self, mask: torch.Tensor) -> torch.Tensor:
        """Resist contour for a mask already on [0, 1] (no sigmoid applied).

        Use this to evaluate the mask returned by :meth:`optimize`; passing
        that mask to :meth:`forward` would apply the sigmoid a second time.
        """
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
        from euvsimulator.aerial.abbe import abbe_image
        from euvsimulator.aerial.pupil import pupil_grid
        from euvsimulator.aerial.source import conventional

        H, W = mask.shape
        grid = max(H, W)
        # Pupil radius in FFT pixels: below ~1 only the zero frequency passes
        # and the image carries no information about the mask.
        radius_px = self.na / self.wavelength_nm * self.pixel_nm * grid
        if radius_px < 1.0:
            warnings.warn(
                f"optics under-resolved: pupil radius {radius_px:.2f} FFT pixels "
                f"(grid {grid} x {self.pixel_nm} nm); use a larger grid or pixel_nm",
                stacklevel=3,
            )

        # Pad to square grid
        padded = torch.zeros(grid, grid, device=self.device)
        y0, x0 = (grid - H) // 2, (grid - W) // 2
        padded[y0 : y0 + H, x0 : x0 + W] = mask

        # Mask FFT
        mask_fft = torch.fft.fft2(padded.to(torch.complex128))
        mask_fft = torch.fft.fftshift(mask_fft)

        # Source + pupil
        source = conventional(grid, sigma=self.sigma, device=self.device)
        fx, fy, inside = pupil_grid(grid, na=self.na, device=self.device)
        pupil = inside.to(torch.float64).to(torch.complex128)

        # Abbe imaging.  abbe_image takes the pixel size as period_m (its FFT
        # spacing is 1/(period_m * G)).  Before 2026-09-25 the default 64 nm
        # was used whatever the target's pixel size, which put the pupil
        # outside the grid: no optical filtering at all.
        aerial = abbe_image(
            mask_fft,
            source,
            fx,
            fy,
            pupil,
            na=self.na,
            period_m=self.pixel_nm * 1e-9,
            wavelength_m=self.wavelength_nm * 1e-9,
        )
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
            Initial mask parameters ``(H, W)`` in ℝ (logits, as for
            :meth:`forward`).
        iterations : int
            Number of gradient descent steps.  Default 100.
        lr : float
            Learning rate.  Default 0.05.
        report_every : int
            Log loss every N iterations.  Default 10.

        Returns
        -------
        optimized_mask : torch.Tensor
            Continuous mask on [0, 1], the sigmoid of the optimised
            parameters; threshold at 0.5 for a binary mask.  Evaluate it with
            :meth:`resist_from_mask`.
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
    pixel_nm: float = 1.0,
) -> torch.Tensor:
    """Convenience function: run ILT on a target contour.

    Parameters
    ----------
    target_contour : torch.Tensor
        Target resist contour ``(H, W)``.
    initial_mask : torch.Tensor, optional
        Initial mask parameters (logits).  Default: random, N(0, 0.3²).
    iterations : int
        Number of ILT iterations.  Default 100.
    lr : float
        Learning rate.  Default 0.05.
    verbose : bool
        Print progress.
    pixel_nm : float
        Pixel size of *target_contour* [nm], see :class:`EUVForwardModel`.

    Returns
    -------
    mask : torch.Tensor
        Optimised continuous mask on [0, 1] (see :meth:`EUVForwardModel.optimize`).
    """
    H, W = target_contour.shape
    model = EUVForwardModel(target=target_contour, pixel_nm=pixel_nm)

    if initial_mask is None:
        initial_mask = torch.randn(H, W) * 0.3

    if verbose:
        print(f"Running ILT: {iterations} iterations, lr={lr}, device={model.device}")
        print(f"  Target shape: {target_contour.shape}")

    return model.optimize(
        initial_mask, iterations=iterations, lr=lr, report_every=10 if verbose else iterations + 1
    )
