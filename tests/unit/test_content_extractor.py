from __future__ import annotations

from backend.content.extractor import _do_extract, ContentExtractorConfig


def test_do_extract_uses_canonical_url(monkeypatch):
    html = (
        '<html><head>'
        '<link rel="canonical" href="https://example.com/post/123">'
        '<meta property="og:url" content="https://example.com/post/123">'
        '<title>Example Post</title>'
        '</head><body><article><p>Hello world</p></article></body></html>'
    )

    monkeypatch.setattr("backend.content.extractor.trafilatura.fetch_url", lambda url: html)
    monkeypatch.setattr(
        "backend.content.extractor.trafilatura.extract",
        lambda *args, **kwargs: '{"title": "Example Post", "text": "Hello world"}',
    )

    result = _do_extract("https://example.com/base", ContentExtractorConfig())

    assert result.status == "no_text" or result.status == "success"
    assert result.url == "https://example.com/post/123"
    assert result.article is not None
    assert result.article.url == "https://example.com/post/123"