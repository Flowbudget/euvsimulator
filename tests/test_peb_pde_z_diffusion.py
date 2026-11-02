"""reaction_diffusion_pde: depth (z) diffusion with many small steps.

Before 2026-10-02 each step blurred along z with a sampled Gaussian of the
per-step sigma (0.75 nm = 0.3 dz at the defaults), which carries only 8.5 %
of the variance, and for sigma < dz/6 none at all. Reference: the exact
solution exp(D t / dz^2 * L) p0 of the flux-form Neumann depth diffusion.
Measured 2026-10-02 (21 layers): top 0.2905 before, 0.264480 after, exact
0.264480; 11 layers: top 0.300000 (unchanged) before, 0.266866 after.
"""

from __future__ import annotations

import pytest
import torch

from euvsimulator.resist.peb import reaction_diffusion_pde


def _neumann_laplacian(n: int) -> torch.Tensor:
    L = torch.zeros(n, n, dtype=torch.float64)
    for i in range(n - 1):
        L[i, i + 1] = 1.0
        L[i + 1, i] = 1.0
        L[i, i] -= 1.0
        L[i + 1, i + 1] -= 1.0
    return L


def _pure_z_diffusion(n_layers: int, dt: float | None = None):
    dz = 50.0 / (n_layers - 1)
    z = torch.arange(n_layers, dtype=torch.float64) * dz
    prof = 0.3 * torch.exp(-0.008 * z)  # Beer-Lambert, alpha = 8 per um
    h0 = prof.view(-1, 1, 1).expand(n_layers, 2, 8).clone()
    h, _, _ = reaction_diffusion_pde(
        h0,
        0.0,
        torch.ones_like(h0),
        D=4.2,
        k=0.0,
        k_trap=0.0,
        quench_rate=0.0,
        t_bake=60.0,
        dx=0.25,
        pag_density=0.2,
        dz=dz,
        dt=dt,
    )
    ref = torch.linalg.matrix_exp(4.2 * 60.0 / dz**2 * _neumann_laplacian(n_layers)) @ prof
    return h, ref, prof


@pytest.mark.parametrize("n_layers, top_exact", [(21, 0.264480), (11, 0.266866)])
def test_pde_depth_diffusion_matches_exact_neumann_solution(n_layers, top_exact):
    h, ref, prof = _pure_z_diffusion(n_layers)
    assert float(ref[0]) == pytest.approx(top_exact, abs=1e-6)
    for iy in range(2):
        for ix in range(8):
            assert torch.allclose(h[:, iy, ix], ref, rtol=0.0, atol=1e-8)
    assert float(h[:, 0, 0].sum()) == pytest.approx(float(prof.sum()), rel=1e-8)


def test_pde_depth_diffusion_does_not_depend_on_the_step():
    h_fine, _, _ = _pure_z_diffusion(21, dt=0.5)
    h_coarse, _, _ = _pure_z_diffusion(21, dt=3.0)
    assert torch.allclose(h_fine, h_coarse, rtol=0.0, atol=1e-9)
