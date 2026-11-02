"""Regression guard: optics and geometry are validated by SimulationConfig itself.

Before the fix only the REST layer (api.fields.physics_errors) checked them;
the Python API and the CLI returned plausible or even negative CDs for
impossible inputs. Measured on the base tree (run_simulation, grid 64,
aerial_threshold): line_width 80 / period 64 -> CD 30.21 nm; na 0 or -0.33
-> CD 64.0; sigma -0.5 -> 31.57; sigma 2.5 -> 18.89; period -64 -> CD -64.0;
grid 2 -> CD 0.0; period 0 -> ZeroDivisionError; ``euv simulate --period 64
--cd 80`` exited 0 with a result.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import euvsimulator.pipeline as pipeline_mod
from euvsimulator.api.fields import physics_errors, resolve_config
from euvsimulator.io.cli import app
from euvsimulator.pipeline import SimulationConfig

INVALID = [
    ({"line_width_nm": 80.0}, "line_width_nm"),
    ({"line_width_nm": 64.0}, "line_width_nm"),
    ({"line_width_nm": 0.0}, "line_width_nm"),
    ({"na": 0.0}, "na "),
    ({"na": -0.33}, "na "),
    ({"na": 1.0}, "na "),
    ({"sigma": -0.5}, "sigma"),
    ({"sigma": 2.5}, "sigma"),
    ({"period_nm": -64.0, "line_width_nm": -32.0}, "period_nm"),
    ({"period_nm": 0.0}, "period_nm"),
    ({"wavelength_nm": 0.0}, "wavelength_nm"),
    ({"grid": 2}, "grid"),
    ({"grid": 1}, "grid"),
    ({"n_rcwa_orders": 0}, "n_rcwa_orders"),
    ({"use_rcwa": True, "n_rcwa_orders": 10}, "odd"),
    ({"na": float("nan")}, "na "),
]


@pytest.mark.parametrize(
    "kwargs, match", INVALID, ids=[",".join(f"{k}={v}" for k, v in kw.items()) for kw, _ in INVALID]
)
def test_simulation_config_rejects_invalid_optics_and_geometry(kwargs, match) -> None:
    with pytest.raises(ValueError, match=match):
        SimulationConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sigma": 0.0},  # coherent limit (tests/test_pipeline.py runs it)
        {"sigma": 1.0},
        {"grid": 4},
        {"n_rcwa_orders": 10},  # thin-mask path: largest |m|, any count >= 1
        {"use_rcwa": True, "n_rcwa_orders": 11},
        {"na": 0.55, "period_nm": 24.0, "line_width_nm": 12.0},
    ],
)
def test_valid_edges_are_accepted(kwargs) -> None:
    SimulationConfig(**kwargs)


def test_rest_layer_uses_the_same_rules() -> None:
    # the coherent limit is valid for the dataclass and the API alike (the API
    # demanded sigma > 0 before)
    assert physics_errors(resolve_config(None, {"sigma": 0.0})) == []
    for kwargs, match in INVALID:
        with pytest.raises(ValueError, match=match):
            resolve_config(None, kwargs)
    assert physics_errors(SimulationConfig()) == []


@pytest.fixture()
def no_simulation(monkeypatch):
    calls = []

    def fake_run_simulation(cfg, *args, **kwargs):
        calls.append(cfg)
        return SimpleNamespace(cd_nm=30.0, nils_value=2.0)

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    return calls


@pytest.mark.parametrize(
    "args, match",
    [
        (["simulate", "--grid", "64", "--period", "64", "--cd", "80"], "line_width_nm"),
        (["simulate", "--grid", "64", "--sigma", "2.5"], "sigma"),
        (["process-window", "--grid", "32", "--na", "0"], "na "),
        (["process-window", "--grid", "32", "--dose-start", "-5"], "dose_mj_cm2"),
    ],
)
def test_cli_reports_invalid_config_and_exits_1(no_simulation, args, match) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    assert not isinstance(result.exception, ValueError), "raw ValueError traceback"
    assert match in result.output
    assert no_simulation == []


def test_cli_config_file_is_validated(tmp_path, no_simulation) -> None:
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"period_nm": 64.0, "line_width_nm": 80.0, "grid": 64}))
    result = CliRunner().invoke(app, ["simulate", "-c", str(cfg)])
    assert result.exit_code == 1, result.output
    assert "line_width_nm" in result.output
    assert no_simulation == []


def test_cli_calibrate_validates_the_geometry_before_fitting(tmp_path, no_simulation) -> None:
    # before the fix the fit ran on a line wider than the period
    fem = tmp_path / "fem.csv"
    fem.write_text("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,28.0\n")
    result = CliRunner().invoke(
        app,
        ["calibrate", str(fem), "--period", "64", "--cd", "80", "--bootstrap", "0"],
    )
    assert result.exit_code == 1, result.output
    assert "line_width_nm" in result.output
    assert no_simulation == []
