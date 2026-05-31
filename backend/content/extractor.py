"""Content extraction from URLs using trafilatura."""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.parse
import urllib.robotparser
from asyncio import to_thread as _to_thread
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import trafilatura
from trafilatura.metadata import extract_metadata
from pydantic import BaseModel, Field

from backend.core.config import ContentExtractionSettings


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ExtractedArticle(BaseModel):
    """Structured content from a scraped webpage."""

    url: str = Field(..., description="Canonical URL the content was fetched from.")
    title: str | None = Field(default=None, description="Article title extracted by trafilatura.")
    text: str = Field(..., description="Boilerplate-free article text. Empty if extraction failed.")
    text_length: int = Field(..., ge=0, description="Word count of the extracted text.")
    excerpt: str | None = Field(
        default=None,
        description="First 200 characters of text, or a standalone description field from the page.",
    )
    author: str | None = Field(default=None, description="Author name if detected, otherwise None.")
    publish_date: str | None = Field(
        default=None,
        description="ISO 8601 date string (YYYY-MM-DD) if detected, otherwise None.",
    )
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code detected by trafilatura, e.g. 'en'.",
    )
    extraction_mode: Literal["article", "text", "comments", "json"] = Field(
        default="article",
        description="Which trafilatura extraction mode was used.",
    )
    raw_html: str | None = Field(
        default=None,
        description="Raw HTML response body. Set to None after extraction unless include_raw_html is True.",
    )

    def __init__(self, **data: object) -> None:
        # Derive text_length from text when not explicitly provided
        if "text_length" not in data and "text" in data:
            data["text_length"] = len(str(data["text"]).split())
        super().__init__(**data)


class ExtractionResult(BaseModel):
    """A single URL extraction attempt, either succeeded or failed."""

    url: str = Field(..., description="URL that was attempted.")
    article: ExtractedArticle | None = Field(
        default=None,
        description="Populated if extraction succeeded. None if all attempts failed.",
    )
    status: Literal["success", "failed", "no_text"] = Field(
        ...,
        description=(
            "'success' - article extracted with non-empty text. "
            "'no_text' - extraction succeeded but text is empty (probably a non-article page). "
            "'failed' - network error or unexpected exception after all retries."
        ),
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error description if status is 'failed'. None otherwise.",
    )
    attempts: int = Field(..., ge=1, description="Number of download attempts made.")
    elapsed_ms: int = Field(..., ge=0, description="Wall-clock time spent in milliseconds.")
    provider_name: str = Field(
        default="trafilatura",
        description="Identifier of the extraction backend used.",
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContentExtractorConfig:
    """Immutable configuration for ContentExtractor.

    Derived from ContentExtractionSettings with additional defaults
    for fields not present in the settings.
    """

    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base_seconds: float = 1.0
    user_agent: str = "CopyGuard/1.0 (+https://github.com/lextrace)"
    include_raw_html: bool = False
    extraction_mode: Literal["article", "text"] = "article"
    min_text_length: int = 50

    @classmethod
    def from_settings(
        cls, settings: ContentExtractionSettings | None = None
    ) -> ContentExtractorConfig:
        """Build a config from ContentExtractionSettings.

        If settings is None, reads from the environment via
        ContentExtractionSettings (which applies env-prefix CONTENT_).
        """
        if settings is None:
            settings = ContentExtractionSettings()
        return cls(
            timeout_seconds=settings.request_timeout_seconds,
            max_retries=settings.retry_attempts,
            retry_backoff_base_seconds=settings.retry_backoff_base_seconds,
            user_agent=settings.user_agent,
        )


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------


class ContentExtractor:
    """Extract article content from web URLs using trafilatura.

    Thread-safe: separate instances have independent state.
    """

    __slots__ = ("_cfg",)

    def __init__(self, config: ContentExtractorConfig | None = None) -> None:
        """Create an extractor. Pass a custom config or use the default."""
        self._cfg = config if config is not None else ContentExtractorConfig.from_settings()

    def extract(self, url: str) -> ExtractionResult:
        """Extract article content from a URL.

        Synchronous. Thread-safe.

        Parameters
        ----------
        url:
            Full HTTP or HTTPS URL to extract. Must be 1-2000 characters.

        Returns
        -------
        ExtractionResult
            Always returns a result (never raises).
            Check ``result.status`` before accessing ``result.article``.

        Raises
        ------
        ValueError
            If ``url`` is not a valid HTTP/HTTPS URL (1-2000 chars, http/https scheme).
        """
        _validate_url(url)

        start_ms = _current_ms()
        cfg = self._cfg
        attempt_limit = max(1, cfg.max_retries)

        # robots.txt check before any download
        if _is_robots_blocked(url):
            return ExtractionResult(
                url=url,
                article=None,
                status="failed",
                error_message="Blocked by robots.txt",
                attempts=1,
                elapsed_ms=_current_ms() - start_ms,
            )

        last_error: str | None = None
        for attempt in range(1, attempt_limit + 1):
            try:
                result = _do_extract(url, cfg)
                return ExtractionResult(
                    url=result.url,
                    article=result.article,
                    status=result.status,
                    error_message=result.error_message,
                    attempts=attempt,
                    elapsed_ms=_current_ms() - start_ms,
                    provider_name=result.provider_name,
                )
            except Exception as exc:  # noqa: BLE001  intentionally broad
                last_error = str(exc)
                if attempt < cfg.max_retries:
                    delay = cfg.retry_backoff_base_seconds * (2 ** (attempt - 1)) + 0.25
                    time.sleep(min(delay, cfg.timeout_seconds))

        # All retries exhausted
        return ExtractionResult(
            url=url,
            article=None,
            status="failed",
            error_message=last_error or "Unknown error after all retries",
            attempts=attempt_limit,
            elapsed_ms=_current_ms() - start_ms,
        )

    async def extract_async(self, url: str) -> ExtractionResult:
        """Async variant - runs extract() in a thread to avoid blocking.

        Same contract as ``extract()`` but non-blocking.
        """
        return await _to_thread(self.extract, url)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


async def extract_url(
    url: str,
    config: ContentExtractorConfig | None = None,
) -> ExtractionResult:
    """Async convenience - create a default extractor and call extract_async()."""
    extractor = ContentExtractor(config)
    return await extractor.extract_async(url)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_WS_COLLAPSE: re.Pattern[str] = re.compile(r"\s{2,}")


def _validate_url(url: str) -> None:
    """Raise ValueError if url is not a valid HTTP/HTTPS URL."""
    if not url:
        raise ValueError("URL must not be empty")
    if len(url) > 2000:
        raise ValueError("URL must be at most 2000 characters")
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must use http or https scheme")


def _is_robots_blocked(url: str) -> bool:
    """Check robots.txt; return True if the URL is disallowed."""
    try:
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robot_parser = urllib.robotparser.RobotFileParser()
        robot_parser.set_url(robots_url)
        robot_parser.read()
        return not robot_parser.can_fetch("*", url)
    except Exception:  # noqa: BLE001
        # If we cannot read robots.txt, allow the fetch
        return False


def _do_extract(url: str, cfg: ContentExtractorConfig) -> ExtractionResult:
    """Perform a single extraction attempt with trafilatura."""
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        return ExtractionResult(
            url=url,
            article=None,
            status="failed",
            error_message="No content downloaded (server returned empty response)",
            attempts=1,
            elapsed_ms=0,
        )

    raw_html: str | None = None
    if cfg.include_raw_html:
        raw_html = _truncate_raw_html(downloaded)

    result = trafilatura.extract(
        downloaded,
        url=url,
        output_format="json",
        include_comments=False,
        include_tables=True,
    )

    if result is None:
        return ExtractionResult(
            url=url,
            article=None,
            status="no_text",
            error_message=None,
            attempts=1,
            elapsed_ms=0,
        )

    data, extracted_text = _coerce_trafilatura_result(result)
    metadata = extract_metadata(downloaded, default_url=url)
    canonical_url = getattr(metadata, "url", None) or url

    title = _norm(data.get("title")) if data.get("title") else None
    text = _norm(data.get("text") or extracted_text) or ""
    text_length = len(text.split())

    article = ExtractedArticle(
        url=canonical_url,
        title=title,
        text=text,
        text_length=text_length,
        excerpt=_build_excerpt(text),
        author=_norm_author(data.get("author")),
        publish_date=_norm_date(data.get("publishDate")),
        language=data.get("language") or None,
        extraction_mode=cfg.extraction_mode,
        raw_html=raw_html,
    )

    if text_length < cfg.min_text_length:
        status: Literal["success", "failed", "no_text"] = "no_text"
    else:
        status = "success"

    return ExtractionResult(
        url=canonical_url,
        article=article,
        status=status,
        error_message=None,
        attempts=1,
        elapsed_ms=0,
    )


def _norm(value: str | None) -> str | None:
    """NFKC-normalize, collapse whitespace, strip."""
    if not value:
        return None
    return unicodedata.normalize("NFKC", _WS_COLLAPSE.sub(" ", value)).strip()


def _norm_author(author: str | list[str] | None) -> str | None:
    """Flatten an author value to a plain string or None."""
    if author is None:
        return None
    if isinstance(author, list):
        return ", ".join(str(a).strip() for a in author if a)
    return _norm(str(author))


def _norm_date(publish_date: str | date | datetime | None) -> str | None:
    """Parse and reformat publish_date to ISO 8601 YYYY-MM-DD, or None."""
    if publish_date is None:
        return None
    if isinstance(publish_date, datetime):
        return publish_date.strftime("%Y-%m-%d")
    if isinstance(publish_date, date):
        return publish_date.strftime("%Y-%m-%d")
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(str(publish_date), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Fall back to the input string if it has some content
    cleaned = str(publish_date).strip()
    return cleaned or None


def _build_excerpt(text: str, max_chars: int = 200) -> str | None:
    """First max_chars of text, breaking on a word boundary."""
    if not text:
        return None
    excerpt = text[:max_chars]
    if len(text) > max_chars:
        excerpt = excerpt.rsplit(" ", 1)[0]
    return excerpt.strip()


def _current_ms() -> int:
    return int(time.monotonic() * 1000)


def _coerce_trafilatura_result(result: object) -> tuple[dict, str | None]:
    """Normalise trafilatura output across return formats.

    Depending on the installed trafilatura version, ``extract(..., output_format="json")``
    can return a mapping or a JSON string. If the value is not structured JSON, preserve
    it as plain text so we still surface extracted body text.
    """
    if isinstance(result, dict):
        return result, None

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return {}, result

        if isinstance(parsed, dict):
            return parsed, None
        if isinstance(parsed, str):
            return {}, parsed

    return {}, None


def _truncate_raw_html(raw_html: str, max_chars: int = 10 * 1024 * 1024) -> str:
    """Limit stored raw HTML to a safe size for debugging payloads."""
    if len(raw_html) <= max_chars:
        return raw_html
    return raw_html[:max_chars]


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "ContentExtractor",
    "ContentExtractorConfig",
    "ExtractedArticle",
    "ExtractionResult",
    "extract_url",
]