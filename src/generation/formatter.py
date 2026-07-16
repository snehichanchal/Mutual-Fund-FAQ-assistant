import re
from typing import Optional, Dict

from src.config import WHITELISTED_DOMAINS
from src.guardrails.pii_filter import scan_output

def sanitize_urls(text: str) -> str:
    """Removes URLs that are not in the whitelisted domains."""
    url_pattern = r'https?://[^\s)\]]+'
    def replace_url(match):
        url = match.group(0)
        if any(domain in url for domain in WHITELISTED_DOMAINS):
            return url
        return "[UNVERIFIED_URL_REMOVED]"
    return re.sub(url_pattern, replace_url, text)

def strip_advisory_language(text: str) -> str:
    """Strips common hallucinated advisory phrases."""
    advisory_phrases = [
        r"(?i)\bi recommend\b",
        r"(?i)\byou should\b",
        r"(?i)\bin my opinion\b",
        r"(?i)\bi advise\b",
        r"(?i)\bit is better to\b"
    ]
    cleaned = text
    for phrase in advisory_phrases:
         cleaned = re.sub(phrase, "", cleaned)
    # clean up extra spaces left behind
    cleaned = re.sub(r' +', ' ', cleaned).strip()
    return cleaned

def enforce_three_sentences(text: str) -> str:
    """Truncates the answer to a maximum of 3 sentences, preserving the citation."""
    lines = text.strip().split('\n')
    citation_lines = []
    content_lines = []
    
    for line in lines:
        if line.startswith("Source:") or line.startswith("Last updated from sources:"):
            citation_lines.append(line)
        else:
            content_lines.append(line)
            
    content = " ".join(content_lines)
    # Simple sentence split heuristic
    sentences = re.split(r'(?<=[.!?])\s+', content.strip())
    sentences = [s for s in sentences if s]
    
    if len(sentences) > 3:
        sentences = sentences[:3]
        
    truncated_content = " ".join(sentences)
    
    final_parts = [truncated_content]
    if citation_lines:
        final_parts.append("")
        final_parts.extend(citation_lines)
        
    return "\n".join(final_parts)
    
def inject_citation_if_missing(text: str, chunks: list) -> str:
    if "Source:" not in text and chunks:
        first_chunk = chunks[0]
        url = first_chunk.get("source_url", "")
        scheme = first_chunk.get("scheme_name", "Scheme")
        date = first_chunk.get("last_updated", "YYYY-MM-DD")
        
        citation = f"\n\nSource: [{scheme} – Groww]({url})\nLast updated from sources: {date}"
        return text.strip() + citation
    return text

def format_response(llm_output: str, retrieved_chunks: list) -> Dict[str, str]:
    """Applies post-processing rules to the LLM response."""
    # 1. Strip advisory language
    text = strip_advisory_language(llm_output)
    
    # 2. Inject citation if missing
    text = inject_citation_if_missing(text, retrieved_chunks)
    
    # 3. Truncate to 3 sentences
    text = enforce_three_sentences(text)
    
    # 4. Sanitize URLs
    text = sanitize_urls(text)
    
    # 5. Scan output for PII
    text = scan_output(text)
    
    return {
        "answer": text,
        "refused": False,
        "disclaimer": "Facts-only. No investment advice."
    }
