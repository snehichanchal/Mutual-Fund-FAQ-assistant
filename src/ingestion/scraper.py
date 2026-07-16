"""
Groww.in Scheme Page Scraper

Fetches raw HTML snapshots from Groww mutual fund scheme pages using
Playwright (headless Chromium). Groww pages are JS-rendered, so a
real browser engine is required.

Reference: Implementation Plan §3.2, Architecture §3.1.1
"""

import json
import asyncio
import time
import logging
from datetime import date
from pathlib import Path

from src.config import (
    SOURCES_FILE,
    RAW_DATA_DIR,
    SCRAPER_TIMEOUT,
    SCRAPER_RETRY_ATTEMPTS,
    SCRAPER_DELAY_BETWEEN_PAGES,
)

logger = logging.getLogger(__name__)

# Custom user agent to reduce bot detection risk
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def load_sources() -> list[dict]:
    """
    Load the scheme registry from data/sources.json.

    Returns:
        List of source dicts, each containing id, url, scheme, last_fetched.

    Raises:
        FileNotFoundError: If sources.json does not exist.
        json.JSONDecodeError: If sources.json is malformed.
        KeyError: If the 'sources' key is missing.
    """
    if not SOURCES_FILE.exists():
        raise FileNotFoundError(f"sources.json not found at {SOURCES_FILE}")

    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "sources" not in data:
        raise KeyError("'sources' key missing from sources.json")

    sources = data["sources"]
    if not sources:
        logger.warning("sources.json contains 0 sources — nothing to scrape.")

    return sources


def update_last_fetched(source_id: str) -> None:
    """
    Update the last_fetched timestamp for a specific source in sources.json.

    Args:
        source_id: The id of the source to update (e.g. 'hdfc-small-cap').
    """
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for source in data["sources"]:
        if source["id"] == source_id:
            source["last_fetched"] = date.today().isoformat()
            break

    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


async def scrape_page(page, url: str, scheme_id: str) -> str | None:
    """
    Scrape a single Groww scheme page with retry logic.

    - Navigates to the URL with wait_until='networkidle'
    - Scrolls to bottom to trigger lazy-loaded content
    - Waits for the main content area to render
    - Returns the full page HTML

    Args:
        page: Playwright page object.
        url: The Groww scheme URL to scrape.
        scheme_id: Identifier for logging (e.g. 'hdfc-small-cap').

    Returns:
        Raw HTML string on success, None on failure after all retries.
    """
    for attempt in range(1, SCRAPER_RETRY_ATTEMPTS + 1):
        try:
            logger.info(
                f"[{scheme_id}] Attempt {attempt}/{SCRAPER_RETRY_ATTEMPTS} — "
                f"Loading {url}"
            )

            # Navigate with networkidle to wait for JS rendering
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=SCRAPER_TIMEOUT,
            )

            # Check HTTP status
            if response and response.status >= 400:
                logger.warning(
                    f"[{scheme_id}] HTTP {response.status} — "
                    f"page may be moved or deleted."
                )
                if response.status == 404:
                    logger.error(f"[{scheme_id}] 404 Not Found — skipping.")
                    return None

            # Scroll to bottom to trigger lazy-loaded sections
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 300;
                        const timer = setInterval(() => {
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= document.body.scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)

            # Brief wait after scroll for remaining content to load
            await page.wait_for_timeout(2000)

            # Extract full page HTML
            html = await page.content()

            # Basic validation — ensure we got meaningful content
            if len(html) < 1024:
                logger.warning(
                    f"[{scheme_id}] HTML too small ({len(html)} bytes) — "
                    f"may be a partial load. Retrying..."
                )
                continue

            logger.info(
                f"[{scheme_id}] Successfully scraped — "
                f"{len(html):,} bytes of HTML"
            )
            return html

        except Exception as e:
            logger.warning(
                f"[{scheme_id}] Attempt {attempt} failed: {type(e).__name__}: {e}"
            )
            if attempt < SCRAPER_RETRY_ATTEMPTS:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 sec
                logger.info(f"[{scheme_id}] Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

    logger.error(
        f"[{scheme_id}] All {SCRAPER_RETRY_ATTEMPTS} attempts failed — skipping."
    )
    return None


async def scrape_all_sources() -> dict:
    """
    Scrape all 5 Groww scheme pages and save raw HTML to data/raw/.

    Uses a single Playwright browser instance with one page, processing
    schemes sequentially with a configurable delay between pages.

    Returns:
        Summary dict with keys: total, success, failed, results.
    """
    from playwright.async_api import async_playwright

    sources = load_sources()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "total": len(sources),
        "success": 0,
        "failed": 0,
        "results": [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
        )
        page = await context.new_page()

        for i, source in enumerate(sources):
            scheme_id = source["id"]
            url = source["url"]
            scheme_name = source["scheme"]

            logger.info(
                f"\n{'─' * 60}\n"
                f"[{i + 1}/{len(sources)}] Scraping: {scheme_name}\n"
                f"  URL: {url}\n"
                f"{'─' * 60}"
            )

            html = await scrape_page(page, url, scheme_id)

            if html:
                # Save raw HTML snapshot
                output_path = RAW_DATA_DIR / f"{scheme_id}.html"
                output_path.write_text(html, encoding="utf-8")

                # Update last_fetched timestamp in sources.json
                update_last_fetched(scheme_id)

                results["success"] += 1
                results["results"].append({
                    "id": scheme_id,
                    "scheme": scheme_name,
                    "status": "success",
                    "file": str(output_path),
                    "size_bytes": len(html),
                })

                logger.info(
                    f"[{scheme_id}] Saved to {output_path} "
                    f"({len(html):,} bytes)"
                )
            else:
                results["failed"] += 1
                results["results"].append({
                    "id": scheme_id,
                    "scheme": scheme_name,
                    "status": "failed",
                    "file": None,
                    "size_bytes": 0,
                })

            # Delay between pages to avoid rate limiting
            if i < len(sources) - 1:
                logger.info(
                    f"Waiting {SCRAPER_DELAY_BETWEEN_PAGES}s before next page..."
                )
                await asyncio.sleep(SCRAPER_DELAY_BETWEEN_PAGES)

        await browser.close()

    return results


def run_scraper() -> dict:
    """
    Synchronous entry point for the scraper.
    Runs the async scrape_all_sources() via asyncio.

    Returns:
        Summary dict with total, success, failed, and per-source results.
    """
    return asyncio.run(scrape_all_sources())


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    results = run_scraper()

    print(f"\n{'═' * 60}")
    print(f"  Scraping Complete")
    print(f"  Total: {results['total']}  |  "
          f"Success: {results['success']}  |  "
          f"Failed: {results['failed']}")
    print(f"{'═' * 60}")

    for r in results["results"]:
        status_icon = "✓" if r["status"] == "success" else "✗"
        size = f"({r['size_bytes']:,} bytes)" if r["size_bytes"] else ""
        print(f"  {status_icon} {r['scheme']}: {r['status']} {size}")
