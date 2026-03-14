"""
SQLite database layer using SQLAlchemy.
Replaces the in-memory dict store.
"""
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from backend.config import DB_PATH

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── Models ──────────────────────────────────────────────────────────────────

class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    company_name = Column(String, nullable=False)
    cin = Column(String, nullable=True)
    pan = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    turnover = Column(Float, nullable=True)
    incorporation_year = Column(Integer, nullable=True)
    promoter_names = Column(String, nullable=True)

    # Loan details
    loan_type = Column(String, nullable=True)
    loan_amount_requested = Column(Float, nullable=True)
    loan_tenure_requested = Column(Integer, nullable=True)
    loan_purpose = Column(String, nullable=True)

    # Status & timestamps
    stage = Column(String, default="onboarding")
    status = Column(String, default="created")
    created_at = Column(DateTime, default=datetime.utcnow)

    # JSON blobs for complex data (stored as text, accessed directly)
    parsed_data = Column(Text, default="{}")
    research = Column(Text, default="{}")
    risk_score = Column(Text, nullable=True)
    swot = Column(Text, nullable=True)
    triangulation = Column(Text, nullable=True)
    loan_structure = Column(Text, nullable=True)
    cam_path = Column(String, nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    insights = relationship("PrimaryInsight", back_populates="application", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        docs = [d.to_dict() for d in self.documents] if self.documents else []
        ins = [i.to_dict() for i in self.insights] if self.insights else []
        return {
            "id": self.id,
            "company_name": self.company_name,
            "cin": self.cin,
            "pan": self.pan,
            "sector": self.sector,
            "industry": self.industry,
            "turnover": self.turnover,
            "incorporation_year": self.incorporation_year,
            "promoter_names": self.promoter_names,
            "loan_type": self.loan_type,
            "loan_amount_requested": self.loan_amount_requested,
            "loan_tenure_requested": self.loan_tenure_requested,
            "loan_purpose": self.loan_purpose,
            "stage": self.stage,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "documents": docs,
            "parsed_data": json.loads(self.parsed_data or "{}"),
            "primary_insights": ins,
            "research": json.loads(self.research or "{}"),
            "risk_score": json.loads(self.risk_score) if self.risk_score else None,
            "swot": json.loads(self.swot) if self.swot else None,
            "triangulation": json.loads(self.triangulation) if self.triangulation else None,
            "loan_structure": json.loads(self.loan_structure) if self.loan_structure else None,
            "cam_path": self.cam_path,
        }


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    filename = Column(String, nullable=False)
    doc_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    classification_confidence = Column(Float, nullable=True)
    classification_evidence = Column(String, nullable=True)
    confirmed = Column(Boolean, default=False)
    parsed_summary = Column(String, nullable=True)
    extracted_fields_json = Column(Text, default="{}")
    risks_json = Column(Text, default="[]")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="documents")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.id,
            "filename": self.filename,
            "doc_type": self.doc_type,
            "path": self.file_path,
            "classification_confidence": self.classification_confidence,
            "classification_evidence": self.classification_evidence,
            "confirmed": self.confirmed,
            "parsed_summary": self.parsed_summary,
            "extracted_fields": json.loads(self.extracted_fields_json or "{}"),
            "risks_identified": json.loads(self.risks_json or "[]"),
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class PrimaryInsight(Base):
    __tablename__ = "primary_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    note_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    officer_name = Column(String, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="insights")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_type": self.note_type,
            "content": self.content,
            "officer_name": self.officer_name,
            "added_at": self.added_at.isoformat() if self.added_at else None,
        }


# ─── Database helpers ────────────────────────────────────────────────────────

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI — yields a session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
