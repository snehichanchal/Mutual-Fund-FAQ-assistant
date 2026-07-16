"""
Retriever — End-to-end retrieval orchestrator for the RAG pipeline.

Wires together: query embedding → vector store search → reranking → result formatting.

This is the single entry point that the API/generation layer calls to get
ranked context chunks for a user query.

Reference: Implementation Plan §5.4 (Phase 4)
"""

import logging
from dataclasses import dataclass, asdict
from typing import Any

from src.config import (
    SIMILARITY_THRESHOLD,
    TOP_K_RERANK,
    TOP_K_RETRIEVAL,
)
from src.ingestion.embedder import embed_query
from src.retrieval.reranker import rerank
from src.retrieval.vector_store import search

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A single retrieved chunk with metadata and similarity score."""

    chunk_id: str
    text: str
    scheme_name: str
    section_title: str
    source_url: str
    last_updated: str
    token_count: int
    chunk_type: str
    similarity: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dictionary."""
        return asdict(self)


def retrieve(
    query: str,
    scheme_name: str | None = None,
    top_k_retrieval: int = TOP_K_RETRIEVAL,
    top_k_rerank: int = TOP_K_RERANK,
    min_similarity: float = SIMILARITY_THRESHOLD,
) -> list[RetrievedChunk]:
    """
    End-to-end retrieval: embed query → search vector store → threshold filter → rerank.

    This is the primary entry point for the generation pipeline. It handles the
    complete retrieval flow:

    1. Embeds the user query using BGE-small-en-v1.5 (with query prefix)
    2. Searches the ChromaDB vector store with optional scheme_name metadata filter
    3. Filters results below the similarity threshold
    4. Reranks and returns the top-k most relevant chunks

    Args:
        query: User's natural language question.
        scheme_name: Optional pre-detected scheme name (from intent classifier).
                     If provided, restricts search to chunks from this scheme only.
                     If None, searches the full corpus across all 5 schemes.
        top_k_retrieval: Number of candidates to fetch from ChromaDB (default: 5).
        top_k_rerank: Number of final results after reranking (default: 3).
        min_similarity: Minimum cosine similarity threshold (default: 0.65).

    Returns:
        Ranked list of up to top_k_rerank RetrievedChunk objects.
        Empty list if no chunks meet the similarity threshold.
    """
    if not query or not query.strip():
        logger.warning("Empty query received — returning no results.")
        return []

    logger.info(
        "Retrieving for query: '%s' (scheme_filter=%s, top_k=%d, threshold=%.2f)",
        query[:80],
        scheme_name or "None",
        top_k_retrieval,
        min_similarity,
    )

    # Step 1: Embed the user query
    try:
        query_embedding = embed_query(query)
    except Exception as exc:
        logger.error("Failed to embed query: %s", exc, exc_info=True)
        return []

    # Step 2: Search the vector store
    try:
        search_results = search(
            query_embedding=query_embedding,
            top_k=top_k_retrieval,
            scheme_filter=scheme_name,
            min_similarity=min_similarity,
        )
    except Exception as exc:
        logger.error("Vector store search failed: %s", exc, exc_info=True)
        return []

    if not search_results:
        logger.info("No chunks found above similarity threshold %.2f.", min_similarity)
        return []

    logger.info(
        "Vector search returned %d results above threshold.", len(search_results)
    )

    # Step 3: Rerank
    reranked = rerank(
        query=query,
        chunks=search_results,
        top_k=top_k_rerank,
    )

    # Step 4: Convert to RetrievedChunk dataclass instances
    retrieved_chunks: list[RetrievedChunk] = []
    for chunk_dict in reranked:
        try:
            retrieved_chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_dict["chunk_id"],
                    text=chunk_dict["text"],
                    scheme_name=chunk_dict["scheme_name"],
                    section_title=chunk_dict["section_title"],
                    source_url=chunk_dict["source_url"],
                    last_updated=chunk_dict["last_updated"],
                    token_count=chunk_dict["token_count"],
                    chunk_type=chunk_dict["chunk_type"],
                    similarity=chunk_dict["similarity"],
                )
            )
        except KeyError as exc:
            logger.warning(
                "Skipping malformed chunk result — missing key: %s", exc
            )
            continue

    logger.info(
        "Retrieval complete: %d chunks returned (query='%s')",
        len(retrieved_chunks),
        query[:50],
    )

    # Log top results for debugging
    for i, chunk in enumerate(retrieved_chunks):
        logger.info(
            "  [%d] sim=%.4f  scheme='%s'  section='%s'  type=%s  id=%s",
            i + 1,
            chunk.similarity,
            chunk.scheme_name,
            chunk.section_title[:40],
            chunk.chunk_type,
            chunk.chunk_id,
        )

    return retrieved_chunks


# ─── CLI Entry Point ─────────────────────────────────────────────────────────


def main() -> None:
    """Run a quick retrieval test from the command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    test_queries = [
        ("What is the expense ratio of HDFC Small Cap Fund?", None),
        ("What are the top holdings of HDFC Mid Cap Fund?", "HDFC Mid Cap Fund"),
        ("How to invest in HDFC Large Cap Fund?", None),
        ("What is the NAV?", None),  # No scheme specified
    ]

    for query, scheme in test_queries:
        print("\n" + "=" * 80)
        print(f"QUERY: {query}")
        print(f"SCHEME FILTER: {scheme or 'None'}")
        print("=" * 80)

        results = retrieve(query, scheme_name=scheme)

        if not results:
            print("  No results found above threshold.")
        else:
            for i, chunk in enumerate(results):
                print(f"\n  [{i+1}] Similarity: {chunk.similarity:.4f}")
                print(f"      Scheme:     {chunk.scheme_name}")
                print(f"      Section:    {chunk.section_title}")
                print(f"      Type:       {chunk.chunk_type}")
                print(f"      Tokens:     {chunk.token_count}")
                print(f"      Text:       {chunk.text[:150]}...")

    print("\n" + "=" * 80)
    print("Retrieval test complete.")
    print("=" * 80)


if __name__ == "__main__":
    main()
