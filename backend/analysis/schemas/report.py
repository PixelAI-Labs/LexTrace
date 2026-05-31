"""Evidence report models for the Analysis Service."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from backend.analysis.schemas.risk import RiskLevel


class ReportFormat(str, Enum):
    """Supported evidence report output formats."""

    text = "text"
    markdown = "markdown"


class EvidenceReportEntry(BaseModel):
    """Single evidence match entry used in report output."""

    match_index: int = Field(..., ge=1, description="1-based index of the match in the report.")
    source: Literal["sentence", "paragraph"] = Field(..., description="Granularity of the match.")
    match_type: str = Field(..., description="Match type (exact, fuzzy, semantic, mixed).")
    original_text: str = Field(..., description="Matched text from the original article.")
    candidate_text: str = Field(..., description="Matched text from the candidate article.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score for the match.",
    )


class EvidenceReportSummary(BaseModel):
    """Summary section for evidence report output."""

    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall similarity score for the candidate.",
    )
    copied_percentage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated fraction of copied content.",
    )
    risk_level: RiskLevel = Field(..., description="Infringement risk level.")
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the risk assessment.",
    )
    total_matches: int = Field(..., ge=0, description="Total matches included in the report.")
    total_paragraphs: int = Field(..., ge=0, description="Total matched paragraphs detected.")
    total_sentences: int = Field(..., ge=0, description="Total matched sentences detected.")
    reasoning: list[str] = Field(
        default_factory=list,
        description="Human-readable reasoning for the risk assessment.",
    )


class EvidenceReport(BaseModel):
    """Structured evidence report output."""

    format: ReportFormat = Field(..., description="Report output format.")
    content: str = Field(..., description="Rendered report content.")
    summary: EvidenceReportSummary = Field(..., description="Summary section of the report.")
    evidence: list[EvidenceReportEntry] = Field(
        default_factory=list,
        description="Evidence section entries.",
    )
