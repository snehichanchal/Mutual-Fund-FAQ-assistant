"""
Reranker — Optional cross-encoder reranking for retrieval results.

V1: Passthrough implementation that returns top-k results sorted by existing
cosine similarity score from the vector store.

When RERANKER_ENABLED is set to True in config, this module will use a
cross-encoder model to rescore (query, chunk) pairs for more accurate ranking.

Reference: Implementation Plan §5.6 (Phase 4)
"""

import logging
from typing import Any

from src.config import RERANKER_ENABLED, TOP_K_RERANK

logger = logging.getLogger(__name__)

# ─── Future: Cross-Encoder Model ─────────────────────────────────────────────
#
# When the corpus grows beyond ~500 chunks or includes unstructured content,
# enable cross-encoder reranking for improved retrieval accuracy.
#
# from sentence_transformers import CrossEncoder
#
# _cross_encoder: CrossEncoder | None = None
#
# def _get_cross_encoder() -> CrossEncoder:
#     """Lazily load and cache the cross-encoder model."""
#     global _cross_encoder
#     if _cross_encoder is None:
#         logger.info("Loading cross-encoder model: cross-encoder/ms-marco-MiniLM-L-6-v2")
#         _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
#     return _cross_encoder
#
#
# def _cross_encoder_rerank(
#     query: str,
#     chunks: list[dict[str, Any]],
#     top_k: int,
# ) -> list[dict[str, Any]]:
#     """
#     Rerank chunks using a cross-encoder model.
#
#     The cross-encoder scores each (query, chunk_text) pair independently,
#     producing a relevance score that is more accurate than bi-encoder
#     cosine similarity but significantly slower.
#
#     Args:
#         query: User's natural language question.
#         chunks: Candidate chunks from vector store search.
#         top_k: Number of top results to return after reranking.
#
#     Returns:
#         Top-k chunks sorted by cross-encoder relevance score.
#     """
#     model = _get_cross_encoder()
#     pairs = [(query, chunk["text"]) for chunk in chunks]
#     scores = model.predict(pairs)
#
#     for chunk, score in zip(chunks, scores):
#         chunk["rerank_score"] = float(score)
#
#     reranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
#     return reranked[:top_k]
# ─────────────────────────────────────────────────────────────────────────────


def rerank(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = TOP_K_RERANK,
) -> list[dict[str, Any]]:
    """
    Rerank retrieval results and return the top-k most relevant chunks.

    V1 (current): Passthrough — returns top_k chunks sorted by existing
    cosine similarity score from the vector store. No additional model inference.

    V2 (future, RERANKER_ENABLED=True): Uses a cross-encoder model to rescore
    each (query, chunk_text) pair for more accurate ranking.

    Args:
        query: User's natural language question (used by cross-encoder in v2).
        chunks: Candidate chunks from vector store search, each containing
                a 'similarity' key with their cosine similarity score.
        top_k: Maximum number of results to return after reranking.

    Returns:
        List of up to top_k chunk dicts, sorted by relevance (highest first).
        Each chunk retains all original metadata plus the similarity score.
    """
    if not chunks:
        logger.info("No chunks to rerank — returning empty list.")
        return []

    if RERANKER_ENABLED:
        # Future: cross-encoder reranking
        # return _cross_encoder_rerank(query, chunks, top_k)
        logger.warning(
            "RERANKER_ENABLED is True but cross-encoder is not yet implemented. "
            "Falling back to passthrough."
        )

    # V1: Passthrough — sort by existing similarity and take top_k
    sorted_chunks = sorted(
        chunks,
        key=lambda c: c.get("similarity", 0.0),
        reverse=True,
    )
    result = sorted_chunks[:top_k]

    logger.info(
        "Reranker (passthrough): %d candidates → %d results (top_k=%d)",
        len(chunks),
        len(result),
        top_k,
    )

    if result:
        logger.info(
            "Top result: chunk_id='%s', sim=%.4f, scheme='%s'",
            result[0].get("chunk_id", "?"),
            result[0].get("similarity", 0.0),
            result[0].get("scheme_name", "?"),
        )

    return result
