"""Smoke tests for the `euv` CLI commands that had no test (audit 2026-09-04, E7).

`serve` (starts a server) and `bench` (grid 512 timings) are deliberately not
exercised here; `simulate` is covered by tests/test_full_chem_config.py and
`calibrate` by tests/test_cli_calibrate.py.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from euvsimulator import __version__
from euvsimulator.io.cli import app

runner = CliRunner()


def test_version_prints_package_version():
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0, r.output
    assert __version__ in r.output


def test_info_lists_modules():
    r = runner.invoke(app, ["info"])
    assert r.exit_code == 0, r.output
    for name in ("optics/", "mask3d/", "resist/", "metro/"):
        assert name in r.output


def test_materials_list_and_nk():
    r = runner.invoke(app, ["materials"])
    assert r.exit_code == 0, r.output
    assert "Si" in r.output and "Mo" in r.output
    r = runner.invoke(app, ["materials", "Si", "--energy", "91.84"])
    assert r.exit_code == 0, r.output
    # CXRO Si at 13.5 nm: n = 1 - delta with delta ~ 1e-3, k ~ 1.8e-3
    assert "0.99" in r.output


def test_make_mask_writes_a_gds_file(tmp_path):
    out = tmp_path / "m.gds"
    r = runner.invoke(
        app, ["make-mask", "--pitch", "64", "--cd", "32", "--n-lines", "3", "--out", str(out)]
    )
    assert r.exit_code == 0, r.output
    assert out.exists() and out.stat().st_size > 0
    import gdstk

    lib = gdstk.read_gds(str(out))
    n_polys = sum(len(c.polygons) for c in lib.cells)
    assert n_polys == 3


def test_process_window_small_grid(tmp_path):
    out = tmp_path / "pw.json"
    r = runner.invoke(
        app,
        [
            "process-window",
            "--period",
            "64",
            "--cd",
            "32",
            "--grid",
            "64",
            "--dose-start",
            "15",
            "--dose-end",
            "25",
            "--dose-steps",
            "3",
            "--focus-start",
            "-30",
            "--focus-end",
            "30",
            "--focus-steps",
            "3",
            "--output",
            str(out),
        ],
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload, "empty process-window output"
    text = json.dumps(payload)
    assert "cd" in text.lower()
