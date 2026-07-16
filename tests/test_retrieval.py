import pytest
from unittest.mock import patch, MagicMock

from src.retrieval.retriever import retrieve, RetrievedChunk

@pytest.fixture
def mock_chunks():
    return [
        RetrievedChunk(
            chunk_id="chunk1",
            text="The expense ratio of HDFC Small Cap Fund is 0.68%.",
            scheme_name="HDFC Small Cap Fund",
            section_title="Expense Ratio",
            source_url="http://groww.in/test",
            last_updated="2026-06-30",
            token_count=15,
            chunk_type="single_section",
            similarity=0.88
        )
    ]

@patch("src.retrieval.retriever.search")
@patch("src.retrieval.retriever.embed_query")
def test_retrieve_factual(mock_embed, mock_search, mock_chunks):
    mock_embed.return_value = [0.1] * 384
    mock_search.return_value = [chunk.to_dict() for chunk in mock_chunks]
    
    results = retrieve("What is the expense ratio?", scheme_name="HDFC Small Cap Fund")
    
    assert len(results) == 1
    assert results[0].scheme_name == "HDFC Small Cap Fund"
    assert results[0].similarity == 0.88

@patch("src.retrieval.retriever.search")
@patch("src.retrieval.retriever.embed_query")
def test_retrieve_no_results(mock_embed, mock_search):
    mock_embed.return_value = [0.1] * 384
    mock_search.return_value = []
    
    results = retrieve("What is the expense ratio?", scheme_name="Unknown Fund")
    
    assert len(results) == 0

def test_retrieve_empty_query():
    results = retrieve("")
    assert len(results) == 0
