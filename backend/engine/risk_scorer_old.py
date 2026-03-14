"""
Credit Risk Scorer - Explainable ML-based scoring
Implements the Five Cs of Credit framework:
- Character: Promoter background, litigation, compliance
- Capacity: Revenue, profitability, cash flow analysis
- Capital: Net worth, equity, retained earnings
- Collateral: Assets, security offered
- Conditions: Industry outlook, regulatory environment

Produces a transparent, explainable score with reasoning.
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class CreditRiskScorer:
    """Transparent, explainable credit risk scoring engine."""

    # Score weights for the Five Cs
    WEIGHTS = {
        "character": 0.20,
        "capacity": 0.25,
        "capital": 0.20,
        "collateral": 0.15,
        "conditions": 0.20,
    }

    def score(self, application: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive credit risk score with full explainability."""
        parsed_data = application.get("parsed_data", {})
        research = application.get("research", {})
        insights = application.get("primary_insights", [])
        documents = application.get("documents", [])

        # Score each C
        character_score = self._score_character(parsed_data, research, documents)
        capacity_score = self._score_capacity(parsed_data, documents)
        capital_score = self._score_capital(parsed_data, documents)
        collateral_score = self._score_collateral(parsed_data, documents)
        conditions_score = self._score_conditions(research, parsed_data)

        # Apply primary insight adjustments
        insight_adjustment = self._process_primary_insights(insights)

        # Calculate weighted score
        five_cs = {
            "character": character_score,
            "capacity": capacity_score,
            "capital": capital_score,
            "collateral": collateral_score,
            "conditions": conditions_score,
        }

        weighted_score = sum(
            five_cs[c]["score"] * self.WEIGHTS[c] for c in five_cs
        )

        # Apply insight adjustment (±10 max)
        adjusted_score = max(0, min(100, weighted_score + insight_adjustment["total_adjustment"]))

        # Determine recommendation
        recommendation = self._generate_recommendation(
            adjusted_score, five_cs, application, insight_adjustment
        )

        # Aggregate all risks
        all_risks = []
        for c_name, c_data in five_cs.items():
            for risk in c_data.get("risks", []):
                risk["category"] = c_name
                all_risks.append(risk)

        # Sort risks by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        all_risks.sort(key=lambda r: severity_order.get(r.get("severity", "LOW"), 4))

        return {
            "overall_score": round(adjusted_score, 1),
            "raw_score": round(weighted_score, 1),
            "grade": self._score_to_grade(adjusted_score),
            "five_cs": five_cs,
            "insight_adjustment": insight_adjustment,
            "recommendation": recommendation,
            "all_risks": all_risks,
            "scored_at": datetime.now().isoformat(),
            "explainability": {
                "methodology": "Weighted scoring across Five Cs of Credit with AI-assisted document analysis",
                "weights": self.WEIGHTS,
                "data_sources": [d.get("doc_type", "unknown") for d in documents],
                "confidence": self._calculate_confidence(documents, research),
            },
        }

    def _score_character(self, parsed_data: dict, research: dict, documents: list) -> Dict[str, Any]:
        """Score Character: Promoter integrity, compliance, litigation history."""
        score = 70  # Base score
        reasons = []
        risks = []

        # Check litigation from research
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

        # Check news sentiment
        sentiment = research.get("news_sentiment", {}).get("sentiment", {})
        if sentiment.get("label") == "NEGATIVE":
            score -= 15
            reasons.append(f"Negative public sentiment (score: {sentiment.get('score', 'N/A')})")
            risks.append({"type": "REPUTATION", "severity": "HIGH", "detail": "Negative news coverage"})
        elif sentiment.get("label") == "POSITIVE":
            score += 10
            reasons.append("Positive public sentiment")

        # Check for legal notices in uploaded documents
        for doc in documents:
            if doc.get("doc_type") == "legal_notice":
                score -= 10
                reasons.append("Legal notice document uploaded")
                for r in doc.get("risks_identified", []):
                    risks.append(r)

        # Check board minutes
        board_data = parsed_data.get("board_minutes", {})
        if board_data:
            for r in board_data.get("risks", []):
                if r.get("type") == "DIRECTOR_RESIGNATION":
                    score -= 5
                    reasons.append("Director resignation noted")
                    risks.append(r)

        # Check shareholding / pledging
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

        return {
            "score": max(0, min(100, score)),
            "reasons": reasons,
            "risks": risks,
            "weight": self.WEIGHTS["character"],
        }

    def _score_capacity(self, parsed_data: dict, documents: list) -> Dict[str, Any]:
        """Score Capacity: Revenue, cash flow, repayment ability."""
        score = 65  # Base
        reasons = []
        risks = []

        # GST analysis
        gst_data = parsed_data.get("gst", {})
        if gst_data:
            turnover = gst_data.get("fields", {}).get("reported_turnover", [])
            if turnover:
                trend = self._analyze_simple_trend(turnover)
                if trend == "growing":
                    score += 15
                    reasons.append("GST turnover shows growth trend")
                elif trend == "declining":
                    score -= 15
                    reasons.append("GST turnover declining")
                    risks.append({"type": "REVENUE_DECLINE", "severity": "HIGH", "detail": "Declining GST turnover trend"})
                else:
                    score += 5
                    reasons.append("GST turnover stable")

            for r in gst_data.get("risks", []):
                if r.get("severity") in ("HIGH", "CRITICAL"):
                    score -= 10
                    risks.append(r)
        else:
            score -= 5
            reasons.append("No GST data available")

        # Bank statement analysis
        bank_data = parsed_data.get("bank_statement", {})
        if bank_data:
            bounce_count = bank_data.get("fields", {}).get("bounce_count", 0)
            if bounce_count > 5:
                score -= 20
                reasons.append(f"{bounce_count} cheque bounces detected")
                risks.append({"type": "CHEQUE_BOUNCES", "severity": "HIGH", "detail": f"{bounce_count} bounced transactions"})
            elif bounce_count > 0:
                score -= bounce_count * 3
                reasons.append(f"{bounce_count} minor cheque bounces")
        else:
            score -= 5
            reasons.append("No bank statement data available")

        # Cross-reference analysis
        cross_ref = parsed_data.get("structured_analysis", {}).get("cross_reference", {})
        if cross_ref:
            consistency = cross_ref.get("consistency_score", 100)
            if consistency < 60:
                score -= 20
                reasons.append("Significant GST-bank data inconsistency")
                risks.append({"type": "DATA_INCONSISTENCY", "severity": "CRITICAL",
                             "detail": f"Cross-reference consistency score: {consistency}/100"})
            elif consistency < 80:
                score -= 10
                reasons.append("Some data inconsistency between GST and bank records")

        # ITR analysis
        itr_data = parsed_data.get("itr", {})
        if itr_data:
            for r in itr_data.get("risks", []):
                if r.get("type") == "REPORTED_LOSS":
                    score -= 15
                    reasons.append("Business loss reported in ITR")
                    risks.append(r)

        # Financial ratios
        fin_data = parsed_data.get("financial_statement", {})
        if fin_data:
            ratios = fin_data.get("fields", {}).get("ratios", {})
            if ratios.get("interest_coverage", 0) < 1.5:
                score -= 15
                reasons.append("Low interest coverage ratio")
                risks.append({"type": "LOW_ICR", "severity": "HIGH", "detail": f"ICR: {ratios.get('interest_coverage')}"})
            elif ratios.get("interest_coverage", 0) > 3:
                score += 10
                reasons.append("Healthy interest coverage ratio")

        return {
            "score": max(0, min(100, score)),
            "reasons": reasons,
            "risks": risks,
            "weight": self.WEIGHTS["capacity"],
        }

    def _score_capital(self, parsed_data: dict, documents: list) -> Dict[str, Any]:
        """Score Capital: Net worth, equity position."""
        score = 65
        reasons = []
        risks = []

        fin_data = parsed_data.get("financial_statement", {})
        if fin_data:
            ratios = fin_data.get("fields", {}).get("ratios", {})
            de_ratio = ratios.get("debt_equity", None)
            if de_ratio is not None:
                if de_ratio > 3:
                    score -= 20
                    reasons.append(f"High debt-equity ratio: {de_ratio}")
                    risks.append({"type": "HIGH_LEVERAGE", "severity": "HIGH", "detail": f"D/E ratio: {de_ratio}"})
                elif de_ratio > 2:
                    score -= 10
                    reasons.append(f"Moderate debt-equity ratio: {de_ratio}")
                elif de_ratio < 1:
                    score += 15
                    reasons.append(f"Conservative leverage: D/E {de_ratio}")
                else:
                    score += 5
                    reasons.append(f"Adequate leverage: D/E {de_ratio}")

            current_ratio = ratios.get("current_ratio", None)
            if current_ratio is not None:
                if current_ratio < 1:
                    score -= 15
                    reasons.append(f"Current ratio below 1: {current_ratio}")
                    risks.append({"type": "LIQUIDITY_RISK", "severity": "HIGH", "detail": f"Current ratio: {current_ratio}"})
                elif current_ratio > 1.5:
                    score += 10
                    reasons.append(f"Healthy current ratio: {current_ratio}")

            roe = ratios.get("roe", None)
            if roe is not None:
                if roe > 15:
                    score += 10
                    reasons.append(f"Strong ROE: {roe}%")
                elif roe < 5:
                    score -= 10
                    reasons.append(f"Weak ROE: {roe}%")
        else:
            reasons.append("Limited financial data available for capital assessment")

        # Annual report insights
        ar_data = parsed_data.get("annual_report", {})
        if ar_data:
            for r in ar_data.get("risks", []):
                if r.get("type") in ("GOING_CONCERN", "ADVERSE_AUDIT"):
                    score -= 25
                    risks.append(r)
                    reasons.append(f"Critical audit observation: {r.get('type')}")
                elif r.get("type") == "QUALIFIED_AUDIT":
                    score -= 15
                    risks.append(r)
                    reasons.append("Qualified audit opinion")

        return {
            "score": max(0, min(100, score)),
            "reasons": reasons,
            "risks": risks,
            "weight": self.WEIGHTS["capital"],
        }

    def _score_collateral(self, parsed_data: dict, documents: list) -> Dict[str, Any]:
        """Score Collateral: Available security, asset quality."""
        score = 60
        reasons = []
        risks = []

        # Check sanction letters for existing security
        sanction_data = parsed_data.get("sanction_letter", {})
        if sanction_data:
            score += 10
            reasons.append("Existing banking relationships evidenced from sanction letters")
        else:
            reasons.append("No sanction letters from other banks provided")

        # Rating report influence
        rating_data = parsed_data.get("rating_report", {})
        if rating_data:
            rating = rating_data.get("fields", {}).get("rating", "")
            outlook = rating_data.get("fields", {}).get("outlook", "")
            if any(g in rating.upper() for g in ["AAA", "AA+"]):
                score += 20
                reasons.append(f"Excellent credit rating: {rating}")
            elif any(g in rating.upper() for g in ["AA", "A+"]):
                score += 15
                reasons.append(f"Good credit rating: {rating}")
            elif any(g in rating.upper() for g in ["A", "BBB"]):
                score += 5
                reasons.append(f"Adequate credit rating: {rating}")
            elif "B" in rating.upper() and "BB" not in rating.upper():
                score -= 15
                reasons.append(f"Weak credit rating: {rating}")
                risks.append({"type": "LOW_RATING", "severity": "HIGH", "detail": f"Rating: {rating}"})

            if "Negative" in outlook:
                score -= 10
                reasons.append(f"Negative rating outlook")
                risks.append({"type": "NEGATIVE_OUTLOOK", "severity": "MEDIUM", "detail": f"Outlook: {outlook}"})

        return {
            "score": max(0, min(100, score)),
            "reasons": reasons,
            "risks": risks,
            "weight": self.WEIGHTS["collateral"],
        }

    def _score_conditions(self, research: dict, parsed_data: dict) -> Dict[str, Any]:
        """Score Conditions: Industry outlook, regulatory environment, macroeconomic factors."""
        score = 65
        reasons = []
        risks = []

        # Industry analysis from research
        industry_data = research.get("industry_analysis", {})
        if industry_data and industry_data.get("trends"):
            trends_text = " ".join([t.get("snippet", "") for t in industry_data["trends"]]).lower()
            positive = sum(1 for kw in ["growth", "expand", "positive", "strong"] if kw in trends_text)
            negative = sum(1 for kw in ["decline", "risk", "headwind", "slow", "weak", "concern"] if kw in trends_text)

            if positive > negative:
                score += 10
                reasons.append("Industry outlook appears positive")
            elif negative > positive:
                score -= 10
                reasons.append("Industry facing headwinds")
                risks.append({"type": "INDUSTRY_HEADWINDS", "severity": "MEDIUM", "detail": "Negative trends in industry outlook"})

        # Research risk flags
        research_flags = research.get("overall_risk_flags", [])
        for flag in research_flags:
            if flag.get("severity") in ("CRITICAL", "HIGH"):
                score -= 10
                risks.append(flag)

        return {
            "score": max(0, min(100, score)),
            "reasons": reasons,
            "risks": risks,
            "weight": self.WEIGHTS["conditions"],
        }

    def _process_primary_insights(self, insights: List[Dict]) -> Dict[str, Any]:
        """Process credit officer's primary insights and compute score adjustment."""
        total_adjustment = 0
        adjustments = []

        for insight in insights:
            content = insight.get("content", "").lower()
            note_type = insight.get("note_type", "other")

            adjustment = 0
            reason = ""

            # Negative indicators
            negative_keywords = {
                "idle": -5, "shut": -8, "closed": -8, "low capacity": -5,
                "40% capacity": -5, "50% capacity": -3, "poor maintenance": -5,
                "concern": -3, "risk": -3, "weak": -5, "problem": -3,
                "not operational": -8, "diversion": -10, "fraud": -10,
                "unsatisfactory": -5, "delayed": -3, "default": -8,
            }
            positive_keywords = {
                "excellent": 5, "well maintained": 3, "full capacity": 5,
                "100% capacity": 5, "90% capacity": 3, "expanding": 3,
                "strong": 3, "profitable": 3, "good": 2, "satisfactory": 2,
                "new orders": 5, "growing": 3, "diversified": 3,
            }

            for kw, adj in negative_keywords.items():
                if kw in content:
                    adjustment += adj
                    reason = f"Insight mentions '{kw}'"

            for kw, adj in positive_keywords.items():
                if kw in content:
                    adjustment += adj
                    reason = f"Insight mentions '{kw}'"

            if adjustment != 0:
                adjustments.append({
                    "note_type": note_type,
                    "adjustment": adjustment,
                    "reason": reason,
                    "content_excerpt": insight.get("content", "")[:100],
                })
                total_adjustment += adjustment

        # Cap adjustment at ±10
        total_adjustment = max(-10, min(10, total_adjustment))

        return {
            "total_adjustment": total_adjustment,
            "adjustments": adjustments,
            "insights_processed": len(insights),
        }

    def _analyze_simple_trend(self, values: list) -> str:
        """Simple trend analysis."""
        if len(values) < 2:
            return "insufficient"
        mid = len(values) // 2
        first_half = sum(values[:mid]) / mid if mid > 0 else 0
        second_half = sum(values[mid:]) / (len(values) - mid) if len(values) - mid > 0 else 0
        if second_half > first_half * 1.1:
            return "growing"
        elif second_half < first_half * 0.9:
            return "declining"
        return "stable"

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 85:
            return "A+"
        elif score >= 75:
            return "A"
        elif score >= 65:
            return "B+"
        elif score >= 55:
            return "B"
        elif score >= 45:
            return "C+"
        elif score >= 35:
            return "C"
        elif score >= 25:
            return "D"
        else:
            return "F"

    def _calculate_confidence(self, documents: list, research: dict) -> str:
        """Calculate confidence level based on data availability."""
        doc_types = {d.get("doc_type") for d in documents}
        essential = {"gst", "bank_statement", "financial_statement"}
        available = essential.intersection(doc_types)

        research_done = bool(research.get("news_sentiment"))

        if len(available) >= 3 and research_done:
            return "HIGH"
        elif len(available) >= 2 or research_done:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_recommendation(
        self, score: float, five_cs: dict, application: dict, insight_adj: dict
    ) -> Dict[str, Any]:
        """Generate final lending recommendation with full reasoning."""
        loan_requested = application.get("loan_amount_requested", 0) or 0

        # Determine recommendation
        if score >= 75:
            decision = "APPROVE"
            suggested_amount = loan_requested
            risk_premium = 0.5  # 50 bps over base
            reasoning = "Strong credit profile across all five Cs of credit."
        elif score >= 60:
            decision = "APPROVE_WITH_CONDITIONS"
            suggested_amount = loan_requested * 0.8
            risk_premium = 1.5
            reasoning = "Acceptable credit profile but with some risk factors requiring mitigation."
        elif score >= 45:
            decision = "APPROVE_REDUCED"
            suggested_amount = loan_requested * 0.5
            risk_premium = 3.0
            reasoning = "Moderate risk profile. Recommend reduced exposure with enhanced monitoring."
        elif score >= 30:
            decision = "REFER_TO_COMMITTEE"
            suggested_amount = loan_requested * 0.3
            risk_premium = 5.0
            reasoning = "Elevated risk. Manual review by credit committee recommended."
        else:
            decision = "REJECT"
            suggested_amount = 0
            risk_premium = None
            reasoning = "High risk profile. Loan not recommended."

        # Build explanation
        explanation_parts = [reasoning]

        # Add key factors
        best_c = max(five_cs.items(), key=lambda x: x[1]["score"])
        worst_c = min(five_cs.items(), key=lambda x: x[1]["score"])

        explanation_parts.append(
            f"Strongest factor: {best_c[0].capitalize()} (score: {best_c[1]['score']}/100)"
        )
        explanation_parts.append(
            f"Weakest factor: {worst_c[0].capitalize()} (score: {worst_c[1]['score']}/100)"
        )

        if insight_adj["total_adjustment"] != 0:
            direction = "positive" if insight_adj["total_adjustment"] > 0 else "negative"
            explanation_parts.append(
                f"Primary insights had a {direction} impact (adjustment: {insight_adj['total_adjustment']:+d} points)"
            )

        # Collect all critical risks for the explanation
        critical_risks = []
        for c_data in five_cs.values():
            for r in c_data.get("risks", []):
                if r.get("severity") in ("CRITICAL", "HIGH"):
                    critical_risks.append(r.get("detail", ""))

        if critical_risks:
            explanation_parts.append(f"Key concerns: {'; '.join(critical_risks[:3])}")

        return {
            "decision": decision,
            "suggested_loan_amount": round(suggested_amount, 2),
            "risk_premium_bps": risk_premium * 100 if risk_premium else None,
            "risk_premium_pct": risk_premium,
            "explanation": " | ".join(explanation_parts),
            "conditions": self._get_conditions(decision, five_cs),
        }

    def _get_conditions(self, decision: str, five_cs: dict) -> List[str]:
        """Generate conditions for approval."""
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
