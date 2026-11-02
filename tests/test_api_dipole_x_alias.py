"""Regression guard: the REST API and GUI accept illumination_shape 'dipole_x'.

The pipeline treats 'dipole_x' as an alias of 'dipole' (aerial/abbe.py), and
AGENTS.md lists it for SimulationConfig.illumination_shape, but the field
catalogue's choices omitted it: physics_errors() returned
['illumination_shape unknown'] and POST /simulate answered 422.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from euvsimulator.api.fields import FIELDS, physics_errors
from euvsimulator.api.main import app
from euvsimulator.pipeline import SimulationConfig

APP_JS = (
    Path(__file__).resolve().parent.parent / "src" / "euvsimulator" / "api" / "static" / "app.js"
)


def test_physics_errors_accepts_dipole_x() -> None:
    assert "dipole_x" in FIELDS["illumination_shape"]["choices"]
    assert physics_errors(SimulationConfig(illumination_shape="dipole_x")) == []


def test_rest_simulate_accepts_dipole_x() -> None:
    body = {"config": {"illumination_shape": "dipole_x", "grid": 32}}
    resp = TestClient(app).post("/simulate", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["config"]["illumination_shape"] == "dipole_x"


def test_gui_shows_pole_opening_for_every_multipole_choice() -> None:
    """app.js shows pole_opening_deg for each dipole/quasar choice of the catalogue."""
    js = APP_JS.read_text(encoding="utf-8")
    m = re.search(r"pole_opening_deg: \[([^\]]*)\]\.includes", js)
    assert m, "app.js: no pole_opening_deg visibility rule"
    listed = set(re.findall(r"'([^']+)'", m.group(1)))
    multipole = {
        c for c in FIELDS["illumination_shape"]["choices"] if c.startswith(("dipole", "quasar"))
    }
    assert multipole <= listed, multipole - listed
