"""Schemas package for the Analysis Service."""

from backend.analysis.schemas.evidence import EvidenceItem, EvidenceSummary, MatchedParagraph, MatchedSentence
from backend.analysis.schemas.dmca import DmcaNotice, DmcaRequest
from backend.analysis.schemas.report import EvidenceReport, ReportFormat
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
    "DmcaNotice",
    "DmcaRequest",
    "EvidenceItem",
    "EvidenceReport",
    "EvidenceSummary",
    "MatchedParagraph",
    "MatchedSentence",
    "ReportFormat",
    "RiskAssessment",
    "RiskLevel",
    "SimilarityBreakdown",
    "SimilarityResult",
    "SimilarityStrategy",
]
