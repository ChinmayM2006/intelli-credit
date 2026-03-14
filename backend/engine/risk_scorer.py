"""
Enhanced Credit Risk Scorer
Integrates Five Cs framework + ML PD predictor + Altman Z-Score + Loan Structurer.
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.engine.ml.predictor import predict_default, extract_features
from backend.engine.ml.altman_z import calculate_altman_z
from backend.engine.loan_structurer import structure_loan


class CreditRiskScorer:
    """Transparent, explainable credit risk scoring engine with ML integration."""

    WEIGHTS = {
        "character": 0.20,
        "capacity": 0.25,
        "capital": 0.20,
        "collateral": 0.15,
        "conditions": 0.20,
    }

    def score(self, application: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive credit risk score with ML + Five Cs."""
        parsed_data = application.get("parsed_data", {})
        research = application.get("research", {})
        insights = application.get("primary_insights", [])
        documents = application.get("documents", [])

        # ── ML-based Prediction ──
        ml_result = predict_default(parsed_data)
        altman_result = calculate_altman_z(parsed_data)

        # ── Five Cs ──
        character_score = self._score_character(parsed_data, research, documents)
        capacity_score = self._score_capacity(parsed_data, documents, ml_result)
        capital_score = self._score_capital(parsed_data, documents, altman_result)
        collateral_score = self._score_collateral(parsed_data, documents)
        conditions_score = self._score_conditions(research, parsed_data)

        insight_adjustment = self._process_primary_insights(insights)

        five_cs = {
            "character": character_score,
            "capacity": capacity_score,
            "capital": capital_score,
            "collateral": collateral_score,
            "conditions": conditions_score,
        }

        weighted_score = sum(five_cs[c]["score"] * self.WEIGHTS[c] for c in five_cs)
        adjusted_score = max(0, min(100, weighted_score + insight_adjustment["total_adjustment"]))

        # ── Loan Structuring ──
        loan_structure = structure_loan(
            parsed_data, ml_result,
            requested_amount=application.get("loan_amount_requested", 0) or 0,
            requested_tenure=application.get("loan_tenure_requested", 0) or 0,
            loan_type=application.get("loan_type", "term_loan") or "term_loan",
        )

        # ── Recommendation ──
        recommendation = self._generate_recommendation(
            adjusted_score, five_cs, application, insight_adjustment, ml_result, loan_structure
        )

        # ── All risks ──
        all_risks = []
        for c_name, c_data in five_cs.items():
            for risk in c_data.get("risks", []):
                risk["category"] = c_name
                all_risks.append(risk)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        all_risks.sort(key=lambda r: severity_order.get(r.get("severity", "LOW"), 4))

        return {
            "overall_score": round(adjusted_score, 1),
            "raw_score": round(weighted_score, 1),
            "grade": self._score_to_grade(adjusted_score),
            "five_cs": five_cs,
            "ml_prediction": ml_result,
            "altman_z_score": altman_result,
            "loan_structure": loan_structure,
            "insight_adjustment": insight_adjustment,
            "recommendation": recommendation,
            "all_risks": all_risks,
            "scored_at": datetime.now().isoformat(),
            "explainability": {
                "methodology": "Hybrid: Five Cs of Credit + ML Probability of Default + Altman Z-Score + Loan Structuring",
                "weights": self.WEIGHTS,
                "ml_method": ml_result.get("method", "unknown"),
                "ml_rating": ml_result.get("rating", "N/A"),
                "pd_probability": ml_result.get("probability_of_default", None),
                "altman_zone": altman_result.get("zone", "N/A"),
                "data_sources": list(set(d.get("doc_type", "unknown") for d in documents)),
                "confidence": self._calculate_confidence(documents, research),
            },
        }

    def _score_character(self, parsed_data: dict, research: dict, documents: list) -> Dict[str, Any]:
        score = 70
        reasons = []
        risks = []

        # Litigation
        lit_risk = research.get("litigation_check", {}).get("litigation_risk", "LOW")
        if lit_risk == "CRITICAL":
            score -= 30
            reasons.append("Critical litigation risk found in public records")
            risks.append({"type": "LITIGATION", "severity": "CRITICAL", "detail": "Serious legal disputes found"})
        elif lit_risk == "HIGH":
            score -= 20
            reasons.append("High litigation risk detected")
            risks.append({"type": "LITIGATION", "severity": "HIGH", "detail": "Active legal proceedings"})
        elif lit_risk == "MEDIUM":
            score -= 10
            reasons.append("Some litigation concerns found")
            risks.append({"type": "LITIGATION", "severity": "MEDIUM", "detail": "Pending legal matters"})
        else:
            score += 10
            reasons.append("Clean litigation record")

        # News sentiment
        sentiment = research.get("news_sentiment", {}).get("sentiment", {})
        if sentiment.get("label") == "NEGATIVE":
            score -= 15
            reasons.append(f"Negative public sentiment (score: {sentiment.get('score', 'N/A')})")
            risks.append({"type": "REPUTATION", "severity": "HIGH", "detail": "Negative news coverage"})
        elif sentiment.get("label") == "POSITIVE":
            score += 10
            reasons.append("Positive public sentiment")

        # Legal notices
        for doc in documents:
            if doc.get("doc_type") == "legal_notice":
                score -= 10
                reasons.append("Legal notice document uploaded")
                for r in doc.get("risks_identified", []):
                    risks.append(r)

        # Shareholding / pledging
        share_data = parsed_data.get("shareholding", {})
        if share_data:
            for r in share_data.get("risks", []):
                if r.get("type") == "HIGH_PLEDGE":
                    score -= 15
                    reasons.append("High promoter share pledging")
                    risks.append(r)
                elif r.get("type") == "LOW_PROMOTER_HOLDING":
                    score -= 10
                    reasons.append("Low promoter holding")
                    risks.append(r)
                elif r.get("type") == "PROMOTER_SELLING":
                    score -= 10
                    reasons.append("Promoter shareholding declining")
                    risks.append(r)

        # GST compliance
        gst_data = parsed_data.get("gst", {})
        if gst_data:
            for r in gst_data.get("risks", []):
                if r.get("type") == "ITC_MISMATCH":
                    score -= 10
                    reasons.append("GST ITC mismatch — compliance concern")
                    risks.append(r)
                elif r.get("type") == "LATE_FILING":
                    score -= 5
                    reasons.append("GST late filing detected")
                    risks.append(r)

        return {"score": max(0, min(100, score)), "reasons": reasons, "risks": risks, "weight": self.WEIGHTS["character"]}

    def _score_capacity(self, parsed_data: dict, documents: list, ml_result: dict) -> Dict[str, Any]:
        score = 65
        reasons = []
        risks = []

        # ML PD integration — most important signal for capacity
        pd_prob = ml_result.get("probability_of_default", 0.05)
        if pd_prob < 0.03:
            score += 20
            reasons.append(f"Strong ML credit score (PD: {pd_prob:.1%}, Rating: {ml_result.get('rating', 'N/A')})")
        elif pd_prob < 0.08:
            score += 10
            reasons.append(f"Adequate ML credit score (PD: {pd_prob:.1%})")
        elif pd_prob < 0.15:
            score -= 5
            reasons.append(f"Elevated default risk (PD: {pd_prob:.1%})")
        elif pd_prob < 0.30:
            score -= 15
            reasons.append(f"High default risk (PD: {pd_prob:.1%})")
            risks.append({"type": "HIGH_PD", "severity": "HIGH", "detail": f"PD: {pd_prob:.1%}"})
        else:
            score -= 25
            reasons.append(f"Very high default risk (PD: {pd_prob:.1%})")
            risks.append({"type": "VERY_HIGH_PD", "severity": "CRITICAL", "detail": f"PD: {pd_prob:.1%}"})

        # GST analysis
        gst_data = parsed_data.get("gst", {})
        if gst_data:
            turnover = gst_data.get("fields", {}).get("reported_turnover", [])
            if turnover:
                trend = self._analyze_simple_trend(turnover)
                if trend == "growing":
                    score += 10
                    reasons.append("GST turnover shows growth trend")
                elif trend == "declining":
                    score -= 10
                    reasons.append("GST turnover declining")
                    risks.append({"type": "REVENUE_DECLINE", "severity": "HIGH", "detail": "Declining GST turnover"})

        # Bank statement
        bank_data = parsed_data.get("bank_statement", {})
        if bank_data:
            bounce_count = bank_data.get("fields", {}).get("bounce_count", 0)
            if bounce_count > 5:
                score -= 15
                reasons.append(f"{bounce_count} cheque bounces detected")
                risks.append({"type": "CHEQUE_BOUNCES", "severity": "HIGH", "detail": f"{bounce_count} bounced transactions"})
            elif bounce_count > 0:
                score -= bounce_count * 2
                reasons.append(f"{bounce_count} cheque bounces noted")

        # Borrowing profile risks
        bp_data = parsed_data.get("borrowing_profile", {})
        if bp_data:
            for r in bp_data.get("risks", []):
                if r.get("severity") in ("CRITICAL", "HIGH"):
                    score -= 10
                    risks.append(r)
                    reasons.append(f"Borrowing concern: {r.get('detail', '')[:50]}")

        # Financial ratios
        features = ml_result.get("features_used", {})
        if features.get("icr", 0) > 3:
            score += 5
            reasons.append(f"Healthy interest coverage ratio: {features['icr']:.1f}x")
        elif features.get("icr", 999) < 1.5:
            score -= 10
            reasons.append(f"Low interest coverage: {features.get('icr', 0):.1f}x")

        return {"score": max(0, min(100, score)), "reasons": reasons, "risks": risks, "weight": self.WEIGHTS["capacity"]}

    def _score_capital(self, parsed_data: dict, documents: list, altman_result: dict) -> Dict[str, Any]:
        score = 65
        reasons = []
        risks = []

        # Altman Z-Score integration
        z_score = altman_result.get("z_score")
        z_zone = altman_result.get("zone", "INSUFFICIENT_DATA")
        if z_zone == "SAFE":
            score += 15
            reasons.append(f"Altman Z-Score: {z_score:.2f} (Safe Zone)")
        elif z_zone == "GREY":
            score += 0
            reasons.append(f"Altman Z-Score: {z_score:.2f} (Grey Zone — requires monitoring)")
        elif z_zone == "DISTRESS":
            score -= 20
            reasons.append(f"Altman Z-Score: {z_score:.2f} (Distress Zone)")
            risks.append({"type": "ALTMAN_DISTRESS", "severity": "HIGH", "detail": f"Z-Score {z_score:.2f} indicates high distress probability"})

        # Financial ratios from annual report
        ar = parsed_data.get("annual_report", {})
        ratios = ar.get("fields", {}).get("ratios", {})
        if not ratios:
            fin_data = parsed_data.get("financial_statement", {})
            ratios = fin_data.get("fields", {}).get("ratios", {})

        de = ratios.get("de_ratio") or ratios.get("debt_equity")
        if de is not None:
            de = float(de)
            if de > 3:
                score -= 15
                reasons.append(f"High leverage: D/E {de:.1f}")
                risks.append({"type": "HIGH_LEVERAGE", "severity": "HIGH", "detail": f"D/E ratio: {de}"})
            elif de > 2:
                score -= 5
                reasons.append(f"Moderate leverage: D/E {de:.1f}")
            elif de < 1:
                score += 10
                reasons.append(f"Conservative leverage: D/E {de:.1f}")

        cr = ratios.get("current_ratio")
        if cr is not None:
            cr = float(cr)
            if cr < 1:
                score -= 10
                reasons.append(f"Low current ratio: {cr:.1f}")
                risks.append({"type": "LIQUIDITY_RISK", "severity": "HIGH", "detail": f"Current ratio: {cr}"})
            elif cr > 1.5:
                score += 5
                reasons.append(f"Healthy liquidity: CR {cr:.1f}")

        # Audit opinion
        audit = ar.get("fields", {}).get("audit_opinion", "unqualified")
        if audit == "qualified":
            score -= 15
            reasons.append("Qualified audit opinion")
            risks.append({"type": "QUALIFIED_AUDIT", "severity": "HIGH", "detail": "Auditor issued qualified opinion"})
        elif audit in ("adverse", "disclaimer"):
            score -= 25
            reasons.append(f"{audit.capitalize()} audit opinion")
            risks.append({"type": f"{audit.upper()}_AUDIT", "severity": "CRITICAL", "detail": f"Auditor issued {audit} opinion"})

        return {"score": max(0, min(100, score)), "reasons": reasons, "risks": risks, "weight": self.WEIGHTS["capital"]}

    def _score_collateral(self, parsed_data: dict, documents: list) -> Dict[str, Any]:
        score = 60
        reasons = []
        risks = []

        rating_data = parsed_data.get("rating_report", {})
        if rating_data:
            rating = rating_data.get("fields", {}).get("rating", "")
            outlook = rating_data.get("fields", {}).get("outlook", "")
            if any(g in rating.upper() for g in ["AAA", "AA+"]):
                score += 20
                reasons.append(f"Excellent external rating: {rating}")
            elif any(g in rating.upper() for g in ["AA", "A+"]):
                score += 15
                reasons.append(f"Good external rating: {rating}")
            elif any(g in rating.upper() for g in ["A", "BBB"]):
                score += 5
                reasons.append(f"Adequate rating: {rating}")
            elif "B" in rating.upper() and "BB" not in rating.upper():
                score -= 15
                reasons.append(f"Weak rating: {rating}")
                risks.append({"type": "LOW_RATING", "severity": "HIGH", "detail": f"Rating: {rating}"})
            if "Negative" in str(outlook):
                score -= 10
                risks.append({"type": "NEGATIVE_OUTLOOK", "severity": "MEDIUM", "detail": f"Outlook: {outlook}"})

        sanction_data = parsed_data.get("sanction_letter", {})
        if sanction_data:
            score += 10
            reasons.append("Existing banking relationships from sanction letters")
        else:
            reasons.append("No previous sanction letters available")

        # Portfolio quality (for NBFCs/banks)
        portfolio = parsed_data.get("portfolio", {})
        if portfolio:
            for r in portfolio.get("risks", []):
                if r.get("severity") in ("CRITICAL", "HIGH"):
                    score -= 10
                    risks.append(r)
                    reasons.append(f"Portfolio risk: {r.get('detail', '')[:60]}")

        return {"score": max(0, min(100, score)), "reasons": reasons, "risks": risks, "weight": self.WEIGHTS["collateral"]}

    def _score_conditions(self, research: dict, parsed_data: dict) -> Dict[str, Any]:
        score = 65
        reasons = []
        risks = []

        industry_data = research.get("industry_analysis", {})
        if industry_data and industry_data.get("trends"):
            text = " ".join([t.get("snippet", "") for t in industry_data["trends"]]).lower()
            pos = sum(1 for kw in ["growth", "expand", "positive", "strong"] if kw in text)
            neg = sum(1 for kw in ["decline", "risk", "headwind", "slow", "weak"] if kw in text)
            if pos > neg:
                score += 10
                reasons.append("Industry outlook appears positive")
            elif neg > pos:
                score -= 10
                reasons.append("Industry facing headwinds")
                risks.append({"type": "INDUSTRY_HEADWINDS", "severity": "MEDIUM", "detail": "Negative industry trends"})

        for flag in research.get("overall_risk_flags", []):
            if flag.get("severity") in ("CRITICAL", "HIGH"):
                score -= 10
                risks.append(flag)

        # ALM risk
        alm = parsed_data.get("alm", {})
        if alm:
            for r in alm.get("risks", []):
                if r.get("severity") in ("CRITICAL", "HIGH"):
                    score -= 10
                    risks.append(r)
                    reasons.append(f"ALM risk: {r.get('detail', '')[:60]}")

        return {"score": max(0, min(100, score)), "reasons": reasons, "risks": risks, "weight": self.WEIGHTS["conditions"]}

    def _process_primary_insights(self, insights: List[Dict]) -> Dict[str, Any]:
        total_adjustment = 0
        adjustments = []
        neg_kw = {"idle": -5, "shut": -8, "closed": -8, "low capacity": -5, "poor maintenance": -5,
                   "concern": -3, "risk": -3, "weak": -5, "not operational": -8, "diversion": -10,
                   "fraud": -10, "unsatisfactory": -5, "delayed": -3, "default": -8}
        pos_kw = {"excellent": 5, "well maintained": 3, "full capacity": 5, "100% capacity": 5,
                  "expanding": 3, "strong": 3, "profitable": 3, "good": 2, "new orders": 5, "growing": 3}
        for insight in insights:
            content = insight.get("content", "").lower()
            adj = 0
            reason = ""
            for kw, v in neg_kw.items():
                if kw in content:
                    adj += v
                    reason = f"'{kw}' noted"
            for kw, v in pos_kw.items():
                if kw in content:
                    adj += v
                    reason = f"'{kw}' noted"
            if adj != 0:
                adjustments.append({"note_type": insight.get("note_type", ""), "adjustment": adj, "reason": reason})
                total_adjustment += adj
        total_adjustment = max(-10, min(10, total_adjustment))
        return {"total_adjustment": total_adjustment, "adjustments": adjustments, "insights_processed": len(insights)}

    def _analyze_simple_trend(self, values: list) -> str:
        if len(values) < 2:
            return "insufficient"
        mid = len(values) // 2
        first = sum(values[:mid]) / mid if mid > 0 else 0
        second = sum(values[mid:]) / max(len(values) - mid, 1)
        if second > first * 1.1:
            return "growing"
        elif second < first * 0.9:
            return "declining"
        return "stable"

    def _score_to_grade(self, score: float) -> str:
        if score >= 85: return "A+"
        elif score >= 75: return "A"
        elif score >= 65: return "B+"
        elif score >= 55: return "B"
        elif score >= 45: return "C+"
        elif score >= 35: return "C"
        elif score >= 25: return "D"
        else: return "F"

    def _calculate_confidence(self, documents: list, research: dict) -> str:
        doc_types = {d.get("doc_type") for d in documents}
        essential = {"annual_report", "borrowing_profile", "gst", "shareholding"}
        available = essential.intersection(doc_types)
        research_done = bool(research.get("news_sentiment"))
        if len(available) >= 3 and research_done:
            return "HIGH"
        elif len(available) >= 2 or research_done:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_recommendation(
        self, score: float, five_cs: dict, application: dict,
        insight_adj: dict, ml_result: dict, loan_structure: dict,
    ) -> Dict[str, Any]:
        loan_requested = application.get("loan_amount_requested", 0) or 0
        pd_prob = ml_result.get("probability_of_default", 0.05)
        ml_rating = ml_result.get("rating", "BBB")

        # Use loan structurer's recommended amount instead of arbitrary %
        structured_amount = loan_structure.get("recommended_amount_cr", 0)
        structured_rate = loan_structure.get("interest_rate_pct", 0)
        structured_tenure = loan_structure.get("recommended_tenure_years", 0)

        if score >= 75:
            decision = "APPROVE"
            suggested = min(structured_amount, loan_requested) if loan_requested else structured_amount
            reasoning = f"Strong credit profile. ML Rating: {ml_rating}. PD: {pd_prob:.2%}."
        elif score >= 60:
            decision = "APPROVE_WITH_CONDITIONS"
            suggested = structured_amount * 0.85
            reasoning = f"Acceptable with conditions. ML Rating: {ml_rating}. Some risk factors require mitigation."
        elif score >= 45:
            decision = "APPROVE_REDUCED"
            suggested = structured_amount * 0.6
            reasoning = f"Moderate risk. Reduced exposure recommended. ML Rating: {ml_rating}."
        elif score >= 30:
            decision = "REFER_TO_COMMITTEE"
            suggested = structured_amount * 0.4
            reasoning = f"Elevated risk. Credit committee review needed. ML Rating: {ml_rating}."
        else:
            decision = "REJECT"
            suggested = 0
            reasoning = f"High risk profile. ML Rating: {ml_rating}, PD: {pd_prob:.2%}. Not recommended."

        best_c = max(five_cs.items(), key=lambda x: x[1]["score"])
        worst_c = min(five_cs.items(), key=lambda x: x[1]["score"])

        return {
            "decision": decision,
            "suggested_loan_amount": round(suggested, 2),
            "interest_rate_pct": structured_rate,
            "recommended_tenure_years": structured_tenure,
            "emi_cr_per_month": loan_structure.get("emi_cr_per_month"),
            "risk_premium_pct": structured_rate - 8.50 if structured_rate > 8.50 else 0,
            "constraining_factor": loan_structure.get("constraining_method", "N/A"),
            "explanation": reasoning,
            "strongest_factor": f"{best_c[0].capitalize()} ({best_c[1]['score']}/100)",
            "weakest_factor": f"{worst_c[0].capitalize()} ({worst_c[1]['score']}/100)",
            "conditions": self._get_conditions(decision, five_cs),
            "covenants": loan_structure.get("covenants", []),
        }

    def _get_conditions(self, decision: str, five_cs: dict) -> List[str]:
        conditions = []
        if decision in ("APPROVE_WITH_CONDITIONS", "APPROVE_REDUCED", "REFER_TO_COMMITTEE"):
            if five_cs["collateral"]["score"] < 60:
                conditions.append("Additional collateral security required")
            if five_cs["character"]["score"] < 60:
                conditions.append("Personal guarantee of promoter required")
            if five_cs["capacity"]["score"] < 60:
                conditions.append("Monthly monitoring of cash flows required")
            if five_cs["conditions"]["score"] < 60:
                conditions.append("Quarterly review of industry conditions")
            if not conditions:
                conditions.append("Standard monitoring and reporting requirements")
        return conditions
