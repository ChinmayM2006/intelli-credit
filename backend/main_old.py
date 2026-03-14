"""
Intelli-Credit: AI-Powered Credit Decisioning Engine
Main FastAPI application
"""
import os
import uuid
import json
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import UPLOAD_DIR, OUTPUT_DIR
from ingestor.parser import parse_document
from ingestor.structured_analysis import analyze_gst_data, analyze_bank_statements, cross_reference_gst_bank
from research.agent import ResearchAgent
from engine.risk_scorer import CreditRiskScorer
from engine.cam_generator import CAMGenerator

app = FastAPI(
    title="Intelli-Credit Engine",
    description="AI-powered Credit Decisioning Engine for Corporate Lending",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory store for demo ───────────────────────────────────────────────
applications: dict = {}


# ─── Models ──────────────────────────────────────────────────────────────────
class ApplicationCreate(BaseModel):
    company_name: str
    cin: Optional[str] = None
    industry: Optional[str] = None
    loan_amount_requested: Optional[float] = None
    loan_purpose: Optional[str] = None


class PrimaryInsight(BaseModel):
    application_id: str
    note_type: str  # factory_visit | management_interview | other
    content: str
    officer_name: Optional[str] = None


class ResearchRequest(BaseModel):
    application_id: str
    company_name: str
    promoter_names: Optional[List[str]] = []
    industry: Optional[str] = None


class ScoreRequest(BaseModel):
    application_id: str


# ─── Application CRUD ────────────────────────────────────────────────────────
@app.post("/api/applications")
async def create_application(data: ApplicationCreate):
    app_id = str(uuid.uuid4())[:8]
    applications[app_id] = {
        "id": app_id,
        "company_name": data.company_name,
        "cin": data.cin,
        "industry": data.industry,
        "loan_amount_requested": data.loan_amount_requested,
        "loan_purpose": data.loan_purpose,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "documents": [],
        "parsed_data": {},
        "primary_insights": [],
        "research": {},
        "risk_score": None,
        "cam_path": None,
    }
    return {"application_id": app_id, "status": "created"}


@app.get("/api/applications")
async def list_applications():
    return list(applications.values())


@app.get("/api/applications/{app_id}")
async def get_application(app_id: str):
    if app_id not in applications:
        raise HTTPException(404, "Application not found")
    return applications[app_id]


# ─── Pillar 1: Data Ingestor ────────────────────────────────────────────────
@app.post("/api/applications/{app_id}/upload")
async def upload_document(
    app_id: str,
    doc_type: str = Form(...),  # gst | itr | bank_statement | annual_report | financial_statement | board_minutes | rating_report | shareholding | sanction_letter | legal_notice | other
    file: UploadFile = File(...),
):
    if app_id not in applications:
        raise HTTPException(404, "Application not found")

    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1]
    save_path = os.path.join(UPLOAD_DIR, f"{app_id}_{file_id}{ext}")

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # Parse the document
    parsed = parse_document(save_path, doc_type)

    doc_entry = {
        "file_id": file_id,
        "filename": file.filename,
        "doc_type": doc_type,
        "path": save_path,
        "parsed_summary": parsed.get("summary", ""),
        "extracted_fields": parsed.get("fields", {}),
        "risks_identified": parsed.get("risks", []),
        "uploaded_at": datetime.now().isoformat(),
    }

    applications[app_id]["documents"].append(doc_entry)
    applications[app_id]["parsed_data"][doc_type] = parsed
    applications[app_id]["status"] = "documents_uploaded"

    return {"file_id": file_id, "parsed": parsed}


@app.post("/api/applications/{app_id}/analyze-structured")
async def analyze_structured_data(app_id: str):
    """Cross-reference GST returns against bank statements to detect circular trading / revenue inflation."""
    if app_id not in applications:
        raise HTTPException(404, "Application not found")

    app_data = applications[app_id]
    gst_data = app_data["parsed_data"].get("gst", {})
    bank_data = app_data["parsed_data"].get("bank_statement", {})

    gst_analysis = analyze_gst_data(gst_data)
    bank_analysis = analyze_bank_statements(bank_data)
    cross_ref = cross_reference_gst_bank(gst_data, bank_data)

    result = {
        "gst_analysis": gst_analysis,
        "bank_analysis": bank_analysis,
        "cross_reference": cross_ref,
    }

    applications[app_id]["parsed_data"]["structured_analysis"] = result
    return result


# ─── Pillar 2: Research Agent ────────────────────────────────────────────────
@app.post("/api/applications/{app_id}/research")
async def run_research(data: ResearchRequest):
    if data.application_id not in applications:
        raise HTTPException(404, "Application not found")

    agent = ResearchAgent()
    research_results = await agent.research_company(
        company_name=data.company_name,
        promoter_names=data.promoter_names or [],
        industry=data.industry or "",
    )

    applications[data.application_id]["research"] = research_results
    applications[data.application_id]["status"] = "research_complete"
    return research_results


@app.post("/api/applications/{app_id}/primary-insight")
async def add_primary_insight(insight: PrimaryInsight):
    if insight.application_id not in applications:
        raise HTTPException(404, "Application not found")

    entry = {
        "note_type": insight.note_type,
        "content": insight.content,
        "officer_name": insight.officer_name,
        "added_at": datetime.now().isoformat(),
    }
    applications[insight.application_id]["primary_insights"].append(entry)
    return {"status": "insight_added", "insights_count": len(applications[insight.application_id]["primary_insights"])}


# ─── Pillar 3: Recommendation Engine ────────────────────────────────────────
@app.post("/api/applications/{app_id}/score")
async def calculate_risk_score(app_id: str):
    if app_id not in applications:
        raise HTTPException(404, "Application not found")

    app_data = applications[app_id]
    scorer = CreditRiskScorer()
    score_result = scorer.score(app_data)

    applications[app_id]["risk_score"] = score_result
    applications[app_id]["status"] = "scored"
    return score_result


@app.post("/api/applications/{app_id}/generate-cam")
async def generate_cam(app_id: str):
    if app_id not in applications:
        raise HTTPException(404, "Application not found")

    app_data = applications[app_id]
    generator = CAMGenerator()
    cam_path = generator.generate(app_data, OUTPUT_DIR)

    applications[app_id]["cam_path"] = cam_path
    applications[app_id]["status"] = "cam_generated"
    return {"cam_path": cam_path, "status": "cam_generated"}


@app.get("/api/applications/{app_id}/download-cam")
async def download_cam(app_id: str):
    if app_id not in applications:
        raise HTTPException(404, "Application not found")

    cam_path = applications[app_id].get("cam_path")
    if not cam_path or not os.path.exists(cam_path):
        raise HTTPException(404, "CAM not generated yet")

    return FileResponse(cam_path, filename=f"CAM_{app_id}.pdf", media_type="application/pdf")


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "engine": "Intelli-Credit"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
