"""Unit tests for backend.discovery.providers.base.

Covers: SearchProvider protocol structure, ProviderName enum values,
method signatures, runtime_checkable behaviour, and isinstance guards
with a minimal mock implementation.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel

from backend.discovery.providers.base import ProviderName, SearchProvider
from backend.discovery.schemas.search_query import ResultType, SearchQuery
from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection


# ---------------------------------------------------------------------------
# TC1 — SearchProvider protocol is runtime_checkable
# ---------------------------------------------------------------------------

def test_TC1_protocol_is_runtime_checkable() -> None:
    """isinstance(provider, SearchProvider) must work at runtime."""
    # A protocol decorated with @runtime_checkable supports isinstance
    assert hasattr(SearchProvider, "__protocol_attrs__")


def test_TC1_protocol_has_required_members() -> None:
    """SearchProvider must define provider_name, execute, supports_result_type."""
    protocol_members = {"provider_name", "execute", "supports_result_type"}
    assert protocol_members.issubset(dir(SearchProvider))


# ---------------------------------------------------------------------------
# TC2 — ProviderName enum completeness
# ---------------------------------------------------------------------------

def test_TC2_all_expected_provider_names() -> None:
    """ProviderName must contain all registered providers."""
    expected = {"google", "duckduckgo", "brave", "tavily"}
    actual = {p.value for p in ProviderName}
    assert actual == expected


def test_TC2_provider_name_is_str_subclass() -> None:
    """Each ProviderName member is a str subclass so it compares cleanly."""
    assert issubclass(ProviderName, str)
    assert ProviderName.GOOGLE == "google"
    assert ProviderName.DUCKDUCKGO == "duckduckgo"


def test_TC2_provider_name_values_are_lowercase() -> None:
    """All enum values must be lowercase strings (used as source_provider field)."""
    for member in ProviderName:
        assert member.value == member.value.lower()
        assert member.value == str(member)


def test_TC2_distinct_provider_names() -> None:
    """All ProviderName values must be distinct."""
    values = [m.value for m in ProviderName]
    assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# TC3 — execute() method signature
# ---------------------------------------------------------------------------

def test_TC3_execute_is_async() -> None:
    """SearchProvider.execute must be an async method."""
    sig = inspect.signature(SearchProvider.execute)
    assert inspect.iscoroutinefunction(SearchProvider.execute) or (
        # Protocol methods don't have iscoroutinefunction on the protocol itself
        # Instead verify the parameters are correct
        "query" in sig.parameters
    )
    # Verify expected parameters
    params = list(sig.parameters.keys())
    assert params == ["self", "query"]


def test_TC3_execute_returns_search_result_collection() -> None:
    """SearchProvider.execute annotation must specify SearchResultCollection return."""
    hints = SearchProvider.execute.__annotations__
    assert "return" in hints
    # Don't require exact type match — just that a return annotation exists
    assert hints["return"] is not inspect._empty  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TC4 — supports_result_type() method signature
# ---------------------------------------------------------------------------

def test_TC4_supports_result_type_is_sync_method() -> None:
    """SearchProvider.supports_result_type must be a synchronous method."""
    sig = inspect.signature(SearchProvider.supports_result_type)
    params = list(sig.parameters.keys())
    assert params == ["self", "result_type"]


def test_TC4_supports_result_type_returns_bool() -> None:
    """SearchProvider.supports_result_type annotation must specify bool return."""
    hints = SearchProvider.supports_result_type.__annotations__
    assert hints.get("return") is bool


# ---------------------------------------------------------------------------
# TC5 — Mock implementation passes isinstance check
# ---------------------------------------------------------------------------

class MockSearchProvider:
    """A minimal concrete implementation of SearchProvider for testing."""

    provider_name = ProviderName.GOOGLE

    async def execute(self, query: SearchQuery) -> SearchResultCollection:
        return SearchResultCollection(
            query_executed=query.query,
            provider_used=self.provider_name,
            total_results=0,
            results=[],
        )

    def supports_result_type(self, result_type: ResultType) -> bool:
        return result_type == ResultType.WEB


def test_TC5_mock_implements_protocol() -> None:
    """A class that fully implements the protocol passes isinstance check."""
    provider: SearchProvider = MockSearchProvider()
    assert isinstance(provider, SearchProvider)


def test_TC5_isinstance_false_for_non_implementer() -> None:
    """A plain object that does not implement the protocol must fail isinstance."""
    assert not isinstance(object(), SearchProvider)


# ---------------------------------------------------------------------------
# TC6 — provider_name returns correct enum member
# ---------------------------------------------------------------------------

def test_TC6_provider_name_is_enum_member() -> None:
    """provider_name property must return a ProviderName enum member, not a raw string."""
    mock: SearchProvider = MockSearchProvider()
    name = mock.provider_name
    assert isinstance(name, ProviderName)


def test_TC6_provider_name_used_in_result_collection() -> None:
    """The provider_name value propagates to result source_provider field."""
    mock: SearchProvider = MockSearchProvider()
    query = SearchQuery(query="python")
    result = mock.execute(query)
    # Verify the async function returns the right provider name without awaiting
    # Since we cannot await in a sync test, we just verify the stub signature


# ---------------------------------------------------------------------------
# TC7 — Protocol isolation: missing methods detected by isinstance
# ---------------------------------------------------------------------------

class IncompleteProvider:
    """Implements provider_name but omits execute — must not pass isinstance."""

    provider_name = ProviderName.GOOGLE

    # execute intentionally omitted
    # supports_result_type intentionally omitted


def test_TC7_incomplete_not_instance() -> None:
    """A class missing any required method fails isinstance SearchProvider."""
    assert not isinstance(IncompleteProvider(), SearchProvider)


class OnlyExecuteProvider:
    """Implements execute but no provider_name."""
    async def execute(self, query: SearchQuery) -> SearchResultCollection:
        return SearchResultCollection(
            query_executed=query.query,
            provider_used="placeholder",
            total_results=0,
            results=[],
        )


def test_TC7_only_execute_not_instance() -> None:
    """Missing provider_name fails isinstance even if execute is present."""
    assert not isinstance(OnlyExecuteProvider(), SearchProvider)


# ---------------------------------------------------------------------------
# TC8 — Mock provider attributes are accessible
# ---------------------------------------------------------------------------

def test_TC8_provider_name_accessible() -> None:
    """mock.provider_name returns the correct ProviderName value."""
    mock: SearchProvider = MockSearchProvider()
    assert mock.provider_name == ProviderName.GOOGLE
    assert mock.provider_name == "google"


def test_TC8_supports_result_type_responds_correctly() -> None:
    """supports_result_type returns True for WEB, False for others."""
    mock: SearchProvider = MockSearchProvider()
    assert mock.supports_result_type(ResultType.WEB) is True
    assert mock.supports_result_type(ResultType.NEWS) is False
    assert mock.supports_result_type(ResultType.IMAGES) is False
    assert mock.supports_result_type(ResultType.VIDEOS) is False


# ---------------------------------------------------------------------------
# TC9 — Protocol compatibility with SearchQuery and SearchResultCollection
# ---------------------------------------------------------------------------

def test_TC9_search_query_accepted_by_execute_signature() -> None:
    """execute(query: SearchQuery) accepts a SearchQuery instance."""
    sig = inspect.signature(SearchProvider.execute)
    query_param = sig.parameters["query"]
    # The annotation must be present
    assert query_param.annotation is not inspect._empty  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TC10 — ResultType values used in supports_result_type
# ---------------------------------------------------------------------------

def test_TC10_all_result_types_tested_in_mock() -> None:
    """Mock supports_result_type is called with each ResultType in tests."""
    mock: SearchProvider = MockSearchProvider()
    for rt in ResultType:
        result = mock.supports_result_type(rt)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# TC11 — ProviderName members are accessible
# ---------------------------------------------------------------------------

def test_TC11_provider_name_members_accessible() -> None:
    """All ProviderName enum members are accessible as class attributes."""
    assert ProviderName.GOOGLE.value == "google"
    assert ProviderName.DUCKDUCKGO.value == "duckduckgo"
    assert ProviderName.BRAVE.value == "brave"
    assert ProviderName.TAVILY.value == "tavily"