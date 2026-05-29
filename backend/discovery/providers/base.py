"""Search provider abstraction layer.

Defines the canonical :class:`SearchProvider` protocol that all concrete
provider implementations (``GoogleProvider``, ``DuckDuckGoProvider``, …)
must satisfy, along with the shared :class:`ProviderName` enum.

No provider-specific logic or API calls live here — only the abstract
contract and type definitions shared across all providers.
"""

from abc import abstractmethod
from enum import StrEnum
from typing import Protocol, runtime_checkable

from backend.discovery.schemas.search_query import ResultType, SearchQuery
from backend.discovery.schemas.search_result import SearchResultCollection


# ---------------------------------------------------------------------------
# Provider identity
# ---------------------------------------------------------------------------

class ProviderName(StrEnum):
    """Canonical names for all registered search providers.

    Each value is lowercase and used as the ``source_provider`` field
    in every :class:`~backend.discovery.schemas.search_result.SearchResult`
    produced by that provider, as well as the key in provider registry
    lookups.

    Adding a new provider: append to this enum and implement
    :class:`SearchProvider` in ``backend/discovery/providers/<name>.py``.
    """

    GOOGLE = "google"
    DUCKDUCKGO = "duckduckgo"
    BRAVE = "brave"
    TAVILY = "tavily"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class SearchProvider(Protocol):
    """Abstract contract for a search provider.

    All concrete providers (``GoogleProvider``, ``DuckDuckGoProvider``, …)
    must implement this protocol. The ``@runtime_checkable`` decoration
    enables ``isinstance(provider, SearchProvider)`` assertions in tests
    and at registration-time type guards.

    The protocol is intentionally silent on authentication details
    (API keys, tokens, etc.) — each provider receives its configuration
    at construction time and is responsible for managing its own credentials.

    Example implementation skeleton::

        class GoogleProvider:
            provider_name = ProviderName.GOOGLE

            def __init__(self, api_key: str, search_engine_id: str) -> None:
                self._api_key = api_key
                self._search_engine_id = search_engine_id

            async def execute(
                self,
                query: SearchQuery,
            ) -> SearchResultCollection:
                # ... build request, call Google API, map response ...
                return SearchResultCollection(...)

            def supports_result_type(self, result_type: ResultType) -> bool:
                return result_type == ResultType.WEB
    """

    @property
    @abstractmethod
    def provider_name(self) -> ProviderName:
        """Return the canonical provider identifier.

        The returned value is used as the ``source_provider`` field
        in all :class:`SearchResult` objects produced by this provider.
        Must be a :class:`ProviderName` enum member (not a raw string).
        """
        ...

    @abstractmethod
    async def execute(
        self,
        query: SearchQuery,
    ) -> SearchResultCollection:
        """Execute a search query and return structured results.

        Parameters
        ----------
        query:
            Structured search query to execute. Contains the query string,
            optional language/region hints, result type, and safe-search
            preferences.

        Returns
        -------
        SearchResultCollection
            A fully-populated result collection with URLs, titles, snippets,
            and execution metadata.

        Raises
        ------
        SearchProviderError
            If the provider fails (network error, quota exceeded,
            invalid API credentials, etc.). Concrete providers may raise
            subclassed variants with additional context.
        """
        ...

    @abstractmethod
    def supports_result_type(self, result_type: ResultType) -> bool:
        """Return ``True`` if this provider supports the given result type.

        Providers that only support WEB searches return ``False`` for
        NEWS, IMAGES, and VIDEOS. Consumers consult this method before
        calling :meth:`execute` with a given :attr:`SearchQuery.result_type`.

        Parameters
        ----------
        result_type
            The :class:`ResultType <backend.discovery.schemas.search_query.ResultType>`
            value to check.

        Returns
        -------
        bool
            ``True`` iff the provider can return results of that type.
        """
        ...