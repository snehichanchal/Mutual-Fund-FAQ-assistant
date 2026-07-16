import pytest
from src.guardrails.intent_classifier import classify_intent, IntentResult
from src.guardrails.pii_filter import scan_input
from src.guardrails.refusal_handler import get_refusal_response
from src.config import AMFI_INVESTOR_LINK

def test_intent_classifier_advisory():
    advisory_queries = [
        "Should I invest in HDFC Small Cap?",
        "Recommend a good mutual fund",
        "Which scheme is better, Small Cap or Mid Cap?",
        "Suggest a fund for 5 years",
        "HDFC Mid Cap vs Large Cap",
        "Compare Small Cap with Mid Cap",
        "Return calculation for HDFC Small Cap",
        "Can you predict the market?"
    ]
    for query in advisory_queries:
        res = classify_intent(query)
        assert res.intent == "ADVISORY"

def test_intent_classifier_factual():
    factual_queries = [
        "What is the NAV of HDFC Small Cap Fund?",
        "Expense ratio of HDFC Mid Cap",
        "Who is the fund manager?",
        "Tell me about HDFC Gold ETF Fund of Fund",
        "Can I do SIP in Large Cap?",
        "What is the AUM?",
        "Show me the portfolio holdings",
        "Exit load of silver fund"
    ]
    for query in factual_queries:
        res = classify_intent(query)
        assert res.intent == "FACTUAL"

def test_intent_classifier_out_of_scope():
    oos_queries = [
        "What is the capital of India?",
        "Tell me a joke",
        "How to cook pasta?",
        "Who won the match?",
        "Are you an AI?"
    ]
    for query in oos_queries:
        res = classify_intent(query)
        assert res.intent == "OUT_OF_SCOPE"

def test_pii_filter_pan():
    res = scan_input("My PAN is ABCDE1234F, what should I do?")
    assert res.blocked == True
    assert "PAN" in res.pii_types

def test_pii_filter_aadhaar():
    res = scan_input("Here is my Aadhaar 1234 5678 9012")
    assert res.blocked == True
    assert "Aadhaar" in res.pii_types

def test_pii_filter_phone_email():
    res = scan_input("Call me at 9876543210 or email test@example.com")
    assert res.blocked == False
    assert "Phone" in res.pii_types
    assert "Email" in res.pii_types
    assert "[PHONE_REDACTED]" in res.cleaned_text
    assert "[EMAIL_REDACTED]" in res.cleaned_text

def test_pii_filter_clean():
    res = scan_input("What is the NAV of small cap?")
    assert res.blocked == False
    assert res.has_pii == False

def test_refusal_handler():
    # Advisory
    res = get_refusal_response("ADVISORY")
    assert res["refused"] == True
    assert AMFI_INVESTOR_LINK in res["answer"]
    assert "Facts-only" in res["disclaimer"]
    
    # PII
    res2 = get_refusal_response("PII", "Blocked PII")
    assert res2["refused"] == True
    assert res2["answer"] == "Blocked PII"
