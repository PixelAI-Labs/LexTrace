"""Similarity contracts for the Analysis Service."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SimilarityStrategy(str, Enum):
    """Supported similarity strategies."""

    exact = "exact"
    fuzzy = "fuzzy"
    semantic = "semantic"


class SimilarityResult(BaseModel):
    """Result from running a single similarity strategy."""

    strategy: SimilarityStrategy = Field(
        ...,
        description="Similarity strategy used to produce this result.",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall similarity score for this strategy.",
    )
    copied_percentage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated fraction of content copied for this strategy.",
    )
    matched_paragraphs: int = Field(
        default=0,
        ge=0,
        description="Number of matched paragraphs detected.",
    )
    matched_sentences: int = Field(
        default=0,
        ge=0,
        description="Number of matched sentences detected.",
    )
    metadata: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Strategy-specific metadata for reporting.",
    )
