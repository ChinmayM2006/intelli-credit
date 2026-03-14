"""
Structured Data Analysis Module
- GST analysis (GSTR-2A vs 3B reconciliation)
- Bank statement analysis  
- Cross-referencing GST with bank data to flag circular trading / revenue inflation
"""
from typing import Dict, Any, List
import re


def _analyze_trend(values: list) -> str:
    """Analyze the trend of a list of values."""
    if len(values) < 2:
        return "insufficient_data"
    mid = len(values) // 2
    first_half = sum(values[:mid]) / mid if mid > 0 else 0
    second_half = sum(values[mid:]) / (len(values) - mid) if len(values) - mid > 0 else 0
    if second_half > first_half * 1.1:
        return "growing"
    elif second_half < first_half * 0.9:
        return "declining"
    return "stable"


def analyze_gst_data(gst_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze GST filing data for anomalies."""
    if not gst_data:
        return {"status": "no_data", "summary": "No GST data uploaded yet"}

    fields = gst_data.get("fields", {})
    risks = gst_data.get("risks", [])
    turnover = fields.get("reported_turnover", [])

    analysis = {
        "gstr_type": fields.get("gstr_type", "Unknown"),
        "gstin": fields.get("gstin", "Not found"),
        "turnover_figures": turnover,
        "turnover_trend": _analyze_trend(turnover),
        "compliance_flags": [],
        "circular_trading_indicators": [],
    }

    # Check for turnover consistency
    if len(turnover) >= 4:
        avg = sum(turnover) / len(turnover)
        for i, t in enumerate(turnover):
            if t > avg * 3:
                analysis["circular_trading_indicators"].append({
                    "period_index": i,
                    "value": t,
                    "avg": round(avg, 2),
                    "flag": "Unusually high turnover - possible circular trading",
                })

    # Add existing risks
    analysis["risk_count"] = len(risks)
    analysis["risks"] = risks

    return analysis


def analyze_bank_statements(bank_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze bank statement data."""
    if not bank_data:
        return {"status": "no_data", "summary": "No bank statement data uploaded yet"}

    fields = bank_data.get("fields", {})

    credit_total = fields.get("credit_total", 0)
    debit_total = fields.get("debit_total", 0)
    bounce_count = fields.get("bounce_count", 0)
    transaction_amounts = fields.get("transaction_amounts", [])

    analysis = {
        "bank_name": fields.get("bank_name", "Unknown"),
        "account_number": fields.get("account_number", "Not found"),
        "credit_total": credit_total,
        "debit_total": debit_total,
        "net_position": credit_total - debit_total,
        "bounce_count": bounce_count,
        "transaction_volume": len(transaction_amounts),
        "behavioral_flags": [],
    }

    # Behavioral analysis
    if bounce_count > 5:
        analysis["behavioral_flags"].append({
            "flag": "FREQUENT_BOUNCES",
            "severity": "HIGH",
            "detail": f"{bounce_count} cheque bounces detected - poor cash management",
        })

    if credit_total > 0:
        utilization = debit_total / credit_total if credit_total > 0 else 0
        analysis["utilization_ratio"] = round(utilization, 2)
        if utilization > 0.95:
            analysis["behavioral_flags"].append({
                "flag": "HIGH_UTILIZATION",
                "severity": "MEDIUM",
                "detail": "Account utilization > 95% - tight cash flow",
            })

    # Check for round-tripping patterns
    if transaction_amounts:
        round_amounts = [a for a in transaction_amounts if a > 0 and a % 100000 == 0]
        if len(round_amounts) > len(transaction_amounts) * 0.3:
            analysis["behavioral_flags"].append({
                "flag": "ROUND_TRIPPING_SUSPECT",
                "severity": "HIGH",
                "detail": f"{len(round_amounts)}/{len(transaction_amounts)} transactions are round figures",
            })

    return analysis


def cross_reference_gst_bank(gst_data: Dict[str, Any], bank_data: Dict[str, Any]) -> Dict[str, Any]:
    """Cross-reference GST returns against bank statements to identify circular trading or revenue inflation."""
    result = {
        "status": "analyzed",
        "consistency_score": 100,  # Start at 100, deduct for issues
        "flags": [],
        "recommendation": "",
    }

    if not gst_data or not bank_data:
        result["status"] = "insufficient_data"
        result["recommendation"] = "Upload both GST returns and bank statements for cross-referencing"
        return result

    gst_fields = gst_data.get("fields", {})
    bank_fields = bank_data.get("fields", {})

    gst_turnover = gst_fields.get("reported_turnover", [])
    bank_credits = bank_fields.get("credit_total", 0)
    bank_transactions = bank_fields.get("transaction_amounts", [])

    # Check 1: GST reported turnover vs bank credits
    if gst_turnover and bank_credits > 0:
        max_gst_turnover = max(gst_turnover) if gst_turnover else 0
        # If GST turnover significantly exceeds bank credits
        if max_gst_turnover > 0 and bank_credits > 0:
            ratio = max_gst_turnover / bank_credits
            if ratio > 1.5:
                result["flags"].append({
                    "type": "REVENUE_INFLATION",
                    "severity": "CRITICAL",
                    "detail": f"GST turnover ({max_gst_turnover:,.0f}) is {ratio:.1f}x bank credits ({bank_credits:,.0f})",
                    "explanation": "Reported GST turnover significantly exceeds actual bank inflows - possible revenue inflation",
                })
                result["consistency_score"] -= 30
            elif ratio < 0.5:
                result["flags"].append({
                    "type": "UNDER_REPORTING",
                    "severity": "HIGH",
                    "detail": f"GST turnover ({max_gst_turnover:,.0f}) is much lower than bank credits ({bank_credits:,.0f})",
                    "explanation": "Bank credits significantly exceed reported GST turnover - possible under-reporting of revenue",
                })
                result["consistency_score"] -= 20

    # Check 2: Round-tripping / circular trading pattern
    if bank_transactions:
        # Look for matching credit-debit pairs (same amount in and out)
        sorted_txns = sorted(bank_transactions)
        circular_pairs = 0
        for i in range(len(sorted_txns) - 1):
            if abs(sorted_txns[i] - sorted_txns[i+1]) < 1:
                circular_pairs += 1

        if circular_pairs > len(bank_transactions) * 0.2:
            result["flags"].append({
                "type": "CIRCULAR_TRADING",
                "severity": "CRITICAL",
                "detail": f"{circular_pairs} potential circular transactions detected",
                "explanation": "Multiple matching credit-debit pairs suggest circular trading to inflate turnover",
            })
            result["consistency_score"] -= 25

    # Check 3: Bounce rate impact
    bounce_count = bank_fields.get("bounce_count", 0)
    if bounce_count > 3:
        result["flags"].append({
            "type": "PAYMENT_STRESS",
            "severity": "HIGH",
            "detail": f"{bounce_count} cheque bounces indicate payment stress",
        })
        result["consistency_score"] -= min(bounce_count * 3, 20)

    # Final recommendation
    score = result["consistency_score"]
    if score >= 80:
        result["recommendation"] = "GST and bank data are largely consistent. Low risk of revenue manipulation."
    elif score >= 60:
        result["recommendation"] = "Some inconsistencies found between GST and bank data. Manual review recommended."
    elif score >= 40:
        result["recommendation"] = "Significant discrepancies between GST returns and bank statements. Detailed investigation required."
    else:
        result["recommendation"] = "CRITICAL: Strong indicators of revenue inflation or circular trading. Exercise extreme caution."

    return result
