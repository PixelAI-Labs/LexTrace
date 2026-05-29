"""
Query Generator Service for the Discovery Service.

Generates 3–8 targeted Google search queries from an article's text (and
optionally its title) to maximise recall of suspected pirated copies while
minimising irrelevant results.

Two operating modes:
- **shallow**: 3–5 queries — exact title + keyword pairs + topic phrases
- **deep**    : up to 8 queries — adds question forms, listicle variants

No Google API calls, no network I/O, no sklearn dependency.
All keyword extraction delegates to ``backend.discovery.utils.text_utils``.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from backend.discovery.utils.text_utils import clean_text, extract_keywords


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class QueryStrategy(Enum):
    """Enumerates the query-generation strategies, ordered by precision.

    Higher precision strategies are listed first and placed first in the
    returned query list so they appear in the API response metadata.
    """

    EXACT_TITLE = "exact_title"
    KEYWORD_PAIR = "keyword_pair"
    TOPIC_PHRASE = "topic_phrase"
    QUESTION_FORM = "question_form"
    LISTICLE_FORM = "listicle_form"
    GENERIC_VARIANT = "generic_variant"


class GeneratedQuery(NamedTuple):
    """A single search query with metadata about how it was generated."""

    text: str
    strategy: QueryStrategy


class QueryGeneratorConfig(NamedTuple):
    """Configuration for a single query generation run.

    Passed in from outside so the service itself is data-free and testable.
    An application layer would typically call ``as_config()`` against
    ``settings.discovery`` to produce an instance.
    """

    max_queries: int = 8
    min_word_length: int = 3
    keyword_top_k: int = 20
    include_generic_variants: bool = True


# ---------------------------------------------------------------------------
# Generator helpers (private)
# ---------------------------------------------------------------------------

_GENERIC_SUFFIXES = [
    "article",
    "tutorial",
    "guide",
    "overview",
    "explained",
    "summary",
]

_LISTICLE_STEMS = [
    "complete guide to",
    "the ultimate guide to",
    "everything you need to know about",
    "top things to know about",
    "beginner's guide to",
]

_QUESTION_STEMS = [
    "how to",
    "what is",
    "why does",
    "when did",
    "where to find",
]

# Characters that are not part of a searchable query word
_NON_QUERY_CHARS = r'["\'\-—/:@#$%^&*()+=<>,.!?\\|~`[\]{}§\n\r\t]'

_QUERY_SANITISE = _NON_QUERY_CHARS


def _sanitise(text: str) -> str:
    """Strip non-search characters and normalise internal spaces."""
    import re as _re

    cleaned = _re.sub(_QUERY_SANITISE, " ", text)
    return " ".join(cleaned.split())


def _exact_title_query(title: str | None) -> list[GeneratedQuery]:
    """Priority 1 — exact title phrase (highest precision signal for Google)."""
    if not title:
        return []
    quoted = f'"{_sanitise(title)}"'
    return [GeneratedQuery(text=quoted, strategy=QueryStrategy.EXACT_TITLE)]


def _keyword_pair_queries(keywords: list[tuple[str, float]]) -> list[GeneratedQuery]:
    """Priority 2 — pair the top two keywords as a high-precision phrase search."""
    top_two = [word for word, _ in keywords[:2]]
    if len(top_two) < 2:
        return []
    pair = f'"{_sanitise(top_two[0])}" "{_sanitise(top_two[1])}"'
    return [GeneratedQuery(text=pair, strategy=QueryStrategy.KEYWORD_PAIR)]


def _topic_phrase_queries(keywords: list[tuple[str, float]]) -> list[GeneratedQuery]:
    """Priority 3 — 3–4 most important keywords as a natural phrase query."""
    top = [w for w, _ in keywords[:4]]
    if not top:
        return []
    phrase = " ".join(top[:4])
    return [GeneratedQuery(text=_sanitise(phrase), strategy=QueryStrategy.TOPIC_PHRASE)]


def _generic_variants(
    keywords: list[tuple[str, float]],
    include: bool,
) -> list[GeneratedQuery]:
    """Priority 4 — random keyword + generic term for broader recall."""
    if not include or len(keywords) < 2:
        return []
    queries: list[GeneratedQuery] = []
    for word, _ in keywords[:5]:
        for suffix in _GENERIC_SUFFIXES:
            queries.append(
                GeneratedQuery(
                    text=f"{_sanitise(word)} {suffix}",
                    strategy=QueryStrategy.GENERIC_VARIANT,
                )
            )
    # Return shuffled-ish subset (deterministic: slice rather than random shuffle)
    return queries[:4]


def _deep_queries(
    keywords: list[tuple[str, float]],
    title: str | None,
) -> list[GeneratedQuery]:
    """Additional strategies available only in deep mode."""
    result: list[GeneratedQuery] = []

    # Listicle forms
    if title:
        for stem in _LISTICLE_STEMS[:2]:
            result.append(
                GeneratedQuery(
                    text=f"{stem} {_sanitise(title)}",
                    strategy=QueryStrategy.LISTICLE_FORM,
                )
            )
    # Also listicle with top keyword
    if keywords:
        word, _ = keywords[0]
        for stem in _LISTICLE_STEMS[:2]:
            result.append(
                GeneratedQuery(
                    text=f"{stem} {_sanitise(word)}",
                    strategy=QueryStrategy.LISTICLE_FORM,
                )
            )

    # Question forms using top keywords
    for word, _ in keywords[:3]:
        for stem in _QUESTION_STEMS:
            result.append(
                GeneratedQuery(
                    text=f"{stem} {_sanitise(word)}",
                    strategy=QueryStrategy.QUESTION_FORM,
                )
            )

    return result


def _insert_keyword_pair_queries(
    keywords: list[tuple[str, float]],
    queries: list[GeneratedQuery],
) -> list[GeneratedQuery]:
    """Insert keyword pair queries right after title queries (highest precision)."""
    pairs = _keyword_pair_queries(keywords)
    # Find insertion index (after any EXACT_TITLE queries)
    insert_at = 0
    for i, q in enumerate(queries):
        if q.strategy != QueryStrategy.EXACT_TITLE:
            insert_at = i
            break
    else:
        insert_at = len(queries)
    return queries[:insert_at] + pairs + queries[insert_at:]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_queries(
    article_text: str,
    config: QueryGeneratorConfig | None = None,
    *,
    title: str | None = None,
    search_depth: str = "shallow",
) -> list[str]:
    """Generate a prioritised list of Google-searchable query strings.

    Parameters
    ----------
    article_text:
        Raw article text to analyse. Must be at least 100 characters.
    config:
        Optionally override the generation limits and keyword extraction
        parameters. If omitted, sensible defaults are used (max_queries=8).
    title:
        Optional article title. If provided, an exact-phrase query is
        added as the highest-precision signal.
    search_depth:
        Either ``"shallow"`` (3–5 queries) or ``"deep"`` (up to 8 queries).

    Returns
    -------
    list[str]
        Prioritised list of query strings. Empty list if input text is too short
        to extract meaningful keywords.

    Example
    -------
    >>> generate_queries(
    ...     "Python is a programming language...",
    ...     title="Introduction to Python",
    ...     search_depth="shallow",
    ... )
    ['"Introduction to Python"', '"Python" "programming"', 'python programming...']
    """
    if config is None:
        config = QueryGeneratorConfig()
    if config.max_queries <= 0:
        return []

    # Clean and extract keywords
    cleaned = clean_text(article_text)
    if len(cleaned) < config.min_word_length * 3:
        return []

    keywords = extract_keywords(
        cleaned,
        top_k=config.keyword_top_k,
        min_word_length=config.min_word_length,
    )
    if not keywords:
        return []

    # Build query list in priority order
    queries: list[GeneratedQuery] = []

    # 1. Exact title (always first if available)
    queries.extend(_exact_title_query(title))

    # 2–3. Topic phrase then keyword pairs
    topic = _topic_phrase_queries(keywords)
    queries.extend(topic)

    queries = _insert_keyword_pair_queries(keywords, queries)

    # 4. Generic variants (shallow only)
    queries.extend(
        _generic_variants(keywords, include=config.include_generic_variants)
    )

    # 5. Deep-only strategies
    if search_depth == "deep":
        is_deep = True
    elif search_depth == "shallow":
        is_deep = False
    else:
        # Unknown depth; default to shallow for safety
        is_deep = False

    if is_deep:
        queries.extend(_deep_queries(keywords, title))

    # Deduplicate (case-insensitive) while preserving order
    seen_lower: set[str] = set()
    unique: list[GeneratedQuery] = []
    for q in queries:
        lo = q.text.lower()
        if lo not in seen_lower and len(q.text) >= 3:
            seen_lower.add(lo)
            unique.append(q)

    # Enforce max_queries cap
    return [q.text for q in unique[: config.max_queries]]


# ---------------------------------------------------------------------------
# Optional Config.from_settings bridge
# ---------------------------------------------------------------------------

def as_config(
    max_queries: int | None = None,
    keyword_top_k: int = 20,
    min_word_length: int = 3,
    include_generic_variants: bool = True,
) -> QueryGeneratorConfig:
    """Build a ``QueryGeneratorConfig`` from explicit values.

    Call this in the service/route layer when you want to pull limits
    from ``settings.discovery`` rather than hard-coded defaults:

        config = as_config(
            max_queries=settings.discovery.max_queries_per_discovery,
            keyword_top_k=20,
        )
        queries = generate_queries(text, config, title=title, search_depth='shallow')
    """
    return QueryGeneratorConfig(
        max_queries=8 if max_queries is None else max_queries,
        min_word_length=min_word_length,
        keyword_top_k=keyword_top_k,
        include_generic_variants=include_generic_variants,
    )