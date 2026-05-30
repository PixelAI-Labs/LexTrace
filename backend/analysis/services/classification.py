"""Canonical similarity classification helpers."""

from __future__ import annotations

from enum import Enum


class SourceClassification(str, Enum):
    """Single source of truth for source classification labels."""

    exact_copy = "EXACT COPY"
    near_duplicate = "NEAR DUPLICATE"
    modified_copy = "MODIFIED COPY"
    partial_copy = "PARTIAL COPY"
    no_match = "NO MATCH"


def classify_similarity(match_percent: int) -> SourceClassification:
    """Classify a source from its match percentage.

    Thresholds are intentionally centralized here so both backend responses and
    frontend rendering use the same contract.
    """

    if match_percent >= 90:
        return SourceClassification.exact_copy
    if match_percent >= 70:
        return SourceClassification.near_duplicate
    if match_percent >= 40:
        return SourceClassification.modified_copy
    if match_percent >= 10:
        return SourceClassification.partial_copy
    return SourceClassification.no_match
