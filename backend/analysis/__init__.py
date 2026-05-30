"""Analysis service package."""

from backend.analysis.schemas import (
    AnalysisMetadata,
    AnalysisOptions,
    AnalysisRequest,
    AnalysisResponse,
    CandidateAnalysis,
    CandidateInput,
    EvidenceItem,
    EvidenceSummary,
    MatchedParagraph,
    MatchedSentence,
    RiskLevel,
    SimilarityBreakdown,
    SimilarityResult,
    SimilarityStrategy,
)
from backend.analysis.services import (
    ArticleSimilarityAnalyzer,
    ArticleSimilarityOutcome,
    SimilarityConfig,
    SimilarityThresholds,
    SimilarityWeights,
)

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
    "ArticleSimilarityAnalyzer",
    "ArticleSimilarityOutcome",
    "SimilarityConfig",
    "SimilarityThresholds",
    "SimilarityWeights",
]
