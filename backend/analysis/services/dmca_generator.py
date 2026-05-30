"""DMCA notice generation service."""

from __future__ import annotations

from pathlib import Path

from backend.analysis.schemas.dmca import DmcaNotice, DmcaRequest
from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.risk import RiskAssessment
from backend.analysis.schemas.responses import CandidateAnalysis


class DmcaGeneratorService:
    """Template-based DMCA notice generator."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self._templates_dir = templates_dir or (base_dir / "templates")

    def generate(
        self,
        request: DmcaRequest,
        assessment: RiskAssessment,
        evidence: EvidenceSummary,
        *,
        template_name: str = "dmca_standard.txt",
        analysis: CandidateAnalysis | None = None,
    ) -> DmcaNotice:
        """Generate a DMCA notice using the specified template."""
        template_path = self._templates_dir / template_name
        template = template_path.read_text(encoding="utf-8")

        matched_paragraphs = evidence.total_matched_paragraphs
        matched_sentences = evidence.total_matched_sentences
        similarity_score = _percent(analysis.similarity_score if analysis else 0.0)
        copied_percentage = _percent(analysis.copied_percentage if analysis else 0.0)

        body = template.format(
            creator_name=request.creator_name,
            creator_email=request.creator_email,
            creator_address=request.creator_address,
            original_url=request.original_url,
            infringing_url=request.infringing_url,
            risk_level=assessment.risk_level.value.upper(),
            similarity_score=similarity_score,
            copied_percentage=copied_percentage,
            matched_paragraphs=matched_paragraphs,
            matched_sentences=matched_sentences,
        )

        subject_line = f"DMCA Takedown Notice for {request.infringing_url}"
        summary = (
            f"Risk {assessment.risk_level.value.upper()} with "
            f"{matched_paragraphs} matched paragraphs and {matched_sentences} matched sentences."
        )

        return DmcaNotice(
            subject=subject_line,
            body=body,
            summary=summary,
            risk_level=assessment.risk_level,
        )


def _percent(value: float) -> str:
    return f"{int(round(value * 100))}%"


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
