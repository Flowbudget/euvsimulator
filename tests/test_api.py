"""Tests for the euvsimulator REST API (``euvsimulator.api.main``).

Uses FastAPI's ``TestClient`` to exercise the endpoints:
- ``GET /health``
- ``GET /presets``, ``GET /fields``
- ``POST /simulate``
- ``GET /materials``
- ``POST /materials/nk``
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from euvsimulator.api.main import app

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client bound to the euvsimulator app."""
    return TestClient(app)


# ──────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────


class TestHealth:
    """``GET /health`` — service health check."""

    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    def test_returns_json_content_type(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers["content-type"] == "application/json"


# ──────────────────────────────────────────────
# POST /simulate
# ──────────────────────────────────────────────


class TestSimulate:
    """``POST /simulate`` — simulation pipeline (preset + flat overrides)."""

    def test_default_config(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["preset"] == "default"
        assert body["config"]["period_nm"] == 64.0
        assert len(body["results"]) > 0
        assert body["notes"]

    def test_overrides_are_applied_and_echoed(self, client: TestClient) -> None:
        payload = {
            "config": {
                "na": 0.55,
                "illumination_shape": "dipole",
                "period_nm": 32.0,
                "line_width_nm": 14.0,
                "absorber_material": "Au",
                "dose_mj_cm2": 30.0,
                "grid": 64,
            }
        }
        resp = client.post("/simulate", json=payload)
        assert resp.status_code == 200
        cfg = resp.json()["config"]
        for k, v in payload["config"].items():
            assert cfg[k] == v, k
        assert cfg["sigma"] == 0.8  # untouched default survives

    def test_preset_with_override(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"preset": "met2d", "config": {"grid": 64}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["preset"] == "met2d"
        assert body["config"]["na"] == 0.30
        assert body["config"]["grid"] == 64
        assert "Sekiguchi" in body["notes"][0]

    def test_unknown_preset_rejected(self, client: TestClient) -> None:
        assert client.post("/simulate", json={"preset": "nope"}).status_code == 422

    def test_unknown_field_rejected(self, client: TestClient) -> None:
        assert client.post("/simulate", json={"config": {"not_a_field": 1}}).status_code == 422

    def test_invalid_na_rejected(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {"na": 99.0}})
        assert resp.status_code == 422
        assert "na" in resp.json()["detail"]

    def test_invalid_pitch_rejected(self, client: TestClient) -> None:
        assert client.post("/simulate", json={"config": {"period_nm": -5}}).status_code == 422

    def test_dataclass_validation_becomes_422(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {"enable_stochastic": True}})
        assert resp.status_code == 422
        assert "full_chem" in resp.json()["detail"]

    def test_results_contain_expected_metrics(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={})
        metrics = {(r["stage"], r["metric"]) for r in resp.json()["results"]}
        assert ("aerial", "nils") in metrics
        assert ("resist", "cd") in metrics


class TestPresetsAndFields:
    def test_presets_listed_with_provenance_and_config(self, client: TestClient) -> None:
        resp = client.get("/presets")
        assert resp.status_code == 200
        presets = {p["key"]: p for p in resp.json()["presets"]}
        assert set(presets) == {"default", "nxe1716", "nxe1716_calibrated", "met2d"}
        assert presets["nxe1716"]["config"]["period_nm"] == 44.0
        assert "19.7" in presets["nxe1716"]["provenance"]
        assert "calibration" in presets["nxe1716_calibrated"]["provenance"]
        assert (
            presets["nxe1716_calibrated"]["config"]["peb_k"] > presets["nxe1716"]["config"]["peb_k"]
        )

    def test_fields_cover_the_dataclass(self, client: TestClient) -> None:
        import dataclasses

        from euvsimulator.pipeline import SimulationConfig

        resp = client.get("/fields")
        assert resp.status_code == 200
        body = resp.json()
        names = [f["name"] for f in body["fields"]]
        assert names == [f.name for f in dataclasses.fields(SimulationConfig)]
        assert set(f["group"] for f in body["fields"]) <= set(body["groups"])
        assert sum(f["head"] for f in body["fields"]) == 6


# ──────────────────────────────────────────────
# GET /materials
# ──────────────────────────────────────────────


class TestListMaterials:
    """``GET /materials`` — available CXRO materials."""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/materials")
        assert resp.status_code == 200

    def test_has_count_and_elements(self, client: TestClient) -> None:
        resp = client.get("/materials")
        body = resp.json()
        assert "count" in body
        assert "elements" in body
        # Even without CXRO CSVs, the list will be empty — unpacking is fine
        assert isinstance(body["elements"], list)

    def test_elements_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/materials")
        body = resp.json()
        for el in body["elements"]:
            assert "symbol" in el
            assert "z" in el
            assert "atomic_mass_g_mol" in el
            assert "density_g_cm3" in el


# ──────────────────────────────────────────────
# POST /materials/nk
# ──────────────────────────────────────────────


class TestNkEndpoint:
    """``POST /materials/nk`` — refractive index."""

    def test_unknown_element_returns_404(self, client: TestClient) -> None:
        resp = client.post("/materials/nk", json={"symbol": "Xx"})
        assert resp.status_code == 404

    def test_valid_element_with_cxro_data(self, client: TestClient) -> None:
        """Mo (molybdenum) is a standard EUV multilayer material — expect 200."""
        resp = client.post("/materials/nk", json={"symbol": "Mo"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "Mo"
        assert body["energy_eV"] == 91.84
        assert isinstance(body["n"], float)
        assert isinstance(body["k"], float)
        assert body["delta"] == pytest.approx(1.0 - body["n"])

    def test_empty_symbol_rejected(self, client: TestClient) -> None:
        resp = client.post("/materials/nk", json={"symbol": ""})
        assert resp.status_code == 422

    def test_long_symbol_rejected(self, client: TestClient) -> None:
        resp = client.post("/materials/nk", json={"symbol": "ABCDE"})
        assert resp.status_code == 422

    def test_negative_energy_rejected(self, client: TestClient) -> None:
        resp = client.post("/materials/nk", json={"symbol": "Si", "energy_eV": -1.0})
        assert resp.status_code == 422

    def test_si_nk_response_shape(self, client: TestClient) -> None:
        """Verify the full response shape for a real element with CXRO data."""
        resp = client.post("/materials/nk", json={"symbol": "Si"})
        assert resp.status_code == 200
        body = resp.json()
        # All required fields present
        assert body["symbol"] == "Si"
        assert body["energy_eV"] == 91.84
        assert isinstance(body["wavelength_nm"], float)
        assert isinstance(body["n"], float)
        assert isinstance(body["k"], float)
        assert isinstance(body["delta"], float)
        assert isinstance(body["density"], float)
        assert isinstance(body["epsilon_real"], float)
        assert isinstance(body["epsilon_imag"], float)
        assert isinstance(body["absorption_length_nm"], float)
        # Physical sanity: n should be slightly less than 1 in the EUV
        assert body["n"] < 1.0
        assert body["k"] > 0.0
        assert body["delta"] > 0.0


# ──────────────────────────────────────────────
# OpenAPI /docs schema
# ──────────────────────────────────────────────


class TestOpenAPI:
    """Verify the FastAPI app generates a valid OpenAPI schema."""

    def test_openapi_schema(self, client: TestClient) -> None:
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "euvsimulator — Open Source EUV Lithography Simulator"
        assert "/health" in schema["paths"]
        assert "/simulate" in schema["paths"]
        assert "/materials" in schema["paths"]
        assert "/materials/nk" in schema["paths"]
