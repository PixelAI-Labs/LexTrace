"""Evidence models for the Analysis Service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MatchedSentence(BaseModel):
    """Sentence-level match information with text location metadata."""

    original_text: str = Field(..., description="Sentence text from the original article.")
    candidate_text: str = Field(..., description="Sentence text from the candidate article.")
    original_start: int = Field(
        ...,
        ge=0,
        description="Start character offset of the original sentence in the source text.",
    )
    original_end: int = Field(
        ...,
        ge=0,
        description="End character offset of the original sentence in the source text.",
    )
    candidate_start: int = Field(
        ...,
        ge=0,
        description="Start character offset of the candidate sentence in the candidate text.",
    )
    candidate_end: int = Field(
        ...,
        ge=0,
        description="End character offset of the candidate sentence in the candidate text.",
    )
    original_sentence_index: int | None = Field(
        default=None,
        ge=0,
        description="Index of the sentence in the original article (0-based), if available.",
    )
    candidate_sentence_index: int | None = Field(
        default=None,
        ge=0,
        description="Index of the sentence in the candidate article (0-based), if available.",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score for the sentence match.",
    )
    match_type: Literal["exact", "fuzzy", "semantic"] = Field(
        ...,
        description="Primary matching strategy that produced this sentence match.",
    )


class MatchedParagraph(BaseModel):
    """Paragraph-level match information with nested sentence matches."""

    original_text: str = Field(..., description="Paragraph text from the original article.")
    candidate_text: str = Field(..., description="Paragraph text from the candidate article.")
    original_start: int = Field(
        ...,
        ge=0,
        description="Start character offset of the original paragraph in the source text.",
    )
    original_end: int = Field(
        ...,
        ge=0,
        description="End character offset of the original paragraph in the source text.",
    )
    candidate_start: int = Field(
        ...,
        ge=0,
        description="Start character offset of the candidate paragraph in the candidate text.",
    )
    candidate_end: int = Field(
        ...,
        ge=0,
        description="End character offset of the candidate paragraph in the candidate text.",
    )
    original_paragraph_index: int | None = Field(
        default=None,
        ge=0,
        description="Index of the paragraph in the original article (0-based), if available.",
    )
    candidate_paragraph_index: int | None = Field(
        default=None,
        ge=0,
        description="Index of the paragraph in the candidate article (0-based), if available.",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score for the paragraph match.",
    )
    match_type: Literal["exact", "fuzzy", "semantic", "mixed"] = Field(
        ...,
        description="Primary matching strategy for the paragraph match.",
    )
    matched_sentences: list[MatchedSentence] = Field(
        default_factory=list,
        description="Sentence-level matches contained within the paragraph.",
    )


class EvidenceItem(BaseModel):
    """Evidence for a single candidate article."""

    candidate_url: str = Field(..., description="Candidate article URL.")
    candidate_title: str | None = Field(default=None, description="Candidate article title, if available.")
    domain: str = Field(..., description="Root domain of the candidate URL.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall similarity score between original and candidate.",
    )
    copied_percentage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated fraction of content copied (0.0 to 1.0).",
    )
    matched_paragraphs: list[MatchedParagraph] = Field(
        default_factory=list,
        description="Paragraph-level evidence matches.",
    )
    matched_sentences: list[MatchedSentence] = Field(
        default_factory=list,
        description="Sentence-level evidence matches (flattened view).",
    )
    high_confidence_matches: int = Field(
        default=0,
        ge=0,
        description="Count of high-confidence matches for reporting.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional notes to assist report generation.",
    )


class EvidenceSummary(BaseModel):
    """Summary of evidence across all candidates."""

    total_candidates: int = Field(
        ...,
        ge=0,
        description="Number of candidates with evidence items.",
    )
    total_matched_paragraphs: int = Field(
        ...,
        ge=0,
        description="Total paragraph matches across all candidates.",
    )
    total_matched_sentences: int = Field(
        ...,
        ge=0,
        description="Total sentence matches across all candidates.",
    )
    high_confidence_matches: int = Field(
        default=0,
        ge=0,
        description="Total high-confidence matches across all candidates.",
    )
    items: list[EvidenceItem] = Field(
        default_factory=list,
        description="Detailed evidence items per candidate.",
    )
    summary: str | None = Field(
        default=None,
        description="Human-readable evidence summary for reporting.",
    )
