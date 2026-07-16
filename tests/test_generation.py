import pytest
from src.generation.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, format_context
from src.generation.formatter import format_response

def test_system_prompt_rules():
    assert "Answer ONLY using the provided context" in SYSTEM_PROMPT
    assert "MAXIMUM of 3 sentences" in SYSTEM_PROMPT
    assert "Do NOT provide investment advice" in SYSTEM_PROMPT
    assert "Source: [Document Title]" in SYSTEM_PROMPT

def test_format_context():
    chunks = [
        {
            "scheme_name": "HDFC Small Cap Fund",
            "section_title": "Expense Ratio",
            "source_url": "https://groww.in/test",
            "last_updated": "2026-06-30",
            "text": "The expense ratio is 0.68%."
        }
    ]
    formatted = format_context(chunks)
    assert "[Chunk 1] Scheme: HDFC Small Cap Fund | Section: Expense Ratio" in formatted
    assert "Source: https://groww.in/test | Last updated: 2026-06-30" in formatted
    assert "The expense ratio is 0.68%." in formatted

def test_user_prompt_template():
    prompt = USER_PROMPT_TEMPLATE.format(
        retrieved_chunks_with_metadata="CONTEXT_HERE",
        user_query="QUERY_HERE"
    )
    assert "CONTEXT_HERE" in prompt
    assert "QUERY_HERE" in prompt

def test_formatter_truncates_sentences():
    llm_output = "Sentence 1. Sentence 2. Sentence 3. Sentence 4. Sentence 5.\n\nSource: [Test](http://groww.in/test)\nLast updated from sources: 2026-06-30"
    res = format_response(llm_output, [])
    # Should only keep first 3 sentences of content + the source
    assert "Sentence 1. Sentence 2. Sentence 3." in res["answer"]
    assert "Sentence 4" not in res["answer"]
    assert "Source:" in res["answer"]

def test_formatter_injects_citation():
    llm_output = "The NAV is 150."
    chunks = [{"scheme_name": "Test Scheme", "source_url": "https://groww.in/123", "last_updated": "2026-07-01"}]
    res = format_response(llm_output, chunks)
    assert "Source: [Test Scheme – Groww](https://groww.in/123)" in res["answer"]
    assert "Last updated from sources: 2026-07-01" in res["answer"]

def test_formatter_removes_bad_urls():
    llm_output = "Check this out https://bad-website.com/test \n\nSource: [Test](https://groww.in/test)\nLast updated from sources: 2026-07-01"
    res = format_response(llm_output, [])
    assert "[UNVERIFIED_URL_REMOVED]" in res["answer"]
    assert "https://groww.in/test" in res["answer"]

def test_formatter_strips_advisory():
    llm_output = "I recommend that you invest in this fund. It is very good.\n\nSource: [Test](https://groww.in/test)\nLast updated from sources: 2026-07-01"
    res = format_response(llm_output, [])
    assert "I recommend" not in res["answer"].lower()
    assert "that you invest in this fund" in res["answer"]
