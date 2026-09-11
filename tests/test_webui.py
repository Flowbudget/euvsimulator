"""Tests for the browser GUI (static files, routing, self-containment) and the
API-to-pipeline mapping the GUI relies on.
"""

from __future__ import annotations

import inspect
import os
import re

import pytest
from fastapi.testclient import TestClient

import euvsimulator.api.main as api_main
from euvsimulator.api.main import app
from euvsimulator.pipeline import SimulationConfig as PipelineConfig

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(HERE, "src", "euvsimulator", "api", "static")
STATIC_FILES = ["index.html", "style.css", "app.js"]


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestStaticFiles:
    @pytest.mark.parametrize("filename", STATIC_FILES)
    def test_exists_and_nonempty(self, filename: str) -> None:
        path = os.path.join(STATIC_DIR, filename)
        assert os.path.isfile(path), path
        assert os.path.getsize(path) > 0, path

    def test_only_the_single_page_ships(self) -> None:
        """Stage 1 collapsed the two pages into one; no second HTML page may reappear."""
        html = [f for f in os.listdir(STATIC_DIR) if f.endswith(".html")]
        assert html == ["index.html"], html

    @pytest.mark.parametrize("filename", STATIC_FILES)
    def test_no_external_assets_and_no_old_name(self, filename: str) -> None:
        """The GUI must work offline: no CDN scripts or styles."""
        with open(os.path.join(STATIC_DIR, filename), encoding="utf-8") as fh:
            text = fh.read()
        urls = re.findall(r"https?://[^\s\"'<>)]+", text)
        allowed = ("https://github.com/Flowbudget/euvsimulator", "http://www.w3.org/2000/svg")
        offenders = [u for u in urls if not u.startswith(allowed)]
        assert not offenders, offenders
        assert "cdn." not in text.lower()


class TestRouting:
    def test_index_is_served_at_root(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<title>euvsimulator</title>" in resp.text
        assert "/static/style.css" in resp.text
        assert "/static/app.js" in resp.text

    def test_old_simulate_page_redirects_to_root(self, client: TestClient) -> None:
        resp = client.get("/simulate", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/"

    def test_style_css_is_served(self, client: TestClient) -> None:
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_app_js_is_served(self, client: TestClient) -> None:
        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]
        expected = (
            "fetchHealth",
            "fetchMaterials",
            "startJob",
            "pollJob",
            "drawProfile",
            "buildForm",
        )
        for fn in expected:
            assert fn in resp.text, fn

    def test_unknown_static_file_returns_404(self, client: TestClient) -> None:
        assert client.get("/static/nonexistent.js").status_code == 404


class TestSimulateEndpoint:
    def test_is_sync_so_fastapi_uses_the_threadpool(self) -> None:
        """A long pipeline run must not block the event loop (health polling, other users)."""
        assert not inspect.iscoroutinefunction(api_main.run_simulation)

    def test_defaults_are_the_pipeline_defaults(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {"grid": 32}})
        assert resp.status_code == 200
        cfg = resp.json()["config"]
        ref = PipelineConfig()
        for name in ("na", "sigma", "period_nm", "line_width_nm", "dose_mj_cm2", "device"):
            assert cfg[name] == getattr(ref, name), name

    @pytest.mark.parametrize(
        "config",
        [
            {"period_nm": 32.0, "line_width_nm": 40.0},  # CD >= pitch
            {"na": 1.0},  # NA must be < 1
            {"sigma": 0.5, "sigma_inner": 0.6},
            {"resist_threshold_norm": 1.0},
            {"mack_n": 1.0},
            {"ler_passband_nm": [800.0, 10.0]},
        ],
    )
    def test_unphysical_requests_are_rejected(self, client: TestClient, config: dict) -> None:
        assert client.post("/simulate", json={"config": config}).status_code == 422

    def test_no_cosmetic_limits(self, client: TestClient) -> None:
        """Large numerical sizes are accepted (validated only, run kept tiny)."""
        from euvsimulator.api.fields import physics_errors, resolve_config

        cfg = resolve_config(None, {"grid": 8192, "stochastic_ler_grid_y": 10**6})
        assert physics_errors(cfg) == []

    def test_threshold_intensity_is_the_one_used_for_cd(self, client: TestClient) -> None:
        """The plotted threshold equals pipeline._cd_via_aerial_threshold's value."""
        from euvsimulator.pipeline import AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2

        resp = client.post(
            "/simulate", json={"config": {"dose_mj_cm2": 10.0, "resist_threshold_norm": 0.4}}
        )
        assert resp.status_code == 200
        raw = resp.json()["raw"]
        profile = raw["aerial_profile_nm"]
        assert len(profile) == raw["grid"]
        # mean over the centre row equals the 2D mean for a 1D line/space image
        mean = sum(profile) / len(profile)
        expected = 0.4 * mean * (AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2 / 10.0)
        assert raw["threshold_intensity"] == pytest.approx(expected, rel=1e-6)

    def test_full_chem_has_no_threshold_line(self, client: TestClient) -> None:
        resp = client.post(
            "/simulate", json={"config": {"resist_model": "full_chem", "dose_mj_cm2": 1.3}}
        )
        assert resp.status_code == 200
        raw = resp.json()["raw"]
        assert "threshold_intensity" not in raw
        assert set(raw["resist_profile"]) <= {0.0, 1.0}

    def test_stochastic_run_reports_ler_and_lwr(self, client: TestClient) -> None:
        resp = client.post(
            "/simulate",
            json={
                "config": {
                    "grid": 64,
                    "resist_model": "full_chem",
                    "dose_mj_cm2": 1.3,
                    "enable_stochastic": True,
                    "stochastic_ler_grid_y": 256,
                    "stochastic_seed": 1,
                }
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        metrics = {r["metric"]: r["value"] for r in body["results"]}
        assert metrics["ler_1sigma"] > 0 and metrics["lwr_1sigma"] > 0
        assert any("SEM bias" in n for n in body["notes"])


class TestExistingApiStillWorks:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_simulate_default(self, client: TestClient) -> None:
        resp = client.post("/simulate", json={"config": {}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_materials_list(self, client: TestClient) -> None:
        resp = client.get("/materials")
        assert resp.status_code == 200
        assert "count" in resp.json()
