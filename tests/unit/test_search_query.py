"""Unit tests for backend.discovery.schemas.search_query.

Covers: SearchQuery field validation, enum values (SearchLanguage,
ResultType, SafeSearchLevel), boundary conditions, custom_parameters,
and JSON round-trip serialization.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.discovery.schemas.search_query import (
    ResultType,
    SafeSearchLevel,
    SearchLanguage,
    SearchQuery,
)


# ---------------------------------------------------------------------------
# TC1 — Default values
# ---------------------------------------------------------------------------

def test_TC1_all_optional_fields_defaults() -> None:
    """All optional search fields must resolve to their documented defaults."""
    q = SearchQuery(query="python tutorial")
    assert q.language is None
    assert q.region is None
    assert q.max_results == 10
    assert q.result_type == ResultType.WEB
    assert q.safe_search == SafeSearchLevel.MODERATE
    assert q.site_restriction is None
    assert q.custom_parameters == {}


def test_TC1_mutable_default_isolation() -> None:
    """custom_parameters must not share state across instances."""
    q1 = SearchQuery(query="test")
    q2 = SearchQuery(query="test")
    q1.custom_parameters["key"] = "value"
    assert "key" not in q2.custom_parameters


# ---------------------------------------------------------------------------
# TC2 — Valid construction
# ---------------------------------------------------------------------------

def test_TC2_minimal_valid() -> None:
    """Query string only — all else uses defaults."""
    q = SearchQuery(query="golang tutorial")
    assert q.query == "golang tutorial"
    assert q.result_type == ResultType.WEB


def test_TC2_full_construction() -> None:
    """All fields populated in a single constructor call."""
    q = SearchQuery(
        query="machine learning introduction",
        language=SearchLanguage.ENGLISH,
        region="us-US",
        max_results=20,
        result_type=ResultType.NEWS,
        safe_search=SafeSearchLevel.STRICT,
        site_restriction="example.com",
        custom_parameters={"foo": "bar"},
    )
    assert q.language == SearchLanguage.ENGLISH
    assert q.region == "us-US"
    assert q.max_results == 20
    assert q.result_type == ResultType.NEWS
    assert q.safe_search == SafeSearchLevel.STRICT
    assert q.site_restriction == "example.com"
    assert q.custom_parameters == {"foo": "bar"}


# ---------------------------------------------------------------------------
# TC3 — Validation errors
# ---------------------------------------------------------------------------

def test_TC3_query_empty_raises() -> None:
    """Empty query string must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="")
    assert "query" in str(exc.value).lower()


def test_TC3_query_whitespace_only_raises() -> None:
    """Whitespace-only query must raise ValidationError (str_strip_whitespace=True)."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="   ")
    assert "query" in str(exc.value).lower()


def test_TC3_query_too_long_raises() -> None:
    """Query above 500 characters must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="a" * 501)
    assert "query" in str(exc.value).lower()


def test_TC3_query_at_upper_bound_accepted() -> None:
    """Exactly 500-character query is valid."""
    q = SearchQuery(query="a" * 500)
    assert len(q.query) == 500


def test_TC3_region_invalid_format_raises() -> None:
    """Invalid region code format must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", region="US")  # missing lowercase suffix
    assert "region" in str(exc.value).lower()

    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", region="us-us")  # lowercase not allowed
    assert "region" in str(exc.value).lower()


def test_TC3_region_valid_formats_accepted() -> None:
    """All valid xx-XX region codes are accepted."""
    for region in ["us-US", "gb-GB", "de-DE", "jp-JP", "br-BR"]:
        q = SearchQuery(query="test", region=region)
        assert q.region == region


# ---------------------------------------------------------------------------
# TC4 — SearchLanguage enum
# ---------------------------------------------------------------------------

def test_TC4_all_language_values_accepted() -> None:
    """Every SearchLanguage enum member is accepted as language."""
    q = SearchQuery(query="test", language=SearchLanguage.ENGLISH)
    assert q.language == SearchLanguage.ENGLISH


def test_TC4_language_none_accepted() -> None:
    """language=None is always valid."""
    q = SearchQuery(query="test", language=None)
    assert q.language is None


# ---------------------------------------------------------------------------
# TC5 — ResultType enum
# ---------------------------------------------------------------------------

def test_TC5_all_result_type_values_accepted() -> None:
    """Every ResultType enum member passes validation."""
    for rt in ResultType:
        q = SearchQuery(query="test", result_type=rt)
        assert q.result_type == rt


def test_TC5_invalid_result_type_raises() -> None:
    """Unknown result_type string must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", result_type="video")  # type: ignore[arg-type]
    assert "result_type" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC6 — SafeSearchLevel enum
# ---------------------------------------------------------------------------

def test_TC6_all_safe_search_values_accepted() -> None:
    """Every SafeSearchLevel enum member passes validation."""
    for level in SafeSearchLevel:
        q = SearchQuery(query="test", safe_search=level)
        assert q.safe_search == level


def test_TC6_invalid_safe_search_raises() -> None:
    """Unknown safe_search string must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", safe_search="high")  # type: ignore[arg-type]
    assert "safe_search" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC7 — max_results bounds
# ---------------------------------------------------------------------------

def test_TC7_max_results_zero_raises() -> None:
    """max_results=0 must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", max_results=0)
    assert "max_results" in str(exc.value).lower()


def test_TC7_max_results_negative_raises() -> None:
    """Negative max_results must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", max_results=-1)
    assert "max_results" in str(exc.value).lower()


def test_TC7_max_results_above_100_raises() -> None:
    """max_results > 100 must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", max_results=101)
    assert "max_results" in str(exc.value).lower()


def test_TC7_max_results_at_boundaries() -> None:
    """max_results=1 and max_results=100 are both valid."""
    lo = SearchQuery(query="test", max_results=1)
    hi = SearchQuery(query="test", max_results=100)
    assert lo.max_results == 1
    assert hi.max_results == 100


# ---------------------------------------------------------------------------
# TC8 — site_restriction bounds
# ---------------------------------------------------------------------------

def test_TC8_site_restriction_max_length_accepted() -> None:
    """site_restriction at exactly 200 characters is valid."""
    q = SearchQuery(query="test", site_restriction="a" * 200)
    assert len(q.site_restriction) == 200


def test_TC8_site_restriction_too_long_raises() -> None:
    """site_restriction above 200 characters must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        SearchQuery(query="test", site_restriction="a" * 201)
    assert "site_restriction" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# TC9 — custom_parameters
# ---------------------------------------------------------------------------

def test_TC9_custom_parameters_accepts_arbitrary_dict() -> None:
    """custom_parameters accepts any string键值对 with no validation."""
    q = SearchQuery(
        query="test",
        custom_parameters={
            "api_param1": "value1",
            "experimental": "true",
            "x-custom-header": "my-value",
        },
    )
    assert q.custom_parameters["api_param1"] == "value1"


def test_TC9_custom_parameters_empty_is_valid() -> None:
    """custom_parameters={} is valid."""
    q = SearchQuery(query="test", custom_parameters={})
    assert q.custom_parameters == {}


# ---------------------------------------------------------------------------
# TC10 — JSON serialization round-trip
# ---------------------------------------------------------------------------

def test_TC10_json_roundtrip_minimal() -> None:
    """Minimal SearchQuery must survive a JSON serialization round-trip."""
    q = SearchQuery(query="python guide")
    parsed = SearchQuery.model_validate_json(q.model_dump_json())
    assert parsed.query == q.query
    assert parsed.max_results == q.max_results


def test_TC10_json_roundtrip_full() -> None:
    """Full SearchQuery must survive a JSON serialization round-trip."""
    q = SearchQuery(
        query="kubernetes deployment",
        language=SearchLanguage.ENGLISH,
        region="us-US",
        max_results=20,
        result_type=ResultType.NEWS,
        safe_search=SafeSearchLevel.STRICT,
        site_restriction="kubernetes.io",
        custom_parameters={"experimental": "true"},
    )
    parsed = SearchQuery.model_validate_json(q.model_dump_json())
    assert parsed.query == q.query
    assert parsed.language == SearchLanguage.ENGLISH
    assert parsed.region == "us-US"
    assert parsed.max_results == 20
    assert parsed.result_type == ResultType.NEWS
    assert parsed.safe_search == SafeSearchLevel.STRICT
    assert parsed.site_restriction == "kubernetes.io"
    assert parsed.custom_parameters == {"experimental": "true"}


def test_TC10_json_includes_all_fields() -> None:
    """model_dump_json() must include all fields including defaults."""
    q = SearchQuery(query="test")
    data = q.model_dump()
    assert data["max_results"] == 10
    assert data["result_type"] == "web"
    assert data["safe_search"] == "moderate"
    assert data["language"] is None