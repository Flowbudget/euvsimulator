"""Regression guard: the CSV loader of ``euv calibrate``.

Before the fix a CSV without the column ``cd_nm`` (e.g. the header
``dose,focus,cd``) ended in a raw ``KeyError`` traceback, and an empty or
``nan`` cd_nm was rejected with the advice to enter a site that did not print
as ``cd_nm 0``. That advice fits a measured 0 nm CD to a site the full_chem
model reports at the pitch when nothing develops, which is the error io-cli-2
removed. The library (``WaferCDData``, ``objective_resist``) and the JSON path
treat NaN as a site without a measurement and skip it; the CSV path now does
the same for an empty or ``nan`` cd_nm.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import euvsimulator.pipeline as pipeline_mod
from euvsimulator.io.cli import app

TABLE = {4.0: 32.0, 4.5: 28.0, 5.0: 26.0, 5.5: 24.0}


@pytest.fixture()
def seen(monkeypatch):
    calls = []

    def fake_run_simulation(cfg):
        calls.append(cfg)
        return SimpleNamespace(cd_nm=TABLE[cfg.dose_mj_cm2] - 0.5 * (cfg.peb_sigma_diff - 7.0))

    monkeypatch.setattr(pipeline_mod, "run_simulation", fake_run_simulation)
    return calls


def _invoke(tmp_path, csv_text: str, *extra: str):
    csv = tmp_path / "fem.csv"
    csv.write_text(csv_text)
    ip = tmp_path / "ip.yaml"
    ip.write_text("peb_sigma_diff: 12.0\n")
    return CliRunner().invoke(
        app,
        ["calibrate", str(csv), "-i", str(ip), "--bootstrap", "0", "--maxiter", "20", *extra],
    )


@pytest.mark.parametrize(
    "header, missing",
    [("dose,focus,cd", "cd_nm"), ("dose,cd_nm", "focus"), ("Dose,Focus,CD_nm", "cd_nm")],
)
def test_wrong_header_gives_a_readable_error(tmp_path, seen, header, missing) -> None:
    result = _invoke(tmp_path, f"{header}\n4.0,0.0,32.0\n4.5,0.0,28.0\n")
    assert result.exit_code == 1, result.output
    assert not isinstance(result.exception, KeyError), "raw KeyError traceback"
    assert "columns" in result.output and missing in result.output
    assert seen == []


def test_empty_or_nan_cd_is_a_site_without_measurement(tmp_path, seen) -> None:
    out = tmp_path / "out.json"
    result = _invoke(
        tmp_path,
        "dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,\n5.0,0.0,nan\n5.5,0.0,24.0\n",
        "-o",
        str(out),
    )
    assert result.exit_code == 0, result.output
    simulated = {c.dose_mj_cm2 for c in seen}
    assert simulated == {4.0, 5.5}, "sites without a measurement must not be simulated"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["fit"]["fitted_params"]["peb_sigma_diff"] == pytest.approx(7.0, abs=0.5)
    assert "2 of 4" in result.output  # reported, not silent


def test_absent_cell_advice_no_longer_says_zero(tmp_path, seen) -> None:
    result = _invoke(tmp_path, "dose,focus,cd_nm\n4.0,0.0,32.0\n4.0,50.0,31.0\n4.5,0.0,28.0\n")
    assert result.exit_code == 1, result.output
    assert "1 of 4" in result.output and "dose=4.5, focus=50" in result.output
    assert "cd_nm 0" not in result.output
    assert "empty" in result.output
    assert seen == []


@pytest.mark.parametrize(
    "csv_text, expected",
    [
        ("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,inf\n", "inf"),
        ("dose,focus,cd_nm\n4.0,0.0,\n4.5,0.0,nan\n", "no finite cd_nm"),
        ("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,,28.0\n", "line 3"),
        ("dose,focus,cd_nm\n4.0,0.0,32.0\n4.5,0.0,abc\n", "line 3"),
    ],
    ids=["inf", "all-empty", "empty-focus", "not-a-number"],
)
def test_invalid_values_are_rejected_readably(tmp_path, seen, csv_text, expected) -> None:
    result = _invoke(tmp_path, csv_text)
    assert result.exit_code == 1, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(
        result.exception
    )
    assert expected in result.output
    assert seen == []
