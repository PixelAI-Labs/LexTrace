"""Article similarity analysis for the Analysis Service."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Iterable

from pydantic import BaseModel, Field

from backend.analysis.schemas.evidence import EvidenceItem, MatchedParagraph, MatchedSentence
from backend.analysis.schemas.requests import CandidateInput
from backend.analysis.schemas.responses import CandidateAnalysis, RiskLevel, SimilarityBreakdown
from backend.analysis.schemas.similarity import SimilarityResult, SimilarityStrategy
from backend.discovery.utils.text_utils import extract_sentences, normalize, strip_html


_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


@dataclass(frozen=True, slots=True)
class SimilarityThresholds:
    """Configurable thresholds for similarity detection."""

    sentence_match: float = 0.84
    paragraph_match: float = 0.8
    exact_match: float = 0.97
    min_sentence_chars: int = 20
    min_paragraph_chars: int = 80
    min_token_overlap: float = 0.4
    max_sentence_matches: int = 120
    max_paragraph_matches: int = 40
    max_candidate_sentences: int = 250
    max_candidate_paragraphs: int = 80
    risk_medium: float = 0.55
    risk_high: float = 0.7
    risk_critical: float = 0.85


@dataclass(frozen=True, slots=True)
class SimilarityWeights:
    """Weights used to combine similarity signals."""

    tfidf_weight: float = 0.6
    copy_weight: float = 0.4


@dataclass(frozen=True, slots=True)
class SimilarityConfig:
    """Top-level configuration for article similarity analysis."""

    thresholds: SimilarityThresholds = SimilarityThresholds()
    weights: SimilarityWeights = SimilarityWeights()
    paragraph_sentence_window: int = 3


@dataclass(frozen=True, slots=True)
class _TextSegment:
    text: str
    start: int
    end: int
    index: int


@dataclass(frozen=True, slots=True)
class _ParagraphSegment:
    text: str
    start: int
    end: int
    index: int
    sentence_indices: tuple[int, ...]


class ArticleSimilarityOutcome(BaseModel):
    """Combined output for a single candidate analysis."""

    analysis: CandidateAnalysis
    evidence: EvidenceItem
    similarity: SimilarityResult


class ArticleSimilarityAnalyzer:
    """Deterministic article similarity analysis (TF-IDF + fuzzy matching)."""

    def __init__(self, config: SimilarityConfig | None = None) -> None:
        self._config = config or SimilarityConfig()

    def analyze(self, original_article: str, candidate: CandidateInput) -> ArticleSimilarityOutcome:
        """Analyze a candidate article against the original content."""
        thresholds = self._config.thresholds
        weights = self._config.weights

        original_text = _clean_text(original_article)
        candidate_text = _clean_text(candidate.content)

        original_sentences = _split_sentences(original_text, thresholds.min_sentence_chars)
        candidate_sentences = _split_sentences(candidate_text, thresholds.min_sentence_chars)

        candidate_sentences = _limit_segments(candidate_sentences, thresholds.max_candidate_sentences)

        sentence_matches = _match_sentences(
            original_sentences,
            candidate_sentences,
            thresholds,
        )

        original_paragraphs = _group_paragraphs(
            original_sentences,
            self._config.paragraph_sentence_window,
            thresholds.min_paragraph_chars,
        )
        candidate_paragraphs = _group_paragraphs(
            candidate_sentences,
            self._config.paragraph_sentence_window,
            thresholds.min_paragraph_chars,
        )

        candidate_paragraphs = _limit_paragraphs(candidate_paragraphs, thresholds.max_candidate_paragraphs)

        paragraph_matches = _match_paragraphs(
            original_paragraphs,
            candidate_paragraphs,
            sentence_matches,
            thresholds,
        )

        exact_chars, fuzzy_chars = _match_char_totals(sentence_matches)
        total_chars = max(len(original_text), 1)
        exact_score = min(exact_chars / total_chars, 1.0)
        fuzzy_score = min(fuzzy_chars / total_chars, 1.0)
        copied_percentage = min(exact_score + fuzzy_score, 1.0)

        tfidf_score = _tfidf_similarity(original_text, candidate_text)
        similarity_score = _weighted_similarity(tfidf_score, copied_percentage, weights)

        breakdown = SimilarityBreakdown(
            exact=exact_score,
            fuzzy=fuzzy_score,
            semantic=0.0,
        )

        risk_level = _risk_level(similarity_score, thresholds)

        candidate_analysis = CandidateAnalysis(
            candidate_url=candidate.url,
            candidate_title=candidate.title,
            domain=candidate.domain,
            similarity_score=similarity_score,
            copied_percentage=copied_percentage,
            breakdown=breakdown,
            risk_level=risk_level,
        )

        evidence_item = EvidenceItem(
            candidate_url=candidate.url,
            candidate_title=candidate.title,
            domain=candidate.domain,
            similarity_score=similarity_score,
            copied_percentage=copied_percentage,
            matched_paragraphs=paragraph_matches,
            matched_sentences=sentence_matches,
            high_confidence_matches=_count_high_confidence(sentence_matches, thresholds),
        )

        similarity_result = SimilarityResult(
            strategy=SimilarityStrategy.fuzzy,
            similarity_score=similarity_score,
            copied_percentage=copied_percentage,
            matched_paragraphs=len(paragraph_matches),
            matched_sentences=len(sentence_matches),
            metadata={
                "tfidf_score": round(tfidf_score, 4),
                "sentence_match_threshold": thresholds.sentence_match,
                "paragraph_match_threshold": thresholds.paragraph_match,
            },
        )

        return ArticleSimilarityOutcome(
            analysis=candidate_analysis,
            evidence=evidence_item,
            similarity=similarity_result,
        )


def _clean_text(text: str) -> str:
    return normalize(strip_html(text))


def _split_sentences(text: str, min_chars: int) -> list[_TextSegment]:
    sentences = [segment.strip() for segment in extract_sentences(text) if segment.strip()]
    filtered = [s for s in sentences if len(s) >= min_chars]
    segments: list[_TextSegment] = []
    cursor = 0
    for idx, sentence in enumerate(filtered):
        start = text.find(sentence, cursor)
        if start == -1:
            start = cursor
        end = start + len(sentence)
        cursor = end
        segments.append(_TextSegment(sentence, start, end, idx))
    return segments


def _group_paragraphs(
    sentences: list[_TextSegment],
    window: int,
    min_chars: int,
) -> list[_ParagraphSegment]:
    paragraphs: list[_ParagraphSegment] = []
    for idx in range(0, len(sentences), window):
        chunk = sentences[idx : idx + window]
        if not chunk:
            continue
        text = " ".join(segment.text for segment in chunk).strip()
        if len(text) < min_chars:
            continue
        start = chunk[0].start
        end = chunk[-1].end
        sentence_indices = tuple(segment.index for segment in chunk)
        paragraphs.append(
            _ParagraphSegment(
                text=text,
                start=start,
                end=end,
                index=len(paragraphs),
                sentence_indices=sentence_indices,
            )
        )
    return paragraphs


def _limit_segments(segments: list[_TextSegment], limit: int) -> list[_TextSegment]:
    if len(segments) <= limit:
        return segments
    return sorted(segments, key=lambda seg: len(seg.text), reverse=True)[:limit]


def _limit_paragraphs(paragraphs: list[_ParagraphSegment], limit: int) -> list[_ParagraphSegment]:
    if len(paragraphs) <= limit:
        return paragraphs
    return sorted(paragraphs, key=lambda seg: len(seg.text), reverse=True)[:limit]


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _token_overlap(tokens_a: list[str], tokens_b: list[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    overlap = len(set_a.intersection(set_b))
    return overlap / max(min(len(set_a), len(set_b)), 1)


def _match_sentences(
    original: list[_TextSegment],
    candidates: list[_TextSegment],
    thresholds: SimilarityThresholds,
) -> list[MatchedSentence]:
    matches: list[MatchedSentence] = []
    candidate_tokens = [_tokenize(segment.text) for segment in candidates]
    used_candidates: set[int] = set()

    for original_segment in original:
        original_tokens = _tokenize(original_segment.text)
        best_index = None
        best_score = 0.0

        for idx, candidate_segment in enumerate(candidates):
            if idx in used_candidates:
                continue
            overlap = _token_overlap(original_tokens, candidate_tokens[idx])
            if overlap < thresholds.min_token_overlap:
                continue
            score = SequenceMatcher(None, original_segment.text, candidate_segment.text).ratio()
            if score > best_score:
                best_score = score
                best_index = idx
            if score >= thresholds.exact_match:
                break

        if best_index is None or best_score < thresholds.sentence_match:
            continue

        candidate_segment = candidates[best_index]
        used_candidates.add(best_index)
        match_type = "exact" if best_score >= thresholds.exact_match else "fuzzy"
        matches.append(
            MatchedSentence(
                original_text=original_segment.text,
                candidate_text=candidate_segment.text,
                original_start=original_segment.start,
                original_end=original_segment.end,
                candidate_start=candidate_segment.start,
                candidate_end=candidate_segment.end,
                original_sentence_index=original_segment.index,
                candidate_sentence_index=candidate_segment.index,
                similarity_score=best_score,
                match_type=match_type,
            )
        )
        if len(matches) >= thresholds.max_sentence_matches:
            break

    return matches


def _match_paragraphs(
    original: list[_ParagraphSegment],
    candidates: list[_ParagraphSegment],
    sentence_matches: list[MatchedSentence],
    thresholds: SimilarityThresholds,
) -> list[MatchedParagraph]:
    matches: list[MatchedParagraph] = []
    candidate_tokens = [_tokenize(segment.text) for segment in candidates]
    used_candidates: set[int] = set()

    sentence_lookup = _index_sentence_matches(sentence_matches)

    for original_segment in original:
        original_tokens = _tokenize(original_segment.text)
        best_index = None
        best_score = 0.0

        for idx, candidate_segment in enumerate(candidates):
            if idx in used_candidates:
                continue
            overlap = _token_overlap(original_tokens, candidate_tokens[idx])
            if overlap < thresholds.min_token_overlap:
                continue
            score = SequenceMatcher(None, original_segment.text, candidate_segment.text).ratio()
            if score > best_score:
                best_score = score
                best_index = idx
            if score >= thresholds.exact_match:
                break

        if best_index is None or best_score < thresholds.paragraph_match:
            continue

        candidate_segment = candidates[best_index]
        used_candidates.add(best_index)

        matched_sentences = _sentences_for_paragraphs(
            sentence_lookup,
            original_segment.sentence_indices,
            candidate_segment.sentence_indices,
        )

        match_type = _paragraph_match_type(best_score, matched_sentences, thresholds)

        matches.append(
            MatchedParagraph(
                original_text=original_segment.text,
                candidate_text=candidate_segment.text,
                original_start=original_segment.start,
                original_end=original_segment.end,
                candidate_start=candidate_segment.start,
                candidate_end=candidate_segment.end,
                original_paragraph_index=original_segment.index,
                candidate_paragraph_index=candidate_segment.index,
                similarity_score=best_score,
                match_type=match_type,
                matched_sentences=matched_sentences,
            )
        )
        if len(matches) >= thresholds.max_paragraph_matches:
            break

    return matches


def _index_sentence_matches(matches: list[MatchedSentence]) -> dict[tuple[int, int], MatchedSentence]:
    lookup: dict[tuple[int, int], MatchedSentence] = {}
    for match in matches:
        if match.original_sentence_index is None or match.candidate_sentence_index is None:
            continue
        key = (match.original_sentence_index, match.candidate_sentence_index)
        lookup[key] = match
    return lookup


def _sentences_for_paragraphs(
    lookup: dict[tuple[int, int], MatchedSentence],
    original_indices: Iterable[int],
    candidate_indices: Iterable[int],
) -> list[MatchedSentence]:
    results: list[MatchedSentence] = []
    for original_index in original_indices:
        for candidate_index in candidate_indices:
            match = lookup.get((original_index, candidate_index))
            if match is not None:
                results.append(match)
    return results


def _paragraph_match_type(
    score: float,
    matched_sentences: list[MatchedSentence],
    thresholds: SimilarityThresholds,
) -> str:
    if score >= thresholds.exact_match:
        return "exact"
    if not matched_sentences:
        return "fuzzy"
    types = {match.match_type for match in matched_sentences}
    if len(types) > 1:
        return "mixed"
    return types.pop()


def _match_char_totals(matches: list[MatchedSentence]) -> tuple[int, int]:
    exact_chars = 0
    fuzzy_chars = 0
    for match in matches:
        if match.match_type == "exact":
            exact_chars += len(match.original_text)
        else:
            fuzzy_chars += len(match.original_text)
    return exact_chars, fuzzy_chars


def _count_high_confidence(matches: list[MatchedSentence], thresholds: SimilarityThresholds) -> int:
    return sum(1 for match in matches if match.similarity_score >= thresholds.exact_match)


def _risk_level(score: float, thresholds: SimilarityThresholds) -> RiskLevel:
    if score >= thresholds.risk_critical:
        return RiskLevel.critical
    if score >= thresholds.risk_high:
        return RiskLevel.high
    if score >= thresholds.risk_medium:
        return RiskLevel.medium
    return RiskLevel.low


def _weighted_similarity(tfidf_score: float, copied_percentage: float, weights: SimilarityWeights) -> float:
    combined = (tfidf_score * weights.tfidf_weight) + (copied_percentage * weights.copy_weight)
    return min(max(combined, 0.0), 1.0)


def _tfidf_similarity(original_text: str, candidate_text: str) -> float:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return SequenceMatcher(None, original_text, candidate_text).ratio()

    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([original_text, candidate_text])
        score = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return float(score)
    except ValueError:
        return 0.0
