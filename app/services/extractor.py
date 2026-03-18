"""
Audyt.ai — claim extraction service.

Uses Claude to break an AI-generated report into individual, self-contained,
verifiable factual claims. Prompts and parsing logic are identical to the
original prototype — only the load_dotenv call is removed (api_key is passed
as a parameter from config).
"""

import re
import anthropic


SYSTEM_PROMPT = """\
You are a precise claim extraction system. Your job is to break down a report into individual, verifiable factual claims.

Rules:
- Extract ONLY factual, verifiable claims (numbers, dates, names, quantities, percentages, specific statements)
- Skip opinions, subjective assessments, recommendations, and transition sentences
- Each claim should be self-contained — understandable without reading the rest of the report
- Preserve the exact numbers and wording from the original report
- Number each claim sequentially

Respond in this exact format, one claim per line:
CLAIM 1: [claim text]
CLAIM 2: [claim text]
CLAIM 3: [claim text]
...

Do NOT include any other text, headers, or explanations."""


def extract_claims(report_text: str, api_key: str, context: str = "") -> list[dict]:
    """
    Sends the report to Claude and parses the response into a list of
    {"claim_number": int, "claim_text": str} dicts.
    Optional context helps Claude understand what the report is about.
    """
    client = anthropic.Anthropic(api_key=api_key)

    context_line = f"Context about this report: {context}\n\n" if context.strip() else ""
    user_content = (
        f"{context_line}"
        f"Extract all verifiable factual claims from this report:\n\n{report_text}"
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = message.content[0].text.strip()

    claims = []
    for line in raw.splitlines():
        line = line.strip()
        match = re.match(r"^CLAIM\s+(\d+):\s*(.+)$", line, re.IGNORECASE)
        if match:
            claims.append({
                "claim_number": int(match.group(1)),
                "claim_text": match.group(2).strip(),
            })

    return claims
