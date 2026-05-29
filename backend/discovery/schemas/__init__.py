"""Schemas package — request and response Pydantic models."""

from backend.discovery.schemas.requests import DiscoveryOptions, DiscoveryRequest
from backend.discovery.schemas.responses import (
    CandidateArticle,
    DiscoveryMetadata,
    DiscoveryResponse,
)
from backend.discovery.schemas.search_query import (
    ResultType,
    SafeSearchLevel,
    SearchLanguage,
    SearchQuery,
)
from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection

__all__ = [
    # Discovery
    "CandidateArticle",
    "DiscoveryMetadata",
    "DiscoveryOptions",
    "DiscoveryRequest",
    "DiscoveryResponse",
    # Search query
    "ResultType",
    "SafeSearchLevel",
    "SearchLanguage",
    "SearchQuery",
    # Search result
    "SearchResult",
    "SearchResultCollection",
]