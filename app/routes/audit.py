"""
Audyt.ai — audit API routes.

POST /api/v1/audit              Start an audit job (returns job_id immediately)
GET  /api/v1/audit/{job_id}     Poll job status; results included when complete
GET  /api/v1/audit/{job_id}/report/txt   Download plain-text report
GET  /api/v1/audit/{job_id}/report/csv   Download CSV report
"""

import uuid
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.jobs import store as job_store
from app.jobs.runner import run_audit
from app.models.schemas import (
    AuditResults,
    AuditSummary,
    ClaimResult,
    JobProgress,
    JobResponse,
    StartAuditResponse,
)

router = APIRouter(prefix="/api/v1", tags=["audit"])


def _optional_email(request: Request) -> Optional[str]:
    """Extract user email from Bearer token if present — never raises."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        from app.services.auth import decode_token
        return decode_token(auth.split(" ", 1)[1])
    except Exception:
        return None


@router.post("/audit", response_model=StartAuditResponse, status_code=202)
async def start_audit(
    request: Request,
    background_tasks: BackgroundTasks,
    source_files: List[UploadFile] = File(..., description="Source documents (PDF, DOCX, XLSX, TXT)"),
    report_file: Optional[UploadFile] = File(None, description="AI-generated report file (optional)"),
    report_text: Optional[str] = Form(None, description="AI-generated report as plain text (optional)"),
    context: str = Form("", description="Optional context hint about the report domain"),
):
    """
    Start an audit job. Accepts source documents and a report (file or text).
    Returns a job_id immediately; poll GET /api/v1/audit/{job_id} for results.
    """
    # Read all file bytes eagerly — UploadFile is not safe to pass across threads
    source_file_data: list[tuple[str, bytes]] = []
    for f in source_files:
        content = await f.read()
        source_file_data.append((f.filename or "unknown", content))

    if not source_file_data:
        raise HTTPException(status_code=422, detail="At least one source file is required.")

    # Resolve report content from file or pasted text
    final_report_text = ""
    if report_file is not None:
        report_bytes = await report_file.read()
        fname = report_file.filename or "report"
        from app.services.parser import parse_uploaded_file
        try:
            blocks = parse_uploaded_file(fname, report_bytes)
            final_report_text = "\n\n".join(b["text"] for b in blocks if b["text"].strip())
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse report file: {exc}")
    elif report_text:
        final_report_text = report_text.strip()

    if not final_report_text:
        raise HTTPException(
            status_code=422,
            detail="Provide either report_file or report_text.",
        )

    user_email = _optional_email(request)
    source_filenames = [name for name, _ in source_file_data]

    job_id = str(uuid.uuid4())
    job_store.create_job(job_id)

    background_tasks.add_task(
        run_audit,
        job_id=job_id,
        source_file_data=source_file_data,
        report_text=final_report_text,
        context=context or "",
        api_key=settings.anthropic_api_key,
        user_email=user_email,
        source_filenames=source_filenames,
    )

    return {"job_id": job_id, "status": "queued"}


@router.get("/audit/{job_id}", response_model=JobResponse)
def get_audit_status(job_id: str):
    """Poll audit job status. Returns full results when status == 'complete'."""
    record = job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    response: dict = {
        "job_id":       record["job_id"],
        "status":       record["status"],
        "progress":     record["progress"],
        "error":        record["error"],
        "created_at":   record["created_at"],
        "completed_at": record["completed_at"],
        "results":      None,
    }

    if record["status"] == "complete" and record["results"]:
        raw = record["results"]
        s = raw["summary"]
        response["results"] = {
            "summary": {
                "total_claims":          s["total_claims"],
                "correct_count":         s["correct_count"],
                "incorrect_count":       s["incorrect_count"],
                "unverifiable_count":    s["unverifiable_count"],
                "accuracy_rate":         s["accuracy_rate"],
                "trust_score":           s["trust_score"],
                "high_confidence_count": s["high_confidence_count"],
            },
            "claims": [
                {
                    "claim_number":   r.get("claim_number", 0),
                    "claim":          r.get("claim", ""),
                    "verdict":        r.get("verdict", ""),
                    "confidence":     r.get("confidence", "NONE"),
                    "citation":       r.get("citation"),
                    "explanation":    r.get("explanation", ""),
                    "source_says":    r.get("source_says"),
                    "distance":       r.get("distance"),
                    "sources_checked": r.get("sources_checked", 0),
                }
                for r in raw["claims"]
            ],
        }

    return response


@router.get("/audit/{job_id}/report/txt", response_class=PlainTextResponse)
def download_report_txt(job_id: str):
    """Download the plain-text audit report once the job is complete."""
    record = job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if record["status"] != "complete":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete yet (status: {record['status']}).",
        )
    return PlainTextResponse(
        content=record["results"]["report_text"],
        headers={"Content-Disposition": f'attachment; filename="audit_{job_id}.txt"'},
    )


@router.get("/audit/{job_id}/report/csv", response_class=PlainTextResponse)
def download_report_csv(job_id: str):
    """Download the CSV audit report once the job is complete."""
    record = job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if record["status"] != "complete":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete yet (status: {record['status']}).",
        )
    return PlainTextResponse(
        content=record["results"]["report_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit_{job_id}.csv"'},
    )
