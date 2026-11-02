"""Regression guard: reversed or degenerate process-window and bands ranges.

Before the fix a descending dose axis gave a negative exposure latitude and a
descending focus axis forced DoF = 0 (``focus_spacing > 0`` guard), both
returned as valid results by ``metro.process_window``, the ``process_window``
job and ``euv process-window``. ``BandsParams`` accepted dose_lo >= dose_hi
(the job failed late) and an empty seeds list (StatisticsError after the
dose-to-size bisections).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

import euvsimulator.pipeline as pipeline_mod
from euvsimulator.api.main import app as api_app
from euvsimulator.api.schemas import BandsParams, ProcessWindowParams
from euvsimulator.io.cli import app as cli_app
from euvsimulator.metro.process_window import process_window, pw_metrics

DOSES = [10.0, 15.0, 20.0, 25.0, 30.0]
FOCUSES = [-50.0, -25.0, 0.0, 25.0, 50.0]
IN_SPEC = np.full((5, 5), 32.0)  # every cell in spec


class TestMetro:
    def test_ascending_axes_unchanged(self) -> None:
        pw = process_window(IN_SPEC, DOSES, FOCUSES, target_cd=32.0, tolerance=0.1)
        assert pw["dof_nm"] == pytest.approx(100.0)
        assert pw["el_pct"] == pytest.approx(200.0)
        m = pw_metrics(IN_SPEC, 32.0, 0.1, doses=DOSES, focuses=FOCUSES)
        assert m["dof_nm"] == pytest.approx(100.0)
        assert m["el_pct"] == pytest.approx(200.0)

    @pytest.mark.parametrize(
        "doses, focuses",
        [(DOSES[::-1], FOCUSES), (DOSES, FOCUSES[::-1]), (DOSES, [0.0, 0.0, 0.0, 25.0, 50.0])],
        ids=["descending-doses", "descending-focuses", "repeated-focus"],
    )
    def test_non_ascending_axes_are_rejected(self, doses, focuses) -> None:
        # before the fix: EL -66.7 % (descending doses) or DoF 0.0 (descending focuses)
        with pytest.raises(ValueError, match="strictly ascending"):
            process_window(IN_SPEC, doses, focuses, target_cd=32.0, tolerance=0.1)
        with pytest.raises(ValueError, match="strictly ascending"):
            pw_metrics(IN_SPEC, 32.0, 0.1, doses=doses, focuses=focuses)

    def test_pw_metrics_without_axes_needs_no_order(self) -> None:
        m = pw_metrics(IN_SPEC, 32.0, 0.1)
        assert m["dof_steps"] == 4 and m["el_steps"] == 4


class TestSchemas:
    @pytest.mark.parametrize(
        "params",
        [
            {"dose_start": 40.0, "dose_end": 10.0},
            {"dose_start": 20.0, "dose_end": 20.0},
            {"focus_start": 50.0, "focus_end": -50.0},
            {"focus_start": 0.0, "focus_end": 0.0},
        ],
    )
    def test_process_window_rejects_reversed_or_empty_range(self, params) -> None:
        with pytest.raises(ValidationError, match="must be smaller than"):
            ProcessWindowParams(**params)

    def test_process_window_defaults_still_valid(self) -> None:
        p = ProcessWindowParams()
        assert p.dose_start < p.dose_end and p.focus_start < p.focus_end

    @pytest.mark.parametrize(
        "params, match",
        [
            ({"dose_lo": 60.0, "dose_hi": 0.3}, "must be smaller than"),
            ({"dose_lo": 5.0, "dose_hi": 5.0}, "must be smaller than"),
            ({"seeds": []}, "at least 1 item"),
        ],
    )
    def test_bands_rejects_reversed_bracket_and_empty_seeds(self, params, match) -> None:
        with pytest.raises(ValidationError, match=match):
            BandsParams(**params)

    def test_jobs_endpoint_returns_422_before_any_work(self) -> None:
        client = TestClient(api_app)
        r = client.post(
            "/jobs",
            json={
                "kind": "process_window",
                "config": {"grid": 32},
                "process_window": {"dose_start": 40, "dose_end": 10},
            },
        )
        assert r.status_code == 422, r.text
        assert "dose_start" in r.text
        r = client.post(
            "/jobs",
            json={
                "kind": "bands",
                "config": {"grid": 32, "resist_model": "full_chem", "dose_mj_cm2": 1.3},
                "bands": {"dose_lo": 60.0, "dose_hi": 0.3},
            },
        )
        assert r.status_code == 422, r.text


class TestCli:
    @pytest.mark.parametrize(
        "extra, match",
        [
            (["--dose-start", "40", "--dose-end", "10"], "--dose-start"),
            (["--focus-start", "50", "--focus-end", "-50"], "--focus-start"),
            (["--dose-steps", "1"], "--dose-steps"),
        ],
    )
    def test_process_window_rejects_reversed_ranges(self, monkeypatch, extra, match) -> None:
        calls = []

        def fake_run_simulation(cfg):
            calls.append(cfg)
            return SimpleNamespace(cd_nm=32.0, nils_value=2.0)

        monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
        r = CliRunner().invoke(cli_app, ["process-window", "--grid", "32", *extra])
        assert r.exit_code == 1, r.output
        assert match in r.output
        assert calls == [], "no simulation may run on rejected ranges"
