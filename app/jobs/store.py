"""
In-memory job store — thread-safe dict keyed by job_id.
Tracks status, progress, and results for each audit job.
"""

from datetime import datetime, timezone
from threading import Lock
from typing import Optional

_store: dict[str, dict] = {}
_lock = Lock()


def create_job(job_id: str) -> dict:
    record = {
        "job_id": job_id,
        "status": "queued",
        "progress": {"stage": "queued", "claims_done": 0, "claims_total": 0},
        "results": None,
        "error": None,
        "created_at": datetime.now(timezone.utc),
        "completed_at": None,
    }
    with _lock:
        _store[job_id] = record
    return record


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        return _store.get(job_id)


def set_processing(
    job_id: str,
    stage: str,
    claims_done: int = 0,
    claims_total: int = 0,
) -> None:
    with _lock:
        if job_id in _store:
            _store[job_id]["status"] = "processing"
            _store[job_id]["progress"] = {
                "stage": stage,
                "claims_done": claims_done,
                "claims_total": claims_total,
            }


def set_complete(job_id: str, results: dict) -> None:
    with _lock:
        if job_id in _store:
            _store[job_id]["status"] = "complete"
            _store[job_id]["results"] = results
            _store[job_id]["completed_at"] = datetime.now(timezone.utc)


def set_failed(job_id: str, error: str) -> None:
    with _lock:
        if job_id in _store:
            _store[job_id]["status"] = "failed"
            _store[job_id]["error"] = error
            _store[job_id]["completed_at"] = datetime.now(timezone.utc)
