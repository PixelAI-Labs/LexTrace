"""Search orchestration response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection


class SearchOrchestratorResult(BaseModel):
    """Structured results returned by the search orchestrator."""

    queries_used: list[str] = Field(
        default_factory=list,
        description="Search queries executed during orchestration.",
    )
    provider_results: list[SearchResultCollection] = Field(
        default_factory=list,
        description="Raw results returned by each provider execution.",
    )
    deduplicated_results: list[SearchResult] = Field(
        default_factory=list,
        description="Aggregated results after URL deduplication.",
    )
    total_unique_urls: int = Field(
        default=0,
        ge=0,
        description="Number of unique URLs collected after deduplication.",
    )
    total_results: int = Field(
        default=0,
        ge=0,
        description="Total number of raw results returned before deduplication.",
    )
    search_time_ms: int = Field(
        default=0,
        ge=0,
        description="Total wall-clock search time across providers, in milliseconds.",
    )
