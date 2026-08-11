"""
RAG Retriever using ChromaDB + sentence-transformers.

Generic version: any company/corpus can be uploaded at runtime (no more
hardcoded hackerrank/claude/visa folders). Also returns retrieval distance
so the caller can compute a confidence score.
"""

import os
import re
import glob
import chromadb
from chromadb.utils import embedding_functions

# ─── Configuration ───────────────────────────────────────────────────────────
APP_DIR = os.path.dirname(__file__)
DATA_DIR = os.environ.get("CHROMA_DATA_DIR", os.path.join(APP_DIR, "storage"))
CHROMA_DIR = os.path.join(DATA_DIR, ".chroma")
SEED_DATA_DIR = os.path.join(APP_DIR, "seed_data")
COLLECTION_NAME = "support_corpus"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

os.makedirs(CHROMA_DIR, exist_ok=True)


def slugify(name: str) -> str:
    """Turn a company display name into a safe corpus key."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "general"


# ─── Chunking ────────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


# ─── ChromaDB Setup ───────────────────────────────────────────────────────────
_ef = None


def get_embedding_function():
    global _ef
    if _ef is None:
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return _ef


def get_client_and_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


# ─── Generic corpus ingestion ─────────────────────────────────────────────────
def add_documents(company: str, docs: list[tuple[str, str]]) -> int:
    """
    Add a set of (filename, text) documents for a company/source to the corpus.
    Returns the number of chunks indexed.
    """
    source = slugify(company)
    _, collection = get_client_and_collection()

    all_chunks = []
    for filename, content in docs:
        if not content or not content.strip():
            continue
        for i, chunk in enumerate(chunk_text(content)):
            all_chunks.append({
                "id": f"{source}::{filename}::chunk_{i}",
                "text": chunk,
                "source": source,
                "filepath": filename,
            })

    if not all_chunks:
        return 0

    BATCH_SIZE = 500
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i : i + BATCH_SIZE]
        collection.upsert(
            ids=[d["id"] for d in batch],
            documents=[d["text"] for d in batch],
            metadatas=[{"source": d["source"], "filepath": d["filepath"]} for d in batch],
        )

    return len(all_chunks)


def delete_company(company: str) -> int:
    """Remove all chunks for a given company/source. Returns count deleted."""
    source = slugify(company)
    _, collection = get_client_and_collection()
    existing = collection.get(where={"source": source})
    ids = existing.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def list_companies() -> list[dict]:
    """Return [{name, chunk_count}] for every distinct source in the corpus."""
    _, collection = get_client_and_collection()
    if collection.count() == 0:
        return []
    all_meta = collection.get(include=["metadatas"])
    counts: dict[str, int] = {}
    for meta in all_meta.get("metadatas", []):
        source = meta.get("source", "unknown")
        counts[source] = counts.get(source, 0) + 1
    return [{"name": k, "chunk_count": v} for k, v in sorted(counts.items())]


def seed_from_disk(force_rebuild: bool = False):
    """Load the bundled example corpora (hackerrank/claude/visa) on first boot."""
    client, collection = get_client_and_collection()

    if collection.count() > 0 and not force_rebuild:
        return collection

    if force_rebuild and collection.count() > 0:
        client.delete_collection(COLLECTION_NAME)

    if not os.path.isdir(SEED_DATA_DIR):
        return collection

    for company in sorted(os.listdir(SEED_DATA_DIR)):
        folder = os.path.join(SEED_DATA_DIR, company)
        if not os.path.isdir(folder):
            continue
        docs = []
        for filepath in glob.glob(os.path.join(folder, "**", "*.md"), recursive=True):
            rel = os.path.relpath(filepath, folder)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    docs.append((rel, f.read()))
            except Exception:
                continue
        if docs:
            add_documents(company, docs)

    _, collection = get_client_and_collection()
    return collection


# ─── Query (with confidence) ──────────────────────────────────────────────────
def query_with_scores(query_text: str, company: str | None = None, n_results: int = 5) -> dict:
    """
    Retrieve the top-N most relevant chunks for a query.

    Returns:
        {
            "context": str,           # formatted chunks for the LLM prompt
            "confidence": float,      # 0..1, higher = stronger retrieval match
            "matches": [ {source, filepath, distance}, ... ],
        }
    """
    _, collection = get_client_and_collection()

    if collection.count() == 0:
        return {"context": "[No documents indexed yet]", "confidence": 0.0, "matches": []}

    where_filter = None
    if company and company.lower() not in ("none", "unknown", ""):
        where_filter = {"source": slugify(company)}

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
            where=where_filter,
        )
        if not results.get("documents") or not results["documents"][0]:
            raise ValueError("no results under filter")
    except Exception:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
        )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if results.get("distances") else []

    if not docs:
        return {"context": "[No relevant documents found]", "confidence": 0.0, "matches": []}

    output_parts = []
    matches = []
    for doc, meta, dist in zip(docs, metas, distances or [None] * len(docs)):
        source_label = meta.get("source", "unknown").upper()
        filepath = meta.get("filepath", "")
        output_parts.append(f"--- [{source_label}] (source: {filepath}) ---\n{doc}")
        matches.append({"source": meta.get("source", "unknown"), "filepath": filepath, "distance": dist})

    # Cosine distance in Chroma is 0 (identical) .. 2 (opposite). Convert the
    # best match into a 0..1 confidence score. Anything with no distance data
    # falls back to a neutral 0.5 so we never silently over-trust.
    if distances:
        best_distance = min(distances)
        confidence = max(0.0, min(1.0, 1 - (best_distance / 2)))
    else:
        confidence = 0.5

    return {
        "context": "\n\n".join(output_parts),
        "confidence": round(confidence, 3),
        "matches": matches,
    }


def query(query_text: str, company: str | None = None, n_results: int = 5) -> str:
    """Backwards-compatible plain-text query (used by the CLI pipeline)."""
    return query_with_scores(query_text, company, n_results)["context"]
