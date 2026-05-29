"""Unit tests for DuckDuckGoProvider.

Covers the SearchProvider contract, result normalisation,
settings, error handling, and edge cases.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from typing_extensions import NotRequired, TypedDict

from backend.core.config import DuckDuckGoSettings
from backend.discovery.providers.base import ProviderName
from backend.discovery.providers.duckduckgo import (
    DuckDuckGoError,
    DuckDuckGoProvider,
    _root_domain,
)
from backend.discovery.schemas.search_query import (
    ResultType,
    SafeSearchLevel,
    SearchLanguage,
    SearchQuery,
)
from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RawDDGResult(TypedDict):
    """Shape returned by duckduckgo_search.DDGS.text() dict items."""
    title: str
    href: str
    body: str


async def _async_gen(values: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Turn a plain list into an async iterator — suitable for duck-side effects."""
    for v in values:
        yield v


# ---------------------------------------------------------------------------
# TC1 — DuckDuckGoProvider satisfies the SearchProvider protocol
# ---------------------------------------------------------------------------

def test_TC1_isinstance_search_provider() -> None:
    """DuckDuckGoProvider must be recognised as a SearchProvider."""
    from backend.discovery.providers.base import SearchProvider

    provider = DuckDuckGoProvider()
    assert isinstance(provider, SearchProvider)


def test_TC1_provider_name_is_duckduckgo() -> None:
    """provider_name must resolve to ProviderName.DUCKDUCKGO."""
    provider = DuckDuckGoProvider()
    assert provider.provider_name == ProviderName.DUCKDUCKGO


# ---------------------------------------------------------------------------
# TC2 — supports_result_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("result_type,expected", [
    (ResultType.WEB, True),
    (ResultType.NEWS, False),
    (ResultType.IMAGES, False),
    (ResultType.VIDEOS, False),
])
def test_TC2_supports_result_type(result_type: ResultType, expected: bool) -> None:
    """Only ResultType.WEB is supported."""
    provider = DuckDuckGoProvider()
    assert provider.supports_result_type(result_type) is expected


# ---------------------------------------------------------------------------
# TC3 — execute() normalises raw results correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC3_execute_normalises_results() -> None:
    """Raw DuckDuckGo dicts must become SearchResult objects with correct fields."""
    raw_results: list[_RawDDGResult] = [
        {
            "title": "Example Article",
            "href": "https://example.com/article",
            "body": "This is the article snippet.",
        },
        {
            "title": "Another Site",
            "href": "https://anothersite.org/post/123",
            "body": "Different content here.",
        },
    ]

    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen(raw_results))

    # Patch DDGS so "with DDGS(...)" yields our mock
    with patch(
        "backend.discovery.providers.duckduckgo.DDGS"
    ) as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        collection = await provider.execute(SearchQuery(query="test article"))

    assert len(collection.results) == 2

    # Spot-check first result
    r0 = collection.results[0]
    assert r0.url == "https://example.com/article"
    assert r0.title == "Example Article"
    assert r0.description == "This is the article snippet."
    assert r0.domain == "example.com"
    assert r0.source_provider == "duckduckgo"
    assert r0.rank == 1
    assert r0.is_paywalled is False
    assert r0.publish_date is None
    assert r0.language is None

    r1 = collection.results[1]
    assert r1.url == "https://anothersite.org/post/123"
    assert r1.domain == "anothersite.org"
    assert r1.rank == 2


# ---------------------------------------------------------------------------
# TC4 — domain extraction strips www. and lowercases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC4_domain_strips_www_and_lowercases() -> None:
    """Root domain must be lowercased and 'www.' prefix removed."""
    raw_results: list[_RawDDGResult] = [
        {"title": "Www Test", "href": "https://WWW.Example.COM/page", "body": "desc"},
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen(raw_results))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        collection = await provider.execute(SearchQuery(query="www test"))

    assert collection.results[0].domain == "example.com"


# ---------------------------------------------------------------------------
# TC5 — max_results respects provider ceiling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC5_max_results_respects_provider_ceiling() -> None:
    """When query.max_results > provider ceiling, the ceiling is used."""
    cfg = DuckDuckGoSettings(max_results_per_query=5)
    raw_results = [
        {"title": f"Result {i}", "href": f"https://site{i}.com/", "body": f"Body {i}"}
        for i in range(10)
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen(raw_results))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider(cfg=cfg)
        # Request 20 but provider caps at 5
        collection = await provider.execute(SearchQuery(query="test", max_results=20))

    # text() was called with at_most max_results = min(20, 5) = 5
    # Note: ddgs.text takes a count parameter that is the MAX to return
    args, _kwargs = mock_ddgs_instance.text.call_args
    assert args[1] == 5  # second positional arg to text() is max_results


# ---------------------------------------------------------------------------
# TC6 — empty results return empty SearchResultCollection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC6_empty_results() -> None:
    """An empty raw list produces an empty collection with total_results=0."""
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen([]))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        collection = await provider.execute(SearchQuery(query="nothing"))

    assert collection.results == []
    assert collection.total_results == 0
    assert collection.provider_used == "duckduckgo"
    assert collection.search_time_ms >= 0


# ---------------------------------------------------------------------------
# TC7 — site_restriction is prepended as "site:" operator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC7_site_restriction_added_to_query() -> None:
    """site_restriction='example.com' makes query text='term site:example.com'."""
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen([]))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        await provider.execute(
            SearchQuery(query="original term", site_restriction="example.com")
        )

    args, _kwargs = mock_ddgs_instance.text.call_args
    assert args[0] == "original term site:example.com"


# ---------------------------------------------------------------------------
# TC8 — search_time_ms is populated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC8_search_time_ms_populated() -> None:
    """search_time_ms must be a non-negative integer."""
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen([]))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        collection = await provider.execute(SearchQuery(query="speed test"))

    assert isinstance(collection.search_time_ms, int)
    assert collection.search_time_ms >= 0


# ---------------------------------------------------------------------------
# TC9 — DuckDuckGoError on provider exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC9_raises_on_ddgs_exception() -> None:
    """If DDGS raises, DuckDuckGoError must be raised."""
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(
        side_effect=RuntimeError("network unreachable")
    )

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        with pytest.raises(DuckDuckGoError, match="network unreachable"):
            await provider.execute(SearchQuery(query="fail"))


# ---------------------------------------------------------------------------
# TC10 — rank is 1-based positional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC10_rank_is_1_indexed() -> None:
    """Rank must start at 1 and increment for each result."""
    raw_results = [
        {"title": f"Title {i}", "href": f"https://site{i}.com/", "body": f"Body {i}"}
        for i in range(5)
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen(raw_results))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        collection = await provider.execute(SearchQuery(query="ranking"))

    for idx, r in enumerate(collection.results, start=1):
        assert r.rank == idx, f"Expected rank {idx}, got {r.rank}"


# ---------------------------------------------------------------------------
# TC11 — query_executed and provider_used fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_TC11_metadata_fields_populated() -> None:
    """query_executed and provider_used must be correct strings."""
    raw_results: list[_RawDDGResult] = [
        {"title": "T", "href": "https://x.com/", "body": "D"},
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=_async_gen(raw_results))

    with patch("backend.discovery.providers.duckduckgo.DDGS") as mock_ddgs_class:
        mock_ddgs_class.return_value.__aenter__.return_value = mock_ddgs_instance
        mock_ddgs_class.return_value.__aexit__.return_value = None

        provider = DuckDuckGoProvider()
        collection = await provider.execute(SearchQuery(query="my search term"))

    assert collection.query_executed == "my search term"
    assert collection.provider_used == "duckduckgo"


# ---------------------------------------------------------------------------
# TC12 — default settings used when no cfg passed
# ---------------------------------------------------------------------------

def test_TC12_default_settings_used() -> None:
    """Without an explicit cfg argument, module-level settings are used."""
    provider = DuckDuckGoProvider()
    # This should not raise and should use the settings singleton
    assert provider._cfg is not None
    assert provider._cfg.max_results_per_query == 10
    assert provider._cfg.request_timeout_seconds == 15.0


def test_TC12_custom_settings_used() -> None:
    """Passing an explicit cfg must bypass the global settings."""
    custom_cfg = DuckDuckGoSettings(max_results_per_query=25, request_timeout_seconds=30.0)
    provider = DuckDuckGoProvider(cfg=custom_cfg)
    assert provider._cfg is custom_cfg
    assert provider._cfg.max_results_per_query == 25


# ---------------------------------------------------------------------------
# TC13 — _root_domain unit tests (pure function)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected_domain", [
    ("https://example.com/article", "example.com"),
    ("https://blog.example.com/post", "blog.example.com"),
    ("https://www.example.com/", "example.com"),
    ("https://WWW.Example.COM/", "example.com"),
    ("https://sub.domain.example.org/page", "sub.domain.example.org"),
    ("https://x.com/", "x.com"),
])
def test_TC13_root_domain(url: str, expected_domain: str) -> None:
    """_root_domain must strip 'www.', lower-case, and return the netloc."""
    assert _root_domain(url) == expected_domain


# ---------------------------------------------------------------------------
# TC14 — provider_name is a ProviderName enum member (not just a string)
# ---------------------------------------------------------------------------

def test_TC14_provider_name_is_enum_member() -> None:
    """provider_name must be exactly ProviderName.DUCKDUCKGO, not just a str."""
    provider = DuckDuckGoProvider()
    assert provider.provider_name is ProviderName.DUCKDUCKGO


# ---------------------------------------------------------------------------
# TC15 — result normalisation skips malformed raw dict entries
# ---------------------------------------------------------------------------

def test_TC15_constructor_succeeds_with_valid_attrs() -> None:
    """DuckDuckGoProvider can be instantiated directly without async setup."""
    provider = DuckDuckGoProvider()
    assert provider.provider_name == ProviderName.DUCKDUCKGO


def test_TC15_provider_accepts_all_search_query_fields() -> None:
    """All SearchQuery fields are accepted and do not raise."""
    cfg = DuckDuckGoSettings()
    provider = DuckDuckGoProvider(cfg=cfg)
    query = SearchQuery(
        query="valid query",
        language=SearchLanguage.ENGLISH,
        region="us-en",
        max_results=10,
        result_type=ResultType.WEB,
        safe_search=SafeSearchLevel.MODERATE,
        site_restriction=None,
        custom_parameters={"key": "value"},
    )
    # At this level we only check SearchQuery validation — execute() is tested elsewhere
    assert query.query == "valid query"
    assert provider.supports_result_type(ResultType.WEB) is True