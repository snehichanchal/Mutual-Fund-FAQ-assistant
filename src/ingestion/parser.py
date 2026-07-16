"""
HTML Parser & Cleaner for Groww Scheme Pages

Converts raw HTML snapshots from data/raw/ into cleaned, structured text
and saves both plain text (.txt) and structured JSON (_parsed.json)
to data/processed/.

Reference: Implementation Plan §3.3, Architecture §3.1.2
"""

import json
import re
import logging
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, SOURCES_FILE
from src.ingestion.scraper import load_sources

logger = logging.getLogger(__name__)

# ─── Tags to strip entirely ──────────────────────────────────────────────────

STRIP_TAGS = {"nav", "header", "footer", "script", "style", "svg", "img",
              "noscript", "iframe", "link", "meta", "button", "input",
              "select", "textarea", "form"}

# ─── Class name patterns indicating non-content elements ─────────────────────

STRIP_CLASS_PATTERNS = re.compile(
    r"(nav|header|footer|sidebar|banner|ad|promo|cookie|modal|popup|overlay|"
    r"breadcrumb|social|share|download-app|signup|login|toast)",
    re.IGNORECASE,
)

# ─── Groww-specific noise class patterns ─────────────────────────────────────
# These are CSS class prefixes found on Groww scheme pages that contain
# non-content elements (animated tickers, navigation links, dropdowns, etc.)

GROWW_NOISE_CLASS_PATTERNS = re.compile(
    r"(hiddenTicker|footerTopSection|letterLinks|dropdownUI|"
    r"compareSimilarFunds|schemeActions|searchScheme)",
    re.IGNORECASE,
)

# ─── Section keywords for Groww mutual fund pages ────────────────────────────
# Used to detect and label sections of interest from the page content.

SECTION_KEYWORDS = [
    "expense ratio",
    "exit load",
    "nav",
    "net asset value",
    "holdings",
    "top holdings",
    "sector allocation",
    "asset allocation",
    "risk",
    "riskometer",
    "benchmark",
    "fund manager",
    "fund house",
    "sip",
    "minimum investment",
    "minimum sip",
    "lump sum",
    "lumpsum",
    "investment amount",
    "fund objective",
    "investment objective",
    "fund overview",
    "scheme overview",
    "fund details",
    "scheme details",
    "fund information",
    "returns",
    "performance",
    "tax implications",
    "stamp duty",
    "lock-in",
    "lockin",
    "lock in",
    "category",
    "fund type",
    "scheme type",
    "aum",
    "assets under management",
    "inception date",
    "launch date",
]

# ─── Pattern to detect animated counter / ticker digit noise ─────────────────
# Groww uses animated digit counters for NAV display, producing text like
# "+ 1 0 1 2 3 4 5 6 7 8 9 3 0 1 2 3 ..." when extracted as plain text.

COUNTER_NOISE_PATTERN = re.compile(
    r"^[\s+\-\.₹%0-9]+$"
)

# Pattern for lines that are just a single stock/entity name (duplicates from
# the holdings table that also appear as individual span elements)
VERY_SHORT_LINE_THRESHOLD = 5  # chars


def _normalize_text(text: str) -> str:
    """
    Normalize Unicode to NFKC and collapse whitespace.

    - Applies NFKC normalization (converts fi → fi, ₹ preserved)
    - Collapses multiple spaces/tabs to a single space
    - Collapses multiple newlines to at most two
    - Strips leading/trailing whitespace per line
    """
    # NFKC normalization
    text = unicodedata.normalize("NFKC", text)

    # Replace non-breaking spaces and other whitespace variants with regular space
    text = re.sub(r"[\u00a0\u2000-\u200b\u202f\u205f\u3000]", " ", text)

    # Collapse multiple spaces/tabs (but not newlines) into a single space
    text = re.sub(r"[^\S\n]+", " ", text)

    # Strip whitespace from each line
    lines = [line.strip() for line in text.splitlines()]

    # Remove completely empty lines that appear more than twice consecutively
    cleaned_lines = []
    empty_count = 0
    for line in lines:
        if line == "":
            empty_count += 1
            if empty_count <= 2:
                cleaned_lines.append(line)
        else:
            empty_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _is_noise_text(text: str) -> bool:
    """
    Detect whether a text fragment is noise that should be discarded.

    Returns True for:
    - Animated counter digit sequences (e.g., "1 0 1 2 3 4 5 6 7 8 9")
    - Trivially short fragments (< 4 chars)
    - Pure numeric/symbol strings
    - Common Groww UI fragments
    """
    stripped = text.strip()

    # Skip empty or very short text
    if len(stripped) < 4:
        return True

    # Skip animated counter digit noise
    if COUNTER_NOISE_PATTERN.match(stripped):
        return True

    # Skip common Groww UI text fragments
    groww_ui_fragments = {
        "compare", "view all", "show more", "show less", "read more",
        "read less", "see all", "see more", "invest now", "start sip",
        "login", "sign up", "download app", "get app",
    }
    if stripped.lower() in groww_ui_fragments:
        return True

    return False


def _strip_unwanted_elements(soup: BeautifulSoup) -> None:
    """
    Remove non-content elements from the soup in-place.

    Strips:
    - Tags listed in STRIP_TAGS (nav, header, footer, script, etc.)
    - Elements with class names matching STRIP_CLASS_PATTERNS
    - Elements with id attributes matching STRIP_CLASS_PATTERNS
    - Groww-specific noise elements (animated tickers, footer links, etc.)

    Note: Elements are collected into a list before decomposing to avoid
    modifying the tree while iterating. A guard checks element.attrs is
    not None (which happens when a parent was already decomposed).
    """
    # Remove tags by name
    for tag_name in STRIP_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    # Remove elements by class pattern — collect first, then decompose
    to_remove = []
    for element in soup.find_all(True):
        if not isinstance(element, Tag) or element.attrs is None:
            continue
        classes = element.get("class", [])
        if isinstance(classes, list):
            class_str = " ".join(classes)
        else:
            class_str = str(classes)

        if not class_str:
            continue

        # Check general noise patterns
        if STRIP_CLASS_PATTERNS.search(class_str):
            to_remove.append(element)
            continue

        # Check Groww-specific noise patterns
        if GROWW_NOISE_CLASS_PATTERNS.search(class_str):
            to_remove.append(element)
            continue

    for element in to_remove:
        if element.attrs is not None:  # Guard: may already be decomposed
            element.decompose()

    # Also check id attributes for the same patterns
    to_remove = []
    for element in soup.find_all(True):
        if not isinstance(element, Tag) or element.attrs is None:
            continue
        elem_id = element.get("id", "")
        if elem_id and STRIP_CLASS_PATTERNS.search(elem_id):
            to_remove.append(element)

    for element in to_remove:
        if element.attrs is not None:
            element.decompose()


def _table_to_markdown(table: Tag) -> str:
    """
    Convert an HTML <table> element to a Markdown-formatted table string.

    Handles tables with <thead>/<tbody> or simple <tr> rows.

    Args:
        table: BeautifulSoup Tag object representing a <table>.

    Returns:
        Markdown table string, or empty string if the table has no content.
    """
    rows = table.find_all("tr")
    if not rows:
        return ""

    md_rows = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        cell_texts = [
            re.sub(r"\s+", " ", cell.get_text(strip=True))
            for cell in cells
        ]
        if any(cell_texts):  # Skip entirely empty rows
            md_rows.append("| " + " | ".join(cell_texts) + " |")

    if not md_rows:
        return ""

    # Insert separator after the first row (header row)
    if len(md_rows) >= 2:
        num_cols = md_rows[0].count("|") - 1
        separator = "|" + "|".join([" --- "] * num_cols) + "|"
        md_rows.insert(1, separator)

    return "\n".join(md_rows)


def _detect_section_title(text: str) -> str | None:
    """
    Attempt to detect a section title from a text block by matching
    against known section keywords.

    Args:
        text: Text to scan (typically a heading or first line of a section).

    Returns:
        Matched section keyword (title-cased) or None.
    """
    text_lower = text.lower().strip()
    for keyword in SECTION_KEYWORDS:
        if keyword in text_lower:
            return keyword.title()
    return None


def _extract_sections(soup: BeautifulSoup) -> list[dict]:
    """
    Extract content sections from the cleaned soup.

    Walks through the body looking for heading elements (h1-h6) and
    content divs. Groups content under detected section titles.
    Filters out noise text (animated counters, duplicate stock names, etc.)

    Returns:
        List of dicts: [{"title": "...", "content": "..."}, ...]
    """
    sections = []
    current_section = {"title": "General", "content_parts": []}
    seen_texts = set()  # Track seen text to avoid duplicates

    body = soup.find("body") or soup

    for element in body.descendants:
        if not isinstance(element, Tag):
            continue

        # Detect headings
        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading_text = element.get_text(strip=True)
            if not heading_text:
                continue

            # Save current section if it has content
            if current_section["content_parts"]:
                content = "\n\n".join(current_section["content_parts"])
                content = _normalize_text(content)
                if content:
                    sections.append({
                        "title": current_section["title"],
                        "content": content,
                    })

            # Start a new section
            detected_title = _detect_section_title(heading_text)
            current_section = {
                "title": detected_title or heading_text,
                "content_parts": [],
            }
            seen_texts = set()  # Reset dedup per section
            continue

        # Collect tables as markdown
        if element.name == "table":
            md_table = _table_to_markdown(element)
            if md_table:
                current_section["content_parts"].append(md_table)
            continue

        # Collect paragraph/div text (only direct text, not nested)
        if element.name in ("p", "span", "li", "dd", "dt"):
            text = element.get_text(separator=" ", strip=True)

            # Skip noise text
            if not text or _is_noise_text(text):
                continue

            # Skip duplicates (e.g., stock names appearing both in
            # table and as individual span elements)
            text_key = text.strip().lower()
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)

            current_section["content_parts"].append(text)

    # Save the last section
    if current_section["content_parts"]:
        content = "\n\n".join(current_section["content_parts"])
        content = _normalize_text(content)
        if content:
            sections.append({
                "title": current_section["title"],
                "content": content,
            })

    return sections


def parse_html(html_content: str) -> dict:
    """
    Parse a raw HTML string into cleaned text and structured sections.

    Args:
        html_content: Raw HTML string from a scraped Groww page.

    Returns:
        Dict with keys:
            - full_text: Complete cleaned plain text
            - sections: List of {"title": ..., "content": ...} dicts
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Step 1: Strip unwanted elements
    _strip_unwanted_elements(soup)

    # Step 2: Extract structured sections
    sections = _extract_sections(soup)

    # Step 3: Build full text from sections
    text_parts = []
    for section in sections:
        text_parts.append(f"## {section['title']}\n\n{section['content']}")

    full_text = _normalize_text("\n\n".join(text_parts))

    return {
        "full_text": full_text,
        "sections": sections,
    }


def parse_single_file(html_path: Path, source_meta: dict) -> dict | None:
    """
    Parse a single raw HTML file and save the results.

    Produces:
    - data/processed/{scheme_id}.txt       — Full cleaned text
    - data/processed/{scheme_id}_parsed.json — Structured sections + metadata

    Args:
        html_path: Path to the raw HTML file.
        source_meta: Source metadata dict (from sources.json) with id, url, scheme, last_fetched.

    Returns:
        Parsed result dict on success, None if the file is too small or empty.
    """
    scheme_id = source_meta["id"]
    scheme_name = source_meta["scheme"]

    # Validate file
    if not html_path.exists():
        logger.warning(f"[{scheme_id}] HTML file not found: {html_path}")
        return None

    file_size = html_path.stat().st_size
    if file_size < 1024:
        logger.warning(
            f"[{scheme_id}] HTML file too small ({file_size} bytes) — "
            f"likely a failed scrape. Skipping."
        )
        return None

    # Read and parse
    logger.info(f"[{scheme_id}] Parsing {html_path.name} ({file_size:,} bytes)")
    html_content = html_path.read_text(encoding="utf-8")
    parsed = parse_html(html_content)

    if not parsed["full_text"]:
        logger.warning(f"[{scheme_id}] No content extracted from HTML.")
        return None

    # Ensure output directory exists
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save plain text
    txt_path = PROCESSED_DATA_DIR / f"{scheme_id}.txt"
    txt_path.write_text(parsed["full_text"], encoding="utf-8")
    logger.info(
        f"[{scheme_id}] Saved cleaned text → {txt_path.name} "
        f"({len(parsed['full_text']):,} chars)"
    )

    # Save structured JSON
    json_output = {
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "source_url": source_meta["url"],
        "last_fetched": source_meta.get("last_fetched"),
        "sections_count": len(parsed["sections"]),
        "full_text_length": len(parsed["full_text"]),
        "sections": parsed["sections"],
    }

    json_path = PROCESSED_DATA_DIR / f"{scheme_id}_parsed.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info(
        f"[{scheme_id}] Saved parsed JSON → {json_path.name} "
        f"({len(parsed['sections'])} sections)"
    )

    return json_output


def parse_all_sources() -> dict:
    """
    Parse all raw HTML files in data/raw/ using metadata from sources.json.

    Returns:
        Summary dict with keys: total, success, failed, results.
    """
    sources = load_sources()

    results = {
        "total": len(sources),
        "success": 0,
        "failed": 0,
        "results": [],
    }

    for source in sources:
        scheme_id = source["id"]
        html_path = RAW_DATA_DIR / f"{scheme_id}.html"

        parsed = parse_single_file(html_path, source)

        if parsed:
            results["success"] += 1
            results["results"].append({
                "id": scheme_id,
                "scheme": source["scheme"],
                "status": "success",
                "sections_count": parsed["sections_count"],
                "text_length": parsed["full_text_length"],
            })
        else:
            results["failed"] += 1
            results["results"].append({
                "id": scheme_id,
                "scheme": source["scheme"],
                "status": "failed",
                "sections_count": 0,
                "text_length": 0,
            })

    return results


def run_parser() -> dict:
    """
    Synchronous entry point for the parser.

    Returns:
        Summary dict with total, success, failed, and per-source results.
    """
    return parse_all_sources()


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    results = run_parser()

    print(f"\n{'═' * 60}")
    print(f"  Parsing Complete")
    print(f"  Total: {results['total']}  |  "
          f"Success: {results['success']}  |  "
          f"Failed: {results['failed']}")
    print(f"{'═' * 60}")

    for r in results["results"]:
        status_icon = "✓" if r["status"] == "success" else "✗"
        sections = f"({r['sections_count']} sections, {r['text_length']:,} chars)" \
            if r["status"] == "success" else ""
        print(f"  {status_icon} {r['scheme']}: {r['status']} {sections}")
