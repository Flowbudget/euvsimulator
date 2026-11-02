"""Regression guard: `euv process-window` must not report a degenerate window silently.

The quick-start command `euv process-window --period 64 --cd 32` scans 10-40
mJ/cm² in 5 mJ/cm² steps and -50..+50 nm focus.  Only one dose column prints
within ±10 %, so EL is 0 by definition, and that column stays in spec over
the whole focus scan, so DoF equals the scan range.  The CLI printed both
numbers without the caveat the GUI shows.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from euvsimulator.io.cli import app

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "llms.txt", "docs/quickstart.rst"]
runner = CliRunner()


def _run(args: list[str], out: Path) -> tuple[dict, str]:
    if "--grid" not in " ".join(args):
        args = [*args, "--grid", "64"]  # cheap; the window is resolved the same way at 256
    r = runner.invoke(app, ["process-window", *args, "--output", str(out)])
    assert r.exit_code == 0, r.output
    return json.loads(out.read_text(encoding="utf-8")), r.output


def test_default_scan_warns_el_and_dof(tmp_path: Path) -> None:
    payload, output = _run(["--period", "64", "--cd", "32"], tmp_path / "pw.json")
    assert payload["exposure_latitude_pct"] == 0.0
    assert payload["depth_of_focus_nm"] == pytest.approx(100.0)
    warnings = payload["warnings"]
    assert any(w.startswith("Exposure latitude not resolved") for w in warnings), warnings
    assert any(w.startswith("Depth of focus saturated") for w in warnings), warnings
    for w in warnings:
        assert w in output


def _documented_commands() -> dict[str, list[str]]:
    cmds: dict[str, list[str]] = {}
    for name in DOCS:
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("euv process-window"):
                cmds[name] = shlex.split(line.split("#", 1)[0])[2:]
    return cmds


def test_documented_example_resolves_the_window(tmp_path: Path) -> None:
    """The process-window example in the docs brackets the dose-to-size finely."""
    cmds = _documented_commands()
    assert set(cmds) == set(DOCS), f"process-window example missing in {set(DOCS) - set(cmds)}"
    for i, args in enumerate({tuple(a) for a in cmds.values()}):
        payload, _ = _run(list(args), tmp_path / f"pw{i}.json")
        focus_span = payload["focuses"][-1] - payload["focuses"][0]
        assert payload["warnings"] == [], (args, payload["warnings"])
        assert payload["exposure_latitude_pct"] > 0.0
        assert 0.0 < payload["depth_of_focus_nm"] < focus_span
