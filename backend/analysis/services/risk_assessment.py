"""Risk assessment service for infringement likelihood."""

from __future__ import annotations

from dataclasses import dataclass

from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.risk import RiskAssessment, RiskLevel
from backend.analysis.schemas.similarity import SimilarityResult


@dataclass(frozen=True, slots=True)
class RiskAssessmentThresholds:
    """Configurable thresholds for risk assessment."""

    medium_score: float = 0.4
    high_score: float = 0.7
    medium_copied: float = 0.3
    high_copied: float = 0.6
    medium_paragraphs: int = 3
    high_paragraphs: int = 8
    medium_sentences: int = 6
    high_sentences: int = 16
    strong_semantic: float = 0.7


@dataclass(frozen=True, slots=True)
class RiskAssessmentWeights:
    """Weights for confidence scoring."""

    similarity: float = 0.45
    copied: float = 0.35
    evidence: float = 0.15
    semantic: float = 0.05


class RiskAssessmentService:
    """Deterministic risk assessment based on similarity and evidence."""

    def __init__(
        self,
        thresholds: RiskAssessmentThresholds | None = None,
        weights: RiskAssessmentWeights | None = None,
    ) -> None:
        self._thresholds = thresholds or RiskAssessmentThresholds()
        self._weights = weights or RiskAssessmentWeights()

    def assess(self, similarity: SimilarityResult, evidence: EvidenceSummary) -> RiskAssessment:
        """Assess infringement risk from similarity and evidence signals."""
        thresholds = self._thresholds
        weights = self._weights

        similarity_score = _clamp(similarity.similarity_score)
        copied_percentage = _clamp(similarity.copied_percentage)
        semantic_score = _clamp(_safe_float(similarity.metadata.get("semantic_score", 0.0)))

        paragraphs = max(evidence.total_matched_paragraphs, 0)
        sentences = max(evidence.total_matched_sentences, 0)

        evidence_factor = _evidence_factor(
            paragraphs,
            sentences,
            thresholds,
        )

        risk_signal = max(similarity_score, copied_percentage, semantic_score)
        risk_signal = max(risk_signal, evidence_factor)

        if risk_signal >= thresholds.high_score or copied_percentage >= thresholds.high_copied:
            risk_level = RiskLevel.high
        elif risk_signal >= thresholds.medium_score or copied_percentage >= thresholds.medium_copied:
            risk_level = RiskLevel.medium
        else:
            risk_level = RiskLevel.low

        confidence = _clamp(
            (similarity_score * weights.similarity)
            + (copied_percentage * weights.copied)
            + (evidence_factor * weights.evidence)
            + (semantic_score * weights.semantic)
        )

        reasoning = _build_reasoning(
            copied_percentage,
            paragraphs,
            sentences,
            semantic_score,
            thresholds,
        )

        return RiskAssessment(
            risk_level=risk_level,
            confidence_score=confidence,
            reasoning=reasoning,
        )


def _build_reasoning(
    copied_percentage: float,
    paragraphs: int,
    sentences: int,
    semantic_score: float,
    thresholds: RiskAssessmentThresholds,
) -> list[str]:
    reasons: list[str] = []
    reasons.append(f"{int(round(copied_percentage * 100))}% of content appears copied")

    if paragraphs > 0:
        reasons.append(f"{paragraphs} matching paragraphs detected")
    if sentences > 0:
        reasons.append(f"{sentences} matching sentences detected")

    if semantic_score >= thresholds.strong_semantic:
        reasons.append("Strong semantic similarity found")

    return reasons


def _evidence_factor(
    paragraphs: int,
    sentences: int,
    thresholds: RiskAssessmentThresholds,
) -> float:
    paragraph_factor = min(paragraphs / max(thresholds.high_paragraphs, 1), 1.0)
    sentence_factor = min(sentences / max(thresholds.high_sentences, 1), 1.0)
    return _clamp((paragraph_factor * 0.6) + (sentence_factor * 0.4))


def _clamp(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
