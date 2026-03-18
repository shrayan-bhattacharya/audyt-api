"""
Audyt.ai — claim verification service.

For each extracted claim, retrieves relevant source chunks from ChromaDB
and asks Claude to return a CORRECT / INCORRECT / UNVERIFIABLE verdict
with an exact citation.

Identical to the original prototype except:
  - load_dotenv removed (api_key comes from config)
  - search_sources imported from app.services.embedder
"""

import re
import anthropic
from app.services.embedder import search_sources


SYSTEM_PROMPT = """\
You are a precise fact-checking system. Compare the CLAIM against the SOURCE material provided.

Rules:
- If the claim is fully supported by the sources, verdict is CORRECT
- If the claim contradicts the sources (wrong numbers, wrong facts, wrong dates), verdict is INCORRECT. State what the source actually says.
- If the sources are somewhat related but don't contain enough information to confirm or deny the claim, verdict is UNVERIFIABLE
- Always cite the specific source (filename, page/row) that supports your verdict
- Be strict — if a number is even slightly different, it's INCORRECT

Respond in this exact format:
VERDICT: [CORRECT/INCORRECT/UNVERIFIABLE]
CITATION: [source filename, page/sheet/row reference]
EXPLANATION: [one clear sentence explaining why]
SOURCE_SAYS: [what the source actually states, if relevant — quote the key part]"""


def _build_citation(meta: dict) -> str:
    """Format a chunk's metadata into a human-readable citation string."""
    source = meta.get("source", "unknown")
    if meta.get("type") == "pdf" and meta.get("page"):
        return f"{source}, Page {meta['page']}"
    if meta.get("type") == "excel" and meta.get("sheet"):
        return f"{source}, Sheet '{meta['sheet']}', Row {meta['row']}"
    if meta.get("type") in ("docx", "txt") and meta.get("paragraph"):
        return f"{source}, Paragraph {meta['paragraph']}"
    return source


def _confidence(distance: float | None) -> str:
    """Map best-chunk distance to a human-readable confidence label."""
    if distance is None:
        return "NONE"
    if distance < 0.5:
        return "HIGH"
    if distance < 0.8:
        return "MEDIUM"
    return "LOW"


def verify_claim(
    claim_text: str,
    collection,
    api_key: str,
    top_k: int = 7,
    distance_threshold: float = 1.2,
    context: str = "",
) -> dict:
    """
    Verifies a single claim against the ChromaDB source collection.
    Returns a dict with verdict, citation, explanation, and source_says.
    """
    hits = search_sources(collection, claim_text, top_k=top_k)
    relevant = [h for h in hits if h["distance"] <= distance_threshold]

    if not relevant:
        return {
            "verdict":         "UNVERIFIABLE",
            "claim":           claim_text,
            "explanation":     "No relevant source material found.",
            "citation":        None,
            "source_says":     None,
            "distance":        None,
            "confidence":      "NONE",
            "sources_checked": 0,
        }

    source_parts = []
    for h in relevant:
        citation = _build_citation(h)
        source_parts.append(f"SOURCE [{citation}]: {h['text']}")
    source_block = "\n\n".join(source_parts)

    context_line = f"Context about this report: {context}\n\n" if context.strip() else ""
    user_prompt = (
        f"{context_line}"
        f"CLAIM: {claim_text}\n\n"
        f"SOURCE MATERIAL:\n{source_block}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    def _extract(label: str) -> str:
        match = re.search(rf"^{label}:\s*(.+)$", raw, re.MULTILINE | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    best_distance = relevant[0]["distance"]
    return {
        "verdict":         _extract("VERDICT").upper(),
        "claim":           claim_text,
        "citation":        _extract("CITATION"),
        "explanation":     _extract("EXPLANATION"),
        "source_says":     _extract("SOURCE_SAYS"),
        "distance":        best_distance,
        "confidence":      _confidence(best_distance),
        "sources_checked": len(relevant),
    }


def verify_all_claims(
    claims_list: list[dict],
    collection,
    api_key: str,
) -> list[dict]:
    """
    Verifies every claim in claims_list against the source collection.
    Each item must have 'claim_number' and 'claim_text'.
    Returns a list of verification result dicts.
    """
    total = len(claims_list)
    results = []
    for item in claims_list:
        print(f"  Verifying claim {item['claim_number']} of {total}...", flush=True)
        result = verify_claim(item["claim_text"], collection, api_key)
        result["claim_number"] = item["claim_number"]
        results.append(result)
    return results
