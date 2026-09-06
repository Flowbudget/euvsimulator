"""Background jobs for the REST API / browser GUI.

A job runs one task (a simulation, a process window, the structural bands)
in a worker thread while the HTTP server stays responsive. Clients poll
``GET /jobs/{id}`` for progress and results and may ``DELETE`` a job to
cancel it. Cancellation is cooperative: the pipeline's progress hook is
checked before each stochastic realisation, and the process-window and
bands loops check it between simulations, so a cancel takes effect at the
next such point and never in the middle of a single deterministic run.

The registry is in-memory and per process (no persistence); finished jobs
are kept until the registry exceeds :data:`MAX_JOBS` and then dropped
oldest first.
"""

from __future__ import annotations

import dataclasses
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional

from euvsimulator.pipeline import SimulationCancelledError

MAX_JOBS = 50

# task(job) -> result dict; the task reports through job.report(...) and
# checks job.cancel_requested (or uses job.progress_hook()).
TaskFn = Callable[["Job"], Dict[str, Any]]


@dataclasses.dataclass
class Job:
    """One background task with its progress and outcome."""

    id: str
    kind: str
    request: Dict[str, Any]
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0  # 0..1
    message: str = ""
    partial: Dict[str, Any] = dataclasses.field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = dataclasses.field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_requested: bool = False
    _lock: threading.Lock = dataclasses.field(default_factory=threading.Lock, repr=False)

    def report(
        self, progress: float, message: str = "", partial: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update progress (0..1), a message and optional partial results."""
        with self._lock:
            self.progress = max(0.0, min(1.0, float(progress)))
            if message:
                self.message = message
            if partial:
                self.partial.update(partial)

    def progress_hook(self, label: str = "realisation") -> Callable[[int, int], bool]:
        """A ``run_simulation(progress=...)`` hook bound to this job."""

        def hook(done: int, total: int) -> bool:
            self.report(done / max(total, 1), f"{label} {done + 1} of {total}")
            return not self.cancel_requested

        return hook

    def snapshot(self) -> Dict[str, Any]:
        """JSON-friendly view for the API."""
        with self._lock:
            elapsed = (self.finished_at or time.time()) - (self.started_at or self.created_at)
            return {
                "id": self.id,
                "kind": self.kind,
                "request": self.request,
                "status": self.status,
                "progress": self.progress,
                "message": self.message,
                "partial": dict(self.partial),
                "result": self.result,
                "error": self.error,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "elapsed_s": elapsed if self.started_at else 0.0,
                "cancel_requested": self.cancel_requested,
            }


class JobRegistry:
    """Thread-safe registry that runs one worker thread per job."""

    def __init__(self, max_jobs: int = MAX_JOBS) -> None:
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def submit(self, kind: str, request: Dict[str, Any], task: TaskFn) -> Job:
        """Register a job and start its worker thread."""
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, request=request)
        with self._lock:
            self._jobs[job.id] = job
            self._evict_locked()
        thread = threading.Thread(target=self._run, args=(job, task), daemon=True, name=job.id)
        thread.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        """The job with this id, or None."""
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> List[Job]:
        """All jobs, oldest first."""
        with self._lock:
            return list(self._jobs.values())

    def cancel(self, job_id: str) -> Optional[Job]:
        """Request cancellation; a queued job is cancelled at once."""
        job = self.get(job_id)
        if job is None:
            return None
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = time.time()
        return job

    def _evict_locked(self) -> None:
        finished = [j for j in self._jobs.values() if j.status in ("done", "failed", "cancelled")]
        while len(self._jobs) > self._max_jobs and finished:
            victim = finished.pop(0)
            self._jobs.pop(victim.id, None)

    @staticmethod
    def _run(job: Job, task: TaskFn) -> None:
        if job.cancel_requested:
            return
        job.status = "running"
        job.started_at = time.time()
        try:
            result = task(job)
            if job.cancel_requested:
                job.status = "cancelled"
            else:
                job.result = result
                job.status = "done"
                job.progress = 1.0
        except SimulationCancelledError:
            job.status = "cancelled"
        except Exception as exc:  # the job must record every failure
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
        finally:
            job.finished_at = time.time()


REGISTRY = JobRegistry()
