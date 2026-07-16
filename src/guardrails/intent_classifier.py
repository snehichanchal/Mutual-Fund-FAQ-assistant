import re
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class IntentResult:
    intent: str  # FACTUAL, ADVISORY, OUT_OF_SCOPE
    confidence: float
    matched_pattern: Optional[str]
    scheme_name: Optional[str] = None

# Exact names from sources.json
SCHEMES = [
    "HDFC Small Cap Fund",
    "HDFC Large Cap Fund",
    "HDFC Mid Cap Fund",
    "HDFC Gold ETF Fund of Fund",
    "HDFC Silver ETF FOF"
]

ADVISORY_PATTERNS = [
    r"\bshould\s+i\b",
    r"\brecommend\b",
    r"\bsuggest\b",
    r"\badvise\b",
    r"\bwhich\s+(fund|scheme)\s+is\s+(better|best)\b",
    r"\bvs\.?\b",
    r"\bcompare\b",
    r"\breturn\s+calculation\b",
    r"\bpredict\b",
    r"\bforecast\b"
]

MF_KEYWORDS = [
    "mutual fund", "nav", "aum", "sip", "lumpsum", "expense ratio",
    "exit load", "return", "holding", "portfolio", "fund manager", "benchmark"
]

def detect_scheme_name(query: str) -> Optional[str]:
    """Extracts scheme name from query using fuzzy/substring matching."""
    query_lower = query.lower()
    
    # Map common abbreviations/variants to the official scheme names
    scheme_mapping = {
        "small cap": "HDFC Small Cap Fund",
        "large cap": "HDFC Large Cap Fund",
        "mid cap": "HDFC Mid Cap Fund",
        "gold etf": "HDFC Gold ETF Fund of Fund",
        "gold fund": "HDFC Gold ETF Fund of Fund",
        "silver etf": "HDFC Silver ETF FOF",
        "silver fof": "HDFC Silver ETF FOF",
        "silver fund": "HDFC Silver ETF FOF",
    }
    
    # Check for exact official names first
    for scheme in SCHEMES:
        if scheme.lower() in query_lower:
            return scheme
            
    # Check for variants
    for variant, official_name in scheme_mapping.items():
        if variant in query_lower:
            return official_name
            
    return None

def classify_intent(query: str) -> IntentResult:
    """Classifies user intent into FACTUAL, ADVISORY, or OUT_OF_SCOPE."""
    query_lower = query.lower()
    
    # 1. Check for ADVISORY intent
    for pattern in ADVISORY_PATTERNS:
        if re.search(pattern, query_lower):
            return IntentResult(
                intent="ADVISORY", 
                confidence=1.0, 
                matched_pattern=pattern,
                scheme_name=detect_scheme_name(query)
            )
            
    # 2. Check for FACTUAL intent (needs scheme or MF keywords)
    scheme = detect_scheme_name(query)
    if scheme:
        return IntentResult(intent="FACTUAL", confidence=1.0, matched_pattern="scheme_match", scheme_name=scheme)
        
    for keyword in MF_KEYWORDS:
        if keyword in query_lower:
            return IntentResult(intent="FACTUAL", confidence=0.8, matched_pattern=keyword, scheme_name=None)
            
    # 3. Default to OUT_OF_SCOPE
    return IntentResult(intent="OUT_OF_SCOPE", confidence=1.0, matched_pattern=None, scheme_name=None)
