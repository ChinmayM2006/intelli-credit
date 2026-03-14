"""
Research Agent - "The Digital Credit Manager"
- Secondary Research: Web crawling for news, MCA filings, litigation
- Uses Serper API for web search and Gemini for intelligent summarization
"""
import os
import re
import json
import httpx
from typing import Dict, Any, List, Optional
from config import GEMINI_API_KEY, SERPER_API_KEY

try:
    import google.generativeai as genai
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    HAS_GEMINI = bool(GEMINI_API_KEY)
except ImportError:
    HAS_GEMINI = False


class ResearchAgent:
    """AI-powered research agent that performs secondary research on companies."""

    def __init__(self):
        self.search_api_key = SERPER_API_KEY
        self.has_search = bool(self.search_api_key)
        self.has_gemini = HAS_GEMINI

    async def research_company(
        self,
        company_name: str,
        promoter_names: List[str] = [],
        industry: str = "",
    ) -> Dict[str, Any]:
        """Run full research pipeline for a company."""
        results = {
            "company_name": company_name,
            "news_sentiment": {},
            "regulatory_filings": {},
            "litigation_check": {},
            "promoter_background": {},
            "industry_analysis": {},
            "overall_risk_flags": [],
            "research_summary": "",
        }

        # Run all research queries
        news = await self._search_news(company_name, industry)
        results["news_sentiment"] = news

        mca = await self._search_mca_filings(company_name)
        results["regulatory_filings"] = mca

        litigation = await self._search_litigation(company_name)
        results["litigation_check"] = litigation

        if promoter_names:
            promoter_bg = await self._search_promoters(promoter_names)
            results["promoter_background"] = promoter_bg

        industry_info = await self._search_industry(industry)
        results["industry_analysis"] = industry_info

        # Aggregate risk flags
        results["overall_risk_flags"] = self._aggregate_risks(results)

        # Generate AI summary if available
        if self.has_gemini:
            results["research_summary"] = await self._generate_ai_summary(results)
        else:
            results["research_summary"] = self._generate_basic_summary(results)

        return results

    async def _web_search(self, query: str, num_results: int = 5) -> List[Dict]:
        """Perform web search using Serper API (or return demo data)."""
        if self.has_search:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": self.search_api_key, "Content-Type": "application/json"},
                        json={"q": query, "num": num_results, "gl": "in", "hl": "en"},
                        timeout=15.0,
                    )
                    data = response.json()
                    return data.get("organic", [])
            except Exception as e:
                return [{"title": f"Search error: {str(e)}", "snippet": "", "link": ""}]

        # Demo/fallback data when no API key
        return self._generate_demo_search_results(query)

    def _generate_demo_search_results(self, query: str) -> List[Dict]:
        """Generate realistic demo search results for prototype demonstration."""
        query_lower = query.lower()

        if "litigation" in query_lower or "court" in query_lower or "legal" in query_lower:
            return [
                {
                    "title": f"Legal proceedings involving {query.split('litigation')[0].strip()} - eCourts",
                    "snippet": "2 active cases found in various High Courts. One commercial dispute worth Rs. 12.5 Cr pending since 2023. Another labor dispute in District Court.",
                    "link": "https://ecourts.gov.in/",
                },
                {
                    "title": "NCLT Case Status Search Results",
                    "snippet": "No insolvency proceedings found. Company has clean NCLT record. No winding up petitions filed.",
                    "link": "https://nclt.gov.in/",
                },
            ]
        elif "mca" in query_lower or "roc" in query_lower or "ministry" in query_lower:
            return [
                {
                    "title": "MCA21 Company Master Data",
                    "snippet": "Company registered as Private Limited. Active status. Last AGM filed on time. All annual returns up to date. No pending compliance issues.",
                    "link": "https://www.mca.gov.in/",
                },
                {
                    "title": "Director DIN Records - MCA Portal",
                    "snippet": "3 directors on board. No disqualifications found. All DINs are active and KYC compliant.",
                    "link": "https://www.mca.gov.in/",
                },
            ]
        elif "rbi" in query_lower or "regulation" in query_lower or "nbfc" in query_lower:
            return [
                {
                    "title": "RBI Circular on Corporate Lending Norms 2025",
                    "snippet": "New RBI guidelines tighten LTV ratios for corporate loans. NBFCs face additional capital adequacy requirements. Sector-wide impact expected.",
                    "link": "https://rbi.org.in/",
                },
                {
                    "title": "Industry headwinds persist amid regulatory changes",
                    "snippet": "RBI's new provisioning norms may impact lending margins. Companies need to maintain higher capital buffers. Watch for NPA classification changes.",
                    "link": "https://economictimes.com/",
                },
            ]
        elif "promoter" in query_lower or "director" in query_lower:
            return [
                {
                    "title": "Promoter Background Check Results",
                    "snippet": "No adverse findings against promoters. Clean CIBIL record. No wilful defaulter classification. Previous ventures show stable track record.",
                    "link": "https://www.cibil.com/",
                },
            ]
        else:
            return [
                {
                    "title": f"Latest news: {query[:50]}",
                    "snippet": "Company reported 15% revenue growth in Q3. Expanding operations to new markets. Industry analysts maintain positive outlook with some sector-level concerns.",
                    "link": "https://economictimes.com/",
                },
                {
                    "title": f"Financial analysis - {query[:40]}",
                    "snippet": "Market cap stable. Debt-to-equity ratio at 1.2x. Interest coverage ratio at 3.5x. Working capital cycle has improved by 10 days.",
                    "link": "https://moneycontrol.com/",
                },
                {
                    "title": "Sector Performance and Outlook",
                    "snippet": "Industry growing at 8% CAGR. Regulatory environment stable. Key risks include raw material price volatility and currency fluctuations.",
                    "link": "https://livemint.com/",
                },
            ]

    async def _search_news(self, company_name: str, industry: str) -> Dict[str, Any]:
        """Search for recent news about the company."""
        results = await self._web_search(f"{company_name} India latest news financial")
        sector_results = await self._web_search(f"{industry} India sector news headwinds 2025 2026")

        positive_keywords = ["growth", "profit", "expand", "positive", "upgrade", "strong", "stable"]
        negative_keywords = ["loss", "default", "fraud", "scam", "decline", "downgrade", "risk", "concern", "weak"]

        sentiment = self._analyze_sentiment(results, positive_keywords, negative_keywords)

        return {
            "company_news": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in results],
            "sector_news": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in sector_results],
            "sentiment": sentiment,
        }

    async def _search_mca_filings(self, company_name: str) -> Dict[str, Any]:
        """Search MCA / ROC filings."""
        results = await self._web_search(f"{company_name} MCA ROC filing India company status")
        return {
            "filings": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in results],
            "compliance_status": "Requires manual verification on MCA portal",
        }

    async def _search_litigation(self, company_name: str) -> Dict[str, Any]:
        """Search for litigation / court cases."""
        results = await self._web_search(f"{company_name} litigation court case India legal dispute eCourts")

        risk_level = "LOW"
        text_combined = " ".join([r.get("snippet", "") for r in results]).lower()
        if any(w in text_combined for w in ["insolvency", "winding up", "nclt", "fraud"]):
            risk_level = "CRITICAL"
        elif any(w in text_combined for w in ["active case", "pending", "dispute"]):
            risk_level = "MEDIUM"

        return {
            "search_results": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in results],
            "litigation_risk": risk_level,
        }

    async def _search_promoters(self, promoter_names: List[str]) -> Dict[str, Any]:
        """Background check on promoters/directors."""
        combined = {}
        for name in promoter_names[:3]:
            results = await self._web_search(f"{name} India promoter director background")
            combined[name] = [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in results]
        return combined

    async def _search_industry(self, industry: str) -> Dict[str, Any]:
        """Research industry trends and RBI regulations."""
        if not industry:
            return {"status": "no_industry_specified"}

        results = await self._web_search(f"{industry} India RBI regulation 2025 2026 sector outlook")
        return {
            "industry": industry,
            "trends": [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in results],
        }

    def _analyze_sentiment(self, results: List[Dict], positive_kw: list, negative_kw: list) -> Dict:
        """Simple keyword-based sentiment analysis."""
        pos_count, neg_count = 0, 0
        combined_text = " ".join([r.get("snippet", "") + " " + r.get("title", "") for r in results]).lower()

        for kw in positive_kw:
            pos_count += combined_text.count(kw)
        for kw in negative_kw:
            neg_count += combined_text.count(kw)

        total = pos_count + neg_count
        if total == 0:
            return {"label": "NEUTRAL", "positive_signals": 0, "negative_signals": 0, "score": 0.5}

        score = pos_count / total
        label = "POSITIVE" if score > 0.6 else "NEGATIVE" if score < 0.4 else "NEUTRAL"
        return {
            "label": label,
            "positive_signals": pos_count,
            "negative_signals": neg_count,
            "score": round(score, 2),
        }

    def _aggregate_risks(self, results: Dict) -> List[Dict]:
        """Aggregate all research risk flags."""
        flags = []

        # News sentiment
        sentiment = results.get("news_sentiment", {}).get("sentiment", {})
        if sentiment.get("label") == "NEGATIVE":
            flags.append({"source": "news", "severity": "HIGH", "detail": "Negative news sentiment detected"})

        # Litigation
        lit_risk = results.get("litigation_check", {}).get("litigation_risk", "LOW")
        if lit_risk in ("CRITICAL", "HIGH"):
            flags.append({"source": "litigation", "severity": lit_risk, "detail": "Active litigation found"})
        elif lit_risk == "MEDIUM":
            flags.append({"source": "litigation", "severity": "MEDIUM", "detail": "Potential litigation concerns"})

        return flags

    async def _generate_ai_summary(self, results: Dict) -> str:
        """Generate an AI-powered research summary using Gemini."""
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""As a credit analyst, summarize the following research findings for a corporate loan application.
            Focus on key risk factors and positive indicators.
            
            Company: {results['company_name']}
            
            News Findings: {json.dumps(results.get('news_sentiment', {}), indent=2)[:2000]}
            
            Regulatory Filings: {json.dumps(results.get('regulatory_filings', {}), indent=2)[:1000]}
            
            Litigation: {json.dumps(results.get('litigation_check', {}), indent=2)[:1000]}
            
            Industry: {json.dumps(results.get('industry_analysis', {}), indent=2)[:1000]}
            
            Provide a concise 200-word summary highlighting:
            1. Key positive indicators
            2. Risk factors identified
            3. Recommended areas for deeper investigation
            """
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return self._generate_basic_summary(results)

    def _generate_basic_summary(self, results: Dict) -> str:
        """Generate a basic summary without AI."""
        parts = [f"Research Summary for {results['company_name']}:\n"]

        sentiment = results.get("news_sentiment", {}).get("sentiment", {})
        parts.append(f"• News Sentiment: {sentiment.get('label', 'N/A')} (Score: {sentiment.get('score', 'N/A')})")

        lit_risk = results.get("litigation_check", {}).get("litigation_risk", "N/A")
        parts.append(f"• Litigation Risk: {lit_risk}")

        flags = results.get("overall_risk_flags", [])
        if flags:
            parts.append(f"• Risk Flags: {len(flags)} identified")
            for f in flags:
                parts.append(f"  - [{f['severity']}] {f['detail']}")
        else:
            parts.append("• No major risk flags identified from secondary research")

        return "\n".join(parts)
