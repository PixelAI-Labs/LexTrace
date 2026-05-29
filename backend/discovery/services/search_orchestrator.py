"""Search orchestrator for the Discovery Service."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse, urlunparse

from backend.core.config import Settings, settings
from backend.discovery.providers.base import SearchProvider
from backend.discovery.providers.duckduckgo import DuckDuckGoProvider
from backend.discovery.schemas.orchestrator import SearchOrchestratorResult
from backend.discovery.schemas.search_query import (
    ResultType,
    SafeSearchLevel,
    SearchLanguage,
    SearchQuery,
)
from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection
from backend.discovery.services.query_generator import as_config, generate_queries


@dataclass(frozen=True)
class SearchOrchestratorConfig:
    """Configuration for a single search orchestration run."""

    max_queries: int
    max_candidates: int
    max_results_per_query: int
    search_depth: str
    result_type: ResultType
    language: SearchLanguage | None
    region: str | None
    safe_search: SafeSearchLevel
    site_restriction: str | None


def build_orchestrator_config(
    *,
    settings_obj: Settings | None = None,
    max_queries: int | None = None,
    max_candidates: int | None = None,
    max_results_per_query: int | None = None,
    search_depth: str | None = None,
    result_type: ResultType = ResultType.WEB,
    language: SearchLanguage | None = None,
    region: str | None = None,
    safe_search: SafeSearchLevel = SafeSearchLevel.MODERATE,
    site_restriction: str | None = None,
) -> SearchOrchestratorConfig:
    """Build a SearchOrchestratorConfig using settings defaults."""
    cfg = settings_obj or settings
    resolved_max_queries = max_queries or cfg.discovery.max_queries_per_discovery
    resolved_max_candidates = max_candidates or cfg.discovery.default_max_candidates
    resolved_max_results_per_query = max_results_per_query or resolved_max_candidates
    resolved_search_depth = search_depth or cfg.discovery.default_search_depth

    return SearchOrchestratorConfig(
        max_queries=max(1, min(resolved_max_queries, cfg.discovery.max_queries_per_discovery)),
        max_candidates=max(1, min(resolved_max_candidates, cfg.discovery.default_max_candidates)),
        max_results_per_query=max(1, min(resolved_max_results_per_query, resolved_max_candidates)),
        search_depth=resolved_search_depth,
        result_type=result_type,
        language=language,
        region=region,
        safe_search=safe_search,
        site_restriction=site_restriction,
    )


def _normalise_url(url: str) -> str:
    """Normalise a URL for deduplication while preserving host and path."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    cleaned = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        fragment="",
    )
    return urlunparse(cleaned).rstrip("/")


def _deduplicate_results(
    results: Iterable[SearchResult],
    max_candidates: int,
) -> list[SearchResult]:
    """Deduplicate results by URL while preserving first-seen order."""
    unique: list[SearchResult] = []
    seen: set[str] = set()
    for result in results:
        key = _normalise_url(result.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
        if len(unique) >= max_candidates:
            break
    return unique


class SearchOrchestrator:
    """Generate queries, execute searches, and aggregate results."""

    def __init__(
        self,
        providers: Iterable[SearchProvider] | None = None,
        *,
        settings_obj: Settings | None = None,
    ) -> None:
        self._settings = settings_obj or settings
        if providers is None:
            providers = (DuckDuckGoProvider(),)
        self._providers = list(providers)

    async def run(
        self,
        article_text: str,
        *,
        title: str | None = None,
        config: SearchOrchestratorConfig | None = None,
    ) -> SearchOrchestratorResult:
        """Execute a full search orchestration run."""
        if config is None:
            config = build_orchestrator_config(settings_obj=self._settings)

        query_config = as_config(max_queries=config.max_queries)
        queries = generate_queries(
            article_text,
            query_config,
            title=title,
            search_depth=config.search_depth,
        )[: config.max_queries]

        provider_results: list[SearchResultCollection] = []
        raw_results: list[SearchResult] = []
        total_search_time_ms = 0

        for query_text in queries:
            query = SearchQuery(
                query=query_text,
                language=config.language,
                region=config.region,
                max_results=config.max_results_per_query,
                result_type=config.result_type,
                safe_search=config.safe_search,
                site_restriction=config.site_restriction,
            )
            for provider in self._providers:
                if not provider.supports_result_type(config.result_type):
                    continue
                start_ms = int(time.perf_counter() * 1000)
                collection = await provider.execute(query)
                elapsed_ms = int(time.perf_counter() * 1000) - start_ms
                total_search_time_ms += elapsed_ms
                provider_results.append(collection)
                raw_results.extend(collection.results)

        deduplicated = _deduplicate_results(raw_results, config.max_candidates)

        return SearchOrchestratorResult(
            queries_used=queries,
            provider_results=provider_results,
            deduplicated_results=deduplicated,
            total_unique_urls=len(deduplicated),
            total_results=len(raw_results),
            search_time_ms=total_search_time_ms,
        )
