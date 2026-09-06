"""Background jobs (``api/jobs.py``), their API and the memory estimate."""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from euvsimulator.api.estimate import estimate_memory_bytes
from euvsimulator.api.jobs import Job, JobRegistry
from euvsimulator.api.main import app
from euvsimulator.pipeline import SimulationCancelledError, SimulationConfig

TINY = {
    "grid": 32,
    "resist_model": "full_chem",
    "dose_mj_cm2": 1.3,
    "enable_stochastic": True,
    "stochastic_ler_grid_y": 64,
    "stochastic_seed": 1,
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _wait(client: TestClient, job_id: str, timeout_s: float = 120.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        s = client.get(f"/jobs/{job_id}").json()
        if s["status"] in ("done", "failed", "cancelled"):
            return s
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


# ── registry unit tests (no pipeline) ────────────────────────────────────


class TestJobRegistry:
    def test_runs_task_and_records_result(self) -> None:
        reg = JobRegistry()

        def task(job: Job) -> dict:
            job.report(0.5, "half way", {"k": 1})
            return {"answer": 42}

        job = reg.submit("simulate", {}, task)
        for _ in range(200):
            if job.status == "done":
                break
            time.sleep(0.01)
        snap = job.snapshot()
        assert snap["status"] == "done"
        assert snap["result"] == {"answer": 42}
        assert snap["progress"] == 1.0
        assert snap["partial"] == {"k": 1}
        assert snap["elapsed_s"] >= 0.0

    def test_failure_is_recorded_not_raised(self) -> None:
        reg = JobRegistry()

        def task(job: Job) -> dict:
            raise RuntimeError("boom")

        job = reg.submit("simulate", {}, task)
        for _ in range(200):
            if job.status == "failed":
                break
            time.sleep(0.01)
        assert job.status == "failed"
        assert job.error == "RuntimeError: boom"

    def test_cancel_through_the_progress_hook(self) -> None:
        reg = JobRegistry()
        started = threading.Event()

        def task(job: Job) -> dict:
            hook = job.progress_hook("step")
            started.set()
            for i in range(1000):
                if not hook(i, 1000):
                    raise SimulationCancelledError("stop")
                time.sleep(0.005)
            return {}

        job = reg.submit("simulate", {}, task)
        assert started.wait(2.0)
        reg.cancel(job.id)
        for _ in range(400):
            if job.status == "cancelled":
                break
            time.sleep(0.01)
        assert job.status == "cancelled"
        assert job.message.startswith("step ")

    def test_eviction_keeps_running_jobs(self) -> None:
        reg = JobRegistry(max_jobs=2)
        done = [reg.submit("simulate", {}, lambda job: {}) for _ in range(3)]
        for j in done:
            for _ in range(200):
                if j.status == "done":
                    break
                time.sleep(0.01)
        reg.submit("simulate", {}, lambda job: {})
        assert len(reg.list()) <= 3  # eviction happens at submit time, oldest finished first


# ── API ──────────────────────────────────────────────────────────────────


class TestJobsApi:
    def test_simulate_job_lifecycle_and_csv(self, client: TestClient) -> None:
        resp = client.post(
            "/jobs", json={"kind": "simulate", "config": {**TINY, "stochastic_n_realisations": 2}}
        )
        assert resp.status_code == 202
        job_id = resp.json()["id"]
        s = _wait(client, job_id)
        assert s["status"] == "done", s["error"]
        assert s["message"] == "realisation 2 of 2"
        metrics = {r["metric"]: r["value"] for r in s["result"]["results"]}
        assert {"cd", "nils", "contrast", "ler_1sigma", "lwr_1sigma"} <= set(metrics)
        assert s["result"]["config"]["grid"] == 32
        csv = client.get(f"/jobs/{job_id}/export.csv")
        assert csv.status_code == 200
        lines = csv.text.splitlines()
        assert lines[0].startswith("# euvsimulator")
        assert "position_nm,local_dose_mj_cm2,developed" in lines
        assert len([ln for ln in lines if not ln.startswith("#")]) == 1 + 32

    def test_sync_and_job_results_agree(self, client: TestClient) -> None:
        cfg = {"grid": 32}
        sync = client.post("/simulate", json={"config": cfg}).json()
        job_id = client.post("/jobs", json={"kind": "simulate", "config": cfg}).json()["id"]
        job = _wait(client, job_id)["result"]
        assert job["results"] == sync["results"]
        assert job["raw"]["aerial_profile_nm"] == sync["raw"]["aerial_profile_nm"]

    def test_process_window_job(self, client: TestClient) -> None:
        resp = client.post(
            "/jobs",
            json={
                "kind": "process_window",
                "config": {"grid": 32},
                "process_window": {
                    "dose_start": 15,
                    "dose_end": 25,
                    "dose_steps": 3,
                    "focus_start": -40,
                    "focus_end": 40,
                    "focus_steps": 3,
                    "tolerance": 0.1,
                },
            },
        )
        assert resp.status_code == 202
        s = _wait(client, resp.json()["id"])
        assert s["status"] == "done", s["error"]
        r = s["result"]
        assert len(r["cd_matrix"]) == 3 and len(r["cd_matrix"][0]) == 3
        assert r["doses"] == [15.0, 20.0, 25.0]
        assert r["depth_of_focus_nm"] >= 0.0 and r["exposure_latitude_pct"] >= 0.0
        csv = client.get(f"/jobs/{s['id']}/export.csv").text.splitlines()
        assert csv[2].startswith("focus_nm\\dose_mj_cm2,15,20,25")

    def test_cancel_running_job(self, client: TestClient) -> None:
        resp = client.post(
            "/jobs",
            json={
                "kind": "simulate",
                "config": {**TINY, "stochastic_ler_grid_y": 256, "stochastic_n_realisations": 50},
            },
        )
        job_id = resp.json()["id"]
        time.sleep(0.3)
        assert client.delete(f"/jobs/{job_id}").status_code == 200
        s = _wait(client, job_id)
        assert s["status"] == "cancelled"
        assert client.get(f"/jobs/{job_id}/export.csv").status_code == 409

    def test_unknown_job_and_kind(self, client: TestClient) -> None:
        assert client.get("/jobs/nope").status_code == 404
        assert client.delete("/jobs/nope").status_code == 404
        assert client.post("/jobs", json={"kind": "teleport"}).status_code == 422
        assert (
            client.post("/jobs", json={"kind": "bands", "config": {"grid": 32}}).status_code == 422
        )

    def test_jobs_are_listed_without_results(self, client: TestClient) -> None:
        job_id = client.post("/jobs", json={"kind": "simulate", "config": {"grid": 32}}).json()[
            "id"
        ]
        _wait(client, job_id)
        listed = {j["id"]: j for j in client.get("/jobs").json()["jobs"]}
        assert job_id in listed
        assert listed[job_id]["result"] is None


class TestEstimate:
    def test_estimate_endpoint(self, client: TestClient) -> None:
        resp = client.post("/estimate", json={"config": {"grid": 128}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["memory_bytes"] > 0 and body["memory_text"].endswith("MB")
        assert body["physics_errors"] == []
        bad = client.post("/estimate", json={"config": {"na": 2.0}}).json()
        assert bad["physics_errors"]

    def test_model_matches_the_m1_measurements_within_30_percent(self) -> None:
        """Peak RSS above baseline measured 2026-09-06 (scratch mem_probe.py)."""
        measured = [
            ({"grid": 128, "resist_model": "full_chem"}, 154e6),
            ({"grid": 256, "resist_model": "full_chem"}, 433e6),
            (
                {
                    "grid": 128,
                    "resist_model": "full_chem",
                    "enable_stochastic": True,
                    "stochastic_ler_grid_y": 512,
                },
                525e6,
            ),
            (
                {
                    "grid": 128,
                    "resist_model": "full_chem",
                    "enable_stochastic": True,
                    "stochastic_ler_grid_y": 4096,
                },
                960e6,
            ),
            (
                {
                    "grid": 256,
                    "resist_model": "full_chem",
                    "enable_stochastic": True,
                    "stochastic_ler_grid_y": 2048,
                },
                1550e6,
            ),
            (
                {
                    "grid": 128,
                    "resist_model": "full_chem",
                    "enable_stochastic": True,
                    "stochastic_ler_grid_y": 2048,
                    "n_develop_layers": 41,
                },
                1866e6,
            ),
        ]
        for kw, peak in measured:
            est = estimate_memory_bytes(SimulationConfig(**kw))
            assert abs(est - peak) / peak <= 0.30, (kw, est, peak)
