"""POST /api/v1/report — generate an evidence report for a single candidate."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.report import EvidenceReport, ReportFormat
from backend.analysis.schemas.responses import CandidateAnalysis
from backend.analysis.schemas.risk import RiskAssessment
from backend.analysis.services.dependencies import get_report_generator
from backend.analysis.evidence_report import EvidenceReportGenerator

router = APIRouter(prefix="/api/v1", tags=["report"])


# ── request / response schemas ────────────────────────────────────────────────

class ReportRequest(BaseModel):
    """Input for the report endpoint."""

    analysis: CandidateAnalysis = Field(
        ...,
        description="Per-candidate analysis result from /analyze.",
    )
    evidence: EvidenceSummary = Field(
        ...,
        description="Evidence summary from /analyze.",
    )
    assessment: RiskAssessment = Field(
        ...,
        description="Risk assessment for this candidate.",
    )
    format: ReportFormat = Field(
        default=ReportFormat.text,
        description="Desired report output format (text or markdown).",
    )


# ── route ─────────────────────────────────────────────────────────────────────

@router.post("/report", response_model=EvidenceReport, summary="Generate evidence report")
def generate_report(
    body: ReportRequest,
    generator: Annotated[EvidenceReportGenerator, Depends(get_report_generator)],
) -> EvidenceReport:
    """Render a human-readable evidence report from analysis outputs.

    Pass the ``analysis``, ``evidence``, and ``assessment`` objects returned by
    ``POST /analyze`` (plus an optional ``format`` preference) and receive a
    structured ``EvidenceReport`` with a rendered ``content`` field ready for
    display or download.
    """
    return generator.generate(
        body.analysis,
        body.evidence,
        body.assessment,
        report_format=body.format,
    )