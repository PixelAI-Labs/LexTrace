"""Request models for the Discovery Service."""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DiscoveryOptions(BaseModel):
    """Optional tuning parameters for a discovery run.

    All fields have defaults — the client may send an empty object ``{}``
    and the service will apply the built-in defaults.
    """

    max_candidates: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of candidate articles to return.",
    )
    search_depth: Literal["shallow", "deep"] = Field(
        default="shallow",
        description=(
            "'shallow' generates 3–5 queries using title + top TF-IDF keywords. "
            "'deep' adds synonyms, question forms, and listicle variants (up to 8 queries)."
        ),
    )
    include_content: bool = Field(
        default=True,
        description="Whether to extract and include full article content for each candidate.",
    )


class DiscoveryRequest(BaseModel):
    """POST /discover request body.

    The caller submits raw article text (and optionally a title or source URL)
    and the service returns a ranked list of suspected pirated copies.
    """

    article_text: str = Field(
        ...,
        min_length=100,
        max_length=50_000,
        description=(
            "The full text of the article to check. "
            "Must be between 100 and 50 000 characters."
        ),
    )
    title: str | None = Field(
        default=None,
        max_length=500,
        description="Optional article title. Improves query generation precision.",
    )
    source_url: str | None = Field(
        default=None,
        description="Optional URL the article was originally published at.",
    )
    options: DiscoveryOptions = Field(
        default_factory=DiscoveryOptions,
        description="Discovery behaviour tuning. Safe to omit — defaults are sensible.",
    )

    @field_validator("source_url")
    @classmethod
    def _validate_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be a valid http or https URL")
        return value