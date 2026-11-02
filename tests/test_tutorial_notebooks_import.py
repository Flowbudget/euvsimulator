"""Regression guard: the docs/tutorials notebooks must import and run.

All three imported from a package ``euv`` that does not exist (the package
is ``euvsimulator``; ``euv`` is only the CLI name).  materials.ipynb also
imported EV_TO_JOULE and PLANCK (not in euvsimulator.constants) and called
CXROTable.available_elements() (the method is list_elements()), and
basic_simulation.ipynb quoted CD ~29.5 nm and an absorber reflectivity of
~0.06 % for a run that gives 27.62 nm.

The two cheap notebooks are executed here; process_window.ipynb (a 63-point
dose-focus sweep) is executed with a stub pipeline in test_tutorial_exposure_latitude_units.py.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TUTORIALS = Path(__file__).resolve().parent.parent / "docs" / "tutorials"
NOTEBOOKS = ["basic_simulation.ipynb", "materials.ipynb", "process_window.ipynb"]


def _cells(name: str, cell_type: str) -> list[str]:
    nb = json.loads((TUTORIALS / name).read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == cell_type]


def _run(name: str, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Execute the code cells of a tutorial in one namespace (no Jupyter)."""
    monkeypatch.setattr(plt, "show", lambda *a, **k: None)
    namespace: dict = {"__name__": "__tutorial__"}
    try:
        for src in _cells(name, "code"):
            exec(compile(src, f"{name}", "exec"), namespace)
    finally:
        plt.close("all")
    return namespace


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_tutorial_imports_resolve(name: str) -> None:
    """Every ``from X import Y`` in a tutorial names an existing module and attribute."""
    for src in _cells(name, "code"):
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = importlib.import_module(node.module)
                for alias in node.names:
                    assert hasattr(module, alias.name), f"{name}: {node.module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    importlib.import_module(alias.name)


def test_materials_tutorial_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """materials.ipynb runs end to end and sweeps Si around 13.5 nm."""
    ns = _run("materials.ipynb", monkeypatch)
    assert len(ns["available"]) >= 90
    assert min(ns["wavelengths_nm"]) < 13.5 < max(ns["wavelengths_nm"])


def test_basic_simulation_tutorial_runs_and_quotes_its_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """basic_simulation.ipynb runs, and the CD its text quotes is the one it computes."""
    ns = _run("basic_simulation.ipynb", monkeypatch)
    result = ns["result"]
    text = "\n".join(_cells("basic_simulation.ipynb", "markdown"))
    quoted = [float(v) for v in re.findall(r"CD ≈ (\d+(?:\.\d+)?) nm", text)]
    assert quoted, "basic_simulation.ipynb: no 'CD ≈ ... nm' in the text"
    for v in quoted:
        assert v == pytest.approx(result.cd_nm, abs=0.05)
