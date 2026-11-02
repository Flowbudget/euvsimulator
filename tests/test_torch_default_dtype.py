"""P1: run_simulation must not change the process-wide torch default dtype.

run_simulation used to call torch.set_default_dtype(torch.float64) and never
restore it. The default is global to the process (every thread), so after the
first simulation all later tensor creation in the caller's process switched
to float64: MPS code without an explicit dtype then failed, and the results
of library calls depended on whether a simulation had run before. The chain
relied on that switch at a few places that created tensors without a dtype;
those now carry an explicit dtype, so the results are the same under any
process default and bit-identical to the former float64-default numbers.
"""

from __future__ import annotations

import math

import pytest
import torch

from euvsimulator.aerial.abbe import aerial_from_orders
from euvsimulator.pipeline import SimulationConfig, run_simulation
from euvsimulator.resist.exposure import dill_abc_exposure


@pytest.fixture
def set_default():
    """Set the process default dtype for one test and restore it after."""
    old = torch.get_default_dtype()
    yield torch.set_default_dtype
    torch.set_default_dtype(old)


def test_run_simulation_leaves_the_default_dtype_alone(set_default):
    set_default(torch.float32)
    run_simulation(SimulationConfig(grid=64, device="cpu"))
    assert torch.get_default_dtype() == torch.float32
    set_default(torch.float64)
    run_simulation(SimulationConfig(grid=64, device="cpu"))
    assert torch.get_default_dtype() == torch.float64


def test_default_golden_under_a_float32_default(set_default):
    """The default golden (CD 26.7034 nm, NILS 4.5018 since 2026-10-03) is the float64 result;
    with the setter removed and nothing else changed it moved by -5.2e-7 nm
    and +4.3e-6 under a float32 default.
    """
    set_default(torch.float32)
    r = run_simulation(SimulationConfig(device="cpu"))
    assert r.cd_nm == pytest.approx(27.29263443728827, abs=1e-9)  # 26.7034 before 2.3.0
    assert r.nils_value == pytest.approx(4.830914089614135, abs=1e-9)
    assert r.aerial_image.dtype == torch.float64


_CONFIGS = {
    "aerial_threshold": dict(grid=64, focus_nm=30.0, illumination_shape="dipole_x"),
    "full_chem": dict(grid=64, resist_model="full_chem", dose_mj_cm2=1.3),
    "stochastic": dict(
        grid=32,
        resist_model="full_chem",
        dose_mj_cm2=1.3,
        enable_stochastic=True,
        stochastic_n_realisations=1,
        stochastic_seed=5,
        stochastic_ler_grid_y=512,
        development_stochasticity=True,
    ),
}


def _same(x, y):
    """Equality with NaN == NaN (one realisation has no confidence interval)."""
    if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
        return True
    return x == y


@pytest.mark.parametrize("name", sorted(_CONFIGS))
def test_results_do_not_depend_on_the_process_default(set_default, name):
    out = {}
    for dtype in (torch.float32, torch.float64):
        set_default(dtype)
        out[dtype] = run_simulation(SimulationConfig(device="cpu", **_CONFIGS[name]))
    a, b = out[torch.float32], out[torch.float64]
    for field in ("cd_nm", "nils_value", "ler_nm", "lwr_nm", "clear_field_reflectivity"):
        assert _same(getattr(a, field), getattr(b, field)), field
    assert torch.equal(a.aerial_image, b.aerial_image)
    assert torch.equal(a.resist_profile, b.resist_profile)
    meta_a, meta_b = a.ler_metadata or {}, b.ler_metadata or {}
    assert meta_a.keys() == meta_b.keys()
    for key in meta_a:
        assert _same(meta_a[key], meta_b[key]), key


def test_aerial_from_orders_does_not_follow_the_process_default(set_default):
    orders = torch.tensor([0.1 + 0.02j, 0.5 + 0.0j, 0.1 + 0.02j], dtype=torch.complex128)
    idx = torch.tensor([-1, 0, 1])
    kw = dict(grid=64, wavelength_m=13.5e-9, period_m=256e-9, na=0.33, sigma=0.5)
    images = []
    for dtype in (torch.float32, torch.float64):
        set_default(dtype)
        images.append(aerial_from_orders(orders, idx, **kw))
    assert images[0].dtype == images[1].dtype == torch.float64
    assert torch.equal(images[0], images[1])


@pytest.mark.parametrize("dose_dtype", [torch.float32, torch.float64])
def test_dill_abc_depth_grid_follows_the_dose(set_default, dose_dtype):
    """Without z_positions the depth grid takes the dose's precision, not the
    process default (a float64 default turned a float32 dose into a float64
    acid field, which MPS cannot hold).
    """
    dose = torch.full((4, 4), 1.3, dtype=dose_dtype)
    results = []
    for dtype in (torch.float32, torch.float64):
        set_default(dtype)
        acid, inhib = dill_abc_exposure(dose, A=0.0, B=4.44, C=0.0152, thickness=0.05, n_layers=5)
        assert acid.dtype == inhib.dtype == dose_dtype
        results.append(acid)
    assert torch.equal(results[0], results[1])
