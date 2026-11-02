"""Regression guard: ``absorber_reflectivity`` must be the absorber's reflectivity.

Until 2026-10 ``SimulationResult.absorber_reflectivity`` held the duty-weighted
mask mean |r_abs|^2 * duty + |r_ML|^2 * (1 - duty), 0.3717 for the default
64/32 pattern, and the GUI tile "Absorber reflectivity", the CLI JSON and the
REST ``raw`` block presented it under that name (the GUI showed 33 %). The
Ta-on-multilayer stack itself reflects |r_abs|^2 = 0.011247 at the 6 deg chief
ray (notebooks/01_aerial_image.ipynb computes the same 0.011247 by hand).

Now ``absorber_reflectivity`` is |r0_abs|^2 of the absorber-on-multilayer
stack at the chief ray, in the polarisation convention of
``clear_field_reflectivity`` (TE on the thin-mask path, TE/TM average with
use_rcwa=True), and the old mean is ``mask_mean_reflectivity``.
"""

from __future__ import annotations

import math

import pytest
import torch
from fastapi.testclient import TestClient

from euvsimulator.constants import HC_EV_NM
from euvsimulator.materials import CXROTable
from euvsimulator.optics.multilayer import mo_si_stack
from euvsimulator.optics.tmm import reflectivity
from euvsimulator.pipeline import SimulationConfig, run_simulation


def _stack_r(cfg: SimulationConfig, *, absorber: bool, te: bool) -> float:
    """|r0|^2 at 6 deg of the bare multilayer or the absorber-on-multilayer stack."""
    energy_eV = HC_EV_NM / cfg.wavelength_nm
    table = CXROTable()
    n_si, k_si = table.refractive_index("Si", energy_eV)
    stack = mo_si_stack(
        n_bilayers=cfg.ml_n_bilayers,
        d_mo_nm=cfg.ml_d_mo_nm,
        d_si_nm=cfg.ml_d_si_nm,
        gamma=cfg.ml_gamma,
        grading_linear_nm=cfg.ml_grading_linear_nm,
        grading_parabolic_nm=cfg.ml_grading_parabolic_nm,
        capping_layer=cfg.ml_capping if cfg.ml_capping != "none" else None,
        d_cap_nm=cfg.ml_capping_nm,
        energy_eV=energy_eV,
    )
    n_layers, thicknesses = stack.n_layers, stack.thicknesses
    if absorber:
        n_a, k_a = table.refractive_index(cfg.absorber_material, energy_eV)
        n_layers = torch.cat([torch.tensor([complex(n_a, k_a)], dtype=torch.complex128), n_layers])
        thicknesses = torch.cat(
            [torch.tensor([cfg.absorber_height_nm * 1e-9], dtype=torch.float64), thicknesses]
        )
    _, r = reflectivity(
        n_layers,
        thicknesses,
        torch.tensor([cfg.wavelength_nm * 1e-9], dtype=torch.float64),
        torch.tensor(math.radians(6.0), dtype=torch.float64),
        n_substrate=torch.tensor(complex(n_si, k_si), dtype=torch.complex128),
        te=te,
        roughness_nm=cfg.ml_roughness_nm,
    )
    return float((abs(r[0]) ** 2).real)


def test_default_absorber_reflectivity_is_the_absorber_stack() -> None:
    """Default 64/32: |r_abs|^2 = 0.011247 (TE, like clear_field_reflectivity), not 0.3717."""
    cfg = SimulationConfig(device="cpu", grid=64)
    r = run_simulation(cfg)
    assert r.absorber_reflectivity == pytest.approx(0.011247, abs=5e-5)
    assert r.absorber_reflectivity == pytest.approx(_stack_r(cfg, absorber=True, te=True), rel=1e-9)
    assert r.clear_field_reflectivity == pytest.approx(
        _stack_r(cfg, absorber=False, te=True), rel=1e-9
    )


@pytest.mark.parametrize("line_width_nm", [16.0, 32.0, 48.0])
def test_absorber_reflectivity_independent_of_duty(line_width_nm: float) -> None:
    """A material property of the absorber stack: the same at every line width."""
    ref = run_simulation(SimulationConfig(device="cpu", grid=64)).absorber_reflectivity
    r = run_simulation(SimulationConfig(device="cpu", grid=64, line_width_nm=line_width_nm))
    assert r.absorber_reflectivity == pytest.approx(ref, rel=1e-12)


@pytest.mark.parametrize("line_width_nm", [16.0, 32.0, 48.0])
def test_mask_mean_reflectivity_is_the_old_duty_weighted_value(line_width_nm: float) -> None:
    """mask_mean_reflectivity = |r_abs|^2 * duty + |r_ML|^2 * (1 - duty) (the pre-fix field)."""
    cfg = SimulationConfig(device="cpu", grid=64, line_width_nm=line_width_nm)
    r = run_simulation(cfg)
    duty = cfg.line_width_nm / cfg.period_nm
    old = _stack_r(cfg, absorber=True, te=True) * duty + _stack_r(cfg, absorber=False, te=True) * (
        1.0 - duty
    )
    assert r.mask_mean_reflectivity == pytest.approx(old, rel=1e-12)
    assert r.mask_mean_reflectivity == pytest.approx(
        r.absorber_reflectivity * duty + r.clear_field_reflectivity * (1.0 - duty), rel=1e-12
    )
    if line_width_nm == 32.0:
        # the value the GUI, CLI and quickstart reported as "absorber reflectivity"
        assert r.mask_mean_reflectivity == pytest.approx(0.3717, abs=5e-5)


def test_rcwa_uses_the_clear_field_polarisation_convention() -> None:
    """use_rcwa=True: TE/TM average for both reported reflectivities."""
    cfg = SimulationConfig(device="cpu", grid=64, use_rcwa=True, n_rcwa_orders=11)
    r = run_simulation(cfg)
    r_abs = 0.5 * (_stack_r(cfg, absorber=True, te=True) + _stack_r(cfg, absorber=True, te=False))
    r_ml = 0.5 * (_stack_r(cfg, absorber=False, te=True) + _stack_r(cfg, absorber=False, te=False))
    assert r.clear_field_reflectivity == pytest.approx(r_ml, rel=1e-9)
    assert r.absorber_reflectivity == pytest.approx(r_abs, rel=1e-9)
    duty = cfg.line_width_nm / cfg.period_nm
    assert r.mask_mean_reflectivity == pytest.approx(r_abs * duty + r_ml * (1.0 - duty), rel=1e-9)


def test_rest_raw_reports_absorber_and_mask_mean() -> None:
    """The REST raw block (read by the GUI tile) carries the absorber value."""
    from euvsimulator.api.main import app

    resp = TestClient(app).post("/simulate", json={"config": {"grid": 64}})
    assert resp.status_code == 200
    raw = resp.json()["raw"]
    assert raw["absorber_reflectivity"] == pytest.approx(0.011247, abs=5e-5)
    assert raw["mask_mean_reflectivity"] == pytest.approx(0.3717, abs=5e-5)


def test_cli_json_reports_absorber_and_mask_mean() -> None:
    """``euv simulate`` prints the absorber value and the mask mean separately."""
    import json

    from typer.testing import CliRunner

    from euvsimulator.io.cli import app

    result = CliRunner().invoke(app, ["simulate", "--grid", "64"])
    assert result.exit_code == 0, result.output
    printed = json.loads(result.output[result.output.index("{") :])
    assert printed["absorber_reflectivity"] == pytest.approx(0.011247, abs=5e-5)
    assert printed["mask_mean_reflectivity"] == pytest.approx(0.3717, abs=5e-5)


def test_gui_tile_reads_the_absorber_value() -> None:
    """The 'Absorber reflectivity' tile (#r-refl) is filled from raw.absorber_reflectivity."""
    from pathlib import Path

    static = Path(__file__).resolve().parent.parent / "src" / "euvsimulator" / "api" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert 'tile-label">Absorber reflectivity</span><span class="tile-value" id="r-refl"' in html
    assert "const refl = data.raw && data.raw.absorber_reflectivity;" in js
    assert "mask_mean_reflectivity;" not in js
