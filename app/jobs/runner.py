"""
Audit job runner — orchestrates the full pipeline end-to-end.
Called as a FastAPI BackgroundTask; updates job_store at each stage.

Pipeline:
  1. Parse source files  → blocks
  2. Chunk + embed       → ChromaDB collection
  3. Extract claims      → list of {claim_number, claim_text}
  4. Verify each claim   → CORRECT / INCORRECT / UNVERIFIABLE + citation
  5. Generate report     → summary dict, plain-text report, CSV
"""

import gc
from typing import Optional

from app.services.parser import parse_uploaded_file
from app.services.embedder import chunk_with_metadata, create_vector_store
from app.services.extractor import extract_claims
from app.services.verifier import verify_claim
from app.services.reporter import generate_report_summary, format_report_text, generate_csv_report
from app.jobs import store as job_store


def run_audit(
    job_id: str,
    source_file_data: list[tuple[str, bytes]],
    report_text: str,
    context: str,
    api_key: str,
    user_email: Optional[str] = None,
    source_filenames: Optional[list[str]] = None,
) -> None:
    collection = None
    chroma_client = None
    try:
        # ── 1. Parse source documents ──────────────────────────────────────────
        job_store.set_processing(job_id, stage="parsing_sources")
        all_blocks: list[dict] = []
        for filename, content in source_file_data:
            blocks = parse_uploaded_file(filename, content)
            all_blocks.extend(blocks)

        if not all_blocks:
            raise ValueError("No text could be extracted from the source documents.")

        # ── 2. Chunk + embed into ChromaDB ─────────────────────────────────────
        job_store.set_processing(job_id, stage="embedding")
        chunks = chunk_with_metadata(all_blocks)
        collection, chroma_client, _ = create_vector_store(chunks)

        # ── 3. Extract verifiable claims from the report ───────────────────────
        job_store.set_processing(job_id, stage="extracting_claims")
        claims = extract_claims(report_text, api_key, context=context)

        if not claims:
            raise ValueError("No verifiable factual claims were extracted from the report.")

        # ── 4. Verify each claim (progress updated per claim) ──────────────────
        results: list[dict] = []
        total = len(claims)
        for i, claim in enumerate(claims):
            job_store.set_processing(
                job_id,
                stage="verifying_claims",
                claims_done=i,
                claims_total=total,
            )
            result = verify_claim(
                claim["claim_text"],
                collection,
                api_key,
                context=context,
            )
            result["claim_number"] = claim["claim_number"]
            results.append(result)

        # ── 5. Generate report artifacts ───────────────────────────────────────
        job_store.set_processing(
            job_id, stage="generating_report",
            claims_done=total, claims_total=total,
        )
        summary = generate_report_summary(results)
        report_text_out = format_report_text(summary)
        report_csv = generate_csv_report(results)

        job_store.set_complete(job_id, {
            "summary": {
                "total_claims":         summary["total_claims"],
                "correct_count":        summary["correct_count"],
                "incorrect_count":      summary["incorrect_count"],
                "unverifiable_count":   summary["unverifiable_count"],
                "accuracy_rate":        summary["accuracy_rate"],
                "trust_score":          summary["trust_score"],
                "high_confidence_count": summary["high_confidence_count"],
            },
            "claims":      results,
            "report_text": report_text_out,
            "report_csv":  report_csv,
        })

        if user_email:
            from app.services.user_store import save_audit_to_history
            save_audit_to_history(user_email, job_id, {
                **summary,
                "filename_hints": source_filenames or [],
            })

    except Exception as exc:
        job_store.set_failed(job_id, str(exc))
    finally:
        try:
            if chroma_client is not None and collection is not None:
                chroma_client.delete_collection(collection.name)
            collection = None
            chroma_client = None
            gc.collect()
            print(f"Memory cleanup complete for job {job_id}")
        except Exception:
            pass
