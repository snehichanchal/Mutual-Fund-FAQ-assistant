"""
Vector Store — Manage vector persistence via ChromaDB.

Reference: Implementation Plan §4.2 (Phase 3), §5.5 (Phase 4)
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import chromadb

from src.config import (
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    PROCESSED_DATA_DIR,
    SIMILARITY_THRESHOLD,
    TOP_K_RETRIEVAL,
)

logger = logging.getLogger(__name__)

import os

# Global client and collection for lazy loading
_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None
_db_mtime: float = 0.0

def get_client() -> chromadb.ClientAPI:
    """Lazily load and cache the ChromaDB client, reloading if the DB file changes."""
    global _client, _collection, _db_mtime
    
    db_file = CHROMA_PERSIST_DIR / "chroma.sqlite3"
    current_mtime = db_file.stat().st_mtime if db_file.exists() else 0.0
    
    # If client is None, or the database file was updated by GitHub Actions
    if _client is None or current_mtime > _db_mtime:
        logger.info("Initializing ChromaDB PersistentClient at %s", CHROMA_PERSIST_DIR)
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        _collection = None  # Force collection to reload too
        _db_mtime = current_mtime
        
    return _client


def get_collection() -> chromadb.Collection:
    """Lazily load or create the ChromaDB collection."""
    global _collection
    if _collection is None:
        client = get_client()
        logger.info("Getting or creating collection '%s'", COLLECTION_NAME)
        # Using cosine similarity (hnsw:space = cosine)
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(chunks: list[dict[str, Any]]) -> None:
    """
    Bulk upsert chunks with embeddings and metadata into ChromaDB.
    
    Args:
        chunks: List of chunk dicts containing 'chunk_id', 'embedding', 'text', and metadata.
    """
    if not chunks:
        logger.warning("No chunks to add to vector store.")
        return

    collection = get_collection()

    ids: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict[str, Any]] = []
    documents: list[str] = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        embeddings.append(chunk["embedding"])
        documents.append(chunk["text"])

        # Prepare metadata (ensure all values are valid types for Chroma, i.e., str, int, float, bool)
        metadata = {
            "scheme_name": chunk.get("scheme_name", ""),
            "section_title": chunk.get("section_title", ""),
            "source_url": chunk.get("source_url", ""),
            "last_updated": chunk.get("last_updated", ""),
            "token_count": int(chunk.get("token_count", 0)),
            "chunk_type": chunk.get("chunk_type", ""),
        }
        metadatas.append(metadata)

    # Batch upserts in groups of 500 (ChromaDB recommendation)
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
            documents=documents[i : i + batch_size],
        )

    logger.info(
        "Added %d chunks to vector store collection '%s'", len(chunks), COLLECTION_NAME
    )


def delete_collection() -> None:
    """Drop and recreate collection for clean re-ingestion."""
    global _collection
    client = get_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
        logger.info("Deleted collection '%s'", COLLECTION_NAME)
    except Exception as e:
        logger.warning(
            "Could not delete collection '%s' (might not exist yet): %s",
            COLLECTION_NAME,
            str(e),
        )
    _collection = None


def get_collection_stats() -> dict[str, Any]:
    """Return count, collection name, sample schemes."""
    collection = get_collection()
    count = collection.count()

    # Get a sample to extract unique schemes
    schemes = set()
    if count > 0:
        sample = collection.peek(limit=min(count, 100))
        if sample and "metadatas" in sample and sample["metadatas"]:
            for metadata in sample["metadatas"]:
                if metadata and "scheme_name" in metadata:
                    schemes.add(metadata["scheme_name"])

    stats = {
        "collection_name": COLLECTION_NAME,
        "count": count,
        "schemes": list(schemes),
    }
    return stats


def search(
    query_embedding: list[float],
    top_k: int = TOP_K_RETRIEVAL,
    scheme_filter: str | None = None,
    min_similarity: float = SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Similarity search with optional metadata filtering and threshold enforcement.

    Queries ChromaDB with the given embedding, optionally filters by scheme_name
    metadata, converts cosine distances to similarity scores, and discards results
    below the minimum similarity threshold.

    Args:
        query_embedding: 384-dimensional embedding vector for the user query.
        top_k: Number of candidate chunks to retrieve from ChromaDB.
        scheme_filter: If set, restricts search to chunks matching this scheme_name.
        min_similarity: Minimum cosine similarity (0–1). Results below this are excluded.

    Returns:
        List of result dicts sorted by descending similarity, each containing:
            chunk_id, text, scheme_name, section_title, source_url,
            last_updated, token_count, chunk_type, similarity
    """
    collection = get_collection()

    if collection.count() == 0:
        logger.warning("Vector store is empty — no results to return.")
        return []

    # Build query kwargs
    query_kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if scheme_filter:
        query_kwargs["where"] = {"scheme_name": scheme_filter}
        logger.info(
            "Searching with scheme_name filter: '%s', top_k=%d", scheme_filter, top_k
        )
    else:
        logger.info("Searching full corpus, top_k=%d", top_k)

    results = collection.query(**query_kwargs)

    # Unpack ChromaDB results (they come as lists-of-lists)
    if not results or not results["ids"] or not results["ids"][0]:
        logger.info("No results returned from ChromaDB.")
        return []

    ids = results["ids"][0]
    documents = results["documents"][0] if results.get("documents") else [""] * len(ids)
    metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
    distances = results["distances"][0] if results.get("distances") else [1.0] * len(ids)

    # Convert distances to similarities and filter by threshold
    search_results: list[dict[str, Any]] = []
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        similarity = 1.0 - distance

        if similarity < min_similarity:
            logger.debug(
                "Discarding chunk '%s' (sim=%.4f < threshold=%.4f)",
                chunk_id,
                similarity,
                min_similarity,
            )
            continue

        search_results.append(
            {
                "chunk_id": chunk_id,
                "text": document,
                "scheme_name": metadata.get("scheme_name", ""),
                "section_title": metadata.get("section_title", ""),
                "source_url": metadata.get("source_url", ""),
                "last_updated": metadata.get("last_updated", ""),
                "token_count": int(metadata.get("token_count", 0)),
                "chunk_type": metadata.get("chunk_type", ""),
                "similarity": round(similarity, 4),
            }
        )

    # Sort by similarity (descending) — ChromaDB returns sorted by distance,
    # but threshold filtering may have changed the order slightly
    search_results.sort(key=lambda r: r["similarity"], reverse=True)

    logger.info(
        "Search returned %d results above threshold (%.2f) out of %d candidates.",
        len(search_results),
        min_similarity,
        len(ids),
    )

    return search_results


def load_chunks_to_store() -> None:
    """
    Read all *_embedded.json files from PROCESSED_DATA_DIR and load them into ChromaDB.
    Called by the ingestion script pipeline.
    """
    logger.info("Loading chunks into vector store...")

    # Recreate the collection for a clean ingestion state
    delete_collection()

    embedded_files = sorted(PROCESSED_DATA_DIR.glob("*_embedded.json"))

    if not embedded_files:
        logger.warning(
            "No *_embedded.json files found in %s. Run embedder first.",
            PROCESSED_DATA_DIR,
        )
        return

    total_chunks = 0
    for file_path in embedded_files:
        logger.info("Reading %s", file_path.name)
        with open(file_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            if chunks:
                add_chunks(chunks)
                total_chunks += len(chunks)

    logger.info("Vector store load complete. Added %d total chunks.", total_chunks)

    stats = get_collection_stats()
    logger.info("Collection stats: %s", stats)


if __name__ == "__main__":
    # Optional standalone test
    logging.basicConfig(level=logging.INFO)
    load_chunks_to_store()

