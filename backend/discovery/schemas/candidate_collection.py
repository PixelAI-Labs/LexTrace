"""Candidate collection models for the Discovery Service."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.discovery.schemas.responses import CandidateArticle


class ExtractionFailure(BaseModel):
    """Details about a failed candidate extraction."""

    url: str = Field(..., description="URL that failed to extract.")
    status: str = Field(..., description="Extraction status (failed or no_text).")
    error_message: str | None = Field(
        default=None,
        description="Human-readable error message if available.",
    )
    attempts: int = Field(..., ge=1, description="Number of extraction attempts made.")
    elapsed_ms: int = Field(..., ge=0, description="Time spent extracting this URL, in milliseconds.")
    position: int = Field(
        ..., ge=1, description="1-based position in the original search ordering."
    )


class CollectionStatistics(BaseModel):
    """Counters describing the collection outcome."""

    total_urls: int = Field(..., ge=0, description="Total URLs considered after deduplication.")
    successful_extractions: int = Field(
        ..., ge=0, description="Number of candidates extracted successfully."
    )
    failed_extractions: int = Field(
        ..., ge=0, description="Number of failed extraction attempts."
    )
    empty_extractions: int = Field(
        ..., ge=0, description="Number of extractions that returned empty content."
    )
    extraction_time_ms: int = Field(
        ..., ge=0, description="Total extraction wall-clock time, in milliseconds."
    )


class CandidateCollectionResult(BaseModel):
    """Result payload from CandidateCollector."""

    candidates: list[CandidateArticle] = Field(
        default_factory=list,
        description="Ordered list of extracted candidate articles.",
    )
    failures: list[ExtractionFailure] = Field(
        default_factory=list,
        description="Extraction failures encountered during collection.",
    )
    statistics: CollectionStatistics = Field(
        ..., description="Collection counters and timings."
    )
    queries_used: list[str] = Field(
        default_factory=list,
        description="Search queries executed for the discovery run.",
    )
    total_urls_collected: int = Field(
        ..., ge=0, description="Total unique URLs collected before extraction."
    )
