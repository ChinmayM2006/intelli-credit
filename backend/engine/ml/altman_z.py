"""
Altman Z-Score Calculator
Adapted for Indian corporate lending context.
Uses the Z''-Score variant (non-manufacturing / emerging markets).
"""
from typing import Dict, Any, Optional


def calculate_altman_z(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute Altman Z''-Score from parsed document data.

    Z'' = 6.56 × X1 + 3.26 × X2 + 6.72 × X3 + 1.05 × X4

    Where:
      X1 = Working Capital / Total Assets
      X2 = Retained Earnings / Total Assets
      X3 = EBIT / Total Assets
      X4 = Book Value of Equity / Total Liabilities
    """
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    bs = ar.get("balance_sheet", {})
    pnl = ar.get("profit_and_loss", {})

    total_assets = _safe_float(bs.get("total_assets"))
    current_assets = _safe_float(bs.get("current_assets"))
    current_liabilities = _safe_float(bs.get("current_liabilities"))
    total_equity = _safe_float(bs.get("total_equity"))
    total_debt = _safe_float(bs.get("total_debt"))
    ebitda = _safe_float(pnl.get("ebitda"))
    interest_expense = _safe_float(pnl.get("interest_expense"))
    pat = _safe_float(pnl.get("pat"))
    depreciation = _safe_float(pnl.get("depreciation"))

    # Try to derive total_assets if not available
    if not total_assets and total_equity and total_debt:
        total_assets = total_equity + total_debt + (current_liabilities or 0)

    if not total_assets or total_assets == 0:
        return {
            "z_score": None,
            "zone": "INSUFFICIENT_DATA",
            "interpretation": "Cannot compute Altman Z-Score — Total Assets not available",
            "components": {},
        }

    # X1: Working Capital / Total Assets
    working_capital = (current_assets or 0) - (current_liabilities or 0)
    x1 = working_capital / total_assets

    # X2: Retained Earnings / Total Assets (approximate as equity - share capital)
    retained_earnings = (total_equity or 0) * 0.7  # Approximation
    x2 = retained_earnings / total_assets

    # X3: EBIT / Total Assets
    if ebitda and depreciation:
        ebit = ebitda - depreciation
    elif ebitda:
        ebit = ebitda * 0.85  # Approximate
    elif pat and interest_expense:
        ebit = pat + interest_expense
    else:
        ebit = 0
    x3 = ebit / total_assets

    # X4: Book Value of Equity / Total Liabilities
    total_liabilities = total_assets - (total_equity or 0)
    x4 = (total_equity or 0) / total_liabilities if total_liabilities > 0 else 0

    # Z''-Score for emerging markets
    z_score = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4

    # Interpretation zones (Z''-Score thresholds)
    if z_score > 2.6:
        zone = "SAFE"
        interpretation = "Low probability of bankruptcy. Financially healthy."
    elif z_score > 1.1:
        zone = "GREY"
        interpretation = "Moderate risk — requires further monitoring and analysis."
    else:
        zone = "DISTRESS"
        interpretation = "High probability of financial distress. Elevated default risk."

    return {
        "z_score": round(z_score, 3),
        "zone": zone,
        "interpretation": interpretation,
        "components": {
            "x1_working_capital_to_assets": round(x1, 4),
            "x2_retained_earnings_to_assets": round(x2, 4),
            "x3_ebit_to_assets": round(x3, 4),
            "x4_equity_to_liabilities": round(x4, 4),
        },
        "inputs": {
            "total_assets": total_assets,
            "working_capital": working_capital,
            "retained_earnings": retained_earnings,
            "ebit": ebit,
            "total_equity": total_equity,
            "total_liabilities": total_liabilities,
        },
    }


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
