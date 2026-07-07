"""Tests for the OpEnUV Web UI static files and routing."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from euv.api.main import app

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(HERE, "src", "euv", "api", "static")


# ──────────────────────────────────────────────
# Static file existence
# ──────────────────────────────────────────────


class TestStaticFilesExist:
    """Verify all required static assets are present on disk."""

    STATIC_FILES = [
        "index.html",
        "style.css",
        "app.js",
    ]

    @pytest.mark.parametrize("filename", STATIC_FILES)
    def test_static_file_exists(self, filename: str) -> None:
        path = os.path.join(STATIC_DIR, filename)
        assert os.path.isfile(path), f"Missing static file: {path}"
        assert os.path.getsize(path) > 0, f"Static file is empty: {path}"


# ──────────────────────────────────────────────
# Static file serving
# ──────────────────────────────────────────────


class TestStaticFileServing:
    """Verify the FastAPI app serves the static files correctly."""

    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(app)

    def test_index_html_is_served(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "OpEnUV Dashboard" in resp.text
        assert "/static/style.css" in resp.text
        assert "/static/app.js" in resp.text

    def test_index_html_at_index_html_path(self, client: TestClient) -> None:
        # /index.html is served by StaticFiles at /static/
        resp = client.get("/static/index.html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_style_css_is_served(self, client: TestClient) -> None:
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_app_js_is_served(self, client: TestClient) -> None:
        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "application/javascript" in resp.headers["content-type"] or "text/javascript" in resp.headers["content-type"]
        assert "fetchHealth" in resp.text
        assert "fetchMaterials" in resp.text
        assert "postSimulation" in resp.text

    def test_unknown_static_file_returns_404(self, client: TestClient) -> None:
        resp = client.get("/static/nonexistent.js")
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Existing API endpoints still work
# ──────────────────────────────────────────────


class TestExistingApiStillWorks:
    """Verify the existing REST endpoints are not broken by adding static files."""

    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(app)

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_simulate_still_works(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_materials_list_still_works(self, client: TestClient) -> None:
        resp = client.get("/materials")
        assert resp.status_code == 200
        assert "count" in resp.json()