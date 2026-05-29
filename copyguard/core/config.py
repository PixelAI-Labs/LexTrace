"""
CopyGuard core configuration.

Loads all settings from environment variables using Pydantic Settings.
This is the single source of truth for every module in the service.

Required env vars (no defaults — fail fast if missing):
    GOOGLE_API_KEY
    GOOGLE_SEARCH_ENGINE_ID

All other values have defaults. See each Settings subclass for details.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Namespace settings groups
# ---------------------------------------------------------------------------


class GoogleSettings(BaseSettings):
    """Google Custom Search API configuration."""

    api_key: str = Field(..., description="Google API key for Custom Search JSON API")
    search_engine_id: str = Field(..., description="Google CX engine identifier")
    max_results_per_query: int = Field(default=10, ge=1, le=50, description="Max results per query")
    request_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)

    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )


class ContentExtractionSettings(BaseSettings):
    """Content extraction (web scraping) configuration."""

    request_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    max_concurrent_extractions: int = Field(default=10, ge=1, le=50)
    retry_attempts: int = Field(default=3, ge=0, le=5)
    retry_backoff_base_seconds: float = Field(default=1.0, ge=0.5, le=10.0)
    user_agent: str = Field(default="CopyGuard/1.0 (+https://github.com/lextrace)")

    model_config = SettingsConfigDict(env_prefix="CONTENT_", env_nested_delimiter="__")


class RateLimitingSettings(BaseSettings):
    """Rate limiting tier configuration."""

    requests_per_minute: int = Field(default=10, ge=1, le=1000)
    google_queries_per_day: int = Field(default=100, ge=1, le=10000)
    content_per_minute_per_domain: int = Field(default=20, ge=1, le=1000)
    bucket_capacity: int = Field(default=10, ge=1, le=100)

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_", env_nested_delimiter="__")


class DiscoverySettings(BaseSettings):
    """Discovery pipeline defaults."""

    default_max_candidates: int = Field(default=20, ge=1, le=50)
    default_search_depth: Literal["shallow", "deep"] = Field(default="shallow")
    max_queries_per_discovery: int = Field(default=8, ge=1, le=20)
    candidate_ttl_seconds: int = Field(default=3600, ge=60)
    include_content_by_default: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="DISCOVERY_", env_nested_delimiter="__")


class LoggingSettings(BaseSettings):
    """Structured logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    format: Literal["json", "text"] = Field(default="json")
    request_id_header: str = Field(default="X-Request-ID")

    model_config = SettingsConfigDict(env_prefix="LOG_", env_nested_delimiter="__")

    @field_validator("level", mode="before")
    @classmethod
    def _uppercase_level(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v


class AppSettings(BaseSettings):
    """Application server configuration."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)

    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")

    @cached_property
    def is_production(self) -> bool:
        return not self.debug

    @cached_property
    def is_debug(self) -> bool:
        return self.debug


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Root configuration aggregating all namespace groups.

    Attributes:
        google: Google Custom Search API settings. Required — raises ValidationError
                on startup if GOOGLE_API_KEY or GOOGLE_SEARCH_ENGINE_ID is absent.
        content_extraction: Web scraping / content extraction settings. All optional.
        rate_limiting: Token-bucket rate limiter settings. All optional.
        discovery: Discovery pipeline defaults. All optional.
        logging: Structured logger settings. All optional.
        app: Application server settings. All optional.

    Example:
        >>> from copyguard.core.config import settings
        >>> settings.google.api_key
        'AIza...'
        >>> settings.discovery.default_max_candidates
        20
    """

    google: GoogleSettings
    content_extraction: ContentExtractionSettings = Field(default_factory=ContentExtractionSettings)
    rate_limiting: RateLimitingSettings = Field(default_factory=RateLimitingSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    app: AppSettings = Field(default_factory=AppSettings)

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @cached_property
    def is_production(self) -> bool:
        return self.app.is_production

    def to_public_dict(self) -> dict:
        """Return a read-only dict suitable for logging / debugging.

        All secret fields (api_key) are redacted.
        """
        return _redact(self.model_dump())


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

settings = Settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRETS = {"api_key"}


def _redact(d: dict, _secrets: frozenset[str] = _SECRETS) -> dict:
    """Recursively redact known secret field names."""
    result = {}
    for k, v in d.items():
        if k in _secrets and isinstance(v, str):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = _redact(v)
        else:
            result[k] = v
    return result