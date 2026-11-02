"""Regression guard: the default time step of reaction_diffusion_pde.

The code chooses dt = min(t_bake / 20, (3 dx)^2 / (2 D)), i.e. a per-step
lateral diffusion sigma sqrt(2 D dt) of AT MOST 3 grid cells. Until 2026-10
the docstring said the opposite ("sigma is >= 3 grid cells").
"""

from __future__ import annotations

import pytest
import torch

import euvsimulator.resist.exposure as exposure
from euvsimulator.resist.peb import reaction_diffusion_pde


def test_default_step_sigma_is_at_most_three_lateral_cells(monkeypatch):
    sigmas: list[float] = []
    blur = exposure.gaussian_se_blur

    def recording_blur(field, sigma, dx):
        sigmas.append(float(sigma))
        return blur(field, sigma=sigma, dx=dx)

    monkeypatch.setattr(exposure, "gaussian_se_blur", recording_blur)
    dx = 1.0
    h0 = torch.full((2, 8), 0.1, dtype=torch.float64)
    reaction_diffusion_pde(
        h0,
        0.0,
        torch.ones_like(h0),
        D=4.2,
        k=1.0,
        k_trap=0.0,
        quench_rate=0.0,
        t_bake=60.0,
        dx=dx,
        pag_density=0.2,
    )
    assert sigmas, "the lateral blur was never called"
    # (3 dx)^2 / (2 D) = 1.07 s < t_bake / 20 = 3 s: the step is set by the 3-cell limit
    assert max(sigmas) <= 3.0 * dx + 1e-12
    assert max(sigmas) == pytest.approx(3.0 * dx, rel=0.05)


def test_docstring_states_the_same_inequality_as_the_code():
    doc = " ".join((reaction_diffusion_pde.__doc__ or "").split())
    assert ">= 3 grid cells" not in doc
    assert "sqrt(2 D dt) <= 3 dx" in doc
