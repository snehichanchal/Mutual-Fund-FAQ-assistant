import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.api.server import app

client = TestClient(app)

@patch("src.api.routes.LLMClient")
@patch("src.api.routes.retrieve")
def test_chat_factual_query(mock_retrieve, mock_llm_client_cls):
    # Mock retrieval
    from src.retrieval.retriever import RetrievedChunk
    mock_chunk = RetrievedChunk(
        chunk_id="1",
        text="NAV is 100.",
        scheme_name="HDFC Small Cap Fund",
        section_title="NAV",
        source_url="http://test.com",
        last_updated="2026-01-01",
        token_count=10,
        chunk_type="test",
        similarity=0.9
    )
    mock_retrieve.return_value = [mock_chunk]
    
    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_llm_instance.generate_response.return_value = "NAV is 100. \n\nSource: [HDFC Small Cap Fund - Groww](http://test.com)\nLast updated from sources: 2026-01-01"
    mock_llm_client_cls.return_value = mock_llm_instance

    response = client.post(
        "/api/chat",
        json={"query": "What is the NAV of HDFC Small Cap Fund?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is False
    assert data["query_type"] == "FACTUAL"
    assert "NAV is 100" in data["answer"]
    assert data["source_url"] == "http://test.com"

def test_chat_advisory_query():
    response = client.post(
        "/api/chat",
        json={"query": "Should I invest in mutual funds?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is True
    assert data["query_type"] == "ADVISORY"
    assert "I can only provide factual information" in data["answer"]

def test_chat_pii_query():
    response = client.post(
        "/api/chat",
        json={"query": "My PAN is ABCDE1234F."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is True
    assert data["query_type"] == "PII"

def test_chat_malformed_query():
    response = client.post(
        "/api/chat",
        json={"query": "   "} # empty after strip
    )
    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is True
    assert data["query_type"] == "MALFORMED"

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
