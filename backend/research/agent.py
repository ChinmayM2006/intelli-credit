"""
Research Agent v2 — AI-powered company research with financial extraction.
Uses web search + LLM to extract structured financial data from public sources.
"""
import os
import re
import json
import httpx
from typing import Dict, Any, List, Optional
from backend.config import SERPER_API_KEY
from backend.llm.provider import get_llm, get_llm_status


class ResearchAgent:
    """AI-powered research agent that extracts structured financial data from web sources."""

    def __init__(self):
        self.search_api_key = SERPER_API_KEY
        self.has_search = bool(self.search_api_key)
        llm_status = get_llm_status()
        self.has_llm = llm_status["provider"] != "fallback"

    async def research_company(
        self,
        company_name: str,
        promoter_names: List[str] = [],
        industry: str = "",
    ) -> Dict[str, Any]:
        results = {
            "company_name": company_name,
            "news_sentiment": {},
            "regulatory_filings": {},
            "litigation_check": {},
            "promoter_background": {},
            "industry_analysis": {},
            "overall_risk_flags": [],
            "research_summary": "",
            "extracted_financials": {},
        }

        results["news_sentiment"] = await self._search_news(company_name, industry)
        results["regulatory_filings"] = await self._search_mca_filings(company_name)
        results["litigation_check"] = await self._search_litigation(company_name)
        if promoter_names:
            results["promoter_background"] = await self._search_promoters(promoter_names)
        else:
            results["promoter_background"] = await self._search_company_leadership(company_name)
        results["industry_analysis"] = await self._search_industry(industry)

        # ── NEW: Extract structured financials from ALL gathered web data ──
        results["extracted_financials"] = await self._extract_financials(company_name, results)

        results["overall_risk_flags"] = self._aggregate_risks(results)

        if self.has_llm:
            results["research_summary"] = await self._generate_ai_summary(results)
        else:
            results["research_summary"] = self._generate_basic_summary(results)

        return results

    # ── Web Search ────────────────────────────────────────────────────────────

    async def _web_search(self, query: str, num_results: int = 5) -> List[Dict]:
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
        return self._generate_demo_search_results(query)

    def _generate_demo_search_results(self, query: str) -> List[Dict]:
        q = query.lower()
        if "litigation" in q or "court" in q or "legal" in q:
            return [
                {"title": "Legal proceedings - eCourts", "snippet": "2 active cases found in various High Courts. One commercial dispute worth Rs. 12.5 Cr pending since 2023. Another labor dispute in District Court.", "link": "https://ecourts.gov.in/"},
                {"title": "NCLT Case Status", "snippet": "No insolvency proceedings found. Company has clean NCLT record. No winding up petitions filed.", "link": "https://nclt.gov.in/"},
            ]
        elif "mca" in q or "roc" in q:
            return [
                {"title": "MCA21 Company Master Data", "snippet": "Company registered as Private Limited. Active status. Last AGM filed on time. All annual returns up to date.", "link": "https://www.mca.gov.in/"},
                {"title": "Director DIN Records", "snippet": "3 directors on board. No disqualifications found. All DINs are active and KYC compliant.", "link": "https://www.mca.gov.in/"},
            ]
        elif "financial" in q or "balance sheet" in q or "annual report" in q:
            return [
                {"title": "Annual Report FY2025 Key Highlights", "snippet": "Revenue from operations: Rs. 8,450 Cr (up 18% YoY). EBITDA: Rs. 2,535 Cr (margin 30%). PAT: Rs. 1,267 Cr. Total Assets: Rs. 85,000 Cr. Net Worth: Rs. 18,500 Cr. D/E Ratio: 3.6x. RoE: 14.2%. Book Value: Rs. 742/share.", "link": "https://www.bseindia.com/"},
                {"title": "Quarterly Results Q3 FY26", "snippet": "Q3 revenue Rs. 2,380 Cr (+15% YoY). PAT Rs. 356 Cr. AUM grew 22% to Rs. 98,000 Cr. Cost of funds 7.8%. NIM at 9.2%. Collection efficiency 99.1%.", "link": "https://economictimes.com/"},
            ]
        elif "rbi" in q or "regulation" in q or "nbfc" in q:
            return [
                {"title": "RBI Circular on Corporate Lending Norms 2025", "snippet": "New RBI guidelines tighten LTV ratios for corporate loans. NBFCs face additional capital adequacy requirements. Minimum CRAR of 15% mandated.", "link": "https://rbi.org.in/"},
                {"title": "Industry headwinds amid regulatory changes", "snippet": "RBI's new provisioning norms may impact lending margins. Companies need to maintain higher capital buffers.", "link": "https://economictimes.com/"},
            ]
        elif "promoter" in q or "director" in q:
            return [
                {"title": "Promoter Background Check", "snippet": "No adverse findings against promoters. Clean CIBIL record. No wilful defaulter classification. Promoter holding 73.4%. No shares pledged.", "link": "https://www.cibil.com/"},
            ]
        elif "npa" in q or "asset quality" in q or "gnpa" in q:
            return [
                {"title": "Asset Quality Report", "snippet": "Gross NPA at 2.8% (down from 3.5% last year). Net NPA at 0.9%. Provision coverage ratio at 68%. Stage 3 assets well provisioned. ECL provision Rs. 1,200 Cr.", "link": "https://moneycontrol.com/"},
                {"title": "Portfolio Quality Analysis", "snippet": "Retail portfolio growing 25% YoY. Corporate book degrown 15% as per strategy. Collection efficiency 99.1% in Q3. Write-offs Rs. 450 Cr.", "link": "https://livemint.com/"},
            ]
        elif "credit rating" in q or "crisil" in q or "icra" in q:
            return [
                {"title": "Credit Rating Update", "snippet": "CRISIL AAA/Stable for long-term borrowings. CRISIL A1+ for commercial paper. Rating reflects strong parentage, adequate capitalization and improving asset quality.", "link": "https://www.crisil.com/"},
            ]
        else:
            return [
                {"title": f"Latest news: {query[:50]}", "snippet": "Company reported 15% revenue growth in Q3. Expanding operations. Industry analysts maintain positive outlook. Revenue Rs. 2,380 Cr for the quarter.", "link": "https://economictimes.com/"},
                {"title": f"Financial analysis: {query[:40]}", "snippet": "Market cap Rs. 42,000 Cr. D/E ratio at 3.6x. ICR at 3.5x. Working capital cycle improved by 10 days. Net Worth Rs. 18,500 Cr. Current ratio 1.3x.", "link": "https://moneycontrol.com/"},
                {"title": "Sector Performance", "snippet": "Industry growing at 8% CAGR. Regulatory environment stable. Key risks: raw material volatility, interest rate changes.", "link": "https://livemint.com/"},
            ]

    # ── Search Methods ────────────────────────────────────────────────────────

    async def _search_news(self, company_name: str, industry: str) -> Dict[str, Any]:
        results = await self._web_search(f"{company_name} India latest news financial")
        sector_results = await self._web_search(f"{industry} India sector news 2025")
        pos_kw = ["growth", "profit", "expand", "positive", "upgrade", "strong", "stable", "robust"]
        neg_kw = ["loss", "default", "fraud", "scam", "decline", "downgrade", "risk", "concern", "weak"]
        sentiment = self._analyze_sentiment(results, pos_kw, neg_kw)
        return {
            "company_news": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in results],
            "sector_news": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in sector_results],
            "sentiment": sentiment,
        }

    async def _search_mca_filings(self, company_name: str) -> Dict[str, Any]:
        results = await self._web_search(f"{company_name} MCA ROC filing India company status")
        return {"filings": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in results],
                "compliance_status": "Requires manual verification on MCA portal"}

    async def _search_litigation(self, company_name: str) -> Dict[str, Any]:
        results = await self._web_search(f"{company_name} litigation court case India legal dispute eCourts")
        risk_level = "LOW"
        text = " ".join([r.get("snippet", "") for r in results]).lower()
        if any(w in text for w in ["insolvency", "winding up", "nclt", "fraud"]):
            risk_level = "CRITICAL"
        elif any(w in text for w in ["active case", "pending", "dispute"]):
            risk_level = "MEDIUM"
        return {"search_results": [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("link", "")} for r in results],
                "litigation_risk": risk_level}

    async def _search_promoters(self, promoter_names: List[str]) -> Dict[str, Any]:
        combined = {}
        for name in promoter_names[:3]:
            results = await self._web_search(f"{name} India promoter director background")
            combined[name] = [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in results]
        return combined

    async def _search_company_leadership(self, company_name: str) -> Dict[str, Any]:
        """Fallback leadership search when promoter names are not supplied at onboarding."""
        results = await self._web_search(f"{company_name} managing director ceo promoter name India")
        entries = [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in results]

        candidate_names = self._extract_person_names(" ".join([f"{e['title']} {e['snippet']}" for e in entries]))
        if candidate_names:
            return {name: entries[:2] for name in candidate_names[:3]}
        return {"leadership": entries}

    def _extract_person_names(self, text: str) -> List[str]:
        candidates = []
        for pattern in [
            r"(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,\s*(?:Managing Director|Chief Executive Officer|Chairman)",
            r"(?:Managing Director|Chief Executive Officer|Chairman)\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        ]:
            for name in re.findall(pattern, text):
                clean = str(name).strip()
                if clean and clean not in candidates:
                    candidates.append(clean)
        return candidates

    async def _search_industry(self, industry: str) -> Dict[str, Any]:
        if not industry:
            return {"status": "no_industry_specified"}
        results = await self._web_search(f"{industry} India RBI regulation 2025 sector outlook")
        return {"industry": industry, "trends": [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in results]}

    # ── NEW: Financial Data Extraction ────────────────────────────────────────

    async def _extract_financials(self, company_name: str, research: Dict) -> Dict[str, Any]:
        """Use LLM to extract structured financial metrics from all gathered web data."""
        # Gather ALL text snippets
        all_snippets = []
        for news in research.get("news_sentiment", {}).get("company_news", []):
            all_snippets.append(f"[News] {news.get('title', '')}: {news.get('snippet', '')}")
        for news in research.get("news_sentiment", {}).get("sector_news", []):
            all_snippets.append(f"[Sector] {news.get('title', '')}: {news.get('snippet', '')}")
        for filing in research.get("regulatory_filings", {}).get("filings", []):
            all_snippets.append(f"[Filing] {filing.get('title', '')}: {filing.get('snippet', '')}")
        for lit in research.get("litigation_check", {}).get("search_results", []):
            all_snippets.append(f"[Legal] {lit.get('title', '')}: {lit.get('snippet', '')}")
        for trend in research.get("industry_analysis", {}).get("trends", []):
            all_snippets.append(f"[Industry] {trend.get('title', '')}: {trend.get('snippet', '')}")
        for pname, items in research.get("promoter_background", {}).items():
            for item in items:
                all_snippets.append(f"[Promoter:{pname}] {item.get('title', '')}: {item.get('snippet', '')}")

        if not all_snippets:
            return self._extract_financials_regex("\n".join(all_snippets))

        # Do ADDITIONAL targeted financial searches
        fin_results = await self._web_search(f"{company_name} annual report revenue EBITDA PAT net worth FY2025 financial results")
        for r in fin_results:
            all_snippets.append(f"[Financial] {r.get('title', '')}: {r.get('snippet', '')}")

        npa_results = await self._web_search(f"{company_name} GNPA NPA asset quality collection efficiency credit rating")
        for r in npa_results:
            all_snippets.append(f"[AssetQuality] {r.get('title', '')}: {r.get('snippet', '')}")

        rating_results = await self._web_search(f"{company_name} CRISIL ICRA credit rating 2025")
        for r in rating_results:
            all_snippets.append(f"[Rating] {r.get('title', '')}: {r.get('snippet', '')}")

        combined_text = "\n".join(all_snippets)

        if self.has_llm:
            return await self._extract_financials_llm(company_name, combined_text)
        else:
            return self._extract_financials_regex(combined_text)

    async def _extract_financials_llm(self, company_name: str, text: str) -> Dict[str, Any]:
        """Use LLM to extract structured financial metrics."""
        llm = get_llm()
        prompt = f"""You are an expert Indian credit analyst. Extract ALL financial metrics you can find from the following web research data about "{company_name}".

RESEARCH DATA:
{text[:6000]}

Return ONLY valid JSON with these fields. Use null for any metric you cannot find. All monetary values in Indian Rupees CRORES (Cr):

{{
  "revenue_cr": <annual revenue in Rs Crores>,
  "pat_cr": <profit after tax in Rs Crores>,
  "ebitda_cr": <EBITDA in Rs Crores>,
  "ebitda_margin_pct": <EBITDA margin as percentage>,
  "total_assets_cr": <total assets in Rs Crores>,
  "total_equity_cr": <net worth / total equity in Rs Crores>,
  "total_debt_cr": <total debt in Rs Crores>,
  "current_assets_cr": <current assets in Rs Crores>,
  "current_liabilities_cr": <current liabilities in Rs Crores>,
  "interest_expense_cr": <interest/finance cost in Rs Crores>,
  "depreciation_cr": <depreciation in Rs Crores>,
  "de_ratio": <debt to equity ratio>,
  "current_ratio": <current ratio>,
  "icr": <interest coverage ratio>,
  "pat_margin_pct": <PAT margin percentage>,
  "roe_pct": <return on equity percentage>,
  "promoter_holding_pct": <promoter holding percentage>,
  "pledged_pct": <pledged shares percentage>,
  "gnpa_pct": <gross NPA percentage>,
  "nnpa_pct": <net NPA percentage>,
  "collection_eff_pct": <collection efficiency percentage>,
  "aum_cr": <assets under management in Rs Crores>,
  "market_cap_cr": <market capitalization in Rs Crores>,
  "revenue_growth_pct": <revenue growth percentage>,
  "credit_rating": <credit rating like "CRISIL AAA" or "ICRA AA+">,
  "rating_outlook": <rating outlook like "Stable" or "Positive">,
  "num_lenders": <number of banking relationships>,
    "cin": <corporate identification number like L65920MH1994PLC080618>,
    "incorporation_year": <year company was incorporated>,
    "promoter_names": [<list of promoter/leader names if found>],
  "sector": <industry sector>,
  "key_strengths": [<list of 3-5 key financial strengths as strings>],
  "key_concerns": [<list of 2-4 key financial concerns as strings>],
  "financial_summary": "<2-3 sentence summary of the company's financial health>"
}}"""

        try:
            response = await llm.generate(prompt, json_mode=True, max_tokens=2000)
            data = json.loads(response)
            data["extraction_method"] = "llm"
            return data
        except (json.JSONDecodeError, Exception) as e:
            return self._extract_financials_regex(text)

    def _extract_financials_regex(self, text: str) -> Dict[str, Any]:
        """Fallback: extract financial metrics using regex patterns."""
        data = {"extraction_method": "regex"}
        original_text = text
        t = text.lower()

        patterns = {
            "revenue_cr": [r"revenue[:\s]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)", r"turnover[:\s]*(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)"],
            "pat_cr": [r"(?:pat|profit after tax)[:\s]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)", r"net profit[:\s]*(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)"],
            "ebitda_cr": [r"ebitda[:\s]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)"],
            "de_ratio": [r"d/?e\s*(?:ratio)?[:\s]*([\d.]+)\s*x?", r"debt[/ ]equity[:\s]*([\d.]+)"],
            "icr": [r"icr[:\s]*([\d.]+)", r"interest coverage[:\s]*([\d.]+)"],
            "current_ratio": [r"current ratio[:\s]*([\d.]+)"],
            "gnpa_pct": [r"(?:gross )?npa[:\s]*([\d.]+)\s*%", r"gnpa[:\s]*([\d.]+)"],
            "promoter_holding_pct": [r"promoter[:\s]*(?:holding)?[:\s]*([\d.]+)\s*%"],
            "collection_eff_pct": [r"collection efficiency[:\s]*([\d.]+)\s*%"],
            "total_assets_cr": [r"total assets[:\s]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)"],
            "total_equity_cr": [r"(?:net worth|equity|networth)[:\s]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)"],
            "market_cap_cr": [r"market cap[:\s]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)"],
            "revenue_growth_pct": [r"(?:revenue|growth)[:\s]*(?:up|grew)?\s*([\d.]+)\s*%"],
        }

        for field, pats in patterns.items():
            for pat in pats:
                m = re.search(pat, t)
                if m:
                    try:
                        val = float(m.group(1).replace(",", ""))
                        data[field] = val
                    except ValueError:
                        pass
                    break

        # Credit rating
        rating_pat = r"(crisil|icra|care|india ratings|fitch)\s+(aaa|aa\+|aa|aa-|a\+|a|a-|bbb\+|bbb|bbb-|bb\+|bb)"
        m = re.search(rating_pat, t)
        if m:
            data["credit_rating"] = f"{m.group(1).upper()} {m.group(2).upper()}"
        outlook_pat = r"(?:outlook|watch)[:\s]*(stable|positive|negative|developing)"
        m = re.search(outlook_pat, t)
        if m:
            data["rating_outlook"] = m.group(1).title()

        cin_match = re.search(r"\b([A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b", original_text)
        if cin_match:
            data["cin"] = cin_match.group(1)

        year_match = re.search(r"(?:incorporated|founded|established)\D{0,15}(19\d{2}|20\d{2})", t)
        if year_match:
            try:
                data["incorporation_year"] = int(year_match.group(1))
            except ValueError:
                pass

        names = []
        for name in re.findall(r"\[Promoter:([^\]]+)\]", original_text):
            clean = name.strip()
            if clean and clean not in names:
                names.append(clean)

        leader_patterns = [
            r"(?:Managing Director|Chief Executive Officer|Chairman|Promoter)\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,\s*(?:Managing Director|Chief Executive Officer|Chairman)",
        ]
        for pattern in leader_patterns:
            for found in re.findall(pattern, original_text):
                clean = found.strip()
                if clean and clean not in names:
                    names.append(clean)

        if names:
            data["promoter_names"] = names[:5]

        return data

    # ── Analysis Helpers ──────────────────────────────────────────────────────

    def _analyze_sentiment(self, results: List[Dict], pos_kw: list, neg_kw: list) -> Dict:
        pos_count, neg_count = 0, 0
        text = " ".join([r.get("snippet", "") + " " + r.get("title", "") for r in results]).lower()
        for kw in pos_kw:
            pos_count += text.count(kw)
        for kw in neg_kw:
            neg_count += text.count(kw)
        total = pos_count + neg_count
        if total == 0:
            return {"label": "NEUTRAL", "positive_signals": 0, "negative_signals": 0, "score": 0.5}
        score = pos_count / total
        label = "POSITIVE" if score > 0.6 else "NEGATIVE" if score < 0.4 else "NEUTRAL"
        return {"label": label, "positive_signals": pos_count, "negative_signals": neg_count, "score": round(score, 2)}

    def _aggregate_risks(self, results: Dict) -> List[Dict]:
        flags = []
        sentiment = results.get("news_sentiment", {}).get("sentiment", {})
        if sentiment.get("label") == "NEGATIVE":
            flags.append({"source": "news", "severity": "HIGH", "detail": "Negative news sentiment detected"})
        lit_risk = results.get("litigation_check", {}).get("litigation_risk", "LOW")
        if lit_risk in ("CRITICAL", "HIGH"):
            flags.append({"source": "litigation", "severity": lit_risk, "detail": "Active litigation found"})
        elif lit_risk == "MEDIUM":
            flags.append({"source": "litigation", "severity": "MEDIUM", "detail": "Potential litigation concerns"})
        return flags

    async def _generate_ai_summary(self, results: Dict) -> str:
        try:
            llm = get_llm()
            financials = results.get("extracted_financials", {})
            fin_str = json.dumps({k: v for k, v in financials.items()
                                  if v is not None and k not in ("extraction_method", "key_strengths", "key_concerns")}, indent=2)

            prompt = f"""As a senior credit analyst at an Indian bank, write a comprehensive research summary for: {results['company_name']}

EXTRACTED FINANCIALS:
{fin_str}

NEWS SENTIMENT: {json.dumps(results.get('news_sentiment', {}).get('sentiment', {}), indent=2)}
REGULATORY: {json.dumps(results.get('regulatory_filings', {}), indent=2)[:600]}
LITIGATION: {json.dumps(results.get('litigation_check', {}), indent=2)[:600]}
INDUSTRY: {json.dumps(results.get('industry_analysis', {}), indent=2)[:600]}

Write a 250-word analytical summary covering:
1. Company Overview & Scale
2. Financial Health Assessment
3. Key Strengths
4. Risk Factors & Concerns
5. Credit Outlook

Be specific with numbers. Write in professional credit analyst style."""

            return await llm.generate(prompt, max_tokens=800)
        except Exception:
            return self._generate_basic_summary(results)

    def _generate_basic_summary(self, results: Dict) -> str:
        parts = [f"Research Summary for {results['company_name']}:\n"]
        fin = results.get("extracted_financials", {})
        if fin.get("revenue_cr"):
            parts.append(f"• Revenue: ₹{fin['revenue_cr']:,.0f} Cr")
        if fin.get("pat_cr"):
            parts.append(f"• PAT: ₹{fin['pat_cr']:,.0f} Cr")
        if fin.get("de_ratio"):
            parts.append(f"• D/E Ratio: {fin['de_ratio']:.1f}x")
        if fin.get("credit_rating"):
            parts.append(f"• Credit Rating: {fin['credit_rating']}")
        sentiment = results.get("news_sentiment", {}).get("sentiment", {})
        parts.append(f"• News Sentiment: {sentiment.get('label', 'N/A')} (Score: {sentiment.get('score', 'N/A')})")
        lit = results.get("litigation_check", {}).get("litigation_risk", "N/A")
        parts.append(f"• Litigation Risk: {lit}")
        flags = results.get("overall_risk_flags", [])
        if flags:
            parts.append(f"• Risk Flags: {len(flags)} identified")
            for f in flags:
                parts.append(f"  - [{f['severity']}] {f['detail']}")
        else:
            parts.append("• No major risk flags identified")
        if fin.get("financial_summary"):
            parts.append(f"\n{fin['financial_summary']}")
        return "\n".join(parts)
