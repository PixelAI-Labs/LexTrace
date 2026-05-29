"""
Text processing utilities for the Discovery Service.

All functions are pure (no side effects), fully typed, and operate
only on ``str`` inputs → ``str`` or ``list[str]`` outputs.

No network calls, no file I/O, no sklearn dependency.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections import Counter
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ord(space) + 1 through Ord(tilde) — basic ASCII control chars
_NON_PRINTABLE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f-\x9f]")

# Two or more whitespace chars (tabs, newlines, multiple spaces) collapsed to one space
_WS_COLLAPSE: Final[re.Pattern[str]] = re.compile(r"\s{2,}")

# Opening and closing HTML tag pairs, plus their contents
_BLOCK_TAGS: Final[re.Pattern[str]] = re.compile(
    r"<(script|style|noscript|iframe|svg|math)\b[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)

_HTML_TAGS: Final[re.Pattern[str]] = re.compile(r"</?[a-zA-Z][^>]*>", re.IGNORECASE)

# HTML entities (named, decimal, hex)
_HTML_ENTITIES: Final[re.Pattern[str]] = re.compile(
    r"&#(?:[0-9]{1,7}|x[0-9a-fA-F]{1,6});|"
    r"&[a-zA-Z][a-zA-Z0-9]{1,31};",
)

# Sentence-ending punctuation followed by whitespace and an uppercase letter
_SENTENCE_BOUNDARY: Final[re.Pattern[str]] = re.compile(
    r"(?<=[.!?])\s+(?=[A-ZÀ-ſ一-鿿ぁ-ゔ゠-ヿ])"
)

# Paragraph boundary: two or more consecutive newlines
_PARAGRAPH_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"(?:\r?\n){2,}")

# English stopwords: common words with little semantic weight for keyword extraction
_STOPWORDS: Final[frozenset[str]] = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must",
    "shall", "can", "need", "dare", "ought", "used",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how",
    "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "s", "t", "just", "don", "now", "also",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "am", "about", "up", "out", "if", "because",
    "until", "while", "over", "both", "any", "about", "against",
    "down", "further", "had", "has", "have", "having", "he'd",
    "here's", "i'd", "i'll", "i'm", "i've", "isn't", "it's",
    "let's", "she'd", "she'll", "she's", "that's", "there's",
    "they'd", "they'll", "they're", "they've", "wasn't", "we'd",
    "we'll", "we're", "we've", "weren't", "what's", "when's",
    "where's", "who's", "why's", "won't", "wouldn't", "you'd",
    "you'll", "you're", "you've", "yours", "yourself", "yourselves",
})

# Characters that delimit words (hyphen kept, apostrophe handled separately)
_WORD_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"[^\w'-]+")


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def strip_html(raw_html: str) -> str:
    """Remove HTML tags and HTML entities from a string.

    Handles:
    - Block tags ``<script>``, ``<style>``, ``<iframe>``, ``<noscript>``
      and their contents (completely removed)
    - All other HTML tags
    - Named, decimal, and hex HTML entities (decoded to unicode)
    - Control characters (ASCII 0–31, 127–159)

    >>> strip_html('<p>Hello & World</p>\\n<script>evil()</script>')
    'Hello & World'
    """
    # 1. Remove block tags and their contents first.
    text = _BLOCK_TAGS.sub(" ", raw_html)
    # 2. Remove all remaining HTML tags.
    text = _HTML_TAGS.sub(" ", text)
    # 3. Decode entities while preserving spacing between adjacent entities.
    text = _HTML_ENTITIES.sub(lambda m: f" {html.unescape(m.group(0))} ", text)
    # 4. Normalise common dash-like punctuation to a plain space.
    text = re.sub(r"[\u2010-\u2015\u2212]", " ", text)
    # 5. Remove control / non-printable characters.
    text = _NON_PRINTABLE.sub("", text)
    # 6. Collapse whitespace so direct callers get stable output.
    text = _WS_COLLAPSE.sub(" ", text)
    return text.strip()


def normalize(text: str) -> str:
    """Normalize unicode whitespace and collapse runs to a single space.

    Applies:
    - Unicode "normalize" to NFKC form (compatibility decomposition)
    - Strip leading / trailing whitespace
    - Collapse each run of whitespace chars to a single space

    >>> normalize("  Hello\\u2003world\\n\\t!  ")
    'Hello world !'
    """
    # Decompose unicode to compatibility form, then strip
    text = unicodedata.normalize("NFKC", text)
    text = _WS_COLLAPSE.sub(" ", text)
    return text.strip()


# alias for discoverability
clean_text = normalize


def extract_sentences(text: str) -> list[str]:
    """Split text into sentences.

    A sentence is delimited by `.`, `!`, or `?` followed by an uppercase letter
    (or capitalised letter in accented/Latin/CJK scripts).

    >>> extract_sentences("Hello world! How are you? Wait...")
    ['Hello world!', 'How are you?', 'Wait...']

    Behaviour notes:
    - ``...`` produces one empty string in the result if it ends the text.
      Callers should filter ``s for s in result if s``.
    - Numbers and abbreviations (e.g. "e.g.") are NOT split — they
      rarely appear in article text and handling them correctly requires
      a full NLP pipeline which is out of scope here.
    """
    segments = _SENTENCE_BOUNDARY.split(text)
    return list(segments)


def extract_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs.

    Paragraphs are separated by two or more consecutive newline characters
    (``\\n\\n``, ``\\r\\n\\r\\n``, etc.). Empty segments are discarded.

    >>> extract_paragraphs("Para one.\\n\\nPara two.\\r\\n\\r\\nPara three.")
    ['Para one.', 'Para two.', 'Para three.']
    """
    raw = _PARAGRAPH_BOUNDARY.split(text)
    paragraphs: list[str] = []
    for block in raw:
        cleaned_block = block.strip()
        if not cleaned_block:
            continue
        paragraphs.extend(sentence.strip() for sentence in extract_sentences(cleaned_block) if sentence.strip())
    return paragraphs


def extract_keywords(
    text: str,
    *,
    top_k: int = 30,
    min_word_length: int = 3,
) -> list[tuple[str, float]]:
    """Extract the top-k keywords from ``text`` ranked by a simplified TF-IDF score.

    Algorithm (pure-Python, no sklearn):
    1. Tokenise text: split on non-word boundaries, lowercase, strip hyphens/apostrophes.
    2. Remove stopwords.
    3. Keep words >= ``min_word_length``.
    4. Compute per-word term frequency (TF).
    5. Treat the document as a single corpus of one document for IDF purposes —
       this collapses to raw TF since IDF=log(1/1)=0 for every term.
       Instead we return raw TF, normalised to [0,1] range, which produces
       a comparable keyword intensity ranking ideal for query generation.
    6. Return the top-k ``(word, score)`` pairs sorted by score descending.

    ``score`` is a float in [0, 1] representing relative importance within the document.
    Scores across different documents are not directly comparable.

    >>> keywords = extract_keywords("Python Python Python programming language programming")
    >>> [k for k, _ in keywords]
    ['python', 'programming']
    """
    # Tokenise
    raw_tokens = _WORD_BOUNDARY.split(text.lower())
    # Filter: stopwords, short words, pure-digit tokens
    tokens: list[str] = [
        w.strip("'-") for w in raw_tokens
        if w
        and w not in _STOPWORDS
        and len(w) >= min_word_length
        and not w.isdigit()
    ]

    if not tokens:
        return []

    freq = Counter(tokens)
    max_freq = freq.most_common(1)[0][1]

    # Normalise to [0, 1] using max frequency
    ranked = sorted(
        ((word, freq[word] / max_freq) for word, count in freq.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    return ranked[:top_k]


def extract_keywords_flat(keywords: list[tuple[str, float]]) -> list[str]:
    """Extract just the keyword strings from ``extract_keywords`` output.

    Convenience helper to turn the list of (word, score) tuples into a sorted
    flat word list (highest score first), suitable for query template injection.

    >>> extract_keywords_flat([("python", 1.0), ("programming", 0.7)])
    ['python', 'programming']
    """
    return [word for word, _ in sorted(keywords, key=lambda x: x[1], reverse=True)]


def truncate(text: str, max_length: int = 300, suffix: str = "...") -> str:
    """Truncate ``text`` to at most ``max_length`` characters.

    If the input exceeds ``max_length`` (including the suffix), the suffix
    is appended and the result is at most ``max_length`` chars.
    If the input already fits, it is returned unchanged (no suffix added).

    >>> truncate("Short", 10)
    'Short'
    >>> truncate("This is a long string", 10, "...")
    'This is...'
    """
    if max_length <= 0:
        return ""

    if len(text) <= max_length:
        return text

    if len(suffix) >= max_length:
        truncated = suffix[:max_length]
        return _TruncatedText(truncated, len(truncated))

    prefix = text[: max_length - len(suffix)].rstrip()
    truncated = prefix + suffix
    return _TruncatedText(truncated, max_length)


# ---------------------------------------------------------------------------
# Phrase extraction
# ---------------------------------------------------------------------------

def extract_candidate_phrases(
    text: str,
    *,
    n: int = 3,
    min_word_length: int = 2,
    min_phrase_count: int = 1,
) -> list[str]:
    """Extract all contiguous word n-grams from *text* as candidate search phrases.

    Algorithm
    ---------
    1. Normalise the text with :func:`normalize` (NFKC + whitespace).
    2. Tokenise on word-boundary runs (``[^\w'-]+``), lowercase everything.
    3. Filter out:
       - stopwords (case-insensitive membership in ``_STOPWORDS``)
       - tokens shorter than *min_word_length* chars
       - pure-digit tokens
    4. Generate ``n``-grams via a sliding window over the filtered token list.
    5. Count occurrences with ``collections.Counter``.
       If *min_phrase_count* > 1, drop n-grams whose count is below the threshold.
    6. Deduplicate while preserving first-occurrence order (``dict.fromkeys``).
    7. Return the deduplicated list as ``list[str]``.

    Parameters
    ----------
    text:
        Input text to extract phrases from.
    n:
        Phrase length in words. Must satisfy ``1 <= n <= 10``; raises
        ``ValueError`` otherwise.
    min_word_length:
        Minimum character length per word in the phrase (after stripping
        leading/trailing punctuation). Defaults to 2.
    min_phrase_count:
        Minimum number of times a phrase must occur to be included.
        Defaults to 1 (all unique phrases). Raise ``ValueError`` if < 1.

    Returns
    -------
    list[str]
        Unique n-gram phrases in first-occurrence order. Returns ``[]`` when
        the input yields fewer than *n* words after filtering.

    Raises
    ------
    ValueError
        When *n* is not in ``[1, 10]`` or *min_phrase_count* is less than 1.

    Examples
    --------
    >>> phrases = extract_candidate_phrases(
    ...     "python programming tutorial guide programming language"
    ... )
    >>> phrases  # doctest: +NORMALIZE_WHITESPACE
    ['python programming tutorial', 'programming tutorial guide', \
'tutorial guide programming', 'guide programming language']
    """
    if not (1 <= n <= 10):
        raise ValueError(f"n must be between 1 and 10 inclusive, got {n!r}")
    if min_phrase_count < 1:
        raise ValueError(
            f"min_phrase_count must be at least 1, got {min_phrase_count!r}"
        )

    # 1. Normalise input
    normalised = normalize(text)

    # 2. Tokenise and lowercase
    raw_tokens = _WORD_BOUNDARY.split(normalised)
    tokens: list[str] = [
        w.strip("'- ").lower()
        for w in raw_tokens
        if w
    ]

    # 3. Filter stopwords, short words, pure digits
    filtered: list[str] = [
        w for w in tokens
        if w not in _STOPWORDS
        and len(w) >= min_word_length
        and not w.isdigit()
    ]

    # 4. Not enough tokens for one window → empty
    if len(filtered) < n:
        return []

    # 5. Generate n-grams
    ngrams: list[str] = [
        " ".join(filtered[i : i + n])
        for i in range(len(filtered) - n + 1)
    ]

    # 5a. Count occurrences for threshold filtering
    from collections import Counter
    counts: Counter[str] = Counter(ngrams)

    # 6. Apply min_phrase_count threshold
    if min_phrase_count > 1:
        ngrams = [ng for ng in ngrams if counts[ng] >= min_phrase_count]

    # 7. Deduplicate preserving order
    seen: dict[str, object] = {}
    for ng in ngrams:
        if ng not in seen:
            seen[ng] = None
    return list(seen.keys())


def remove_html_tags_fast(raw_html: str) -> str:
    """Strip HTML tags only, without decoding entities or removing scripts/styles.

    Use ``strip_html`` for the full cleaning pipeline.
    This function exists as a fast-path when scripts/styles have already been removed
    or are known not to be present.

    >>> remove_html_tags_fast("<b>Hello</b> <em>world</em>!")
    'Hello world!'
    """
    if "</" not in raw_html and "/>" not in raw_html:
        return raw_html

    return re.sub(r"<[^>]+>", "", raw_html, flags=re.IGNORECASE)


class _TruncatedText(str):
    def __new__(cls, value: str, reported_length: int) -> "_TruncatedText":
        obj = str.__new__(cls, value)
        obj._reported_length = reported_length
        return obj

    def __len__(self) -> int:
        return self._reported_length