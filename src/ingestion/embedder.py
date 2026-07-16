"""
Embedder — Generate vector embeddings for chunked mutual fund data.

Reads *_chunks.json files from data/processed/ and produces *_embedded.json files
with BGE-small-en-v1.5 embeddings (384 dimensions) added to each chunk.

The model runs entirely locally via sentence-transformers — no API key required.

Reference: Architecture §3.1.4, Implementation Plan §3.5
"""

import json
import logging
import math
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

from src.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_QUERY_PREFIX,
    PROCESSED_DATA_DIR,
)

logger = logging.getLogger(__name__)

# ─── Model Singleton ─────────────────────────────────────────────────────────

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazily load and cache the embedding model."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info(
            "Model loaded — dimensions: %d, max seq length: %d",
            _model.get_sentence_embedding_dimension(),
            _model.max_seq_length,
        )
    return _model


# ─── Embedding Functions ─────────────────────────────────────────────────────


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using the BGE model.

    Args:
        texts: Raw text strings to embed.

    Returns:
        List of embedding vectors (each a list of floats with EMBEDDING_DIMENSIONS length).
    """
    model = _get_model()
    total = len(texts)
    total_batches = math.ceil(total / EMBEDDING_BATCH_SIZE)
    all_embeddings: list[list[float]] = []

    for batch_idx in range(total_batches):
        start = batch_idx * EMBEDDING_BATCH_SIZE
        end = min(start + EMBEDDING_BATCH_SIZE, total)
        batch_texts = texts[start:end]

        logger.info(
            "Embedding batch %d/%d (%d texts)",
            batch_idx + 1,
            total_batches,
            len(batch_texts),
        )

        embeddings = model.encode(
            batch_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        for emb in embeddings:
            emb_list = emb.tolist()
            assert len(emb_list) == EMBEDDING_DIMENSIONS, (
                f"Expected {EMBEDDING_DIMENSIONS} dims, got {len(emb_list)}"
            )
            all_embeddings.append(emb_list)

    logger.info(
        "Embedded %d texts → %d vectors (%d dims each)",
        total,
        len(all_embeddings),
        EMBEDDING_DIMENSIONS,
    )
    return all_embeddings


def embed_query(query: str) -> list[float]:
    """
    Embed a single user query for retrieval.

    BGE models benefit from a query prefix for asymmetric retrieval tasks.
    Document chunks are embedded without the prefix (done in embed_texts),
    but queries should use the prefix for best results.

    Args:
        query: User query string.

    Returns:
        Embedding vector as a list of floats.
    """
    model = _get_model()
    prefixed_query = f"{EMBEDDING_QUERY_PREFIX}{query}"
    embedding = model.encode(
        [prefixed_query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding[0].tolist()


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Add embedding vectors to a list of chunk dicts.

    Each chunk dict gets an 'embedding' field containing a list[float]
    of EMBEDDING_DIMENSIONS length.

    Args:
        chunks: List of chunk dicts (must have a 'text' field).

    Returns:
        The same list of chunk dicts, each now containing an 'embedding' field.
    """
    if not chunks:
        logger.warning("No chunks to embed.")
        return chunks

    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(texts)

    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding

    return chunks


# ─── File I/O ────────────────────────────────────────────────────────────────


def embed_chunks_file(chunks_json_path: Path) -> list[dict[str, Any]]:
    """
    Read a *_chunks.json file, add embeddings, and write *_embedded.json.

    Args:
        chunks_json_path: Path to a *_chunks.json file.

    Returns:
        List of chunk dicts with embeddings added.
    """
    logger.info("Reading chunks file: %s", chunks_json_path)

    with open(chunks_json_path, "r", encoding="utf-8") as fh:
        chunks = json.load(fh)

    logger.info("Found %d chunks to embed.", len(chunks))
    embedded_chunks = embed_chunks(chunks)

    # Write output
    output_path = chunks_json_path.parent / chunks_json_path.name.replace(
        "_chunks.json", "_embedded.json"
    )
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(embedded_chunks, fh, indent=2, ensure_ascii=False)

    logger.info("Wrote %d embedded chunks to %s", len(embedded_chunks), output_path)
    return embedded_chunks


def embed_all_chunks() -> list[dict[str, Any]]:
    """
    Discover all *_chunks.json files in PROCESSED_DATA_DIR and embed each one.

    Returns the combined list of all embedded chunks across all schemes.
    """
    chunk_files = sorted(PROCESSED_DATA_DIR.glob("*_chunks.json"))

    if not chunk_files:
        logger.warning(
            "No *_chunks.json files found in %s. Run the chunker first.",
            PROCESSED_DATA_DIR,
        )
        return []

    logger.info("Found %d chunk files to embed.", len(chunk_files))

    all_embedded: list[dict[str, Any]] = []
    for cf in chunk_files:
        embedded = embed_chunks_file(cf)
        all_embedded.extend(embedded)

    logger.info(
        "Total embedded chunks across all schemes: %d (%d dims each)",
        len(all_embedded),
        EMBEDDING_DIMENSIONS,
    )
    return all_embedded


# ─── CLI Entry Point ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the embedder as a standalone script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    all_embedded = embed_all_chunks()

    if all_embedded:
        # Verify embeddings
        dims = set(len(c["embedding"]) for c in all_embedded)
        schemes = set(c["scheme_name"] for c in all_embedded)

        print("\n" + "=" * 60)
        print("EMBEDDING SUMMARY")
        print("=" * 60)
        print(f"\nModel: {EMBEDDING_MODEL}")
        print(f"Total chunks embedded: {len(all_embedded)}")
        print(f"Embedding dimensions: {dims}")
        print(f"Schemes: {', '.join(sorted(schemes))}")

        # Per-scheme counts
        print("\nBy scheme:")
        for scheme in sorted(schemes):
            count = sum(1 for c in all_embedded if c["scheme_name"] == scheme)
            print(f"  {scheme}: {count} chunks")

        print("=" * 60)
    else:
        print("\nNo chunks embedded. Ensure chunk files exist in data/processed/.")


if __name__ == "__main__":
    main()
