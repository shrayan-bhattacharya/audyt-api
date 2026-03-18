"""
Audyt.ai — report generation service.

Compiles claim verification results into:
  - A structured summary dict (counts, accuracy/trust scores)
  - A human-readable plain-text report
  - A downloadable CSV string

Identical to the original prototype — no changes needed.
"""

import csv
import io
from datetime import datetime


def generate_report_summary(verification_results: list[dict]) -> dict:
    """
    Aggregates verification results into a summary dictionary.
    Returns counts, accuracy/trust scores, issues list, and sorted full results.
    """
    total     = len(verification_results)
    correct   = [r for r in verification_results if r["verdict"] == "CORRECT"]
    incorrect = [r for r in verification_results if r["verdict"] == "INCORRECT"]
    unverif   = [r for r in verification_results if r["verdict"] == "UNVERIFIABLE"]
    high_conf = [r for r in verification_results if r.get("confidence") == "HIGH"]

    decidable     = len(correct) + len(incorrect)
    accuracy_rate = round(len(correct) / decidable * 100, 1) if decidable else 0.0
    trust_score   = round(len(correct) / total * 100, 1) if total else 0.0

    issues             = incorrect + unverif
    all_results_sorted = incorrect + unverif + correct

    return {
        "total_claims":          total,
        "correct_count":         len(correct),
        "incorrect_count":       len(incorrect),
        "unverifiable_count":    len(unverif),
        "accuracy_rate":         accuracy_rate,
        "trust_score":           trust_score,
        "high_confidence_count": len(high_conf),
        "issues":                issues,
        "all_results":           all_results_sorted,
    }


def format_report_text(summary: dict) -> str:
    """Renders the summary as a professional plain-text report string."""
    lines = []
    width = 70

    def rule(char="="):
        lines.append(char * width)

    def section(title):
        lines.append("")
        rule("-")
        lines.append(f"  {title}")
        rule("-")

    rule()
    lines.append("  AUDYT.AI HALLUCINATION REPORT".center(width))
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(width))
    rule()

    section("OVERVIEW")
    t = summary["total_claims"]
    c = summary["correct_count"]
    i = summary["incorrect_count"]
    u = summary["unverifiable_count"]
    lines.append(f"  Claims Analyzed  : {t}")
    lines.append(f"  Verified Correct : {c}  ({round(c/t*100,1) if t else 0}%)")
    lines.append(f"  Incorrect        : {i}  ({round(i/t*100,1) if t else 0}%)")
    lines.append(f"  Unverifiable     : {u}  ({round(u/t*100,1) if t else 0}%)")
    lines.append(f"  Accuracy Rate    : {summary['accuracy_rate']}%  (excl. unverifiable)")
    lines.append(f"  Trust Score      : {summary['trust_score']}%  (correct / total)")
    lines.append(f"  High-Conf Checks : {summary['high_confidence_count']}")

    if summary["issues"]:
        section("ISSUES REQUIRING ATTENTION")
        for r in summary["issues"]:
            tag = f"[{r['verdict']}]"
            claim_short = (r["claim"][:90] + "...") if len(r["claim"]) > 90 else r["claim"]
            lines.append(f"\n  {tag} Claim: \"{claim_short}\"")
            if r["verdict"] == "INCORRECT" and r.get("source_says"):
                lines.append(f"    Source says : {r['source_says']}")
                lines.append(f"    Citation    : {r.get('citation') or 'N/A'}")
            elif r["verdict"] == "UNVERIFIABLE":
                lines.append(f"    No supporting source found in uploaded documents.")
                if r.get("citation"):
                    lines.append(f"    Closest source: {r['citation']}")
    else:
        section("ISSUES REQUIRING ATTENTION")
        lines.append("  None — all claims verified against source documents.")

    section("FULL VERIFICATION RESULTS")
    for r in summary["all_results"]:
        num         = r.get("claim_number", "?")
        verdict     = r["verdict"]
        confidence  = r.get("confidence", "N/A")
        citation    = r.get("citation") or "N/A"
        explanation = r.get("explanation", "")
        claim_short = (r["claim"][:85] + "...") if len(r["claim"]) > 85 else r["claim"]

        lines.append(f"\n  Claim {num:>2}  [{verdict}]  confidence: {confidence}")
        lines.append(f"    Text       : {claim_short}")
        lines.append(f"    Citation   : {citation}")
        lines.append(f"    Explanation: {explanation}")

    lines.append("")
    rule()
    lines.append("  End of Report — Audyt.ai".center(width))
    rule()

    return "\n".join(lines)


def generate_csv_report(verification_results: list[dict]) -> str:
    """
    Returns a CSV-formatted string with one row per verified claim.
    Columns: Claim Number, Claim Text, Verdict, Confidence, Citation,
             Explanation, Source Says
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    writer.writerow([
        "Claim Number", "Claim Text", "Verdict", "Confidence",
        "Citation", "Explanation", "Source Says",
    ])

    for r in sorted(verification_results, key=lambda x: x.get("claim_number", 0)):
        writer.writerow([
            r.get("claim_number", ""),
            r.get("claim", ""),
            r.get("verdict", ""),
            r.get("confidence", ""),
            r.get("citation") or "",
            r.get("explanation", ""),
            r.get("source_says") or "",
        ])

    return output.getvalue()
