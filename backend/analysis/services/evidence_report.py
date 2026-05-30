"""Evidence report generator for the Analysis Service."""

from __future__ import annotations

from backend.analysis.schemas.evidence import EvidenceSummary
from backend.analysis.schemas.report import (
    EvidenceReport,
    EvidenceReportEntry,
    EvidenceReportSummary,
    ReportFormat,
)
from backend.analysis.schemas.responses import CandidateAnalysis
from backend.analysis.schemas.risk import RiskAssessment


class EvidenceReportGenerator:
    """Generate deterministic evidence reports from analysis inputs."""

    def __init__(self, report_format: ReportFormat = ReportFormat.text) -> None:
        self._format = report_format

    def generate(
        self,
        analysis: CandidateAnalysis,
        evidence: EvidenceSummary,
        assessment: RiskAssessment,
        *,
        report_format: ReportFormat | None = None,
    ) -> EvidenceReport:
        """Generate an evidence report in the requested format."""
        format_choice = report_format or self._format

        evidence_item = _select_evidence_item(evidence, analysis.candidate_url)
        evidence_entries = _build_entries(evidence_item)

        summary = EvidenceReportSummary(
            similarity_score=analysis.similarity_score,
            copied_percentage=analysis.copied_percentage,
            risk_level=assessment.risk_level,
            confidence_score=assessment.confidence_score,
            total_matches=len(evidence_entries),
            total_paragraphs=evidence.total_matched_paragraphs,
            total_sentences=evidence.total_matched_sentences,
            reasoning=list(assessment.reasoning),
        )

        if format_choice == ReportFormat.markdown:
            content = _render_markdown(analysis, summary, evidence_entries)
        else:
            content = _render_text(analysis, summary, evidence_entries)

        return EvidenceReport(
            format=format_choice,
            content=content,
            summary=summary,
            evidence=evidence_entries,
        )


def _select_evidence_item(evidence: EvidenceSummary, candidate_url: str):
    for item in evidence.items:
        if item.candidate_url == candidate_url:
            return item
    if len(evidence.items) == 1:
        return evidence.items[0]
    return None


def _build_entries(evidence_item) -> list[EvidenceReportEntry]:
    if evidence_item is None:
        return []

    entries: list[EvidenceReportEntry] = []
    if evidence_item.matched_sentences:
        for idx, match in enumerate(evidence_item.matched_sentences, start=1):
            entries.append(
                EvidenceReportEntry(
                    match_index=idx,
                    source="sentence",
                    match_type=match.match_type,
                    original_text=match.original_text,
                    candidate_text=match.candidate_text,
                    similarity_score=match.similarity_score,
                )
            )
        return entries

    for idx, match in enumerate(evidence_item.matched_paragraphs, start=1):
        entries.append(
            EvidenceReportEntry(
                match_index=idx,
                source="paragraph",
                match_type=match.match_type,
                original_text=match.original_text,
                candidate_text=match.candidate_text,
                similarity_score=match.similarity_score,
            )
        )

    return entries


def _render_text(
    analysis: CandidateAnalysis,
    summary: EvidenceReportSummary,
    evidence: list[EvidenceReportEntry],
) -> str:
    lines: list[str] = [
        "COPYGUARD EVIDENCE REPORT",
        "",
        "Original Article",
        "---------------",
        "URL: (not provided)",
        "",
        "Suspected Copy",
        "--------------",
        f"URL: {analysis.candidate_url}",
    ]
    if analysis.candidate_title:
        lines.append(f"Title: {analysis.candidate_title}")

    lines.extend(
        [
            "",
            "Analysis Summary",
            "----------------",
            f"Similarity Score: {_format_percent(summary.similarity_score)}",
            f"Copied Percentage: {_format_percent(summary.copied_percentage)}",
            f"Risk Level: {summary.risk_level.value.upper()}",
            f"Confidence Score: {_format_percent(summary.confidence_score)}",
            f"Matched Paragraphs: {summary.total_paragraphs}",
            f"Matched Sentences: {summary.total_sentences}",
        ]
    )

    if summary.reasoning:
        lines.append("Reasoning:")
        lines.extend(f"- {reason}" for reason in summary.reasoning)

    lines.extend(["", "Evidence", "--------"])

    if not evidence:
        lines.append("No evidence matches available.")
        return "\n".join(lines)

    for entry in evidence:
        lines.extend(
            [
                f"Match #{entry.match_index}",
                "Original:",
                f"\"{entry.original_text}\"",
                "",
                "Copied:",
                f"\"{entry.candidate_text}\"",
                "",
                f"Similarity: {_format_percent(entry.similarity_score)}",
                f"Match Type: {entry.match_type}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def _render_markdown(
    analysis: CandidateAnalysis,
    summary: EvidenceReportSummary,
    evidence: list[EvidenceReportEntry],
) -> str:
    lines: list[str] = [
        "# COPYGUARD EVIDENCE REPORT",
        "",
        "## Original Article",
        "- URL: (not provided)",
        "",
        "## Suspected Copy",
        f"- URL: {analysis.candidate_url}",
    ]
    if analysis.candidate_title:
        lines.append(f"- Title: {analysis.candidate_title}")

    lines.extend(
        [
            "",
            "## Analysis Summary",
            f"- Similarity Score: {_format_percent(summary.similarity_score)}",
            f"- Copied Percentage: {_format_percent(summary.copied_percentage)}",
            f"- Risk Level: {summary.risk_level.value.upper()}",
            f"- Confidence Score: {_format_percent(summary.confidence_score)}",
            f"- Matched Paragraphs: {summary.total_paragraphs}",
            f"- Matched Sentences: {summary.total_sentences}",
        ]
    )

    if summary.reasoning:
        lines.append("- Reasoning:")
        lines.extend(f"  - {reason}" for reason in summary.reasoning)

    lines.extend(["", "## Evidence"])

    if not evidence:
        lines.append("No evidence matches available.")
        return "\n".join(lines)

    for entry in evidence:
        lines.extend(
            [
                "",
                f"### Match #{entry.match_index}",
                f"**Original:** \"{entry.original_text}\"",
                "",
                f"**Copied:** \"{entry.candidate_text}\"",
                "",
                f"**Similarity:** {_format_percent(entry.similarity_score)}",
                f"**Match Type:** {entry.match_type}",
            ]
        )

    return "\n".join(lines)


def _format_percent(value: float) -> str:
    return f"{int(round(value * 100))}%"
