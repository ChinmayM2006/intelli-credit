"""
SWOT Generator v2 — Async-aware SWOT analysis using LLM + rule-based fallback.
"""
import json
from typing import Dict, Any, Optional
from backend.llm.provider import get_llm, get_llm_status


async def generate_swot(
    parsed_data: Dict[str, Any],
    research: Dict[str, Any],
    ml_result: Dict[str, Any],
    company_name: str = "",
) -> Dict[str, Any]:
    """Generate comprehensive SWOT analysis using LLM with rule-based fallback."""
    llm_status = get_llm_status()
    if llm_status["provider"] != "fallback":
        try:
            return await _llm_swot(parsed_data, research, ml_result, company_name)
        except Exception:
            pass
    return _rule_based_swot(parsed_data, research, ml_result, company_name)


async def _llm_swot(
    parsed_data: Dict[str, Any],
    research: Dict[str, Any],
    ml_result: Dict[str, Any],
    company_name: str,
) -> Dict[str, Any]:
    """LLM-powered SWOT analysis."""
    llm = get_llm()

    # Build rich context from ALL available data
    fin = research.get("extracted_financials", {})
    fin_str = json.dumps({k: v for k, v in fin.items()
                          if v is not None and k not in ("extraction_method",)}, indent=2)

    news_snippets = []
    for n in research.get("news_sentiment", {}).get("company_news", [])[:5]:
        news_snippets.append(f"- {n.get('title', '')}: {n.get('snippet', '')}")
    news_text = "\n".join(news_snippets) if news_snippets else "No news data available."

    sector_snippets = []
    for n in research.get("news_sentiment", {}).get("sector_news", [])[:3]:
        sector_snippets.append(f"- {n.get('title', '')}: {n.get('snippet', '')}")
    sector_text = "\n".join(sector_snippets) if sector_snippets else "No sector data."

    lit_risk = research.get("litigation_check", {}).get("litigation_risk", "N/A")
    sentiment = research.get("news_sentiment", {}).get("sentiment", {})

    ml_pd = ml_result.get("probability_of_default", "N/A")
    ml_rating = ml_result.get("rating", "N/A")
    overall_score = ml_result.get("five_c_scores", {})

    prompt = f"""You are a senior credit analyst at an Indian bank. Generate a detailed SWOT analysis for a corporate lending decision about "{company_name}".

EXTRACTED FINANCIAL DATA:
{fin_str}

COMPANY NEWS:
{news_text}

SECTOR/INDUSTRY NEWS:
{sector_text}

RISK INDICATORS:
- Litigation Risk: {lit_risk}
- News Sentiment: {json.dumps(sentiment)}
- ML Credit Rating: {ml_rating}
- Probability of Default: {ml_pd}
- Overall Credit Score: {json.dumps(overall_score)}

RESEARCH SUMMARY:
{research.get('research_summary', 'Not available')[:800]}

Return ONLY valid JSON in this exact format:
{{
  "strengths": [
    {{"point": "<strength title>", "detail": "<1-2 sentence explanation with numbers>", "impact": "HIGH|MEDIUM|LOW"}},
    ...3-5 items
  ],
  "weaknesses": [
    {{"point": "<weakness title>", "detail": "<1-2 sentence explanation>", "impact": "HIGH|MEDIUM|LOW"}},
    ...2-4 items
  ],
  "opportunities": [
    {{"point": "<opportunity title>", "detail": "<1-2 sentence explanation>", "impact": "HIGH|MEDIUM|LOW"}},
    ...2-4 items
  ],
  "threats": [
    {{"point": "<threat title>", "detail": "<1-2 sentence explanation>", "impact": "HIGH|MEDIUM|LOW"}},
    ...2-4 items
  ],
  "overall_assessment": "<3-4 sentence overall credit assessment>",
  "recommendation": "APPROVE|APPROVE_WITH_CONDITIONS|DECLINE"
}}

Be specific. Use actual numbers from the data. Focus on credit risk implications."""

    response = await llm.generate(prompt, json_mode=True, max_tokens=2000)
    swot = json.loads(response)
    swot["generation_method"] = "llm"
    return swot


def _rule_based_swot(
    parsed_data: Dict[str, Any],
    research: Dict[str, Any],
    ml_result: Dict[str, Any],
    company_name: str,
) -> Dict[str, Any]:
    """Rule-based SWOT fallback when LLM is unavailable."""
    fin = research.get("extracted_financials", {})
    sentiment = research.get("news_sentiment", {}).get("sentiment", {})
    lit_risk = research.get("litigation_check", {}).get("litigation_risk", "LOW")

    strengths, weaknesses, opportunities, threats = [], [], [], []

    # ── Strengths ──
    if fin.get("credit_rating") and "AAA" in str(fin.get("credit_rating", "")):
        strengths.append({"point": "Highest Credit Rating", "detail": f"Rated {fin['credit_rating']} indicating superior creditworthiness.", "impact": "HIGH"})
    elif fin.get("credit_rating"):
        strengths.append({"point": "Investment Grade Rating", "detail": f"Rated {fin['credit_rating']}.", "impact": "MEDIUM"})

    if fin.get("revenue_cr") and fin["revenue_cr"] > 1000:
        strengths.append({"point": "Strong Revenue Base", "detail": f"Revenue of ₹{fin['revenue_cr']:,.0f} Cr indicates significant scale of operations.", "impact": "HIGH"})
    elif fin.get("revenue_cr"):
        strengths.append({"point": "Established Revenue", "detail": f"Revenue of ₹{fin['revenue_cr']:,.0f} Cr.", "impact": "MEDIUM"})

    if fin.get("collection_eff_pct") and fin["collection_eff_pct"] > 95:
        strengths.append({"point": "High Collection Efficiency", "detail": f"Collection efficiency at {fin['collection_eff_pct']:.1f}%.", "impact": "HIGH"})

    if fin.get("promoter_holding_pct") and fin["promoter_holding_pct"] > 50:
        strengths.append({"point": "Strong Promoter Commitment", "detail": f"Promoter holding at {fin['promoter_holding_pct']:.1f}% shows skin in the game.", "impact": "MEDIUM"})

    if sentiment.get("label") == "POSITIVE":
        strengths.append({"point": "Positive Market Sentiment", "detail": f"Sentiment score {sentiment.get('score', 0):.0%}.", "impact": "MEDIUM"})

    if lit_risk == "LOW":
        strengths.append({"point": "Clean Legal Record", "detail": "No significant litigation or legal concerns identified.", "impact": "MEDIUM"})

    if not strengths:
        strengths.append({"point": "Established Operations", "detail": f"{company_name} has an established market presence.", "impact": "MEDIUM"})

    # ── Weaknesses ──
    if fin.get("de_ratio") and fin["de_ratio"] > 3:
        weaknesses.append({"point": "High Leverage", "detail": f"D/E ratio at {fin['de_ratio']:.1f}x is above comfortable levels for the sector.", "impact": "HIGH"})
    elif fin.get("de_ratio") and fin["de_ratio"] > 1.5:
        weaknesses.append({"point": "Moderate Leverage", "detail": f"D/E ratio at {fin['de_ratio']:.1f}x.", "impact": "MEDIUM"})

    if fin.get("gnpa_pct") and fin["gnpa_pct"] > 3:
        weaknesses.append({"point": "Asset Quality Concern", "detail": f"GNPA at {fin['gnpa_pct']:.1f}% needs monitoring.", "impact": "HIGH"})
    elif fin.get("gnpa_pct"):
        weaknesses.append({"point": "Asset Quality Risk", "detail": f"GNPA at {fin['gnpa_pct']:.1f}%.", "impact": "MEDIUM"})

    if sentiment.get("label") == "NEGATIVE":
        weaknesses.append({"point": "Negative Market Perception", "detail": "Adverse news coverage detected.", "impact": "HIGH"})

    if not weaknesses:
        weaknesses.append({"point": "Limited Public Data", "detail": "Comprehensive financial data not fully available from public sources.", "impact": "LOW"})

    # ── Opportunities ──
    if fin.get("revenue_growth_pct") and fin["revenue_growth_pct"] > 10:
        opportunities.append({"point": "Strong Growth Trajectory", "detail": f"Revenue growing at {fin['revenue_growth_pct']:.0f}%.", "impact": "HIGH"})

    if fin.get("aum_cr"):
        opportunities.append({"point": "AUM Growth Potential", "detail": f"AUM at ₹{fin['aum_cr']:,.0f} Cr with expansion potential.", "impact": "MEDIUM"})

    opportunities.append({"point": "Market Expansion", "detail": "Growth potential through market penetration and new products.", "impact": "MEDIUM"})

    # ── Threats ──
    if lit_risk in ("CRITICAL", "HIGH"):
        threats.append({"point": "Legal Risk", "detail": "Significant litigation concerns identified.", "impact": "HIGH"})
    elif lit_risk == "MEDIUM":
        threats.append({"point": "Litigation Monitoring Needed", "detail": "Active cases require monitoring.", "impact": "MEDIUM"})

    threats.append({"point": "Regulatory Changes", "detail": "Changes in RBI norms or sector regulations could impact operations.", "impact": "MEDIUM"})
    threats.append({"point": "Interest Rate Risk", "detail": "Rising interest rate environment may increase cost of funds.", "impact": "MEDIUM"})

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "threats": threats,
        "overall_assessment": f"Based on available data, {company_name} shows {'strong' if len(strengths) > len(weaknesses) else 'moderate'} creditworthiness with key metrics indicating {'stable' if lit_risk == 'LOW' else 'cautious'} outlook.",
        "recommendation": "APPROVE_WITH_CONDITIONS",
        "generation_method": "rule_based",
    }
