"""
Audyt.ai — chunking and ChromaDB embedding service.

Uses EphemeralClient (in-memory, per-job) instead of PersistentClient
so each audit job gets an isolated vector store with no disk state.
"""

import uuid
import chromadb


def chunk_with_metadata(
    parsed_blocks: list[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[dict]:
    """
    Splits parsed blocks into ChromaDB-ready chunks.
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
    Embeds all chunks into an in-memory ChromaDB EphemeralClient.
    Lists are converted to comma-separated strings (ChromaDB scalar-only requirement).
    Returns (collection, client, chunks).
    """
    client = chromadb.EphemeralClient()
    name = collection_name if collection_name else f"job_{uuid.uuid4().hex}"
    collection = client.create_collection(name)

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["text"])

        meta = {}
        for k, v in chunk.items():
            if k in ("text", "chunk_id"):
                continue
            if isinstance(v, list):
                meta[k] = ", ".join(str(x) for x in v)
            elif v is None:
                meta[k] = ""
            else:
                meta[k] = v
        metadatas.append(meta)

    if not ids:
        raise ValueError("No chunks to embed — the parsed documents may be empty or unreadable.")

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return collection, client, chunks


def search_sources(collection, query: str, top_k: int = 5) -> list[dict]:
    """
    Semantic search over the ChromaDB collection.
    Returns top_k results sorted by distance (closest first),
    each with full metadata and distance score.
    """
    results = collection.query(query_texts=[query], n_results=top_k)

    hits = []
    for i in range(len(results["ids"][0])):
        hit = {
            "text": results["documents"][0][i],
            "distance": round(results["distances"][0][i], 4),
            **results["metadatas"][0][i],
        }
        hits.append(hit)

    hits.sort(key=lambda x: x["distance"])
    return hits
