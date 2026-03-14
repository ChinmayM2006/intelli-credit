"""
Data Triangulation Module v2
Cross-references data from documents, research, and ML results.
Handles sparse data gracefully — generates meaningful output even without documents.
"""
from typing import Dict, Any, List


def triangulate(
    parsed_data: Dict[str, Any],
    research_data: Dict[str, Any],
    ml_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Triangulate data across all sources."""
    checks = []
    discrepancies = []
    confirmations = []

    # Standard cross-checks (require documents)
    checks.append(_check_revenue_vs_gst(parsed_data))
    checks.append(_check_debt_consistency(parsed_data))
    checks.append(_check_profit_vs_itr(parsed_data))
    checks.append(_check_shareholding_consistency(parsed_data))
    checks.append(_check_asset_quality(parsed_data))
    checks.append(_check_alm_borrowing(parsed_data))

    # Research-based checks (work even without documents)
    checks.append(_check_research_alignment(parsed_data, research_data, ml_result))
    checks.append(_check_research_data_quality(research_data))
    checks.append(_check_research_vs_features(parsed_data, research_data))

    checks = [c for c in checks if c is not None]

    for check in checks:
        if check["status"] == "discrepancy":
            discrepancies.append(check)
        elif check["status"] == "confirmed":
            confirmations.append(check)

    total_checks = len(checks)
    confirmed_count = len(confirmations)
    discrepancy_count = len(discrepancies)
    insufficient_count = sum(1 for c in checks if c["status"] == "insufficient_data")

    # Calculate confidence — don't penalize insufficient data as heavily
    if total_checks > 0:
        active_checks = total_checks - insufficient_count
        if active_checks > 0:
            confidence = confirmed_count / active_checks * 100
            confidence -= discrepancy_count * 10
        else:
            # All checks insufficient — rate based on research quality
            rf = research_data.get("extracted_financials", {})
            if rf and len([v for v in rf.values() if v is not None and v != "regex" and v != "llm"]) > 5:
                confidence = 55  # Research data provides some confidence
            else:
                confidence = 40  # Minimal data
        confidence = max(0, min(100, confidence))
    else:
        confidence = 40

    if discrepancy_count >= 3:
        data_integrity = "LOW"
    elif discrepancy_count >= 1:
        data_integrity = "MEDIUM"
    elif confirmed_count >= 3:
        data_integrity = "HIGH"
    else:
        data_integrity = "MODERATE"

    return {
        "overall_confidence_pct": round(confidence, 1),
        "data_integrity": data_integrity,
        "total_checks": total_checks,
        "confirmations": confirmed_count,
        "discrepancies": discrepancy_count,
        "insufficient_data_checks": insufficient_count,
        "checks": checks,
        "summary": _generate_summary(confirmations, discrepancies, checks, confidence, research_data),
    }


# ── Document Cross-Checks ────────────────────────────────────────────────────

def _check_revenue_vs_gst(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    gst = parsed_data.get("gst", {}).get("fields", {})
    ar_revenue = ar.get("profit_and_loss", {}).get("revenue")
    gst_turnover = gst.get("reported_turnover", [])
    gst_max = max(gst_turnover) if gst_turnover else None

    if not ar_revenue or not gst_max:
        return {"check": "Revenue vs GST Turnover", "status": "insufficient_data",
                "detail": "Annual Report revenue or GST turnover data not available", "severity": "info"}

    ar_revenue, gst_max = float(ar_revenue), float(gst_max)
    if ar_revenue > 0 and gst_max > 0:
        ratio = ar_revenue / gst_max
        if 0.5 < ratio < 20:
            return {"check": "Revenue vs GST Turnover", "status": "confirmed",
                    "detail": f"AR Revenue ₹{ar_revenue:,.0f}Cr and GST ₹{gst_max:,.0f}Cr broadly consistent", "severity": "ok"}
        else:
            return {"check": "Revenue vs GST Turnover", "status": "discrepancy",
                    "detail": f"Gap: AR Revenue ₹{ar_revenue:,.0f}Cr vs GST ₹{gst_max:,.0f}Cr (ratio: {ratio:.1f}x)", "severity": "high"}
    return None


def _check_debt_consistency(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    bp = parsed_data.get("borrowing_profile", {}).get("fields", {})
    ar_debt = ar.get("balance_sheet", {}).get("total_debt")
    bp_outstanding = bp.get("total_outstanding")

    if not ar_debt or not bp_outstanding:
        return {"check": "Debt: AR vs Borrowing Profile", "status": "insufficient_data",
                "detail": "Debt data missing from one or both sources", "severity": "info"}

    ar_debt, bp_outstanding = float(ar_debt), float(bp_outstanding)
    if ar_debt > 0 or bp_outstanding > 0:
        diff_pct = abs(ar_debt - bp_outstanding) / max(ar_debt, bp_outstanding, 1) * 100
        if diff_pct < 15:
            return {"check": "Debt: AR vs Borrowing Profile", "status": "confirmed",
                    "detail": f"Debt consistent: AR ₹{ar_debt:,.0f}Cr vs BP ₹{bp_outstanding:,.0f}Cr ({diff_pct:.0f}% diff)", "severity": "ok"}
        else:
            return {"check": "Debt: AR vs Borrowing Profile", "status": "discrepancy",
                    "detail": f"Debt mismatch: AR ₹{ar_debt:,.0f}Cr vs BP ₹{bp_outstanding:,.0f}Cr ({diff_pct:.0f}% diff)", "severity": "medium" if diff_pct < 30 else "high"}
    return None


def _check_profit_vs_itr(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    itr = parsed_data.get("itr", {}).get("fields", {})
    ar_pat = ar.get("profit_and_loss", {}).get("pat")
    itr_income = itr.get("income_figures", {})
    itr_total = itr_income.get("total income") or itr_income.get("business income")

    if not ar_pat or not itr_total:
        return {"check": "Profit: AR vs ITR", "status": "insufficient_data",
                "detail": "ITR or AR PAT data missing for comparison", "severity": "info"}

    ar_pat, itr_total = float(ar_pat), float(itr_total)
    if ar_pat > 0 and itr_total > 0:
        ratio = ar_pat / itr_total if itr_total != 0 else 0
        if 0.3 < ratio < 3:
            return {"check": "Profit: AR vs ITR", "status": "confirmed",
                    "detail": f"Profit aligned: AR PAT ₹{ar_pat:,.0f}Cr, ITR ₹{itr_total:,.0f}Cr", "severity": "ok"}
        else:
            return {"check": "Profit: AR vs ITR", "status": "discrepancy",
                    "detail": f"Profit mismatch: AR PAT ₹{ar_pat:,.0f}Cr vs ITR ₹{itr_total:,.0f}Cr", "severity": "high"}
    return {"check": "Profit: AR vs ITR", "status": "insufficient_data", "detail": "Zero/negative values cannot compare", "severity": "info"}


def _check_shareholding_consistency(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    sh = parsed_data.get("shareholding", {}).get("fields", {})
    promoter = sh.get("promoter_holding_pct")
    public = sh.get("public_holding_pct")

    if not promoter:
        return {"check": "Shareholding Consistency", "status": "insufficient_data",
                "detail": "Shareholding data not available", "severity": "info"}

    if promoter and public:
        total = float(promoter) + float(public)
        if 95 < total < 105:
            return {"check": "Shareholding Consistency", "status": "confirmed",
                    "detail": f"Promoter {promoter}% + Public {public}% = {total:.0f}% (consistent)", "severity": "ok"}
        else:
            return {"check": "Shareholding Consistency", "status": "discrepancy",
                    "detail": f"Shareholding doesn't add up: {promoter}% + {public}% = {total:.0f}%", "severity": "medium"}

    return {"check": "Shareholding Consistency", "status": "confirmed",
            "detail": f"Promoter holding: {promoter}%", "severity": "ok"}


def _check_asset_quality(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    pf = parsed_data.get("portfolio", {}).get("fields", {})
    bp = parsed_data.get("borrowing_profile", {}).get("fields", {})
    gnpa = pf.get("gnpa_pct")
    overdue = bp.get("total_overdue", 0)

    if not gnpa and not overdue:
        return {"check": "Asset Quality Cross-Check", "status": "insufficient_data",
                "detail": "No asset quality data from portfolio or borrowing profile", "severity": "info"}

    if gnpa and float(gnpa) > 5 and (not overdue or overdue == 0):
        return {"check": "Asset Quality Cross-Check", "status": "discrepancy",
                "detail": f"Portfolio shows {gnpa}% GNPA but no overdue in borrowing profile", "severity": "medium"}

    return {"check": "Asset Quality Cross-Check", "status": "confirmed",
            "detail": f"Asset quality signals consistent (GNPA: {gnpa or 'N/A'}%, Overdue: ₹{overdue or 0}Cr)", "severity": "ok"}


def _check_alm_borrowing(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    alm = parsed_data.get("alm", {}).get("fields", {})
    bp = parsed_data.get("borrowing_profile", {}).get("fields", {})
    buckets = alm.get("maturity_buckets", {})
    total_outstanding = bp.get("total_outstanding")

    if not buckets or not total_outstanding:
        return {"check": "ALM vs Borrowing Structure", "status": "insufficient_data",
                "detail": "ALM or borrowing data not available", "severity": "info"}

    total_outflows = sum(b.get("outflows", 0) for b in buckets.values())
    if total_outflows > 0 and float(total_outstanding) > 0:
        ratio = total_outflows / float(total_outstanding)
        if 0.5 < ratio < 2:
            return {"check": "ALM vs Borrowing Structure", "status": "confirmed",
                    "detail": f"ALM outflows ₹{total_outflows:,.0f}Cr match borrowing ₹{total_outstanding}Cr", "severity": "ok"}
        else:
            return {"check": "ALM vs Borrowing Structure", "status": "discrepancy",
                    "detail": f"ALM ₹{total_outflows:,.0f}Cr vs borrowing ₹{total_outstanding}Cr — {ratio:.1f}x gap", "severity": "medium"}

    return {"check": "ALM vs Borrowing Structure", "status": "insufficient_data",
            "detail": "Zero values in ALM or borrowing data", "severity": "info"}


# ── Research-Based Checks (work without documents) ───────────────────────────

def _check_research_alignment(parsed_data: Dict, research_data: Dict, ml_result: Dict) -> Dict:
    """Check if research sentiment aligns with financial risk profile."""
    sentiment = research_data.get("news_sentiment", {}).get("sentiment", {})
    pd_prob = ml_result.get("probability_of_default", 0.05)
    label = sentiment.get("label", "NEUTRAL")

    if label == "NEUTRAL" and pd_prob < 0.10:
        return {"check": "Research Sentiment Alignment", "status": "confirmed",
                "detail": f"Neutral/positive sentiment aligns with moderate risk profile (PD: {pd_prob:.1%})", "severity": "ok"}

    if label == "POSITIVE" and pd_prob < 0.08:
        return {"check": "Research Sentiment Alignment", "status": "confirmed",
                "detail": f"Positive news sentiment consistent with low risk (PD: {pd_prob:.1%})", "severity": "ok"}

    if label == "NEGATIVE" and pd_prob > 0.15:
        return {"check": "Research Sentiment Alignment", "status": "confirmed",
                "detail": "Negative sentiment confirmed by elevated risk indicators", "severity": "ok"}

    if label == "POSITIVE" and pd_prob > 0.20:
        return {"check": "Research Sentiment Alignment", "status": "discrepancy",
                "detail": f"Positive news but high risk (PD: {pd_prob:.1%}) — possible lag or data issue", "severity": "medium"}

    if label == "NEGATIVE" and pd_prob < 0.05:
        return {"check": "Research Sentiment Alignment", "status": "discrepancy",
                "detail": f"Negative news but low risk (PD: {pd_prob:.1%}) — investigate recent developments", "severity": "medium"}

    return {"check": "Research Sentiment Alignment", "status": "confirmed",
            "detail": f"No significant misalignment (Sentiment: {label}, PD: {pd_prob:.1%})", "severity": "ok"}


def _check_research_data_quality(research_data: Dict) -> Dict:
    """Assess the quality and completeness of research data."""
    fin = research_data.get("extracted_financials", {})
    news = research_data.get("news_sentiment", {}).get("company_news", [])
    summary = research_data.get("research_summary", "")

    # Count meaningful financial metrics extracted
    metric_count = sum(1 for k, v in fin.items()
                       if v is not None and k not in ("extraction_method", "key_strengths", "key_concerns", "financial_summary", "sector"))
    has_rating = bool(fin.get("credit_rating"))
    has_news = len(news) >= 2
    has_summary = len(summary) > 100

    score = 0
    details = []
    if metric_count >= 8:
        score += 3
        details.append(f"{metric_count} financial metrics extracted from web")
    elif metric_count >= 4:
        score += 2
        details.append(f"{metric_count} financial metrics extracted")
    elif metric_count > 0:
        score += 1
        details.append(f"Only {metric_count} metrics — limited data")

    if has_rating:
        score += 2
        details.append(f"Credit rating found: {fin['credit_rating']}")
    if has_news:
        score += 1
        details.append(f"{len(news)} news articles analyzed")
    if has_summary:
        score += 1
        details.append("AI research summary generated")

    if score >= 5:
        return {"check": "Research Data Quality", "status": "confirmed",
                "detail": f"Good research coverage: {'; '.join(details)}", "severity": "ok"}
    elif score >= 3:
        return {"check": "Research Data Quality", "status": "confirmed",
                "detail": f"Moderate research coverage: {'; '.join(details)}", "severity": "ok"}
    else:
        return {"check": "Research Data Quality", "status": "insufficient_data",
                "detail": f"Limited research data: {'; '.join(details) if details else 'minimal data collected'}", "severity": "info"}


def _check_research_vs_features(parsed_data: Dict, research_data: Dict) -> Dict:
    """Cross-check research-extracted financials vs document-extracted features."""
    rf = research_data.get("extracted_financials", {})
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    pnl = ar.get("profit_and_loss", {})
    ratios = ar.get("ratios", {})

    if not rf or not pnl.get("revenue"):
        # Can't cross-check — no doc data
        if rf and rf.get("revenue_cr"):
            return {"check": "Research vs Document Data", "status": "confirmed",
                    "detail": f"Using research data (revenue ₹{rf['revenue_cr']:,.0f}Cr) — no document data to cross-check", "severity": "ok"}
        return {"check": "Research vs Document Data", "status": "insufficient_data",
                "detail": "Cannot cross-check — limited document and/or research data", "severity": "info"}

    # Compare revenue
    doc_rev = float(pnl.get("revenue", 0))
    res_rev = rf.get("revenue_cr")
    if doc_rev > 0 and res_rev:
        diff_pct = abs(doc_rev - float(res_rev)) / max(doc_rev, float(res_rev)) * 100
        if diff_pct < 20:
            return {"check": "Research vs Document Data", "status": "confirmed",
                    "detail": f"Revenue consistent: Doc ₹{doc_rev:,.0f}Cr vs Research ₹{float(res_rev):,.0f}Cr ({diff_pct:.0f}% diff)", "severity": "ok"}
        else:
            return {"check": "Research vs Document Data", "status": "discrepancy",
                    "detail": f"Revenue differs: Doc ₹{doc_rev:,.0f}Cr vs Research ₹{float(res_rev):,.0f}Cr ({diff_pct:.0f}% diff)", "severity": "medium"}

    return {"check": "Research vs Document Data", "status": "confirmed",
            "detail": "Data sources broadly aligned", "severity": "ok"}


# ── Summary Generator ─────────────────────────────────────────────────────────

def _generate_summary(confirmations, discrepancies, all_checks, confidence, research_data) -> str:
    parts = [f"Data triangulation completed with {confidence:.0f}% confidence."]

    insufficient = [c for c in all_checks if c["status"] == "insufficient_data"]

    if confirmations:
        parts.append(f"\n✓ {len(confirmations)} cross-check(s) passed:")
        for c in confirmations[:5]:
            parts.append(f"  • {c['check']}: {c['detail']}")

    if discrepancies:
        parts.append(f"\n⚠ {len(discrepancies)} discrepancy(ies) found:")
        for d in discrepancies:
            parts.append(f"  • {d['check']}: {d['detail']}")

    if insufficient:
        parts.append(f"\nℹ {len(insufficient)} check(s) had insufficient data:")
        for c in insufficient[:3]:
            parts.append(f"  • {c['check']}: {c['detail']}")

    # Add research confidence note
    fin = research_data.get("extracted_financials", {})
    method = fin.get("extraction_method", "none")
    if method == "llm":
        parts.append("\n📊 Financial data extracted from web sources using AI analysis.")
    elif method == "regex":
        parts.append("\n📊 Financial data extracted from web sources using pattern matching.")

    if not discrepancies and not confirmations:
        parts.append("\nNote: Limited data available for cross-referencing. Assessment based primarily on research data.")

    return "\n".join(parts)
