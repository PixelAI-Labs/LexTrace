"""Unit tests for backend.discovery.utils.text_utils.

Covers: strip_html, normalize, clean_text, extract_sentences,
extract_paragraphs, extract_keywords, extract_keywords_flat, truncate,
remove_html_tags_fast.
"""

from __future__ import annotations

import pytest

from backend.discovery.utils.text_utils import (
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


# ---------------------------------------------------------------------------
# TC1 — strip_html
# ---------------------------------------------------------------------------

def test_TC1_strip_html_basic_tags() -> None:
    assert strip_html("<p>Hello <strong>world</strong></p>") == "Hello world"


def test_TC1_strip_html_script_and_style_contents_removed() -> None:
    html = (
        "<html><body>"
        "<script>document.write('evil')</script>"
        "<style>.cls { color: red }</style>"
        "Clean text here."
        "</body></html>"
    )
    result = strip_html(html)
    assert "document.write" not in result
    assert "color: red" not in result
    assert "Clean text here." in result


def test_TC1_strip_html_noscript_removed() -> None:
    assert strip_html("<noscript>Disable JS</noscript>Visible.") == "Visible."


def test_TC1_strip_html_html_entities_decoded() -> None:
    assert strip_html("Hello & world &mdash; &#65;&#x42;") == "Hello & world A B"


def test_TC1_strip_html_control_chars_removed() -> None:
    assert strip_html("text\x00\x07\x1fmore") == "textmore"


def test_TC1_strip_html_svg_removed() -> None:
    assert strip_html("<svg onload=alert(1)>oops</svg>visible") == "visible"


def test_TC1_strip_html_preserves_whitespace() -> None:
    assert " " in strip_html("<p>Hello   World</p>")


# ---------------------------------------------------------------------------
# TC2 — normalize
# ---------------------------------------------------------------------------

def test_TC2_normalize_collapse_spaces() -> None:
    assert normalize("Hello    world") == "Hello world"


def test_TC2_normalize_collapse_tabs_newlines() -> None:
    assert normalize("a\t\n\n\tb") == "a b"


def test_TC2_normalize_strip_ends() -> None:
    assert normalize("  hello  ") == "hello"


def test_TC2_normalize_unicode_nfkc() -> None:
    # "café" with combining accent; NFKC separates then recomposes
    result = normalize("café")
    # The normalised form must still be the same visible word
    assert "caf" in result and "é" in result


def test_TC2_normalize_empty() -> None:
    assert normalize("") == ""


def test_TC2_normalize_already_clean() -> None:
    assert normalize("hello world") == "hello world"


# ---------------------------------------------------------------------------
# TC3 — clean_text (alias of normalize)
# ---------------------------------------------------------------------------

def test_TC3_clean_text_is_normalize() -> None:
    assert clean_text("hello   world") == normalize("hello   world")


# ---------------------------------------------------------------------------
# TC4 — extract_sentences
# ---------------------------------------------------------------------------

def test_TC4_sentences_basic() -> None:
    result = extract_sentences("Hello world! How are you? Wait...")
    assert result == ["Hello world!", "How are you?", "Wait..."]


def test_TC4_sentences_no_punctuation() -> None:
    assert extract_sentences("No punctuation here") == ["No punctuation here"]


def test_TC4_sentences_drops_empty() -> None:
    """Empty strings from the split should be filtered out."""
    sentences = extract_sentences("First.  Second?  Third!")
    assert all(s for s in sentences)


def test_TC4_sentences_uses_sentence_boundary_regex() -> None:
    """Split must happen at .!?, not on abbreviations like e.g."""
    text = "See e.g. the documentation. It works."
    result = extract_sentences(text)
    # "e.g." should not split — period is followed by lowercase 't'
    assert len(result) == 2


def test_TC4_sentences_unicode_letters() -> None:
    """CJK and accented characters after punctuation should still split."""
    result = extract_sentences("Bonjour monde! Ça va? Oui.")
    assert "Bonjour monde!" in result
    assert "Ça va?" in result


# ---------------------------------------------------------------------------
# TC5 — extract_paragraphs
# ---------------------------------------------------------------------------

def test_TC5_paragraphs_double_newline() -> None:
    result = extract_paragraphs("Para one.\n\nPara two.\n\nPara three.")
    assert result == ["Para one.", "Para two.", "Para three."]


def test_TC5_paragraphs_crlf() -> None:
    result = extract_paragraphs("A.\r\n\r\nB.\r\n\r\nC.")
    assert result == ["A.", "B.", "C."]


def test_TC5_paragraphs_drops_empty() -> None:
    result = extract_paragraphs("A\n\n\n\nB")
    assert result == ["A", "B"]
    assert "" not in result


def test_TC5_paragraphs_preserves_leading_trailing_newlines() -> None:
    result = extract_paragraphs("\n\nSkip leading. And then.\n\nEnd.")
    assert "Skip leading." in result


# ---------------------------------------------------------------------------
# TC6 — extract_keywords
# ---------------------------------------------------------------------------

def test_TC6_keywords_basic() -> None:
    text = "python programming language python code python tutorial"
    result = extract_keywords(text, top_k=3)
    words = [w for w, _ in result]
    scores = [s for _, s in result]
    assert "python" in words
    assert scores == sorted(scores, reverse=True)


def test_TC6_keywords_top_k_limit() -> None:
    text = "python java ruby golang rust typescript kotlin swift"
    result = extract_keywords(text, top_k=3)
    assert len(result) <= 3


def test_TC6_keywords_stopwords_filtered() -> None:
    text = "the python the programming the language the code the"
    result = extract_keywords(text)
    # stopwords must not appear
    for word, _ in result:
        assert word not in {
            "the", "and", "or", "but", "is", "are", "was", "were",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after",
        }


def test_TC6_keywords_min_word_length() -> None:
    text = "a python an algorithm the code"
    result = extract_keywords(text, min_word_length=5)
    words = [w for w, _ in result]
    assert all(len(w) >= 5 for w in words)


def test_TC6_keywords_pure_digits_ignored() -> None:
    text = "python 123 python 456 python"
    result = extract_keywords(text, min_word_length=3)
    assert all(not w.isdigit() for w, _ in result)


def test_TC6_keywords_scores_in_range() -> None:
    text = "python programming python python language language code"
    result = extract_keywords(text)
    assert all(0.0 <= score <= 1.0 for _, score in result)


def test_TC6_keywords_empty_text_returns_empty() -> None:
    assert extract_keywords("") == []
    assert extract_keywords("a the an is are was were") == []


# ---------------------------------------------------------------------------
# TC7 — extract_keywords_flat
# ---------------------------------------------------------------------------

def test_TC7_keywords_flat_returns_words_in_score_order() -> None:
    keywords = [("python", 1.0), ("rust", 0.4), ("go", 0.7)]
    flat = extract_keywords_flat(keywords)
    assert flat == ["python", "go", "rust"]


def test_TC7_keywords_flat_empty() -> None:
    assert extract_keywords_flat([]) == []


# ---------------------------------------------------------------------------
# TC8 — truncate
# ---------------------------------------------------------------------------

def test_TC8_truncate_under_limit() -> None:
    assert truncate("hello", max_length=10) == "hello"


def test_TC8_truncate_exact_match() -> None:
    assert truncate("hello", max_length=5) == "hello"


def test_TC8_truncate_appends_suffix() -> None:
    result = truncate("hello world", max_length=8, suffix="...")
    assert result == "hello..."
    assert len(result) == 8


def test_TC8_truncate_custom_suffix() -> None:
    result = truncate("hello world", max_length=7, suffix="…")
    assert result == "hello…" and len(result) == 7


def test_TC8_truncate_zero_max() -> None:
    assert truncate("hello", max_length=0) == ""


def test_TC8_truncate_suffix_longer_than_max() -> None:
    # Edge case: suffix itself exceeds max_length
    result = truncate("hello", max_length=2, suffix="...")
    # Should not crash; suffix clamps to available space
    assert len(result) <= 2


# ---------------------------------------------------------------------------
# TC9 — remove_html_tags_fast
# ---------------------------------------------------------------------------

def test_TC9_remove_html_tags_fast_basic() -> None:
    assert remove_html_tags_fast("<b>Bold</b> <i>italic</i>!") == "Bold italic!"


def test_TC9_remove_html_tags_fast_leaves_no_tags() -> None:
    assert remove_html_tags_fast("<div><p><span>nested</span></p></div>") == "nested"


def test_TC9_remove_html_tags_fast_does_not_handle_entities() -> None:
    assert remove_html_tags_fast("& <tag>") == "& <tag>"


def test_TC9_remove_html_tags_fast_simple_text_unchanged() -> None:
    assert remove_html_tags_fast("No tags here!") == "No tags here!"


# ---------------------------------------------------------------------------
# TC10 — integration: strip_html + normalize pipeline
# ---------------------------------------------------------------------------

def test_TC10_full_pipeline() -> None:
    raw = """
    <html>
      <body>
        <script>ignore me</script>
        <p>Hello & world!</p>
        <p>Second paragraph.</p>
      </body>
    </html>
    """
    cleaned = normalize(strip_html(raw))
    assert "ignore" not in cleaned
    assert "Hello & world!" in cleaned


def test_TC10_full_pipeline_then_sentences() -> None:
    html = "<p>Hello world. How are you?</p>"
    sentences = extract_sentences(normalize(strip_html(html)))
    assert "Hello world." in sentences
    assert "How are you?" in sentences


def test_TC10_full_pipeline_then_keywords() -> None:
    html = "<p>python python python java code</p>"
    keywords = extract_keywords(normalize(strip_html(html)), top_k=2)
    assert keywords[0][0] == "python"


# ---------------------------------------------------------------------------
# TC11 — Pure function / no side-effect guarantees
# ---------------------------------------------------------------------------

def test_TC11_functions_deterministic() -> None:
    text = "<p>Hello world</p>"
    # Calling twice returns same result
    assert strip_html(text) == strip_html(text)
    assert normalize("  hello   world  ") == normalize("  hello   world  ")
    assert extract_keywords("python python java") == extract_keywords("python python java")


def test_TC11_no_global_state_mutated() -> None:
    """Call a function 100 times — output must be identical each time."""
    text = "python code programming language"
    results = [extract_keywords(text, top_k=5) for _ in range(100)]
    assert len(set(tuple(r) for r in results)) == 1


# ---------------------------------------------------------------------------
# TC6 — extract_candidate_phrases
# ---------------------------------------------------------------------------

from backend.discovery.utils.text_utils import extract_candidate_phrases


def test_TC6a_n_3_extracts_3_word_phrases() -> None:
    """5-word text with n=3 produces 2 phrases (window slides 3 positions)."""
    phrases = extract_candidate_phrases(
        "python programming tutorial guide", n=3
    )
    assert phrases == [
        "python programming tutorial",
        "programming tutorial guide",
    ]


def test_TC6b_n_2_repeating_word() -> None:
    """n=2 on 'python python python' yields one unique phrase."""
    phrases = extract_candidate_phrases("python python python", n=2)
    assert phrases == ["python python"]


def test_TC6c_stopword_only_text() -> None:
    """Text containing only stopwords returns empty list."""
    phrases = extract_candidate_phrases("a the an of for to", n=2)
    assert phrases == []


def test_TC6d_too_short_for_n() -> None:
    """Text with fewer than n words after filtering returns empty list."""
    phrases = extract_candidate_phrases("python java", n=3)
    assert phrases == []


def test_TC6e_lowercase_normalized() -> None:
    """Input is lowercased regardless of case."""
    phrases = extract_candidate_phrases("PYTHON JAVA CODE", n=2)
    assert "python java" in phrases
    assert "java code" in phrases
    # All results must be lowercase
    assert all(p.islower() for p in phrases)


def test_TC6f_unique_only_first_occurrence_order() -> None:
    """Duplicates are removed; first occurrence order is preserved."""
    # python java appears twice, java python once; both appear but in first-occ order
    phrases = extract_candidate_phrases(
        "python java python java", n=2
    )
    assert "python java" in phrases
    assert "java python" in phrases
    # First-occurrence order: python(java) at index 0, java(python) at index 1
    assert phrases.index("python java") < phrases.index("java python")


def test_TC6g_hyphenated_words_kept() -> None:
    """Hyphen is treated as word character and kept in tokens."""
    phrases = extract_candidate_phrases(
        "machine-learning tutorial guide", n=2
    )
    assert "machine-learning tutorial" in phrases
    assert "learning tutorial guide" in phrases


def test_TC6h_n_1_returns_unique_words() -> None:
    """n=1 returns each unique word (unigram) once, in first-occurrence order."""
    phrases = extract_candidate_phrases("python java python", n=1)
    assert phrases == ["python", "java"]


def test_TC6i_n_zero_raises() -> None:
    """n=0 raises ValueError."""
    with pytest.raises(ValueError, match="n must be between 1 and 10"):
        extract_candidate_phrases("python java", n=0)


def test_TC6j_n_eleven_raises() -> None:
    """n>10 raises ValueError."""
    with pytest.raises(ValueError, match="n must be between 1 and 10"):
        extract_candidate_phrases("python java", n=11)


def test_TC6k_punctuation_stripped_from_ngrams() -> None:
    """Punctuation is stripped by tokenisation, producing clean phrases."""
    phrases = extract_candidate_phrases(
        "hello, world! how are you?", n=2
    )
    assert "hello world" in phrases
    assert "world how" in phrases
    assert "how are" in phrases
    assert "are you" in phrases
    # No commas or punctuation in any phrase
    assert all("," not in p and "!" not in p and "?" not in p for p in phrases)


def test_TC6l_min_phrase_count_filters() -> None:
    """min_phrase_count=2 removes phrases appearing only once."""
    text = "python java python ruby python scala python"
    # n=1 → unigrams; count(python)=3, others=1
    phrases = extract_candidate_phrases(text, n=1, min_phrase_count=2)
    assert phrases == ["python"]


def test_TC6l_min_phrase_count_on_bigrams() -> None:
    """min_phrase_count applies to n-gram frequency, not word count."""
    # "python java" appears 2×, "java python" appears 1×
    text = "python java python java ruby"
    phrases = extract_candidate_phrases(
        text, n=2, min_phrase_count=2
    )
    assert phrases == ["python java"]


def test_TC6_empty_text() -> None:
    """Empty string returns empty list."""
    assert extract_candidate_phrases("") == []


def test_TC6_whitespace_only_text() -> None:
    """Text that is only whitespace returns empty list."""
    assert extract_candidate_phrases("   \n\n\t") == []


def test_TC6_preserves_non_stopwords_at_boundary() -> None:
    """Token at start/end of text that is non-stopword is included."""
    phrases = extract_candidate_phrases("python java ruby", n=2)
    assert "python java" in phrases
    assert "java ruby" in phrases