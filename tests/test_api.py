"""
Tests for the OpEnUV REST API (``euv.api.main``).

Uses FastAPI's ``TestClient`` to exercise all four endpoints:
- ``GET /health``
- ``POST /simulate``
- ``GET /materials``
- ``POST /materials/nk``
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from euv.api.main import app


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client bound to the OpEnUV app."""
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
    """``POST /simulate`` — simulation pipeline."""

    def test_default_config(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert "config" in body
        assert "results" in body
        assert len(body["results"]) > 0

    def test_custom_config(self, client: TestClient) -> None:
        payload = {
            "config": {
                "aerial": {"na": 0.55, "illumination_shape": "dipole"},
                "mask": {"pitch_nm": 32.0, "cd_nm": 14.0, "absorber_material": "Au"},
                "resist": {"resist_type": "MOR", "dose_mJ_cm2": 30.0},
            }
        }
        resp = client.post("/simulate", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["config"]["aerial"]["na"] == 0.55
        assert body["config"]["mask"]["pitch_nm"] == 32.0
        assert body["config"]["resist"]["resist_type"] == "MOR"

    def test_invalid_na_rejected(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {"aerial": {"na": 99.0}}})
        # Pydantic validation via FastAPI returns 422
        assert resp.status_code == 422

    def test_invalid_mask_pitch(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {"mask": {"pitch_nm": -5}}})
        assert resp.status_code == 422

    def test_results_contain_expected_metrics(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {}})
        results = resp.json()["results"]
        metrics = {(r["stage"], r["metric"]) for r in results}
        assert ("aerial", "nils") in metrics


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
        assert schema["info"]["title"] == "OpEnUV — Open Source EUV Lithography Simulator"
        assert "/health" in schema["paths"]
        assert "/simulate" in schema["paths"]
        assert "/materials" in schema["paths"]
        assert "/materials/nk" in schema["paths"]