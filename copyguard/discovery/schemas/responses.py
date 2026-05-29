"""Response models for the Discovery Service."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CandidateArticle(BaseModel):
    """A single candidate article found during discovery.

    All confidence scores are floats in the range [0.0, 1.0], where
    1.0 means the candidate is maximally similar to the original.
    """

    rank: int = Field(..., ge=1, description="1-based position in the ranked results.")
    url: str = Field(..., description="Canonical URL of the candidate article.")
    domain: str = Field(..., description="Root domain of the candidate URL (e.g. 'example.com').")
    title: str | None = Field(default=None, description="Article title extracted from the candidate page.")
    rank_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite similarity score weighting keyword coverage, TF-IDF cosine, structural similarity, and title match.",
    )
    keyword_coverage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of original article keywords found in the candidate.",
    )
    content_preview: str = Field(
        ...,
        max_length=500,
        description="First ~300 characters of the normalised candidate content.",
    )
    text_length: int = Field(..., ge=0, description="Total word count of the extracted candidate content.")
    publish_date: str | None = Field(
        default=None,
        description="ISO 8601 date string (YYYY-MM-DD) if a publish date was detected, otherwise null.",
    )
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code detected from the candidate content, e.g. 'en'.",
    )


class DiscoveryMetadata(BaseModel):
    """Timings and counters describing how the discovery run executed."""

    total_candidates: int = Field(..., ge=0, description="Total candidates returned to the client.")
    queries_generated: int = Field(..., ge=0, description="Number of search queries sent to Google.")
    extraction_time_ms: int = Field(..., ge=0, description="Wall-clock time spent extracting candidate content, in milliseconds.")
    search_time_ms: int = Field(..., ge=0, description="Wall-clock time spent querying Google, in milliseconds.")
    total_time_ms: int = Field(..., ge=0, description="End-to-end wall-clock time for the discovery run, in milliseconds.")


class DiscoveryResponse(BaseModel):
    """POST /discover response body."""

    request_id: str = Field(..., description="UUID assigned to this discovery request for tracing.")
    status: Literal["completed", "partial", "failed"] = Field(
        ...,
        description=(
            "'completed' — all candidates successfully extracted. "
            "'partial' — some candidates failed but usable results were returned. "
            "'failed' — no candidates could be extracted."
        ),
    )
    original_title: str | None = Field(
        default=None,
        description="Echo back of the title supplied in the request (null if absent).",
    )
    queries_used: list[str] = Field(
        default_factory=list,
        description="List of Google query strings that were executed.",
    )
    total_urls_collected: int = Field(
        ...,
        ge=0,
        description="Total unique URLs collected from Google before extraction.",
    )
    candidates: list[CandidateArticle] = Field(
        default_factory=list,
        description="Ranked list of candidate articles, ordered by rank_score descending.",
    )
    metadata: DiscoveryMetadata = Field(
        ...,
        description="Timing and counter metadata for this run.",
    )