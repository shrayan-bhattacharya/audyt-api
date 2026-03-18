from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class JobProgress(BaseModel):
    stage: str
    claims_done: int = 0
    claims_total: int = 0


class ClaimResult(BaseModel):
    claim_number: int
    claim: str
    verdict: str
    confidence: str
    citation: Optional[str] = None
    explanation: str
    source_says: Optional[str] = None
    distance: Optional[float] = None
    sources_checked: int


class AuditSummary(BaseModel):
    total_claims: int
    correct_count: int
    incorrect_count: int
    unverifiable_count: int
    accuracy_rate: float
    trust_score: float
    high_confidence_count: int


class AuditResults(BaseModel):
    summary: AuditSummary
    claims: list[ClaimResult]


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: Optional[JobProgress] = None
    results: Optional[AuditResults] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class StartAuditResponse(BaseModel):
    job_id: str
    status: str
