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
from euvsimulator.api.main import app, pipeline_config_from_request
from euvsimulator.api.schemas import SimulationConfig as ApiConfig
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
        """The GUI must work offline: no CDN scripts/styles, and no 'OpEnUV' leftovers."""
        with open(os.path.join(STATIC_DIR, filename), encoding="utf-8") as fh:
            text = fh.read()
        assert "OpEnUV" not in text
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
        for fn in ("fetchHealth", "fetchMaterials", "postSimulation", "drawProfile"):
            assert fn in resp.text, fn

    def test_unknown_static_file_returns_404(self, client: TestClient) -> None:
        assert client.get("/static/nonexistent.js").status_code == 404


class TestSimulateEndpoint:
    def test_is_sync_so_fastapi_uses_the_threadpool(self) -> None:
        """A long pipeline run must not block the event loop (health polling, other users)."""
        assert not inspect.iscoroutinefunction(api_main.run_simulation)

    def test_every_api_field_reaches_the_pipeline(self) -> None:
        """Each schema field is forwarded to a distinct pipeline field with its value intact."""
        api_cfg = ApiConfig.model_validate(
            {
                "aerial": {
                    "na": 0.55,
                    "illumination_sigma": 0.9,
                    "illumination_shape": "dipole",
                    "inner_sigma": 0.62,
                    "pole_opening_deg": 90.0,
                    "focus_nm": -35.0,
                },
                "mask": {
                    "pitch_nm": 44.0,
                    "cd_nm": 22.0,
                    "absorber_material": "Ni",
                    "absorber_height_nm": 42.0,
                    "capping_material": "Ru",
                    "capping_height_nm": 2.0,
                    "multilayer_pairs": 41,
                    "ml_d_mo_nm": 2.7,
                    "ml_d_si_nm": 4.2,
                    "ml_gamma": 0.42,
                    "ml_grading_linear_nm": 0.03,
                    "ml_grading_parabolic_nm": 0.02,
                    "ml_roughness_nm": 0.25,
                },
                "resist": {
                    "thickness_nm": 35.0,
                    "development_time_s": 45.0,
                    "dose_mJ_cm2": 11.0,
                    "resist_model": "full_chem",
                    "threshold_norm": 0.4,
                },
            }
        )
        expected = {
            "na": 0.55,
            "sigma": 0.9,
            "illumination_shape": "dipole",
            "sigma_inner": 0.62,
            "pole_opening_deg": 90.0,
            "focus_nm": -35.0,
            "period_nm": 44.0,
            "line_width_nm": 22.0,
            "absorber_material": "Ni",
            "absorber_height_nm": 42.0,
            "ml_capping": "Ru",
            "ml_capping_nm": 2.0,
            "ml_n_bilayers": 41,
            "ml_d_mo_nm": 2.7,
            "ml_d_si_nm": 4.2,
            "ml_gamma": 0.42,
            "ml_grading_linear_nm": 0.03,
            "ml_grading_parabolic_nm": 0.02,
            "ml_roughness_nm": 0.25,
            "resist_thickness_nm": 35.0,
            "develop_time_s": 45.0,
            "dose_mj_cm2": 11.0,
            "resist_model": "full_chem",
            "resist_threshold_norm": 0.4,
        }
        pipe = pipeline_config_from_request(api_cfg)
        for name, value in expected.items():
            assert getattr(pipe, name) == value, name
        # Count check: every leaf field of the API schema has a target above.
        n_api_fields = sum(
            len(type(model).model_fields)
            for model in (api_cfg.aerial, api_cfg.mask, api_cfg.resist)
        )
        assert n_api_fields == len(expected)

    def test_defaults_mirror_the_pipeline(self) -> None:
        pipe = pipeline_config_from_request(ApiConfig())
        ref = PipelineConfig()
        for name in (
            "na",
            "sigma",
            "illumination_shape",
            "period_nm",
            "line_width_nm",
            "absorber_material",
            "absorber_height_nm",
            "ml_n_bilayers",
            "ml_d_mo_nm",
            "ml_d_si_nm",
            "dose_mj_cm2",
            "resist_model",
            "resist_threshold_norm",
            "resist_thickness_nm",
            "develop_time_s",
        ):
            assert getattr(pipe, name) == getattr(ref, name), name
        assert pipe.device == ref.device  # not pinned to CPU any more

    @pytest.mark.parametrize(
        "payload",
        [
            {"config": {"mask": {"pitch_nm": 32.0, "cd_nm": 40.0}}},  # CD >= pitch
            {"config": {"aerial": {"na": 1.0}}},  # NA must be < 1
            {"config": {"aerial": {"illumination_sigma": 0.5, "inner_sigma": 0.6}}},
            {"config": {"resist": {"threshold_norm": 1.0}}},
        ],
    )
    def test_unphysical_requests_are_rejected(self, client: TestClient, payload: dict) -> None:
        assert client.post("/simulate", json=payload).status_code == 422

    def test_threshold_intensity_is_the_one_used_for_cd(self, client: TestClient) -> None:
        """The plotted threshold equals pipeline._cd_via_aerial_threshold's value."""
        from euvsimulator.pipeline import AERIAL_THRESHOLD_REFERENCE_DOSE_MJ_CM2

        resp = client.post(
            "/simulate", json={"config": {"resist": {"dose_mJ_cm2": 10.0, "threshold_norm": 0.4}}}
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
            "/simulate",
            json={"config": {"resist": {"resist_model": "full_chem", "dose_mJ_cm2": 1.3}}},
        )
        assert resp.status_code == 200
        raw = resp.json()["raw"]
        assert "threshold_intensity" not in raw
        assert set(raw["resist_profile"]) <= {0.0, 1.0}


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
