"""
Data Ingestor - Multi-format document parser
Handles: PDF (scanned/digital), Excel, CSV
Extracts: Financial data, commitments, risks from unstructured documents
"""
import os
import re
import json
from typing import Dict, Any

import pdfplumber
import pandas as pd


def parse_document(file_path: str, doc_type: str) -> Dict[str, Any]:
    """Route document to the appropriate parser based on type and format."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        raw_text = extract_pdf_text(file_path)
    elif ext in (".xlsx", ".xls"):
        raw_text = extract_excel_text(file_path)
    elif ext == ".csv":
        raw_text = extract_csv_text(file_path)
    else:
        raw_text = ""

    # Route to the specialized parser
    parsers = {
        "gst": parse_gst,
        "itr": parse_itr,
        "bank_statement": parse_bank_statement,
        "annual_report": parse_annual_report,
        "financial_statement": parse_financial_statement,
        "board_minutes": parse_board_minutes,
        "rating_report": parse_rating_report,
        "shareholding": parse_shareholding,
        "sanction_letter": parse_sanction_letter,
        "legal_notice": parse_legal_notice,
    }

    parser = parsers.get(doc_type, parse_generic)
    return parser(raw_text, file_path)


def extract_pdf_text(file_path: str) -> str:
    """Extract text from PDF using pdfplumber (handles both digital and scanned PDFs)."""
    text_parts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

                # Also extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text_parts.append(" | ".join([str(c) if c else "" for c in row]))
    except Exception as e:
        text_parts.append(f"[PDF extraction error: {str(e)}]")

    return "\n".join(text_parts)


def extract_excel_text(file_path: str) -> str:
    """Extract data from Excel files."""
    try:
        dfs = pd.read_excel(file_path, sheet_name=None)
        parts = []
        for sheet_name, df in dfs.items():
            parts.append(f"=== Sheet: {sheet_name} ===")
            parts.append(df.to_string())
        return "\n".join(parts)
    except Exception as e:
        return f"[Excel extraction error: {str(e)}]"


def extract_csv_text(file_path: str) -> str:
    """Extract data from CSV files."""
    try:
        df = pd.read_csv(file_path)
        return df.to_string()
    except Exception as e:
        return f"[CSV extraction error: {str(e)}]"


# ─── Specialized Parsers ────────────────────────────────────────────────────

def _extract_amounts(text: str) -> list:
    """Extract monetary amounts from text (INR context)."""
    patterns = [
        r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)\s*(?:Cr|Crore|Lakh|L|cr|lakh)?',
        r'([\d,]+(?:\.\d{2})?)\s*(?:Cr|Crore|Lakh|crore|lakh)',
    ]
    amounts = []
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            try:
                amounts.append(float(m.replace(",", "")))
            except ValueError:
                pass
    return amounts


def _extract_dates(text: str) -> list:
    """Extract dates from text."""
    patterns = [
        r'\d{2}[/-]\d{2}[/-]\d{4}',
        r'\d{4}[/-]\d{2}[/-]\d{2}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}',
    ]
    dates = []
    for pat in patterns:
        dates.extend(re.findall(pat, text, re.IGNORECASE))
    return dates[:20]  # Cap at 20


def parse_gst(text: str, file_path: str) -> Dict[str, Any]:
    """Parse GST returns (GSTR-2A, GSTR-3B, etc.)."""
    amounts = _extract_amounts(text)
    gstr_type = "GSTR-3B" if "3B" in text.upper() else "GSTR-2A" if "2A" in text.upper() else "GST Return"

    # Extract GSTIN
    gstin_match = re.search(r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}', text)
    gstin = gstin_match.group() if gstin_match else "Not found"

    # Extract turnover figures
    turnover_keywords = ["taxable value", "total taxable", "turnover", "aggregate"]
    turnover_values = []
    for kw in turnover_keywords:
        idx = text.lower().find(kw)
        if idx != -1:
            nearby = text[idx:idx+100]
            vals = _extract_amounts(nearby)
            turnover_values.extend(vals)

    # Detect tax periods
    tax_periods = re.findall(r'(?:FY|AY|April|March|Quarter)\s*[\d\-/]+', text, re.IGNORECASE)

    return {
        "doc_type": "gst",
        "gstr_type": gstr_type,
        "gstin": gstin,
        "summary": f"{gstr_type} filing for GSTIN {gstin}",
        "fields": {
            "gstin": gstin,
            "gstr_type": gstr_type,
            "reported_turnover": turnover_values[:5] if turnover_values else amounts[:5],
            "tax_periods": tax_periods[:10],
            "total_amounts_found": amounts[:20],
        },
        "risks": _identify_gst_risks(text, amounts),
        "raw_text_length": len(text),
    }


def _identify_gst_risks(text: str, amounts: list) -> list:
    risks = []
    text_lower = text.lower()
    if "mismatch" in text_lower or "discrepancy" in text_lower:
        risks.append({"type": "DATA_MISMATCH", "severity": "HIGH", "detail": "Mismatch/discrepancy detected in GST filing"})
    if "nil return" in text_lower or "nil filing" in text_lower:
        risks.append({"type": "NIL_FILING", "severity": "MEDIUM", "detail": "Nil GST return detected - possible dormant period"})
    if "late fee" in text_lower or "penalty" in text_lower:
        risks.append({"type": "COMPLIANCE_ISSUE", "severity": "MEDIUM", "detail": "Late fees or penalties found in GST filing"})
    if "reverse charge" in text_lower:
        risks.append({"type": "REVERSE_CHARGE", "severity": "LOW", "detail": "Reverse charge mechanism transactions present"})
    # Check for large variance in amounts
    if len(amounts) >= 2:
        max_amt = max(amounts)
        min_amt = min(amounts) if min(amounts) > 0 else 1
        if max_amt / min_amt > 10:
            risks.append({"type": "AMOUNT_VARIANCE", "severity": "MEDIUM", "detail": f"High variance in amounts: {min_amt} to {max_amt}"})
    return risks


def parse_itr(text: str, file_path: str) -> Dict[str, Any]:
    """Parse Income Tax Returns."""
    amounts = _extract_amounts(text)
    pan_match = re.search(r'[A-Z]{5}\d{4}[A-Z]', text)
    pan = pan_match.group() if pan_match else "Not found"

    income_keywords = ["gross total income", "total income", "net income", "business income", "profit"]
    incomes = {}
    for kw in income_keywords:
        idx = text.lower().find(kw)
        if idx != -1:
            nearby_amounts = _extract_amounts(text[idx:idx+150])
            if nearby_amounts:
                incomes[kw] = nearby_amounts[0]

    return {
        "doc_type": "itr",
        "summary": f"ITR for PAN {pan}",
        "fields": {
            "pan": pan,
            "income_figures": incomes,
            "all_amounts": amounts[:20],
            "assessment_years": re.findall(r'(?:AY|FY)\s*\d{4}[\-/]\d{2,4}', text, re.IGNORECASE),
        },
        "risks": _identify_itr_risks(text, incomes),
        "raw_text_length": len(text),
    }


def _identify_itr_risks(text: str, incomes: dict) -> list:
    risks = []
    text_lower = text.lower()
    if "loss" in text_lower:
        risks.append({"type": "REPORTED_LOSS", "severity": "HIGH", "detail": "Business loss reported in ITR"})
    if "revised" in text_lower:
        risks.append({"type": "REVISED_RETURN", "severity": "MEDIUM", "detail": "Revised ITR filed - check for material changes"})
    if "audit" in text_lower and "report" in text_lower:
        risks.append({"type": "INFO", "severity": "LOW", "detail": "Tax audit report available"})
    return risks


def parse_bank_statement(text: str, file_path: str) -> Dict[str, Any]:
    """Parse bank statements."""
    amounts = _extract_amounts(text)

    # Try to extract credit/debit totals
    credit_total = 0
    debit_total = 0
    for kw in ["total credit", "credits total", "sum of credits"]:
        idx = text.lower().find(kw)
        if idx != -1:
            vals = _extract_amounts(text[idx:idx+100])
            if vals:
                credit_total = vals[0]
    for kw in ["total debit", "debits total", "sum of debits"]:
        idx = text.lower().find(kw)
        if idx != -1:
            vals = _extract_amounts(text[idx:idx+100])
            if vals:
                debit_total = vals[0]

    # Extract account number
    acc_match = re.search(r'(?:A/c|Account)\s*(?:No\.?|Number)?\s*:?\s*(\d{9,18})', text, re.IGNORECASE)
    account_no = acc_match.group(1) if acc_match else "Not found"

    # Extract bank name
    bank_names = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "Punjab National", "Bank of Baroda", "Union Bank", "Canara", "IndusInd"]
    detected_bank = "Unknown"
    for bn in bank_names:
        if bn.lower() in text.lower():
            detected_bank = bn
            break

    # Detect bounced cheques
    bounce_count = len(re.findall(r'bounce|dishonour|return|unpaid', text, re.IGNORECASE))

    return {
        "doc_type": "bank_statement",
        "summary": f"Bank statement from {detected_bank}, Account: {account_no}",
        "fields": {
            "bank_name": detected_bank,
            "account_number": account_no,
            "credit_total": credit_total,
            "debit_total": debit_total,
            "bounce_count": bounce_count,
            "statement_period": _extract_dates(text)[:2],
            "transaction_amounts": amounts[:30],
        },
        "risks": _identify_bank_risks(bounce_count, credit_total, debit_total),
        "raw_text_length": len(text),
    }


def _identify_bank_risks(bounce_count: int, credit_total: float, debit_total: float) -> list:
    risks = []
    if bounce_count > 0:
        severity = "HIGH" if bounce_count > 3 else "MEDIUM"
        risks.append({"type": "CHEQUE_BOUNCES", "severity": severity, "detail": f"{bounce_count} bounced/dishonoured transactions detected"})
    if credit_total > 0 and debit_total > 0 and debit_total > credit_total * 1.2:
        risks.append({"type": "CASH_OUTFLOW", "severity": "MEDIUM", "detail": "Debits significantly exceed credits"})
    return risks


def parse_annual_report(text: str, file_path: str) -> Dict[str, Any]:
    """Parse annual reports - extract key financial commitments and risks."""
    amounts = _extract_amounts(text)

    # Key sections to look for
    sections = {
        "directors_report": bool(re.search(r"director'?s?\s+report", text, re.IGNORECASE)),
        "auditor_report": bool(re.search(r"auditor'?s?\s+report|independent\s+auditor", text, re.IGNORECASE)),
        "balance_sheet": bool(re.search(r"balance\s+sheet", text, re.IGNORECASE)),
        "pnl": bool(re.search(r"profit\s+and\s+loss|income\s+statement|statement\s+of\s+profit", text, re.IGNORECASE)),
        "cash_flow": bool(re.search(r"cash\s+flow", text, re.IGNORECASE)),
        "notes_to_accounts": bool(re.search(r"notes\s+to\s+(?:the\s+)?(?:financial\s+)?(?:statement|account)", text, re.IGNORECASE)),
    }

    # Extract contingent liabilities
    contingent_section = ""
    idx = text.lower().find("contingent liabilit")
    if idx != -1:
        contingent_section = text[idx:idx+500]

    # Extract related party transactions
    rpt_section = ""
    idx = text.lower().find("related party")
    if idx != -1:
        rpt_section = text[idx:idx+500]

    risks = []
    text_lower = text.lower()
    risk_keywords = {
        "going concern": ("GOING_CONCERN", "CRITICAL"),
        "material weakness": ("MATERIAL_WEAKNESS", "HIGH"),
        "qualified opinion": ("QUALIFIED_AUDIT", "HIGH"),
        "adverse opinion": ("ADVERSE_AUDIT", "CRITICAL"),
        "contingent liabilit": ("CONTINGENT_LIABILITY", "MEDIUM"),
        "default": ("DEFAULT_MENTION", "HIGH"),
        "fraud": ("FRAUD_MENTION", "CRITICAL"),
        "litigation": ("LITIGATION", "MEDIUM"),
    }
    for keyword, (risk_type, severity) in risk_keywords.items():
        if keyword in text_lower:
            risks.append({"type": risk_type, "severity": severity, "detail": f"'{keyword}' mentioned in annual report"})

    return {
        "doc_type": "annual_report",
        "summary": f"Annual report with {sum(sections.values())}/{len(sections)} key sections identified",
        "fields": {
            "sections_found": sections,
            "key_amounts": amounts[:20],
            "contingent_liabilities_excerpt": contingent_section[:300],
            "related_party_excerpt": rpt_section[:300],
        },
        "risks": risks,
        "raw_text_length": len(text),
    }


def parse_financial_statement(text: str, file_path: str) -> Dict[str, Any]:
    """Parse standalone financial statements."""
    amounts = _extract_amounts(text)
    ratios = {}

    # Try to find key financial ratios
    ratio_patterns = {
        "current_ratio": r"current\s+ratio\s*[:\-]?\s*([\d.]+)",
        "debt_equity": r"debt[\s\-/]+equity\s*[:\-]?\s*([\d.]+)",
        "pat_margin": r"(?:PAT|net\s+profit)\s*margin\s*[:\-]?\s*([\d.]+)\s*%?",
        "roe": r"(?:ROE|return\s+on\s+equity)\s*[:\-]?\s*([\d.]+)\s*%?",
        "interest_coverage": r"interest\s+coverage\s*[:\-]?\s*([\d.]+)",
    }
    for name, pat in ratio_patterns.items():
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            ratios[name] = float(match.group(1))

    return {
        "doc_type": "financial_statement",
        "summary": f"Financial statement with {len(ratios)} ratios extracted",
        "fields": {
            "ratios": ratios,
            "key_amounts": amounts[:20],
        },
        "risks": [],
        "raw_text_length": len(text),
    }


def parse_board_minutes(text: str, file_path: str) -> Dict[str, Any]:
    """Extract key decisions from board meeting minutes."""
    risks = []
    text_lower = text.lower()

    if "resignation" in text_lower:
        risks.append({"type": "DIRECTOR_RESIGNATION", "severity": "MEDIUM", "detail": "Director resignation mentioned"})
    if "loan" in text_lower and "approv" in text_lower:
        risks.append({"type": "NEW_BORROWING", "severity": "LOW", "detail": "New borrowing approval in board minutes"})

    return {
        "doc_type": "board_minutes",
        "summary": "Board meeting minutes parsed",
        "fields": {"dates": _extract_dates(text), "amounts": _extract_amounts(text)[:10]},
        "risks": risks,
        "raw_text_length": len(text),
    }


def parse_rating_report(text: str, file_path: str) -> Dict[str, Any]:
    """Parse credit rating agency reports (CRISIL, ICRA, CARE, etc.)."""
    # Detect rating agency
    agencies = {"CRISIL": "CRISIL", "ICRA": "ICRA", "CARE": "CARE", "Brickwork": "Brickwork", "India Ratings": "India Ratings", "ACUITE": "Acuité"}
    detected_agency = "Unknown"
    for key, val in agencies.items():
        if key.lower() in text.lower():
            detected_agency = val
            break

    # Extract rating
    rating_match = re.search(r'([A-Z]{1,5}[\+\-]?\s*(?:\(.*?\))?)\s*(?:rating|assigned|reaffirmed|upgraded|downgraded)', text, re.IGNORECASE)
    rating = rating_match.group(1).strip() if rating_match else "Not found"

    # Detect outlook
    outlook_match = re.search(r'outlook\s*[:\-]?\s*(stable|positive|negative|watch)', text, re.IGNORECASE)
    outlook = outlook_match.group(1).capitalize() if outlook_match else "Not specified"

    risks = []
    if "downgrad" in text.lower():
        risks.append({"type": "RATING_DOWNGRADE", "severity": "HIGH", "detail": "Rating downgrade mentioned"})
    if "negative" in outlook.lower() or "watch" in outlook.lower():
        risks.append({"type": "NEGATIVE_OUTLOOK", "severity": "MEDIUM", "detail": f"Rating outlook: {outlook}"})

    return {
        "doc_type": "rating_report",
        "summary": f"Rating by {detected_agency}: {rating} (Outlook: {outlook})",
        "fields": {"agency": detected_agency, "rating": rating, "outlook": outlook},
        "risks": risks,
        "raw_text_length": len(text),
    }


def parse_shareholding(text: str, file_path: str) -> Dict[str, Any]:
    """Parse shareholding pattern."""
    promoter_match = re.search(r'promoter.*?(\d+\.?\d*)\s*%', text, re.IGNORECASE)
    public_match = re.search(r'public.*?(\d+\.?\d*)\s*%', text, re.IGNORECASE)

    fields = {
        "promoter_holding": float(promoter_match.group(1)) if promoter_match else None,
        "public_holding": float(public_match.group(1)) if public_match else None,
    }

    risks = []
    if fields["promoter_holding"] and fields["promoter_holding"] < 30:
        risks.append({"type": "LOW_PROMOTER_HOLDING", "severity": "MEDIUM", "detail": f"Promoter holding is only {fields['promoter_holding']}%"})

    # Check for pledged shares
    pledge_match = re.search(r'pledg.*?(\d+\.?\d*)\s*%', text, re.IGNORECASE)
    if pledge_match:
        pledge_pct = float(pledge_match.group(1))
        fields["pledged_shares_pct"] = pledge_pct
        if pledge_pct > 20:
            risks.append({"type": "HIGH_PLEDGE", "severity": "HIGH", "detail": f"{pledge_pct}% promoter shares pledged"})

    return {
        "doc_type": "shareholding",
        "summary": f"Shareholding pattern - Promoter: {fields.get('promoter_holding', 'N/A')}%",
        "fields": fields,
        "risks": risks,
        "raw_text_length": len(text),
    }


def parse_sanction_letter(text: str, file_path: str) -> Dict[str, Any]:
    """Parse sanction letters from other banks."""
    amounts = _extract_amounts(text)
    return {
        "doc_type": "sanction_letter",
        "summary": f"Sanction letter with {len(amounts)} amount references",
        "fields": {
            "sanctioned_amounts": amounts[:10],
            "dates": _extract_dates(text)[:5],
        },
        "risks": [],
        "raw_text_length": len(text),
    }


def parse_legal_notice(text: str, file_path: str) -> Dict[str, Any]:
    """Parse legal notices."""
    amounts = _extract_amounts(text)
    risks = [{"type": "LEGAL_NOTICE", "severity": "HIGH", "detail": "Legal notice/dispute document present"}]

    if "winding up" in text.lower():
        risks.append({"type": "WINDING_UP", "severity": "CRITICAL", "detail": "Winding up petition mentioned"})
    if "nclt" in text.lower() or "tribunal" in text.lower():
        risks.append({"type": "TRIBUNAL_CASE", "severity": "HIGH", "detail": "NCLT/tribunal proceedings mentioned"})

    return {
        "doc_type": "legal_notice",
        "summary": "Legal notice/dispute document",
        "fields": {"amounts_at_stake": amounts[:10], "dates": _extract_dates(text)[:5]},
        "risks": risks,
        "raw_text_length": len(text),
    }


def parse_generic(text: str, file_path: str) -> Dict[str, Any]:
    """Fallback generic parser."""
    return {
        "doc_type": "other",
        "summary": f"Document parsed ({len(text)} chars extracted)",
        "fields": {
            "amounts": _extract_amounts(text)[:20],
            "dates": _extract_dates(text)[:10],
        },
        "risks": [],
        "raw_text_length": len(text),
    }
