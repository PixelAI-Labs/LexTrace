"""POST /api/v1/analyze — run similarity + risk analysis on candidate articles."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.analysis.schemas.evidence import EvidenceItem, EvidenceSummary
from backend.analysis.schemas.requests import AnalysisRequest
from backend.analysis.schemas.responses import AnalysisResponse
from backend.analysis.schemas.similarity import SimilarityResult, SimilarityStrategy
from backend.analysis.services.dependencies import get_analyzer, get_risk_service
from backend.analysis.services.article_similarity import ArticleSimilarityAnalyzer, SimilarityConfig
from backend.analysis.services.risk_assessment import RiskAssessmentService

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse, summary="Analyze candidate articles")
def analyze(
    body: AnalysisRequest,
    analyzer: Annotated[ArticleSimilarityAnalyzer, Depends(get_analyzer)],
    risk_service: Annotated[RiskAssessmentService, Depends(get_risk_service)],
) -> AnalysisResponse:
    """Compare the original article against every candidate and return similarity
    results, a consolidated evidence summary, and a risk assessment for the
    highest-risk candidate.
    """
    options = body.options
    analyzer_instance = analyzer
    if analyzer._config.enable_semantic != options.enable_semantic:
        analyzer_instance = ArticleSimilarityAnalyzer(
            SimilarityConfig(
                thresholds=analyzer._config.thresholds,
                weights=analyzer._config.weights,
                paragraph_sentence_window=analyzer._config.paragraph_sentence_window,
                enable_semantic=options.enable_semantic,
                semantic_model_name=analyzer._config.semantic_model_name,
            )
        )

    results = []
    evidence_items: list[EvidenceItem] = []

    for candidate in body.candidate_articles[: options.max_candidates]:
        outcome = analyzer_instance.analyze(body.original_article, candidate, body.original_url)
        results.append(outcome.analysis)
        evidence_items.append(outcome.evidence)

    results.sort(key=lambda item: item.similarity_score, reverse=True)
    evidence_items.sort(key=lambda item: item.similarity_score, reverse=True)

    flagged_results = [
        result for result in results if result.similarity_score >= options.min_similarity
    ]

    # ── evidence summary ──────────────────────────────────────────────────────
    evidence_summary = EvidenceSummary(
        total_candidates=len(evidence_items),
        total_matched_paragraphs=sum(len(e.matched_paragraphs) for e in evidence_items),
        total_matched_sentences=sum(len(e.matched_sentences) for e in evidence_items),
        high_confidence_matches=sum(e.high_confidence_matches for e in evidence_items),
        items=evidence_items,
    )

    # ── risk assessment (highest-risk candidate) ──────────────────────────────
    risk_assessment = None
    if flagged_results:
        top = max(flagged_results, key=lambda r: r.similarity_score)
        _top_item = next(
            (e for e in evidence_items if e.candidate_url == top.candidate_url), None
        )
        top_evidence = EvidenceSummary(
            total_candidates=1 if _top_item else 0,
            total_matched_paragraphs=len(_top_item.matched_paragraphs) if _top_item else 0,
            total_matched_sentences=len(_top_item.matched_sentences) if _top_item else 0,
            high_confidence_matches=_top_item.high_confidence_matches if _top_item else 0,
            items=[_top_item] if _top_item else [],
        )
        sim_result = SimilarityResult(
            strategy=SimilarityStrategy.hybrid,
            overall_similarity=top.overall_similarity,
            exact_match_score=top.exact_match_score,
            paragraph_match_score=top.paragraph_match_score,
            ngram_score=top.ngram_score,
            embedding_score=top.embedding_score,
            similarity_score=top.similarity_score,
            copied_percentage=top.copied_percentage,
            matched_paragraphs=top_evidence.total_matched_paragraphs,
            matched_sentences=top_evidence.total_matched_sentences,
        )
        risk_assessment = risk_service.assess(sim_result, top_evidence)

    return AnalysisResponse(
        results=results,
        evidence=evidence_summary,
        risk_assessment=risk_assessment,
    )