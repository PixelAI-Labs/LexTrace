"""Candidate collection for the Discovery Service."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse, urlunparse

from backend.content import ContentExtractor, ContentExtractorConfig, ExtractionResult
from backend.core.config import ContentExtractionSettings, Settings, settings
from backend.discovery.schemas.candidate_collection import (
    CandidateCollectionResult,
    CollectionStatistics,
    ExtractionFailure,
)
from backend.discovery.schemas.orchestrator import SearchOrchestratorResult
from backend.discovery.schemas.responses import CandidateArticle
from backend.discovery.schemas.search_result import SearchResult


@dataclass(frozen=True, slots=True)
class CollectorConfig:
    """Configuration for candidate collection and extraction."""

    max_concurrent_extractions: int
    content_extractor_config: ContentExtractorConfig | None = None

    @classmethod
    def from_settings(
        cls,
        settings_obj: Settings | None = None,
        content_settings: ContentExtractionSettings | None = None,
    ) -> CollectorConfig:
        cfg = settings_obj or settings
        extraction_settings = content_settings or cfg.content_extraction
        return cls(
            max_concurrent_extractions=extraction_settings.max_concurrent_extractions,
            content_extractor_config=ContentExtractorConfig.from_settings(extraction_settings),
        )


def _normalise_url(url: str) -> str:
    """Normalise a URL for defensive deduplication."""
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


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


class CandidateCollector:
    """Collect candidate articles by extracting content from search results."""

    __slots__ = ("_extractor", "_config")

    def __init__(
        self,
        extractor: ContentExtractor | None = None,
        *,
        config: CollectorConfig | None = None,
    ) -> None:
        self._config = config or CollectorConfig.from_settings()
        if extractor is None:
            extractor = ContentExtractor(self._config.content_extractor_config)
        self._extractor = extractor

    async def collect(
        self,
        orchestrator_result: SearchOrchestratorResult,
    ) -> CandidateCollectionResult:
        """Extract content for deduplicated search results."""
        start_ms = int(time.perf_counter() * 1000)

        deduped_results = _defensive_dedupe(orchestrator_result.deduplicated_results)
        total_urls = len(deduped_results)

        semaphore = asyncio.Semaphore(self._config.max_concurrent_extractions)
        tasks = [
            _extract_with_semaphore(semaphore, self._extractor, result)
            for result in deduped_results
        ]

        extraction_results = await asyncio.gather(*tasks)

        candidates: list[CandidateArticle] = []
        failures: list[ExtractionFailure] = []
        successful = 0
        empty = 0
        failed = 0

        for position, (search_result, extraction) in enumerate(
            zip(deduped_results, extraction_results, strict=True),
            start=1,
        ):
            if extraction.status == "success" and extraction.article is not None:
                candidate = _build_candidate(search_result, extraction, rank=len(candidates) + 1)
                if candidate is None:
                    empty += 1
                    failures.append(_build_failure(extraction, position))
                    continue
                candidates.append(candidate)
                successful += 1
                continue

            if extraction.status == "no_text":
                empty += 1
            else:
                failed += 1

            failures.append(_build_failure(extraction, position))

        elapsed_ms = int(time.perf_counter() * 1000) - start_ms

        stats = CollectionStatistics(
            total_urls=total_urls,
            successful_extractions=successful,
            failed_extractions=failed,
            empty_extractions=empty,
            extraction_time_ms=elapsed_ms,
        )

        return CandidateCollectionResult(
            candidates=candidates,
            failures=failures,
            statistics=stats,
            queries_used=orchestrator_result.queries_used,
            total_urls_collected=orchestrator_result.total_unique_urls,
        )


async def _extract_with_semaphore(
    semaphore: asyncio.Semaphore,
    extractor: ContentExtractor,
    result: SearchResult,
) -> ExtractionResult:
    async with semaphore:
        return await extractor.extract_async(result.url)


def _build_candidate(
    search_result: SearchResult,
    extraction: ExtractionResult,
    *,
    rank: int,
) -> CandidateArticle | None:
    article = extraction.article
    if article is None:
        return None

    if article.text_length <= 0 and not article.excerpt:
        return None

    title = article.title or search_result.title or None
    content = article.text.strip() if article.text else ""
    if len(content) > 200_000:
        content = content[:200_000]
    content_value = content or None
    preview = article.excerpt or search_result.description or ""
    if not preview and article.text:
        preview = article.text[:300]

    if not preview:
        return None

    domain = search_result.domain or _domain_from_url(search_result.url)

    return CandidateArticle(
        rank=rank,
        url=search_result.url,
        domain=domain,
        title=title,
        rank_score=0.0,
        keyword_coverage=0.0,
        content_preview=preview,
        content=content_value,
        text_length=article.text_length,
        publish_date=article.publish_date,
        language=article.language,
    )


def _build_failure(extraction: ExtractionResult, position: int) -> ExtractionFailure:
    return ExtractionFailure(
        url=extraction.url,
        status=extraction.status,
        error_message=extraction.error_message,
        attempts=extraction.attempts,
        elapsed_ms=extraction.elapsed_ms,
        position=position,
    )


def _defensive_dedupe(results: Iterable[SearchResult]) -> list[SearchResult]:
    unique: list[SearchResult] = []
    seen: set[str] = set()
    for result in results:
        key = _normalise_url(result.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


async def collect_candidates(
    orchestrator_result: SearchOrchestratorResult,
    *,
    collector: CandidateCollector | None = None,
) -> CandidateCollectionResult:
    """Convenience wrapper to collect candidates from orchestrator output."""
    collector_instance = collector or CandidateCollector()
    return await collector_instance.collect(orchestrator_result)
