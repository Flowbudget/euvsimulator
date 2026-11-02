"""reaction_diffusion_adi on a strip of shape (1, W) or (H, 1).

Before 2026-10-02 _build_tridiagonal_matrix wrote T[0, 1] for n = 1 and the
explicit Laplacians read A[1], so any size-1 axis raised IndexError. With
Neumann boundaries the strip is a 1D problem and Peaceman-Rachford reduces
to Crank-Nicolson: A_n = C^n A_0, C = (I - a L)^-1 (I + a L), a = D dt / 2,
L the flux-form Neumann Laplacian.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.peb import reaction_diffusion_adi


def _neumann_laplacian(n: int) -> torch.Tensor:
    L = torch.zeros(n, n, dtype=torch.float64)
    for i in range(n - 1):
        L[i, i + 1] = 1.0
        L[i + 1, i] = 1.0
        L[i, i] -= 1.0
        L[i + 1, i + 1] -= 1.0
    return L


def _strip() -> torch.Tensor:
    g = torch.Generator().manual_seed(0)
    return torch.rand(1, 16, generator=g, dtype=torch.float64)


def _crank_nicolson(a0: torch.Tensor) -> torch.Tensor:
    a = 2.0 * 1.0 / 2.0  # D dt / (2 dx^2) with D 2, dt 1, dx 1
    eye = torch.eye(16, dtype=torch.float64)
    L = _neumann_laplacian(16)
    C = torch.linalg.matrix_power(torch.linalg.solve(eye - a * L, eye + a * L), 4)
    return C @ a0


def test_adi_row_strip_neumann_is_crank_nicolson():
    a0 = _strip()
    out, _ = reaction_diffusion_adi(
        a0, torch.ones_like(a0), D=2.0, k=0.0, dt=1.0, n_steps=4, dx=1.0
    )
    assert out.shape == (1, 16)
    assert torch.allclose(out[0], _crank_nicolson(a0[0]), rtol=0.0, atol=1e-12)
    assert float(out.sum()) == pytest.approx(float(a0.sum()), rel=1e-12)


def test_adi_column_strip_neumann_is_crank_nicolson():
    a0 = _strip()
    col = a0.T.contiguous()  # shape (16, 1)
    out, _ = reaction_diffusion_adi(
        col, torch.ones_like(col), D=2.0, k=0.0, dt=1.0, n_steps=4, dx=1.0
    )
    assert out.shape == (16, 1)
    assert torch.allclose(out[:, 0], _crank_nicolson(a0[0]), rtol=0.0, atol=1e-12)


def test_adi_strip_dirichlet_runs_and_loses_mass():
    a0 = _strip()
    out, _ = reaction_diffusion_adi(
        a0, torch.ones_like(a0), D=2.0, k=0.0, dt=1.0, n_steps=4, dx=1.0, boundary="dirichlet"
    )
    assert torch.isfinite(out).all()
    assert float(out.sum()) < float(a0.sum())
