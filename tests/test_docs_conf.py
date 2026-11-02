"""docs/conf.py must put <repo>/src on sys.path and report the package version."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import euvsimulator

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_conf_py_puts_repo_src_first_on_sys_path(monkeypatch) -> None:
    # Sphinx executes conf.py with docs/ as the current working directory.
    monkeypatch.chdir(DOCS)
    monkeypatch.setattr(sys, "path", list(sys.path))
    runpy.run_path(str(DOCS / "conf.py"))
    assert Path(sys.path[0]).resolve() == (ROOT / "src").resolve()


def test_conf_py_release_matches_package_version(monkeypatch) -> None:
    monkeypatch.chdir(DOCS)
    monkeypatch.setattr(sys, "path", list(sys.path))
    namespace = runpy.run_path(str(DOCS / "conf.py"))
    assert namespace["release"] == euvsimulator.__version__
