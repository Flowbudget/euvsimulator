"""Validation tests against the independent reference model.

These tests verify that OpEnUV's NILS computation matches the
independent numpy/scipy reference model (reference_model.py) which
implements the standard Hopkins imaging theory with correct TCC
(2*J1(x)/x for circular source) and identical pupil/coherence cutoffs.

Run with: pytest tests/test_reference_nils.py -v
"""

import pytest
import torch
import math
import sys
sys.path.insert(0, "/Users/pi-server/OpEnUV")

from euv.aerial.abbe import aerial_from_orders, nils as op_nils
from reference_model import (
    aerial_image as ref_aerial_image,
    nils_from_image as ref_nils,
)


# ──────────────────────────────────────────────
# Common EUV setup (identical TMM inputs)
# ──────────────────────────────

def _setup_euv_tmm():
    """Build the same TMM reflectivities used by OpEnUV."""
    from euv.materials import CXROTable
    from euv.optics.multilayer import mo_si_stack
    from euv.optics.tmm import reflectivity
    import torch
    import math

    table = CXROTable()
    theta0 = torch.tensor(math.radians(6.0))
    wl_t = torch.tensor([13.5e-9])
    n_si, k_si = table.refractive_index("Si", 91.84)
    n_sub = torch.tensor(complex(n_si, k_si))
    ml = mo_si_stack(n_bilayers=50, d_mo_nm=2.8, d_si_nm=4.1,
                     capping_layer="Ru", d_cap_nm=2.5)
    _, r_space = reflectivity(ml.n_layers, ml.thicknesses, wl_t, theta0,
                              n_substrate=n_sub)
    n_ta, k_ta = table.refractive_index("Ta", 91.84)
    n_abs = torch.tensor(complex(n_ta, k_ta))
    d_abs = torch.tensor([60e-9])
    full_n = torch.cat([n_abs.unsqueeze(0), ml.n_layers])
    full_d = torch.cat([d_abs, ml.thicknesses])
    _, r_ab = reflectivity(full_n, full_d, wl_t, theta0, n_substrate=n_sub)
    a = complex(r_ab[0])
    b = complex(r_space[0])
    return a, b


def _build_orders(a: complex, b: complex, duty: float = 0.5,
                  n_orders: int = 21, period_nm: float = 64.0,
                  na: float = 0.33, wavelength_nm: float = 13.5):
    """Build diffraction orders and apply pupil cutoff (matching OpEnUV)."""
    import numpy as np
    import math

    period_m = period_nm * 1e-9
    wl_m = wavelength_nm * 1e-9
    max_order = int(math.floor(na * period_m / wl_m))

    # Build orders like OpEnUV
    oi = list(range(-n_orders, n_orders + 1))
    amps = []
    for m in oi:
        if m == 0:
            amps.append(a * duty + b * (1 - duty))
        else:
            amps.append((a - b) * math.sin(math.pi * m * duty) / (math.pi * m))

    # Apply pupil cutoff (same as OpEnUV)
    oi_p = [m for m in oi if abs(m) <= max_order]
    amps_p = [amps[i] for i, m in enumerate(oi) if abs(m) <= max_order]

    return oi_p, amps_p, max_order


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────

def test_nils_blur_zero_matches_reference():
    """OpEnUV NILS at blur=0 must match reference model (diff < 0.3)."""
    a, b = _setup_euv_tmm()
    oi_p, amps_p, max_order = _build_orders(a, b)
    assert max_order == 1, "For 64nm/NA=0.33 only 0,±1 should pass pupil"

    period_m = 64e-9
    na = 0.33
    wl_m = 13.5e-9
    sigma = 0.8
    grid = 512
    dose = 20.0

    # OpEnUV
    amps_t = torch.tensor(amps_p, dtype=torch.complex128)
    oi_t = torch.tensor(oi_p, dtype=torch.int64)
    ae = aerial_from_orders(
        amps_t, oi_t,
        period_m=period_m, na=na, wavelength_m=wl_m,
        sigma=sigma, illumination_shape="conventional",
        grid=grid, se_blur_nm=0.0,
    )
    ae = ae * dose
    half = grid // 2
    lw = 256
    dx = period_m / grid * 1e9
    n_op = op_nils(ae, half, lw, dx)

    # Reference (same pupil/coherence cutoffs, correct TCC)
    import numpy as np
    m_np = np.array(oi_p, dtype=int)
    a_np = np.array(amps_p, dtype=complex)
    Iref = ref_aerial_image(
        m_np, a_np, 64.0, sigma, na, 13.5, grid,
        dose_mj_cm2=dose, sigma_blur_nm=0.0,
    )
    n_ref = ref_nils(Iref, 64.0, grid)

    # OpEnUV uses |dI/dx|, reference uses signed slope -> compare abs
    diff = abs(n_op - abs(n_ref))
    assert diff < 0.3, f"NILS diff={diff:.3f} > 0.3 (OpEnUV={n_op:.3f}, Ref={n_ref:.3f})"


def test_nils_blur_10nm_matches_reference():
    """OpEnUV NILS at blur=10nm must match reference model (diff < 0.3)."""
    a, b = _setup_euv_tmm()
    oi_p, amps_p, max_order = _build_orders(a, b)

    period_m = 64e-9
    na = 0.33
    wl_m = 13.5e-9
    sigma = 0.8
    grid = 512
    dose = 20.0

    # OpEnUV
    amps_t = torch.tensor(amps_p, dtype=torch.complex128)
    oi_t = torch.tensor(oi_p, dtype=torch.int64)
    ae = aerial_from_orders(
        amps_t, oi_t,
        period_m=period_m, na=na, wavelength_m=wl_m,
        sigma=sigma, illumination_shape="conventional",
        grid=grid, se_blur_nm=10.0,
    )
    ae = ae * dose
    half = grid // 2
    lw = 256
    dx = period_m / grid * 1e9
    n_op = op_nils(ae, half, lw, dx)

    # Reference
    import numpy as np
    m_np = np.array(oi_p, dtype=int)
    a_np = np.array(amps_p, dtype=complex)
    Iref = ref_aerial_image(
        m_np, a_np, 64.0, sigma, na, 13.5, grid,
        dose_mj_cm2=dose, sigma_blur_nm=10.0,
    )
    n_ref = ref_nils(Iref, 64.0, grid)

    # Both use |dI/dx| at blur=10 -> direct compare
    diff = abs(n_op - abs(n_ref))
    assert diff < 0.3, f"NILS diff={diff:.3f} > 0.3 (OpEnUV={n_op:.3f}, Ref={n_ref:.3f})"


def test_nils_realistic_range():
    """NILS at realistic SE blur (10nm) should be in literature range [1.5, 4.0]."""
    a, b = _setup_euv_tmm()
    oi_p, amps_p, max_order = _build_orders(a, b)

    period_m = 64e-9
    na = 0.33
    wl_m = 13.5e-9
    sigma = 0.8
    grid = 512
    dose = 20.0

    amps_t = torch.tensor(amps_p, dtype=torch.complex128)
    oi_t = torch.tensor(oi_p, dtype=torch.int64)
    ae = aerial_from_orders(
        amps_t, oi_t,
        period_m=period_m, na=na, wavelength_m=wl_m,
        sigma=sigma, illumination_shape="conventional",
        grid=grid, se_blur_nm=10.0,
    )
    ae = ae * dose
    half = grid // 2
    lw = 256
    dx = period_m / grid * 1e9
    n_op = op_nils(ae, half, lw, dx)

    # Literature for k1≈0.78, σ=0.8: NILS ~ 2-3
    # Our model with blur=10nm gives ~2.7 (validated against reference)
    assert 1.5 <= n_op <= 4.0, f"NILS={n_op:.3f} outside realistic range [1.5, 4.0]"


# ──────────────────────────────────────────────
# Integration test: full pipeline with SE blur
# ──────────────────────────────

def test_pipeline_with_se_blur():
    """Full pipeline run_simulation with se_blur_nm produces sensible NILS."""
    from euv.pipeline import run_simulation, SimulationConfig

    # Standard 64nm/32nm line/space with SE blur = 10nm
    cfg = SimulationConfig(
        se_blur_nm=10.0,
        grid=256,
        dose_mj_cm2=20.0,
    )
    result = run_simulation(cfg)

    # NILS should be realistic (not 8.8)
    assert 1.5 <= result.nils_value <= 4.0, (
        f"Pipeline NILS={result.nils_value:.3f} outside realistic range"
    )

    # CD should be measurable
    assert result.cd_nm > 0, f"CD={result.cd_nm:.2f} not measurable"


def test_pipeline_car_preset():
    """CAR preset (5nm blur) produces realistic NILS."""
    from euv.pipeline import run_simulation, SimulationConfig, RESIST_PRESETS

    cfg = SimulationConfig(
        se_blur_nm=RESIST_PRESETS["CAR"],
        grid=256,
        dose_mj_cm2=20.0,
    )
    result = run_simulation(cfg)

    # CAR blur=5nm should give NILS ~ 4-5 (higher than 10nm blur)
    assert 2.0 <= result.nils_value <= 6.0, (
        f"CAR preset NILS={result.nils_value:.3f} outside expected range"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])