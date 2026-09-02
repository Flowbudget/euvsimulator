"""Independent Mack-NILS tests.

The expected values are computed from the analytic definition

    NILS = CD * abs(dI/dx) / I_edge

at the intensity-threshold crossings of a synthetic 1D profile.
They do not call euvsimulator.aerial.abbe.nils.
"""

from __future__ import annotations

import torch

from euvsimulator.aerial.abbe import nils


def _profile_to_aerial(cut: torch.Tensor) -> torch.Tensor:
    """Replicate a 1D cut to a square aerial image (y-invariant)."""
    G = cut.shape[0]
    return cut.unsqueeze(0).expand(G, G).clone()


def _trapezoid_cut(
    G: int = 100,
    *,
    x_left_outer: float = 30.0,
    ramp_left: float = 5.0,
    plateau: float = 20.0,
    ramp_right: float = 5.0,
    I_space: float = 3.0,
    I_line: float = 1.0,
) -> torch.Tensor:
    """Piecewise-linear dark line on a bright background.

    Outer-left ramp starts at ``x_left_outer`` (pixel coordinate).
    Intensities are sampled at integer pixel centres 0 .. G-1.
    """
    x = torch.arange(G, dtype=torch.float64)
    x_left_inner = x_left_outer + ramp_left
    x_right_inner = x_left_inner + plateau
    x_right_outer = x_right_inner + ramp_right
    I = torch.empty(G, dtype=torch.float64)
    for i in range(G):
        xi = float(x[i])
        if xi <= x_left_outer or xi >= x_right_outer:
            I[i] = I_space
        elif xi < x_left_inner:
            t = (xi - x_left_outer) / ramp_left
            I[i] = I_space + t * (I_line - I_space)
        elif xi <= x_right_inner:
            I[i] = I_line
        else:
            t = (xi - x_right_inner) / ramp_right
            I[i] = I_line + t * (I_space - I_line)
    return I


def _analytic_nils_trapezoid(
    *,
    x_left_outer: float,
    ramp_left: float,
    plateau: float,
    ramp_right: float,
    I_space: float,
    I_line: float,
    threshold: float,
    dx_nm: float,
) -> tuple[float, float, float, float]:
    """Analytic Mack NILS for the trapezoid (independent of euvsimulator).

    Returns (nils_mean, cd_nm, nils_left, nils_right).
    """
    # Linear ramps: I(x) = I_space + (x-x_lo)/ramp * (I_line-I_space)
    # Crossing: threshold = I_space + t/ramp * (I_line-I_space)
    t_left = (threshold - I_space) / (I_line - I_space) * ramp_left
    x_left = x_left_outer + t_left
    t_right = (threshold - I_line) / (I_space - I_line) * ramp_right
    x_right = x_left_outer + ramp_left + plateau + t_right
    cd_px = x_right - x_left
    cd_nm = cd_px * dx_nm
    slope_left = (I_line - I_space) / ramp_left  # per pixel
    slope_right = (I_space - I_line) / ramp_right
    dIdx_left = slope_left / dx_nm
    dIdx_right = slope_right / dx_nm
    nils_left = cd_nm * abs(dIdx_left) / threshold
    nils_right = cd_nm * abs(dIdx_right) / threshold
    return 0.5 * (nils_left + nils_right), cd_nm, nils_left, nils_right


def test_analytic_symmetric_trapezoid():
    """Mack NILS on a symmetric trapezoid matches the closed-form value."""
    dx = 1.0
    G = 100
    params = dict(
        x_left_outer=30.0,
        ramp_left=5.0,
        plateau=20.0,
        ramp_right=5.0,
        I_space=3.0,
        I_line=1.0,
    )
    thr = 2.0
    expected, _, nL, nR = _analytic_nils_trapezoid(threshold=thr, dx_nm=dx, **params)
    assert abs(nL - nR) < 1e-12
    assert abs(expected - 5.0) < 1e-12  # 25 nm * 0.4 /nm / 2.0

    cut = _trapezoid_cut(G, **params)
    aerial = _profile_to_aerial(cut)
    got = nils(aerial, line_center=G // 2, line_width_px=20, dx_nm=dx, threshold=thr)
    assert abs(got - expected) < 1e-6, f"NILS={got:.6f} expected={expected:.6f}"


def test_symmetric_left_right_equal():
    """Left and right edge NILS are equal on a symmetric profile."""
    dx = 1.0
    G = 100
    params = dict(
        x_left_outer=30.0,
        ramp_left=5.0,
        plateau=20.0,
        ramp_right=5.0,
        I_space=3.0,
        I_line=1.0,
    )
    _, _, nL, nR = _analytic_nils_trapezoid(threshold=2.0, dx_nm=dx, **params)
    assert abs(nL - nR) < 1e-12
    cut = _trapezoid_cut(G, **params)
    aerial = _profile_to_aerial(cut)
    got = nils(aerial, G // 2, 20, dx, threshold=2.0)
    assert abs(got - nL) < 1e-6


def test_threshold_shift_moves_evaluation_point():
    """A different threshold must change NILS (evaluated at the new edge)."""
    dx = 1.0
    G = 100
    params = dict(
        x_left_outer=30.0,
        ramp_left=5.0,
        plateau=20.0,
        ramp_right=5.0,
        I_space=3.0,
        I_line=1.0,
    )
    cut = _trapezoid_cut(G, **params)
    aerial = _profile_to_aerial(cut)
    n_lo = nils(aerial, G // 2, 20, dx, threshold=1.5)
    n_hi = nils(aerial, G // 2, 20, dx, threshold=2.5)
    exp_lo, _, _, _ = _analytic_nils_trapezoid(threshold=1.5, dx_nm=dx, **params)
    exp_hi, _, _, _ = _analytic_nils_trapezoid(threshold=2.5, dx_nm=dx, **params)
    assert abs(n_lo - exp_lo) < 1e-6
    assert abs(n_hi - exp_hi) < 1e-6
    assert abs(n_lo - n_hi) > 0.1


def test_asymmetric_not_global_argmax_gradient():
    """Steep left / shallow right: NILS is the mean, not the steep-edge-only value.

    Old nils() used argmax(|dI/dx|), which sits on the steep ramp and
    ignores the shallow edge.  Mack NILS must average both printed edges.
    """
    dx = 1.0
    G = 120
    params = dict(
        x_left_outer=20.0,
        ramp_left=4.0,
        plateau=24.0,
        ramp_right=16.0,
        I_space=3.0,
        I_line=1.0,
    )
    thr = 2.0
    expected, cd, nL, nR = _analytic_nils_trapezoid(threshold=thr, dx_nm=dx, **params)
    assert nL > nR * 1.5  # left is steeper
    cut = _trapezoid_cut(G, **params)
    aerial = _profile_to_aerial(cut)
    got = nils(aerial, G // 2, 24, dx, threshold=thr)
    assert abs(got - expected) < 1e-5, f"NILS={got:.6f} expected={expected:.6f}"
    # Must not collapse to the steep-edge-only value
    assert abs(got - nL) > 0.2


def test_pipeline_cd_unchanged_nils_at_threshold():
    """Optical CD stays ~27.62 nm (sub-pixel, was 27.5 integer); NILS is Mack at the same threshold.

    4.95 is a physical check, not a golden value.
    """
    from euvsimulator.pipeline import SimulationConfig, run_simulation

    cfg = SimulationConfig(
        period_nm=64,
        line_width_nm=32,
        dose_mj_cm2=20,
        na=0.33,
        sigma=0.8,
        grid=256,
        device="cpu",
        use_rcwa=False,
        se_blur_nm=0.0,
        resist_model="aerial_threshold",
    )
    r = run_simulation(cfg)
    assert abs(r.cd_nm - 27.62) < 0.01, f"Optical CD changed: {r.cd_nm}"
    # Interpolated Mack NILS at thr=0.5*mean is ~4.97 for this aerial.
    # Bound is wide enough to catch a return to the old ~4.12 heuristic
    # without freezing a golden digit.
    assert 4.7 < r.nils_value < 5.2, f"NILS={r.nils_value:.4f} not Mack-at-threshold"
