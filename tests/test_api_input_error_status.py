"""Regression guard: input errors found inside the pipeline must not be HTTP 500.

The explicit-null and unknown-element cases were fixed earlier (r5-fields-1/2).
Still open before this fix: ``POST /simulate`` turned every exception of
``run_simulation`` into HTTP 500, so an even ``n_rcwa_orders`` with
``use_rcwa`` (RCWAConfig: "n_orders must be odd") and dissolution-cell noise
with the ``column`` development model (NotImplementedError) were reported as
server errors although the request was invalid.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import euvsimulator.api.main as main_mod
from euvsimulator.api.fields import physics_errors, resolve_config

EVEN_RCWA = {"grid": 32, "use_rcwa": True, "n_rcwa_orders": 10}
COLUMN_NOISE = {
    "grid": 32,
    "resist_model": "full_chem",
    "dose_mj_cm2": 1.3,
    "enable_stochastic": True,
    "stochastic_ler_grid_y": 32,
    "stochastic_seed": 1,
    "development_stochasticity": True,
    "development_model": "column",
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main_mod.app)


def test_physics_errors_name_both_cases() -> None:
    # since A73 SimulationConfig itself rejects the even RCWA count (shared rule
    # SimulationConfig.optics_geometry_errors, which physics_errors also reports)
    with pytest.raises(ValueError, match="n_rcwa_orders must be odd"):
        resolve_config(None, EVEN_RCWA)
    cfg = resolve_config(None, {"grid": 32})
    cfg.use_rcwa, cfg.n_rcwa_orders = True, 10  # mutated after validation
    msgs = physics_errors(cfg)
    assert any("n_rcwa_orders" in m and "odd" in m for m in msgs), msgs
    msgs = physics_errors(resolve_config(None, COLUMN_NOISE))
    assert any("development_stochasticity" in m for m in msgs), msgs
    # still valid: odd RCWA counts, an even count on the thin-mask path, and the
    # column model without dissolution-cell noise
    assert physics_errors(resolve_config(None, {**EVEN_RCWA, "n_rcwa_orders": 11})) == []
    assert physics_errors(resolve_config(None, {**EVEN_RCWA, "use_rcwa": False})) == []
    no_noise = {**COLUMN_NOISE, "development_stochasticity": False}
    assert physics_errors(resolve_config(None, no_noise)) == []


@pytest.mark.parametrize("config", [EVEN_RCWA, COLUMN_NOISE], ids=["even-rcwa", "column-noise"])
@pytest.mark.parametrize("path", ["/simulate", "/jobs"])
def test_invalid_combinations_are_422(client: TestClient, path: str, config: dict) -> None:
    # before the fix /simulate answered 500 and /jobs accepted (202) a job that failed
    resp = client.post(path, json={"config": config})
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "exc, status", [(ValueError("bad input"), 422), (NotImplementedError("not here"), 422)]
)
def test_pipeline_input_errors_are_422(client, monkeypatch, exc, status) -> None:
    def raising(cfg, *args, **kwargs):
        raise exc

    monkeypatch.setattr(main_mod, "run_pipeline", raising)
    resp = client.post("/simulate", json={"config": {"grid": 32}})
    assert resp.status_code == status, resp.text
    assert str(exc) in resp.json()["detail"]


def test_other_pipeline_errors_stay_500(client, monkeypatch) -> None:
    def raising(cfg, *args, **kwargs):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(main_mod, "run_pipeline", raising)
    resp = client.post("/simulate", json={"config": {"grid": 32}})
    assert resp.status_code == 500, resp.text
