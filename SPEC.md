# QueryGenerator — Implementation Specification

## Module

`backend/discovery/query_generator.py`

## Package

`backend.discovery`

## Context

The Discovery Service receives an original article (HTML or plain text) and must produce a set of search queries that maximize the chance of finding copied or substantially similar versions of that article published elsewhere on the web.

The generator is responsible for extracting distinctive content from the article and formulating it into `SearchQuery` objects suitable for any `SearchProvider` in the system.

---

## Goals & Constraints

- All functions are **pure** (no I/O, no network calls, no side effects).
- Fully typed — `pyright --strict` compatible.
- Input article is raw HTML or plain text; the generator handles cleanup internally.
- Output is `list[SearchQuery]`, ordered by predicted discovery value descending.
- **No external APIs** — only the text utility functions defined in the same module.
- Reproducible: identical input always produces identical output.

---

## Available Text Utilities

These are already implemented and must be used for content extraction:

| Function | Signature | Purpose |
|----------|-----------|---------|
| `normalize` | `(text: str) -> str` | Unicode NFKC + whitespace collapse |
| `strip_html` | `(raw_html: str) -> str` | Remove markup, decode entities |
| `extract_candidate_phrases` | `(text: str, *, n: int = 3, min_word_length: int = 2, min_phrase_count: int = 1) -> list[str]` | Multi-word phrase n-grams |
| `extract_keywords` | `(text: str, *, top_k: int = 30, min_word_length: int = 3) -> list[tuple[str, float]]` | Frequency-ranked keywords with scores |
| `extract_keywords_flat` | `(keywords: list[tuple[str, float]]) -> list[str]` | Keywords without scores |

---

## Public Interfaces

---

### `class QueryGenerationConfig`

Immutable configuration for the generator. All values come from `settings.discovery` or reasonable defaults.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class QueryGenerationConfig:
    max_queries: int                      # Max SearchQuery objects to return  (default: 8)
    phrase_query_count: int               # Target exact-phrase queries         (default: 5)
    keyword_query_count: int              # Target keyword-combination queries  (default: 3)
    phrase_lengths: tuple[int, int, int]  # (min, default, max) n for phrases  (default: (2, 3, 4))
    min_word_length: int                  # Min word chars in extracted tokens (default: 3)
    min_phrase_freq: int                  # Min raw occurrence count per phrase (default: 1)
    include_exact_title: bool             # Add full title as exact-match query  (default: True)
    include_short_phrases: bool           # Allow n=2 phrase queries             (default: True)
    keyword_top_k: int                   # Keywords to extract for KW queries   (default: 20)
```

**Validation:** Raises `ValueError` if `max_queries < 1`, `phrase_lengths` values are not `1 ≤ min ≤ default ≤ max ≤ 10`, or `min_word_length < 1`.

**Construction:**

```python
# Default — reads from settings.discovery
config = QueryGenerationConfig.from_settings()

# Override one or more fields
config = QueryGenerationConfig(max_queries=12, phrase_query_count=7, keyword_query_count=5)
```

---

### `class QueryGenerator`

The main public class. Receives an article and produces ranked search queries.

```python
from dataclasses import dataclass

class QueryGenerator:
    __slots__ = ("_cfg",)

    def __init__(self, config: QueryGenerationConfig | None = None) -> None:
        """Create a generator. Pass a custom config or use the default."""
        ...

    def generate(
        self,
        article_text: str,
        *,
        title: str | None = None,
        language: SearchLanguage | None = None,
        strip_html_first: bool = True,
    ) -> list[SearchQuery]:
        """Generate ranked search queries from an article.

        Parameters
        ----------
        article_text:
            Raw article content (HTML or plain text).Cleaned internally.
        title:
            Optional article title. Used for exact-match title queries if set.
        language:
            Optional ISO 639-1 language code for the SearchQuery objects.
            Inferred from article structure if not provided.
        strip_html_first:
            If True (default), run strip_html() before extraction.
            Set False if article_text is already plain text.

        Returns
        -------
        list[SearchQuery]
            Ordered by predicted discovery value descending.
            Never empty — keyword fallback always produces at least one query.
        """
        ...
```

**Guarantees:**
- Result is never empty; if extraction fails it falls back to a keyword-only query from the raw input.
- All queries have valid `query` strings 1–500 characters.
- `max_queries` is never exceeded.
- Exact-duplicate queries (identical `query` string) are never returned.

---

### `class ScoredQuery`

Internal intermediate type used during ranking. Not public API.

```python
@dataclass
class ScoredQuery:
    query_text: str
    score: float          # Higher = more distinctive for discovery
    is_exact_phrase: bool
    is_title_query: bool
    is_keyword_query: bool
    source_phrase: str | None   # If generated from a specific phrase
```

---

## Data Flow

```
article_text (raw HTML or plain)
        │
        ▼
    strip_html()          (if strip_html_first=True)
        │
        ▼
    normalize()            Unicode + whitespace cleanup
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  EXTRACTION PHASE                       │
  ├─────────────────────────────────────────┤
  │  extract_candidate_phrases(text, n=2)   │──► List[str]  n=2 phrases
  │  extract_candidate_phrases(text, n=3)   │──► List[str]  n=3 phrases
  │  extract_candidate_phrases(text, n=4)   │──► List[str]  n=4 phrases
  │  extract_keywords(text, top_k=20)       │──► List[tuple[str, float]]
  │  optional: extract_keywords_flat()        │──► List[str]  top keywords
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  CANDIDATE QUERY BUILDING               │
  ├─────────────────────────────────────────┤
  │  Phrase candidates                      │
  │    → wrapped in quotes:   "python tutorial guide"
  │    → min_phrase_freq filter applied    │
  │  Keyword candidates                     │
  │    → top-k keywords joined: "python tutorial java"
  │    → word count capped at 5 tokens      │
  │  Title candidate (if title provided)    │
  │    → normalized title as exact: "Full Article Title"
  │    → title noun/keyword subset for KW: title words top-k
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  SCORING & RANKING PHASE                │
  ├─────────────────────────────────────────┤
  │  score = phrase_length_weight            │
  │        × frequency_weight               │
  │        × distinctiveness_penalty        │
  │  where:                                 │
  │    phrase_length_weight = len(words) / 5 capped at [1.0, 2.0]
  │    frequency_weight     = min(raw_count / 3, 1.5)      │
  │    distinctiveness_penalty = 1.0 if not_overly_common │
  │  Title query receives +0.5 bonus.        │
  │  Keyword-only queries receive -0.3 penalty. │
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  DEDUPLICATION                          │
  ├─────────────────────────────────────────┤
  │  Tokenize each candidate query           │
  │  For each new candidate:                │
  │    If JS divergence < 0.3 to existing →  │
  │       skip (prefer higher-scored one)   │
  │  Otherwise keep.                        │
  │  Also skip exact string duplicates.       │
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  SELECTION & OUTPUT                      │
  ├─────────────────────────────────────────┤
  │  Sort by score descending.              │
  │  Take top max_queries items.            │
  │  Ensure minimum 1 kw query if possible.  │
  │  Wrap each in SearchQuery().             │
  │  Return list[SearchQuery].               │
  └─────────────────────────────────────────┘
```

---

## Query Generation Strategy

### Phrase queries (exact-match)

The most important query type for plagiarism discovery. Longer phrases are more distinctive and return fewer false positives.

1. Extract n-grams at `n ∈ {2, 3, 4}` simultaneously (in a single pass over tokens for efficiency).
2. Run `min_phrase_freq` filter: only keep phrases occurring at least `n` times in the source text.
3. Wrap each surviving phrase in double quotes to form a phrase query: `"python programming tutorial"`.
4. Score by length + frequency (see Scoring below).

**Why n=2,3,4?**
- `n=1` (single words) → too generic, excluded.
- `n=2` (bigrams) → catch partial copies and rewrites.
- `n=3` (trigrams) → strong indicator of verbatim copy.
- `n=4+` → very distinctive but rare in short articles; include but deprioritize if frequency is low.

**Phrase query distribution:** Aim for roughly 60% of `max_queries` as phrase queries, capped at `phrase_query_count`.

### Keyword combination queries

For broad recall when phrase matches are too specific or unavailable.

1. Extract top-k keywords via `extract_keywords`.
2. Group top keywords in sets of 3–5 tokens: `"python tutorial guide"`.
3. These queries are *not* quoted — they are general search queries.
4. Receive a score penalty vs phrase queries.

**Why not just keywords?**
- Keyword-only queries return too many results, making it hard to identify copied content.
- Phrase queries narrow results dramatically (exact-match semantics).
- A mix of both maximizes recall × precision.

### Title query (if title provided)

The article title is the most authoritative phrase in the document. It receives the highest score.

1. `normalize(title)` → if non-empty, add as exact-match phrase query `"normalized title"`.
2. Also extract keywords from the title alone (ignore stopwords) and use in keyword combinations.

---

## Ranking Strategy

### Scoring formula

For a candidate query `q`:

```
base_score = len(words_in_q) / 5.0          # longer = better (normalized)

freq_score = min(phrase_raw_count(q) / 3.0, 1.5)  # more occurrences = more confident

bonus = +0.5  if is_title_query
bonus = -0.3  if is_keyword_query (not phrase)

raw_score = (base_score * freq_score) + bonus
```

`raw_score` is clamped to `[0.0, 3.0]` and used for sorting.

**Why this formula?**
- Longer phrases are exponentially more distinctive. A 5-word phrase is much harder to match accidentally than a 2-word phrase.
- Frequency matters: a phrase appearing 5 times in an article is more likely to be a key concept than a phrase appearing once.
- Title bonus: the article title is authored by the original creator — it's the strongest signal.
- Keyword penalty: unquoted keyword queries have lower precision, so they're ranked below phrase queries.

### Dedup strategy

Use **Jaccard similarity on token sets** to detect near-duplicate queries.

```
jaccard(tokens_a, tokens_b) = |set_a ∩ set_b| / |set_a ∪ set_b|
```

- If `jaccard(tokens_new, tokens_any_existing) > 0.7` → skip `new` (keep the one with higher score).
- After filtering, if fewer than `phrase_query_count` phrase queries remain, backfill from shorter-n candidates.

---

## QueryConstruction Helpers

### `def _build_exact_phrase_queries(phrases: list[str]) -> list[ScoredQuery]`

Wrap each phrase in double quotes. Assign `is_exact_phrase=True`, `is_title_query=False`.

### `def _build_title_query(title: str) -> ScoredQuery | None`

If `normalize(title)` is non-empty and `len(words) >= 2`, return a `ScoredQuery` with `is_title_query=True` and `+0.5` bonus.

### `def _build_keyword_queries(keywords: list[str], top_k: int = 20) -> list[ScoredQuery]`

Partition `keywords[:top_k]` into groups of 3–5 consecutive keywords (preserve order). Join with single space (no quotes). Set `is_keyword_query=True` and apply the keyword penalty.

### `def _score_candidates(candidates: list[ScoredQuery]) -> list[ScoredQuery]`

Apply the scoring formula to all candidates. Sort descending by `raw_score`.

### `def _deduplicate(candidates: list[ScoredQuery], threshold: float = 0.7) -> list[ScoredQuery]`

Tokenize each candidate's query string. For each new candidate, if Jaccard similarity with any higher-scored existing candidate exceeds `threshold`, skip it. Otherwise keep.

### `def _build_search_query(scored: ScoredQuery, *, language: SearchLanguage | None, max_results: int = 10) -> SearchQuery`

Wrap `scored.query_text` in a `SearchQuery`. Set `max_results=max_results`, `language=language`, `result_type=ResultType.WEB`, `safe_search=SafeSearchLevel.MODERATE`.

---

## Configuration Requirements

The `QueryGenerationConfig` is derived from `settings.discovery` with the following defaults:

| Config field | Source | Default | Fallback if missing |
|---|---|---|---|
| `max_queries` | `DISCOVERY_MAX_QUERIES_PER_DISCOVERY` | `8` | `8` |
| `phrase_query_count` | — | `5` | `max_queries * 0.6` |
| `keyword_query_count` | — | `3` | `max_queries * 0.4` |
| `phrase_lengths` | — | `(2, 3, 4)` | — |

**If `settings.discovery` is inaccessible at runtime**, fall back to hardcoded defaults.

**Environment variables** (processed via `settings.discovery`):

| Variable | Type | Default | Effect |
|---|---|---|---|
| `DISCOVERY_MAX_QUERIES_PER_DISCOVERY` | `int 1–20` | `8` | Hard cap on returned `SearchQuery` count |
| `DISCOVERY_DEFAULT_MAX_CANDIDATES` | `int 1–50` | `20` | Reserved for future discovery orchestration |
| `DISCOVERY_DEFAULT_SEARCH_DEPTH` | `str` | `"shallow"` | Ignored by QueryGenerator |

---

## Edge Cases

| Case | Handling |
|------|----------|
| Empty article text | Return a single `SearchQuery` with the raw text as the query (if non-empty) or `"copy"` as fallback keyword query |
| All-stopwords text | Fall back to keyword extraction without stopword filter (bypass stopword list for this input only) |
| Very short article (<10 words) | Skip `n=4` extraction; generate queries from whatever keywords remain; return up to 3 queries |
| `title` is empty string | Skip title query; treat article as untitled |
| Title equals article text | Deduplicate; avoid returning the same query twice |
| `extract_keywords` returns empty | Generate a "copy" or "blog" keyword fallback query; never return empty list |
| Single candidate phrase only | Return it as an exact-phrase query (if `max_queries >= 1`) |
| `max_queries = 1` | Return only the top-ranked query (likely the title or longest phrase) |
| Phrase appears only once | Exclude if `min_phrase_freq > 1`; include if `min_phrase_freq == 1` |
| Very long title (>50 words) | Truncate to 50 words, then normalize and use |

---

## Acceptance Criteria

### Functional

- [ ] `QueryGenerator.generate(article_text)` returns `list[SearchQuery]`
- [ ] Result is ordered by descending discovery value
- [ ] Result length never exceeds `config.max_queries`
- [ ] Result is never empty (keyword fallback always yields at least one query)
- [ ] All stopword-only text returns keyword-fallback query (never empty)
- [ ] Exact-match phrase queries are wrapped in double quotes in the `query` string
- [ ] `title` is included as an exact-match phrase query when provided
- [ ] `language`, `result_type`, `safe_search` fields are populated in every returned `SearchQuery`
- [ ] Identical `query` strings are never duplicated in the result list
- [ ] Near-duplicate queries (Jaccard > 0.7) are deduplicated

### Scoring

- [ ] Title query is always ranked first if it exists
- [ ] Longer phrase queries are ranked above shorter ones (all else equal)
- [ ] Keyword-only queries are always ranked below phrase queries
- [ ] Phrases occurring once are still included (with low score) when `min_phrase_freq=1`

### Configuration

- [ ] `QueryGenerationConfig.from_settings()` reads from `settings.discovery`
- [ ] Constructor accepts `QueryGenerationConfig` override
- [ ] All config field values are validated on construction (raise `ValueError` on invalid)

### Purity & deterministic output

- [ ] `generate()` is pure — calling it twice with the same arguments returns identical `list[SearchQuery]`
- [ ] No I/O, file access, or network calls inside `generate()`
- [ ] Module-level constants are immutable (`Final`)

### Type safety

- [ ] `QueryGenerator` and all public functions are fully type-annotated
- [ ] Module passes `pyright --strict` with no errors
- [ ] No `Any` return types

### Edge cases

- [ ] Empty `article_text = ""` → returns at least 1 `SearchQuery`
- [ ] `n=0` or `n>10` inside `extract_candidate_phrases` raises `ValueError` (upstream contract)
- [ ] Very long article (>50k words) — extraction phase is bounded by `top_k` and `max_phrases` to avoid OOM
- [ ] HTML input (`"<p>Hello</p>"`) — output is identical to plain-text input after `strip_html_first`

---

## Module Layout

```
backend/discovery/
    query_generator.py    # QueryGenerator, QueryGenerationConfig, ScoredQuery, all helpers
    utils/
        __init__.py       # Exports text utilities
        text_utils.py    # (existing — do not modify)
    schemas/
        __init__.py
        search_query.py  # SearchQuery, SearchLanguage, ResultType, SafeSearchLevel
```

**Exports from `query_generator.py`:**

```python
__all__ = [
    "QueryGenerationConfig",
    "QueryGenerator",
]
```

---

## Design Rationale

### Why quoted phrase queries?

Search engines treat quoted strings as exact-match operators. Searching `"python programming tutorial"` returns pages containing that exact sequence of words — ideal for finding copied content. Unquoted queries (e.g. `python programming tutorial`) match pages containing those words anywhere, producing millions of noisy results.

### Why multi-length n-grams?

Short articles might not contain any 4-word distinctive phrases. Including `n=2` ensures we still generate usable queries from shorter content. Including `n=4` captures highly distinctive long-form content (legal text, technical documentation, quotes).

### Why the keyword penalty?

Keyword-only queries are valuable for recall but have very low precision in a plagiarism context. A page matching "python tutorial" could be about any python tutorial — not necessarily a copy of the target article. We rank them lower but still include them because in some cases they are the only viable queries.

### Why Jaccard deduplication and not Levenshtein?

Jaccard similarity on token sets is O(n×m) where n = number of queries, m = average tokens per query. For a maximum of 8–20 queries, this is negligible. Levenshtein is character-level and doesn't capture semantic overlap between queries like `"python tutorial guide"` and `"python tutorial java"` efficiently for this use case.

### Why fallback to "copy" keyword?

The safest minimal query for an empty article is `"copy"` — it is:
- Short, valid search syntax for all providers
- Broad enough to return results on any provider
- Clearly not generating results about a specific (unknown) topic

If the article has any content at all beyond stopwords, `extract_keywords` will produce a better query than this fallback.

---

# Content Extraction — Implementation Specification

## Module

`backend/content/extractor.py`

## Package

`backend.content`

## Context

The Discovery Service collects candidate article URLs from search providers. Before comparison with the original article, those candidate pages must be downloaded and their readable content extracted.

The Content Extraction layer receives a URL and returns structured, normalized article text — ready for comparison against the original.

**Who calls this:** The discovery pipeline (orchestration layer) after URL collection via search providers.

---

## Technology

`trafilatura` is used as the extraction backend.

Rationale for trafilatura:
- Purpose-built for extracting **boilerplate-free article text** from any web page
- Handles JavaScript-rendered pages via fallback heuristics when no `<article>` body is found
- Returns title, text, excerpt, author, and publish date in one call
- Built-in HTTPS download with configurable timeout
- Pure Python, no Selenimum/Playwright required — suitable for hackathon MVP
- Active maintenance, comprehensive test corpus

---

## Data Models

---

### `class ExtractedArticle`

The canonical output of the extractor. Represents a single candidate article with its extracted content.

```python
class ExtractedArticle(BaseModel):
    """Structured content from a scraped webpage."""

    url: str = Field(..., description="Canonical URL the content was fetched from.")
    title: str | None = Field(default=None, description="Article title extracted by trafilatura.")
    text: str = Field(..., description="Boilerplate-free article text. Empty if extraction failed.")
    text_length: int = Field(..., ge=0, description="Word count of the extracted text.")
    excerpt: str | None = Field(
        default=None,
        description="First 200 characters of text, or a standalone description field from the page.",
    )
    author: str | None = Field(default=None, description="Author name if detected, otherwise None.")
    publish_date: str | None = Field(
        default=None,
        description="ISO 8601 date string (YYYY-MM-DD) if detected, otherwise None.",
    )
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code detected by trafilatura, e.g. 'en'.",
    )
    extraction_mode: Literal["article", "text", "comments", "json"] = Field(
        default="article",
        description="Which trafilatura extraction mode was used.",
    )
    raw_html: str | None = Field(
        default=None,
        description="Raw HTML response body. Set to None after extraction to avoid retaining large strings.",
    )
```

**Validation:**
- `text_length` is always `len(text.split())` — a derived field, recomputed on set.
- `url` must be a valid HTTP/HTTPS URL.
- Empty `text` (`""`) is valid — it means extraction wholly failed and the caller must handle the null state.

---

### `class ExtractionResult`

A wrapper that captures both the successfully extracted article and the failure state.

```python
from typing import Annotated, Literal

class ExtractionResult(BaseModel):
    """A single URL extraction attempt, either succeeded or failed."""

    url: str = Field(..., description="URL that was attempted.")
    article: ExtractedArticle | None = Field(
        default=None,
        description="Populated if extraction succeeded. None if all attempts failed.",
    )
    status: Literal["success", "failed", "no_text"] = Field(
        ...,
        description=(
            "'success' — article extracted with non-empty text. "
            "'no_text' — extraction succeeded but text is empty (probably a non-article page). "
            "'failed' — network error or unexpected exception after all retries."
        ),
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error description if status is 'failed'. None otherwise.",
    )
    attempts: int = Field(..., ge=1, description="Number of download attempts made.")
    elapsed_ms: int = Field(..., ge=0, description="Wall-clock time spent in milliseconds.")
   ProviderName: str = Field(
        default="trafilatura",
        description="Identifier of the extraction backend used.",
    )
```

---

### `class ContentExtractorConfig`

Configuration derived from `settings.content_extraction`. Immutable after construction.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ContentExtractorConfig:
    timeout_seconds: float          # HTTP request timeout  (default: 15.0)
    max_retries: int               # Retry count on failure  (default: 3)
    retry_backoff_base_seconds: float  # Exponential backoff base (default: 1.0)
    user_agent: str                # HTTP User-Agent header  (default: "CopyGuard/1.0 ...")
    include_raw_html: bool         # Whether to retain raw HTML in result (default: False)
    extraction_mode: Literal["article", "text"]  # trafilatura mode (default: "article")
    min_text_length: int          # Minimum acceptable word count to count as "success" (default: 50)
```

**Construction:**

```python
# Default — reads from settings.content_extraction
config = ContentExtractorConfig.from_settings()

# Explicit override
config = ContentExtractorConfig(timeout_seconds=30.0, max_retries=5)
```

---

## Public Interfaces

---

### `class ContentExtractor`

The main public class.

```python
class ContentExtractor:
    __slots__ = ("_cfg",)

    def __init__(self, config: ContentExtractorConfig | None = None) -> None:
        """Create an extractor. Pass a custom config or use the default."""
        ...

    def extract(self, url: str) -> ExtractionResult:
        """Extract article content from a URL.

        Synchronous. Thread-safe — separate instances have independent state.

        Parameters
        ----------
        url:
            Full HTTP or HTTPS URL to extract. Must be 1–2000 characters.

        Returns
        -------
        ExtractionResult
            Always returns a result (never raises).
            Check ``result.status`` before accessing ``result.article``.

        Raises
        ------
        ValueError
            If ``url`` is not a valid HTTP/HTTPS URL.
        """
        ...

    async def extract_async(self, url: str) -> ExtractionResult:
        """Async variant — runs extract() in a background thread to avoid blocking.

        Same contract as ``extract()`` but non-blocking.
        """
        ...
```

---

### `async def extract_url(url: str, config: ContentExtractorConfig | None = None) -> ExtractionResult`

Module-level convenience function. Creates a default extractor and calls `extract_async`.

```python
async def extract_url(
    url: str,
    config: ContentExtractorConfig | None = None,
) -> ExtractionResult:
    ...
```

---

## Error Handling Strategy

### Failure modes

| Failure mode | Symptom | Handling |
|---|---|---|
| DNS resolution failure | `socket.gaierror` | Treat as `failed`, return `ExtractionResult` with status=`failed` |
| Connection timeout | `httpx.TimeoutException` | Retry (up to `max_retries`); if all fail → `failed` |
| HTTP 4xx client error | `httpx.HTTPStatusError` | Do **not** retry; return `failed` immediately |
| HTTP 429 rate-limit | `httpx.HTTPStatusError` 429 | Retry after `Retry-After` header if present, else exponential backoff |
| HTTP 5xx server error | `httpx.HTTPStatusError` 5xx | Retry with backoff; if all fail → `failed` |
| Invalid URL | `httpx.InvalidURL` | Return `failed` immediately without retry |
| SSL error | `httpx.SSLError` | Treat as `failed`; do not retry SSL failures |
| No article body found | trafilatura returns `None` text | Return `ExtractionResult` with status=`no_text`, article has `text=""` |
| Robots.txt blocked | detection via `robots_txt_blocked()` check | Return `failed` with descriptive `error_message` |

### Retry with exponential backoff

```
delay = retry_backoff_base_seconds × 2^(attempt_index - 1) + jitter(0, 0.5)
```

- Attempt 1: immediate
- Attempt 2: base × 2 + jitter
- Attempt 3: base × 4 + jitter
- Capped at `timeout_seconds` per attempt

### Robots.txt handling

- Before every extraction, check `robots.txt` via `urllib.robotparser.RobotFileParser`.
- If blocked: return `ExtractionResult` with `status="failed"` and `error_message="Blocked by robots.txt"`.
- Do **not** raise an exception — robots.txt exclusion is a handled, expected case.

---

## Extraction Pipeline

```
url (string)
        │
        ▼
URL validation  ──── invalid ──► ExtractionResult(status=failed)
        │ valid
        ▼
robots.txt check ──── blocked ──► ExtractionResult(status=failed)
        │ allowed
        ▼
trafilatura.fetch_url(url, timeout=cfg.timeout_seconds)
        │
        ├─── returns HTML body
        ▼
trafilatura.extract(
    downloaded_html,
    url=url,
    output_format="json",
    extraction_mode=cfg.extraction_mode,
    settings={...},
)
        │
        ├─── result is None / text empty ──► ExtractionResult(status=no_text)
        ├─── result with text ──► ExtractionResult(status=success)
        └─── raises exception ──► retry loop
                │
                ├─── retries exhausted ──► ExtractionResult(status=failed)
                └─── max_retries == 0 ──► immediate fail
```

**Post-extraction normalization:**
1. Strip leading/trailing whitespace from `title` and `text`.
2. Set `text_length = len(text.split())`.
3. Optionally discard `raw_html` after extraction (`include_raw_html=False`) to free memory.
4. Normalize `publish_date` to ISO 8601 `YYYY-MM-DD` if trafilatura returns a datetime.

---

## Configuration Requirements

Configuration is read from `settings.content_extraction` (already defined in `backend/core/config.py`):

| Field | Env var | Type | Default |
|---|---|---|---|
| `request_timeout_seconds` | `CONTENT_REQUEST_TIMEOUT_SECONDS` | `float 1–60` | `15.0` |
| `max_concurrent_extractions` | `CONTENT_MAX_CONCURRENT_EXTRACTIONS` | `int 1–50` | `10` |
| `retry_attempts` | `CONTENT_RETRY_ATTEMPTS` | `int 0–5` | `3` |
| `retry_backoff_base_seconds` | `CONTENT_RETRY_BACKOFF_BASE_SECONDS` | `float 0.5–10` | `1.0` |
| `user_agent` | `CONTENT_USER_AGENT` | `str` | `"CopyGuard/1.0 (+https://github.com/lextrace)"` |

**Additional fields not in `settings` (derived defaults):**

| Field | Default |
|---|---|
| `include_raw_html` | `False` (set to `True` for debugging) |
| `extraction_mode` | `"article"` (`"text"` for raw body without heuristics) |
| `min_text_length` | `50` (words; below this → status=`no_text` rather than `success`) |

---

## Edge Cases

| Case | Handling |
|------|----------|
| URL is `None` or empty | Raise `ValueError` immediately |
| URL too long (>2000 chars) | Raise `ValueError` |
| URL scheme not http/https | Raise `ValueError` |
| trafilatura returns `None` for title | Set `title=None` |
| trafilatura returns publish date as datetime | Convert to ISO8601 `YYYY-MM-DD` string |
| trafilatura returns author list | Join with comma `", "`, store as single string |
| trafilatura detects language as `None` | Set `language=None` |
| Single retry attempt (`max_retries=0`) | No retry loop; return single attempt result only |
| Server returns 429 with no `Retry-After` | Apply backoff based on `retry_backoff_base_seconds` |
| `raw_html` very large (>10 MB) | Truncate to 10 MB before storing; log a warning |
| Non-article page (login wall, search results) | trafilatura finds no body → `status=no_text` |
| Unicode homepage with little text | trafilatura extracts what it can; `text_length` reflects reality |

---

## Module Layout

```
backend/content/
    __init__.py                            # Exports ContentExtractor, extract_url
    extractor.py                            # ContentExtractor, ContentExtractorConfig, ExtractedArticle, ExtractionResult

backend/core/
    config.py                              # ContentExtractionSettings (already exists)

backend/discovery/
    schemas/
        responses.py                       # CandidateArticle (already exists — maps to ExtractionResult)
```

**Exports from `backend/content/__init__.py`:**

```python
__all__ = [
    "ContentExtractor",
    "ContentExtractorConfig",
    "ExtractedArticle",
    "ExtractionResult",
    "extract_url",           # async convenience function
]
```

---

## Relationship to Existing Schema

`ExtractedArticle` is the raw extracted content. It feeds into the discovery pipeline which transforms it into `CandidateArticle` (defined in `backend/discovery/schemas/responses.py`).

The orchestration layer that receives candidate URLs from search providers will:

```
URL list
  │
  ▼
ContentExtractor.extract_async(url)  for each URL   (concurrent, bounded by max_concurrent_extractions)
  │
  ▼
ExtractionResult → CandidateArticle   (transform + rank)
  │
  ▼
DiscoveryResponse (final API response)
```

---

## Acceptance Criteria

### Functional

- [ ] `ContentExtractor.extract(url)` returns an `ExtractionResult`
- [ ] `ExtractionResult.status` is always one of `"success"`, `"no_text"`, `"failed"`
- [ ] `status="success"` means `article.text` is non-empty and `len(article.text.split()) >= min_text_length`
- [ ] `status="failed"` means all retry attempts were exhausted or URL was invalid/blocked
- [ ] `status="no_text"` means trafilatura ran but found no article body
- [ ] Raw `ValueError` from invalid URL is never propagated — always wrapped in `ExtractionResult`
- [ ] Network timeouts trigger retry up to `max_retries` with exponential backoff
- [ ] HTTP 4xx errors are not retried — immediately return `status=failed`
- [ ] HTTP 5xx errors are retried with backoff
- [ ] robots.txt exclusion returns `status=failed` with descriptive error

### Data completeness

- [ ] `ExtractedArticle.text` contains only the article body — no navigation, no ads, no boilerplate
- [ ] `ExtractedArticle.text` is Unicode-normalized (NFKC) and whitespace-collapsed
- [ ] `ExtractedArticle.title` is stripped of HTML and normalized whitespace
- [ ] `publish_date` is ISO 8601 `YYYY-MM-DD` string, or `None` if undetectable
- [ ] `author` is a plain string with no HTML, or `None`
- [ ] `text_length` matches `len(article.text.split())`
- [ ] `language` is a valid ISO 639-1 two-letter code or `None`

### Configuration

- [ ] `ContentExtractorConfig.from_settings()` reads from `settings.content_extraction`
- [ ] Constructor accepts `ContentExtractorConfig` override
- [ ] All config values are validated on construction

### Performance

- [ ] `max_concurrent_extractions` is respected by the caller (orchestration layer)
- [ ] `raw_html` is dropped (`= None`) after extraction unless `include_raw_html=True`
- [ ] Total memory per extraction is bounded by response size (no unbounded growth)

### Type safety

- [ ] All public functions and classes are fully type-annotated
- [ ] Module passes `pyright --strict` with no errors
- [ ] No `Any` return types

### Async

- [ ] `ContentExtractor.extract_async()` runs without blocking the event loop
- [ ] Multiple concurrent `extract_async()` calls are safe (thread pool under the hood)