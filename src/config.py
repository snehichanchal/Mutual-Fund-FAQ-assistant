"""
Centralized configuration for the Mutual Fund FAQ Assistant.

Loads environment variables from .env and defines all application constants.
Reference: Architecture §3 and Implementation Plan §2.3
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Project Paths ───────────────────────────────────────────────────────────

# Root of the project (two levels up from src/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SOURCES_FILE = DATA_DIR / "sources.json"

# ChromaDB persistence directory
CHROMA_PERSIST_DIR = DATA_DIR / "chromadb"

# Frontend directory
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# ─── Environment Variables ───────────────────────────────────────────────────

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")

# Groq API key (required for LLM generation)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# CORS origins for the API server
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")

# ─── Embedding Model Configuration ──────────────────────────────────────────
# Reference: Architecture §3.1.4

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384
EMBEDDING_BATCH_SIZE = 32
EMBEDDING_QUERY_PREFIX = "Represent this sentence: "

# ─── LLM Configuration ──────────────────────────────────────────────────────
# Reference: Architecture §3.4.2

LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 300
LLM_RETRY_ATTEMPTS = 3

# ─── Chunking Configuration ─────────────────────────────────────────────────
# Reference: Architecture §3.1.3, Implementation Plan §3.4

CHUNK_SIZE_MAX = 500       # Maximum tokens per chunk
CHUNK_SIZE_MIN = 20        # Minimum tokens per chunk (below this, chunk is discarded)
CHUNK_OVERLAP = 50         # Token overlap between adjacent chunks
CHUNK_TOKENIZER = "cl100k_base"  # tiktoken tokenizer for token counting

# 3-Tier chunking thresholds (Implementation Plan §3.4.2)
CHUNK_MERGE_THRESHOLD = 75       # Tier 1: sections ≤ this are merged into composites
CHUNK_MERGE_MAX_COMPOSITE = 300  # Maximum tokens for a Tier 1 composite chunk
CHUNK_SPLIT_TARGET = 300         # Target sub-chunk size when splitting Tier 3 sections

# ─── Vector Store Configuration ──────────────────────────────────────────────
# Reference: Architecture §3.2

COLLECTION_NAME = "hdfc_mf_corpus"
TOP_K_RETRIEVAL = 5        # Initial retrieval count
TOP_K_RERANK = 3           # Count after reranking
SIMILARITY_THRESHOLD = 0.65  # Minimum cosine similarity for retrieval
RERANKER_ENABLED = False   # Toggle cross-encoder reranking (placeholder)

# ─── API Server Configuration ────────────────────────────────────────────────
# Reference: Architecture §6.2

RATE_LIMIT = "30/minute"   # Max requests per IP per minute
MAX_QUERY_LENGTH = 500     # Maximum character length for user queries

# ─── Scraper Configuration ───────────────────────────────────────────────────
# Reference: Implementation Plan §3.2

SCRAPER_TIMEOUT = 30000         # Page load timeout in milliseconds
SCRAPER_RETRY_ATTEMPTS = 3     # Number of retry attempts per page
SCRAPER_DELAY_BETWEEN_PAGES = 2  # Seconds between page requests

# ─── Whitelisted Domains ─────────────────────────────────────────────────────
# Reference: Implementation Plan §5.7 — URLs allowed in LLM responses

WHITELISTED_DOMAINS = [
    "groww.in",
    "hdfcfund.com",
    "amfiindia.com",
    "sebi.gov.in",
]

# ─── Refusal Links ───────────────────────────────────────────────────────────

AMFI_INVESTOR_LINK = "https://www.amfiindia.com/investor-corner"

# ─── Validation ──────────────────────────────────────────────────────────────

def validate_config():
    """
    Validate that critical configuration values are set.
    Raises EnvironmentError if required values are missing.
    """
    errors = []

    if not GROQ_API_KEY:
        errors.append(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and set your Groq API key. "
            "Get a free key at https://console.groq.com"
        )

    if not SOURCES_FILE.exists():
        errors.append(
            f"sources.json not found at {SOURCES_FILE}. "
            "Ensure data/sources.json exists with the scheme registry."
        )

    if errors:
        raise EnvironmentError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )
