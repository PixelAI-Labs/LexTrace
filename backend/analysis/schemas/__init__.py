"""Schemas package for the Analysis Service."""

from backend.analysis.schemas.evidence import EvidenceItem, EvidenceSummary, MatchedParagraph, MatchedSentence
from backend.analysis.schemas.requests import AnalysisOptions, AnalysisRequest, CandidateInput
from backend.analysis.schemas.responses import (
    AnalysisMetadata,
    AnalysisResponse,
    CandidateAnalysis,
    SimilarityBreakdown,
)
from backend.analysis.schemas.risk import RiskAssessment, RiskLevel
from backend.analysis.schemas.similarity import SimilarityResult, SimilarityStrategy

__all__ = [
    "AnalysisMetadata",
    "AnalysisOptions",
    "AnalysisRequest",
    "AnalysisResponse",
    "CandidateAnalysis",
    "CandidateInput",
    "EvidenceItem",
    "EvidenceSummary",
    "MatchedParagraph",
    "MatchedSentence",
    "RiskAssessment",
    "RiskLevel",
    "SimilarityBreakdown",
    "SimilarityResult",
    "SimilarityStrategy",
]
