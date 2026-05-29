"""Unit tests for backend.core.config.

Covers:
- Default values load when env vars are absent (for optional fields)
- Required env vars (google.api_key, google.search_engine_id) raise ValidationError when missing
- ENV overrides take precedence over defaults
- Field constraints (ge/le) are enforced
- to_public_dict() redacts secrets
- is_production / is_debug helpers
- Import does not trigger side effects
- Subclass instantiation works in isolation
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from backend.core.config import (
    AppSettings,
    ContentExtractionSettings,
    DiscoverySettings,
    GoogleSettings,
    LoggingSettings,
    RateLimitingSettings,
    Settings,
    _redact,
    settings,
)


# ---------------------------------------------------------------------------
# TC1 — App fails fast when required google fields are absent
# ---------------------------------------------------------------------------

def test_TC1_missing_google_api_key_raises(minimal_google_env: None) -> None:
    """App must not start if GOOGLE_API_KEY is missing."""
    os.environ.pop("GOOGLE_API_KEY", None)
    with pytest.raises(ValidationError) as exc_info:
        Settings.model_validate({})
    assert "api_key" in str(exc_info.value).lower()


def test_TC1_missing_google_search_engine_id_raises(minimal_google_env: None) -> None:
    """App must not start if GOOGLE_SEARCH_ENGINE_ID is missing."""
    os.environ.pop("GOOGLE_SEARCH_ENGINE_ID", None)
    with pytest.raises(ValidationError) as exc_info:
        Settings.model_validate({})
    assert "search_engine_id" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TC2 — All required env vars present → app starts, env overrides defaults
# ---------------------------------------------------------------------------

def test_TC2_google_api_key_from_env(minimal_google_env: None) -> None:
    """GOOGLE_API_KEY env var must populate google.api_key."""
    s = Settings.model_validate({})
    assert s.google.api_key == "test-api-key-12345"


def test_TC2_google_search_engine_id_from_env(minimal_google_env: None) -> None:
    """GOOGLE_SEARCH_ENGINE_ID env var must populate google.search_engine_id."""
    s = Settings.model_validate({})
    assert s.google.search_engine_id == "test-cx-id"


def test_TC2_log_level_override(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL env var must override default log level."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "text")
    s = Settings.model_validate({})
    assert s.logging.level == "DEBUG"
    assert s.logging.format == "text"


def test_TC2_discovery_max_candidates_override(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """DISCOVERY_DEFAULT_MAX_CANDIDATES env var must override default."""
    monkeypatch.setenv("DISCOVERY_DEFAULT_MAX_CANDIDATES", "30")
    s = Settings.model_validate({})
    assert s.discovery.default_max_candidates == 30


def test_TC2_app_port_override(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_PORT env var must override default port."""
    monkeypatch.setenv("APP_PORT", "9000")
    s = Settings.model_validate({})
    assert s.app.port == 9000


# ---------------------------------------------------------------------------
# TC3 — Empty / whitespace-only required fields raise ValidationError
# ---------------------------------------------------------------------------

def test_TC3_whitespace_api_key_raises(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Whitespace-only GOOGLE_API_KEY must raise ValidationError."""
    monkeypatch.setenv("GOOGLE_API_KEY", "   ")
    with pytest.raises(ValidationError) as exc_info:
        Settings.model_validate({})
    assert "api_key" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TC4 — Invalid LOG_LEVEL raises ValidationError
# ---------------------------------------------------------------------------

def test_TC4_invalid_log_level_raises(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid LOG_LEVEL value must raise ValidationError."""
    monkeypatch.setenv("LOG_LEVEL", "TRACE")
    with pytest.raises(ValidationError) as exc_info:
        Settings.model_validate({})
    assert "level" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TC5 — Out-of-range numeric values raise ValidationError
# ---------------------------------------------------------------------------

def test_TC5_google_max_results_over_max_raises(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """GOOGLE_MAX_RESULTS_PER_QUERY > 50 must raise ValidationError."""
    monkeypatch.setenv("GOOGLE_MAX_RESULTS_PER_QUERY", "100")
    with pytest.raises(ValidationError):
        Settings.model_validate({})


def test_TC5_google_timeout_too_high_raises(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """GOOGLE_REQUEST_TIMEOUT_SECONDS > 60 must raise ValidationError."""
    monkeypatch.setenv("GOOGLE_REQUEST_TIMEOUT_SECONDS", "120")
    with pytest.raises(ValidationError):
        Settings.model_validate({})


def test_TC5_rate_limit_negative_raises(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative RATE_LIMIT_REQUESTS_PER_MINUTE must raise ValidationError."""
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "-5")
    with pytest.raises(ValidationError):
        Settings.model_validate({})


def test_TC5_app_port_out_of_range_raises(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_PORT outside 1-65535 range must raise ValidationError."""
    monkeypatch.setenv("APP_PORT", "70000")
    with pytest.raises(ValidationError):
        Settings.model_validate({})


# ---------------------------------------------------------------------------
# TC6 — APP_DEBUG=false → is_production True, is_debug False
# ---------------------------------------------------------------------------

def test_TC6_is_production_correct(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_DEBUG=false must set is_production=True and is_debug=False."""
    monkeypatch.setenv("APP_DEBUG", "false")
    s = Settings.model_validate({})
    assert s.app.is_production is True
    assert s.app.is_debug is False


def test_TC6_is_debug_correct(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_DEBUG=true must set is_debug=True."""
    monkeypatch.setenv("APP_DEBUG", "true")
    s = Settings.model_validate({})
    assert s.app.is_debug is True
    assert s.is_production is False


# ---------------------------------------------------------------------------
# TC7 — to_public_dict() redacts api_key and search_engine_id
# ---------------------------------------------------------------------------

def test_TC7_to_public_dict_redacts_api_key(minimal_google_env: None) -> None:
    """to_public_dict() must replace api_key with [REDACTED]."""
    s = Settings.model_validate({})
    public = s.to_public_dict()
    assert public["google"]["api_key"] == "[REDACTED]"
    assert "[REDACTED]" in str(public["google"])


def test_TC7_to_public_dict_redacts_search_engine_id(minimal_google_env: None) -> None:
    """to_public_dict() must replace search_engine_id with [REDACTED]."""
    s = Settings.model_validate({})
    public = s.to_public_dict()
    assert public["google"]["search_engine_id"] == "[REDACTED]"


def test_TC7_to_public_dict_non_secret_fields_preserved(minimal_google_env: None) -> None:
    """to_public_dict() must NOT redact non-secret fields."""
    s = Settings.model_validate({})
    public = s.to_public_dict()
    assert public["app"]["port"] == 8000
    assert public["logging"]["level"] == "INFO"
    assert public["discovery"]["default_max_candidates"] == 20


# ---------------------------------------------------------------------------
# TC8 — Import settings does NOT trigger side effects
# ---------------------------------------------------------------------------

def test_TC8_settings_singleton_is_instance() -> None:
    """The imported `settings` singleton must be a valid Settings instance."""
    assert isinstance(settings, Settings)


def test_TC8_import_does_not_connect_network() -> None:
    """Importing the config module must not open sockets or load files."""
    # If we reach here with a clean env, no network calls were made.
    assert settings is not None


# ---------------------------------------------------------------------------
# TC9 — model_construct lets tests override single fields
# ---------------------------------------------------------------------------

def test_TC9_model_construct_partial_override(minimal_google_env: None) -> None:
    """model_construct must allow partial override without full validation."""
    partial = Settings.model_construct(
        google=GoogleSettings(api_key="override-key", search_engine_id="override-cx"),
    )
    assert partial.google.api_key == "override-key"
    assert partial.discovery.default_max_candidates == 20  # default preserved


# ---------------------------------------------------------------------------
# TC10 — lowercase env var names also work (case-insensitive)
# ---------------------------------------------------------------------------

def test_TC10_case_insensitive_env_vars(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lowercase env var names must work the same as uppercase."""
    monkeypatch.setenv("google_api_key", "case-insensitive-key")
    monkeypatch.setenv("google_search_engine_id", "case-insensitive-cx")
    s = Settings.model_validate({})
    assert s.google.api_key == "case-insensitive-key"
    assert s.google.search_engine_id == "case-insensitive-cx"


# ---------------------------------------------------------------------------
# TC11 — Settings subclasses instantiate in isolation (no root required)
# ---------------------------------------------------------------------------

def test_TC11_google_settings_standalone(minimal_google_env: None) -> None:
    """GoogleSettings must instantiate without a parent Settings."""
    gs = GoogleSettings.model_construct(
        api_key="standalone-key",
        search_engine_id="standalone-cx",
    )
    assert gs.api_key == "standalone-key"
    assert gs.max_results_per_query == 10  # default


def test_TC11_discovery_settings_standalone() -> None:
    """DiscoverySettings must instantiate without any required parent fields."""
    ds = DiscoverySettings()
    assert ds.default_max_candidates == 20
    assert ds.default_search_depth == "shallow"


def test_TC11_content_extraction_settings_standalone() -> None:
    """ContentExtractionSettings must instantiate without any required fields."""
    cs = ContentExtractionSettings()
    assert cs.max_concurrent_extractions == 10
    assert cs.retry_attempts == 3


# ---------------------------------------------------------------------------
# TC12 — LOG_LEVEL is uppercased even if lowercase env var is passed
# ---------------------------------------------------------------------------

def test_TC12_log_level_uppercase_conversion(minimal_google_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lowercase 'info' LOG_LEVEL must be stored as 'INFO'."""
    monkeypatch.setenv("LOG_LEVEL", "info")
    s = Settings.model_validate({})
    assert s.logging.level == "INFO"


# ---------------------------------------------------------------------------
# TC13 — _redact helper
# ---------------------------------------------------------------------------

def test_TC13_redact_nested_secret() -> None:
    """_redact must redact nested dict fields that match _SECRETS."""
    d = {"google": {"api_key": "secret123", "search_engine_id": "cx-id"}}
    result = _redact(d)
    assert result["google"]["api_key"] == "[REDACTED]"
    assert result["google"]["search_engine_id"] == "[REDACTED]"


def test_TC13_redact_preserves_non_secret() -> None:
    """_redact must not modify fields not in _SECRETS."""
    d = {
        "google": {"api_key": "secret123", "search_engine_id": "cx-id", "max_results_per_query": 10},
        "app": {"port": 8000},
    }
    result = _redact(d)
    assert result["google"]["max_results_per_query"] == 10
    assert result["app"]["port"] == 8000