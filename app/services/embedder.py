"""
Audyt.ai — chunking and keyword search service.

Replaces ChromaDB (which loads an 80MB onnxruntime model) with a
lightweight in-memory Jaccard keyword search. Claude does the actual
reasoning; we just need to surface the most relevant source chunks.

Memory saving: ~200MB less RAM per process on Render free tier.
"""

import re
import uuid


def chunk_with_metadata(
    parsed_blocks: list[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[dict]:
    """
    Splits parsed blocks into searchable chunks.
    Short blocks (< chunk_size) pass through as a single chunk.
    Long blocks are split with overlap; every sub-chunk inherits all parent metadata.
    Each chunk gets a unique chunk_id.
    """
    chunks = []

    for block in parsed_blocks:
        text = block["text"]

        if len(text) <= chunk_size:
            chunks.append({**block, "chunk_id": str(uuid.uuid4()), "chunk_part": "1 of 1"})
        else:
            parts = []
            start = 0
            while start < len(text):
                end = start + chunk_size
                parts.append(text[start:end])
                if end >= len(text):
                    break
                start += chunk_size - chunk_overlap

            total = len(parts)
            for i, part_text in enumerate(parts, start=1):
                chunks.append({
                    **block,
                    "text": part_text,
                    "chunk_id": str(uuid.uuid4()),
                    "chunk_part": f"{i} of {total}",
                })

    return chunks


def create_vector_store(chunks: list[dict], collection_name: str | None = None):
    """
    Stores chunks in memory for keyword search.
    Returns (chunks, None, chunks) — API-compatible with the old ChromaDB version.
    The first element (chunks list) is what gets passed as 'collection' to search_sources.
    """
    if not chunks:
        raise ValueError("No chunks to store — the parsed documents may be empty or unreadable.")
    return chunks, None, chunks


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r'\b\w+\b', text.lower()))


def search_sources(collection: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """
    Keyword search over the chunks list using Jaccard similarity.
    Returns top_k results sorted by distance (lower = more relevant).
    Distance is 1 - Jaccard(query_tokens, chunk_tokens), range [0, 1].
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = []
    for chunk in collection:
        chunk_tokens = _tokenize(chunk["text"])
        if not chunk_tokens:
            continue
        overlap = len(query_tokens & chunk_tokens)
        if overlap == 0:
            continue
        similarity = overlap / len(query_tokens | chunk_tokens)
        distance = round(1.0 - similarity, 4)
        scored.append((distance, chunk))

    scored.sort(key=lambda x: x[0])
    return [{"distance": d, **c} for d, c in scored[:top_k]]
