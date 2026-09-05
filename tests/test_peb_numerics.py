"""PEB numerics: conservation properties of the diffusion operators.

1. ADI reaction-diffusion solver with zero-flux (Neumann) boundaries must
   conserve the total acid (k = 0) to round-off -- it created +0.14..+1.6 %
   before 2026-09-04 because the implicit and explicit half-steps used
   different-order boundary stencils (audit C1).
2. The depth (z) Gaussian blur of the unified PEB step must conserve the
   column total (mirror boundaries), tend to the depth average for σ much
   larger than the film, and be the identity for σ -> 0 / single layer.
3. With dz given, the diffusion is isotropic: a delta in a uniform field
   spreads along z with the same σ as laterally.
"""

import math

import pytest
import torch

from euvsimulator.resist.peb import (
    _gaussian_blur_z,
    reaction_diffusion_adi,
    reaction_diffusion_with_quenching,
)

torch.set_default_dtype(torch.float64)


@pytest.mark.parametrize("D, dt", [(5.0, 1.0), (20.0, 1.0), (2.0, 0.25)])
def test_adi_neumann_conserves_mass(D, dt):
    A0 = torch.zeros(48, 40)
    A0[16:32, 12:28] = 1.0
    M0 = torch.ones_like(A0)
    A, _ = reaction_diffusion_adi(A0, M0, D=D, k=0.0, dt=dt, n_steps=12, dx=1.0, boundary="neumann")
    assert float(A.sum()) == pytest.approx(float(A0.sum()), rel=1e-12)
    assert float(A.min()) >= -1e-12


def test_adi_dirichlet_loses_mass():
    A0 = torch.zeros(32, 32)
    A0[8:24, 8:24] = 1.0
    A, _ = reaction_diffusion_adi(
        A0, torch.ones_like(A0), D=20.0, k=0.0, dt=1.0, n_steps=12, dx=1.0, boundary="dirichlet"
    )
    assert float(A.sum()) < float(A0.sum())


def test_z_blur_conserves_column_total_and_averages():
    N, H, W = 21, 4, 5
    z = torch.linspace(0, 1, N).view(N, 1, 1)
    field = torch.exp(-1.06 * 0.05 * z).expand(N, H, W).clone()  # Beer-Lambert-like
    for sigma in (2.5, 10.0, 200.0):
        out = _gaussian_blur_z(field, sigma_nm=sigma, dz=2.5)
        assert torch.allclose(out.sum(dim=0), field.sum(dim=0), rtol=1e-12)
    flat = _gaussian_blur_z(field, sigma_nm=200.0, dz=2.5)
    assert float((flat - field.mean(dim=0, keepdim=True)).abs().max()) < 1e-3 * float(field.mean())


def test_z_blur_identity_limits():
    field = torch.rand(7, 3, 3)
    assert torch.equal(_gaussian_blur_z(field, sigma_nm=0.0, dz=2.5), field)
    single = torch.rand(1, 3, 3)
    out = reaction_diffusion_with_quenching(
        single,
        0.0,
        torch.ones_like(single),
        D=3.3,
        k=0.0723,
        quench_rate=15.0,
        t_bake=60.0,
        dx=0.25,
        pag_density=0.2,
        dz=2.5,
    )[2]
    ref = reaction_diffusion_with_quenching(
        single,
        0.0,
        torch.ones_like(single),
        D=3.3,
        k=0.0723,
        quench_rate=15.0,
        t_bake=60.0,
        dx=0.25,
        pag_density=0.2,
    )[2]
    assert torch.allclose(out, ref)


def test_peb_step_is_isotropic_with_dz():
    """A delta acid spike in the middle layer/pixel spreads with the same σ
    along z (dz units) and along x (dx units).
    """
    N, H, W, dx, dz = 161, 1, 201, 0.25, 0.25  # ±20 nm in z = 5 sigma: no boundary influence
    acid = torch.zeros(N, H, W)
    acid[N // 2, 0, W // 2] = 1.0
    sigma = 4.0
    h, _, _ = reaction_diffusion_with_quenching(
        acid,
        0.0,
        torch.ones_like(acid),
        D=0.0,
        k=0.0,
        quench_rate=0.0,
        t_bake=1.0,
        sigma_diff=sigma,
        dx=dx,
        pag_density=0.2,
        dz=dz,
    )
    prof_z = h[:, 0, W // 2]
    prof_x = h[N // 2, 0, :]
    zc = (torch.arange(N) - N // 2) * dz
    xc = (torch.arange(W) - W // 2) * dx
    sz = math.sqrt(float((prof_z * zc**2).sum() / prof_z.sum()))
    sx = math.sqrt(float((prof_x * xc**2).sum() / prof_x.sum()))
    assert sz == pytest.approx(sigma, rel=0.05)
    assert sx == pytest.approx(sigma, rel=0.05)
