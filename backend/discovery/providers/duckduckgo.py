"""DuckDuckGo search provider implementation.

 Implements the :class:`SearchProvider` protocol using the
 ``ddgs`` library.  Normalises raw DuckDuckGo JSON
 responses into canonical :class:`SearchResult` objects.
"""

from __future__ import annotations

import asyncio
import time
import urllib.parse
from typing import Any

from ddgs import DDGS

from backend.core.config import DuckDuckGoSettings, settings
from backend.discovery.providers.base import ProviderName, SearchProvider
from backend.discovery.schemas.search_query import ResultType, SearchQuery
from backend.discovery.schemas.search_result import (
    SearchResult,
    SearchResultCollection,
)


def _root_domain(url: str) -> str:
    """Return the lowercased root domain of *url* stripping 'www.' if present."""
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _collect_ddg_results(
    ddgs: DDGS,
    query_text: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Collect DuckDuckGo results from the sync generator."""
    results: list[dict[str, Any]] = []
    for raw in ddgs.text(query_text, max_results=max_results):
        results.append(dict(raw))
    return results


class DuckDuckGoProvider:
    """DuckDuckGo-backed :class:`SearchProvider`.

    Parameters
    ----------
    settings:
        Provider-specific configuration.  If omitted the module-level
        :data:`settings` singleton is used.
    """

    __slots__ = ("_cfg",)

    def __init__(
        self,
        cfg: DuckDuckGoSettings | None = None,
    ) -> None:
        self._cfg = cfg if cfg is not None else settings.duckduckgo

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.DUCKDUCKGO

    def supports_result_type(self, result_type: ResultType) -> bool:
        """DuckDuckGo organic results only support ``ResultType.WEB``."""
        return result_type == ResultType.WEB

    async def execute(self, query: SearchQuery) -> SearchResultCollection:
        """Execute a DuckDuckGo web search and return a normalised result collection.

        Parameters
        ----------
        query:
            The :class:`SearchQuery` to execute.  ``language``, ``region``,
            and ``safe_search`` are accepted but DuckDuckGo maps these
            to its own internal parameters.  ``max_results`` is capped at
            the configured :attr:`DuckDuckGoSettings.max_results_per_query`.
            ``site_restriction`` adds a ``site:`` operator to the query.

        Returns
        -------
        SearchResultCollection
            Normalised results with execution metadata.

        Raises
        ------
        DuckDuckGoError
            If the underlying ``ddgs`` call fails for any reason.
        """
        start_ms = int(time.perf_counter() * 1000)

        # Build the effective query text
        q = query.query.strip()
        if query.site_restriction:
            q = f"{q} site:{query.site_restriction}"

        # Respect per-provider max ceiling
        max_results = min(query.max_results, self._cfg.max_results_per_query)

        try:
            def _run_query() -> list[dict[str, Any]]:
                with DDGS(timeout=self._cfg.request_timeout_seconds) as ddgs:
                    return _collect_ddg_results(ddgs, q, max_results)

            raw_results = await asyncio.to_thread(_run_query)
        except Exception as exc:  # pragma: no cover — network errors are unrepresentable in unit tests
            raise DuckDuckGoError(str(exc)) from exc

        elapsed_ms = int(time.perf_counter() * 1000) - start_ms

        results: list[SearchResult] = []
        for rank_offset, raw in enumerate(raw_results, start=1):
            try:
                result = SearchResult(
                    url=raw["href"],
                    title=raw.get("title", ""),
                    description=raw.get("body", ""),
                    domain=_root_domain(raw.get("href", "")),
                    publish_date=None,
                    language=None,
                    source_provider=ProviderName.DUCKDUCKGO.value,
                    is_paywalled=False,
                    rank=rank_offset,
                )
                results.append(result)
            except Exception as exc:  # pragma: no cover — malformed raw items
                raise DuckDuckGoError(
                    f"Failed to normalise DuckDuckGo result: {exc}"
                ) from exc

        total = len(results)  # DuckDuckGo doesn't provide a total count
        return SearchResultCollection(
            query_executed=query.query,
            provider_used=ProviderName.DUCKDUCKGO.value,
            total_results=total,
            results=results,
            search_time_ms=elapsed_ms,
        )


class DuckDuckGoError(Exception):
    """Raised when the DuckDuckGo search call fails or returns an unparseable response."""