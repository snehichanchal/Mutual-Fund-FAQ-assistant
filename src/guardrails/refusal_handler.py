from typing import Dict, Any

from src.config import AMFI_INVESTOR_LINK

def get_refusal_response(intent: str, pii_warning: str = "") -> Dict[str, Any]:
    """Returns static refusal responses based on intent or PII block."""
    
    disclaimer = "Facts-only. No investment advice."
    
    if intent == "PII":
        message = pii_warning or "For your security, please do not share personal information."
    elif intent == "ADVISORY":
        message = f"I can only provide factual information about HDFC mutual fund schemes. I do not provide investment advice, recommendations, or comparisons. For general investor education, visit {AMFI_INVESTOR_LINK}."
    elif intent == "OUT_OF_SCOPE":
        message = f"I'm a facts-only assistant for HDFC schemes on Groww. I can only answer questions related to those specific mutual funds. For general mutual fund queries, please visit {AMFI_INVESTOR_LINK}."
    elif intent == "MALFORMED":
        message = "Could you please rephrase your question? Try asking about NAV, Expense Ratio, Returns, or Holdings of a specific scheme."
    else:
        message = "I cannot process this request."
        
    return {
        "answer": message,
        "refused": True,
        "disclaimer": disclaimer,
        "source": None
    }
