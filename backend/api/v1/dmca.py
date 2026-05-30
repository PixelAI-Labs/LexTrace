"""POST /api/v1/dmca — generate a DMCA takedown notice."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.analysis.schemas.dmca import DmcaNotice, DmcaRequest
from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.responses import CandidateAnalysis
from backend.analysis.schemas.risk import RiskAssessment
from backend.analysis.services.dependencies import get_dmca_generator
from backend.analysis.dmca_generator import DmcaGeneratorService

router = APIRouter(prefix="/api/v1", tags=["dmca"])


# ── request schema ────────────────────────────────────────────────────────────

class DmcaGenerateRequest(BaseModel):
    """Input for the DMCA generation endpoint."""

    dmca_request: DmcaRequest = Field(
        ...,
        description="Copyright holder details and URLs.",
    )
    assessment: RiskAssessment = Field(
        ...,
        description="Risk assessment for the infringing candidate.",
    )
    evidence: EvidenceSummary = Field(
        ...,
        description="Evidence summary from /analyze.",
    )
    analysis: CandidateAnalysis | None = Field(
        default=None,
        description=(
            "Per-candidate analysis result. When supplied, similarity scores "
            "are included in the notice body."
        ),
    )
    template_name: str = Field(
        default="dmca_standard.txt",
        description="Template file to use for the notice body.",
    )


# ── route ─────────────────────────────────────────────────────────────────────

@router.post("/dmca", response_model=DmcaNotice, summary="Generate DMCA takedown notice")
def generate_dmca(
    body: DmcaGenerateRequest,
    generator: Annotated[DmcaGeneratorService, Depends(get_dmca_generator)],
) -> DmcaNotice:
    """Produce a ready-to-send DMCA takedown notice.

    Combines the copyright holder contact details in ``dmca_request`` with
    evidence and risk signals to render a notice using the chosen template.
    Returns a ``DmcaNotice`` with ``subject``, ``body``, ``summary``, and
    ``risk_level`` fields.
    """
    return generator.generate(
        body.dmca_request,
        body.assessment,
        body.evidence,
        template_name=body.template_name,
        analysis=body.analysis,
    )