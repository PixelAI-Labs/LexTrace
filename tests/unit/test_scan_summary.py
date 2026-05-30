"""Unit tests for the canonical scan summary contract."""

from __future__ import annotations

from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.responses import AnalysisResponse, CandidateAnalysis, SimilarityBreakdown
from backend.analysis.schemas.risk import RiskLevel
from backend.analysis.services.classification import SourceClassification, classify_similarity
from backend.analysis.services.scan_summary import build_scan_summary
from backend.discovery.schemas.responses import CandidateArticle, DiscoveryMetadata, DiscoveryResponse


def test_classify_similarity_thresholds() -> None:
    assert classify_similarity(90) == SourceClassification.exact_copy
    assert classify_similarity(70) == SourceClassification.near_duplicate
    assert classify_similarity(40) == SourceClassification.modified_copy
    assert classify_similarity(10) == SourceClassification.partial_copy
    assert classify_similarity(9) == SourceClassification.no_match


def test_build_scan_summary_counts_and_confidence_are_backend_derived() -> None:
    discovery = DiscoveryResponse(
        request_id="550e8400-e29b-41d4-a716-446655440000",
        status="completed",
        original_title="Original Article",
        queries_used=["original article"],
        total_urls_collected=1,
        candidates=[
            CandidateArticle(
                rank=1,
                url="https://example.com/candidate",
                domain="example.com",
                title="Candidate Article",
                rank_score=0.0,
                keyword_coverage=0.0,
                content_preview="Preview",
                text_length=1200,
            ),
        ],
        metadata=DiscoveryMetadata(
            total_candidates=1,
            queries_generated=1,
            extraction_time_ms=25,
            search_time_ms=50,
            total_time_ms=75,
        ),
    )
    analysis = AnalysisResponse(
        results=[],
        evidence=EvidenceSummary(
            total_candidates=0,
            total_matched_paragraphs=0,
            total_matched_sentences=0,
            items=[],
        ),
        risk_assessment=None,
    )

    summary = build_scan_summary(
        original_article="This is the original article body for testing.",
        discovery=discovery,
        analysis=analysis,
    )

    assert summary.similarity == 0
    assert summary.source_count == 1
    assert summary.matched_source_count == 0
    assert summary.candidate_source_count == 1
    assert summary.confidence == 85
    assert summary.sources[0].classification == SourceClassification.no_match
    assert summary.sources[0].authority is None
    assert summary.insight == "1 candidate source was discovered, but no overlapping passages were detected."


def test_build_scan_summary_uses_analysis_results_for_matches() -> None:
    discovery = DiscoveryResponse(
        request_id="550e8400-e29b-41d4-a716-446655440001",
        status="completed",
        original_title="Original Article",
        queries_used=["original article"],
        total_urls_collected=1,
        candidates=[
            CandidateArticle(
                rank=1,
                url="https://example.com/match",
                domain="example.com",
                title="Matching Article",
                rank_score=0.0,
                keyword_coverage=0.0,
                content_preview="Preview",
                text_length=1200,
            ),
        ],
        metadata=DiscoveryMetadata(
            total_candidates=1,
            queries_generated=1,
            extraction_time_ms=25,
            search_time_ms=50,
            total_time_ms=75,
        ),
    )
    analysis = AnalysisResponse(
        results=[
            CandidateAnalysis(
                candidate_url="https://example.com/match",
                candidate_title="Matching Article",
                domain="example.com",
                similarity_score=0.92,
                copied_percentage=0.88,
                breakdown=SimilarityBreakdown(exact=0.1, fuzzy=0.5, semantic=0.32),
                risk_level=RiskLevel.high,
            ),
        ],
        evidence=EvidenceSummary(
            total_candidates=1,
            total_matched_paragraphs=2,
            total_matched_sentences=4,
            items=[],
        ),
        risk_assessment=None,
    )

    summary = build_scan_summary(
        original_article="This is the original article body for testing. It has enough words.",
        discovery=discovery,
        analysis=analysis,
    )

    assert summary.similarity == 92
    assert summary.matched_source_count == 1
    assert summary.candidate_source_count == 0
    assert summary.sources[0].classification == SourceClassification.exact_copy
    assert summary.sources[0].words_matched > 0