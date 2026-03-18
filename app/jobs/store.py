"""
File-backed job store — persists job state to disk so audits survive server restarts.
Thread-safe with a lock around all file reads/writes.
Jobs older than 24 hours are pruned automatically on each new job creation.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_JOBS_FILE = os.path.join(_DATA_DIR, "jobs.json")
_lock = Lock()

# Ensure data directory and jobs file exist at import time
os.makedirs(_DATA_DIR, exist_ok=True)
if not os.path.exists(_JOBS_FILE):
    with open(_JOBS_FILE, "w", encoding="utf-8") as _f:
        json.dump({}, _f)


def _read() -> dict:
    try:
        with open(_JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _write(store: dict) -> None:
    with open(_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prune(store: dict) -> dict:
    """Drop jobs older than 24 hours to keep the file small."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return {
        job_id: job
        for job_id, job in store.items()
        if datetime.fromisoformat(job["created_at"]) > cutoff
    }


def create_job(job_id: str) -> dict:
    record = {
        "job_id": job_id,
        "status": "queued",
        "progress": {"stage": "queued", "claims_done": 0, "claims_total": 0},
        "results": None,
        "error": None,
        "created_at": _now(),
        "completed_at": None,
    }
    with _lock:
        store = _prune(_read())
        store[job_id] = record
        _write(store)
    return record


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        return _read().get(job_id)


def set_processing(
    job_id: str,
    stage: str,
    claims_done: int = 0,
    claims_total: int = 0,
) -> None:
    with _lock:
        store = _read()
        if job_id in store:
            store[job_id]["status"] = "processing"
            store[job_id]["progress"] = {
                "stage": stage,
                "claims_done": claims_done,
                "claims_total": claims_total,
            }
            _write(store)


def set_complete(job_id: str, results: dict) -> None:
    with _lock:
        store = _read()
        if job_id in store:
            store[job_id]["status"] = "complete"
            store[job_id]["results"] = results
            store[job_id]["completed_at"] = _now()
            _write(store)


def set_failed(job_id: str, error: str) -> None:
    with _lock:
        store = _read()
        if job_id in store:
            store[job_id]["status"] = "failed"
            store[job_id]["error"] = error
            store[job_id]["completed_at"] = _now()
            _write(store)
