"""
Loan Structuring Engine
4-method approach:
  1. DSCR Method — maximum loan serviced by cash flows
  2. Turnover Method — % of annual revenue
  3. Net Worth Method — multiple of tangible net worth
  4. ALM Capacity Method — based on ALM gap availability

Final recommendation = conservative minimum of all methods.
Includes: risk premium calculator, tenure recommender, auto-covenants.
"""
import math
from typing import Dict, Any, List, Optional, Tuple


# ─── Configuration ────────────────────────────────────────────────────────────

BASE_RATE = 8.50  # SBI MCLR-like base rate (%)
MIN_SPREAD = 0.50
MAX_SPREAD = 8.00
MIN_TENURE_YEARS = 1
MAX_TENURE_YEARS = 10
DEFAULT_DSCR_TARGET = 1.5  # Minimum DSCR the bank would want


def structure_loan(
    parsed_data: Dict[str, Any],
    ml_result: Dict[str, Any],
    requested_amount: float = 0,
    requested_tenure: int = 0,
    loan_type: str = "term_loan",
) -> Dict[str, Any]:
    """
    Determine optimal loan amount, interest rate, tenure, and covenants.

    Args:
        parsed_data: Combined parsed document data
        ml_result: Output from ML predictor (has PD, rating, features)
        requested_amount: Amount requested by borrower (₹ Cr)
        requested_tenure: Tenure requested (years)
        loan_type: "term_loan" or "working_capital"
    """
    pd_prob = ml_result.get("probability_of_default", 0.05)
    features = ml_result.get("features_used", {})
    rating = ml_result.get("rating", "BBB")

    # ── Extract key financials ──
    revenue = features.get("revenue_cr", 0)
    pat = features.get("pat_cr", 0)
    ebitda = _estimate_ebitda(features)
    total_equity = features.get("revenue_cr", 0) * 0.3  # rough proxy
    total_debt = features.get("total_debt_cr", 0)
    icr = features.get("icr", 2.0)
    interest_expense = ebitda / icr if icr > 0 else 0

    # Try to get better values from annual report
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    if ar:
        pnl = ar.get("profit_and_loss", {})
        bs = ar.get("balance_sheet", {})
        if pnl.get("ebitda"):
            ebitda = float(pnl["ebitda"])
        if pnl.get("revenue"):
            revenue = float(pnl["revenue"])
        if pnl.get("pat"):
            pat = float(pnl["pat"])
        if pnl.get("interest_expense"):
            interest_expense = float(pnl["interest_expense"])
        if bs.get("total_equity"):
            total_equity = float(bs["total_equity"])
        if bs.get("total_debt"):
            total_debt = float(bs["total_debt"])

    # ── Method 1: DSCR Approach ──
    dscr_result = _dscr_method(ebitda, interest_expense, total_debt, pd_prob)

    # ── Method 2: Turnover Approach ──
    turnover_result = _turnover_method(revenue, loan_type)

    # ── Method 3: Net Worth Approach ──
    networth_result = _networth_method(total_equity, total_debt)

    # ── Method 4: ALM Capacity ──
    alm_result = _alm_method(parsed_data)

    # ── Conservative minimum ──
    method_amounts = []
    methods = {
        "dscr": dscr_result,
        "turnover": turnover_result,
        "net_worth": networth_result,
        "alm_capacity": alm_result,
    }
    for name, result in methods.items():
        if result["eligible_amount"] and result["eligible_amount"] > 0:
            method_amounts.append((name, result["eligible_amount"]))

    if method_amounts:
        min_method, min_amount = min(method_amounts, key=lambda x: x[1])
        recommended_amount = min_amount
        constraining_method = min_method
    else:
        recommended_amount = requested_amount * 0.5 if requested_amount else 0
        constraining_method = "none"

    # If requested amount is specified, don't exceed it
    if requested_amount and recommended_amount > requested_amount:
        recommended_amount = requested_amount

    # ── Interest Rate ──
    interest_rate, rate_breakdown = _calculate_interest_rate(pd_prob, rating, loan_type)

    # ── Tenure ──
    recommended_tenure = _recommend_tenure(features, pd_prob, loan_type, requested_tenure)

    # ── Covenants ──
    covenants = _generate_covenants(features, pd_prob, rating)

    # ── EMI / Repayment ──
    emi = None
    if recommended_amount > 0 and recommended_tenure > 0 and interest_rate > 0:
        monthly_rate = interest_rate / 12 / 100
        num_payments = recommended_tenure * 12
        if monthly_rate > 0:
            emi = recommended_amount * monthly_rate * (1 + monthly_rate) ** num_payments / \
                  ((1 + monthly_rate) ** num_payments - 1)
            emi = round(emi, 2)

    return {
        "recommended_amount_cr": round(recommended_amount, 2),
        "requested_amount_cr": requested_amount,
        "constraining_method": constraining_method,
        "interest_rate_pct": round(interest_rate, 2),
        "rate_breakdown": rate_breakdown,
        "recommended_tenure_years": recommended_tenure,
        "emi_cr_per_month": emi,
        "loan_type": loan_type,
        "methods": {
            "dscr": dscr_result,
            "turnover": turnover_result,
            "net_worth": networth_result,
            "alm_capacity": alm_result,
        },
        "covenants": covenants,
        "method_comparison": [
            {"method": name, "amount_cr": round(result["eligible_amount"] or 0, 2), "rationale": result["rationale"]}
            for name, result in methods.items()
        ],
    }


# ─── Method Implementations ──────────────────────────────────────────────────

def _dscr_method(ebitda: float, interest_expense: float, existing_debt: float, pd_prob: float) -> Dict[str, Any]:
    """DSCR-based: max additional debt such that DSCR stays above target."""
    if ebitda <= 0:
        return {"eligible_amount": None, "rationale": "EBITDA not available or negative", "details": {}}

    # Free cash for debt service = EBITDA - existing interest
    free_cash = ebitda - interest_expense
    if free_cash <= 0:
        return {"eligible_amount": 0, "rationale": "No free cash after existing interest obligations", "details": {"ebitda": ebitda, "interest_expense": interest_expense}}

    # Additional debt capacity = free_cash / target_dscr / assumed_debt_service_rate
    target_dscr = DEFAULT_DSCR_TARGET
    assumed_rate = (BASE_RATE + _risk_spread(pd_prob)) / 100
    # Annual debt service per unit of principal (interest + 10% amortization for TL)
    debt_service_rate = assumed_rate + 0.10

    max_additional = free_cash / (target_dscr * debt_service_rate) if debt_service_rate > 0 else 0

    return {
        "eligible_amount": round(max(0, max_additional), 2),
        "rationale": f"EBITDA ₹{ebitda:.0f}Cr supports ₹{max_additional:.0f}Cr at {target_dscr}x DSCR",
        "details": {
            "ebitda": ebitda,
            "free_cash_for_service": round(free_cash, 2),
            "target_dscr": target_dscr,
            "assumed_cost": round(assumed_rate * 100, 2),
        }
    }


def _turnover_method(revenue: float, loan_type: str) -> Dict[str, Any]:
    """Turnover-based: WC = 25% of revenue, TL = 50% of revenue."""
    if revenue <= 0:
        return {"eligible_amount": None, "rationale": "Revenue data not available", "details": {}}

    if loan_type == "working_capital":
        pct = 0.25  # Nayak Committee norm (25% of projected turnover)
        eligible = revenue * pct
        norm = "Nayak Committee Norm (25% of turnover)"
    else:
        pct = 0.50
        eligible = revenue * pct
        norm = "50% of annual revenue"

    return {
        "eligible_amount": round(eligible, 2),
        "rationale": f"Revenue ₹{revenue:.0f}Cr × {pct*100:.0f}% = ₹{eligible:.0f}Cr ({norm})",
        "details": {"revenue": revenue, "percentage": pct, "norm": norm}
    }


def _networth_method(total_equity: float, total_debt: float) -> Dict[str, Any]:
    """Net worth: additional debt capped at 3x equity minus existing debt."""
    if total_equity <= 0:
        return {"eligible_amount": None, "rationale": "Net worth data not available", "details": {}}

    max_total_debt = total_equity * 3  # Cap D/E at 3x
    additional = max_total_debt - total_debt
    additional = max(0, additional)

    return {
        "eligible_amount": round(additional, 2),
        "rationale": f"Net worth ₹{total_equity:.0f}Cr × 3x D/E cap = ₹{max_total_debt:.0f}Cr total, minus existing ₹{total_debt:.0f}Cr",
        "details": {
            "net_worth": total_equity,
            "existing_debt": total_debt,
            "max_de_ratio": 3.0,
            "max_total_debt": round(max_total_debt, 2),
        }
    }


def _alm_method(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """ALM-based: surplus in 1-5 year buckets represents repayment capacity."""
    alm = parsed_data.get("alm", {}).get("fields", {})
    buckets = alm.get("maturity_buckets", {})

    if not buckets:
        return {"eligible_amount": None, "rationale": "ALM data not available", "details": {}}

    # Look at medium-term surplus (1-5 year buckets)
    surplus = 0
    for bucket_key in ["1_3_years", "3_5_years"]:
        b = buckets.get(bucket_key, {})
        mismatch = b.get("mismatch", 0)
        if mismatch > 0:
            surplus += mismatch

    # Also consider overall gap
    total_inflows = sum(b.get("inflows", 0) for b in buckets.values())
    total_outflows = sum(b.get("outflows", 0) for b in buckets.values())

    eligible = surplus * 0.7  # 70% of available surplus

    return {
        "eligible_amount": round(max(0, eligible), 2),
        "rationale": f"Medium-term ALM surplus of ₹{surplus:.0f}Cr (used 70%) = ₹{eligible:.0f}Cr",
        "details": {
            "medium_term_surplus": round(surplus, 2),
            "total_inflows": round(total_inflows, 2),
            "total_outflows": round(total_outflows, 2),
        }
    }


# ─── Interest Rate Calculation ────────────────────────────────────────────────

def _risk_spread(pd_prob: float) -> float:
    """Map PD to risk spread (bps equivalent)."""
    # Log-linear mapping: spread = base_spread × e^(k × PD)
    spread = MIN_SPREAD + (MAX_SPREAD - MIN_SPREAD) * (1 - math.exp(-5 * pd_prob))
    return round(min(spread, MAX_SPREAD), 2)


def _calculate_interest_rate(pd_prob: float, rating: str, loan_type: str) -> Tuple[float, Dict]:
    """Calculate all-in interest rate."""
    spread = _risk_spread(pd_prob)

    # Loan-type adjustment
    type_adj = 0
    if loan_type == "working_capital":
        type_adj = -0.25  # WC typically slightly cheaper (shorter tenor)

    # Tenure adjustment (handled externally, but short tenures get small discount)
    total_rate = BASE_RATE + spread + type_adj

    breakdown = {
        "base_rate": BASE_RATE,
        "risk_spread": spread,
        "loan_type_adjustment": type_adj,
        "total": round(total_rate, 2),
        "explanation": f"Base {BASE_RATE}% + Risk Spread {spread}% (PD={pd_prob:.2%}) + Type Adj {type_adj}%",
    }

    return round(total_rate, 2), breakdown


# ─── Tenure Recommendation ────────────────────────────────────────────────────

def _recommend_tenure(features: Dict[str, float], pd_prob: float, loan_type: str, requested: int) -> int:
    """Recommend loan tenure based on financials and risk."""
    if loan_type == "working_capital":
        return 1  # WC is typically 12 months renewable

    # Base tenure from risk
    if pd_prob < 0.05:
        base_tenure = 7
    elif pd_prob < 0.10:
        base_tenure = 5
    elif pd_prob < 0.20:
        base_tenure = 3
    else:
        base_tenure = 2

    # Adjust based on DSCR comfort
    icr = features.get("icr", 2.0)
    if icr > 3:
        base_tenure = min(base_tenure + 1, MAX_TENURE_YEARS)
    elif icr < 1.5:
        base_tenure = max(base_tenure - 1, MIN_TENURE_YEARS)

    # If borrower requested specific tenure, don't exceed their ask but cap at our max
    if requested > 0:
        return min(requested, base_tenure + 2, MAX_TENURE_YEARS)

    return min(base_tenure, MAX_TENURE_YEARS)


# ─── Covenant Generation ─────────────────────────────────────────────────────

def _generate_covenants(features: Dict[str, float], pd_prob: float, rating: str) -> List[Dict[str, Any]]:
    """Auto-generate loan covenants based on risk signals."""
    covenants = []

    # Standard covenants
    covenants.append({
        "type": "financial",
        "covenant": "Minimum DSCR of 1.25x to be maintained at all times",
        "trigger_level": 1.25,
        "current_value": features.get("icr", None),
        "priority": "mandatory",
    })

    # D/E covenant
    de = features.get("de_ratio", 0)
    de_limit = min(max(de * 1.3, 2.0), 4.0)
    covenants.append({
        "type": "financial",
        "covenant": f"Maximum Debt/Equity ratio of {de_limit:.1f}x",
        "trigger_level": de_limit,
        "current_value": de,
        "priority": "mandatory",
    })

    # Current ratio
    covenants.append({
        "type": "financial",
        "covenant": "Minimum current ratio of 1.10x",
        "trigger_level": 1.10,
        "current_value": features.get("current_ratio", None),
        "priority": "mandatory",
    })

    # Promoter holding (if low)
    ph = features.get("promoter_holding_pct", 50)
    if ph < 50:
        covenants.append({
            "type": "governance",
            "covenant": f"Promoter holding to be maintained above {max(ph - 5, 20):.0f}%",
            "trigger_level": max(ph - 5, 20),
            "current_value": ph,
            "priority": "important",
        })

    # Pledge (if present)
    pledge = features.get("pledged_pct", 0)
    if pledge > 10:
        covenants.append({
            "type": "governance",
            "covenant": "No further pledge of promoter shares without prior lender consent",
            "trigger_level": pledge,
            "current_value": pledge,
            "priority": "mandatory",
        })

    # Higher risk = more covenants
    if pd_prob > 0.10:
        covenants.append({
            "type": "reporting",
            "covenant": "Quarterly financial statements and compliance certificate within 45 days of quarter end",
            "trigger_level": None,
            "current_value": None,
            "priority": "mandatory",
        })
        covenants.append({
            "type": "restrictive",
            "covenant": "No dividend distribution if DSCR falls below 1.5x",
            "trigger_level": 1.5,
            "current_value": None,
            "priority": "important",
        })

    if pd_prob > 0.20:
        covenants.append({
            "type": "restrictive",
            "covenant": "No additional borrowing without prior written consent of lender",
            "trigger_level": None,
            "current_value": None,
            "priority": "mandatory",
        })
        covenants.append({
            "type": "security",
            "covenant": "Personal guarantee of promoter directors to be furnished",
            "trigger_level": None,
            "current_value": None,
            "priority": "mandatory",
        })

    return covenants


# ─── Helper ───────────────────────────────────────────────────────────────────

def _estimate_ebitda(features: Dict[str, float]) -> float:
    """Estimate EBITDA from available features."""
    rev = features.get("revenue_cr", 0)
    margin = features.get("pat_margin_pct", 5)
    # EBITDA margin ~ PAT margin + interest + depreciation (rough 1.5x PAT margin)
    ebitda_margin = min(margin * 1.5, 30)
    return rev * ebitda_margin / 100 if rev > 0 else 0
