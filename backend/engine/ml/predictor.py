"""
ML-based Credit Risk Predictor v2
Uses XGBoost / Logistic Regression trained on Indian corporate data.
Falls back to rule-based scoring if no model is available.
Now also extracts features from research-derived financial data when documents are sparse.
"""
import os
import json
import math
import numpy as np
from typing import Dict, Any, Optional, Tuple

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


MODEL_PATH = os.path.join(os.path.dirname(__file__), "credit_model.pkl")

# ─── Feature Definitions ─────────────────────────────────────────────────────

FEATURE_NAMES = [
    "revenue_cr",
    "pat_cr",
    "de_ratio",
    "current_ratio",
    "icr",
    "pat_margin_pct",
    "roe_pct",
    "alm_short_term_gap",
    "promoter_holding_pct",
    "pledged_pct",
    "total_debt_cr",
    "num_lenders",
    "overdue_pct",
    "gnpa_pct",
    "collection_eff_pct",
    "itc_mismatch_pct",
]

FEATURE_DEFAULTS = {name: 0.0 for name in FEATURE_NAMES}
FEATURE_DEFAULTS.update({
    "current_ratio": 1.5,
    "icr": 2.0,
    "promoter_holding_pct": 50.0,
    "collection_eff_pct": 95.0,
})


# ─── Feature Extraction from Parsed Data (with research fallback) ────────────

def extract_features(parsed_data: Dict[str, Any]) -> Dict[str, float]:
    """Extract ML features from parsed document data + research financials."""
    features = dict(FEATURE_DEFAULTS)
    sources = {}  # Track where each feature came from

    # ── 1. Try document-based extraction first ──
    ar = parsed_data.get("annual_report", {}).get("fields", {})
    fs = parsed_data.get("financial_statement", {}).get("fields", {})
    pnl = ar.get("profit_and_loss", {})
    bs = ar.get("balance_sheet", {})
    ratios = ar.get("ratios", {}) or fs.get("ratios", {})

    def _set(key, val, source):
        if val:
            try:
                features[key] = float(val)
                sources[key] = source
            except (ValueError, TypeError):
                pass

    _set("revenue_cr", pnl.get("revenue"), "annual_report")
    _set("pat_cr", pnl.get("pat"), "annual_report")
    _set("de_ratio", ratios.get("de_ratio"), "annual_report")
    _set("current_ratio", ratios.get("current_ratio"), "annual_report")
    _set("icr", ratios.get("icr"), "annual_report")
    _set("pat_margin_pct", ratios.get("pat_margin_pct"), "annual_report")
    _set("roe_pct", ratios.get("roe_pct"), "annual_report")

    # Financial statement fallback
    if fs.get("ratios"):
        fr = fs["ratios"]
        if "de_ratio" not in sources:
            _set("de_ratio", fr.get("debt_equity"), "financial_statement")
        if "current_ratio" not in sources:
            _set("current_ratio", fr.get("current_ratio"), "financial_statement")
        if "icr" not in sources:
            _set("icr", fr.get("interest_coverage"), "financial_statement")

    # ALM features
    alm = parsed_data.get("alm", {}).get("fields", {})
    buckets = alm.get("maturity_buckets", {})
    short_term_outflows = 0
    short_term_mismatch = 0
    for bucket_key in ["1_30_days", "31_90_days"]:
        b = buckets.get(bucket_key, {})
        short_term_outflows += b.get("outflows", 0)
        short_term_mismatch += b.get("mismatch", 0)
    if short_term_outflows > 0:
        features["alm_short_term_gap"] = round(short_term_mismatch / short_term_outflows * 100, 2)
        sources["alm_short_term_gap"] = "alm"

    # Shareholding features
    sh = parsed_data.get("shareholding", {}).get("fields", {})
    _set("promoter_holding_pct", sh.get("promoter_holding_pct"), "shareholding")
    _set("pledged_pct", sh.get("pledged_shares_pct"), "shareholding")

    # Borrowing profile features
    bp = parsed_data.get("borrowing_profile", {}).get("fields", {})
    _set("total_debt_cr", bp.get("total_outstanding"), "borrowing_profile")
    _set("num_lenders", bp.get("number_of_lenders"), "borrowing_profile")
    if bp.get("total_overdue") and bp.get("total_outstanding"):
        outstanding = float(bp["total_outstanding"])
        if outstanding > 0:
            features["overdue_pct"] = round(float(bp["total_overdue"]) / outstanding * 100, 2)
            sources["overdue_pct"] = "borrowing_profile"

    # Portfolio features
    pf = parsed_data.get("portfolio", {}).get("fields", {})
    _set("gnpa_pct", pf.get("gnpa_pct"), "portfolio")
    _set("collection_eff_pct", pf.get("collection_efficiency_pct"), "portfolio")

    # GST features
    gst = parsed_data.get("gst", {}).get("fields", {})
    _set("itc_mismatch_pct", gst.get("itc_mismatch_pct"), "gst")

    # ── 2. RESEARCH FALLBACK: Fill gaps from research-extracted financials ──
    rf = parsed_data.get("research_financials", {})
    if rf:
        # Map research keys → feature names
        mapping = {
            "revenue_cr": "revenue_cr",
            "pat_cr": "pat_cr",
            "de_ratio": "de_ratio",
            "current_ratio": "current_ratio",
            "icr": "icr",
            "pat_margin_pct": "pat_margin_pct",
            "roe_pct": "roe_pct",
            "promoter_holding_pct": "promoter_holding_pct",
            "pledged_pct": "pledged_pct",
            "total_debt_cr": "total_debt_cr",
            "num_lenders": "num_lenders",
            "gnpa_pct": "gnpa_pct",
            "collection_eff_pct": "collection_eff_pct",
        }
        for rf_key, feat_key in mapping.items():
            if feat_key not in sources and rf.get(rf_key) is not None:
                try:
                    val = float(rf[rf_key])
                    features[feat_key] = val
                    sources[feat_key] = "research_web"
                except (ValueError, TypeError):
                    pass

        # Derive computed ratios from research data if still missing
        if "pat_margin_pct" not in sources and rf.get("pat_cr") and rf.get("revenue_cr"):
            try:
                rev = float(rf["revenue_cr"])
                if rev > 0:
                    features["pat_margin_pct"] = round(float(rf["pat_cr"]) / rev * 100, 2)
                    sources["pat_margin_pct"] = "research_derived"
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        if "roe_pct" not in sources and rf.get("pat_cr") and rf.get("total_equity_cr"):
            try:
                eq = float(rf["total_equity_cr"])
                if eq > 0:
                    features["roe_pct"] = round(float(rf["pat_cr"]) / eq * 100, 2)
                    sources["roe_pct"] = "research_derived"
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        if "de_ratio" not in sources and rf.get("total_debt_cr") and rf.get("total_equity_cr"):
            try:
                eq = float(rf["total_equity_cr"])
                if eq > 0:
                    features["de_ratio"] = round(float(rf["total_debt_cr"]) / eq, 2)
                    sources["de_ratio"] = "research_derived"
            except (ValueError, TypeError, ZeroDivisionError):
                pass

    features["_sources"] = sources
    return features


# ─── ML Prediction ────────────────────────────────────────────────────────────

def predict_default(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Predict probability of default using ML model or rule-based fallback."""
    features = extract_features(parsed_data)
    sources = features.pop("_sources", {})
    feature_vector = np.array([[features[f] for f in FEATURE_NAMES]])

    if HAS_JOBLIB and os.path.exists(MODEL_PATH):
        result = _ml_predict(feature_vector, features)
    else:
        result = _rule_based_predict(features)

    result["feature_sources"] = sources
    result["document_features_count"] = sum(1 for v in sources.values() if v not in ("research_web", "research_derived"))
    result["research_features_count"] = sum(1 for v in sources.values() if v in ("research_web", "research_derived"))
    return result


def _ml_predict(feature_vector: np.ndarray, features: Dict[str, float]) -> Dict[str, Any]:
    """Run ML model prediction with SHAP explanations."""
    model = joblib.load(MODEL_PATH)
    pd_prob = float(model.predict_proba(feature_vector)[0][1])

    explanations = {}
    if HAS_SHAP:
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(feature_vector)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            for i, name in enumerate(FEATURE_NAMES):
                explanations[name] = {
                    "value": features[name],
                    "impact": round(float(shap_values[0][i]), 4),
                    "direction": "increases_risk" if shap_values[0][i] > 0 else "decreases_risk",
                }
        except Exception:
            pass

    rating = _pd_to_rating(pd_prob)
    return {
        "method": "ml_model",
        "probability_of_default": round(pd_prob, 4),
        "rating": rating,
        "features_used": features,
        "feature_importance": explanations,
        "model_type": type(model).__name__,
    }


def _rule_based_predict(features: Dict[str, float]) -> Dict[str, Any]:
    """Rule-based PD estimation calibrated to Indian corporate norms."""
    log_odds = math.log(0.04 / 0.96)
    adjustments = []

    de = features["de_ratio"]
    if de > 3:
        adj = 0.5 * (de - 3)
        log_odds += adj
        adjustments.append(("de_ratio", adj, f"D/E {de:.1f}x > 3x threshold"))
    elif de > 0 and de < 0.5:
        adj = -0.3
        log_odds += adj
        adjustments.append(("de_ratio", adj, f"Conservative D/E of {de:.1f}x"))

    icr = features["icr"]
    if icr > 0 and icr < 1.5:
        adj = 1.0
        log_odds += adj
        adjustments.append(("icr", adj, f"ICR {icr:.1f}x below 1.5x — debt servicing stress"))
    elif icr > 3:
        adj = -0.3
        log_odds += adj
        adjustments.append(("icr", adj, f"Healthy ICR of {icr:.1f}x"))

    cr = features["current_ratio"]
    if cr > 0 and cr < 1.0:
        adj = 0.6
        log_odds += adj
        adjustments.append(("current_ratio", adj, f"Current ratio {cr:.1f} < 1 — liquidity risk"))
    elif cr > 2:
        adj = -0.2
        log_odds += adj
        adjustments.append(("current_ratio", adj, f"Strong liquidity with CR {cr:.1f}"))

    pm = features["pat_margin_pct"]
    if pm < 0:
        adj = 0.8
        log_odds += adj
        adjustments.append(("pat_margin_pct", adj, "Negative PAT margin — unprofitable"))
    elif pm > 10:
        adj = -0.3
        log_odds += adj
        adjustments.append(("pat_margin_pct", adj, f"Healthy {pm:.1f}% PAT margin"))

    ph = features["promoter_holding_pct"]
    if ph < 25:
        adj = 0.4
        log_odds += adj
        adjustments.append(("promoter_holding_pct", adj, f"Low promoter holding: {ph:.1f}%"))
    elif ph > 60:
        adj = -0.2
        log_odds += adj
        adjustments.append(("promoter_holding_pct", adj, f"Strong promoter holding: {ph:.1f}%"))

    pledge = features["pledged_pct"]
    if pledge > 50:
        adj = 0.8
        log_odds += adj
        adjustments.append(("pledged_pct", adj, f"Critical pledge level: {pledge:.1f}%"))
    elif pledge > 20:
        adj = 0.3
        log_odds += adj
        adjustments.append(("pledged_pct", adj, f"High pledge level: {pledge:.1f}%"))

    overdue = features["overdue_pct"]
    if overdue > 0:
        adj = 0.5 + 0.1 * overdue
        log_odds += adj
        adjustments.append(("overdue_pct", adj, f"Overdues present: {overdue:.1f}% of outstanding"))

    gnpa = features["gnpa_pct"]
    if gnpa > 5:
        adj = 0.4
        log_odds += adj
        adjustments.append(("gnpa_pct", adj, f"High GNPA: {gnpa:.1f}%"))
    elif gnpa > 0 and gnpa < 2:
        adj = -0.15
        log_odds += adj
        adjustments.append(("gnpa_pct", adj, f"Controlled GNPA: {gnpa:.1f}%"))

    ce = features["collection_eff_pct"]
    if ce > 0 and ce < 90:
        adj = 0.3
        log_odds += adj
        adjustments.append(("collection_eff_pct", adj, f"Low collection efficiency: {ce:.1f}%"))
    elif ce > 98:
        adj = -0.2
        log_odds += adj
        adjustments.append(("collection_eff_pct", adj, f"Strong collection efficiency: {ce:.1f}%"))

    itc = features["itc_mismatch_pct"]
    if itc > 10:
        adj = 0.3
        log_odds += adj
        adjustments.append(("itc_mismatch_pct", adj, f"ITC mismatch: {itc:.1f}%"))

    alm_gap = features["alm_short_term_gap"]
    if alm_gap < -10:
        adj = 0.4
        log_odds += adj
        adjustments.append(("alm_short_term_gap", adj, f"Negative ALM gap: {alm_gap:.1f}%"))

    # Revenue size factor — larger is more stable
    rev = features["revenue_cr"]
    if rev > 5000:
        adj = -0.4
        log_odds += adj
        adjustments.append(("revenue_cr", adj, f"Large-scale operations: ₹{rev:,.0f} Cr"))
    elif rev > 1000:
        adj = -0.2
        log_odds += adj
        adjustments.append(("revenue_cr", adj, f"Significant revenue base: ₹{rev:,.0f} Cr"))

    pd_prob = 1 / (1 + math.exp(-log_odds))
    pd_prob = max(0.001, min(0.999, pd_prob))
    rating = _pd_to_rating(pd_prob)

    explanations = {}
    for feat_name, impact, detail in adjustments:
        explanations[feat_name] = {
            "value": features[feat_name],
            "impact": round(impact, 4),
            "direction": "increases_risk" if impact > 0 else "decreases_risk",
            "detail": detail,
        }

    return {
        "method": "rule_based_calibrated",
        "probability_of_default": round(pd_prob, 4),
        "rating": rating,
        "features_used": features,
        "feature_importance": explanations,
        "adjustments": [{"feature": f, "impact": round(i, 4), "detail": d} for f, i, d in adjustments],
    }


def _pd_to_rating(pd_prob: float) -> str:
    """Convert PD to internal rating grade (aligned to CRISIL scale)."""
    if pd_prob < 0.005:
        return "AAA"
    elif pd_prob < 0.01:
        return "AA+"
    elif pd_prob < 0.02:
        return "AA"
    elif pd_prob < 0.03:
        return "AA-"
    elif pd_prob < 0.05:
        return "A+"
    elif pd_prob < 0.08:
        return "A"
    elif pd_prob < 0.12:
        return "A-"
    elif pd_prob < 0.18:
        return "BBB+"
    elif pd_prob < 0.25:
        return "BBB"
    elif pd_prob < 0.35:
        return "BBB-"
    elif pd_prob < 0.50:
        return "BB+"
    elif pd_prob < 0.65:
        return "BB"
    elif pd_prob < 0.80:
        return "B"
    else:
        return "C/D"
