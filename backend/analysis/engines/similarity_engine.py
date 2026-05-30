"""Similarity engine protocol for the Analysis Service."""

from __future__ import annotations

from typing import Protocol

from backend.analysis.schemas.similarity import SimilarityResult, SimilarityStrategy


class SimilarityEngine(Protocol):
    """Protocol for a pluggable similarity engine."""

    strategy: SimilarityStrategy

    def analyze(self, original_article: str, candidate_article: str) -> SimilarityResult:
        """Compute similarity between the original and candidate articles."""
        ...
