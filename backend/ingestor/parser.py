"""
Data Ingestor - Multi-format document parser
Handles: PDF (scanned/digital), Excel, CSV, images
Extracts: Financial data, commitments, risks from unstructured documents
Supports: ALM, Shareholding, Borrowing Profile, Annual Report, Portfolio,
          GST, ITR, Bank Statement, Financial Statement, and more.
"""
import os
import re
import json
import importlib
from typing import Dict, Any, List, Optional, Callable

import pdfplumber
import pandas as pd
from backend.config import (
    OCR_MAX_PAGES,
    OCR_BATCH_SIZE,
    OCR_VISUAL_MAX_PAGES,
    OCR_VISUAL_MAX_REGIONS_PER_PAGE,
    OCR_VISUAL_MIN_TEXT_CHARS,
    OCR_LOW_TEXT_THRESHOLD,
    OCR_MAX_LOW_TEXT_PAGES,
)


# ─── Core Extraction ─────────────────────────────────────────────────────────

def _normalize_parse_mode(parse_mode: Optional[str]) -> str:
    mode = str(parse_mode or "balanced").strip().lower()
    aliases = {
        "fast": "fast",
        "⚡": "fast",
        "balanced": "balanced",
        "balance": "balanced",
        "⚖️": "balanced",
        "coverage": "max_coverage",
        "max_coverage": "max_coverage",
        "max-coverage": "max_coverage",
        "high_coverage": "max_coverage",
        "🔍": "max_coverage",
    }
    return aliases.get(mode, "balanced")


def _resolve_parse_limits(parse_mode: str) -> Dict[str, int]:
    """Resolve OCR/visual limits for mode presets."""
    mode = _normalize_parse_mode(parse_mode)

    base = {
        "low_text_threshold": max(1, OCR_LOW_TEXT_THRESHOLD),
        "max_low_text_pages": max(1, OCR_MAX_LOW_TEXT_PAGES),
        "visual_max_pages": max(1, OCR_VISUAL_MAX_PAGES),
        "visual_max_regions_per_page": max(1, OCR_VISUAL_MAX_REGIONS_PER_PAGE),
        "visual_min_text_chars": max(1, OCR_VISUAL_MIN_TEXT_CHARS),
    }

    if mode == "fast":
        return {
            **base,
            "low_text_threshold": max(50, int(base["low_text_threshold"] * 0.75)),
            "max_low_text_pages": max(8, int(base["max_low_text_pages"] * 0.5)),
            "visual_max_pages": max(20, int(base["visual_max_pages"] * 0.6)),
            "visual_max_regions_per_page": max(3, int(base["visual_max_regions_per_page"] * 0.6)),
            "visual_min_text_chars": max(16, base["visual_min_text_chars"]),
        }

    if mode == "max_coverage":
        return {
            **base,
            "low_text_threshold": min(260, int(base["low_text_threshold"] * 1.35)),
            "max_low_text_pages": max(base["max_low_text_pages"], int(base["max_low_text_pages"] * 1.7)),
            "visual_max_pages": max(base["visual_max_pages"], int(base["visual_max_pages"] * 1.6)),
            "visual_max_regions_per_page": max(base["visual_max_regions_per_page"], int(base["visual_max_regions_per_page"] * 1.5)),
            "visual_min_text_chars": max(8, int(base["visual_min_text_chars"] * 0.8)),
        }

    return base


def _safe_emit_progress(progress_hook: Optional[Callable[[int, str], None]], pct: int, message: str) -> None:
    if not progress_hook:
        return
    try:
        progress_hook(max(0, min(100, int(pct))), str(message or ""))
    except Exception:
        return


def parse_document(
    file_path: str,
    doc_type: str,
    parse_mode: str = "balanced",
    progress_hook: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Route document to the appropriate parser based on type and format."""
    ext = os.path.splitext(file_path)[1].lower()
    normalized_mode = _normalize_parse_mode(parse_mode)
    mode_limits = _resolve_parse_limits(normalized_mode)
    visual_extraction: Dict[str, Any] = {}

    _safe_emit_progress(progress_hook, 5, "Starting document parse")

    if ext == ".pdf":
        _safe_emit_progress(progress_hook, 8, "Extracting PDF text")
        pdf_meta = extract_pdf_text_with_stats(
            file_path,
            progress_hook=lambda pct, msg: _safe_emit_progress(progress_hook, 8 + int((pct / 100) * 34), msg),
        )
        raw_text = pdf_meta.get("raw_text", "")
        page_stats = pdf_meta.get("page_stats", [])

        low_text_pages = [
            p.get("page") for p in page_stats
            if (p.get("text_len") or 0) < mode_limits["low_text_threshold"]
        ]
        if low_text_pages:
            _safe_emit_progress(progress_hook, 44, "Running selective OCR on low-text pages")
            selective_ocr_text = _ocr_selected_pages(
                file_path,
                low_text_pages[: mode_limits["max_low_text_pages"]],
                progress_hook=lambda pct, msg: _safe_emit_progress(progress_hook, 44 + int((pct / 100) * 16), msg),
            )
            if selective_ocr_text:
                raw_text = f"{raw_text}\n\n[SELECTIVE_PAGE_OCR]\n{selective_ocr_text}".strip()

        _safe_emit_progress(progress_hook, 60, "Processing embedded visuals and graphs")
        visual_extraction = extract_pdf_visual_ocr(
            file_path,
            page_stats=page_stats,
            max_pages=mode_limits["visual_max_pages"],
            max_regions_per_page=mode_limits["visual_max_regions_per_page"],
            min_text_chars=mode_limits["visual_min_text_chars"],
            progress_hook=lambda pct, msg: _safe_emit_progress(progress_hook, 60 + int((pct / 100) * 20), msg),
        )
        visual_text = (visual_extraction or {}).get("ocr_text", "")
        if visual_text.strip():
            raw_text = f"{raw_text}\n\n[VISUAL_OCR]\n{visual_text}".strip()
        # OCR fallback for scanned PDFs
        if len(raw_text.strip()) < 100:
            _safe_emit_progress(progress_hook, 80, "Running full-page OCR fallback")
            raw_text = _ocr_fallback(
                file_path,
                progress_hook=lambda pct, msg: _safe_emit_progress(progress_hook, 80 + int((pct / 100) * 12), msg),
            ) or raw_text
    elif ext in (".xlsx", ".xls"):
        raw_text = extract_excel_text(file_path)
    elif ext == ".csv":
        raw_text = extract_csv_text(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        raw_text = _ocr_image(file_path) or ""
    else:
        raw_text = ""

    parsers = {
        "alm": parse_alm,
        "shareholding": parse_shareholding,
        "borrowing_profile": parse_borrowing_profile,
        "annual_report": parse_annual_report,
        "portfolio": parse_portfolio,
        "gst": parse_gst,
        "itr": parse_itr,
        "bank_statement": parse_bank_statement,
        "financial_statement": parse_financial_statement,
        "board_minutes": parse_board_minutes,
        "rating_report": parse_rating_report,
        "sanction_letter": parse_sanction_letter,
        "legal_notice": parse_legal_notice,
    }

    parser = parsers.get(doc_type, parse_generic)
    _safe_emit_progress(progress_hook, 94, "Structuring extracted data")
    result = parser(raw_text, file_path)
    result["raw_text_length"] = len(raw_text)
    result["raw_text"] = raw_text  # Keep for classification & LLM extraction
    result["file_format"] = ext
    result["parse_mode"] = normalized_mode
    result["parse_mode_meta"] = mode_limits
    if visual_extraction:
        result["visual_extraction"] = visual_extraction
    _safe_emit_progress(progress_hook, 100, "Parsing complete")
    return result


def extract_pdf_text(file_path: str) -> str:
    """Extract text from PDF using pdfplumber (handles digital PDFs)."""
    return extract_pdf_text_with_stats(file_path).get("raw_text", "")


def extract_pdf_text_with_stats(
    file_path: str,
    progress_hook: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Extract PDF text/tables and return per-page stats for adaptive OCR decisions."""
    text_parts = []
    page_stats: List[Dict[str, Any]] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = max(1, len(pdf.pages))
            for idx, page in enumerate(pdf.pages, start=1):
                text_parts.append(f"[PAGE {idx}]")
                page_text = page.extract_text()
                table_rows = 0
                if page_text:
                    text_parts.append(page_text)
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text_parts.append(" | ".join([str(c) if c else "" for c in row]))
                            table_rows += 1
                page_stats.append({
                    "page": idx,
                    "text_len": len((page_text or "").strip()),
                    "table_rows": table_rows,
                    "image_count": len(page.images or []),
                })
                _safe_emit_progress(progress_hook, int((idx / total_pages) * 100), f"Reading page {idx}/{total_pages}")
    except Exception as e:
        text_parts.append(f"[PDF extraction error: {str(e)}]")
    return {
        "raw_text": "\n".join(text_parts),
        "page_stats": page_stats,
        "total_pages": len(page_stats),
    }


def _classify_visual_kind(text: str) -> str:
    """Heuristic label for OCR text extracted from embedded visuals."""
    t = (text or "").lower()
    if any(k in t for k in ["chart", "graph", "axis", "trendline", "bar", "line", "%"]):
        return "graph"
    if any(k in t for k in ["figure", "image", "illustration", "diagram"]):
        return "figure"
    if any(k in t for k in ["table", "total", "amount", "revenue", "ebitda", "pat"]):
        return "table_like_visual"
    return "image"


def extract_pdf_visual_ocr(
    file_path: str,
    page_stats: Optional[List[Dict[str, Any]]] = None,
    max_pages: Optional[int] = None,
    max_regions_per_page: Optional[int] = None,
    min_text_chars: Optional[int] = None,
    progress_hook: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    OCR text from embedded image/graph regions inside PDF pages.
    Returns structured visual artifacts and concatenated OCR text.
    """
    try:
        pytesseract = importlib.import_module("pytesseract")
        image_ops = importlib.import_module("PIL.ImageOps")
    except Exception:
        return {
            "enabled": False,
            "reason": "pytesseract/Pillow not available",
            "elements": [],
            "ocr_text": "",
        }

    elements: List[Dict[str, Any]] = []
    ocr_fragments: List[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            if page_stats:
                prioritized = sorted(
                    [p for p in page_stats if (p.get("image_count") or 0) > 0],
                    key=lambda x: (x.get("image_count") or 0),
                    reverse=True,
                )
                candidate_pages = [int(p.get("page")) for p in prioritized if p.get("page")]
            else:
                candidate_pages = []

            if not candidate_pages:
                candidate_pages = list(range(1, total_pages + 1))

            max_scan_pages = max(1, int(max_pages or OCR_VISUAL_MAX_PAGES))
            candidate_pages = candidate_pages[: min(len(candidate_pages), max_scan_pages)]
            regions_per_page = max(1, int(max_regions_per_page or OCR_VISUAL_MAX_REGIONS_PER_PAGE))
            if total_pages > 150:
                regions_per_page = max(3, regions_per_page // 2)

            min_chars = max(1, int(min_text_chars or OCR_VISUAL_MIN_TEXT_CHARS))

            total_candidates = max(1, len(candidate_pages))
            for idx_page, page_num in enumerate(candidate_pages, start=1):
                if page_num < 1 or page_num > total_pages:
                    continue
                page = pdf.pages[page_num - 1]
                page_images = (page.images or [])[: max(1, regions_per_page)]

                _safe_emit_progress(progress_hook, int((idx_page / total_candidates) * 100), f"Visual OCR page {page_num}/{total_pages}")

                if not page_images:
                    continue

                try:
                    page_pil = page.to_image(resolution=220).original.convert("RGB")
                except Exception:
                    continue

                scale_x = page_pil.width / max(float(page.width or 1), 1.0)
                scale_y = page_pil.height / max(float(page.height or 1), 1.0)

                for img_idx, img_meta in enumerate(page_images, start=1):
                    x0 = float(img_meta.get("x0", 0.0) or 0.0)
                    x1 = float(img_meta.get("x1", page.width) or page.width)
                    top = float(img_meta.get("top", 0.0) or 0.0)
                    bottom = float(img_meta.get("bottom", page.height) or page.height)

                    left_px = max(0, min(int(x0 * scale_x), page_pil.width - 1))
                    right_px = max(left_px + 1, min(int(x1 * scale_x), page_pil.width))
                    upper_px = max(0, min(int(top * scale_y), page_pil.height - 1))
                    lower_px = max(upper_px + 1, min(int(bottom * scale_y), page_pil.height))

                    if right_px <= left_px or lower_px <= upper_px:
                        continue

                    region = page_pil.crop((left_px, upper_px, right_px, lower_px))
                    try:
                        gray = image_ops.grayscale(region)
                        ocr_text = pytesseract.image_to_string(gray, lang="eng")
                    except Exception:
                        ocr_text = ""

                    cleaned = (ocr_text or "").strip()
                    if len(cleaned) < min_chars:
                        continue

                    kind = _classify_visual_kind(cleaned)
                    elements.append({
                        "page": page_num,
                        "index": img_idx,
                        "kind": kind,
                        "bbox_pdf": {
                            "x0": round(x0, 2),
                            "x1": round(x1, 2),
                            "top": round(top, 2),
                            "bottom": round(bottom, 2),
                        },
                        "ocr_text": cleaned[:4000],
                    })
                    ocr_fragments.append(f"[PAGE {page_num}][{kind.upper()} {img_idx}] {cleaned}")
    except Exception as e:
        return {
            "enabled": False,
            "reason": f"visual OCR failed: {str(e)}",
            "elements": [],
            "ocr_text": "",
        }

    return {
        "enabled": True,
        "elements": elements,
        "ocr_text": "\n".join(ocr_fragments),
        "summary": {
            "elements_found": len(elements),
            "pages_scanned": len(candidate_pages) if 'candidate_pages' in locals() else 0,
            "graph_like_elements": sum(1 for e in elements if e.get("kind") == "graph"),
        },
    }


def _ocr_selected_pages(
    file_path: str,
    pages: List[int],
    progress_hook: Optional[Callable[[int, str], None]] = None,
) -> Optional[str]:
    """OCR only selected low-text pages for speed + better mixed-document coverage."""
    if not pages:
        return None
    try:
        pdf2image = importlib.import_module("pdf2image")
        pytesseract = importlib.import_module("pytesseract")
        convert_from_path = getattr(pdf2image, "convert_from_path")
    except Exception:
        return None

    fragments = []
    seen = set()
    total_pages = max(1, len(pages))
    for idx, page_num in enumerate(pages, start=1):
        try:
            p = int(page_num)
        except Exception:
            continue
        if p <= 0 or p in seen:
            continue
        seen.add(p)
        try:
            images = convert_from_path(file_path, dpi=220, first_page=p, last_page=p)
            if not images:
                continue
            text = pytesseract.image_to_string(images[0], lang="eng")
            cleaned = (text or "").strip()
            if cleaned:
                fragments.append(f"[PAGE {p}] {cleaned}")
        except Exception:
            continue
        _safe_emit_progress(progress_hook, int((idx / total_pages) * 100), f"Selective OCR page {idx}/{total_pages}")

    return "\n".join(fragments) if fragments else None


def _ocr_fallback(
    file_path: str,
    progress_hook: Optional[Callable[[int, str], None]] = None,
) -> Optional[str]:
    """OCR fallback for scanned PDFs using pytesseract."""
    try:
        pdf2image = importlib.import_module("pdf2image")
        pytesseract = importlib.import_module("pytesseract")
        convert_from_path = getattr(pdf2image, "convert_from_path")
        pdfinfo_from_path = getattr(pdf2image, "pdfinfo_from_path")

        try:
            info = pdfinfo_from_path(file_path)
            total_pages = int(info.get("Pages", 0))
        except Exception:
            total_pages = 0

        if total_pages <= 0:
            total_pages = OCR_MAX_PAGES

        last_page = min(total_pages, max(1, OCR_MAX_PAGES))
        texts = []

        start = 1
        processed_pages = 0
        total_for_progress = max(1, last_page)
        while start <= last_page:
            end = min(start + max(1, OCR_BATCH_SIZE) - 1, last_page)
            images = convert_from_path(file_path, dpi=200, first_page=start, last_page=end)
            for offset, img in enumerate(images):
                page_num = start + offset
                texts.append(f"[PAGE {page_num}]")
                text = pytesseract.image_to_string(img, lang="eng")
                texts.append(text)
                processed_pages += 1
                _safe_emit_progress(progress_hook, int((processed_pages / total_for_progress) * 100), f"OCR page {processed_pages}/{total_for_progress}")
            start = end + 1

        return "\n".join(texts)
    except ImportError:
        return None
    except Exception:
        return None


def _ocr_image(file_path: str) -> Optional[str]:
    """OCR for image files."""
    try:
        pil_image = importlib.import_module("PIL.Image")
        pytesseract = importlib.import_module("pytesseract")
        image_open = getattr(pil_image, "open")
        img = image_open(file_path)
        return pytesseract.image_to_string(img, lang="eng")
    except ImportError:
        return None
    except Exception:
        return None


def extract_excel_text(file_path: str) -> str:
    """Extract data from Excel files."""
    try:
        dfs = pd.read_excel(file_path, sheet_name=None)
        parts = []
        for sheet_name, df in dfs.items():
            parts.append(f"=== Sheet: {sheet_name} ===")
            parts.append(df.to_string())
        return "\n".join(parts)
    except Exception as e:
        return f"[Excel extraction error: {str(e)}]"


def extract_csv_text(file_path: str) -> str:
    """Extract data from CSV files."""
    try:
        df = pd.read_csv(file_path)
        return df.to_string()
    except Exception as e:
        return f"[CSV extraction error: {str(e)}]"


# ─── Utility Functions ───────────────────────────────────────────────────────

def _extract_amounts(text: str) -> List[float]:
    """Extract monetary amounts from text (INR context)."""
    patterns = [
        r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)\s*(?:Cr|Crore|Lakh|L|cr|lakh)?',
        r'([\d,]+(?:\.\d{1,2})?)\s*(?:Cr|Crore|Lakh|crore|lakh)',
    ]
    amounts = []
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m.replace(",", ""))
                if val > 0:
                    amounts.append(val)
            except ValueError:
                pass
    return amounts


def _extract_dates(text: str) -> List[str]:
    """Extract dates from text."""
    patterns = [
        r'\d{2}[/-]\d{2}[/-]\d{4}',
        r'\d{4}[/-]\d{2}[/-]\d{2}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}',
    ]
    dates = []
    for pat in patterns:
        dates.extend(re.findall(pat, text, re.IGNORECASE))
    return dates[:20]


def _extract_percentages(text: str) -> List[float]:
    """Extract percentage values."""
    matches = re.findall(r'([\d]+\.?\d*)\s*%', text)
    return [float(m) for m in matches if 0 <= float(m) <= 100]


def _find_near_keyword(text: str, keywords: List[str], extract_fn, window: int = 200):
    """Find values near specific keywords."""
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            nearby = text[idx:idx + window]
            result = extract_fn(nearby)
            if result:
                return result[0] if isinstance(result, list) else result
    return None


# ─── NEW: ALM Parser ────────────────────────────────────────────────────────

def parse_alm(text: str, file_path: str) -> Dict[str, Any]:
    """Parse ALM (Asset-Liability Management) statement."""
    amounts = _extract_amounts(text)
    percentages = _extract_percentages(text)
    text_lower = text.lower()

    # Extract maturity buckets
    bucket_names = {
        "1_30_days": ["1-30", "1 to 30", "upto 30", "0-30", "up to 1 month"],
        "31_90_days": ["31-90", "31 to 90", "1-3 month", "over 1 month"],
        "91_180_days": ["91-180", "91 to 180", "3-6 month", "over 3 month"],
        "181_365_days": ["181-365", "181 to 365", "6-12 month", "6 month to 1 year"],
        "1_3_years": ["1-3 year", "over 1 year", "1 to 3 year"],
        "3_5_years": ["3-5 year", "over 3 year", "3 to 5 year"],
        "over_5_years": ["over 5 year", "above 5 year", "> 5 year"],
    }

    buckets = {}
    for bucket_key, keywords in bucket_names.items():
        for kw in keywords:
            idx = text_lower.find(kw)
            if idx != -1:
                nearby = text[max(0, idx - 50):idx + 300]
                nearby_amounts = _extract_amounts(nearby)
                if len(nearby_amounts) >= 2:
                    buckets[bucket_key] = {
                        "inflows": nearby_amounts[0],
                        "outflows": nearby_amounts[1],
                        "mismatch": nearby_amounts[0] - nearby_amounts[1],
                    }
                break

    # Cumulative mismatch
    cum_mismatch = _find_near_keyword(text, ["cumulative mismatch", "cumulative gap"], _extract_percentages)

    # NII sensitivity
    nii_sensitivity = _find_near_keyword(text, ["nii sensitivity", "nii impact", "net interest income"], _extract_amounts)

    # Identify risks
    risks = []
    negative_short_term = False
    for bucket_key in ["1_30_days", "31_90_days", "91_180_days"]:
        if bucket_key in buckets and buckets[bucket_key].get("mismatch", 0) < 0:
            negative_short_term = True
            risks.append({
                "type": "NEGATIVE_SHORT_TERM_MISMATCH",
                "severity": "HIGH",
                "detail": f"Negative mismatch in {bucket_key.replace('_', '-')} bucket: {buckets[bucket_key]['mismatch']}",
            })

    if cum_mismatch and cum_mismatch < -10:
        risks.append({
            "type": "HIGH_CUMULATIVE_MISMATCH",
            "severity": "CRITICAL",
            "detail": f"Cumulative mismatch exceeds -10%: {cum_mismatch}%",
        })

    if "structural liquidity" in text_lower and "negative" in text_lower:
        risks.append({"type": "STRUCTURAL_LIQUIDITY_RISK", "severity": "HIGH",
                       "detail": "Negative structural liquidity statement identified"})

    return {
        "doc_type": "alm",
        "summary": f"ALM statement with {len(buckets)} maturity buckets identified",
        "fields": {
            "maturity_buckets": buckets,
            "cumulative_mismatch_pct": cum_mismatch,
            "nii_sensitivity": nii_sensitivity,
            "has_negative_short_term": negative_short_term,
            "all_amounts": amounts[:20],
            "all_percentages": percentages[:15],
        },
        "risks": risks,
    }


# ─── ENHANCED: Shareholding Parser ──────────────────────────────────────────

def parse_shareholding(text: str, file_path: str) -> Dict[str, Any]:
    """Parse shareholding pattern with enhanced extraction."""
    text_lower = text.lower()

    # Promoter holding
    promoter_pct = _find_near_keyword(text, ["promoter", "promoter group", "promoter and promoter group"], _extract_percentages)
    public_pct = _find_near_keyword(text, ["public", "non-promoter", "public shareholding"], _extract_percentages)

    # FII/DII
    fii_pct = _find_near_keyword(text, ["fii", "foreign institutional", "foreign portfolio"], _extract_percentages)
    dii_pct = _find_near_keyword(text, ["dii", "domestic institutional", "mutual fund"], _extract_percentages)

    # Pledged shares
    pledge_pct = _find_near_keyword(text, ["pledged", "encumbered", "pledge"], _extract_percentages)

    # Promoter entities
    promoter_entities = []
    promoter_patterns = re.findall(r'(?:promoter|holding company)[\s:]+([A-Z][A-Za-z\s&]+(?:Ltd|Limited|LLP|Pvt))', text)
    promoter_entities = [p.strip() for p in promoter_patterns[:5]]

    # QoQ change
    qoq_change = None
    change_match = re.search(r'(?:change|increase|decrease).*?(\d+\.?\d*)\s*%', text_lower)
    if change_match:
        qoq_change = float(change_match.group(1))
        if "decrease" in text_lower[max(0, change_match.start() - 50):change_match.start()]:
            qoq_change = -qoq_change

    fields = {
        "promoter_holding_pct": promoter_pct,
        "public_holding_pct": public_pct,
        "fii_holding_pct": fii_pct,
        "dii_holding_pct": dii_pct,
        "pledged_shares_pct": pledge_pct,
        "promoter_entities": promoter_entities,
        "qoq_change_promoter": qoq_change,
    }

    risks = []
    if promoter_pct and promoter_pct < 30:
        risks.append({"type": "LOW_PROMOTER_HOLDING", "severity": "MEDIUM",
                       "detail": f"Promoter holding is only {promoter_pct}%"})
    if pledge_pct and pledge_pct > 20:
        severity = "CRITICAL" if pledge_pct > 50 else "HIGH"
        risks.append({"type": "HIGH_PLEDGE", "severity": severity,
                       "detail": f"{pledge_pct}% promoter shares pledged"})
    if qoq_change and qoq_change < -5:
        risks.append({"type": "PROMOTER_SELLING", "severity": "HIGH",
                       "detail": f"Promoter holding decreased by {abs(qoq_change)}%"})

    return {
        "doc_type": "shareholding",
        "summary": f"Shareholding pattern - Promoter: {promoter_pct or 'N/A'}%, Pledged: {pledge_pct or 'N/A'}%",
        "fields": fields,
        "risks": risks,
    }


# ─── NEW: Borrowing Profile Parser ──────────────────────────────────────────

def parse_borrowing_profile(text: str, file_path: str) -> Dict[str, Any]:
    """Parse borrowing/loan facility profile."""
    amounts = _extract_amounts(text)
    text_lower = text.lower()

    # Extract facility details
    facilities = []
    # Look for table rows with lender info
    lender_patterns = [
        r'(SBI|HDFC|ICICI|Axis|PNB|Bank of Baroda|Union Bank|Canara|IndusInd|Yes Bank|Kotak|BOB|BOI|UCO|IDBI|Federal)\s*.*?([\d,.]+)\s*.*?([\d,.]+)',
    ]
    for pat in lender_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            try:
                facilities.append({
                    "lender": m[0].strip(),
                    "sanctioned": float(m[1].replace(",", "")),
                    "outstanding": float(m[2].replace(",", "")),
                })
            except (ValueError, IndexError):
                pass

    # Totals
    total_sanctioned = _find_near_keyword(text, ["total sanctioned", "aggregate sanctioned", "total limit"], _extract_amounts) or 0
    total_outstanding = _find_near_keyword(text, ["total outstanding", "aggregate outstanding", "total utilization"], _extract_amounts) or 0
    total_overdue = _find_near_keyword(text, ["total overdue", "overdue amount", "npa amount"], _extract_amounts) or 0

    # Facility types
    has_wc = any(kw in text_lower for kw in ["working capital", "cash credit", "cc limit", "overdraft", "od limit"])
    has_tl = any(kw in text_lower for kw in ["term loan", "tl ", "term facility"])

    # Number of lenders
    bank_names = re.findall(r'(?:SBI|HDFC|ICICI|Axis|PNB|Bank of Baroda|Union Bank|Canara|IndusInd|Yes Bank|Kotak|BOB|BOI|UCO|IDBI|Federal|Bandhan|RBL)', text, re.IGNORECASE)
    num_lenders = len(set(b.upper() for b in bank_names))

    risks = []
    if total_overdue and total_overdue > 0:
        severity = "CRITICAL" if total_overdue > total_outstanding * 0.1 else "HIGH"
        risks.append({"type": "OVERDUE_PRESENT", "severity": severity,
                       "detail": f"Overdue amount: ₹{total_overdue} Cr"})
    if total_sanctioned and total_outstanding:
        utilization = total_outstanding / total_sanctioned * 100 if total_sanctioned > 0 else 0
        if utilization > 90:
            risks.append({"type": "HIGH_UTILIZATION", "severity": "HIGH",
                           "detail": f"Facility utilization at {utilization:.0f}%"})
    if num_lenders > 5:
        risks.append({"type": "MULTIPLE_LENDERS", "severity": "MEDIUM",
                       "detail": f"{num_lenders} lenders identified — check consortium arrangements"})

    return {
        "doc_type": "borrowing_profile",
        "summary": f"Borrowing profile: {num_lenders} lenders, ₹{total_outstanding} outstanding",
        "fields": {
            "total_sanctioned": total_sanctioned,
            "total_outstanding": total_outstanding,
            "total_overdue": total_overdue,
            "facilities": facilities[:20],
            "number_of_lenders": num_lenders,
            "has_working_capital": has_wc,
            "has_term_loan": has_tl,
            "all_amounts": amounts[:20],
        },
        "risks": risks,
    }


# ─── ENHANCED: Annual Report Parser ─────────────────────────────────────────

def parse_annual_report(text: str, file_path: str) -> Dict[str, Any]:
    """Parse annual reports — extract P&L, BS, CF, ratios, and risk signals."""
    amounts = _extract_amounts(text)
    text_lower = text.lower()

    # Key sections detection
    sections = {
        "directors_report": bool(re.search(r"director'?s?\s+report", text, re.IGNORECASE)),
        "auditor_report": bool(re.search(r"auditor'?s?\s+report|independent\s+auditor", text, re.IGNORECASE)),
        "balance_sheet": bool(re.search(r"balance\s+sheet", text, re.IGNORECASE)),
        "pnl": bool(re.search(r"profit\s+and\s+loss|income\s+statement|statement\s+of\s+profit", text, re.IGNORECASE)),
        "cash_flow": bool(re.search(r"cash\s+flow", text, re.IGNORECASE)),
        "notes_to_accounts": bool(re.search(r"notes\s+to\s+(?:the\s+)?(?:financial\s+)?(?:statement|account)", text, re.IGNORECASE)),
    }

    # P&L extraction
    revenue = _find_near_keyword(text, ["revenue from operations", "gross revenue", "total revenue", "net sales"], _extract_amounts)
    pat_val = _find_near_keyword(text, ["profit after tax", "pat", "net profit for the year", "profit for the period"], _extract_amounts)
    ebitda = _find_near_keyword(text, ["ebitda", "operating profit", "profit before interest"], _extract_amounts)
    interest_expense = _find_near_keyword(text, ["interest expense", "finance cost", "finance charges", "interest paid"], _extract_amounts)
    depreciation = _find_near_keyword(text, ["depreciation", "depreciation and amortisation"], _extract_amounts)

    # Balance Sheet
    total_equity = _find_near_keyword(text, ["total equity", "shareholder", "net worth", "equity and liabilities"], _extract_amounts)
    total_debt = _find_near_keyword(text, ["total borrowing", "total debt", "long term borrowing", "total loans"], _extract_amounts)
    current_assets = _find_near_keyword(text, ["current assets", "total current assets"], _extract_amounts)
    current_liabilities = _find_near_keyword(text, ["current liabilities", "total current liabilities"], _extract_amounts)
    total_assets = _find_near_keyword(text, ["total assets"], _extract_amounts)

    # Cash Flow
    cfo = _find_near_keyword(text, ["cash from operating", "operating activities", "cash generated from operations"], _extract_amounts)

    # Compute ratios
    ratios = {}
    if total_debt and total_equity and total_equity > 0:
        ratios["de_ratio"] = round(total_debt / total_equity, 2)
    if current_assets and current_liabilities and current_liabilities > 0:
        ratios["current_ratio"] = round(current_assets / current_liabilities, 2)
    if ebitda and interest_expense and interest_expense > 0:
        ratios["icr"] = round(ebitda / interest_expense, 2)
    elif pat_val and interest_expense and interest_expense > 0:
        ratios["icr"] = round((pat_val + interest_expense) / interest_expense, 2)
    if pat_val and revenue and revenue > 0:
        ratios["pat_margin_pct"] = round(pat_val / revenue * 100, 2)
    if pat_val and total_equity and total_equity > 0:
        ratios["roe_pct"] = round(pat_val / total_equity * 100, 2)
    if total_debt and ebitda and ebitda > 0:
        ratios["debt_ebitda"] = round(total_debt / ebitda, 2)

    # Also try regex for explicitly stated ratios
    ratio_patterns = {
        "current_ratio": r"current\s+ratio\s*[:\-]?\s*([\d.]+)",
        "de_ratio": r"debt[\s\-/]+equity\s*[:\-]?\s*([\d.]+)",
        "icr": r"interest\s+coverage\s*[:\-]?\s*([\d.]+)",
        "pat_margin_pct": r"(?:PAT|net\s+profit)\s*margin\s*[:\-]?\s*([\d.]+)\s*%?",
        "roe_pct": r"(?:ROE|return\s+on\s+equity)\s*[:\-]?\s*([\d.]+)\s*%?",
    }
    for name, pat in ratio_patterns.items():
        if name not in ratios:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                ratios[name] = float(match.group(1))

    # Audit opinion
    audit_opinion = "unqualified"
    if "qualified opinion" in text_lower:
        audit_opinion = "qualified"
    elif "adverse opinion" in text_lower:
        audit_opinion = "adverse"
    elif "disclaimer of opinion" in text_lower:
        audit_opinion = "disclaimer"

    # Contingent liabilities
    contingent = _find_near_keyword(text, ["contingent liabilit"], _extract_amounts)

    # Related party transactions
    rpt_section = ""
    idx = text_lower.find("related party")
    if idx != -1:
        rpt_section = text[idx:idx + 500]

    # Risks
    risks = []
    risk_keywords = {
        "going concern": ("GOING_CONCERN", "CRITICAL"),
        "material weakness": ("MATERIAL_WEAKNESS", "HIGH"),
        "qualified opinion": ("QUALIFIED_AUDIT", "HIGH"),
        "adverse opinion": ("ADVERSE_AUDIT", "CRITICAL"),
        "disclaimer of opinion": ("DISCLAIMER_AUDIT", "CRITICAL"),
        "contingent liabilit": ("CONTINGENT_LIABILITY", "MEDIUM"),
        "default": ("DEFAULT_MENTION", "HIGH"),
        "fraud": ("FRAUD_MENTION", "CRITICAL"),
        "litigation": ("LITIGATION", "MEDIUM"),
        "related party": ("RELATED_PARTY", "LOW"),
    }
    for keyword, (risk_type, severity) in risk_keywords.items():
        if keyword in text_lower:
            risks.append({"type": risk_type, "severity": severity, "detail": f"'{keyword}' mentioned in annual report"})

    # Ratio-based risks
    if ratios.get("de_ratio", 0) > 3:
        risks.append({"type": "HIGH_LEVERAGE", "severity": "HIGH", "detail": f"D/E ratio: {ratios['de_ratio']}"})
    if ratios.get("icr", 999) < 1.5:
        risks.append({"type": "LOW_ICR", "severity": "HIGH", "detail": f"ICR: {ratios.get('icr')}"})
    if ratios.get("current_ratio", 999) < 1:
        risks.append({"type": "LIQUIDITY_RISK", "severity": "HIGH", "detail": f"Current ratio: {ratios['current_ratio']}"})

    return {
        "doc_type": "annual_report",
        "summary": f"Annual report: {sum(sections.values())}/{len(sections)} sections, {len(ratios)} ratios computed",
        "fields": {
            "sections_found": sections,
            "profit_and_loss": {
                "revenue": revenue, "ebitda": ebitda, "pat": pat_val,
                "interest_expense": interest_expense, "depreciation": depreciation,
            },
            "balance_sheet": {
                "total_equity": total_equity, "total_debt": total_debt,
                "current_assets": current_assets, "current_liabilities": current_liabilities,
                "total_assets": total_assets,
            },
            "cash_flow": {"cfo": cfo},
            "ratios": ratios,
            "audit_opinion": audit_opinion,
            "contingent_liabilities": contingent,
            "related_party_excerpt": rpt_section[:300] if rpt_section else None,
            "key_amounts": amounts[:20],
        },
        "risks": risks,
    }


# ─── NEW: Portfolio Parser ───────────────────────────────────────────────────

def parse_portfolio(text: str, file_path: str) -> Dict[str, Any]:
    """Parse portfolio cuts / performance data (common for NBFCs/Banks)."""
    amounts = _extract_amounts(text)
    percentages = _extract_percentages(text)
    text_lower = text.lower()

    # Key metrics
    aum = _find_near_keyword(text, ["aum", "assets under management", "total portfolio", "loan book"], _extract_amounts)
    gnpa = _find_near_keyword(text, ["gnpa", "gross npa", "gross non-performing"], _extract_percentages)
    nnpa = _find_near_keyword(text, ["nnpa", "net npa", "net non-performing"], _extract_percentages)
    pcr = _find_near_keyword(text, ["provision coverage", "pcr", "coverage ratio"], _extract_percentages)
    collection_eff = _find_near_keyword(text, ["collection efficiency", "recovery rate"], _extract_percentages)
    restructured = _find_near_keyword(text, ["restructured", "restructuring"], _extract_percentages)

    # DPD buckets
    dpd_0_30 = _find_near_keyword(text, ["0-30 dpd", "0 to 30 days", "current bucket"], _extract_percentages)
    dpd_31_60 = _find_near_keyword(text, ["31-60 dpd", "30-60 days", "30 to 60"], _extract_percentages)
    dpd_61_90 = _find_near_keyword(text, ["61-90 dpd", "60-90 days", "60 to 90"], _extract_percentages)
    dpd_90_plus = _find_near_keyword(text, ["90+ dpd", "90 plus", "over 90 days", "npa bucket"], _extract_percentages)

    # Sector exposure
    sectors_found = []
    sector_keywords = ["housing", "vehicle", "personal", "msme", "corporate", "agriculture",
                        "infrastructure", "retail", "wholesale", "nbfc", "microfinance"]
    for s in sector_keywords:
        if s in text_lower:
            pct = _find_near_keyword(text, [s], _extract_percentages)
            if pct:
                sectors_found.append({"sector": s.title(), "pct": pct})

    # Top borrower concentration
    concentration = _find_near_keyword(text, ["top 10", "top borrower", "single borrower", "concentration"], _extract_percentages)

    risks = []
    if gnpa and gnpa > 5:
        risks.append({"type": "HIGH_GNPA", "severity": "HIGH", "detail": f"GNPA at {gnpa}%"})
    if gnpa and gnpa > 10:
        risks.append({"type": "CRITICAL_NPA", "severity": "CRITICAL", "detail": f"GNPA exceeds 10%: {gnpa}%"})
    if collection_eff and collection_eff < 90:
        risks.append({"type": "LOW_COLLECTION", "severity": "HIGH", "detail": f"Collection efficiency: {collection_eff}%"})
    if concentration and concentration > 25:
        risks.append({"type": "CONCENTRATION_RISK", "severity": "HIGH",
                       "detail": f"Top borrower concentration: {concentration}%"})
    if restructured and restructured > 5:
        risks.append({"type": "HIGH_RESTRUCTURED", "severity": "MEDIUM",
                       "detail": f"Restructured book: {restructured}%"})
    if dpd_90_plus and dpd_90_plus > 5:
        risks.append({"type": "HIGH_DPD_90", "severity": "HIGH", "detail": f"90+ DPD: {dpd_90_plus}%"})

    return {
        "doc_type": "portfolio",
        "summary": f"Portfolio: AUM ₹{aum or 'N/A'} Cr, GNPA {gnpa or 'N/A'}%, Collection {collection_eff or 'N/A'}%",
        "fields": {
            "total_aum": aum,
            "gnpa_pct": gnpa,
            "nnpa_pct": nnpa,
            "provision_coverage_ratio": pcr,
            "collection_efficiency_pct": collection_eff,
            "restructured_book_pct": restructured,
            "sector_exposure": sectors_found,
            "top_borrower_concentration_pct": concentration,
            "dpd_buckets": {
                "0_30": dpd_0_30, "31_60": dpd_31_60,
                "61_90": dpd_61_90, "90_plus": dpd_90_plus,
            },
            "all_amounts": amounts[:15],
        },
        "risks": risks,
    }


# ─── ENHANCED: GST Parser (India-specific: 2A vs 2B vs 3B) ─────────────────

def parse_gst(text: str, file_path: str) -> Dict[str, Any]:
    """Parse GST returns with India-specific nuance (GSTR-1/2A/2B/3B/9)."""
    amounts = _extract_amounts(text)
    text_upper = text.upper()
    text_lower = text.lower()

    # Detect GSTR type with proper understanding
    gstr_type = "GST Return"
    gstr_types_info = {
        "GSTR-1": {"pattern": "GSTR.?1[^0-9]|GSTR-1", "desc": "Outward supplies return"},
        "GSTR-2A": {"pattern": "GSTR.?2A|2A", "desc": "Auto-populated inward supplies (dynamic, supplier-filed)"},
        "GSTR-2B": {"pattern": "GSTR.?2B|2B", "desc": "Auto-drafted ITC statement (static, reliable for ITC matching)"},
        "GSTR-3B": {"pattern": "GSTR.?3B|3B", "desc": "Summary return with tax liability and ITC claim"},
        "GSTR-9": {"pattern": "GSTR.?9[^A]|ANNUAL RETURN", "desc": "Annual GST return"},
    }
    for gtype, info in gstr_types_info.items():
        if re.search(info["pattern"], text_upper):
            gstr_type = gtype
            break

    # GSTIN
    gstin_match = re.search(r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}', text)
    gstin = gstin_match.group() if gstin_match else "Not found"

    # Turnover / taxable value
    turnover_keywords = ["taxable value", "total taxable", "turnover", "aggregate turnover"]
    turnover_values = []
    for kw in turnover_keywords:
        idx = text_lower.find(kw)
        if idx != -1:
            vals = _extract_amounts(text[idx:idx + 150])
            turnover_values.extend(vals)

    # ITC (Input Tax Credit) — critical for 2B vs 3B matching
    itc_claimed = _find_near_keyword(text, ["itc claimed", "input tax credit claimed", "itc availed", "eligible itc claimed"], _extract_amounts) or 0
    itc_eligible = _find_near_keyword(text, ["itc eligible", "eligible itc", "itc available", "auto-drafted itc", "2b itc"], _extract_amounts) or 0
    itc_mismatch = 0
    if itc_claimed and itc_eligible and itc_eligible > 0:
        itc_mismatch = round(abs(itc_claimed - itc_eligible) / itc_eligible * 100, 2)

    # Tax components
    igst = _find_near_keyword(text, ["igst"], _extract_amounts) or 0
    cgst = _find_near_keyword(text, ["cgst"], _extract_amounts) or 0
    sgst = _find_near_keyword(text, ["sgst"], _extract_amounts) or 0

    # Tax periods
    tax_periods = re.findall(r'(?:FY|AY|April|March|Quarter|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*[\d\-/]+', text, re.IGNORECASE)

    # Reverse charge
    reverse_charge = _find_near_keyword(text, ["reverse charge"], _extract_amounts) or 0

    # Late fee
    late_fee = _find_near_keyword(text, ["late fee", "penalty"], _extract_amounts) or 0

    risks = _identify_gst_risks(text, amounts, gstr_type, itc_mismatch, late_fee)

    return {
        "doc_type": "gst",
        "gstr_type": gstr_type,
        "gstin": gstin,
        "summary": f"{gstr_type} for GSTIN {gstin}. ITC mismatch: {itc_mismatch}%",
        "fields": {
            "gstin": gstin,
            "gstr_type": gstr_type,
            "gstr_description": gstr_types_info.get(gstr_type, {}).get("desc", ""),
            "reported_turnover": turnover_values[:5] if turnover_values else amounts[:5],
            "itc_claimed": itc_claimed,
            "itc_eligible": itc_eligible,
            "itc_mismatch_pct": itc_mismatch,
            "igst": igst, "cgst": cgst, "sgst": sgst,
            "reverse_charge": reverse_charge,
            "late_fee": late_fee,
            "tax_periods": tax_periods[:10],
        },
        "risks": risks,
    }


def _identify_gst_risks(text: str, amounts: list, gstr_type: str, itc_mismatch: float, late_fee: float) -> list:
    risks = []
    text_lower = text.lower()

    if itc_mismatch > 10:
        severity = "CRITICAL" if itc_mismatch > 20 else "HIGH"
        risks.append({"type": "ITC_MISMATCH", "severity": severity,
                       "detail": f"ITC mismatch of {itc_mismatch}% between claimed (3B) and eligible (2B). "
                                 f"Potential overclaim of input tax credit — common fraud indicator."})

    if "mismatch" in text_lower or "discrepancy" in text_lower:
        risks.append({"type": "DATA_MISMATCH", "severity": "HIGH", "detail": "Mismatch/discrepancy detected in GST filing"})
    if "nil return" in text_lower or "nil filing" in text_lower:
        risks.append({"type": "NIL_FILING", "severity": "MEDIUM", "detail": "Nil GST return — possible dormant period"})
    if late_fee and late_fee > 0:
        risks.append({"type": "LATE_FILING", "severity": "MEDIUM", "detail": f"Late fee of ₹{late_fee} — compliance issue"})
    if "reverse charge" in text_lower:
        risks.append({"type": "REVERSE_CHARGE", "severity": "LOW", "detail": "Reverse charge transactions present"})

    # Large variance in amounts
    if len(amounts) >= 2:
        max_amt = max(amounts)
        min_amt = min(a for a in amounts if a > 0) if any(a > 0 for a in amounts) else 1
        if max_amt / min_amt > 10:
            risks.append({"type": "AMOUNT_VARIANCE", "severity": "MEDIUM",
                           "detail": f"High variance in amounts: {min_amt} to {max_amt}"})
    return risks


# ─── Existing Parsers (kept for backward compat) ────────────────────────────

def parse_itr(text: str, file_path: str) -> Dict[str, Any]:
    """Parse Income Tax Returns."""
    amounts = _extract_amounts(text)
    pan_match = re.search(r'[A-Z]{5}\d{4}[A-Z]', text)
    pan = pan_match.group() if pan_match else "Not found"

    income_keywords = ["gross total income", "total income", "net income", "business income", "profit"]
    incomes = {}
    for kw in income_keywords:
        idx = text.lower().find(kw)
        if idx != -1:
            nearby_amounts = _extract_amounts(text[idx:idx + 150])
            if nearby_amounts:
                incomes[kw] = nearby_amounts[0]

    risks = []
    text_lower = text.lower()
    if "loss" in text_lower:
        risks.append({"type": "REPORTED_LOSS", "severity": "HIGH", "detail": "Business loss reported in ITR"})
    if "revised" in text_lower:
        risks.append({"type": "REVISED_RETURN", "severity": "MEDIUM", "detail": "Revised ITR filed"})

    return {
        "doc_type": "itr",
        "summary": f"ITR for PAN {pan}",
        "fields": {"pan": pan, "income_figures": incomes, "all_amounts": amounts[:20],
                    "assessment_years": re.findall(r'(?:AY|FY)\s*\d{4}[\-/]\d{2,4}', text, re.IGNORECASE)},
        "risks": risks,
    }


def parse_bank_statement(text: str, file_path: str) -> Dict[str, Any]:
    """Parse bank statements."""
    amounts = _extract_amounts(text)
    text_lower = text.lower()

    credit_total = _find_near_keyword(text, ["total credit", "credits total", "sum of credits"], _extract_amounts) or 0
    debit_total = _find_near_keyword(text, ["total debit", "debits total", "sum of debits"], _extract_amounts) or 0

    acc_match = re.search(r'(?:A/c|Account)\s*(?:No\.?|Number)?\s*:?\s*(\d{9,18})', text, re.IGNORECASE)
    account_no = acc_match.group(1) if acc_match else "Not found"

    bank_names = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "Punjab National", "Bank of Baroda", "Union Bank", "Canara", "IndusInd"]
    detected_bank = "Unknown"
    for bn in bank_names:
        if bn.lower() in text_lower:
            detected_bank = bn
            break

    bounce_count = len(re.findall(r'bounce|dishonour|return|unpaid', text, re.IGNORECASE))

    risks = []
    if bounce_count > 0:
        severity = "HIGH" if bounce_count > 3 else "MEDIUM"
        risks.append({"type": "CHEQUE_BOUNCES", "severity": severity, "detail": f"{bounce_count} bounced transactions"})
    if credit_total > 0 and debit_total > 0 and debit_total > credit_total * 1.2:
        risks.append({"type": "CASH_OUTFLOW", "severity": "MEDIUM", "detail": "Debits significantly exceed credits"})

    return {
        "doc_type": "bank_statement",
        "summary": f"Bank statement from {detected_bank}, Account: {account_no}",
        "fields": {"bank_name": detected_bank, "account_number": account_no,
                    "credit_total": credit_total, "debit_total": debit_total,
                    "bounce_count": bounce_count, "statement_period": _extract_dates(text)[:2],
                    "transaction_amounts": amounts[:30]},
        "risks": risks,
    }


def parse_financial_statement(text: str, file_path: str) -> Dict[str, Any]:
    """Parse standalone financial statements."""
    amounts = _extract_amounts(text)
    ratios = {}
    ratio_patterns = {
        "current_ratio": r"current\s+ratio\s*[:\-]?\s*([\d.]+)",
        "debt_equity": r"debt[\s\-/]+equity\s*[:\-]?\s*([\d.]+)",
        "pat_margin": r"(?:PAT|net\s+profit)\s*margin\s*[:\-]?\s*([\d.]+)\s*%?",
        "roe": r"(?:ROE|return\s+on\s+equity)\s*[:\-]?\s*([\d.]+)\s*%?",
        "interest_coverage": r"interest\s+coverage\s*[:\-]?\s*([\d.]+)",
    }
    for name, pat in ratio_patterns.items():
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            ratios[name] = float(match.group(1))

    return {
        "doc_type": "financial_statement",
        "summary": f"Financial statement with {len(ratios)} ratios extracted",
        "fields": {"ratios": ratios, "key_amounts": amounts[:20]},
        "risks": [],
    }


def parse_board_minutes(text: str, file_path: str) -> Dict[str, Any]:
    risks = []
    text_lower = text.lower()
    if "resignation" in text_lower:
        risks.append({"type": "DIRECTOR_RESIGNATION", "severity": "MEDIUM", "detail": "Director resignation mentioned"})
    if "loan" in text_lower and "approv" in text_lower:
        risks.append({"type": "NEW_BORROWING", "severity": "LOW", "detail": "New borrowing approval"})
    return {
        "doc_type": "board_minutes", "summary": "Board meeting minutes parsed",
        "fields": {"dates": _extract_dates(text), "amounts": _extract_amounts(text)[:10]},
        "risks": risks,
    }


def parse_rating_report(text: str, file_path: str) -> Dict[str, Any]:
    agencies = {"CRISIL": "CRISIL", "ICRA": "ICRA", "CARE": "CARE", "Brickwork": "Brickwork", "India Ratings": "India Ratings", "ACUITE": "Acuité"}
    detected_agency = "Unknown"
    for key, val in agencies.items():
        if key.lower() in text.lower():
            detected_agency = val
            break

    rating_match = re.search(r'([A-Z]{1,5}[\+\-]?\s*(?:\(.*?\))?)\s*(?:rating|assigned|reaffirmed)', text, re.IGNORECASE)
    rating = rating_match.group(1).strip() if rating_match else "Not found"
    outlook_match = re.search(r'outlook\s*[:\-]?\s*(stable|positive|negative|watch)', text, re.IGNORECASE)
    outlook = outlook_match.group(1).capitalize() if outlook_match else "Not specified"

    risks = []
    if "downgrad" in text.lower():
        risks.append({"type": "RATING_DOWNGRADE", "severity": "HIGH", "detail": "Rating downgrade mentioned"})
    if "negative" in outlook.lower() or "watch" in outlook.lower():
        risks.append({"type": "NEGATIVE_OUTLOOK", "severity": "MEDIUM", "detail": f"Rating outlook: {outlook}"})

    return {
        "doc_type": "rating_report",
        "summary": f"Rating by {detected_agency}: {rating} (Outlook: {outlook})",
        "fields": {"agency": detected_agency, "rating": rating, "outlook": outlook},
        "risks": risks,
    }


def parse_sanction_letter(text: str, file_path: str) -> Dict[str, Any]:
    amounts = _extract_amounts(text)
    return {
        "doc_type": "sanction_letter",
        "summary": f"Sanction letter with {len(amounts)} amount references",
        "fields": {"sanctioned_amounts": amounts[:10], "dates": _extract_dates(text)[:5]},
        "risks": [],
    }


def parse_legal_notice(text: str, file_path: str) -> Dict[str, Any]:
    amounts = _extract_amounts(text)
    risks = [{"type": "LEGAL_NOTICE", "severity": "HIGH", "detail": "Legal notice/dispute document present"}]
    if "winding up" in text.lower():
        risks.append({"type": "WINDING_UP", "severity": "CRITICAL", "detail": "Winding up petition mentioned"})
    if "nclt" in text.lower() or "tribunal" in text.lower():
        risks.append({"type": "TRIBUNAL_CASE", "severity": "HIGH", "detail": "NCLT/tribunal proceedings mentioned"})
    return {
        "doc_type": "legal_notice", "summary": "Legal notice/dispute document",
        "fields": {"amounts_at_stake": amounts[:10], "dates": _extract_dates(text)[:5]},
        "risks": risks,
    }


def parse_generic(text: str, file_path: str) -> Dict[str, Any]:
    return {
        "doc_type": "other",
        "summary": f"Document parsed ({len(text)} chars extracted)",
        "fields": {"amounts": _extract_amounts(text)[:20], "dates": _extract_dates(text)[:10]},
        "risks": [],
    }
