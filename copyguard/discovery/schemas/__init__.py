"""Discovery Service — Pydantic schemas for requests and responses."""

from copyguard.discovery.schemas.requests import DiscoveryOptions, DiscoveryRequest
from copyguard.discovery.schemas.responses import (
    CandidateArticle,
    DiscoveryMetadata,
    DiscoveryResponse,
)

__all__ = [
    "DiscoveryOptions",
    "DiscoveryRequest",
    "CandidateArticle",
    "DiscoveryMetadata",
    "DiscoveryResponse",
]