"""
Chunker — 3-tier section-aware chunking for parsed mutual fund data.

Reads *_parsed.json files from data/processed/ and produces *_chunks.json files
with semantically meaningful chunks optimised for embedding and retrieval.

Strategy (Implementation Plan §3.4):
  Tier 1 — Merge small sections (≤ 75 tokens) into composite chunks (≤ 300 tokens)
  Tier 2 — Keep medium sections (76–500 tokens) as single chunks
  Tier 3 — Split large sections (> 500 tokens) on table-row boundaries (~300 tok sub-chunks, 50-token overlap)

Reference: Architecture §3.1.3, Implementation Plan §3.4
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import tiktoken

from src.config import (
    CHUNK_MERGE_MAX_COMPOSITE,
    CHUNK_MERGE_THRESHOLD,
    CHUNK_OVERLAP,
    CHUNK_SIZE_MAX,
    CHUNK_SIZE_MIN,
    CHUNK_SPLIT_TARGET,
    CHUNK_TOKENIZER,
    PROCESSED_DATA_DIR,
    SOURCES_FILE,
)

logger = logging.getLogger(__name__)

# ─── Tier Thresholds (imported from config) ──────────────────────────────────
# CHUNK_MERGE_THRESHOLD  = 75   → Tier 1: sections ≤ this are merge candidates
# CHUNK_SIZE_MAX         = 500  → Tier 2 upper bound
# CHUNK_MERGE_MAX_COMPOSITE = 300 → Max composite chunk when merging
# CHUNK_SPLIT_TARGET     = 300  → Target sub-chunk size for Tier 3
# CHUNK_OVERLAP          = 50   → Overlap tokens between Tier 3 sub-chunks

MERGE_THRESHOLD = CHUNK_MERGE_THRESHOLD
SINGLE_THRESHOLD = CHUNK_SIZE_MAX
MERGE_MAX_COMPOSITE = CHUNK_MERGE_MAX_COMPOSITE
SPLIT_TARGET = CHUNK_SPLIT_TARGET

# ─── Tokenizer ───────────────────────────────────────────────────────────────

_tokenizer: tiktoken.Encoding | None = None


def _get_tokenizer() -> tiktoken.Encoding:
    """Lazily initialise and cache the tiktoken tokenizer."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding(CHUNK_TOKENIZER)
    return _tokenizer


def count_tokens(text: str) -> int:
    """Return the token count for *text* using the configured tokenizer."""
    return len(_get_tokenizer().encode(text))


# ─── Source Lookup ───────────────────────────────────────────────────────────

def _load_sources_map() -> dict[str, dict[str, str]]:
    """
    Load sources.json and return a mapping from scheme_id → source metadata.
    Used to enrich chunk metadata with source_url and last_fetched.
    """
    if not SOURCES_FILE.exists():
        logger.warning("sources.json not found at %s; chunk metadata will lack source info.", SOURCES_FILE)
        return {}

    with open(SOURCES_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    return {
        src["id"]: {
            "source_url": src.get("url", ""),
            "last_fetched": src.get("last_fetched", ""),
            "scheme_name": src.get("scheme", ""),
        }
        for src in data.get("sources", [])
    }


# ─── Tier 1: Merge Small Sections ───────────────────────────────────────────

def _merge_small_sections(
    sections: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Merge adjacent sections whose token count is ≤ MERGE_THRESHOLD into
    composite chunks.  Each composite chunk is capped at MERGE_MAX_COMPOSITE
    tokens.

    Returns a list of dicts with keys:
        text, section_title, chunk_type, token_count
    """
    composites: list[dict[str, Any]] = []
    current_parts: list[str] = []
    current_titles: list[str] = []
    current_token_count = 0

    for section in sections:
        title = section["title"]
        content = section["content"]
        section_text = f"{title}: {content}"
        section_tokens = count_tokens(section_text)

        if section_tokens > MERGE_THRESHOLD:
            # Flush any pending composite before skipping this section
            continue

        # Would adding this section exceed the composite cap?
        if current_parts and (current_token_count + section_tokens) > MERGE_MAX_COMPOSITE:
            # Flush current composite
            composites.append({
                "text": "\n\n".join(current_parts),
                "section_title": " / ".join(current_titles),
                "chunk_type": "merged_faq",
                "token_count": current_token_count,
            })
            current_parts = []
            current_titles = []
            current_token_count = 0

        current_parts.append(section_text)
        current_titles.append(title)
        current_token_count += section_tokens

    # Flush remaining
    if current_parts:
        composites.append({
            "text": "\n\n".join(current_parts),
            "section_title": " / ".join(current_titles),
            "chunk_type": "merged_faq",
            "token_count": current_token_count,
        })

    return composites


# ─── Tier 2: Keep Medium Sections ───────────────────────────────────────────

def _keep_medium_sections(
    sections: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Sections with token count in (MERGE_THRESHOLD, SINGLE_THRESHOLD] are kept
    as individual chunks with the section title prepended.
    """
    chunks: list[dict[str, Any]] = []

    for section in sections:
        title = section["title"]
        content = section["content"]
        section_text = f"{title}: {content}"
        section_tokens = count_tokens(section_text)

        if MERGE_THRESHOLD < section_tokens <= SINGLE_THRESHOLD:
            chunks.append({
                "text": section_text,
                "section_title": title,
                "chunk_type": "single_section",
                "token_count": section_tokens,
            })

    return chunks


# ─── Tier 3: Split Large Sections ───────────────────────────────────────────

def _split_large_section(
    title: str,
    content: str,
) -> list[dict[str, Any]]:
    """
    Split a large section (> SINGLE_THRESHOLD tokens) into sub-chunks of
    approximately SPLIT_TARGET tokens.

    Splitting strategy:
      1. Split content into lines.
      2. Identify Markdown table rows (lines starting with '|').
      3. Group lines into sub-chunks of ~SPLIT_TARGET tokens.
      4. Apply CHUNK_OVERLAP tokens of overlap between consecutive sub-chunks
         by repeating the last few lines of the previous sub-chunk.
    """
    lines = content.split("\n")
    sub_chunks: list[dict[str, Any]] = []

    current_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)

        # If adding this line would exceed the target and we already have content,
        # start a new sub-chunk.
        if current_lines and (current_tokens + line_tokens) > SPLIT_TARGET:
            chunk_text = f"{title}: " + "\n".join(current_lines)
            sub_chunks.append({
                "text": chunk_text,
                "section_title": title,
                "chunk_type": "split_table",
                "token_count": count_tokens(chunk_text),
            })

            # Build overlap: collect trailing lines from current_lines up to
            # CHUNK_OVERLAP tokens.
            overlap_lines: list[str] = []
            overlap_tokens = 0
            for prev_line in reversed(current_lines):
                prev_tokens = count_tokens(prev_line)
                if overlap_tokens + prev_tokens > CHUNK_OVERLAP:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_tokens += prev_tokens

            current_lines = overlap_lines.copy()
            current_tokens = overlap_tokens

        current_lines.append(line)
        current_tokens += line_tokens

    # Flush remaining lines
    if current_lines:
        chunk_text = f"{title}: " + "\n".join(current_lines)
        final_tokens = count_tokens(chunk_text)
        sub_chunks.append({
            "text": chunk_text,
            "section_title": title,
            "chunk_type": "split_table",
            "token_count": final_tokens,
        })

    return sub_chunks


def _split_large_sections(
    sections: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Find sections exceeding SINGLE_THRESHOLD tokens and split them into
    sub-chunks.
    """
    chunks: list[dict[str, Any]] = []

    for section in sections:
        title = section["title"]
        content = section["content"]
        section_text = f"{title}: {content}"
        section_tokens = count_tokens(section_text)

        if section_tokens > SINGLE_THRESHOLD:
            sub_chunks = _split_large_section(title, content)
            chunks.extend(sub_chunks)

    return chunks


# ─── Chunk Assembly ──────────────────────────────────────────────────────────

def chunk_scheme(parsed_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Apply the 3-tier chunking strategy to a single scheme's parsed data.

    Args:
        parsed_data: Dict loaded from a *_parsed.json file.

    Returns:
        List of chunk dicts matching the metadata schema (§3.4.4).
    """
    scheme_id = parsed_data["scheme_id"]
    scheme_name = parsed_data["scheme_name"]
    source_url = parsed_data.get("source_url", "")
    last_fetched = parsed_data.get("last_fetched", "")
    sections = parsed_data.get("sections", [])

    if not sections:
        logger.warning("No sections found for scheme '%s'; skipping.", scheme_id)
        return []

    # Apply all three tiers
    tier1_chunks = _merge_small_sections(sections)
    tier2_chunks = _keep_medium_sections(sections)
    tier3_chunks = _split_large_sections(sections)

    # Combine in order: merged FAQ → single sections → split tables
    all_raw_chunks = tier1_chunks + tier2_chunks + tier3_chunks

    # Filter out noise fragments below minimum token count
    filtered_chunks = [
        c for c in all_raw_chunks if c["token_count"] >= CHUNK_SIZE_MIN
    ]

    # Assign chunk IDs and full metadata
    final_chunks: list[dict[str, Any]] = []
    for idx, chunk in enumerate(filtered_chunks, start=1):
        chunk_id = f"{scheme_id}-chunk-{idx:02d}"
        final_chunks.append({
            "chunk_id": chunk_id,
            "text": chunk["text"],
            "scheme_name": scheme_name,
            "section_title": chunk["section_title"],
            "source_url": source_url,
            "last_updated": last_fetched,
            "token_count": chunk["token_count"],
            "chunk_type": chunk["chunk_type"],
        })

    logger.info(
        "Chunked '%s': %d chunks (Tier1=%d, Tier2=%d, Tier3=%d)",
        scheme_name,
        len(final_chunks),
        len(tier1_chunks),
        len(tier2_chunks),
        len(tier3_chunks),
    )

    return final_chunks


# ─── File I/O ────────────────────────────────────────────────────────────────

def chunk_parsed_file(parsed_json_path: Path) -> list[dict[str, Any]]:
    """
    Read a *_parsed.json file, chunk it, and write the result to
    *_chunks.json in the same directory.

    Returns the list of chunks produced.
    """
    logger.info("Reading parsed file: %s", parsed_json_path)

    with open(parsed_json_path, "r", encoding="utf-8") as fh:
        parsed_data = json.load(fh)

    chunks = chunk_scheme(parsed_data)

    # Write output
    output_path = parsed_json_path.parent / parsed_json_path.name.replace(
        "_parsed.json", "_chunks.json"
    )
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(chunks, fh, indent=2, ensure_ascii=False)

    logger.info("Wrote %d chunks to %s", len(chunks), output_path)
    return chunks


def chunk_all_schemes() -> list[dict[str, Any]]:
    """
    Discover all *_parsed.json files in PROCESSED_DATA_DIR and chunk each one.

    Returns the combined list of all chunks across all schemes.
    """
    parsed_files = sorted(PROCESSED_DATA_DIR.glob("*_parsed.json"))

    if not parsed_files:
        logger.warning(
            "No *_parsed.json files found in %s. Run the parser first.",
            PROCESSED_DATA_DIR,
        )
        return []

    logger.info("Found %d parsed files to chunk.", len(parsed_files))

    all_chunks: list[dict[str, Any]] = []
    for pf in parsed_files:
        chunks = chunk_parsed_file(pf)
        all_chunks.extend(chunks)

    logger.info(
        "Total chunks across all schemes: %d",
        len(all_chunks),
    )
    return all_chunks


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

def main() -> None:
    """Run the chunker as a standalone script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    all_chunks = chunk_all_schemes()

    # Print summary
    if all_chunks:
        scheme_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for chunk in all_chunks:
            sn = chunk["scheme_name"]
            ct = chunk["chunk_type"]
            scheme_counts[sn] = scheme_counts.get(sn, 0) + 1
            type_counts[ct] = type_counts.get(ct, 0) + 1

        print("\n" + "=" * 60)
        print("CHUNKING SUMMARY")
        print("=" * 60)
        print(f"\nTotal chunks: {len(all_chunks)}")
        print(f"\nBy scheme:")
        for scheme, count in sorted(scheme_counts.items()):
            print(f"  {scheme}: {count} chunks")
        print(f"\nBy type:")
        for ctype, count in sorted(type_counts.items()):
            print(f"  {ctype}: {count} chunks")
        print(f"\nToken range: {min(c['token_count'] for c in all_chunks)}–{max(c['token_count'] for c in all_chunks)}")
        print("=" * 60)
    else:
        print("\nNo chunks produced. Ensure parsed data exists in data/processed/.")


if __name__ == "__main__":
    main()
