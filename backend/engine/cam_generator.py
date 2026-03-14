"""
CAM (Credit Appraisal Memo) Generator v2
Produces a professional PDF with robust handling of sparse data,
prominent research findings, and improved formatting.
"""
import os
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, Frame, PageTemplate,
    BaseDocTemplate, NextPageTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus.flowables import Flowable


# ── Colour palette ────────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#0f1b4c")
INDIGO    = colors.HexColor("#1a237e")
MID_BLUE  = colors.HexColor("#283593")
LIGHT_BG  = colors.HexColor("#f0f2f8")
WHITE     = colors.white
GREY_TEXT = colors.HexColor("#5f6368")
LIGHT_GREY = colors.HexColor("#e8eaed")
GREEN     = colors.HexColor("#1b7a3d")
GREEN_BG  = colors.HexColor("#e6f4ea")
AMBER     = colors.HexColor("#e37400")
AMBER_BG  = colors.HexColor("#fef7e0")
RED       = colors.HexColor("#c5221f")
RED_BG    = colors.HexColor("#fce8e6")
BLUE_ACC  = colors.HexColor("#1a73e8")
BLUE_BG   = colors.HexColor("#e8f0fe")
DARK_SURFACE = colors.HexColor("#37474f")
TEAL      = colors.HexColor("#00695c")
TEAL_BG   = colors.HexColor("#e0f2f1")


# ── Custom Flowables ──────────────────────────────────────────────────────────

class ScoreBar(Flowable):
    """Horizontal bar showing a score out of 100 with colour coding."""
    def __init__(self, score, width=200, height=12, label=""):
        Flowable.__init__(self)
        self.score = max(0, min(100, score or 0))
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor("#e0e0e0"))
        c.roundRect(0, 0, self.width, self.height, 3, fill=True, stroke=0)
        fill_w = self.width * (self.score / 100.0)
        fill_color = GREEN if self.score >= 60 else AMBER if self.score >= 40 else RED
        c.setFillColor(fill_color)
        c.roundRect(0, 0, max(fill_w, 6), self.height, 3, fill=True, stroke=0)
        c.setFillColor(WHITE if fill_w > 30 else colors.HexColor("#333"))
        c.setFont("Helvetica-Bold", 8)
        text_x = min(fill_w - 4, self.width - 20) if fill_w > 30 else fill_w + 4
        c.drawString(text_x, 2.5, f"{self.score:.0f}")


# ── Page callbacks ────────────────────────────────────────────────────────────

def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(INDIGO)
    canvas.setLineWidth(2)
    canvas.line(40, h - 35, w - 40, h - 35)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(INDIGO)
    canvas.drawString(42, h - 30, "INTELLI-CREDIT  |  AI Credit Decisioning Engine")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY_TEXT)
    canvas.drawRightString(w - 42, h - 30, "CONFIDENTIAL")
    canvas.setStrokeColor(LIGHT_GREY)
    canvas.setLineWidth(0.5)
    canvas.line(40, 40, w - 40, 40)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY_TEXT)
    canvas.drawString(42, 28, f"Generated {datetime.now().strftime('%d %b %Y')}")
    canvas.drawRightString(w - 42, 28, f"Page {doc.page}")
    canvas.restoreState()


def _title_page_template(canvas, doc):
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_crore(val, prefix="Rs."):
    """Format a value in crores with proper handling of None/0."""
    if val is None or val == "":
        return "N/A"
    try:
        v = float(val)
        if v == 0:
            return "N/A"
        return f"{prefix}{v:,.2f} Cr"
    except (ValueError, TypeError):
        return "N/A"


def _fmt_pct(val, suffix="%"):
    if val is None or val == "":
        return "N/A"
    try:
        v = float(val)
        return f"{v:.2f}{suffix}"
    except (ValueError, TypeError):
        return "N/A"


def _fmt_ratio(val, suffix="x"):
    if val is None or val == "":
        return "N/A"
    try:
        v = float(val)
        if v == 0:
            return "N/A"
        return f"{v:.2f}{suffix}"
    except (ValueError, TypeError):
        return "N/A"


def _safe(val, default="N/A"):
    if val is None or val == "" or val == 0:
        return default
    return str(val)


def _sanitize_pdf_text(value):
    """Recursively sanitize text values for PDF-safe rendering."""
    if isinstance(value, str):
        return value.replace("₹", "Rs.")
    if isinstance(value, list):
        return [_sanitize_pdf_text(item) for item in value]
    if isinstance(value, dict):
        return {k: _sanitize_pdf_text(v) for k, v in value.items()}
    return value


# ── Main Generator ────────────────────────────────────────────────────────────

class CAMGenerator:
    """Generate professional Credit Appraisal Memo as PDF."""

    def generate(self, application: Dict[str, Any], output_dir: str) -> str:
        application = _sanitize_pdf_text(application)
        app_id = application.get("id", "unknown")
        company = application.get("company_name", "Unknown Company")
        safe_name = company.replace(" ", "_").replace("/", "_")[:50]
        output_path = os.path.join(output_dir, f"CAM_{app_id}_{safe_name}.pdf")

        doc = BaseDocTemplate(
            output_path, pagesize=A4,
            rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=55,
        )
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        doc.addPageTemplates([
            PageTemplate(id='TitlePage', frames=frame, onPage=_title_page_template),
            PageTemplate(id='ContentPage', frames=frame, onPage=_header_footer),
        ])

        styles = getSampleStyleSheet()
        self._register_styles(styles)

        story = []

        # Title page
        story.extend(self._build_title_page(application, styles))
        story.append(NextPageTemplate('ContentPage'))
        story.append(PageBreak())

        # S1: Executive Summary
        story.extend(self._section_executive_summary(application, styles))
        story.append(Spacer(1, 14))

        # S2: Company Financial Profile (NEW — from research data)
        story.extend(self._section_financial_profile(application, styles))
        story.append(PageBreak())

        # S3: Five Cs
        story.extend(self._section_five_cs(application, styles))
        story.append(PageBreak())

        # S4: ML Assessment
        story.extend(self._section_ml_assessment(application, styles))
        story.append(Spacer(1, 14))

        # S5: SWOT
        story.extend(self._section_swot(application, styles))
        story.append(PageBreak())

        # S6: Loan Structure
        story.extend(self._section_loan_structure(application, styles))
        story.append(Spacer(1, 14))

        # S7: Data Triangulation
        story.extend(self._section_triangulation(application, styles))
        story.append(PageBreak())

        # S8: Research Findings (expanded)
        story.extend(self._section_research(application, styles))
        story.append(Spacer(1, 14))

        # S9: Document Analysis
        story.extend(self._section_documents(application, styles))
        story.append(Spacer(1, 14))

        # S10: Risk Matrix
        story.extend(self._section_risk_matrix(application, styles))
        story.append(PageBreak())

        # S11: Recommendation
        story.extend(self._section_recommendation(application, styles))

        # Disclaimer
        story.extend(self._build_disclaimer(styles))

        doc.build(story)
        return output_path

    # ══════════════════════════════════════════════════════════════════════
    #  STYLES
    # ══════════════════════════════════════════════════════════════════════

    def _register_styles(self, s):
        s.add(ParagraphStyle('CoverTitle', fontName='Helvetica-Bold', fontSize=28, leading=34,
                             textColor=WHITE, alignment=TA_LEFT, spaceAfter=6))
        s.add(ParagraphStyle('CoverSubtitle', fontName='Helvetica', fontSize=13, leading=18,
                             textColor=colors.HexColor("#c5cae9"), alignment=TA_LEFT, spaceAfter=4))
        s.add(ParagraphStyle('CoverMeta', fontName='Helvetica', fontSize=10, leading=14,
                             textColor=GREY_TEXT, alignment=TA_LEFT, spaceAfter=3))
        s.add(ParagraphStyle('SectionNum', fontName='Helvetica-Bold', fontSize=10,
                             textColor=INDIGO, spaceAfter=0))
        s.add(ParagraphStyle('SectionTitle', fontName='Helvetica-Bold', fontSize=15, leading=20,
                             textColor=NAVY, spaceBefore=14, spaceAfter=8))
        s.add(ParagraphStyle('SubHead', fontName='Helvetica-Bold', fontSize=11, leading=15,
                             textColor=MID_BLUE, spaceBefore=10, spaceAfter=4))
        s.add(ParagraphStyle('Body', fontName='Helvetica', fontSize=9.5, leading=14,
                             textColor=colors.HexColor("#202124"), alignment=TA_JUSTIFY, spaceAfter=5))
        s.add(ParagraphStyle('BodyBold', fontName='Helvetica-Bold', fontSize=9.5, leading=14,
                             textColor=colors.HexColor("#202124"), spaceAfter=5))
        s.add(ParagraphStyle('BulletItem', fontName='Helvetica', fontSize=9.5, leading=13,
                             textColor=colors.HexColor("#202124"), leftIndent=14, bulletIndent=0, spaceAfter=3))
        s.add(ParagraphStyle('SmallGrey', fontName='Helvetica', fontSize=7.5, leading=10,
                             textColor=GREY_TEXT, alignment=TA_CENTER, spaceAfter=3))
        s.add(ParagraphStyle('DecisionBig', fontName='Helvetica-Bold', fontSize=20, leading=26,
                             alignment=TA_CENTER, spaceAfter=10, spaceBefore=10))
        s.add(ParagraphStyle('KPIValue', fontName='Helvetica-Bold', fontSize=22, leading=26, alignment=TA_CENTER))
        s.add(ParagraphStyle('KPILabel', fontName='Helvetica', fontSize=8, leading=11,
                             textColor=GREY_TEXT, alignment=TA_CENTER))
        s.add(ParagraphStyle('DataSource', fontName='Helvetica-Oblique', fontSize=7.5, leading=10,
                             textColor=BLUE_ACC, spaceAfter=2))

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _section_heading(self, number, title, styles):
        return [
            Paragraph(f"SECTION {number}", styles['SectionNum']),
            Paragraph(title, styles['SectionTitle']),
            HRFlowable(width="100%", color=INDIGO, thickness=1.5, spaceAfter=8),
        ]

    @staticmethod
    def _make_table(data, col_widths, header_bg=INDIGO, font_size=9, row_alt=True):
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ('BACKGROUND',    (0, 0), (-1, 0), header_bg),
            ('TEXTCOLOR',     (0, 0), (-1, 0), WHITE),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 0), (-1, -1), font_size),
            ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING',    (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('GRID',          (0, 0), (-1, 0), 0.5, header_bg),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, header_bg),
            ('LINEBELOW',     (0, -1), (-1, -1), 0.5, LIGHT_GREY),
            ('LINEBEFORE',    (0, 1), (0, -1), 0.5, LIGHT_GREY),
            ('LINEAFTER',     (-1, 1), (-1, -1), 0.5, LIGHT_GREY),
        ]
        if row_alt and len(data) > 2:
            style_cmds.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor("#f8f9fc")]))
        for i in range(1, len(data)):
            style_cmds.append(('LINEBELOW', (0, i), (-1, i), 0.25, LIGHT_GREY))
        t.setStyle(TableStyle(style_cmds))
        return t

    @staticmethod
    def _kpi_cell(value, label, accent=INDIGO, bg=LIGHT_BG):
        accent_hex = accent.hexval() if hasattr(accent, 'hexval') else str(accent)
        inner = Table(
            [[Paragraph(f"<font color='{accent_hex}'>{value}</font>",
                        ParagraphStyle('_kv', fontName='Helvetica-Bold', fontSize=20, alignment=TA_CENTER, leading=24))],
             [Paragraph(label, ParagraphStyle('_kl', fontName='Helvetica', fontSize=8, alignment=TA_CENTER,
                                              textColor=GREY_TEXT, leading=11))]],
            colWidths=[130], rowHeights=[30, 16]
        )
        inner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 6),
        ]))
        return inner

    def _severity_color(self, sev):
        sev = (sev or "").upper()
        if sev in ("CRITICAL", "HIGH"):
            return RED
        if sev == "MEDIUM":
            return AMBER
        return GREEN

    # ══════════════════════════════════════════════════════════════════════
    #  TITLE PAGE
    # ══════════════════════════════════════════════════════════════════════

    def _build_title_page(self, app, styles):
        elements = []
        page_w = A4[0] - 100

        elements.append(Spacer(1, 60))

        banner_data = [
            [Paragraph("CREDIT APPRAISAL<br/>MEMORANDUM", styles['CoverTitle'])],
            [Paragraph(app.get("company_name", "Unknown Company"), styles['CoverSubtitle'])],
            [Paragraph(
                f"{app.get('industry', '')}  {'  |  CIN: ' + app.get('cin', '') if app.get('cin') else ''}",
                styles['CoverSubtitle']
            )],
        ]
        banner = Table(banner_data, colWidths=[page_w - 30])
        banner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('LEFTPADDING', (0, 0), (-1, -1), 24),
            ('RIGHTPADDING', (0, 0), (-1, -1), 24),
            ('TOPPADDING', (0, 0), (0, 0), 30),
            ('BOTTOMPADDING', (0, -1), (0, -1), 24),
        ]))
        elements.append(banner)
        elements.append(Spacer(1, 30))

        # Meta info
        loan_amt = app.get("loan_amount_requested", 0)
        meta_rows = [
            ["Application ID",  str(app.get("id", "N/A"))],
            ["Loan Type",       str(app.get("loan_type", "N/A")).replace("_", " ").title()],
            ["Amount Requested", f"INR {loan_amt:,.2f} Cr" if loan_amt else "N/A"],
            ["Purpose",         _safe(app.get("loan_purpose"))],
            ["Incorporation",   _safe(app.get("incorporation_year"))],
            ["Promoter(s)",     _safe(app.get("promoter_names"))],
            ["Report Date",     datetime.now().strftime("%d %B %Y")],
        ]

        # Add credit rating if available from research
        fin = app.get("research", {}).get("extracted_financials", {})
        if fin.get("credit_rating"):
            meta_rows.insert(3, ["Credit Rating", str(fin["credit_rating"]) + (f" ({fin.get('rating_outlook', '')})" if fin.get('rating_outlook') else "")])

        meta = Table(meta_rows, colWidths=[140, page_w - 170])
        meta.setStyle(TableStyle([
            ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',  (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE',  (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), GREY_TEXT),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor("#202124")),
            ('ALIGN',     (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN',     (1, 0), (1, -1), 'LEFT'),
            ('VALIGN',    (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, -2), 0.25, LIGHT_GREY),
        ]))
        elements.append(meta)
        elements.append(Spacer(1, 60))

        elements.append(HRFlowable(width="60%", color=INDIGO, thickness=1))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(
            "Generated by <b>Intelli-Credit</b>  —  AI-Powered Credit Decisioning Engine", styles['SmallGrey']))
        elements.append(Paragraph("CONFIDENTIAL  |  For Authorised Internal Use Only", styles['SmallGrey']))
        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S1 – EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════

    def _section_executive_summary(self, app, styles):
        elements = self._section_heading(1, "Executive Summary", styles)

        risk = app.get("risk_score", {})
        ml = risk.get("ml_prediction", {})
        altman = risk.get("altman_z", {})
        rec = risk.get("recommendation", {})
        ls = risk.get("loan_structure", {})
        fin = app.get("research", {}).get("extracted_financials", {})

        decision = (rec.get("decision") or "PENDING").replace("_", " ")
        rating = ml.get("rating") or fin.get("credit_rating") or "N/A"
        pd_pct = ml.get("pd_percent") or 0
        z_score = altman.get("z_score") or 0
        z_zone = altman.get("zone") or "N/A"

        # KPI cards
        kpi_data = [[
            self._kpi_cell(str(rating), "Credit Rating", INDIGO, LIGHT_BG),
            self._kpi_cell(f"{pd_pct:.2f}%", "Probability of Default",
                           RED if pd_pct > 5 else AMBER if pd_pct > 2 else GREEN,
                           RED_BG if pd_pct > 5 else AMBER_BG if pd_pct > 2 else GREEN_BG),
            self._kpi_cell(f"{z_score:.2f}", f"Altman Z'' ({z_zone})",
                           GREEN if z_zone == "SAFE" else AMBER if z_zone == "GREY" else RED,
                           GREEN_BG if z_zone == "SAFE" else AMBER_BG if z_zone == "GREY" else RED_BG),
        ]]
        kpi_table = Table(kpi_data, colWidths=[165, 165, 165])
        kpi_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 12))

        # Decision banner
        dec_color = {"APPROVE": GREEN, "APPROVE WITH CONDITIONS": AMBER,
                     "APPROVE REDUCED": AMBER, "REFER TO COMMITTEE": RED, "REJECT": RED}.get(decision, GREY_TEXT)
        dec_bg = {"APPROVE": GREEN_BG, "APPROVE WITH CONDITIONS": AMBER_BG,
                  "APPROVE REDUCED": AMBER_BG, "REFER TO COMMITTEE": RED_BG, "REJECT": RED_BG}.get(decision, LIGHT_BG)
        dec_hex = dec_color.hexval() if hasattr(dec_color, 'hexval') else str(dec_color)
        dec_table = Table(
            [[Paragraph(f"<font color='{dec_hex}'>{decision}</font>", styles['DecisionBig'])]],
            colWidths=[495]
        )
        dec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), dec_bg),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(dec_table)
        elements.append(Spacer(1, 10))

        # Explanation
        explanation = rec.get("explanation", "")
        if explanation:
            elements.append(Paragraph(explanation, styles['Body']))

        # Research-based summary if available
        research_summary = app.get("research", {}).get("research_summary", "")
        if research_summary and len(research_summary) > 50:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("<b>AI Research Assessment:</b>", styles['Body']))
            # Truncate very long summaries
            summary_text = research_summary[:800] + ("..." if len(research_summary) > 800 else "")
            elements.append(Paragraph(summary_text, styles['Body']))

        # Loan terms
        amt = rec.get("suggested_loan_amount") or ls.get("recommended_amount_cr") or 0
        rate = rec.get("interest_rate_pct") or ls.get("interest_rate_pct") or 0
        tenure = rec.get("recommended_tenure_years") or ls.get("tenure_years") or 0
        if amt:
            terms = Table(
                [["Recommended Amount", "Interest Rate", "Tenure"],
                 [_fmt_crore(amt, "INR "), _fmt_pct(rate), f"{tenure} yrs" if tenure else "N/A"]],
                colWidths=[165, 165, 165]
            )
            terms.setStyle(TableStyle([
                ('FONTNAME',  (0, 0), (-1, 0), 'Helvetica'),
                ('FONTNAME',  (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE',  (0, 0), (-1, 0), 8),
                ('FONTSIZE',  (0, 1), (-1, 1), 12),
                ('TEXTCOLOR', (0, 0), (-1, 0), GREY_TEXT),
                ('TEXTCOLOR', (0, 1), (-1, 1), NAVY),
                ('ALIGN',     (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(Spacer(1, 8))
            elements.append(terms)

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S2 – COMPANY FINANCIAL PROFILE (NEW)
    # ══════════════════════════════════════════════════════════════════════

    def _section_financial_profile(self, app, styles):
        elements = self._section_heading(2, "Company Financial Profile", styles)

        fin = app.get("research", {}).get("extracted_financials", {})
        features = app.get("risk_score", {}).get("ml_prediction", {}).get("features_used", {})

        if not fin and not features:
            elements.append(Paragraph("Financial profile data not available. No documents or web data could be analyzed.", styles['Body']))
            return elements

        method = fin.get("extraction_method", "N/A")
        source_label = "AI Web Analysis" if method == "llm" else "Pattern Matching" if method == "regex" else "Document Analysis"
        elements.append(Paragraph(f"<i>Data Source: {source_label}</i>", styles['DataSource']))
        elements.append(Spacer(1, 4))

        # Key metrics table — combine research + features
        def _best(research_key, feature_key=None):
            """Get the best available value from research or features."""
            val = fin.get(research_key)
            if val is not None:
                return val
            if feature_key and features.get(feature_key):
                return features[feature_key]
            return None

        # ── Income & Profitability ──
        elements.append(Paragraph("2.1  Income &amp; Profitability", styles['SubHead']))
        income_data = [
            ["Metric", "Value", "Assessment"],
            ["Revenue from Operations", _fmt_crore(_best("revenue_cr", "revenue_cr")),
             self._assess_revenue(_best("revenue_cr", "revenue_cr"))],
            ["EBITDA", _fmt_crore(_best("ebitda_cr")),
             f"Margin: {_fmt_pct(_best('ebitda_margin_pct'))}" if _best("ebitda_margin_pct") else "N/A"],
            ["Profit After Tax (PAT)", _fmt_crore(_best("pat_cr", "pat_cr")),
             f"Margin: {_fmt_pct(_best('pat_margin_pct', 'pat_margin_pct'))}" if _best("pat_margin_pct", "pat_margin_pct") else "N/A"],
            ["Return on Equity", _fmt_pct(_best("roe_pct", "roe_pct")),
             self._assess_roe(_best("roe_pct", "roe_pct"))],
            ["Revenue Growth", _fmt_pct(_best("revenue_growth_pct")),
             self._assess_growth(_best("revenue_growth_pct"))],
        ]
        elements.append(self._make_table(income_data, [160, 140, 190], header_bg=TEAL))
        elements.append(Spacer(1, 10))

        # ── Balance Sheet & Leverage ──
        elements.append(Paragraph("2.2  Balance Sheet &amp; Leverage", styles['SubHead']))
        bs_data = [
            ["Metric", "Value", "Assessment"],
            ["Total Assets", _fmt_crore(_best("total_assets_cr")), ""],
            ["Net Worth / Equity", _fmt_crore(_best("total_equity_cr")), ""],
            ["Total Debt", _fmt_crore(_best("total_debt_cr", "total_debt_cr")), ""],
            ["D/E Ratio", _fmt_ratio(_best("de_ratio", "de_ratio")),
             self._assess_de(_best("de_ratio", "de_ratio"))],
            ["Current Ratio", _fmt_ratio(_best("current_ratio", "current_ratio"), ""),
             self._assess_cr(_best("current_ratio", "current_ratio"))],
            ["Interest Coverage Ratio", _fmt_ratio(_best("icr", "icr"), "x"),
             self._assess_icr(_best("icr", "icr"))],
        ]
        elements.append(self._make_table(bs_data, [160, 140, 190], header_bg=TEAL))
        elements.append(Spacer(1, 10))

        # ── Asset Quality & Collections (for NBFCs/Banks) ──
        if _best("gnpa_pct", "gnpa_pct") or _best("collection_eff_pct", "collection_eff_pct") or _best("aum_cr"):
            elements.append(Paragraph("2.3  Asset Quality &amp; Portfolio", styles['SubHead']))
            aq_data = [
                ["Metric", "Value", "Assessment"],
                ["Gross NPA", _fmt_pct(_best("gnpa_pct", "gnpa_pct")),
                 self._assess_gnpa(_best("gnpa_pct", "gnpa_pct"))],
                ["Net NPA", _fmt_pct(_best("nnpa_pct")), ""],
                ["Collection Efficiency", _fmt_pct(_best("collection_eff_pct", "collection_eff_pct")),
                 self._assess_collection(_best("collection_eff_pct", "collection_eff_pct"))],
                ["AUM", _fmt_crore(_best("aum_cr")), ""],
            ]
            elements.append(self._make_table(aq_data, [160, 140, 190], header_bg=TEAL))
            elements.append(Spacer(1, 10))

        # ── Market & Governance ──
        elements.append(Paragraph("2.4  Market &amp; Governance", styles['SubHead']))
        gov_data = [
            ["Metric", "Value", "Assessment"],
            ["Promoter Holding", _fmt_pct(_best("promoter_holding_pct", "promoter_holding_pct")),
             self._assess_promoter(_best("promoter_holding_pct", "promoter_holding_pct"))],
            ["Pledged Shares", _fmt_pct(_best("pledged_pct", "pledged_pct")),
             self._assess_pledge(_best("pledged_pct", "pledged_pct"))],
            ["Market Capitalization", _fmt_crore(_best("market_cap_cr")), ""],
            ["Credit Rating", _safe(fin.get("credit_rating")), _safe(fin.get("rating_outlook"))],
        ]
        elements.append(self._make_table(gov_data, [160, 140, 190], header_bg=TEAL))

        # Key strengths and concerns from LLM extraction
        strengths = fin.get("key_strengths", [])
        concerns = fin.get("key_concerns", [])
        if strengths or concerns:
            elements.append(Spacer(1, 10))
            if strengths:
                green_hex = GREEN.hexval() if hasattr(GREEN, 'hexval') else str(GREEN)
                elements.append(Paragraph(f"<font color='{green_hex}'><b>Key Strengths (from Research):</b></font>", styles['Body']))
                for s in strengths[:5]:
                    elements.append(Paragraph(f"<bullet>&bull;</bullet> {s}", styles['BulletItem']))
            if concerns:
                red_hex = RED.hexval() if hasattr(RED, 'hexval') else str(RED)
                elements.append(Paragraph(f"<font color='{red_hex}'><b>Key Concerns (from Research):</b></font>", styles['Body']))
                for c in concerns[:4]:
                    elements.append(Paragraph(f"<bullet>&bull;</bullet> {c}", styles['BulletItem']))

        return elements

    # Assessment helpers
    def _assess_revenue(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 5000: return "Large Enterprise"
            if v > 1000: return "Mid-Large Enterprise"
            if v > 100: return "Mid Enterprise"
            return "Small Enterprise"
        except: return ""

    def _assess_roe(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 15: return "Strong"
            if v > 10: return "Adequate"
            if v > 0: return "Below average"
            return "Negative — Loss-making"
        except: return ""

    def _assess_growth(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 20: return "High growth"
            if v > 10: return "Healthy growth"
            if v > 0: return "Modest growth"
            return "Declining"
        except: return ""

    def _assess_de(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v < 1: return "Conservative leverage"
            if v < 2: return "Moderate leverage"
            if v < 4: return "Acceptable for NBFC/infra"
            return "High leverage — monitor"
        except: return ""

    def _assess_cr(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 2: return "Strong liquidity"
            if v > 1.2: return "Adequate"
            if v > 1: return "Tight liquidity"
            return "Liquidity stress"
        except: return ""

    def _assess_icr(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 3: return "Comfortable debt servicing"
            if v > 1.5: return "Adequate"
            if v > 1: return "Marginal"
            return "Debt servicing stress"
        except: return ""

    def _assess_gnpa(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v < 2: return "Good asset quality"
            if v < 4: return "Moderate"
            if v < 6: return "Elevated"
            return "High — concern"
        except: return ""

    def _assess_collection(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 98: return "Excellent"
            if v > 95: return "Good"
            if v > 90: return "Adequate"
            return "Below industry norm"
        except: return ""

    def _assess_promoter(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v > 70: return "High promoter control"
            if v > 50: return "Majority control"
            if v > 25: return "Significant minority"
            return "Low — governance risk"
        except: return ""

    def _assess_pledge(self, v):
        if v is None: return ""
        try:
            v = float(v)
            if v == 0: return "No pledge — positive"
            if v < 20: return "Low pledge"
            if v < 50: return "Elevated — monitor"
            return "High — significant risk"
        except: return ""

    # ══════════════════════════════════════════════════════════════════════
    #  S3 – FIVE Cs
    # ══════════════════════════════════════════════════════════════════════

    def _section_five_cs(self, app, styles):
        elements = self._section_heading(3, "Five Cs of Credit Analysis", styles)

        five_cs = app.get("risk_score", {}).get("five_cs", {})
        overall_score = app.get("risk_score", {}).get("overall_score", 0)
        if not five_cs:
            elements.append(Paragraph("Five Cs analysis not available.", styles['Body']))
            return elements

        # Summary table of all Five Cs scores
        summary_data = [["Credit Dimension", "Weight", "Score", "Assessment"]]
        for c_name, c_data in five_cs.items():
            display = c_name.replace("_", " ").capitalize()
            score = c_data.get("score") or 0
            weight = c_data.get("weight") or 0
            assessment = self._score_assessment_text(score)
            summary_data.append([display, f"{weight*100:.0f}%", f"{score:.0f}/100", assessment])
        summary_data.append(["Weighted Total", "100%", f"{overall_score:.1f}/100", self._score_assessment_text(overall_score)])
        summary_tbl = self._make_table(summary_data, [120, 60, 65, 245], header_bg=INDIGO)
        # Bold the last row
        last_row = len(summary_data) - 1
        summary_tbl.setStyle(TableStyle([
            ('FONTNAME', (0, last_row), (-1, last_row), 'Helvetica-Bold'),
            ('BACKGROUND', (0, last_row), (-1, last_row), LIGHT_BG),
            ('LINEABOVE', (0, last_row), (-1, last_row), 1, INDIGO),
        ]))
        elements.append(summary_tbl)
        elements.append(Spacer(1, 14))

        # Detailed breakdown per C
        for idx, (c_name, c_data) in enumerate(five_cs.items(), 1):
            display = c_name.replace("_", " ").capitalize()
            score = c_data.get("score") or 0
            weight = c_data.get("weight") or 0
            reasons = c_data.get("reasons", [])
            risks = c_data.get("risks", [])

            grey_hex = GREY_TEXT.hexval() if hasattr(GREY_TEXT, 'hexval') else str(GREY_TEXT)
            score_clr = GREEN if score >= 70 else AMBER if score >= 40 else RED
            score_hex = score_clr.hexval() if hasattr(score_clr, 'hexval') else str(score_clr)
            elements.append(Paragraph(
                f"3.{idx}  {display}  "
                f"<font size='8' color='{grey_hex}'>(Weight {weight*100:.0f}%)</font>  "
                f"<font size='10' color='{score_hex}'><b>{score:.0f}/100</b></font>",
                styles['SubHead']
            ))
            elements.append(ScoreBar(score, width=360, height=14))
            elements.append(Spacer(1, 4))

            # Justification: why this score
            if reasons:
                elements.append(Paragraph("<b>Scoring Rationale:</b>", styles['Body']))
                for r in reasons:
                    elements.append(Paragraph(f"<bullet>&bull;</bullet> {r}", styles['BulletItem']))
            else:
                elements.append(Paragraph(
                    f"<i>Score based on default baseline assessment. No specific positive or negative signals detected for {display.lower()}.</i>",
                    styles['Body']
                ))

            if risks:
                elements.append(Spacer(1, 3))
                elements.append(Paragraph("<b>Identified Risks:</b>", styles['Body']))
                for rk in risks:
                    sev = rk.get("severity", "LOW")
                    clr = self._severity_color(sev)
                    clr_hex = clr.hexval() if hasattr(clr, 'hexval') else str(clr)
                    elements.append(Paragraph(
                        f"<bullet>&bull;</bullet> <font color='{clr_hex}'>[{sev}]</font> {rk.get('detail', '')}",
                        styles['BulletItem']
                    ))
            elements.append(Spacer(1, 8))

        return elements

    def _score_assessment_text(self, score):
        """Return a human-readable assessment for a 0-100 score."""
        if score >= 80: return "Excellent — strong credit profile"
        if score >= 70: return "Good — above average creditworthiness"
        if score >= 60: return "Adequate — acceptable with monitoring"
        if score >= 50: return "Fair — requires closer review"
        if score >= 40: return "Below Average — elevated risk"
        if score >= 25: return "Weak — significant concerns"
        return "Poor — high risk of default"

    # ══════════════════════════════════════════════════════════════════════
    #  S4 – ML ASSESSMENT
    # ══════════════════════════════════════════════════════════════════════

    def _section_ml_assessment(self, app, styles):
        elements = self._section_heading(4, "ML-Based Credit Assessment", styles)

        risk = app.get("risk_score", {})
        ml = risk.get("ml_prediction", {})
        altman = risk.get("altman_z", {})

        if not ml and not altman:
            elements.append(Paragraph("ML assessment data not available.", styles['Body']))
            return elements

        if ml:
            elements.append(Paragraph("4.1  Probability of Default Model", styles['SubHead']))

            # Show data source info
            doc_feats = ml.get("document_features_count", 0)
            res_feats = ml.get("research_features_count", 0)
            if res_feats > 0:
                elements.append(Paragraph(
                    f"<i>Features: {doc_feats} from documents, {res_feats} from web research</i>",
                    styles['DataSource']
                ))

            pd_data = [
                ["Metric", "Value"],
                ["PD (%)", _fmt_pct(ml.get('pd_percent'), '%')],
                ["Credit Rating", _safe(ml.get("rating"))],
                ["Model", (ml.get("model_type") or ml.get("method", "calibrated_rule_based")).replace("_", " ").title()],
            ]
            elements.append(self._make_table(pd_data, [220, 270], header_bg=MID_BLUE))
            elements.append(Spacer(1, 8))

            # Top risk factors
            factors = ml.get("top_factors", [])
            adjustments = ml.get("adjustments", [])
            items = factors if factors else adjustments
            if items:
                elements.append(Paragraph("<b>Key Risk Drivers</b>", styles['Body']))
                fac_data = [["Factor", "Direction", "Detail"]]
                for f in items[:10]:
                    if isinstance(f, dict):
                        feature = (f.get("feature") or f.get("name", "")).replace("_", " ").title()
                        impact = f.get("impact", 0)
                        detail = f.get("detail", "")
                        d = "positive" if impact < 0 else "negative" if impact > 0 else "neutral"
                        clr = GREEN if d == "positive" else RED
                        clr_hex = clr.hexval() if hasattr(clr, 'hexval') else str(clr)
                        arrow = "▼ Risk" if d == "positive" else "▲ Risk"
                        fac_data.append([
                            feature,
                            Paragraph(f"<font color='{clr_hex}'>{arrow}</font>",
                                      ParagraphStyle('_d', alignment=TA_CENTER, fontSize=8, fontName='Helvetica-Bold')),
                            detail[:80] if detail else f"Impact: {impact:.4f}",
                        ])
                if len(fac_data) > 1:
                    elements.append(self._make_table(fac_data, [130, 70, 290], header_bg=DARK_SURFACE, font_size=8))
                elements.append(Spacer(1, 10))

        # Altman Z''
        if altman:
            elements.append(Paragraph("4.2  Altman Z''-Score (Emerging Markets Variant)", styles['SubHead']))
            z = altman.get("z_score") or 0
            zone = altman.get("zone") or "N/A"
            zone_clr = GREEN if zone == "SAFE" else AMBER if zone == "GREY" else RED
            zone_bg = GREEN_BG if zone == "SAFE" else AMBER_BG if zone == "GREY" else RED_BG
            zone_hex = zone_clr.hexval() if hasattr(zone_clr, 'hexval') else str(zone_clr)

            z_banner = Table(
                [[Paragraph(f"Z'' = <b>{z:.2f}</b>",
                            ParagraphStyle('_z', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER)),
                  Paragraph(f"<font color='{zone_hex}'><b>{zone} ZONE</b></font>",
                            ParagraphStyle('_zz', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER))]],
                colWidths=[245, 245]
            )
            z_banner.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), LIGHT_BG),
                ('BACKGROUND', (1, 0), (1, 0), zone_bg),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(z_banner)
            elements.append(Spacer(1, 6))

            comps = altman.get("components", {})
            if comps:
                desc_map = {"x1": "Working Capital / Total Assets", "x2": "Retained Earnings / Total Assets",
                            "x3": "EBIT / Total Assets", "x4": "Book Equity / Total Liabilities"}
                coeff_map = {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05}
                comp_data = [["Component", "Description", "Value", "Coeff", "Contribution"]]
                for k, v in comps.items():
                    v = v or 0
                    coeff = coeff_map.get(k, 0)
                    comp_data.append([k.upper(), desc_map.get(k, k), f"{v:.4f}", f"{coeff}", f"{v * coeff:.4f}"])
                elements.append(self._make_table(comp_data, [55, 200, 65, 55, 80], header_bg=DARK_SURFACE, font_size=8))

            elements.append(Spacer(1, 3))
            elements.append(Paragraph(
                "Z'' &gt; 2.60 = Safe  |  1.10 &lt; Z'' &lt; 2.60 = Grey  |  Z'' &lt; 1.10 = Distress",
                styles['SmallGrey']))

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S5 – SWOT
    # ══════════════════════════════════════════════════════════════════════

    def _section_swot(self, app, styles):
        elements = self._section_heading(5, "SWOT Analysis", styles)

        swot = app.get("swot", {})
        if not swot:
            elements.append(Paragraph("SWOT analysis not performed.", styles['Body']))
            return elements

        # Show generation method
        gen_method = swot.get("generation_method", "")
        if gen_method:
            label = "AI-Generated" if gen_method == "llm" else "Rule-Based"
            elements.append(Paragraph(f"<i>Analysis Method: {label}</i>", styles['DataSource']))
            elements.append(Spacer(1, 4))

        quad_cfg = [
            ("strengths",     "Strengths",     GREEN,    GREEN_BG),
            ("weaknesses",    "Weaknesses",    AMBER,    AMBER_BG),
            ("opportunities", "Opportunities", BLUE_ACC, BLUE_BG),
            ("threats",       "Threats",       RED,      RED_BG),
        ]

        cells = []
        for key, label, accent, bg in quad_cfg:
            items = swot.get(key, [])
            accent_hex = accent.hexval() if hasattr(accent, 'hexval') else str(accent)

            # Handle both formats: list of strings or list of dicts
            bullets = []
            for item in items:
                if isinstance(item, dict):
                    point = item.get("point", "")
                    detail = item.get("detail", "")
                    impact = item.get("impact", "")
                    if detail:
                        bullets.append(f"&#8226; <b>{point}</b>: {detail}")
                    else:
                        bullets.append(f"&#8226; {point}")
                else:
                    bullets.append(f"&#8226; {item}")

            bullet_text = "<br/>".join(bullets) if bullets else "<i>None identified</i>"
            cell_content = [
                [Paragraph(f"<font color='{accent_hex}'><b>{label.upper()}</b></font>",
                           ParagraphStyle('_sw', fontSize=10, fontName='Helvetica-Bold', leading=14))],
                [Paragraph(bullet_text,
                           ParagraphStyle('_sb', fontSize=8.5, leading=12, textColor=colors.HexColor("#333")))],
            ]
            cell_table = Table(cell_content, colWidths=[230])
            cell_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (0, 0), 8),
                ('BOTTOMPADDING', (0, -1), (0, -1), 8),
                ('LINEABOVE', (0, 0), (-1, 0), 3, accent),
            ]))
            cells.append(cell_table)

        grid = Table([[cells[0], cells[1]], [cells[2], cells[3]]], colWidths=[245, 245])
        grid.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(grid)

        # Overall assessment
        assessment = swot.get("overall_assessment", "")
        if assessment:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"<b>Overall Assessment:</b> {assessment}", styles['Body']))

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S6 – LOAN STRUCTURE
    # ══════════════════════════════════════════════════════════════════════

    def _section_loan_structure(self, app, styles):
        elements = self._section_heading(6, "Loan Structure & Covenants", styles)

        risk = app.get("risk_score", {})
        ls = risk.get("loan_structure", {})
        rec = risk.get("recommendation", {})

        if not ls and not rec:
            elements.append(Paragraph("Loan structuring not completed.", styles['Body']))
            return elements

        params = [
            ["Parameter", "Value"],
            ["Recommended Amount", _fmt_crore(ls.get('recommended_amount_cr') or rec.get('suggested_loan_amount'), "INR ")],
            ["Interest Rate", _fmt_pct(ls.get('interest_rate_pct') or rec.get('interest_rate_pct'))],
            ["Tenure", f"{ls.get('tenure_years') or rec.get('recommended_tenure_years') or 'N/A'} years"],
            ["Constraining Method", (ls.get("constraining_method") or "N/A").replace("_", " ").title()],
        ]
        if ls.get("emi_cr"):
            params.append(["EMI (Monthly)", _fmt_crore(ls['emi_cr'], "INR ")])
        elements.append(self._make_table(params, [200, 290], header_bg=colors.HexColor("#1b5e20")))
        elements.append(Spacer(1, 12))

        # Method breakdown
        methods = ls.get("methods", {})
        constraining = ls.get("constraining_method", "")
        if methods and isinstance(methods, dict):
            elements.append(Paragraph("<b>4-Method Eligibility Analysis</b>", styles['Body']))
            m_data = [["Method", "Eligible Amount (Cr)", "Rationale", "Binding?"]]
            for name, info in methods.items():
                if not isinstance(info, dict):
                    continue
                amt = info.get("eligible_amount") or 0
                rationale = (info.get("rationale") or "")[:80]
                is_bind = name == constraining
                m_data.append([
                    name.replace("_", " ").title(),
                    _fmt_crore(amt, "INR ") if amt else "N/A",
                    rationale,
                    "YES" if is_bind else "",
                ])
            tbl = self._make_table(m_data, [95, 100, 230, 55], header_bg=DARK_SURFACE, font_size=8)
            for ri in range(1, len(m_data)):
                if m_data[ri][3] == "YES":
                    tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, ri), (-1, ri), colors.HexColor("#e8f5e9")),
                        ('FONTNAME', (0, ri), (-1, ri), 'Helvetica-Bold'),
                    ]))
            elements.append(tbl)
            elements.append(Spacer(1, 12))

        # Covenants
        covenants = rec.get("covenants", [])
        if covenants:
            elements.append(Paragraph("<b>Proposed Covenants</b>", styles['Body']))
            cov_data = [["Type", "Covenant", "Trigger Level", "Priority"]]
            for cov in covenants:
                cov_data.append([
                    cov.get("type", "").replace("_", " ").title(),
                    cov.get("covenant", ""),
                    str(cov.get("trigger_level", "")),
                    cov.get("priority", "").upper(),
                ])
            cov_tbl = self._make_table(cov_data, [65, 240, 80, 60], header_bg=colors.HexColor("#e65100"), font_size=8)
            for ri in range(1, len(cov_data)):
                p = cov_data[ri][3]
                if p == "HIGH":
                    cov_tbl.setStyle(TableStyle([('TEXTCOLOR', (3, ri), (3, ri), RED)]))
                elif p == "MEDIUM":
                    cov_tbl.setStyle(TableStyle([('TEXTCOLOR', (3, ri), (3, ri), AMBER)]))
            elements.append(cov_tbl)

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S7 – TRIANGULATION
    # ══════════════════════════════════════════════════════════════════════

    def _section_triangulation(self, app, styles):
        elements = self._section_heading(7, "Data Triangulation & Integrity", styles)

        tri = app.get("triangulation", {})
        if not tri:
            elements.append(Paragraph("Data triangulation not performed.", styles['Body']))
            return elements

        integrity = tri.get("data_integrity", "N/A")
        confidence = tri.get("overall_confidence_pct") or 0
        int_clr = GREEN if integrity == "HIGH" else AMBER if integrity in ("MEDIUM", "MODERATE") else RED
        int_bg = GREEN_BG if integrity == "HIGH" else AMBER_BG if integrity in ("MEDIUM", "MODERATE") else RED_BG
        int_hex = int_clr.hexval() if hasattr(int_clr, 'hexval') else str(int_clr)

        banner = Table(
            [[Paragraph(f"Data Integrity: <font color='{int_hex}'><b>{integrity}</b></font>",
                        ParagraphStyle('_ti', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER)),
              Paragraph(f"Overall Confidence: <b>{confidence:.1f}%</b>",
                        ParagraphStyle('_tc', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER))]],
            colWidths=[245, 245]
        )
        banner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), int_bg),
            ('BACKGROUND', (1, 0), (1, 0), LIGHT_BG),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(banner)
        elements.append(Spacer(1, 10))

        checks = tri.get("checks", [])
        if checks:
            chk_data = [["Check", "Status", "Detail"]]
            for chk in checks:
                status = (chk.get("status") or "N/A").lower()
                if status in ("confirmed",):
                    status_icon = "✓ PASS"
                elif status in ("discrepancy",):
                    status_icon = "✗ FAIL"
                else:
                    status_icon = "— INFO"
                chk_data.append([
                    chk.get("check", "").replace("_", " "),
                    status_icon,
                    (chk.get("detail") or "")[:90],
                ])
            tbl = self._make_table(chk_data, [140, 55, 295], header_bg=DARK_SURFACE, font_size=8)
            for ri in range(1, len(chk_data)):
                st = chk_data[ri][1]
                if "PASS" in st:
                    tbl.setStyle(TableStyle([('TEXTCOLOR', (1, ri), (1, ri), GREEN),
                                              ('FONTNAME', (1, ri), (1, ri), 'Helvetica-Bold')]))
                elif "FAIL" in st:
                    tbl.setStyle(TableStyle([('TEXTCOLOR', (1, ri), (1, ri), RED),
                                              ('FONTNAME', (1, ri), (1, ri), 'Helvetica-Bold')]))
                else:
                    tbl.setStyle(TableStyle([('TEXTCOLOR', (1, ri), (1, ri), BLUE_ACC),
                                              ('FONTNAME', (1, ri), (1, ri), 'Helvetica-Bold')]))
            elements.append(tbl)

        # Summary text
        summary = tri.get("summary", "")
        if summary:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(summary.replace("\n", "<br/>"), styles['Body']))

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S8 – RESEARCH FINDINGS (expanded)
    # ══════════════════════════════════════════════════════════════════════

    def _section_research(self, app, styles):
        elements = self._section_heading(8, "Secondary Research Findings", styles)

        research = app.get("research", {})
        if not research:
            elements.append(Paragraph("Secondary research not yet performed.", styles['Body']))
            return elements

        # AI Summary
        summary = research.get("research_summary", "")
        if summary and len(summary) > 30:
            elements.append(Paragraph("<b>Research Summary</b>", styles['SubHead']))
            elements.append(Paragraph(summary, styles['Body']))
            elements.append(Spacer(1, 8))

        # News Sentiment
        sentiment = research.get("news_sentiment", {}).get("sentiment", {})
        if sentiment:
            label = sentiment.get("label", "N/A")
            s_score = sentiment.get("score", 0)
            clr = GREEN if label == "POSITIVE" else RED if label == "NEGATIVE" else AMBER
            clr_hex = clr.hexval() if hasattr(clr, 'hexval') else str(clr)
            elements.append(Paragraph(
                f"<b>News Sentiment:</b> <font color='{clr_hex}'><b>{label}</b></font> (confidence: {s_score:.0%})",
                styles['Body']
            ))

        # Company news headlines
        news = research.get("news_sentiment", {}).get("company_news", [])
        if news:
            elements.append(Paragraph("<b>Key News Items:</b>", styles['Body']))
            for n in news[:5]:
                title = n.get("title", "")
                snippet = n.get("snippet", "")
                if title:
                    elements.append(Paragraph(
                        f"<bullet>&bull;</bullet> <b>{title[:60]}</b>: {snippet[:120]}",
                        styles['BulletItem']
                    ))

        # Litigation
        lit = research.get("litigation_check", {})
        risk_lev = lit.get("litigation_risk", "N/A")
        clr = self._severity_color(risk_lev)
        clr_hex = clr.hexval() if hasattr(clr, 'hexval') else str(clr)
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            f"<b>Litigation Risk:</b> <font color='{clr_hex}'><b>{risk_lev}</b></font>",
            styles['Body']
        ))
        for item in lit.get("search_results", [])[:3]:
            snippet = item.get("snippet", "")
            if snippet:
                elements.append(Paragraph(f"<bullet>&bull;</bullet> {snippet[:150]}", styles['BulletItem']))

        # Regulatory / MCA
        filings = research.get("regulatory_filings", {}).get("filings", [])
        if filings:
            elements.append(Spacer(1, 4))
            elements.append(Paragraph("<b>Regulatory & MCA Filings:</b>", styles['Body']))
            for f in filings[:3]:
                elements.append(Paragraph(f"<bullet>&bull;</bullet> {f.get('snippet', '')[:150]}", styles['BulletItem']))

        # Industry
        industry = research.get("industry_analysis", {}).get("trends", [])
        if industry:
            elements.append(Spacer(1, 4))
            elements.append(Paragraph("<b>Industry Trends:</b>", styles['Body']))
            for t in industry[:3]:
                elements.append(Paragraph(f"<bullet>&bull;</bullet> {t.get('snippet', '')[:150]}", styles['BulletItem']))

        # Risk flags
        flags = research.get("overall_risk_flags", [])
        if flags:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("<b>Research Risk Flags:</b>", styles['Body']))
            for flag in flags:
                sev = flag.get("severity", "LOW")
                clr = self._severity_color(sev)
                clr_hex = clr.hexval() if hasattr(clr, 'hexval') else str(clr)
                elements.append(Paragraph(
                    f"<bullet>&bull;</bullet> <font color='{clr_hex}'>[{sev}]</font> {flag.get('detail', '')}",
                    styles['BulletItem']
                ))

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S9 – DOCUMENTS
    # ══════════════════════════════════════════════════════════════════════

    def _section_documents(self, app, styles):
        elements = self._section_heading(9, "Document Analysis", styles)

        docs = app.get("documents", [])
        if not docs:
            elements.append(Paragraph(
                "No documents were uploaded for this application. Credit assessment is based entirely on web research and public data.",
                styles['Body']
            ))
            return elements

        doc_data = [["#", "Document Type", "Filename", "Confidence", "Risks"]]
        for i, d in enumerate(docs, 1):
            risks_count = len(d.get("risks_identified", []))
            doc_data.append([
                str(i),
                d.get("doc_type", "N/A").replace("_", " ").title(),
                d.get("filename", "N/A")[:35],
                f"{(d.get('classification_confidence') or 0):.0%}",
                str(risks_count),
            ])
        elements.append(self._make_table(doc_data, [25, 130, 185, 65, 45]))

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S10 – RISK MATRIX
    # ══════════════════════════════════════════════════════════════════════

    def _section_risk_matrix(self, app, styles):
        elements = self._section_heading(10, "Consolidated Risk Matrix", styles)

        all_risks = app.get("risk_score", {}).get("all_risks", [])
        if not all_risks:
            elements.append(Paragraph("No significant risks identified in the analysis.", styles['Body']))
            return elements

        risk_data = [["#", "Category", "Type", "Severity", "Detail"]]
        for i, r in enumerate(all_risks[:15], 1):
            risk_data.append([
                str(i),
                r.get("category", "").replace("_", " ").title(),
                r.get("type", ""),
                r.get("severity", ""),
                r.get("detail", "")[:70],
            ])

        tbl = self._make_table(risk_data, [22, 75, 90, 55, 248], header_bg=colors.HexColor("#b71c1c"), font_size=8)
        for ri in range(1, len(risk_data)):
            sev = risk_data[ri][3].upper()
            clr = self._severity_color(sev)
            tbl.setStyle(TableStyle([
                ('TEXTCOLOR', (3, ri), (3, ri), clr),
                ('FONTNAME', (3, ri), (3, ri), 'Helvetica-Bold'),
            ]))
        elements.append(tbl)

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  S11 – RECOMMENDATION
    # ══════════════════════════════════════════════════════════════════════

    def _section_recommendation(self, app, styles):
        elements = self._section_heading(11, "Final Recommendation", styles)

        risk = app.get("risk_score", {})
        rec = risk.get("recommendation", {})
        if not rec:
            elements.append(Paragraph("Risk scoring not completed.", styles['Body']))
            return elements

        decision = (rec.get("decision") or "N/A").replace("_", " ")
        dec_color = {"APPROVE": GREEN, "APPROVE WITH CONDITIONS": AMBER,
                     "APPROVE REDUCED": AMBER, "REFER TO COMMITTEE": RED, "REJECT": RED}.get(decision, GREY_TEXT)
        dec_bg = {"APPROVE": GREEN_BG, "APPROVE WITH CONDITIONS": AMBER_BG,
                  "APPROVE REDUCED": AMBER_BG, "REFER TO COMMITTEE": RED_BG, "REJECT": RED_BG}.get(decision, LIGHT_BG)
        dec_hex = dec_color.hexval() if hasattr(dec_color, 'hexval') else str(dec_color)

        dec_table = Table(
            [[Paragraph(f"<font color='{dec_hex}'>{decision}</font>", styles['DecisionBig'])]],
            colWidths=[490]
        )
        dec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), dec_bg),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(dec_table)
        elements.append(Spacer(1, 12))

        rec_rows = [
            ["Parameter", "Details"],
            ["Suggested Amount", _fmt_crore(rec.get('suggested_loan_amount'), "INR ")],
            ["Interest Rate",    _fmt_pct(rec.get('interest_rate_pct'))],
            ["Tenure",           f"{rec.get('recommended_tenure_years', 'N/A')} years" if rec.get('recommended_tenure_years') else "N/A"],
            ["Strongest Factor", (rec.get("strongest_factor") or "N/A").replace("_", " ").title()],
            ["Weakest Factor",   (rec.get("weakest_factor") or "N/A").replace("_", " ").title()],
        ]
        explanation = rec.get("explanation", "")
        if explanation:
            rec_rows.append(["Assessment", explanation[:250]])
        elements.append(self._make_table(rec_rows, [130, 360], header_bg=INDIGO))
        elements.append(Spacer(1, 10))

        # ── Detailed Decision Justification ──
        elements.append(Paragraph("<b>Decision Justification</b>", styles['SubHead']))
        justification_parts = []
        five_cs = risk.get("five_cs", {})
        overall_score = risk.get("overall_score", 0)
        ml = risk.get("ml_prediction", {})
        altman = risk.get("altman_z", {})

        justification_parts.append(
            f"The overall weighted credit score is <b>{overall_score:.1f}/100</b> "
            f"({self._score_assessment_text(overall_score).split(' — ')[0]}). "
        )
        if ml.get("rating"):
            justification_parts.append(
                f"The ML model assigns a credit rating of <b>{ml['rating']}</b> "
                f"with a probability of default of <b>{ml.get('pd_percent', 0):.2f}%</b>. "
            )
        if altman.get("zone"):
            z_zone = altman['zone']
            z_score = altman.get('z_score', 0)
            zone_text = "indicating financial stability" if z_zone == "SAFE" else "suggesting moderate financial risk" if z_zone == "GREY" else "indicating financial distress"
            justification_parts.append(
                f"The Altman Z''-Score of <b>{z_score:.2f}</b> places the company in the <b>{z_zone}</b> zone, {zone_text}. "
            )
        strongest = rec.get("strongest_factor", "").replace("_", " ")
        weakest = rec.get("weakest_factor", "").replace("_", " ")
        if strongest:
            strongest_score = five_cs.get(rec.get("strongest_factor", ""), {}).get("score", 0)
            justification_parts.append(
                f"The strongest dimension is <b>{strongest.title()}</b> (score: {strongest_score:.0f}/100)"
            )
        if weakest:
            weakest_score = five_cs.get(rec.get("weakest_factor", ""), {}).get("score", 0)
            justification_parts.append(
                f", while <b>{weakest.title()}</b> is the weakest area (score: {weakest_score:.0f}/100). "
            )
        if decision in ("APPROVE", "APPROVE WITH CONDITIONS"):
            justification_parts.append(
                "Based on the composite assessment, the credit profile meets the threshold for approval. "
            )
        elif "REDUCED" in decision:
            justification_parts.append(
                "While the overall profile is acceptable, certain risk factors warrant a reduced exposure. "
            )
        elif "COMMITTEE" in decision:
            justification_parts.append(
                "The risk profile presents mixed signals requiring senior management review before sanction. "
            )
        elif "REJECT" in decision:
            justification_parts.append(
                "The risk indicators are below acceptable thresholds. The application does not meet credit standards. "
            )
        elements.append(Paragraph("".join(justification_parts), styles['Body']))
        elements.append(Spacer(1, 10))

        conditions = rec.get("conditions", [])
        if conditions:
            elements.append(Paragraph("<b>Conditions for Approval</b>", styles['Body']))
            for c in conditions:
                elements.append(Paragraph(f"<bullet>&bull;</bullet> {c}", styles['BulletItem']))

        # Signature area
        elements.append(Spacer(1, 40))
        sig = Table(
            [["Prepared By", "Reviewed By", "Approved By"],
             ["_________________", "_________________", "_________________"],
             ["Credit Analyst (AI)", "Relationship Manager", "Sanctioning Authority"]],
            colWidths=[165, 165, 165]
        )
        sig.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 0), (-1, -1), GREY_TEXT),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 1), (-1, 1), 25),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
        ]))
        elements.append(sig)

        return elements

    # ══════════════════════════════════════════════════════════════════════
    #  DISCLAIMER
    # ══════════════════════════════════════════════════════════════════════

    def _build_disclaimer(self, styles):
        elements = [
            Spacer(1, 24),
            HRFlowable(width="100%", color=LIGHT_GREY, thickness=0.5),
            Spacer(1, 6),
            Paragraph(
                "<b>Disclaimer:</b> This Credit Appraisal Memo has been generated by the Intelli-Credit AI Engine. "
                "While the analysis incorporates established credit assessment frameworks (Five Cs, Altman Z''-Score, "
                "PD modelling, DSCR/Turnover/Net Worth-based structuring), final lending decisions must involve "
                "human judgment and appropriate due diligence. This document is confidential and intended for internal use only.",
                styles['SmallGrey']
            ),
            Spacer(1, 4),
            Paragraph(
                f"Generated on {datetime.now().strftime('%d %B %Y at %H:%M:%S IST')} by Intelli-Credit Engine v2.0",
                styles['SmallGrey']
            ),
        ]
        return elements
