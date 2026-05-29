"""Providers package — search provider abstraction layer."""
from backend.discovery.providers.base import ProviderName, SearchProvider
from backend.discovery.providers.duckduckgo import DuckDuckGoError, DuckDuckGoProvider

__all__ = ["DuckDuckGoError", "DuckDuckGoProvider", "ProviderName", "SearchProvider"]