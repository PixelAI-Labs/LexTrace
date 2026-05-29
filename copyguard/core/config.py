"""
CopyGuard core configuration.

Loads all settings from environment variables using Pydantic Settings.
This is the single source of truth for every module in the service.

Required env vars (no defaults — fail fast if missing):
    GOOGLE_API_KEY        → google.api_key
    GOOGLE_SEARCH_ENGINE_ID → google.search_engine_id

All other values have defaults. See each Settings subclass for details.

Env var format:
    Top-level fields:       <FIELD_NAME>          (e.g.  APP_PORT=9000)
    Nested namespace fields: <PREFIX>_<FIELD_NAME>  (e.g.  GOOGLE_MAX_RESULTS_PER_QUERY=10)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Namespace settings groups
# ---------------------------------------------------------------------------


class GoogleSettings(BaseSettings):
    """Google Custom Search API configuration.

    Required:
        GOOGLE_API_KEY
        GOOGLE_SEARCH_ENGINE_ID
    Optional (with defaults):
        GOOGLE_MAX_RESULTS_PER_QUERY=10
        GOOGLE_REQUEST_TIMEOUT_SECONDS=15.0
    """

    api_key: str = Field(..., description="Google API key for Custom Search JSON API")
    search_engine_id: str = Field(..., description="Google CX engine identifier")
    max_results_per_query: int = Field(default=10, ge=1, le=50)
    request_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)

    model_config = SettingsConfigDict(env_prefix="GOOGLE_")


class ContentExtractionSettings(BaseSettings):
    """Content extraction (web scraping) configuration.

    All fields optional. Defaults:
        CONTENT_REQUEST_TIMEOUT_SECONDS=15.0
        CONTENT_MAX_CONCURRENT_EXTRACTIONS=10
        CONTENT_RETRY_ATTEMPTS=3
        CONTENT_RETRY_BACKOFF_BASE_SECONDS=1.0
    """

    request_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    max_concurrent_extractions: int = Field(default=10, ge=1, le=50)
    retry_attempts: int = Field(default=3, ge=0, le=5)
    retry_backoff_base_seconds: float = Field(default=1.0, ge=0.5, le=10.0)
    user_agent: str = Field(default="CopyGuard/1.0 (+https://github.com/lextrace)")

    model_config = SettingsConfigDict(env_prefix="CONTENT_")


class RateLimitingSettings(BaseSettings):
    """Token-bucket rate limiter tiers.

    All fields optional. Defaults:
        RATE_LIMIT_REQUESTS_PER_MINUTE=10
        RATE_LIMIT_GOOGLE_QUERIES_PER_DAY=100
        RATE_LIMIT_CONTENT_PER_MINUTE_PER_DOMAIN=20
        RATE_LIMIT_BUCKET_CAPACITY=10
    """

    requests_per_minute: int = Field(default=10, ge=1, le=1000)
    google_queries_per_day: int = Field(default=100, ge=1, le=10000)
    content_per_minute_per_domain: int = Field(default=20, ge=1, le=1000)
    bucket_capacity: int = Field(default=10, ge=1, le=100)

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")


class DiscoverySettings(BaseSettings):
    """Discovery pipeline behaviour defaults.

    All fields optional. Defaults:
        DISCOVERY_DEFAULT_MAX_CANDIDATES=20
        DISCOVERY_DEFAULT_SEARCH_DEPTH=shallow
        DISCOVERY_MAX_QUERIES_PER_DISCOVERY=8
        DISCOVERY_CANDIDATE_TTL_SECONDS=3600
        DISCOVERY_INCLUDE_CONTENT_BY_DEFAULT=true
    """

    default_max_candidates: int = Field(default=20, ge=1, le=50)
    default_search_depth: Literal["shallow", "deep"] = Field(default="shallow")
    max_queries_per_discovery: int = Field(default=8, ge=1, le=20)
    candidate_ttl_seconds: int = Field(default=3600, ge=60)
    include_content_by_default: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="DISCOVERY_")


class LoggingSettings(BaseSettings):
    """Structured logging configuration.

    All fields optional. Defaults:
        LOG_LEVEL=INFO
        LOG_FORMAT=json
        LOG_REQUEST_ID_HEADER=X-Request-ID

    LOG_LEVEL is case-insensitive; "info" and "INFO" are equivalent.
    """

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    format: Literal["json", "text"] = Field(default="json")
    request_id_header: str = Field(default="X-Request-ID")

    model_config = SettingsConfigDict(env_prefix="LOG_")

    @field_validator("level", mode="before")
    @classmethod
    def _uppercase_level(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v


class AppSettings(BaseSettings):
    """Application server configuration.

    All fields optional. Defaults:
        APP_HOST=0.0.0.0
        APP_PORT=8000
        APP_DEBUG=false
        APP_RELOAD=false
    """

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)

    model_config = SettingsConfigDict(env_prefix="APP_")

    @property
    def is_production(self) -> bool:
        return not self.debug

    @property
    def is_debug(self) -> bool:
        return self.debug


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Root configuration aggregating all namespace groups.

    Two fields are required (no defaults — app fails fast if absent):
        google.api_key       (env: GOOGLE_API_KEY)
        google.search_engine_id (env: GOOGLE_SEARCH_ENGINE_ID)

    All others have defaults and are optional.

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
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def to_public_dict(self) -> dict:
        """Dump settings as a dict, redacting known secret field names.

        Use this for logging and debugging. Never use model_dump() directly —
        it may include sensitive values.
        """
        return _redact(self.model_dump())


# ---------------------------------------------------------------------------
# Module-level singleton (initialised on first import)
# ---------------------------------------------------------------------------

settings = Settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRETS: frozenset[str] = frozenset({"api_key", "search_engine_id"})


def _redact(d: dict) -> dict:
    """Recursively replace known secret field values with '[REDACTED]'."""
    result = {}
    for k, v in d.items():
        if k in _SECRETS and isinstance(v, str):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = _redact(v)
        else:
            result[k] = v
    return result