"""Seed draws of the tiled stochastic chain (pipeline._draw_seeds_cpu).

_noisy_depth_map draws its tile seeds and its development-noise seed from the
run's generator. That generator lives on the simulation device, and
torch.randint(..., device="cpu") rejects a CUDA or MPS generator ("Expected a
'cpu' device type for generator"), so every tiled stochastic run on a GPU
crashed. The draw now runs on the generator's own device.
"""

from __future__ import annotations

import pytest
import torch

import euvsimulator.pipeline as P


def test_seed_draw_on_cpu_is_the_old_call():
    """On a CPU generator the helper gives the old draw bit for bit and
    advances the generator by the same amount, so seeded CPU runs and their
    goldens do not change.
    """
    g_old = torch.Generator(device="cpu")
    g_old.manual_seed(123)
    g_new = torch.Generator(device="cpu")
    g_new.manual_seed(123)
    old = torch.randint(0, 2**62, (5,), generator=g_old, device="cpu")
    new = P._draw_seeds_cpu(g_new, 5)
    assert torch.equal(old, new)
    assert new.device.type == "cpu"
    assert new.dtype == torch.int64
    assert torch.equal(torch.rand(3, generator=g_old), torch.rand(3, generator=g_new))


def _check_accelerator_generator(dev):
    g = torch.Generator(device=dev)
    g.manual_seed(7)
    seeds = P._draw_seeds_cpu(g, 4)
    assert seeds.device.type == "cpu"
    assert seeds.dtype == torch.int64
    assert tuple(seeds.shape) == (4,)
    assert int(seeds.min()) >= 0
    assert int(seeds.max()) < 2**62


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs a CUDA device")
def test_seed_draw_accepts_a_cuda_generator():
    _check_accelerator_generator("cuda")


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="needs an MPS device")
def test_seed_draw_accepts_an_mps_generator():
    _check_accelerator_generator("mps")
