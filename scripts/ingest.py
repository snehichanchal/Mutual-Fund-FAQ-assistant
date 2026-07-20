#!/usr/bin/env python3
"""
Ingestion pipeline orchestration script.

Runs one or more pipeline stages depending on the CLI flags provided:
  --full       (default) scrape → parse → chunk → embed → load
  --scrape-only          scrape only
  --parse-only           parse only
  --no-scrape            parse → chunk → embed → load
  --chunk-only           chunk only
  --embed-only           embed only

Reference: Implementation Plan §3.6
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'src' is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("ingest")


def run_scrape() -> None:
    """Run the scraper stage."""
    logger.info("─── Stage: SCRAPE ────────────────────────────────────────")
    try:
        from src.ingestion.scraper import run_scraper
        run_scraper()
    except ImportError:
        logger.error("Scraper module not yet implemented. Skipping.")
    except Exception as exc:
        logger.error("Scraper failed: %s", exc, exc_info=True)
        raise


def run_parse() -> None:
    """Run the parser stage."""
    logger.info("─── Stage: PARSE ─────────────────────────────────────────")
    try:
        from src.ingestion.parser import parse_all_sources
        parse_all_sources()
    except ImportError:
        logger.error("Parser module not yet implemented. Skipping.")
    except Exception as exc:
        logger.error("Parser failed: %s", exc, exc_info=True)
        raise


def run_chunk() -> None:
    """Run the chunker stage."""
    logger.info("─── Stage: CHUNK ─────────────────────────────────────────")
    from src.ingestion.chunker import chunk_all_schemes
    chunks = chunk_all_schemes()
    logger.info("Chunking complete: %d total chunks produced.", len(chunks))


def run_embed() -> None:
    """Run the embedder stage."""
    logger.info("─── Stage: EMBED ─────────────────────────────────────────")
    try:
        from src.ingestion.embedder import embed_all_chunks
        embed_all_chunks()
    except ImportError:
        logger.error("Embedder module not yet implemented. Skipping.")
    except Exception as exc:
        logger.error("Embedder failed: %s", exc, exc_info=True)
        raise


def run_load() -> None:
    """Run the vector store loading stage."""
    logger.info("─── Stage: LOAD ──────────────────────────────────────────")
    try:
        from src.retrieval.vector_store import load_chunks_to_store
        load_chunks_to_store()
    except ImportError:
        logger.error("Vector store module not yet implemented. Skipping.")
    except Exception as exc:
        logger.error("Vector store loading failed: %s", exc, exc_info=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mutual Fund FAQ Assistant — Data Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/ingest.py                  # Full pipeline (default)
  python scripts/ingest.py --scrape-only    # Scrape HTML only
  python scripts/ingest.py --parse-only     # Parse HTML only
  python scripts/ingest.py --chunk-only     # Chunk parsed data only
  python scripts/ingest.py --embed-only     # Embed chunks only
  python scripts/ingest.py --no-scrape      # Skip scraping, run rest
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--full",
        action="store_true",
        default=True,
        help="Run the full pipeline: scrape → parse → chunk → embed → load (default)",
    )
    group.add_argument(
        "--scrape-only",
        action="store_true",
        help="Run scraper only",
    )
    group.add_argument(
        "--parse-only",
        action="store_true",
        help="Run parser only",
    )
    group.add_argument(
        "--chunk-only",
        action="store_true",
        help="Run chunker only",
    )
    group.add_argument(
        "--embed-only",
        action="store_true",
        help="Run embedder only",
    )
    group.add_argument(
        "--no-scrape",
        action="store_true",
        help="Run all stages except scraping",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    logger.info("=" * 60)
    logger.info("Mutual Fund FAQ Assistant — Ingestion Pipeline")
    logger.info("=" * 60)

    try:
        if args.scrape_only:
            run_scrape()
        elif args.parse_only:
            run_parse()
        elif args.chunk_only:
            run_chunk()
        elif args.embed_only:
            run_embed()
        elif args.no_scrape:
            run_parse()
            run_chunk()
            run_embed()
            run_load()
        else:
            # --full (default)
            run_scrape()
            run_parse()
            run_chunk()
            run_embed()
            run_load()

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully.")
        logger.info("=" * 60)

    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
