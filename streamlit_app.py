"""
Streamlit App — Mutual Fund FAQ Assistant

Replaces the FastAPI + HTML/CSS/JS frontend with a single Streamlit interface.
Calls the same RAG pipeline modules directly (no HTTP layer).

Reference: docs/deployment_plan.md
"""

import re
import json
import logging

import streamlit as st

from src.config import SOURCES_FILE
from src.guardrails.pii_filter import scan_input
from src.guardrails.intent_classifier import classify_intent
from src.guardrails.refusal_handler import get_refusal_response
from src.retrieval.retriever import retrieve
from src.generation.prompt_templates import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    format_context,
)
from src.generation.llm_client import LLMClient
from src.generation.formatter import format_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Page Configuration ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="HDFC Fund FAQ Assistant",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

/* Global overrides */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Main container */
.stApp {
    background: #0f172a;
    background-image:
        radial-gradient(circle at 15% 50%, rgba(99, 102, 241, 0.12), transparent 25%),
        radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.12), transparent 25%);
}

/* Header badge */
.disclaimer-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8rem;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.05);
    padding: 6px 16px;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin-bottom: 0.5rem;
}

.disclaimer-badge .pulse-dot {
    width: 7px;
    height: 7px;
    background: #34d399;
    border-radius: 50%;
    display: inline-block;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%   { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52,211,153,.7); }
    70%  { transform: scale(1);    box-shadow: 0 0 0 6px rgba(52,211,153,0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52,211,153,0); }
}

/* Title gradient */
.gradient-title {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 1.75rem;
    margin: 0;
    line-height: 1.3;
}

/* Example chip buttons */
.example-chip {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 10px 16px;
    border-radius: 12px;
    font-size: 0.85rem;
    font-family: 'Inter', sans-serif;
    cursor: pointer;
    transition: all 0.2s ease;
    width: 100%;
    text-align: left;
}

.example-chip:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: #6366f1;
    color: #f8fafc;
    transform: translateY(-1px);
}

/* Welcome card */
.welcome-card {
    background: rgba(79, 70, 229, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 18px;
    padding: 24px;
    margin-bottom: 1rem;
}

.welcome-card h3 {
    margin: 0 0 8px 0;
    font-weight: 500;
    color: #f8fafc;
    font-size: 1.1rem;
}

.welcome-card p {
    margin: 0 0 6px 0;
    color: #94a3b8;
    font-size: 0.95rem;
    line-height: 1.5;
}

/* Citation box */
.citation-box {
    margin-top: 10px;
    padding: 8px 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 0.78rem;
    color: #94a3b8;
}

.citation-box a {
    color: #8b5cf6;
    text-decoration: none;
}

.citation-box a:hover {
    text-decoration: underline;
    color: #6366f1;
}

/* Refusal message styling */
.refusal-msg {
    background: rgba(217, 119, 6, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 14px;
    padding: 14px 18px;
    color: #fcd34d;
    font-size: 0.92rem;
    line-height: 1.5;
}

/* Error message styling */
.error-msg {
    background: rgba(220, 38, 38, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 14px;
    padding: 14px 18px;
    color: #fca5a5;
    font-size: 0.92rem;
    line-height: 1.5;
}

/* Scheme card in sidebar */
.scheme-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 8px;
    color: #e2e8f0;
    font-size: 0.88rem;
    transition: all 0.2s;
}

.scheme-card:hover {
    border-color: rgba(99, 102, 241, 0.4);
    background: rgba(99, 102, 241, 0.08);
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: #1e293b;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

/* Chat input styling */
.stChatInput > div {
    border-color: rgba(255, 255, 255, 0.15) !important;
    background: rgba(0, 0, 0, 0.2) !important;
}

.stChatInput > div:focus-within {
    border-color: #8b5cf6 !important;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
}

/* Chat message containers */
.stChatMessage {
    background: transparent !important;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)


# ─── Cached Resources ───────────────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def load_schemes() -> list[dict]:
    """Load scheme list from sources.json (cached)."""
    try:
        with open(SOURCES_FILE, "r") as f:
            data = json.load(f)
        return data.get("sources", [])
    except Exception:
        return []


# ─── Helper Functions ────────────────────────────────────────────────────────


def sanitize_input(text: str) -> str:
    """Strip HTML tags, script content, SQL keywords."""
    clean = re.sub(r"<[^>]*>", "", text)
    sql_patterns = [
        r"\bSELECT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bINSERT\b",
        r"\bDROP\b",
        r"\b--\b",
    ]
    for pat in sql_patterns:
        clean = re.sub(pat, "", clean, flags=re.IGNORECASE)
    return clean.strip()


def process_query(query: str) -> dict:
    """
    Run the full RAG pipeline. Returns a dict with:
    answer, source_url, source_title, last_updated, refused, query_type
    """
    # Step 1: Sanitize
    safe_query = sanitize_input(query)
    if not safe_query:
        refusal = get_refusal_response("MALFORMED")
        return {
            "answer": refusal["answer"],
            "refused": True,
            "query_type": "MALFORMED",
        }

    # Step 2: PII check
    pii_res = scan_input(safe_query)
    if pii_res.blocked:
        refusal = get_refusal_response("PII", pii_res.warning_message)
        return {"answer": refusal["answer"], "refused": True, "query_type": "PII"}
    safe_query = pii_res.cleaned_text

    # Step 3: Intent classification
    intent_res = classify_intent(safe_query)
    if intent_res.intent in ["ADVISORY", "OUT_OF_SCOPE", "MALFORMED"]:
        refusal = get_refusal_response(intent_res.intent)
        return {
            "answer": refusal["answer"],
            "refused": True,
            "query_type": intent_res.intent,
        }

    # Step 4: Retrieve chunks
    try:
        chunks = retrieve(query=safe_query, scheme_name=intent_res.scheme_name)
    except Exception as e:
        logger.error("Retrieval failed: %s", e)
        return {
            "answer": "I'm temporarily unable to process your question. Please try again shortly.",
            "refused": False,
            "query_type": "ERROR",
        }

    if not chunks:
        return {
            "answer": "I don't have this information in my knowledge base.",
            "refused": False,
            "query_type": intent_res.intent,
        }

    # Step 5: Generate LLM response
    chunks_dicts = [chunk.to_dict() for chunk in chunks]
    context_str = format_context(chunks_dicts)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        retrieved_chunks_with_metadata=context_str,
        user_query=safe_query,
    )

    try:
        llm_client = LLMClient()
        llm_output = llm_client.generate_response(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        if not llm_output:
            return {
                "answer": "Service temporarily unavailable due to high demand. Please try again shortly.",
                "refused": False,
                "query_type": "ERROR",
            }
    except Exception as e:
        logger.error("LLM generation failed: %s", e)
        return {
            "answer": "Service temporarily unavailable due to high demand. Please try again shortly.",
            "refused": False,
            "query_type": "ERROR",
        }

    # Step 6: Format response
    final_result = format_response(llm_output, chunks_dicts)

    return {
        "answer": final_result["answer"],
        "source_url": chunks[0].source_url,
        "source_title": f"{chunks[0].scheme_name} – Groww",
        "last_updated": chunks[0].last_updated,
        "refused": False,
        "query_type": intent_res.intent,
    }


# ─── Session State ───────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []


# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown('<p class="gradient-title">📊 HDFC Fund FAQ Assistant</p>', unsafe_allow_html=True)
st.markdown(
    '<div class="disclaimer-badge">'
    '<span class="pulse-dot"></span>'
    "Facts-only · No investment advice · Powered by Groww data"
    "</div>",
    unsafe_allow_html=True,
)


# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📋 Supported Schemes")
    schemes = load_schemes()
    for scheme in schemes:
        st.markdown(
            f'<div class="scheme-card">'
            f'<a href="{scheme.get("url", "#")}" target="_blank" '
            f'style="color: #e2e8f0; text-decoration: none;">'
            f'{scheme.get("scheme", "Unknown")}'
            f"</a></div>",
            unsafe_allow_html=True,
        )
    st.markdown("---")
    st.markdown(
        '<p style="font-size: 0.75rem; color: #64748b;">'
        "Data sourced exclusively from Groww.in<br>"
        "Disclaimer: Facts-only. No investment advice."
        "</p>",
        unsafe_allow_html=True,
    )


# ─── Chat History Display ────────────────────────────────────────────────────

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            data = message.get("data", {})
            if data.get("refused"):
                st.markdown(
                    f'<div class="refusal-msg">{data["answer"]}</div>',
                    unsafe_allow_html=True,
                )
            elif data.get("query_type") == "ERROR":
                st.markdown(
                    f'<div class="error-msg">{data["answer"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(data.get("answer", message.get("content", "")))
                if data.get("source_url"):
                    st.markdown(
                        f'<div class="citation-box">'
                        f'Source: <a href="{data["source_url"]}" target="_blank">'
                        f'{data.get("source_title", "Link")}</a>'
                        f'<br>Last updated: {data.get("last_updated", "Unknown")}'
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(message["content"])


# ─── Welcome Card + Example Chips (shown only on first load) ─────────────────

if not st.session_state.messages:
    st.markdown(
        '<div class="welcome-card">'
        "<h3>Hello! 👋</h3>"
        "<p>I'm a facts-only assistant for HDFC mutual fund schemes on Groww.</p>"
        "<p>You can ask me about Expense Ratios, NAV, AUM, Returns, "
        "Exit Loads, Holdings, and more.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    EXAMPLE_QUESTIONS = [
        "What is the expense ratio of HDFC Small Cap Fund?",
        "What is the exit load of HDFC Mid Cap Fund?",
        "What is the minimum SIP amount for HDFC Large Cap Fund?",
    ]

    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for idx, (col, question) in enumerate(zip(cols, EXAMPLE_QUESTIONS)):
        with col:
            if st.button(
                question,
                key=f"example_{idx}",
                use_container_width=True,
            ):
                st.session_state["_pending_query"] = question
                st.rerun()


# ─── Chat Input ──────────────────────────────────────────────────────────────

# Handle pending query from example chips
pending = st.session_state.pop("_pending_query", None)
prompt = pending or st.chat_input("Ask about HDFC mutual funds...")

if prompt:
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge base..."):
            result = process_query(prompt)

        if result.get("refused"):
            st.markdown(
                f'<div class="refusal-msg">{result["answer"]}</div>',
                unsafe_allow_html=True,
            )
        elif result.get("query_type") == "ERROR":
            st.markdown(
                f'<div class="error-msg">{result["answer"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(result.get("answer", ""))
            if result.get("source_url"):
                st.markdown(
                    f'<div class="citation-box">'
                    f'Source: <a href="{result["source_url"]}" target="_blank">'
                    f'{result.get("source_title", "Link")}</a>'
                    f'<br>Last updated: {result.get("last_updated", "Unknown")}'
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # Save to session state
    st.session_state.messages.append(
        {"role": "assistant", "content": result.get("answer", ""), "data": result}
    )
