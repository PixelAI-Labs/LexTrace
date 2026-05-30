"""FastAPI dependency providers for the Analysis API."""

from __future__ import annotations

from functools import lru_cache

from .article_similarity import ArticleSimilarityAnalyzer, SimilarityConfig
from .dmca_generator import DmcaGeneratorService
from .evidence_report import EvidenceReportGenerator
from .risk_assessment import RiskAssessmentService
from backend.analysis.schemas.report import ReportFormat


# ── singletons (one per process) ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_analyzer() -> ArticleSimilarityAnalyzer:
    """Return a shared ArticleSimilarityAnalyzer instance."""
    return ArticleSimilarityAnalyzer(SimilarityConfig())


@lru_cache(maxsize=1)
def get_risk_service() -> RiskAssessmentService:
    """Return a shared RiskAssessmentService instance."""
    return RiskAssessmentService()


@lru_cache(maxsize=1)
def get_report_generator() -> EvidenceReportGenerator:
    """Return a shared EvidenceReportGenerator (defaults to text format)."""
    return EvidenceReportGenerator(ReportFormat.text)


@lru_cache(maxsize=1)
def get_dmca_generator() -> DmcaGeneratorService:
    """Return a shared DmcaGeneratorService instance."""
    return DmcaGeneratorService()