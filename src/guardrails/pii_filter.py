import re
from dataclasses import dataclass
from typing import List

@dataclass
class PIIResult:
    has_pii: bool
    pii_types: List[str]
    cleaned_text: str
    blocked: bool
    warning_message: str

PII_PATTERNS = {
    "PAN": r"[A-Z]{5}[0-9]{4}[A-Z]",
    "Aadhaar": r"\d{4}\s?\d{4}\s?\d{4}",
    "Phone": r"(\+91[\s\-]?)?[6-9]\d{9}",
    "Email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "Account Number": r"\b\d{9,18}\b"
}

ACCOUNT_KEYWORDS = ["account", "bank", "demat", "folio", "a/c", "acct"]

def scan_input(query: str) -> PIIResult:
    has_pii = False
    pii_types = []
    blocked = False
    warning_message = ""
    cleaned_text = query
    
    # Check PAN
    if re.search(PII_PATTERNS["PAN"], query, re.IGNORECASE):
        has_pii = True
        pii_types.append("PAN")
        blocked = True
        
    # Check Aadhaar
    if re.search(PII_PATTERNS["Aadhaar"], query):
        has_pii = True
        pii_types.append("Aadhaar")
        blocked = True
        
    # Check Account Number (Context aware)
    query_lower = query.lower()
    has_account_context = any(kw in query_lower for kw in ACCOUNT_KEYWORDS)
    if has_account_context and re.search(PII_PATTERNS["Account Number"], query):
        has_pii = True
        pii_types.append("Account Number")
        blocked = True
        
    # Check Phone
    if re.search(PII_PATTERNS["Phone"], cleaned_text):
        has_pii = True
        pii_types.append("Phone")
        cleaned_text = re.sub(PII_PATTERNS["Phone"], "[PHONE_REDACTED]", cleaned_text)
        
    # Check Email
    if re.search(PII_PATTERNS["Email"], cleaned_text, re.IGNORECASE):
        has_pii = True
        pii_types.append("Email")
        cleaned_text = re.sub(PII_PATTERNS["Email"], "[EMAIL_REDACTED]", cleaned_text, flags=re.IGNORECASE)
        
    if blocked:
        warning_message = "For your security, please do not share personal information like PAN, Aadhaar, or Account numbers."
        
    return PIIResult(
        has_pii=has_pii,
        pii_types=pii_types,
        cleaned_text=cleaned_text,
        blocked=blocked,
        warning_message=warning_message
    )

def scan_output(response: str) -> str:
    # Always strip, never block
    cleaned = response
    cleaned = re.sub(PII_PATTERNS["PAN"], "[PAN_REDACTED]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(PII_PATTERNS["Aadhaar"], "[AADHAAR_REDACTED]", cleaned)
    cleaned = re.sub(PII_PATTERNS["Phone"], "[PHONE_REDACTED]", cleaned)
    cleaned = re.sub(PII_PATTERNS["Email"], "[EMAIL_REDACTED]", cleaned, flags=re.IGNORECASE)
    
    # Simple strip for account numbers in output just in case
    has_account_context = any(kw in cleaned.lower() for kw in ACCOUNT_KEYWORDS)
    if has_account_context:
         cleaned = re.sub(PII_PATTERNS["Account Number"], "[ACCOUNT_REDACTED]", cleaned)
         
    return cleaned
