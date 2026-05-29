"""Content extraction from URLs via trafilatura."""

from backend.content.extractor import (
    ContentExtractor,
    ContentExtractorConfig,
    ExtractedArticle,
    ExtractionResult,
    extract_url,
)

__all__ = [
    "ContentExtractor",
    "ContentExtractorConfig",
    "ExtractedArticle",
    "ExtractionResult",
    "extract_url",
]