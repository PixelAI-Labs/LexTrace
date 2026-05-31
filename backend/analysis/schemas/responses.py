"""Response models for the Analysis Service."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.risk import RiskAssessment, RiskLevel


class SimilarityBreakdown(BaseModel):
    """Similarity contributions by strategy."""

    exact: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Exact match contribution.",
    )
    paragraph: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Paragraph-level match contribution.",
    )
    ngram: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="N-gram similarity contribution.",
    )
    embedding: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic embedding contribution.",
    )


class CandidateAnalysis(BaseModel):
    """Per-candidate analysis result."""

    candidate_url: str = Field(..., description="Candidate article URL.")
    candidate_title: str | None = Field(default=None, description="Candidate article title, if available.")
    domain: str = Field(..., description="Root domain of the candidate URL.")
    overall_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weighted overall similarity across all signals.",
    )
    exact_match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Exact match score for the candidate.",
    )
    paragraph_match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Paragraph-level match score for the candidate.",
    )
    ngram_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="N-gram similarity score for the candidate.",
    )
    embedding_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic embedding similarity score for the candidate.",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Backward-compatible alias for overall similarity.",
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

    results: list[CandidateAnalysis] = Field(
        default_factory=list,
        description="Per-candidate similarity analysis results.",
    )
    risk_assessment: RiskAssessment | None = Field(
        default=None,
        description="Risk assessment for the highest-risk candidate.",
    )
    evidence: EvidenceSummary | None = Field(
        default=None,
        description="Evidence summary across matched candidates.",
    )
