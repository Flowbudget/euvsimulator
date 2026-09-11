"""`euv calibrate` wiring tests (fast: the simulation is replaced by a stub).

Regression for a shadowing bug found 2026-09-05: the CSV loader's loop
variable `cd` overwrote the `--cd` option, so every fit simulated the LAST
measured CD as the nominal line width (24 nm instead of 32 nm in the smoke
test) and converged to nonsense (σ = 1 nm, RMSE 6.6 nm on a synthetic FEM
generated at σ = 7 nm).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import euvsimulator.pipeline as pipeline_mod
from euvsimulator.io.cli import app


def _write_fem(tmp_path):
    csv = tmp_path / "fem.csv"
    csv.write_text("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,28.0\n5.0,0.0,26.0\n5.5,0.0,24.0\n")
    return csv


def test_calibrate_simulates_the_requested_geometry(tmp_path, monkeypatch):
    seen = []

    def fake_run_simulation(cfg):
        seen.append(cfg)
        # a smooth, sigma-dependent stand-in that reproduces the FEM exactly at
        # sigma = 7, so the optimiser has a well-defined minimum to find
        table = {4.0: 32.0, 4.5: 28.0, 5.0: 26.0, 5.5: 24.0}
        cd = table[cfg.dose_mj_cm2] - 0.5 * (cfg.peb_sigma_diff - 7.0)
        return SimpleNamespace(cd_nm=cd)

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    ip = tmp_path / "ip.yaml"
    ip.write_text("peb_sigma_diff: 12.0\n")
    out = tmp_path / "out.json"
    result = CliRunner().invoke(
        app,
        [
            "calibrate",
            str(_write_fem(tmp_path)),
            "-i",
            str(ip),
            "--period",
            "44",
            "--cd",
            "22",
            "--grid",
            "64",
            "--se-blur",
            "3",
            "--bootstrap",
            "0",
            "--maxiter",
            "20",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen, "pipeline was never called"
    assert {c.period_nm for c in seen} == {44.0}
    assert {c.line_width_nm for c in seen} == {22.0}, "--cd must reach the simulation unchanged"
    assert {c.grid for c in seen} == {64}
    assert {c.se_blur_nm for c in seen} == {3.0}
    assert {c.resist_model for c in seen} == {"full_chem"}
    assert {c.dose_mj_cm2 for c in seen} == {4.0, 4.5, 5.0, 5.5}
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["fit"]["fitted_params"]["peb_sigma_diff"] == pytest.approx(7.0, abs=0.5)
    assert payload["fit"]["rmse"] < 0.3


def test_calibrate_only_fits_parameters_given_in_initial_file(tmp_path, monkeypatch):
    seen = []

    def fake_run_simulation(cfg):
        seen.append(cfg)
        return SimpleNamespace(cd_nm=30.0)

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    ip = tmp_path / "ip.yaml"
    ip.write_text("peb_sigma_diff: 9.0\n")
    result = CliRunner().invoke(
        app,
        [
            "calibrate",
            str(_write_fem(tmp_path)),
            "-i",
            str(ip),
            "--bootstrap",
            "0",
            "--maxiter",
            "5",
        ],
    )
    assert result.exit_code == 0, result.output
    # every other resist parameter stays at the SimulationConfig default
    default = pipeline_mod.SimulationConfig()
    for c in seen:
        assert c.dill_C == default.dill_C
        assert c.peb_k == default.peb_k
        assert c.mack_n == default.mack_n
        assert c.mack_M_th == default.mack_M_th
