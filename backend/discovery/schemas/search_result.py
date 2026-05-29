"""Search result models for the Discovery Service.

Defines the canonical output schema returned by any :class:`SearchProvider`.
:class:`SearchResult` is a single item; :class:`SearchResultCollection`
 groups a query's results with execution metadata.
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """A single organic search result returned by a search provider.

    All scores and confidence values are floats in ``[0.0, 1.0]`` where
    higher values indicate stronger relevance signals (used for ranking later).

    Attributes
    ----------
    url:
        The canonical URL of the result page.
    title:
        The result's display title. May be empty for certain rich result types.
    description:
        The query-biased snippet / abstract. May be empty if only a title
        is returned by the provider.
    domain:
        The root domain of ``url`` (e.g. ``"example.com"`` from
        ``"https://blog.example.com/post/1"``). Always lowercase.
    publish_date:
        ISO 8601 date string (``YYYY-MM-DD``) if a publish date was detected.
        ``None`` if the provider did not expose one.
    language:
        ISO 639-1 language code detected from the result page content.
        ``None`` if undetectable.
    source_provider:
        Identifier of the provider that returned this result (e.g. ``"google"``,
        ``"duckduckgo"``). Corresponds to :attr:`SearchProvider.provider_name`.
    is_paywalled:
        ``True`` when the result URL is suspected to lead to a paywalled page.
    rank:
        1-based position of this result in the raw provider response.
        ``None`` when the provider does not expose positional information.
    """

    url: Annotated[str, Field(description="Canonical URL of the result page.")]
    title: Annotated[str, Field(max_length=500, description="Result display title.")]
    description: Annotated[str, Field(
        max_length=1000,
        description="Query-biased snippet or abstract text.",
    )]
    domain: Annotated[str, Field(
        description="Root domain of the result URL, lowercased (e.g. 'example.com').",
    )]
    publish_date: str | None = Field(
        default=None,
        description="ISO 8601 date string (YYYY-MM-DD) if detected.",
    )
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code of the result content.",
    )
    source_provider: Annotated[str, Field(
        description="Name of the provider that returned this result.",
    )]
    is_paywalled: bool = Field(
        default=False,
        description="Whether the result URL is suspected to be behind a paywall.",
    )
    rank: Annotated[int | None, Field(
        default=None,
        ge=1,
        description="1-based position in the raw provider response.",
    )]

    @field_validator("url")
    @classmethod
    def _validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid http or https URL")
        return value


class SearchResultCollection(BaseModel):
    """A complete search response — execution metadata plus the result list.

    Returned by :meth:`SearchProvider.execute`. Consumers use this to
    iterate candidate URLs, inspect timing metadata, or hand the
    structured list off to downstream services (extraction, ranking).
    """

    query_executed: Annotated[str, Field(
        description="The query string that was sent to the provider.",
    )]
    provider_used: Annotated[str, Field(
        description="Provider name (e.g. 'google') that produced these results.",
    )]
    total_results: Annotated[int, Field(
        ge=0,
        description="Total number of results returned by the provider (may exceed len(results)).",
    )]
    results: Annotated[list[SearchResult], Field(
        default_factory=list,
        description="Ordered list of individual search results.",
    )]
    search_time_ms: Annotated[int, Field(
        default=0,
        ge=0,
        description="Wall-clock time the provider took to respond, in milliseconds.",
    )]

    @property
    def urls(self) -> list[str]:
        """Convenience property: extract all result URLs as strings."""
        return [str(r.url) for r in self.results]

    @property
    def domains(self) -> list[str]:
        """Convenience property: extract all result domains as strings."""
        return [r.domain for r in self.results]