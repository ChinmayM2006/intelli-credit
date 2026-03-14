"""
Auto-classifier for Indian financial documents.
Layer 1: Fast keyword-based classification
Layer 2: LLM-based classification (when available)
"""
import re
from typing import Dict, Any, Optional

# Keyword signatures per document type with weights
DOC_SIGNATURES = {
    "alm": {
        "keywords": {
            "asset liability": 5, "alm": 5, "maturity bucket": 4, "cumulative mismatch": 5,
            "nii sensitivity": 4, "liquidity ratio": 3, "1-30 days": 3, "31-90 days": 3,
            "181-365 days": 3, "time bucket": 4, "structural liquidity": 4,
            "outflow": 2, "inflow": 2, "mismatch": 3, "maturity": 2,
        },
        "total_possible": 52,
    },
    "shareholding": {
        "keywords": {
            "shareholding pattern": 5, "promoter": 4, "public holding": 4,
            "pledged": 4, "encumbered": 3, "fii": 3, "dii": 3, "mutual fund": 2,
            "custodian": 2, "depository": 2, "category of shareholder": 4,
            "non-promoter": 3, "total shareholding": 4, "shares held": 3,
        },
        "total_possible": 46,
    },
    "borrowing_profile": {
        "keywords": {
            "borrowing": 4, "lender": 4, "facility": 4, "sanctioned": 4,
            "outstanding": 3, "overdue": 4, "repayment schedule": 5,
            "working capital": 3, "term loan": 3, "cash credit": 3,
            "overdraft": 3, "consortium": 3, "security": 2, "collateral": 2,
            "rate of interest": 3, "emi": 2, "installment": 2,
        },
        "total_possible": 54,
    },
    "annual_report": {
        "keywords": {
            "profit and loss": 5, "balance sheet": 5, "cash flow": 5,
            "directors report": 4, "auditor": 4, "notes to account": 3,
            "revenue from operations": 4, "total income": 3, "depreciation": 2,
            "reserves and surplus": 3, "share capital": 3, "ind as": 3,
            "schedule": 2, "significant accounting": 3, "contingent liabilit": 3,
            "related party": 3, "earnings per share": 3,
        },
        "total_possible": 58,
    },
    "portfolio": {
        "keywords": {
            "portfolio": 4, "aum": 5, "npa": 4, "gnpa": 5, "nnpa": 5,
            "collection efficiency": 5, "sector exposure": 4, "disbursement": 3,
            "restructured": 4, "write off": 3, "provision coverage": 4,
            "top borrower": 3, "concentration": 3, "vintage": 2,
            "delinquency": 3, "bucket": 2, "0-30 dpd": 3, "30-60 dpd": 3,
            "90+ dpd": 3, "stage 1": 2, "stage 2": 2, "stage 3": 3,
        },
        "total_possible": 72,
    },
    "gst": {
        "keywords": {
            "gstr": 5, "gstin": 5, "gst": 4, "taxable value": 4,
            "igst": 3, "cgst": 3, "sgst": 3, "itc": 4,
            "input tax credit": 4, "reverse charge": 3, "hsn": 3,
            "e-way bill": 2, "outward supplies": 3, "inward supplies": 3,
        },
        "total_possible": 49,
    },
    "financial_statement": {
        "keywords": {
            "current ratio": 4, "debt equity": 4, "interest coverage": 4,
            "pat margin": 3, "roe": 3, "roce": 3, "ebitda": 3,
            "net worth": 3, "total assets": 2, "total liabilities": 2,
            "ratio analysis": 4, "financial ratio": 4,
        },
        "total_possible": 39,
    },
    "itr": {
        "keywords": {
            "income tax return": 5, "itr": 5, "assessment year": 5,
            "pan": 4, "gross total income": 4, "total income": 3,
            "tax payable": 3, "refund": 2, "form 26as": 4, "tds": 3,
            "advance tax": 3, "self assessment": 3, "section 80": 2,
            "computation of income": 4,
        },
        "total_possible": 50,
    },
    "bank_statement": {
        "keywords": {
            "bank statement": 5, "account statement": 5, "transaction": 3,
            "opening balance": 4, "closing balance": 4, "credit": 2, "debit": 2,
            "cheque": 3, "neft": 3, "rtgs": 3, "imps": 2, "upi": 2,
            "account number": 4, "ifsc": 3, "bank name": 3, "bounce": 4,
            "ecs return": 3, "emi": 2, "interest charged": 2,
        },
        "total_possible": 57,
    },
    "board_minutes": {
        "keywords": {
            "board of directors": 5, "minutes": 5, "resolution": 5,
            "board meeting": 5, "chairperson": 3, "quorum": 4,
            "agenda": 3, "approved": 3, "resolved": 4, "unanimous": 2,
            "authoris": 3, "appointed": 2, "certified copy": 3,
        },
        "total_possible": 47,
    },
    "rating_report": {
        "keywords": {
            "credit rating": 5, "rating report": 5, "crisil": 4, "icra": 4,
            "care": 3, "india ratings": 4, "brickwork": 3, "acuite": 3,
            "rating rationale": 5, "outlook": 4, "stable": 2, "negative": 2,
            "positive": 2, "watch": 2, "upgrade": 3, "downgrade": 3,
            "long term": 2, "short term": 2, "aaa": 3, "aa": 2,
        },
        "total_possible": 61,
    },
    "sanction_letter": {
        "keywords": {
            "sanction letter": 5, "sanctioned": 4, "sanction": 3,
            "facility": 4, "disbursement": 4, "credit facility": 4,
            "terms and conditions": 3, "security": 3, "hypothecation": 3,
            "margin": 2, "processing fee": 3, "validity": 3,
            "drawdown": 3, "repayment": 3, "rate of interest": 3,
        },
        "total_possible": 50,
    },
    "legal_notice": {
        "keywords": {
            "legal notice": 5, "advocate": 4, "court": 3, "tribunal": 3,
            "plaintiff": 3, "defendant": 3, "suit": 3, "petition": 3,
            "arbitration": 4, "nclt": 4, "nclat": 3, "claim": 3,
            "damages": 3, "injunction": 3, "compliance": 2, "order": 2,
        },
        "total_possible": 49,
    },
}


def classify_document(text: str, filename: str = "") -> Dict[str, Any]:
    """
    Classify a document using keyword scoring.
    Returns: {predicted_type, confidence, evidence, needs_review}
    """
    text_lower = text.lower()
    filename_lower = filename.lower()
    scores = {}
    evidence = {}

    for doc_type, sig in DOC_SIGNATURES.items():
        score = 0
        matched_keywords = []
        for kw, weight in sig["keywords"].items():
            count = text_lower.count(kw)
            if count > 0:
                score += weight * min(count, 3)  # Cap at 3 occurrences
                matched_keywords.append(f"{kw} ({count}x)")

        # Filename bonus
        if doc_type in filename_lower or any(k in filename_lower for k in list(sig["keywords"].keys())[:3]):
            score += 5

        normalized = min(score / sig["total_possible"], 1.0) if sig["total_possible"] > 0 else 0
        scores[doc_type] = normalized
        evidence[doc_type] = matched_keywords[:5]

    # Find best match
    if not scores:
        return {"predicted_type": "other", "confidence": 0, "evidence": [], "needs_review": True, "all_scores": {}}

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # Check if second-best is close
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    needs_review = False
    if best_score < 0.2:
        needs_review = True
        best_type = "other"
    elif len(sorted_scores) > 1 and sorted_scores[1][1] > best_score * 0.8:
        needs_review = True  # Ambiguous

    return {
        "predicted_type": best_type,
        "confidence": round(best_score, 3),
        "evidence": evidence.get(best_type, []),
        "needs_review": needs_review,
        "all_scores": {k: round(v, 3) for k, v in sorted_scores[:5]},
    }


async def classify_with_llm(text: str, filename: str = "") -> Dict[str, Any]:
    """Enhanced classification using LLM (Layer 2)."""
    from backend.llm.provider import get_llm

    # First do keyword classification
    keyword_result = classify_document(text, filename)

    llm = get_llm()
    if llm.name == "fallback":
        return keyword_result

    # Only call LLM if keyword result is uncertain
    if keyword_result["confidence"] > 0.6 and not keyword_result["needs_review"]:
        return keyword_result

    prompt = f"""Classify this Indian financial document into ONE of these categories:
- alm (Asset-Liability Management statement)
- shareholding (Shareholding Pattern report)
- borrowing_profile (Borrowing/Loan facility details)
- annual_report (Annual Report with P&L, Balance Sheet, Cash Flow)
- portfolio (Portfolio data, NPA report, collection data)
- gst (GST Return - GSTR-1/2A/2B/3B)
- financial_statement (Financial ratios / standalone financials)
- itr (Income Tax Return - ITR forms, computation of income)
- bank_statement (Bank account statement with transactions)
- board_minutes (Board meeting minutes and resolutions)
- rating_report (Credit rating report from CRISIL, ICRA, CARE etc.)
- sanction_letter (Loan sanction/facility letter from banks)
- legal_notice (Legal notices, court orders, litigation documents)
- other (None of the above)

Filename: {filename}

First 3000 characters of document:
{text[:3000]}

Respond in JSON format:
{{"type": "category_name", "confidence": 0.0-1.0, "evidence": "brief reason"}}"""

    try:
        response = await llm.generate(prompt, json_mode=True)
        import json
        llm_result = json.loads(response)
        llm_type = llm_result.get("type", "other")
        llm_conf = float(llm_result.get("confidence", 0.5))

        # Combine keyword and LLM results
        if llm_type == keyword_result["predicted_type"]:
            final_conf = max(llm_conf, keyword_result["confidence"])
        else:
            # They disagree — go with higher confidence
            if llm_conf > keyword_result["confidence"]:
                return {
                    "predicted_type": llm_type,
                    "confidence": round(llm_conf, 3),
                    "evidence": [llm_result.get("evidence", "")],
                    "needs_review": True,
                    "all_scores": keyword_result["all_scores"],
                }
            final_conf = keyword_result["confidence"]

        keyword_result["confidence"] = round(final_conf, 3)
        keyword_result["needs_review"] = final_conf < 0.5
        return keyword_result

    except Exception:
        return keyword_result
