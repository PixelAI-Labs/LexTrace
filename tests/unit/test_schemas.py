"""Unit tests for discovery schemas.

Covers request validation, response model construction,
field constraints, edge cases, and serialization shape.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from copyguard.discovery.schemas import (
    CandidateArticle,
    DiscoveryMetadata,
    DiscoveryOptions,
    DiscoveryRequest,
    DiscoveryResponse,
)


# ---------------------------------------------------------------------------
# TC1 — DiscoveryOptions defaults
# ---------------------------------------------------------------------------

def test_TC1_options_default_values() -> None:
    """All optional fields must resolve to their documented defaults."""
    opts = DiscoveryOptions()
    assert opts.max_candidates == 20
    assert opts.search_depth == "shallow"
    assert opts.include_content is True


def test_TC1_options_can_be_overridden() -> None:
    """Explicit values must override defaults."""
    opts = DiscoveryOptions(max_candidates=5, search_depth="deep", include_content=False)
    assert opts.max_candidates == 5
    assert opts.search_depth == "deep"
    assert opts.include_content is False


# ---------------------------------------------------------------------------
# TC2 — DiscoveryRequest valid input
# ---------------------------------------------------------------------------

def test_TC2_valid_request_minimal() -> None:
    """article_text only — all else optional and defaulted."""
    req = DiscoveryRequest(article_text="x" * 100)
    assert req.article_text == "x" * 100
    assert req.title is None
    assert req.source_url is None
    assert req.options.max_candidates == 20


def test_TC2_valid_request_full() -> None:
    """Full request with all fields populated."""
    req = DiscoveryRequest(
        article_text="x" * 100,
        title="Test Article",
        source_url="https://example.com/article",
        options=DiscoveryOptions(max_candidates=10),
    )
    assert req.title == "Test Article"
    assert req.source_url == "https://example.com/article"
    assert req.options.max_candidates == 10


# ---------------------------------------------------------------------------
# TC3 — DiscoveryRequest validation errors
# ---------------------------------------------------------------------------

def test_TC3_article_text_too_short_raises() -> None:
    """article_text below 100 chars must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryRequest(article_text="short")
    errors = exc.value.errors()
    assert any("article_text" in str(e) and "min_length" in str(e) for e in errors)


def test_TC3_article_text_too_long_raises() -> None:
    """article_text above 50 000 chars must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryRequest(article_text="x" * 50_001)
    assert exc.value.error_count() == 1


def test_TC3_article_text_at_lower_bound_accepted() -> None:
    """Exactly 100-character article_text is valid."""
    req = DiscoveryRequest(article_text="x" * 100)
    assert len(req.article_text) == 100


def test_TC3_article_text_at_upper_bound_accepted() -> None:
    """Exactly 50 000-character article_text is valid."""
    req = DiscoveryRequest(article_text="x" * 50_000)
    assert len(req.article_text) == 50_000


def test_TC3_title_too_long_raises() -> None:
    """title above 500 chars must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryRequest(article_text="x" * 100, title="y" * 501)
    assert "title" in str(exc.value).lower()


def test_TC3_source_url_invalid_format_raises() -> None:
    """source_url must be a valid URL if provided."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryRequest(article_text="x" * 100, source_url="not-a-url")
    assert "source_url" in str(exc.value).lower()


def test_TC3_source_url_valid_formats_accepted() -> None:
    """HTTP and HTTPS URLs are both accepted."""
    for url in ["http://example.com", "https://example.com/path?a=1"]:
        req = DiscoveryRequest(article_text="x" * 100, source_url=url)
        assert req.source_url == url


# ---------------------------------------------------------------------------
# TC4 — DiscoveryOptions validation errors
# ---------------------------------------------------------------------------

def test_TC4_max_candidates_below_min_raises() -> None:
    """max_candidates below 1 must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryOptions(max_candidates=0)
    assert "max_candidates" in str(exc.value).lower()


def test_TC4_max_candidates_above_max_raises() -> None:
    """max_candidates above 50 must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryOptions(max_candidates=51)
    assert "max_candidates" in str(exc.value).lower()


def test_TC4_search_depth_invalid_value_raises() -> None:
    """search_depth must be 'shallow' or 'deep'."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryOptions(search_depth="medium")
    assert "search_depth" in str(exc.value).lower()


def test_TC4_search_depth_both_values_accepted() -> None:
    """'shallow' and 'deep' must both be accepted."""
    for depth in ["shallow", "deep"]:
        opts = DiscoveryOptions(search_depth=depth)
        assert opts.search_depth == depth


# ---------------------------------------------------------------------------
# TC5 — CandidateArticle validation
# ---------------------------------------------------------------------------

def test_TC5_candidate_all_fields_valid() -> None:
    """Full CandidateArticle with all optional fields."""
    cand = CandidateArticle(
        rank=1,
        url="https://example.com/pirated-article",
        domain="example.com",
        title="Pirated Article Title",
        rank_score=0.95,
        keyword_coverage=0.88,
        content_preview="This is the first 300 chars of the article content...",
        text_length=1245,
        publish_date="2024-03-15",
        language="en",
    )
    assert cand.rank == 1
    assert cand.rank_score == 0.95
    assert cand.language == "en"


def test_TC5_candidate_optional_fields_null() -> None:
    """title, publish_date, language can all be null."""
    cand = CandidateArticle(
        rank=1,
        url="https://example.com/thing",
        domain="example.com",
        rank_score=0.5,
        keyword_coverage=0.3,
        content_preview="...",
        text_length=100,
    )
    assert cand.title is None
    assert cand.publish_date is None
    assert cand.language is None


def test_TC5_rank_score_below_zero_raises() -> None:
    """rank_score must be >= 0.0."""
    with pytest.raises(ValidationError) as exc:
        CandidateArticle(
            rank=1, url="https://x.com", domain="x.com",
            rank_score=-0.01, keyword_coverage=0.5,
            content_preview="...", text_length=100,
        )
    assert "rank_score" in str(exc.value).lower()


def test_TC5_rank_score_above_one_raises() -> None:
    """rank_score must be <= 1.0."""
    with pytest.raises(ValidationError) as exc:
        CandidateArticle(
            rank=1, url="https://x.com", domain="x.com",
            rank_score=1.01, keyword_coverage=0.5,
            content_preview="...", text_length=100,
        )
    assert "rank_score" in str(exc.value).lower()


def test_TC5_keyword_coverage_at_boundaries() -> None:
    """keyword_coverage must accept 0.0 and 1.0."""
    for score in [0.0, 1.0]:
        cand = CandidateArticle(
            rank=1, url="https://x.com", domain="x.com",
            rank_score=score, keyword_coverage=score,
            content_preview="...", text_length=100,
        )
        assert cand.keyword_coverage == score


def test_TC5_rank_must_be_positive() -> None:
    """rank must be >= 1."""
    with pytest.raises(ValidationError) as exc:
        CandidateArticle(
            rank=0, url="https://x.com", domain="x.com",
            rank_score=0.5, keyword_coverage=0.5,
            content_preview="...", text_length=100,
        )
    assert "rank" in str(exc.value).lower()


def test_TC5_text_length_must_be_non_negative() -> None:
    """text_length must be >= 0 (empty article is valid)."""
    cand = CandidateArticle(
        rank=1, url="https://x.com", domain="x.com",
        rank_score=0.5, keyword_coverage=0.5,
        content_preview="", text_length=0,
    )
    assert cand.text_length == 0


# ---------------------------------------------------------------------------
# TC6 — DiscoveryMetadata validation
# ---------------------------------------------------------------------------

def test_TC6_metadata_all_fields() -> None:
    """Full metadata with all timing fields."""
    meta = DiscoveryMetadata(
        total_candidates=20,
        queries_generated=5,
        extraction_time_ms=4821,
        search_time_ms=1340,
        total_time_ms=6261,
    )
    assert meta.total_candidates == 20
    assert meta.total_time_ms == 6261


def test_TC6_metadata_zero_values_accepted() -> None:
    """Zero is valid for all timing and counter fields."""
    meta = DiscoveryMetadata(
        total_candidates=0, queries_generated=0,
        extraction_time_ms=0, search_time_ms=0, total_time_ms=0,
    )
    assert meta.total_candidates == 0


def test_TC6_metadata_negative_raises() -> None:
    """Negative values on any field raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryMetadata(
            total_candidates=-1, queries_generated=0,
            extraction_time_ms=0, search_time_ms=0, total_time_ms=0,
        )
    assert "total_candidates" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC7 — DiscoveryResponse model composition
# ---------------------------------------------------------------------------

def test_TC7_response_completed() -> None:
    """A fully populated 'completed' response."""
    resp = DiscoveryResponse(
        request_id="550e8400-e29b-41d4-a716-446655440000",
        status="completed",
        original_title="Original Article Title",
        queries_used=["\"Original Title\"", "keyword1 keyword2"],
        total_urls_collected=42,
        candidates=[
            CandidateArticle(
                rank=1,
                url="https://example.com/pirated",
                domain="example.com",
                rank_score=0.94,
                keyword_coverage=0.87,
                content_preview="Preview text...",
                text_length=1245,
            ),
        ],
        metadata=DiscoveryMetadata(
            total_candidates=1,
            queries_generated=5,
            extraction_time_ms=4821,
            search_time_ms=1340,
            total_time_ms=6261,
        ),
    )
    assert resp.status == "completed"
    assert len(resp.candidates) == 1
    assert resp.metadata.total_time_ms == 6261


def test_TC7_response_status_values() -> None:
    """status must be one of 'completed', 'partial', 'failed'."""
    base = dict(
        request_id="uid", total_urls_collected=0, candidates=[],
        metadata=DiscoveryMetadata(0, 0, 0, 0, 0),
    )
    for status in ["completed", "partial", "failed"]:
        resp = DiscoveryResponse(**base, status=status)
        assert resp.status == status


def test_TC7_response_invalid_status_raises() -> None:
    """Unknown status value raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        DiscoveryResponse(
            request_id="uid",
            status="finished",  # type: ignore[arg-type]
            total_urls_collected=0,
            candidates=[],
            metadata=DiscoveryMetadata(0, 0, 0, 0, 0),
        )
    assert "status" in str(exc.value).lower()


def test_TC7_response_no_candidates_is_valid() -> None:
    """An empty candidate list is valid (e.g., status='failed')."""
    resp = DiscoveryResponse(
        request_id="uid",
        status="failed",
        original_title=None,
        queries_used=[],
        total_urls_collected=0,
        candidates=[],
        metadata=DiscoveryMetadata(0, 0, 0, 0, 0),
    )
    assert resp.candidates == []
    assert resp.status == "failed"


# ---------------------------------------------------------------------------
# TC8 — Serialization / deserialization round-trips
# ---------------------------------------------------------------------------

def test_TC8_request_json_roundtrip() -> None:
    """DiscoveryRequest must serialize and parse back identically via Pydantic model."""
    req = DiscoveryRequest(
        article_text="x" * 200,
        title="My Article",
        source_url="https://example.com/article",
        options=DiscoveryOptions(max_candidates=10),
    )
    payload = req.model_dump_json()
    parsed = DiscoveryRequest.model_validate_json(payload)
    assert parsed.article_text == req.article_text
    assert parsed.title == req.title
    assert parsed.options.max_candidates == 10


def test_TC8_response_json_roundtrip() -> None:
    """DiscoveryResponse must survive a full JSON serialization round-trip."""
    resp = DiscoveryResponse(
        request_id="uid",
        status="completed",
        original_title="Test",
        queries_used=["query1", "query2"],
        total_urls_collected=10,
        candidates=[],
        metadata=DiscoveryMetadata(0, 2, 100, 50, 150),
    )
    parsed = DiscoveryResponse.model_validate_json(resp.model_dump_json())
    assert parsed.request_id == resp.request_id
    assert parsed.status == resp.status
    assert len(parsed.candidates) == 0


def test_TC8_candidate_article_json_roundtrip() -> None:
    """CandidateArticle must survive JSON round-trip."""
    cand = CandidateArticle(
        rank=1,
        url="https://example.com/article",
        domain="example.com",
        title=None,
        rank_score=0.75,
        keyword_coverage=0.60,
        content_preview="Some content...",
        text_length=500,
        publish_date=None,
        language=None,
    )
    parsed = CandidateArticle.model_validate_json(cand.model_dump_json())
    assert parsed.rank_score == cand.rank_score
    assert parsed.title is None


# ---------------------------------------------------------------------------
# TC9 — Content preview max_length constraint
# ---------------------------------------------------------------------------

def test_TC9_content_preview_too_long_raises() -> None:
    """content_preview exceeding 500 characters must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        CandidateArticle(
            rank=1, url="https://x.com", domain="x.com",
            rank_score=0.5, keyword_coverage=0.5,
            content_preview="x" * 501, text_length=501,
        )
    assert "content_preview" in str(exc.value).lower()


def test_TC9_content_preview_at_boundaries() -> None:
    """Empty string and 500-char limit must both be accepted."""
    for length in [0, 500]:
        cand = CandidateArticle(
            rank=1, url="https://x.com", domain="x.com",
            rank_score=0.5, keyword_coverage=0.5,
            content_preview="x" * length, text_length=length,
        )
        assert len(cand.content_preview) == length