"""
JSON-file storage for users and audit history.
Thread-safety: simple file-level read/write (fine for this scale).
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_USERS_FILE = os.path.join(_DATA_DIR, "users.json")
_AUDITS_FILE = os.path.join(_DATA_DIR, "audits.json")


def _read(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Users ──────────────────────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    return _read(_USERS_FILE)


def get_user_by_email(email: str) -> Optional[dict]:
    return next((u for u in get_all_users() if u["email"] == email), None)


def create_user(email: str, hashed_password: str) -> dict:
    users = get_all_users()
    user = {
        "email": email,
        "hashed_password": hashed_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users.append(user)
    _write(_USERS_FILE, users)
    return user


# ── Audit history ──────────────────────────────────────────────────────────────

def save_audit_to_history(email: str, job_id: str, summary: dict) -> None:
    audits = _read(_AUDITS_FILE)
    record = {
        "email": email,
        "job_id": job_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "filename_hints": summary.get("filename_hints", []),
        "total_claims": summary.get("total_claims", 0),
        "correct": summary.get("correct_count", 0),
        "incorrect": summary.get("incorrect_count", 0),
        "unverifiable": summary.get("unverifiable_count", 0),
        "accuracy_rate": summary.get("accuracy_rate", 0.0),
    }
    audits.append(record)
    _write(_AUDITS_FILE, audits)


def get_user_audits(email: str) -> list[dict]:
    return [a for a in _read(_AUDITS_FILE) if a["email"] == email]
