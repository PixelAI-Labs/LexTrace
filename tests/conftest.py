"""Pytest fixtures for CopyGuard unit tests."""

from __future__ import annotations

import os
from typing import Generator

import pytest

from copyguard.core.config import (
    AppSettings,
    ContentExtractionSettings,
    DiscoverySettings,
    GoogleSettings,
    LoggingSettings,
    RateLimitingSettings,
    Settings,
)


@pytest.fixture(autouse=True)
def clean_env() -> Generator[None, None, None]:
    """Erase all CopyGuard-related env vars before and after each test."""
    prefixes = (
        "GOOGLE_",
        "CONTENT_",
        "RATE_LIMIT_",
        "DISCOVERY_",
        "LOG_",
        "APP_",
    )
    # Capture original values
    originals = {k: os.environ.get(k) for k in os.environ if any(k.startswith(p) for p in prefixes)}
    # Wipe before test
    for k in list(os.environ.keys()):
        if any(k.startswith(p) for p in prefixes):
            os.environ.pop(k)

    yield

    # Restore after test
    for k, v in originals.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def minimal_google_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set only the required Google env vars."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test-cx-id")


@pytest.fixture
def google_settings() -> GoogleSettings:
    return GoogleSettings(
        api_key="test-key",
        search_engine_id="test-cx",
        max_results_per_query=10,
        request_timeout_seconds=15.0,
    )


@pytest.fixture
def content_extraction_settings() -> ContentExtractionSettings:
    return ContentExtractionSettings(
        request_timeout_seconds=10.0,
        max_concurrent_extractions=5,
        retry_attempts=2,
    )


@pytest.fixture
def rate_limiting_settings() -> RateLimitingSettings:
    return RateLimitingSettings(
        requests_per_minute=20,
        google_queries_per_day=50,
        bucket_capacity=5,
    )


@pytest.fixture
def discovery_settings() -> DiscoverySettings:
    return DiscoverySettings(
        default_max_candidates=10,
        default_search_depth="shallow",
        max_queries_per_discovery=4,
    )


@pytest.fixture
def logging_settings() -> LoggingSettings:
    return LoggingSettings(level="DEBUG", format="text")


@pytest.fixture
def app_settings() -> AppSettings:
    return AppSettings(host="127.0.0.1", port=9000, debug=True)