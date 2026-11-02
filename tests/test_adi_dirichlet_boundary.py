"""reaction_diffusion_adi, boundary='dirichlet': the explicit half-step must
use the same ghost-zero boundary as the implicit one.

For k = 0 Peaceman-Rachford ADI on a square grid is exactly
A_n = C^n A_0 (C^n)^T with C = (I - a L)^-1 (I + a L), a = D dt / (2 dx^2)
and L the ghost-zero tridiagonal [1, -2, 1]. Before 2026-10-02 the explicit
boundary rows dropped the neighbour term (max deviation 0.20 from this
reference); the physics reference exp(D t L) gives edge 0.2491, corner
0.0620, total 834.6 (the old code: 0.0878, 0.0040, 771.9).
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.peb import reaction_diffusion_adi


def _dirichlet_laplacian(n: int) -> torch.Tensor:
    return (
        torch.diag(torch.full((n,), -2.0, dtype=torch.float64))
        + torch.diag(torch.ones(n - 1, dtype=torch.float64), 1)
        + torch.diag(torch.ones(n - 1, dtype=torch.float64), -1)
    )


def test_adi_dirichlet_matches_the_peaceman_rachford_product():
    n, D, dt, steps = 33, 1.0, 0.5, 10
    U = torch.ones(n, n, dtype=torch.float64)
    A, _ = reaction_diffusion_adi(
        U, torch.ones_like(U), D=D, k=0.0, dt=dt, n_steps=steps, dx=1.0, boundary="dirichlet"
    )
    L = _dirichlet_laplacian(n)
    a = D * dt / 2.0
    eye = torch.eye(n, dtype=torch.float64)
    C = torch.linalg.matrix_power(torch.linalg.solve(eye - a * L, eye + a * L), steps)
    assert torch.allclose(A, C @ U @ C.T, rtol=0.0, atol=1e-12)


def test_adi_dirichlet_is_close_to_the_exact_solution():
    n, D, dt, steps = 33, 1.0, 0.5, 10
    U = torch.ones(n, n, dtype=torch.float64)
    A, _ = reaction_diffusion_adi(
        U, torch.ones_like(U), D=D, k=0.0, dt=dt, n_steps=steps, dx=1.0, boundary="dirichlet"
    )
    E = torch.linalg.matrix_exp(D * dt * steps * _dirichlet_laplacian(n))
    exact = E @ U @ E.T
    assert float(A[0, 16]) == pytest.approx(float(exact[0, 16]), abs=0.01)
    assert float(A[0, 0]) == pytest.approx(float(exact[0, 0]), abs=0.01)
    assert float(A.sum()) == pytest.approx(float(exact.sum()), rel=0.01)
    assert float(A.min()) > 0.0
