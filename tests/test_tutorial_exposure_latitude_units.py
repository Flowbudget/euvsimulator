"""Regression guard: docs/tutorials/process_window.ipynb computes EL with the right units.

The tutorial computed the exposure latitude as
``(d_ok.max() - d_ok.min()) / target_cd * 100``, a dose range in mJ/cm²
divided by a CD in nm -- the unit error io/cli.py fixed on 2026-09-04.  EL is
(dose_max - dose_min) / dose_best × 100 % at best focus, as
``euvsimulator.metro.process_window.process_window`` computes it.

The notebook is executed with a stub pipeline (an analytic CD model), so the
test checks the tutorial's metric code, not the physics, in a fraction of a
second.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import euvsimulator.pipeline as pipeline_module  # noqa: E402
from euvsimulator.metro.process_window import process_window  # noqa: E402

NOTEBOOK = Path(__file__).resolve().parent.parent / "docs" / "tutorials" / "process_window.ipynb"


def _stub_run_simulation(cfg):
    """Analytic CD: shrinks weakly with dose, grows slowly with defocus.

    Every dose of any reasonable grid prints in spec at focus 0, so a correct
    EL is large and differs from the unit-error value.
    """
    cd = 32.0 * (16.0 / cfg.dose_mj_cm2) ** 0.1 * (1.0 + 0.5 * (cfg.focus_nm / 300.0) ** 2)
    return SimpleNamespace(cd_nm=cd, nils_value=3.0)


def _run_notebook(monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(pipeline_module, "run_simulation", _stub_run_simulation)
    monkeypatch.setattr(plt, "show", lambda *a, **k: None)
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    namespace: dict = {"__name__": "__tutorial__"}
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(compile("".join(cell["source"]), NOTEBOOK.name, "exec"), namespace)
    finally:
        plt.close("all")
    return namespace


def test_tutorial_el_and_dof_match_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """EL and DoF printed by the tutorial equal the library's definitions."""
    ns = _run_notebook(monkeypatch)
    doses = np.asarray(ns["doses"], dtype=float)
    focuses = np.asarray(ns["focuses"], dtype=float)
    cd_matrix = np.asarray(ns["cd_matrix"], dtype=float)
    assert cd_matrix.shape == (len(doses), len(focuses))
    ref = process_window(
        cd_matrix.T, list(doses), list(focuses), target_cd=ns["target_cd"], tolerance=0.1
    )
    assert ref["el_pct"] > 0.0
    assert ns["el"] == pytest.approx(ref["el_pct"], rel=1e-12)
    assert ns["dof"] == pytest.approx(ref["dof_nm"], rel=1e-12)
