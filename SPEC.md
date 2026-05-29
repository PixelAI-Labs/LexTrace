# Text Utilities — Implementation Specification

## Module

`backend/discovery/utils/text_utils.py`

## Package

`backend.discovery.utils`

## Goals & Constraints

- All functions are **pure** (no side effects, no file I/O, no network calls).
- Fully typed with `pyright`/`mypy` strict mode compatibility.
- No `sklearn` or other heavy statistical dependencies — pure Python only.
- Every function accepts `str` → returns `str` or `list[str]` or `list[tuple[str, float]]`.
- Deterministically produce identical output for identical input across calls.

---

## Public Functions

---

### 1. `normalize(text: str) -> str`

**Responsibility:** Normalize unicode text and whitespace to a canonical form.

**What it does — in order:**

1. **Unicode NFKC normalization** — `unicodedata.normalize("NFKC", text)`. Decomposes compatibility characters (e.g. `"ﬁ"` → `"fi"`, `"½"` → `"1/2"`, `"ℌ"` → `"H"`), then recomposes. Ensures consistent byte representation for comparison and storage.

2. **Whitespace collapse** — one-or-more consecutive whitespace characters (`\s{2,}`) replaced with a single ASCII space.

3. **Trim** — leading and trailing ASCII whitespace removed.

**Notes on NFKC vs NFC:** NFKC (compatibility) is chosen over NFC (canonical) because it also normalizes character width (fullwidth forms), subscripts/superscripts, and multiple representations of the same visual character (e.g. `"②"` → `"2"`). This is important for search text where users may paste mixed-width or compatibility-equivalent characters.

**Input:** Any `str`, including empty string.
**Output:** A normalized `str`, or `""` if input is empty or only whitespace.

**Edge cases:**

| Input | Output |
|-------|--------|
| `""` | `""` |
| `"   "` | `""` |
| `"café"` (U+0065 U+0301 combined) | `"café"` (composed) |
| `"café"` (U+0065 U+0301 decomposed) | `"café"` (identical composed form) |
| `" "` (em space) | `" "` (collapsed to single space) |
| `" "` (non-breaking space) | `" "` (treated as whitespace) |
| `"‐"` (hyphen) | `" "` (treated as whitespace by collapse) |
| `"  Hello world  "` | `"Hello world"` |
| Mixed-width: `"Ｈｅｌｌｏ"` | `"Hello"` (fullwidth → ASCII) |
| Compatibility: `"ﬁle"` | `"file"` |

**Notes for implementation:**
- Use `re.compile(r"\s{2,}")` for the whitespace collapse regex (pre-compiled at module level as `_WS_COLLAPSE`).
- Pre-compile `_NON_PRINTABLE` pattern (`[\x00-\x1f\x7f-\x9f]`) and optionally strip non-printable control characters too, as `strip_html` already handles this but `normalize` alone should also produce clean output.
- NFKC normalization via `unicodedata.normalize("NFKC", text)`.

---

### 2. `normalize_whitespace(text: str) -> str`

**Responsibility:** Collapse all runs of whitespace characters to a single ASCII space and strip ends.

**What it does:**
- Identical to the whitespace-normalization step of `normalize()`.
- Does **not** perform NFKC normalization — this is a dedicated whitespace-only function for cases where unicode content should be preserved as-is.

**When to use:**
- After extracting text from structured formats where unicode must be preserved but layout whitespace is noisy.
- Not needed if `normalize()` is already called.

**Input:** Any `str`.
**Output:** WhitESPACE-normalized `str`.

**Edge cases:**

| Input | Output |
|-------|--------|
| `""` | `""` |
| `"\n\n\n"` | `""` |
| `"\t  hello \n world "` | `"hello world"` |
| `"  "` (NBSP + em space) | `" "` (both whitespace, collapsed) |

---

### 3. `strip_html(raw_html: str) -> str`

**Responsibility:** Remove HTML markup, decode HTML entities, and clean control characters, producing plain text.

**Existing implementation — confirmed correct.** Do not change behavior.

**What it does (in order):**

1. Remove block-level tags and their contents — `<script>`, `<style>`, `<noscript>`, `<iframe>`, `<svg>`, `<math>` — via `_BLOCK_TAGS` regex with `re.DOTALL | re.IGNORECASE`.
2. Remove all remaining HTML tags via `_HTML_TAGS` regex.
3. Decode HTML entities (named, decimal, hex) via `_HTML_ENTITIES` regex, wrapping with spaces so adjacent entities don't merge.
4. Normalize unicode dashes (`‐`–`―`, `−`) to ASCII space.
5. Remove ASCII control characters (`\x00-\x1f`, `\x7f-\x9f`) via `_NON_PRINTABLE` regex.
6. Collapse whitespace runs to single space.
7. Strip leading/trailing whitespace.

**Input:** Any `str` containing HTML, possibly mixed with plain text.
**Output:** Plain text `str`.

**Edge cases:**

| Input | Output |
|-------|--------|
| `"<p>Hello</p>"` | `"Hello"` |
| `"Hello & world"` | `"Hello & world"` |
| `"&#65;&#x42;"` | `"AB"` |
| `"<script>evil()</script>safe"` | `"safe"` |
| `"\x00control"` | `"control"` |
| Empty string | `""` |
| Plain text (no tags) | Passed through whitespace-normalized |

---

### 4. `extract_sentences(text: str) -> list[str]`

**Responsibility:** Split natural-language prose text into individual sentences.

**Existing implementation — confirmed correct.** Do not change behavior.

**Algorithm:** Split on the `_SENTENCE_BOUNDARY` regex:

```
(?<=[.!?])\s+(?=[A-ZÀ-ſ一-鿿ぁ-ゔ゠-ヿ])
```

A positive lookbehind for `.` `!` `?`, followed by one-or-more whitespace, followed by an uppercase letter (ASCII A–Z, Latin extended capital, CJK, Japanese halfwidth/fullwidth katakana). This avoids splitting on abbreviations (`"e.g."` followed by lowercase `t`), decimal numbers (`"3.14"`), and ellipses.

**Post-processing:** Split returns a list; trailing empty strings from the regex split are **retained** (not filtered). Callers who want to skip empty strings filter with `s for s in result if s`.

**Input:** Any `str`, ideally already cleaned of HTML.
**Output:** `list[str]` of potential sentences, in order. May contain empty strings.

**Edge cases:**

| Input | Output |
|-------|--------|
| `"Hello world!"` | `["Hello world!"]` |
| `"Hello world! How are you?"` | `["Hello world!", "How are you?"]` |
| `"No terminal punctuation"` | `["No terminal punctuation"]` |
| `"Wait..."` | `["Wait...", ""]` (second element is empty; filter if needed) |
| `"See e.g. the docs. It works."` | `["See e.g. the docs.", "It works."]` |
| Empty string | `[]` |
| `"   "` | `[]` (after normalize, input won't have this) |
| `"Bonjour monde! Ça va? Oui."` | Correctly splits on accented capitals |
| `"3.14 is pi."` | `["3.14 is pi."]` (no split after decimal) |
| `"What?! Genuinely?"` | `["What?!", "Genuinely?"]` (multiple punct OK) |

**Notes:** Abbreviation handling via the boundary regex is intentionally simple. Complex cases like `"Dr. Smith"` or `"U.S.A."` are not handled; they require a full NLP pipeline. This is acceptable for the Discovery Service context where article content is clean prose, not citations.

---

### 5. `extract_paragraphs(text: str) -> list[str]`

**Responsibility:** Split text into semantic paragraphs delimited by two or more consecutive newline characters.

**Existing implementation — confirmed correct.** Do not change behavior.

**Algorithm:**
1. Split on `_PARAGRAPH_BOUNDARY` regex: `(?:\r?\n){2,}` (handles both `\n\n` and `\r\n\r\n`).
2. For each block, strip leading/trailing whitespace.
3. Discard blocks that are empty after stripping.
4. For non-empty blocks, further split on `_SENTENCE_BOUNDARY` and append each non-empty sentence as its own paragraph entry.

**Input:** Any `str`, ideally raw text with line breaks.
**Output:** `list[str]` of paragraph sentences. Each entry is a single sentence (not multi-sentence blocks). Empty entries discarded.

**Edge cases:**

| Input | Output |
|-------|--------|
| `"Para one.\n\nPara two."` | `["Para one.", "Para two."]` |
| `"A.\r\n\r\nB.\r\n\r\nC."` | `["A.", "B.", "C."]` |
| `"A\n\n\n\nB"` | `["A", "B"]` |
| `"\n\nSkip leading. Continue.\n\nEnd."` | `["Skip leading.", "Continue.", "End."]` |
| Empty string | `[]` |
| `"No breaks here just text"` | `["No breaks here just text"]` |

---

### 6. `extract_candidate_phrases(text: str, *, n: int = 3) -> list[str]`

**Responsibility:** Extract all contiguous word n-grams (phrases of length `n`) from `text` as candidate search phrases.

**This function does not yet exist and must be implemented.**

**Algorithm:**

1. **Normalize input** — run `normalize(text)` first to ensure consistent tokenization.
2. **Tokenize** — split on word boundaries defined as runs of non-word characters (same splitter as `extract_keywords`: `r"[^\w'-]+"`). Acquire tokens as lowercase strings.
3. **Filter tokens** — remove stopwords (same `_STOPWORDS` set), tokens shorter than `min_word_length=2`, pure-digit tokens.
4. **Generate n-grams** — for each window of size `n` sliding over the filtered token list, yield the tuple of `n` tokens joined by a single space.
5. **Deduplicate** — return a list of unique phrases preserving insertion order (first occurrence order). Use a `dict.fromkeys()` pattern to deduplicate while preserving order.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | — | Input text to extract phrases from. |
| `n` | `int` | `3` | Phrase length in words. Must be ≥ 1 and ≤ 10. |
| `min_word_length` | `int` | `2` | Minimum character length per word in the phrase. |
| `min_phrase_count` | `int` | `1` | If a phrase appears fewer than this many times in the text, drop it. Default 1 means accept all unique phrases. |

**Input:** Any `str`; must be at least `n` words after stopword filtering.
**Output:** `list[str]` of unique n-gram phrases, in first-occurrence order.

**Edge cases:**

| Input | n | Output |
|-------|---|--------|
| `"python programming language tutorial guide"` | 3 | `["python programming language", "programming language tutorial", "language tutorial guide"]` |
| `"python python python"` (same word 3×) | 3 | `["python python python"]` if min_phrase_count=1 |
| `"a the an of"` (all stopwords) | 2 | `[]` |
| Short text fewer than n words | 3 | `[]` |
| `text` with punctuation | 2 | `"hello, world!"` → tokenizes as `["hello", "world"]` → phrase: `"hello world"` |
| Hyphenated words: `"machine-learning tutorial"` | 2 | `"machine-learning tutorial"` (hyphen in `\w` range kept) |

**Return type annotation:** `-> list[str]`

**Example doctest:**
```python
>>> phrases = extract_candidate_phrases("python programming tutorial guide programming language")
>>> phrases
['python programming tutorial', 'programming tutorial guide', 'tutorial guide programming', 'guide programming language']
```

**Notes for implementation:**
- Pre-compile the word-boundary regex at module level (`_PHRASE_WORD_BOUNDARY = re.compile(r"[^\w'-]+")` — reuse `_WORD_BOUNDARY`).
- Handle `n <= 0` or `n > 10` by raising `ValueError` with a descriptive message.
- For `min_phrase_count > 1`, count occurrences using `collections.Counter` over all n-grams.
- Empty input or input that yields no phrases returns `[]`.

---

### 7. `extract_keywords(text: str, *, top_k: int = 30, min_word_length: int = 3) -> list[tuple[str, float]]`

**Responsibility:** Extract the top-k most frequent terms from text, ranked by normalized term frequency.

**Existing implementation — confirmed correct.** Do not change behavior.

**Algorithm:**

1. Tokenize: split on `r"[^\w'-]+"`, lowercase all tokens.
2. Filter: drop stopwords (case-insensitive membership test in `_STOPWORDS` frozenset), tokens shorter than `min_word_length`, pure-digit tokens.
3. Frequency: `collections.Counter` over filtered tokens.
4. Score: `score = count / max_count` for each word (normalized to [0.0, 1.0] by max term frequency).
5. Sort descending by score, return top-k as `list[tuple[str, float]]`.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | — | Input text |
| `top_k` | `int` | `30` | Maximum keywords to return. Must be ≥ 1. |
| `min_word_length` | `int` | `3` | Minimum character length per word. Must be ≥ 1. |

**Input:** Any `str`.
**Output:** `list[tuple[str, float]]` sorted by score descending, `score ∈ [0.0, 1.0]`. Empty list if no keywords found.

**Edge cases:**

| Input | Output |
|-------|--------|
| `""` | `[]` |
| `"a the an is was were"` (all stopwords) | `[]` |
| `"python 123 python"` | `[("python", 1.0)]` (digits filtered) |
| Word appearing once | Score 1.0 (max_freq = 1, so normalized = 1.0) |
| `top_k=0` | Raise `ValueError` |
| All scores equal | Return in insertion order (sorted stableness) |

---

### 8. `extract_keywords_flat(keywords: list[tuple[str, float]]) -> list[str]`

**Responsibility:** Convert a `extract_keywords` output (`list[tuple[str, float]]`) into a flat sorted list of keyword strings.

**Existing implementation — confirmed correct.** Do not change behavior.

**Algorithm:** Sort the tuples by score descending, return only the keyword string from each tuple.

**Edge cases:**

| Input | Output |
|-------|--------|
| `[("python", 1.0), ("rust", 0.4), ("go", 0.7)]` | `["python", "go", "rust"]` |
| `[]` | `[]` |

---

## Module-Level Constants (Implementation参考)

These constants already exist in the module. They are listed here for completeness and must be preserved:

```python
_NON_PRINTABLE: Final[re.Pattern[str]]     # ASCII control chars [\x00-\x1f\x7f-\x9f]
_WS_COLLAPSE: Final[re.Pattern[str]]       # Two+ whitespace [\s]{2,}
_BLOCK_TAGS: Final[re.Pattern[str]]        # script/style/iframe/noscript SVG/math + contents
_HTML_TAGS: Final[re.Pattern[str]]         # All HTML tags
_HTML_ENTITIES: Final[re.Pattern[str]]    # Named, decimal, hex entities
_SENTENCE_BOUNDARY: Final[re.Pattern[str]] # (?<=[.!?])\s+(?=[A-ZÀ-ſ一-鿿])
_PARAGRAPH_BOUNDARY: Final[re.Pattern[str]] # (?:\r?\n){2,}
_STOPWORDS: Final[frozenset[str]]          # ~100 common English stopwords
_WORD_BOUNDARY: Final[re.Pattern[str]]      # [^\w']+
```

**Note:** `_STOPWORDS` is lowercase. Stopword filtering must be case-insensitive — implement as `if w.lower() not in _STOPWORDS`.

---

## Exports (`__init__.py`)

`backend/discovery/utils/__init__.py` should export all public functions:

```python
"""Text processing utilities for the Discovery Service."""
from backend.discovery.utils.text_utils import (
    clean_text,           # alias of normalize
    extract_candidate_phrases,
    extract_keywords,
    extract_keywords_flat,
    extract_paragraphs,
    extract_sentences,
    normalize,
    normalize_whitespace,
    strip_html,
    truncate,
    remove_html_tags_fast,
)

__all__ = [
    "clean_text",
    "extract_candidate_phrases",
    "extract_keywords",
    "extract_keywords_flat",
    "extract_paragraphs",
    "extract_sentences",
    "normalize",
    "normalize_whitespace",
    "strip_html",
    "truncate",
    "remove_html_tags_fast",
]
```

---

## Test Cases

### TC1 — `normalize`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC1a | Collapse multiple spaces | `"Hello    world"` | `"Hello world"` |
| TC1b | Collapse tabs/newlines | `"a\t\n\n\tb"` | `"a b"` |
| TC1c | Strip leading/trailing | `"  hello  "` | `"hello"` |
| TC1d | NFKC normalization composes combined chars | `"café"` (combined U+00E9) | `"café"` (unchanged) |
| TC1e | NFKC fullwidth to ASCII | `"ＨＥＬＬＯ"` | `"HELLO"` |
| TC1f | NFKC subscripts | `"H₂O"` | `"H2O"` |
| TC1g | Empty string | `""` | `""` |
| TC1h | Only whitespace | `"   \n\t  "` | `""` |
| TC1i | Already clean | `"hello world"` | `"hello world"` |
| TC1j | NFKC compat: ﬁ → fi | `"ﬁle"` | `"file"` |

### TC2 — `normalize_whitespace`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC2a | Collapse spaces | `"a    b"` | `"a b"` |
| TC2b | Collapse tabs | `"a\t\tb"` | `"a b"` |
| TC2c | Does NOT NFKC normalize | `"ＨＥＬＬＯ"` | `"ＨＥＬＬＯ"` |
| TC2d | Empty string | `""` | `""` |

### TC3 — `strip_html`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC3a | Remove basic tags | `"<p>Hello</p>"` | `"Hello"` |
| TC3b | Remove script + contents | `"<script>evil()</script>safe"` | `"safe"` |
| TC3c | Remove style + contents | `"<style>.cls{}</style>text"` | `"text"` |
| TC3d | Decode `&` entity | `"Hello & world"` | `"Hello & world"` |
| TC3e | Decode `&#65;` decimal | `"&#65;"` | `"A"` |
| TC3f | Decode `&#x41;` hex | `"&#x41;"` | `"A"` |
| TC3g | Remove SVG with attributes | `"<svg onload=alert(1)>oops</svg>safe"` | `"safe"` |
| TC3h | Remove control chars | `"\x00\x07text"` | `"text"` |
| TC3i | Preserve spaces | `"<p>Hello   World</p>"` | Contains `" "` |
| TC3j | Preserve `&` not entity | `"& <tag>"` | `"& <tag>"` |

### TC4 — `extract_sentences`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC4a | Simple split | `"Hello world! How are you?"` | `["Hello world!", "How are you?"]` |
| TC4b | No punctuation | `"No punctuation here"` | `["No punctuation here"]` |
| TC4c | Ellipsis at end produces empty 2nd element | `"Wait..."` | `["Wait...", ""]` |
| TC4d | e.g. not split | `"See e.g. the docs. It works."` | 2 elements, `"e.g."` not split |
| TC4e | CJK capitalization | `"Bonjour monde! Ça va?"` | Includes `"Ça va?"` |
| TC4f | Decimal numbers | `"Pi is 3.14."` | `["Pi is 3.14."]` |
| TC4g | Empty input | `""` | `[]` |
| TC4h | Multi-punctuation | `"What?! Genuinely?"` | `["What?!", "Genuinely?"]` |

### TC5 — `extract_paragraphs`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC5a | Double newline split | `"A.\n\nB.\n\nC."` | `["A.", "B.", "C."]` |
| TC5b | CRLF double newline | `"A.\r\n\r\nB."` | `["A.", "B."]` |
| TC5c | Triple newlines | `"A\n\n\nB"` | `["A", "B"]` |
| TC5d | Skip leading blank | `"\n\nSkip. Continue.\n\nEnd."` | includes `"Skip."` |
| TC5e | Empty input | `""` | `[]` |
| TC5f | No newlines, one sentence | `"Single paragraph."` | `["Single paragraph."]` |

### TC6 — `extract_candidate_phrases` (NEW — must be implemented)

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC6a | 3-word phrases from 5-word text | `text="python programming tutorial guide"`, `n=3` | `["python programming tutorial", "programming tutorial guide"]` |
| TC6b | 2-word phrases | `text="python python python"`, `n=2` | `["python python"]` |
| TC6c | Stopword-only text | `text="a the an of"`, `n=2` | `[]` |
| TC6d | Too short for n | `text="python java"`, `n=3` | `[]` |
| TC6e | Lowercase normalized | `text="PYTHON JAVA CODE"`, `n=2` | `["python java", "java code"]` |
| TC6f | Unique only | `text="python java python java"`, `n=2` | `["python java", "java python"]` (first-occ order) |
| TC6g | Hyphenated words | `text="machine-learning tutorial guide"`, `n=2` | `["machine-learning tutorial", "learning tutorial guide"]` |
| TC6h | n=1 returns unique words | `text="python java python"`, `n=1` | `["python", "java"]` |
| TC6i | n out of bounds LOW | `n=0` | raises `ValueError` |
| TC6j | n out of bounds HIGH | `n=11` | raises `ValueError` |
| TC6k | Punctuation stripped | `text="hello, world! how are you?"`, `n=2` | `["hello world", "world how", "how are", "are you"]` |
| TC6l | min_phrase_count=2 filtering | `text="python java python ruby python scala python"`, `n=1`, `min_phrase_count=2` | `["python", "java"]` (python=3, java=1, ruby=1, scala=1 → only python qualifies with count>=2) |

*Correction for TC6l:* `min_phrase_count=2` filters by raw term frequency across the whole text, not by n-gram occurrence count. For `n=1`, phrases are individual words. For `text="python java python ruby python scala python"`:
- count("python")=3, count("java")=1, count("ruby")=1, count("scala")=1
- With `min_phrase_count=2`: only `"python"` passes

### TC7 — `extract_keywords`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC7a | Basic top-k | `text="python python python java code"`, `top_k=2` | `[("python", 1.0), ("java", 0.something < 1.0)]` — python first |
| TC7b | Stopwords excluded | `text="the python the language the"`, `top_k=5` | No stopwords in result |
| TC7c | Score monotonic descending | `text="python python python"` | `score == 1.0` for the word |
| TC7d | Scores in [0,1] | any normal text | `all(0.0 <= s <= 1.0)` |
| TC7e | Empty text | `""` | `[]` |
| TC7f | All stopwords | `"a the an is was were"` | `[]` |
| TC7g | Digits filtered | `text="python 123 python 456"`, `min_word_length=3` | Only `"python"` |
| TC7h | `top_k=1` | any text | list of length ≤ 1 |
| TC7i | `top_k=0` | any text | raises `ValueError` |
| TC7j | `min_word_length=5` | `text="a python an algorithm"` | no 1-2 char results |

### TC8 — `extract_keywords_flat`

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| TC8a | Basic | `[("python", 1.0), ("rust", 0.4), ("go", 0.7)]` | `["python", "go", "rust"]` |
| TC8b | Empty | `[]` | `[]` |
| TC8c | Single element | `[("python", 1.0)]` | `["python"]` |

### TC9 — Pipeline Integration

| ID | Description |
|----|-------------|
| TC9a | `normalize(strip_html(html_text))` → clean plain text |
| TC9b | `extract_sentences(normalize(strip_html(html_text)))` → sentence list from HTML |
| TC9c | `extract_keywords(normalize(strip_html(html_text)), top_k=10)` → top keywords from HTML |
| TC9d | `extract_candidate_phrases(normalize(strip_html(html_text)), n=3, min_phrase_count=2)` → phrases appearing ≥ 2 times from HTML |
| TC9e | `extract_paragraphs(strip_html(raw))` → paragraph list from HTML |

### TC10 — Determinism

| ID | Description |
|----|-------------|
| TC10a | Calling any function twice on same input returns identical output |
| TC10b | Calling any function 100 times returns identical result each call (no global state mutation) |

---

## Acceptance Criteria

### Functional

- [ ] `normalize()` applies NFKC normalization, collapses whitespace, strips ends
- [ ] `normalize_whitespace()` only collapses whitespace — does NOT alter unicode characters
- [ ] `strip_html()` removes all HTML tags, decodes all entity types, removes control chars
- [ ] `extract_sentences()` splits on `.` `!` `?` before uppercase, not on `e.g.` or decimals
- [ ] `extract_paragraphs()` splits on `\n\n` or `\r\n\r\n`, discards empty, returns single sentences
- [ ] `extract_candidate_phrases()` returns ordered unique n-grams, lowercased, stopwords removed
- [ ] `extract_keywords()` returns `list[tuple[str, float]]` sorted by score descending, scores in [0,1]
- [ ] `extract_keywords_flat()` converts keyword tuples to sorted strings
- [ ] All functions are pure — identical input always yields identical output

### Type safety

- [ ] All functions have complete type annotations (`-> str`, `-> list[str]`, `-> list[tuple[str, float]]`)
- [ ] No `Any` return types (except possibly for `**kwargs` passthrough)
- [ ] Module passes `pyright --strict` with no errors

### Edge cases

- [ ] Empty string returns `[]` from all list-returning functions
- [ ] All-stopword input returns `[]` for keyword/phrase extraction
- [ ] `n <= 0` or `n > 10` in `extract_candidate_phrases` raises `ValueError`
- [ ] `top_k=0` in `extract_keywords` raises `ValueError`
- [ ] Results contain no stopwords (verified by checking against `_STOPWORDS`)

### Test coverage

- [ ] Every public function has at least one unit test per edge case in TC1–TC10 above
- [ ] All 35 existing tests continue to pass (no regression in existing functions)
- [ ] Pipeline tests (TC9) verify full `strip_html` → `normalize` → `extract_X` chains