"""Unit tests for backend.discovery.schemas.search_result.

Covers: SearchResult field validation, SearchResultCollection assembly,
convenience properties, boundary conditions, and JSON round-trip serialization.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection


# ---------------------------------------------------------------------------
# TC1 — SearchResult full construction
# ---------------------------------------------------------------------------

def test_TC1_full_construction() -> None:
    """All fields populated in a single constructor call."""
    r = SearchResult(
        url="https://example.com/pirated-article",
        title="How to Learn Python Fast",
        description="A comprehensive guide to learning Python quickly.",
        domain="example.com",
        publish_date="2024-03-15",
        language="en",
        source_provider="google",
        is_paywalled=True,
        rank=1,
    )
    assert r.url == "https://example.com/pirated-article"
    assert r.title == "How to Learn Python Fast"
    assert r.description == "A comprehensive guide to learning Python quickly."
    assert r.domain == "example.com"
    assert r.publish_date == "2024-03-15"
    assert r.language == "en"
    assert r.source_provider == "google"
    assert r.is_paywalled is True
    assert r.rank == 1


# ---------------------------------------------------------------------------
# TC2 — SearchResult optional fields defaults
# ---------------------------------------------------------------------------

def test_TC2_optional_fields_default_to_null_false() -> None:
    """publish_date, language, rank default to None; is_paywalled defaults to False."""
    r = SearchResult(
        url="https://example.com/article",
        title="Article Title",
        description="Article description here.",
        domain="example.com",
        source_provider="google",
    )
    assert r.publish_date is None
    assert r.language is None
    assert r.rank is None
    assert r.is_paywalled is False


# ---------------------------------------------------------------------------
# TC3 — SearchResult validation: missing required fields
# ---------------------------------------------------------------------------

def test_TC3_url_required() -> None:
    """Missing url must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            title="Title",
            description="Desc",
            domain="x.com",
            source_provider="google",
        )
    assert "url" in str(exc.value).lower()


def test_TC3_title_required() -> None:
    """Missing title must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            description="Desc",
            domain="example.com",
            source_provider="google",
        )
    assert "title" in str(exc.value).lower()


def test_TC3_description_required() -> None:
    """Missing description must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="Title",
            domain="example.com",
            source_provider="google",
        )
    assert "description" in str(exc.value).lower()


def test_TC3_domain_required() -> None:
    """Missing domain must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="Title",
            description="Desc",
            source_provider="google",
        )
    assert "domain" in str(exc.value).lower()


def test_TC3_source_provider_required() -> None:
    """Missing source_provider must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="Title",
            description="Desc",
            domain="example.com",
        )
    assert "source_provider" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC4 — SearchResult: url validation
# ---------------------------------------------------------------------------

def test_TC4_url_must_be_valid_http_url() -> None:
    """Invalid URL format must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="not-a-valid-url",
            title="Title",
            description="Desc",
            domain="example.com",
            source_provider="google",
        )
    assert "url" in str(exc.value).lower()


def test_TC4_valid_url_formats_accepted() -> None:
    """HTTP and HTTPS URLs are both accepted."""
    for url in ["http://example.com", "https://example.com/path?a=1#anchor"]:
        r = SearchResult(
            url=url,
            title="T",
            description="D",
            domain="example.com",
            source_provider="google",
        )
        assert str(r.url) == url


# ---------------------------------------------------------------------------
# TC5 — SearchResult: description max_length boundary
# ---------------------------------------------------------------------------

def test_TC5_description_at_upper_bound() -> None:
    """description at exactly 1000 characters is valid."""
    r = SearchResult(
        url="https://example.com",
        title="Title",
        description="d" * 1000,
        domain="example.com",
        source_provider="google",
    )
    assert len(r.description) == 1000


def test_TC5_description_above_1000_raises() -> None:
    """description above 1000 characters must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="Title",
            description="d" * 1001,
            domain="example.com",
            source_provider="google",
        )
    assert "description" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC6 — SearchResult: title max_length boundary
# ---------------------------------------------------------------------------

def test_TC6_title_at_upper_bound() -> None:
    """title at exactly 500 characters is valid."""
    r = SearchResult(
        url="https://example.com",
        title="t" * 500,
        description="D",
        domain="example.com",
        source_provider="google",
    )
    assert len(r.title) == 500


def test_TC6_title_above_500_raises() -> None:
    """title above 500 characters must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="t" * 501,
            description="D",
            domain="example.com",
            source_provider="google",
        )
    assert "title" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC7 — SearchResult: rank validation
# ---------------------------------------------------------------------------

def test_TC7_rank_must_be_positive() -> None:
    """rank=0 must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="Title",
            description="Desc",
            domain="example.com",
            source_provider="google",
            rank=0,
        )
    assert "rank" in str(exc.value).lower()


def test_TC7_rank_negative_raises() -> None:
    """Negative rank must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResult(
            url="https://example.com",
            title="Title",
            description="Desc",
            domain="example.com",
            source_provider="google",
            rank=-1,
        )
    assert "rank" in str(exc.value).lower()


def test_TC7_rank_one_is_valid() -> None:
    """rank=1 is valid (first position)."""
    r = SearchResult(
        url="https://example.com",
        title="Title",
        description="Desc",
        domain="example.com",
        source_provider="google",
        rank=1,
    )
    assert r.rank == 1


# ---------------------------------------------------------------------------
# TC8 — SearchResult: JSON round-trip
# ---------------------------------------------------------------------------

def test_TC8_json_roundtrip() -> None:
    """SearchResult must survive a full JSON serialization round-trip."""
    r = SearchResult(
        url="https://example.com/article",
        title="Python Tutorial",
        description="Learn Python fast.",
        domain="example.com",
        publish_date="2024-01-15",
        language="en",
        source_provider="google",
        is_paywalled=False,
        rank=3,
    )
    parsed = SearchResult.model_validate_json(r.model_dump_json())
    assert str(parsed.url) == str(r.url)
    assert parsed.title == r.title
    assert parsed.description == r.description
    assert parsed.domain == r.domain
    assert parsed.publish_date == r.publish_date
    assert parsed.language == r.language
    assert parsed.source_provider == r.source_provider
    assert parsed.is_paywalled == r.is_paywalled
    assert parsed.rank == r.rank


def test_TC8_json_roundtrip_nullable_fields() -> None:
    """Results with null optional fields survive round-trip."""
    r = SearchResult(
        url="https://example.com",
        title="T",
        description="D",
        domain="example.com",
        source_provider="google",
        rank=None,
    )
    parsed = SearchResult.model_validate_json(r.model_dump_json())
    assert parsed.publish_date is None
    assert parsed.language is None
    assert parsed.rank is None


# ---------------------------------------------------------------------------
# TC9 — SearchResultCollection: full construction
# ---------------------------------------------------------------------------

def test_TC9_full_construction() -> None:
    """All fields populated with nested SearchResult objects."""
    result = SearchResult(
        url="https://example.com/article",
        title="Title",
        description="Desc",
        domain="example.com",
        source_provider="google",
        rank=1,
    )
    coll = SearchResultCollection(
        query_executed="python tutorial",
        provider_used="google",
        total_results=50,
        results=[result],
        search_time_ms=234,
    )
    assert coll.query_executed == "python tutorial"
    assert coll.provider_used == "google"
    assert coll.total_results == 50
    assert len(coll.results) == 1
    assert coll.search_time_ms == 234


# ---------------------------------------------------------------------------
# TC10 — SearchResultCollection: empty results list
# ---------------------------------------------------------------------------

def test_TC10_empty_results_list_valid() -> None:
    """An empty results list is valid (e.g., no matches found)."""
    coll = SearchResultCollection(
        query_executed="xyzzy nonsense query",
        provider_used="google",
        total_results=0,
        results=[],
        search_time_ms=50,
    )
    assert coll.results == []
    assert coll.total_results == 0


# ---------------------------------------------------------------------------
# TC11 — SearchResultCollection: negative total_results raises
# ---------------------------------------------------------------------------

def test_TC11_negative_total_results_raises() -> None:
    """Negative total_results must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchResultCollection(
            query_executed="test",
            provider_used="google",
            total_results=-1,
            results=[],
        )
    assert "total_results" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC12 — SearchResultCollection: JSON round-trip
# ---------------------------------------------------------------------------

def test_TC12_json_roundtrip_full() -> None:
    """SearchResultCollection must survive a full JSON serialization round-trip."""
    r = SearchResult(
        url="https://example.com/article",
        title="How to Code",
        description="A guide to coding.",
        domain="example.com",
        source_provider="google",
        rank=2,
    )
    coll = SearchResultCollection(
        query_executed="coding guide",
        provider_used="google",
        total_results=10,
        results=[r],
        search_time_ms=150,
    )
    parsed = SearchResultCollection.model_validate_json(coll.model_dump_json())
    assert parsed.query_executed == coll.query_executed
    assert parsed.provider_used == coll.provider_used
    assert parsed.total_results == coll.total_results
    assert len(parsed.results) == 1
    assert parsed.search_time_ms == 150


def test_TC12_json_roundtrip_empty() -> None:
    """Empty SearchResultCollection round-trips correctly."""
    coll = SearchResultCollection(
        query_executed="empty query",
        provider_used="duckduckgo",
        total_results=0,
        results=[],
        search_time_ms=0,
    )
    parsed = SearchResultCollection.model_validate_json(coll.model_dump_json())
    assert parsed.results == []


# ---------------------------------------------------------------------------
# TC13 — SearchResultCollection: convenience properties
# ---------------------------------------------------------------------------

def test_TC13_urls_property() -> None:
    """urls returns list of all result URLs as strings."""
    coll = SearchResultCollection(
        query_executed="test",
        provider_used="google",
        total_results=3,
        results=[
            SearchResult(
                url="https://a.com",
                title="A",
                description="D",
                domain="a.com",
                source_provider="google",
            ),
            SearchResult(
                url="https://b.com/path",
                title="B",
                description="D",
                domain="b.com",
                source_provider="google",
            ),
        ],
        search_time_ms=10,
    )
    assert coll.urls == ["https://a.com", "https://b.com/path"]


def test_TC13_domains_property() -> None:
    """domains returns list of all result domains as strings."""
    coll = SearchResultCollection(
        query_executed="test",
        provider_used="google",
        total_results=2,
        results=[
            SearchResult(
                url="https://blog.example.com/post",
                title="A",
                description="D",
                domain="blog.example.com",
                source_provider="google",
            ),
            SearchResult(
                url="https://news.example.org/article",
                title="B",
                description="D",
                domain="news.example.org",
                source_provider="google",
            ),
        ],
        search_time_ms=10,
    )
    assert coll.domains == ["blog.example.com", "news.example.org"]


def test_TC13_properties_empty_collection() -> None:
    """urls and domains return empty lists when results is empty."""
    coll = SearchResultCollection(
        query_executed="test",
        provider_used="google",
        total_results=0,
        results=[],
        search_time_ms=0,
    )
    assert coll.urls == []
    assert coll.domains == []