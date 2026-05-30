"""Schemas package for the Analysis Service."""

from backend.analysis.schemas.evidence import EvidenceItem, EvidenceSummary, MatchedParagraph, MatchedSentence
from backend.analysis.schemas.requests import AnalysisOptions, AnalysisRequest, CandidateInput
from backend.analysis.schemas.responses import (
    AnalysisMetadata,
    AnalysisResponse,
    CandidateAnalysis,
    RiskLevel,
    SimilarityBreakdown,
)
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
    "RiskLevel",
    "SimilarityBreakdown",
    "SimilarityResult",
    "SimilarityStrategy",
]
