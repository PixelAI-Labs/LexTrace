"""Search query models for the Discovery Service.

Defines the canonical input schema accepted by any :class:`SearchProvider`.
All fields are provider-agnostic; individual providers map these to their
own API parameters at the infrastructure layer.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SearchLanguage(str, Enum):
    """ISO 639-1 language codes supported by search providers.

    Not all providers support every language. Providers must return their
    closest available locale when an exact match is unavailable.
    """

    ARABIC = "ar"
    BENGALI = "bn"
    BULGARIAN = "bg"
    CZECH = "cs"
    DANISH = "da"
    GERMAN = "de"
    GREEK = "el"
    ENGLISH = "en"
    SPANISH = "es"
    ESTONIAN = "et"
    PERSIAN = "fa"
    FINNISH = "fi"
    FRENCH = "fr"
    GUJARATI = "gu"
    HEBREW = "he"
    HINDI = "hi"
    CROATIAN = "hr"
    HUNGARIAN = "hu"
    INDONESIAN = "id"
    ITALIAN = "it"
    JAPANESE = "ja"
    KANNADA = "kn"
    KOREAN = "ko"
    LITHUANIAN = "lt"
    LATVIAN = "lv"
    MALAYALAM = "ml"
    MARATHI = "mr"
    NORWEGIAN = "no"
    DUTCH = "nl"
    POLISH = "pl"
    PORTUGUESE = "pt"
    ROMANIAN = "ro"
    RUSSIAN = "ru"
    SLOVAK = "sk"
    SLOVENIAN = "sl"
    SERBIAN = "sr"
    SWEDISH = "sv"
    SWAHILI = "sw"
    TAMIL = "ta"
    TELUGU = "te"
    THAI = "th"
    TAGALOG = "tl"
    TURKISH = "tr"
    UKRAINIAN = "uk"
    URDU = "ur"
    VIETNAMESE = "vi"
    CHINESE_SIMPLIFIED = "zh"


class ResultType(str, Enum):
    """General category of search results to retrieve."""

    WEB = "web"
    NEWS = "news"
    IMAGES = "images"
    VIDEOS = "videos"


class SafeSearchLevel(str, Enum):
    """Safe-search filtering level applied to results.

    - ``off``      — No filtering; adult content may appear.
    - ``moderate`` —过滤 explicit content but allow mature themes.
    - ``strict``  — Remove all adult content.
    """

    OFF = "off"
    MODERATE = "moderate"
    STRICT = "strict"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class SearchQuery(BaseModel):
    """A structured search query consumable by any :class:`SearchProvider`.

    This model is provider-agnostic. Each concrete provider is responsible
    for mapping these fields to its own API parameters (e.g. Google's ``lr``,
    ``cr``, ``safe``) when executing the search.

    Attributes
    ----------
    query:
        The raw query string. May contain boolean operators, quoted phrases,
        or site: modifiers depending on provider support.
    language:
        Two-letter ISO 639-1 language code to bias results toward a locale.
        ``None`` instructs the provider to use its default.
    region:
        Regional targeting hint in ``xx-XX`` format (e.g. ``us-US``).
        ``None`` means no regional constraint is applied.
    max_results:
        Maximum number of results to return. Providers may return fewer.
    result_type:
        Category of results (web, news, images, …).
    safe_search:
        Content-safety filter level.
    site_restriction:
        Optional domain restriction prepended as ``site:<domain>``.
    custom_parameters:
        Provider-specific overrides. Values here take precedence over
        derived defaults. Use with caution — no validation is performed
        on keys or values.
    """

    query: Annotated[str, Field(
        ...,
        min_length=1,
        max_length=500,
        description="The search query string. Max 500 characters.",
    )]
    language: SearchLanguage | None = Field(
        default=None,
        description="ISO 639-1 language code to bias results toward (e.g. 'en').",
    )
    region: Annotated[str | None, Field(
        default=None,
        pattern=r"^[a-z]{2}-(?:[A-Z]{2}|en)$",
        description="Regional code in xx-XX format or DuckDuckGo locale form (e.g. 'us-US' or 'us-en').",
    )]
    max_results: Annotated[int, Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return.",
    )]
    result_type: ResultType = Field(
        default=ResultType.WEB,
        description="Category of results to retrieve.",
    )
    safe_search: SafeSearchLevel = Field(
        default=SafeSearchLevel.MODERATE,
        description="Safe-search filter level.",
    )
    site_restriction: Annotated[str | None, Field(
        default=None,
        max_length=200,
        description="Optional domain to restrict results to (site:<domain>).",
    )]
    custom_parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Provider-specific parameter overrides. No validation is performed.",
    )

    model_config = {"str_strip_whitespace": True}