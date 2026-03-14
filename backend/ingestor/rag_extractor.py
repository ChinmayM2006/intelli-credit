"""
RAG-based document extractor for large files.

Pipeline:
1) Chunk raw text with overlap (page-aware when markers exist)
2) Retrieve most relevant chunks using hybrid TF-IDF + keyword scoring
3) Run LLM extraction on retrieved context (not just first N chars)
"""
import json
import re
from typing import Any, Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from backend.config import RAG_MAX_TFIDF_CHUNKS, RAG_MAX_CONTEXT_CHARS


def _split_with_overlap(text: str, chunk_size: int = 2200, overlap: int = 300) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end]
        if end < n:
            newline = chunk.rfind("\n")
            if newline > int(chunk_size * 0.6):
                end = start + newline
                chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def _extract_page_num(text: str) -> Optional[int]:
    m = re.search(r"\[PAGE\s+(\d+)\]", text)
    return int(m.group(1)) if m else None


def _chunk_document(raw_text: str) -> List[Dict[str, Any]]:
    """Chunk text and keep page hints where available."""
    blocks = re.split(r"(?=\[PAGE\s+\d+\])", raw_text or "")
    chunks: List[Dict[str, Any]] = []
    idx = 0
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        page = _extract_page_num(block)
        for part in _split_with_overlap(block):
            idx += 1
            chunks.append({"id": idx, "text": part, "page": page})

    if not chunks:
        for part in _split_with_overlap(raw_text or ""):
            idx += 1
            chunks.append({"id": idx, "text": part, "page": None})
    return chunks


def _hybrid_retrieve(chunks: List[Dict[str, Any]], query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    if not chunks:
        return []

    q_terms = [w for w in re.findall(r"[a-zA-Z_]{3,}", query.lower()) if w not in {"json", "return", "extract"}]

    # Coarse prefilter for very large corpora
    working = chunks
    if len(chunks) > max(100, RAG_MAX_TFIDF_CHUNKS):
        coarse = []
        for chunk in chunks:
            t = chunk["text"].lower()
            score = 0
            for term in q_terms:
                if term in t:
                    score += min(t.count(term), 8)
            coarse.append((score, chunk))
        coarse.sort(key=lambda x: x[0], reverse=True)
        working = [c for s, c in coarse[:RAG_MAX_TFIDF_CHUNKS] if s > 0] or [c for _, c in coarse[:RAG_MAX_TFIDF_CHUNKS]]

    texts = [c["text"] for c in working]

    # TF-IDF score
    tfidf_scores = [0.0] * len(working)
    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=12000)
        matrix = vectorizer.fit_transform(texts + [query])
        q = matrix[-1]
        sims = (matrix[:-1] @ q.T).toarray().ravel()
        tfidf_scores = sims.tolist()
    except Exception:
        pass

    # Keyword score (robust fallback)
    keyword_scores = []
    for text in texts:
        t = text.lower()
        score = 0.0
        for term in q_terms:
            count = t.count(term)
            if count:
                score += min(count, 6)
        keyword_scores.append(score)

    # Normalize and combine
    max_tfidf = max(tfidf_scores) if tfidf_scores else 0.0
    max_kw = max(keyword_scores) if keyword_scores else 0.0
    ranked = []
    for i, chunk in enumerate(working):
        t = (tfidf_scores[i] / max_tfidf) if max_tfidf > 0 else 0.0
        k = (keyword_scores[i] / max_kw) if max_kw > 0 else 0.0
        score = 0.7 * t + 0.3 * k
        ranked.append((score, chunk))

    ranked.sort(key=lambda x: x[0], reverse=True)
    selected = [c for s, c in ranked[:max(1, top_k)] if s > 0]
    return selected or [c for _, c in ranked[:max(1, top_k)]]


async def extract_with_rag(raw_text: str, doc_type: str, top_k: int = 8) -> Optional[Dict[str, Any]]:
    """RAG-based extractor for large docs. Returns extracted fields dict or None."""
    from backend.llm.provider import get_llm
    from backend.ingestor.llm_extractor import EXTRACTION_PROMPTS

    llm = get_llm()
    if llm.name == "fallback":
        return None

    prompt_template = EXTRACTION_PROMPTS.get(doc_type)
    if not prompt_template:
        return None

    chunks = _chunk_document(raw_text)
    if not chunks:
        return None

    # Adaptive retrieval depth for larger documents
    if len(chunks) > 1500:
        top_k = max(top_k, 16)
    elif len(chunks) > 700:
        top_k = max(top_k, 12)

    retrieval_query = f"{doc_type} financial fields amounts ratios covenants taxes legal status dates auditor remarks"
    selected = _hybrid_retrieve(chunks, retrieval_query + "\n" + prompt_template[:500], top_k=top_k)
    context_blocks = []
    pages_used = []
    context_chars = 0
    for chunk in selected:
        p = chunk.get("page")
        if p is not None:
            pages_used.append(p)
            header = f"[CHUNK {chunk['id']} | PAGE {p}]"
        else:
            header = f"[CHUNK {chunk['id']}]"
        block = f"{header}\n{chunk['text']}"
        if context_chars + len(block) > max(4000, RAG_MAX_CONTEXT_CHARS):
            break
        context_blocks.append(block)
        context_chars += len(block)

    context = "\n\n".join(context_blocks)

    system_prompt = (
        "You are an expert Indian financial document parser. "
        "Extract financial data with high precision from retrieved chunks. "
        "Use 0 for missing numeric fields and empty strings/lists for missing text fields. "
        "Return ONLY valid JSON."
    )

    prompt = f"""{prompt_template}

Retrieved document context:
{context}

Return JSON only."""

    try:
        response = await llm.generate(prompt, system_prompt=system_prompt, json_mode=True, max_tokens=2500)
        response = (response or "").strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        data = json.loads(response)
        data["_rag_meta"] = {
            "chunks_considered": len(chunks),
            "chunks_used": len(selected),
            "context_chars": context_chars,
            "pages_used": sorted(list(set([p for p in pages_used if p is not None]))),
        }
        return data
    except (json.JSONDecodeError, Exception):
        return None


async def extract_open_schema_with_rag(raw_text: str, top_k: int = 14) -> Optional[Dict[str, Any]]:
    """
    Schema-less extraction for "everything relevant" from a document.
    Returns dynamic facts instead of fixed doc-type fields.
    """
    from backend.llm.provider import get_llm

    llm = get_llm()
    if llm.name == "fallback":
        return None

    chunks = _chunk_document(raw_text)
    if not chunks:
        return None

    if len(chunks) > 1500:
        top_k = max(top_k, 20)
    elif len(chunks) > 700:
        top_k = max(top_k, 16)

    query = (
        "all key financial numbers, dates, entities, legal matters, covenants, "
        "auditor comments, ratings, borrowings, tax signals, and risk indicators"
    )
    selected = _hybrid_retrieve(chunks, query, top_k=top_k)

    context_blocks = []
    pages_used = []
    context_chars = 0
    for chunk in selected:
        page = chunk.get("page")
        if page is not None:
            pages_used.append(page)
            header = f"[CHUNK {chunk['id']} | PAGE {page}]"
        else:
            header = f"[CHUNK {chunk['id']}]"
        block = f"{header}\n{chunk['text']}"
        if context_chars + len(block) > max(4000, RAG_MAX_CONTEXT_CHARS):
            break
        context_blocks.append(block)
        context_chars += len(block)

    context = "\n\n".join(context_blocks)

    system_prompt = (
        "You are a forensic document analyst for credit underwriting. "
        "Extract all materially relevant facts from retrieved text chunks. "
        "Do not invent values. If uncertain, lower confidence. "
        "Return only valid JSON."
    )

    prompt = f"""
Extract a schema-less representation from the context below.

Return JSON exactly in this structure:
{{
  "document_summary": "2-4 sentence summary",
  "key_facts": [
    {{
      "key": "normalized_fact_name",
      "value": "string or number",
      "category": "financial|governance|legal|operational|tax|risk|other",
      "unit": "optional",
      "period": "optional",
      "page": 0,
      "evidence": "short quote from context",
      "confidence": 0.0
    }}
  ],
  "entities": ["list of important entities/people/institutions"],
  "risk_signals": [
    {{"signal": "", "severity": "low|medium|high|critical", "evidence": "", "page": 0}}
  ],
  "missing_but_important": ["important items that appear missing in the document"]
}}

Rules:
- Include only facts supported by context.
- Keep only high-value facts; avoid duplicates.
- Provide at most 40 key_facts.

Context:
{context}
"""

    try:
        response = await llm.generate(prompt, system_prompt=system_prompt, json_mode=True, max_tokens=3000)
        response = (response or "").strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]

        data = json.loads(response)
        facts = data.get("key_facts", [])
        if isinstance(facts, list) and len(facts) > 40:
            data["key_facts"] = facts[:40]

        data["_rag_meta"] = {
            "chunks_considered": len(chunks),
            "chunks_used": len(selected),
            "context_chars": context_chars,
            "pages_used": sorted(list(set([p for p in pages_used if p is not None]))),
            "mode": "open_schema",
        }
        return data
    except (json.JSONDecodeError, Exception):
        return None
