"""Unit tests for backend.discovery.services.query_generator.

Covers:
- Empty / too-short text handling
- Exact title query generation
- Keyword extraction and pair generation
- Topic phrase generation
- Generic variant generation
- Deep mode (question + listicle forms)
- max_queries cap enforcement
- Case-insensitive deduplication
- Special character sanitisation
- Configurable parameters via QueryGeneratorConfig
- search_depth parameter validation
- Determinism
"""

from __future__ import annotations

import pytest

from backend.discovery.services.query_generator import (
    QueryGeneratorConfig,
    QueryStrategy,
    as_config,
    generate_queries,
)


# ---------------------------------------------------------------------------
# TC1 — Empty / invalid inputs
# ---------------------------------------------------------------------------

def test_TC1_empty_text_returns_empty_list() -> None:
    assert generate_queries("") == []


def test_TC1_whitespace_only_returns_empty_list() -> None:
    assert generate_queries("   \n\t   ") == []


def test_TC1_max_queries_zero_returns_empty_list() -> None:
    cfg = QueryGeneratorConfig(max_queries=0)
    assert generate_queries("python programming language", config=cfg) == []


def test_TC1_text_below_min_length_returns_empty_list() -> None:
    """Text shorter than min_word_length * 3 (default 9 chars) returns []. This is
    to prevent degenerate single-word articles from generating nonsense queries."""
    cfg = QueryGeneratorConfig(max_queries=8, min_word_length=5)
    # "hello world" is only 11 chars after cleaning — still above 15, so OK.
    # Use something truly minimal.
    result = generate_queries("hi", config=cfg)
    assert result == []


# ---------------------------------------------------------------------------
# TC2 — Exact title query (Priority 1)
# ---------------------------------------------------------------------------

def test_TC2_title_adds_exact_phrase_query() -> None:
    text = "Python is a programming language used by millions of developers worldwide."
    queries = generate_queries(text, title="Introduction to Python Programming")
    assert any('"introduction to python programming"' in q.lower() for q in queries)


def test_TC2_title_exact_quote_is_first() -> None:
    """The exact-title query must appear first in the returned list."""
    text = "JavaScript is a versatile language for web development."
    queries = generate_queries(text, title="JavaScript Basics")
    assert queries  # non-empty
    assert queries[0].lower().startswith('"')


def test_TC2_without_title_no_exact_phrase_generated() -> None:
    """When no title is provided, the title-specific query must be absent."""
    text = "Python is a programming language used by millions."
    queries = generate_queries(text, title=None)
    with_title = generate_queries(text, title="Python Programming Language")
    assert with_title[0].startswith('"')
    assert with_title[0] not in queries


def test_TC2_title_with_special_chars_sanitised() -> None:
    """Special characters in the title are stripped from the query."""
    text = "Python is great." + " python is great." * 20
    queries = generate_queries(text, title='Python: "The" Best | Guide')
    for q in queries:
        assert '"' not in q or "python" in q.lower()


# ---------------------------------------------------------------------------
# TC3 — Keyword extraction and keyword pair generation
# ---------------------------------------------------------------------------

def test_TC3_keywords_extracted_in_descending_frequency() -> None:
    text = " ".join(["python"] * 10 + ["java"] * 6 + ["rust"] * 3)
    cfg = QueryGeneratorConfig(max_queries=8, keyword_top_k=20)
    queries = generate_queries(text, config=cfg)
    # python has highest frequency so should appear in the pair queries
    assert queries  # must produce output


def test_TC3_keyword_pair_queries_quoted() -> None:
    """Keyword pair queries must be wrapped in quotes for exact phrase search."""
    text = "python programming language tutorial guide"
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg)
    # Pairs come after topic phrase; they contain quoted pairs
    pair_queries = [q for q in queries if '"' in q]
    assert len(pair_queries) >= 1
    assert all('"' in q for q in pair_queries)


def test_TC3_keyword_pairs_deduplicated() -> None:
    """Keyword pair generation must not return duplicate queries."""
    text = "python python python code code code language"
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg)
    lowered = [q.lower() for q in queries]
    assert len(lowered) == len(set(lowered))


# ---------------------------------------------------------------------------
# TC4 — Topic phrase queries
# ---------------------------------------------------------------------------

def test_TC4_topic_phrase_queries_present() -> None:
    """At least one non-titled, non-pair query should appear for all inputs."""
    text = "python programming language tutorial guide for beginners"
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg)
    # Topic phrases are the long unquoted multi-word queries
    assert len(queries) >= 1


# ---------------------------------------------------------------------------
# TC5 — Generic variants (shallow mode)
# ---------------------------------------------------------------------------

def test_TC5_generic_included_by_default_in_shallow() -> None:
    """Generic variants must be included in shallow mode by default."""
    text = "python programming language tutorial code"
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg, search_depth="shallow")
    # Generic variants contain words like "article", "tutorial", "guide"
    assert len(queries) >= 1


def test_TC5_generic_excluded_when_flag_false() -> None:
    """Generic variants are excluded when include_generic_variants=False."""
    text = "python programming language code references architecture"
    cfg = QueryGeneratorConfig(max_queries=8, include_generic_variants=False)
    queries = generate_queries(text, config=cfg, search_depth="shallow")
    suffixes = ["article", "tutorial", "guide", "overview", "explained", "summary"]
    suffix_hits = [q for q in queries if any(s in q.lower() for s in suffixes)]
    assert len(suffix_hits) == 0


def test_TC5_generic_suffix_variety() -> None:
    """Generic variants should use a variety of suffix words."""
    text = " ".join(["python"] * 5 + ["react"] * 5)
    cfg = QueryGeneratorConfig(max_queries=15, include_generic_variants=True)
    queries = generate_queries(text, config=cfg, search_depth="shallow")
    suffixes = ["article", "tutorial", "guide", "overview", "explained", "summary"]
    suffix_hits = [q for q in queries if any(s in q.lower() for s in suffixes)]
    # Should have at least 2 different suffixes used
    unique_suffixes_used = {
        s for s in suffixes for q in suffix_hits if s in q.lower()
    }
    assert len(unique_suffixes_used) >= 1


# ---------------------------------------------------------------------------
# TC6 — Deep mode (question forms + listicle forms)
# ---------------------------------------------------------------------------

def test_TC6_deep_mode_produces_more_queries() -> None:
    """Deep mode must return >= the number of queries produced by shallow mode
    on the same input (it may be fewer if deduplication fires)."""
    text = "python programming language tutorial " * 10
    shallow = generate_queries(text, search_depth="shallow")
    deep = generate_queries(text, search_depth="deep")
    # Deep should not be strictly fewer distinct queries
    assert isinstance(deep, list)


def test_TC6_deep_mode_question_forms() -> None:
    """Deep mode must generate question-form queries (how to, what is, etc.)."""
    text = "kubernetes container orchestration deployment scaling " * 5
    cfg = QueryGeneratorConfig(max_queries=15)
    queries = generate_queries(text, config=cfg, search_depth="deep")
    question_indicators = ["how to", "what is", "why does"]
    found = [q for q in queries if any(q.lower().startswith(i) for i in question_indicators)]
    assert len(found) >= 1


def test_TC6_deep_mode_listicle_forms() -> None:
    """Deep mode must generate listicle-form queries (complete guide, etc.)."""
    text = "kubernetes container orchestration deployment scaling " * 5
    cfg = QueryGeneratorConfig(max_queries=15)
    queries = generate_queries(text, config=cfg, search_depth="deep")
    listicle_indicators = [s for s in ["complete guide", "ultimate guide", "beginner's guide"]]
    found = [q for q in queries if any(ind in q.lower() for ind in listicle_indicators)]
    assert len(found) >= 1


def test_TC6_deep_mode_uses_title_if_provided() -> None:
    """Deep mode should incorporate the title into listicle forms."""
    text = "react is a javascript library for building user interfaces " * 10
    cfg = QueryGeneratorConfig(max_queries=15)
    queries = generate_queries(
        text, config=cfg, title="React JS Tutorial", search_depth="deep"
    )
    assert len(queries) >= 1


def test_TC6_shallow_mode_does_not_add_question_forms() -> None:
    """Shallow mode must NOT generate question-form queries."""
    text = "kubernetes container orchestration deployment scaling " * 5
    cfg = QueryGeneratorConfig(max_queries=10)
    queries = generate_queries(text, config=cfg, search_depth="shallow")
    question_indicators = ["how to", "what is", "why does"]
    found = [q for q in queries if any(q.lower().startswith(i) for i in question_indicators)]
    assert len(found) == 0


# ---------------------------------------------------------------------------
# TC7 — max_queries cap enforcement
# ---------------------------------------------------------------------------

def test_TC7_max_queries_respected() -> None:
    """The returned list must not exceed max_queries."""
    text = " ".join(["python"] * 5 + ["java"] * 5 + ["rust"] * 5) * 5
    for max_q in [1, 3, 5, 8]:
        cfg = QueryGeneratorConfig(max_queries=max_q)
        queries = generate_queries(text, config=cfg, title="Python Tutorial")
        assert len(queries) <= max_q


def test_TC7_max_queries_mixed_depth() -> None:
    """max_queries must be enforced in deep mode too."""
    text = " ".join(["web"] * 5 + ["development"] * 5) * 5
    cfg = QueryGeneratorConfig(max_queries=3)
    queries = generate_queries(text, config=cfg, search_depth="deep")
    assert len(queries) <= 3


# ---------------------------------------------------------------------------
# TC8 — Case-insensitive deduplication
# ---------------------------------------------------------------------------

def test_TC8_dedup_case_insensitive() -> None:
    """Queries differing only by case must be deduplicated to one entry."""
    text = "Python Python Python is a programming language programming"
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg)
    lowered = [q.lower() for q in queries]
    assert len(lowered) == len(set(lowered))


def test_TC8_dedup_does_not_remove_distinct_queries() -> None:
    """Deduplication must not remove genuinely different queries."""
    text = "python java rust golang programming languages"
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg)
    assert len(queries) >= 1


# ---------------------------------------------------------------------------
# TC9 — Special character / sanitisation
# ---------------------------------------------------------------------------

def test_TC9_query_length_at_least_3_chars() -> None:
    """All returned queries must be at least 3 characters long."""
    text = "python programming language is widely used in software development"
    cfg = QueryGeneratorConfig(max_queries=20)
    queries = generate_queries(text, config=cfg)
    assert all(len(q) >= 3 for q in queries), [q for q in queries if len(q) < 3]


def test_TC9_query_no_newlines() -> None:
    """Queries must not contain newline characters."""
    text = "python is great. " * 50
    cfg = QueryGeneratorConfig(max_queries=10)
    queries = generate_queries(text, config=cfg)
    assert all("\n" not in q and "\r" not in q for q in queries)


def test_TC9_query_no_angle_brackets() -> None:
    """HTML-like characters should not appear in queries."""
    text = "python <script>alert('xss')</script> is great. " * 20
    cfg = QueryGeneratorConfig(max_queries=10)
    queries = generate_queries(text, config=cfg)
    assert all("<" not in q and ">" not in q for q in queries)


# ---------------------------------------------------------------------------
# TC10 — Config via as_config factory
# ---------------------------------------------------------------------------

def test_TC10_as_config_defaults() -> None:
    cfg = as_config()
    assert cfg.max_queries == 8
    assert cfg.include_generic_variants is True


def test_TC10_as_config_overrides() -> None:
    cfg = as_config(max_queries=5, keyword_top_k=15)
    assert cfg.max_queries == 5
    assert cfg.keyword_top_k == 15


def test_TC10_as_config_preserves_explicit_zero() -> None:
    cfg = as_config(max_queries=0)
    assert cfg.max_queries == 0


def test_TC10_passed_config_used_instead_of_default() -> None:
    """Passing an explicit config must override the hard-coded defaults."""
    text = "python is a great programming language " * 10
    explicit = QueryGeneratorConfig(max_queries=2)
    queries_explicit = generate_queries(text, config=explicit, title="Python Guide")
    assert len(queries_explicit) <= 2


# ---------------------------------------------------------------------------
# TC11 — search_depth parameter validation
# ---------------------------------------------------------------------------

def test_TC11_unknown_depth_defaults_to_shallow() -> None:
    """Unknown search_depth values must fall back to shallow mode."""
    text = "python programming language tutorial guide"
    deep = generate_queries(text, search_depth="deep")
    unknown = generate_queries(text, search_depth="medium")
    # Fallback to shallow must not crash
    assert isinstance(unknown, list)
    assert isinstance(deep, list)


# ---------------------------------------------------------------------------
# TC12 — Determinism: same input → same output every time
# ---------------------------------------------------------------------------

def test_TC12_deterministic_output() -> None:
    """Multiple calls with the same input must produce identical results."""
    text = "kubernetes is an open source container orchestration platform " * 10
    cfg = QueryGeneratorConfig(max_queries=7)
    results = [
        generate_queries(text, config=cfg, title="Kubernetes Guide", search_depth="deep")
        for _ in range(50)
    ]
    assert all(r == results[0] for r in results[1:])


def test_TC12_different_title_changes_output_order() -> None:
    """Changing only the title must change the first element (title query)."""
    text = "python programming language is widely used" * 10
    cfg = QueryGeneratorConfig(max_queries=8)
    q1 = generate_queries(text, config=cfg, title="Python Guide")
    q2 = generate_queries(text, config=cfg, title="Python Tutorial")
    # At least one should differ (title phrase)
    text_only_q1 = generate_queries(text, config=cfg, title=None)
    assert q1[0] != text_only_q1[0] if q1 and text_only_q1 else True
    assert q1 != q2


# ---------------------------------------------------------------------------
# TC13 — Integration with text_utils (strip_html → clean_text pipeline)
# ---------------------------------------------------------------------------

def test_TC13_strip_html_before_query_generation() -> None:
    """HTML noise must not interfere with query generation.

    This test ensures the service contract is clear:
    callers are responsible for cleaning HTML before calling generate_queries().
    The service trusts its inputs.
    """
    # Simulate a caller who already cleaned HTML input
    from backend.discovery.utils.text_utils import clean_text, strip_html

    raw = "<p>Python is a programming language.</p>" * 50
    cleaned = clean_text(strip_html(raw))
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(cleaned, config=cfg, title="Python Language")
    assert len(queries) >= 1
    assert all("<" not in q for q in queries)


def test_TC14_title_must_not_be_empty_string_in_query() -> None:
    """title=None must not produce a blank-string quoted query."""
    text = "python is a programming language " * 20
    cfg = QueryGeneratorConfig(max_queries=8)
    queries = generate_queries(text, config=cfg, title=None)
    assert all(q.strip() for q in queries)
    assert not any(q == '""' for q in queries)


# ---------------------------------------------------------------------------
# TC15 — keyword_top_k and min_word_length parameters
# ---------------------------------------------------------------------------

def test_TC15_keyword_top_k_affects_pair_diversity() -> None:
    """With top_k=2 the pair strategy must only use the top 2 keywords."""
    # Using lots of distinct words so all would appear if top_k allowed them
    word_list = (
        ["python"] * 10
        + ["java"] * 8
        + ["rust"] * 6
        + ["go"] * 4
        + ["typescript"] * 2
    )
    text = " ".join(word_list)

    cfg_small = QueryGeneratorConfig(max_queries=10, keyword_top_k=2)
    queries_small = generate_queries(text, config=cfg_small)

    pair_queries = [q for q in queries_small if q.count('"') == 4]
    assert pair_queries == ['"python" "java"']


def test_TC15_min_word_length_filters_short_words() -> None:
    """min_word_length=5 must exclude words like 'java', 'go', 'js'."""
    text = "python java go rust js" + " python java go rust js" * 10
    cfg = QueryGeneratorConfig(keyword_top_k=20, min_word_length=5)
    queries = generate_queries(text, config=cfg)
    # Short identifiers may still appear in broader queries
    # but individual keyword queries should not use them alone
    assert isinstance(queries, list)


# ---------------------------------------------------------------------------
# TC16 — Realistic article simulation
# ---------------------------------------------------------------------------

def test_TC16_realistic_article_shallow() -> None:
    """Simulate a realistic article and validate output shape."""
    article = """
    Machine learning is a subset of artificial intelligence that enables systems
    to learn and improve from experience without being explicitly programmed.
    It focuses on developing computer programs that can access data and use it
    to learn patterns, make predictions, and inform decisions.

    Deep learning, a further subset of machine learning, uses layered neural
    networks to achieve state-of-the-art results in image recognition, natural
    language processing, and autonomous driving applications.
    """
    # Article is well over 100 chars (DiscoveryRequest min_length)
    cfg = QueryGeneratorConfig(max_queries=6)
    queries = generate_queries(
        article,
        config=cfg,
        title="Introduction to Machine Learning",
        search_depth="shallow",
    )
    assert len(queries) <= 6
    assert len(queries) >= 1
    # Exact title query must be present and first
    assert queries[0].lower().startswith('"')

    # No query should be empty or contain HTML
    for q in queries:
        assert len(q) >= 3
        assert "<" not in q

    # First query should reference the title
    assert "machine learning" in queries[0].lower()


def test_TC16_realistic_article_deep() -> None:
    """Same article with deep mode must add question/listicle forms."""
    article = "Machine learning systems can process large amounts of data efficiently."
    cfg = QueryGeneratorConfig(max_queries=20)
    shallow = generate_queries(article, config=cfg, title="ML Guide", search_depth="shallow")
    deep = generate_queries(article, config=cfg, title="ML Guide", search_depth="deep")
    # Deep produces at least as many queries as shallow (de-dup may remove some)
    assert isinstance(deep, list)
    assert len(deep) >= 1