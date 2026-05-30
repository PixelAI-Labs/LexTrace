"""Build the canonical combined scan summary from discovery and analysis output."""

from __future__ import annotations

import re

from backend.analysis.schemas.responses import AnalysisResponse, CandidateAnalysis
from backend.analysis.schemas.scan import ScanSourceSummary, ScanSummary
from backend.analysis.services.classification import classify_similarity, SourceClassification
from backend.discovery.schemas.responses import CandidateArticle, DiscoveryResponse


_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def build_scan_summary(
    *,
    original_article: str,
    discovery: DiscoveryResponse,
    analysis: AnalysisResponse,
) -> ScanSummary:
    """Create a single source of truth for the UI.

    Confidence is independent from similarity: it measures how complete the
    scan pipeline is. When discovery completes successfully and sources are
    found, confidence can be high even if the textual overlap is zero.
    """

    original_word_count = _count_words(original_article)
    analysis_by_url = {result.candidate_url: result for result in analysis.results}

    sources: list[ScanSourceSummary] = []
    for candidate in discovery.candidates:
        sources.append(_build_source_summary(candidate, analysis_by_url.get(candidate.url), original_word_count))

    matched_sources = [source for source in sources if source.classification != SourceClassification.no_match]
    candidate_sources = [source for source in sources if source.classification == SourceClassification.no_match]

    top_similarity = max((source.match_percent for source in matched_sources), default=0)
    confidence = _calculate_confidence(discovery, sources, top_similarity)
    insight = _build_insight(discovery, matched_sources, top_similarity)

    return ScanSummary(
        similarity=top_similarity,
        confidence=confidence,
        source_count=len(sources),
        matched_source_count=len(matched_sources),
        candidate_source_count=len(candidate_sources),
        original_word_count=original_word_count,
        sources=sources,
        matched_sources=matched_sources,
        candidate_sources=candidate_sources,
        insight=insight,
        confidence_notes=(
            "Confidence is derived from discovery completion, source presence, and overlap strength; "
            "it is not a proxy for similarity."
        ),
    )


def _build_source_summary(
    candidate: CandidateArticle,
    analysis_result: CandidateAnalysis | None,
    original_word_count: int,
) -> ScanSourceSummary:
    if analysis_result is None:
        match_percent = 0.0
        words_matched = 0
    else:
        match_percent = round(analysis_result.similarity_score * 100, 1)
        words_matched = int(round(original_word_count * analysis_result.copied_percentage))

    classification = classify_similarity(match_percent)

    return ScanSourceSummary(
        domain=candidate.domain,
        url=candidate.url,
        title=candidate.title,
        match_percent=match_percent,
        words_matched=words_matched,
        authority=candidate.authority,
        classification=classification,
    )


def _calculate_confidence(discovery: DiscoveryResponse, sources: list[ScanSourceSummary], top_similarity: float) -> int:
    discovery_quality = {
        "completed": 1.0,
        "partial": 0.7,
        "failed": 0.2,
    }[discovery.status]

    source_presence = 1.0 if sources else 0.0
    overlap_strength = top_similarity / 100.0

    confidence = round((0.6 * discovery_quality) + (0.25 * source_presence) + (0.15 * overlap_strength), 2)
    return int(round(confidence * 100))


def _build_insight(
    discovery: DiscoveryResponse,
    matched_sources: list[ScanSourceSummary],
    top_similarity: float,
) -> str:
    total_sources = discovery.metadata.total_candidates

    if total_sources == 0:
        return "No candidate sources were discovered."

    if not matched_sources:
        source_label = "source was" if total_sources == 1 else "sources were"
        return f"{total_sources} candidate {source_label} discovered, but no overlapping passages were detected."

    if top_similarity < 40:
        return "Potential topical overlap detected, but textual similarity remains below reporting thresholds."

    if top_similarity < 70:
        return "Multiple matching passages were identified across indexed sources."

    return "Strong textual overlap was identified across indexed sources."


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))
