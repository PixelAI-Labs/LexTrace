"""Canonical scan response models for the combined discovery + analysis flow."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.analysis.services.classification import SourceClassification


class ScanSourceSummary(BaseModel):
    """A single source rendered in the scan report."""

    domain: str = Field(..., description="Root domain for the source.")
    url: str = Field(..., description="Canonical URL for the source.")
    title: str | None = Field(default=None, description="Source title if available.")
    match_percent: float = Field(..., ge=0, le=100, description="Match percentage as a float to preserve precision.")
    exact_match_score: float = Field(default=0.0, ge=0, le=100, description="Exact match percentage.")
    paragraph_match_score: float = Field(default=0.0, ge=0, le=100, description="Paragraph match percentage.")
    ngram_score: float = Field(default=0.0, ge=0, le=100, description="N-gram percentage.")
    embedding_score: float = Field(default=0.0, ge=0, le=100, description="Semantic embedding percentage.")
    words_matched: int = Field(..., ge=0, description="Estimated matched word count.")
    authority: int | None = Field(
        default=None,
        ge=0,
        description="Optional source authority signal when the backend can provide one.",
    )
    classification: SourceClassification = Field(..., description="Canonical similarity class.")


class ScanSummary(BaseModel):
    """Backend-owned summary of the similarity analysis run."""

    similarity: float = Field(..., ge=0, le=100, description="Top similarity percentage as a float to preserve precision.")
    exact_match_score: float = Field(default=0.0, ge=0, le=100, description="Top exact match percentage.")
    paragraph_match_score: float = Field(default=0.0, ge=0, le=100, description="Top paragraph match percentage.")
    ngram_score: float = Field(default=0.0, ge=0, le=100, description="Top n-gram match percentage.")
    embedding_score: float = Field(default=0.0, ge=0, le=100, description="Top semantic embedding percentage.")
    confidence: int = Field(
        ..., ge=0, le=100, description="Independent confidence in the analysis pipeline, not the similarity score."
    )
    source_count: int = Field(..., ge=0, description="Total number of source rows in the response.")
    matched_source_count: int = Field(..., ge=0, description="Rows with a non-NO MATCH classification.")
    candidate_source_count: int = Field(..., ge=0, description="Rows with a NO MATCH classification.")
    original_word_count: int = Field(..., ge=0, description="Word count of the original article input.")
    sources: list[ScanSourceSummary] = Field(default_factory=list, description="All source rows.")
    matched_sources: list[ScanSourceSummary] = Field(
        default_factory=list,
        description="Sources above the reporting threshold.",
    )
    candidate_sources: list[ScanSourceSummary] = Field(
        default_factory=list,
        description="Sources below the reporting threshold.",
    )
    insight: str = Field(..., description="Human-readable insight derived from the scan results.")
    confidence_notes: str = Field(
        ...,
        description="Short explanation of how confidence was derived for the scan.",
    )
