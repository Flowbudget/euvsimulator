"""euv calibrate --bootstrap N: the CI block belongs to the reported fit.

Before the fix the CLI printed the main fit (--maxiter) under "Fitted
parameters" and a second, independent fit at maxiter 1000 as the point
estimate of the confidence intervals (8.4000 vs 7.0000 in this setup).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import euvsimulator.calibrate.wafer_fit as wafer_fit
import euvsimulator.pipeline as pipeline_mod
from euvsimulator.io.cli import app


def test_bootstrap_uses_the_reported_fit_and_maxiter(tmp_path, monkeypatch):
    def fake_run_simulation(cfg):
        table = {4.0: 32.0, 4.5: 28.0, 5.0: 26.0, 5.5: 24.0}
        return SimpleNamespace(cd_nm=table[cfg.dose_mj_cm2] - 0.5 * (cfg.peb_sigma_diff - 7.0))

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    real_bootstrap = wafer_fit.bootstrap_fit
    calls = []

    def spy_bootstrap(*args, **kwargs):
        calls.append(kwargs)
        out = real_bootstrap(*args, **kwargs)
        out["bootstrap_samples"] = out["bootstrap_samples"].tolist()  # JSON-safe
        return out

    monkeypatch.setattr(wafer_fit, "bootstrap_fit", spy_bootstrap)
    csv = tmp_path / "fem.csv"
    csv.write_text("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,28.0\n5.0,0.0,26.0\n5.5,0.0,24.0\n")
    ip = tmp_path / "ip.yaml"
    ip.write_text("peb_sigma_diff: 12.0\n")
    out = tmp_path / "out.json"
    result = CliRunner().invoke(
        app,
        [
            "calibrate",
            str(csv),
            "-i",
            str(ip),
            "--bootstrap",
            "3",
            "--maxiter",
            "3",
            "--seed",
            "0",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0]["options"] == {"maxiter": 3}
    payload = json.loads(out.read_text(encoding="utf-8"))
    fitted = payload["fit"]["fitted_params"]["peb_sigma_diff"]
    assert fitted != pytest.approx(7.0, abs=0.01)  # maxiter 3 stops before the minimum
    assert payload["bootstrap"]["fitted_on_original"] == payload["fit"]["fitted_params"]
    assert f"peb_sigma_diff: {fitted:.4f}  [" in result.output
