"""Response models for the Analysis Service."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from backend.analysis.schemas.evidence import EvidenceSummary


class RiskLevel(str, Enum):
    """Risk classification for infringement likelihood."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SimilarityBreakdown(BaseModel):
    """Similarity contributions by strategy."""

    exact: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Exact match contribution.",
    )
    fuzzy: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fuzzy match contribution.",
    )
    semantic: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic similarity contribution.",
    )


class CandidateAnalysis(BaseModel):
    """Per-candidate analysis result."""

    candidate_url: str = Field(..., description="Candidate article URL.")
    candidate_title: str | None = Field(default=None, description="Candidate article title, if available.")
    domain: str = Field(..., description="Root domain of the candidate URL.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall similarity score between original and candidate.",
    )
    copied_percentage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated fraction of content copied (0.0 to 1.0).",
    )
    breakdown: SimilarityBreakdown = Field(
        default_factory=SimilarityBreakdown,
        description="Similarity breakdown across strategies.",
    )
    risk_level: RiskLevel = Field(..., description="Risk classification for the candidate.")


class AnalysisMetadata(BaseModel):
    """Metadata describing the analysis run."""

    analysis_time_ms: int = Field(
        ...,
        ge=0,
        description="End-to-end analysis time in milliseconds.",
    )
    engine_version: str = Field(
        default="0.1.0",
        description="Version of the analysis engine used.",
    )
    thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Thresholds applied during analysis (e.g. min_similarity).",
    )


class AnalysisResponse(BaseModel):
    """POST /analyze response body."""

    analysis_id: str = Field(..., description="Unique identifier for this analysis run.")
    status: Literal["completed", "partial", "failed"] = Field(
        ...,
        description="Overall status of the analysis request.",
    )
    similarity_results: list[CandidateAnalysis] = Field(
        default_factory=list,
        description="Per-candidate similarity analysis results.",
    )
    evidence_report: EvidenceSummary | None = Field(
        default=None,
        description="Evidence report summarizing matched content and metadata.",
    )
    risk_assessment: dict[str, object] | None = Field(
        default=None,
        description="Risk assessment placeholder; detailed models arrive in Phase 3.",
    )
    dmca_notice: dict[str, str] | None = Field(
        default=None,
        description="DMCA notice placeholder; structured model arrives later.",
    )
    metadata: AnalysisMetadata = Field(
        ...,
        description="Timing and configuration metadata for this run.",
    )
