import re
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json

from src.config import MAX_QUERY_LENGTH, SOURCES_FILE, RATE_LIMIT
from src.api.limiter import limiter
from src.guardrails.pii_filter import scan_input
from src.guardrails.intent_classifier import classify_intent
from src.guardrails.refusal_handler import get_refusal_response
from src.retrieval.retriever import retrieve
from src.generation.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, format_context
from src.generation.llm_client import LLMClient
from src.generation.formatter import format_response

router = APIRouter()

class ChatRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_LENGTH, min_length=1)
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    last_updated: Optional[str] = None
    refused: bool
    query_type: str

def sanitize_input(text: str) -> str:
    """Regex stripping of HTML tags, script content, SQL keywords."""
    # Strip HTML tags
    clean = re.sub(r'<[^>]*>', '', text)
    # Basic SQL injection keywords strip
    sql_patterns = [r'\bSELECT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bINSERT\b', r'\bDROP\b', r'\b--\b']
    for pat in sql_patterns:
        clean = re.sub(pat, '', clean, flags=re.IGNORECASE)
    return clean.strip()

@router.get("/api/health")
async def health_check():
    return {"status": "ok"}

@router.get("/api/schemes")
async def list_schemes():
    try:
        with open(SOURCES_FILE, "r") as f:
            data = json.load(f)
            return {"schemes": [s.get("scheme") for s in data.get("sources", [])]}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load schemes")

@router.post("/api/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat(request: Request, body: ChatRequest):
    query = body.query.strip()
    if not query:
        refusal = get_refusal_response("MALFORMED")
        return ChatResponse(
            answer=refusal["answer"],
            refused=True,
            query_type="MALFORMED"
        )
        
    # Step 2: Sanitize input
    safe_query = sanitize_input(query)
    
    if not safe_query:
        refusal = get_refusal_response("MALFORMED")
        return ChatResponse(
            answer=refusal["answer"],
            refused=True,
            query_type="MALFORMED"
        )

    # Step 3: PII Filter scan
    pii_res = scan_input(safe_query)
    if pii_res.blocked:
        refusal = get_refusal_response("PII", pii_res.warning_message)
        return ChatResponse(
            answer=refusal["answer"],
            refused=True,
            query_type="PII"
        )
    
    safe_query = pii_res.cleaned_text
    
    # Step 4: Intent Classification
    intent_res = classify_intent(safe_query)
    if intent_res.intent in ["ADVISORY", "OUT_OF_SCOPE", "MALFORMED"]:
        refusal = get_refusal_response(intent_res.intent)
        return ChatResponse(
            answer=refusal["answer"],
            refused=True,
            query_type=intent_res.intent
        )
        
    # Step 5 & 6: Vector search
    try:
        chunks = retrieve(query=safe_query, scheme_name=intent_res.scheme_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Retrieval failed")
        
    if not chunks:
        return ChatResponse(
            answer="I don't have this information in my knowledge base.",
            refused=False,
            query_type=intent_res.intent
        )
        
    # Step 7: Build prompt
    chunks_dicts = [chunk.to_dict() for chunk in chunks]
    context_str = format_context(chunks_dicts)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        retrieved_chunks_with_metadata=context_str,
        user_query=safe_query
    )
    
    # Step 8: Call LLM
    llm_client = LLMClient()
    try:
        llm_output = llm_client.generate_response(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt
        )
        if not llm_output:
             raise HTTPException(status_code=503, detail="Service temporarily unavailable due to high demand")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable due to high demand")
        
    # Step 9: Format response
    final_result = format_response(llm_output, chunks_dicts)
    
    # Try to extract source url and title from top chunk
    source_url = None
    source_title = None
    last_updated = None
    if chunks:
        source_url = chunks[0].source_url
        source_title = f"{chunks[0].scheme_name} - Groww"
        last_updated = chunks[0].last_updated

    return ChatResponse(
        answer=final_result["answer"],
        source_url=source_url,
        source_title=source_title,
        last_updated=last_updated,
        refused=False,
        query_type=intent_res.intent
    )
