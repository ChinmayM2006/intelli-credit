"""
LLM-assisted document extraction.
Sends raw text + structured prompts to LLM for high-precision field extraction.
Falls back to regex parsers when no LLM is available.
"""
import json
from typing import Dict, Any, Optional

EXTRACTION_PROMPTS = {
    "alm": """Extract the following from this ALM (Asset-Liability Management) document. Return JSON:
{
    "maturity_buckets": {
        "1_30_days": {"inflows": 0, "outflows": 0, "mismatch": 0},
        "31_90_days": {"inflows": 0, "outflows": 0, "mismatch": 0},
        "91_180_days": {"inflows": 0, "outflows": 0, "mismatch": 0},
        "181_365_days": {"inflows": 0, "outflows": 0, "mismatch": 0},
        "1_3_years": {"inflows": 0, "outflows": 0, "mismatch": 0},
        "3_5_years": {"inflows": 0, "outflows": 0, "mismatch": 0},
        "over_5_years": {"inflows": 0, "outflows": 0, "mismatch": 0}
    },
    "cumulative_mismatch_pct": 0,
    "nii_sensitivity_100bps": 0,
    "liquidity_coverage_ratio": 0,
    "negative_mismatch_buckets": []
}""",

    "shareholding": """Extract from this Shareholding Pattern document. Return JSON:
{
    "promoter_holding_pct": 0,
    "public_holding_pct": 0,
    "fii_holding_pct": 0,
    "dii_holding_pct": 0,
    "pledged_shares_pct": 0,
    "encumbered_pct": 0,
    "promoter_entities": [],
    "qoq_change_promoter": 0,
    "total_shareholders": 0,
    "top_10_shareholders": []
}""",

    "borrowing_profile": """Extract from this Borrowing Profile document. Return JSON:
{
    "total_sanctioned": 0,
    "total_outstanding": 0,
    "total_overdue": 0,
    "facilities": [
        {"lender": "", "type": "TL/WC/CC/OD", "sanctioned": 0, "outstanding": 0, "overdue": 0, "rate": 0}
    ],
    "number_of_lenders": 0,
    "working_capital_limit": 0,
    "term_loan_outstanding": 0,
    "primary_security": "",
    "collateral_security": ""
}""",

    "annual_report": """Extract from this Annual Report. Return JSON:
{
    "profit_and_loss": {
        "revenue": 0, "other_income": 0, "total_income": 0,
        "total_expenses": 0, "ebitda": 0, "depreciation": 0,
        "interest_expense": 0, "pbt": 0, "tax": 0, "pat": 0
    },
    "balance_sheet": {
        "share_capital": 0, "reserves": 0, "total_equity": 0,
        "long_term_debt": 0, "short_term_debt": 0, "total_debt": 0,
        "current_assets": 0, "current_liabilities": 0,
        "total_assets": 0, "net_worth": 0
    },
    "cash_flow": {
        "cfo": 0, "cfi": 0, "cff": 0, "net_cash_flow": 0
    },
    "ratios": {
        "de_ratio": 0, "current_ratio": 0, "icr": 0,
        "pat_margin_pct": 0, "roe_pct": 0, "roce_pct": 0,
        "debt_ebitda": 0
    },
    "audit_opinion": "unqualified/qualified/adverse/disclaimer",
    "contingent_liabilities": 0,
    "related_party_transactions": ""
}""",

    "portfolio": """Extract from this Portfolio/Performance document. Return JSON:
{
    "total_aum": 0,
    "gnpa_pct": 0,
    "nnpa_pct": 0,
    "provision_coverage_ratio": 0,
    "collection_efficiency_pct": 0,
    "restructured_book_pct": 0,
    "write_off_amount": 0,
    "sector_exposure": [{"sector": "", "pct": 0}],
    "top_borrower_concentration_pct": 0,
    "stage_1_pct": 0,
    "stage_2_pct": 0,
    "stage_3_pct": 0,
    "disbursements_current_period": 0,
    "dpd_buckets": {"0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
}""",

    "gst": """Extract from this GST Return document. Return JSON:
{
    "gstin": "",
    "gstr_type": "GSTR-1/2A/2B/3B/9",
    "tax_period": "",
    "taxable_turnover": 0,
    "igst": 0, "cgst": 0, "sgst": 0,
    "itc_claimed": 0,
    "itc_eligible": 0,
    "itc_mismatch": 0,
    "reverse_charge_amount": 0,
    "late_fee": 0,
    "nil_rated_supplies": 0,
    "exempt_supplies": 0
}""",

    "itr": """Extract from this Income Tax Return document. Return JSON:
{
    "pan": "",
    "assessment_year": "",
    "itr_form": "",
    "gross_total_income": 0,
    "total_income": 0,
    "total_tax_payable": 0,
    "tax_paid": 0,
    "refund_claimed": 0,
    "income_from_business": 0,
    "income_from_other_sources": 0,
    "deductions_80c": 0,
    "total_deductions": 0
}""",

    "bank_statement": """Extract from this Bank Statement document. Return JSON:
{
    "bank_name": "",
    "account_number": "",
    "account_type": "",
    "statement_period": "",
    "opening_balance": 0,
    "closing_balance": 0,
    "total_credits": 0,
    "total_debits": 0,
    "average_monthly_balance": 0,
    "bounce_count": 0,
    "emi_payments_found": 0,
    "largest_credit": 0,
    "largest_debit": 0,
    "monthly_inflow_trend": [],
    "cash_deposit_pct": 0
}""",

    "rating_report": """Extract from this Credit Rating Report. Return JSON:
{
    "rating_agency": "",
    "instrument": "",
    "rating": "",
    "outlook": "",
    "previous_rating": "",
    "rating_action": "reaffirmed/upgraded/downgraded/assigned",
    "rated_amount_cr": 0,
    "key_strengths": [],
    "key_concerns": [],
    "financial_summary": {}
}""",

    "sanction_letter": """Extract from this Sanction Letter document. Return JSON:
{
    "sanctioning_bank": "",
    "facility_type": "",
    "sanctioned_amount": 0,
    "interest_rate": 0,
    "tenure_months": 0,
    "security_primary": "",
    "security_collateral": "",
    "processing_fee_pct": 0,
    "conditions_precedent": [],
    "covenants": [],
    "validity_date": ""
}""",

    "legal_notice": """Extract from this Legal/Litigation document. Return JSON:
{
    "case_type": "",
    "court_tribunal": "",
    "parties": [],
    "amount_at_stake": 0,
    "date_filed": "",
    "current_status": "",
    "relief_sought": "",
    "next_hearing_date": "",
    "risk_assessment": "low/medium/high/critical"
}""",
}


async def extract_with_llm(raw_text: str, doc_type: str) -> Optional[Dict[str, Any]]:
    """
    Use LLM to extract structured data from raw document text.
    Returns extracted fields dict, or None if LLM is unavailable.
    """
    from backend.llm.provider import get_llm

    llm = get_llm()
    if llm.name == "fallback":
        return None

    prompt_template = EXTRACTION_PROMPTS.get(doc_type)
    if not prompt_template:
        return None

    system_prompt = (
        "You are an expert Indian financial document parser. "
        "Extract financial data with high precision. Use 0 for missing numeric fields. "
        "Amounts should be in the original unit (Crores/Lakhs as stated). "
        "Return ONLY valid JSON."
    )

    prompt = f"""{prompt_template}

Document text (first 6000 chars):
{raw_text[:6000]}"""

    try:
        response = await llm.generate(prompt, system_prompt=system_prompt, json_mode=True)
        # Clean response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return json.loads(response)
    except (json.JSONDecodeError, Exception):
        return None
