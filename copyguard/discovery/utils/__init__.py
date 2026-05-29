"""Text processing utilities for the Discovery Service."""

from copyguard.discovery.utils.text_utils import (
    clean_text,
    extract_keywords,
    extract_keywords_flat,
    extract_paragraphs,
    extract_sentences,
    normalize,
    remove_html_tags_fast,
    strip_html,
    truncate,
)

__all__ = [
    "strip_html",
    "remove_html_tags_fast",
    "normalize",
    "clean_text",
    "extract_sentences",
    "extract_paragraphs",
    "extract_keywords",
    "extract_keywords_flat",
    "truncate",
]