"""Request models for the Analysis Service."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisOptions(BaseModel):
    """Optional tuning parameters for analysis."""

    min_similarity: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score required to include a candidate in risk assessment.",
    )
    max_candidates: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of candidates to analyze.",
    )
    enable_semantic: bool = Field(
        default=False,
        description="Whether to enable semantic similarity strategies.",
    )


class CandidateInput(BaseModel):
    """Candidate article payload sent from discovery."""

    url: str = Field(..., description="Canonical URL for the candidate article.")
    title: str | None = Field(default=None, description="Candidate article title, if available.")
    content: str = Field(
        ...,
        min_length=1,
        max_length=200_000,
        description="Full text content of the candidate article.",
    )
    domain: str = Field(..., description="Root domain of the candidate URL (e.g. 'example.com').")


class AnalysisRequest(BaseModel):
    """POST /analyze request body.

    The caller submits the original article along with candidate articles for analysis.
    """

    original_article: str = Field(
        ...,
        min_length=100,
        max_length=100_000,
        description="Full text of the original article to compare against.",
    )
    original_url: str | None = Field(
        default=None,
        description="Optional canonical URL for the original article when the caller has it.",
    )
    candidate_articles: list[CandidateInput] = Field(
        ...,
        min_length=1,
        description="Candidate articles to analyze for similarity.",
    )
    options: AnalysisOptions = Field(
        default_factory=AnalysisOptions,
        description="Analysis tuning options. Safe to omit.",
    )
