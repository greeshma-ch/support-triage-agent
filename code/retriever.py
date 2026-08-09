"""
RAG Retriever using ChromaDB + sentence-transformers.

Loads .md files from data/hackerrank, data/claude, data/visa,
chunks them, and stores in a persistent ChromaDB collection.
Supports company-filtered semantic search.
"""

import os
import glob
import chromadb
from chromadb.utils import embedding_functions


# ─── Configuration ───────────────────────────────────────────────────────────
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
CHROMA_DIR = os.path.join(DATA_DIR, ".chroma")
COLLECTION_NAME = "support_corpus"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Company → subfolder mapping
COMPANY_FOLDERS = {
    "hackerrank": os.path.join(DATA_DIR, "hackerrank"),
    "claude": os.path.join(DATA_DIR, "claude"),
    "visa": os.path.join(DATA_DIR, "visa"),
}


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


# ─── File Loading ─────────────────────────────────────────────────────────────
def load_documents(source: str, folder: str) -> list[dict]:
    """Load and chunk all .md files from a folder, tagging each chunk with source."""
    docs = []
    pattern = os.path.join(folder, "**", "*.md")
    files = glob.glob(pattern, recursive=True)

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        if not content.strip():
            continue

        rel_path = os.path.relpath(filepath, DATA_DIR)
        chunks = chunk_text(content)

        for i, chunk in enumerate(chunks):
            docs.append({
                "id": f"{source}::{rel_path}::chunk_{i}",
                "text": chunk,
                "source": source,
                "filepath": rel_path,
            })

    return docs


# ─── ChromaDB Setup ───────────────────────────────────────────────────────────
def get_embedding_function():
    """Return the sentence-transformer embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )


def get_client_and_collection():
    """Return a persistent ChromaDB client and the support_corpus collection."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    ef = get_embedding_function()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def build_index(force_rebuild: bool = False):
    """
    Load all corpus documents, chunk them, and upsert into ChromaDB.
    Skips if collection already has documents (unless force_rebuild=True).
    """
    client, collection = get_client_and_collection()

    if collection.count() > 0 and not force_rebuild:
        print(f"  [OK] ChromaDB collection already has {collection.count()} chunks - skipping rebuild.")
        return collection

    if force_rebuild:
        # Delete and recreate
        client.delete_collection(COLLECTION_NAME)
        ef = get_embedding_function()
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    print("  Building vector index from corpus...")
    all_docs = []
    for source, folder in COMPANY_FOLDERS.items():
        docs = load_documents(source, folder)
        all_docs.extend(docs)
        print(f"    {source}: {len(docs)} chunks from {folder}")

    if not all_docs:
        print("  [WARN] No documents found in corpus!")
        return collection

    # Upsert in batches (ChromaDB has limits on batch size)
    BATCH_SIZE = 500
    for i in range(0, len(all_docs), BATCH_SIZE):
        batch = all_docs[i : i + BATCH_SIZE]
        collection.upsert(
            ids=[d["id"] for d in batch],
            documents=[d["text"] for d in batch],
            metadatas=[{"source": d["source"], "filepath": d["filepath"]} for d in batch],
        )

    print(f"  [OK] Indexed {len(all_docs)} total chunks into ChromaDB.")
    return collection


# ─── Query ────────────────────────────────────────────────────────────────────
def query(query_text: str, company: str | None = None, n_results: int = 5) -> str:
    """
    Retrieve the top-N most relevant chunks for a query.
    If company is provided (and not 'none'/'unknown'), filter to that company's corpus.
    Returns a single string with labelled chunks.
    """
    _, collection = get_client_and_collection()

    if collection.count() == 0:
        return "[No documents indexed yet]"

    # Build optional company filter
    where_filter = None
    if company and company.lower() not in ("none", "unknown", ""):
        where_filter = {"source": company.lower()}

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
            where=where_filter,
        )
    except Exception:
        # Fallback: query without filter
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
        )

    # Format results
    output_parts = []
    if results and results["documents"] and results["documents"][0]:
        for idx, (doc, meta) in enumerate(
            zip(results["documents"][0], results["metadatas"][0]), 1
        ):
            source_label = meta.get("source", "unknown").upper()
            filepath = meta.get("filepath", "")
            output_parts.append(
                f"--- [{source_label}] (source: {filepath}) ---\n{doc}"
            )

    if not output_parts:
        return "[No relevant documents found]"

    return "\n\n".join(output_parts)


# ─── CLI Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Building index...")
    build_index()
    print()

    test_queries = [
        ("How do I add extra time for a candidate?", "hackerrank"),
        ("How do I delete a conversation?", "claude"),
        ("My Visa card was stolen, what do I do?", "visa"),
        ("site is down", None),
    ]

    for q, c in test_queries:
        print(f"Query: {q}  |  Company filter: {c}")
        result = query(q, c)
        print(result[:300])
        print("---\n")
