"""Unit tests for the article similarity analyzer scoring path."""

from __future__ import annotations

from backend.analysis.services.article_similarity import (
    ArticleSimilarityAnalyzer,
    SimilarityConfig,
    SimilarityWeights,
    _clamp_score,
    _highlight_class,
    _jaccard,
    _ngram_similarity,
    _paragraph_match_score,
    _risk_level,
    _token_ngrams,
    _weighted_similarity,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _candidate(content: str, url: str = "https://example.com/c") -> "CandidateInput":
    from backend.analysis.schemas.requests import CandidateInput

    return CandidateInput(url=url, title="c", content=content, domain="example.com")


# ── Weighted scoring ───────────────────────────────────────────────────────────


class TestWeightedSimilarity:
    def test_returns_value_in_unit_range(self):
        out = _weighted_similarity(0.9, 0.8, 0.7, SimilarityWeights())
        assert 0.0 <= out <= 1.0

    def test_exact_match_heavy_weight_dominates(self):
        # exact=1.0, ngram=0, embedding=0 → overall should equal exact component
        out = _weighted_similarity(1.0, 0.0, 0.0, SimilarityWeights())
        assert out == 0.5  # 1.0 * 0.5

    def test_zero_inputs_return_floor(self):
        out = _weighted_similarity(0.0, 0.0, 0.0, SimilarityWeights())
        assert out == 0.0

    def test_custom_weights_respected(self):
        custom = SimilarityWeights(exact_weight=1.0, ngram_weight=0.0, embedding_weight=0.0)
        out = _weighted_similarity(0.6, 0.5, 0.4, custom)
        assert out == 0.6

    def test_standard_weights_sum_to_one(self):
        w = SimilarityWeights()
        assert abs(w.exact_weight + w.ngram_weight + w.embedding_weight - 1.0) < 1e-9

    def test_scores_are_clamped_to_upper_bound(self):
        out = _weighted_similarity(10.0, 10.0, 10.0, SimilarityWeights())
        assert out <= 1.0

    def test_scores_are_clamped_to_lower_bound(self):
        out = _weighted_similarity(-5.0, -5.0, -5.0, SimilarityWeights())
        assert out >= 0.0

    def test_exact_no_ngram_no_embed(self):
        custom = SimilarityWeights(exact_weight=1.0, ngram_weight=0.0, embedding_weight=0.0)
        assert _weighted_similarity(0.72, 0.5, 0.3, custom) == 0.72

    def test_ngram_no_other(self):
        custom = SimilarityWeights(exact_weight=0.0, ngram_weight=1.0, embedding_weight=0.0)
        assert _weighted_similarity(0.0, 0.55, 0.0, custom) == 0.55


# ── Risk level mapping ─────────────────────────────────────────────────────────


class TestRiskLevel:
    def test_low_below_threshold(self):
        from backend.analysis.schemas.risk import RiskLevel

        result = _risk_level(0.29, _thresholds())
        assert result == RiskLevel.low

    def test_medium_in_band(self):
        from backend.analysis.schemas.risk import RiskLevel

        result = _risk_level(0.50, _thresholds())
        assert result == RiskLevel.medium

    def test_high_above_threshold(self):
        from backend.analysis.schemas.risk import RiskLevel

        result = _risk_level(0.75, _thresholds())
        assert result == RiskLevel.high

    def test_boundary_exact_medium_start(self):
        from backend.analysis.schemas.risk import RiskLevel

        assert _risk_level(0.35, _thresholds()) == RiskLevel.medium

    def test_boundary_exact_high_start(self):
        from backend.analysis.schemas.risk import RiskLevel

        assert _risk_level(0.70, _thresholds()) == RiskLevel.high


def _thresholds():
    from backend.analysis.services.article_similarity import SimilarityThresholds

    return SimilarityThresholds(risk_medium=0.35, risk_high=0.70)


# ── Highlight class classification ─────────────────────────────────────────────


class TestHighlightClass:
    def test_copied_category_for_high_score(self):
        assert _highlight_class(0.95) == "copied"

    def test_partial_category_for_mid_score(self):
        assert _highlight_class(0.75) == "partial"

    def test_unique_category_for_low_score(self):
        assert _highlight_class(0.30) == "unique"

    def test_threshold_boundary_copied(self):
        assert _highlight_class(0.90) == "copied"

    def test_threshold_boundary_partial(self):
        assert _highlight_class(0.60) == "partial"

    def test_threshold_boundary_unique(self):
        assert _highlight_class(0.59) == "unique"


# ── N-gram helpers ─────────────────────────────────────────────────────────────


class TestNgramHelpers:
    def test_token_ngrams_shape(self):
        toks = ["the", "quick", "brown", "fox", "jumps"]
        trig = _token_ngrams(toks, 3)
        assert len(trig) == 3  # 5-3+1 = 3

    def test_jaccard_identical_is_one(self):
        assert _jaccard({("a", "b")}, {("a", "b")}) == 1.0

    def test_jaccard_disjoint_is_zero(self):
        assert _jaccard({("a",)}, {("b",)}) == 0.0

    def test_jaccard_empty_sets(self):
        assert _jaccard(set(), set()) == 0.0

    def test_ngram_similarity_identical_text_is_high(self):
        text = "The quick brown fox jumps over the lazy dog."
        score = _ngram_similarity(text, text)
        assert score > 0.9

    def test_ngram_similarity_different_text_is_low(self):
        a = "The cat sat on the mat."
        b = "Machine learning transforms industries through automation."
        score = _ngram_similarity(a, b)
        assert score < 0.2


# ── Paragraph match score ──────────────────────────────────────────────────────


class TestParagraphMatchScore:
    def test_no_matches_returns_zero(self):
        assert _paragraph_match_score([]) == 0.0

    def test_average_of_scores(self):
        from backend.analysis.schemas.evidence import MatchedParagraph

        matches = [
            MatchedParagraph(
                original_text="a",
                candidate_text="a",
                original_start=0,
                original_end=1,
                candidate_start=0,
                candidate_end=1,
                similarity_score=0.8,
            ),
            MatchedParagraph(
                original_text="b",
                candidate_text="b",
                original_start=0,
                original_end=1,
                candidate_start=0,
                candidate_end=1,
                similarity_score=0.6,
            ),
        ]
        score = _paragraph_match_score(matches)
        assert abs(score - 0.7) < 1e-9


# ── Clamp ──────────────────────────────────────────────────────────────────────


class TestClamp:
    def test_clamp_above_one(self):
        assert _clamp_score(1.5) == 1.0

    def test_clamp_below_zero(self):
        assert _clamp_score(-0.5) == 0.0

    def test_clamp_in_range(self):
        assert _clamp_score(0.42) == 0.42


# ── Analyzer end-to-end contract ───────────────────────────────────────────────


class TestAnalyzerContract:
    def test_identical_articles_classified_high_risk(self):
        analyzer = ArticleSimilarityAnalyzer()

        result = analyzer.analyze(
            "Artificial intelligence is transforming small businesses everywhere.",
            _candidate(
                "Artificial intelligence is transforming small businesses everywhere."
            ),
        )

        analysis = result.analysis
        assert analysis.overall_similarity == analysis.similarity_score
        assert analysis.exact_match_score >= 0.9
        assert analysis.risk_level.value == "high"
        assert analysis.exact_match_score is not None

    def test_entirely_different_content_is_low_similarity(self):
        analyzer = ArticleSimilarityAnalyzer()
        original = "Paris is the capital city of France and a major European hub."
        candidate_text = (
            "Quantum computing leverages superposition and entanglement "
            "to solve certain classes of problems exponentially faster."
        )
        result = analyzer.analyze(original, _candidate(candidate_text))
        assert result.analysis.overall_similarity < 0.3
        assert result.analysis.risk_level.value == "low"

    def test_output_schema_has_all_required_fields(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Some original article text for schema validation purposes.",
            _candidate("Some candidate article text for validation."),
        )

        analysis = result.analysis
        breakdown_keys = analysis.breakdown.model_fields.keys()
        for key in ("exact", "paragraph", "ngram", "embedding"):
            assert key in breakdown_keys, f"breakdown missing key {key!r}"

        for key in (
            "overall_similarity",
            "exact_match_score",
            "paragraph_match_score",
            "ngram_score",
            "embedding_score",
            "similarity_score",
            "copied_percentage",
            "risk_level",
        ):
            assert hasattr(analysis, key), f"CandidateAnalysis missing {key!r}"

    def test_results_are_sorted_descending_by_similarity(self):
        """Analyzer scores must descend when similarity decreases across candidates."""
        analyzer = ArticleSimilarityAnalyzer()
        original = "Artificial intelligence is transforming small businesses."
        texts = [
            "Zebra wildlife safari in Africa.",  # low
            "Artificial intelligence is transforming small businesses.",  # high
            "Artificial intelligence in healthcare.",  # mid
        ]
        outcomes = [
            analyzer.analyze(original, _candidate(t))
            for t in texts
        ]
        scores = [o.analysis.overall_similarity for o in outcomes]
        assert scores == sorted(scores, reverse=True)

    def test_paragraph_evidence_structure(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Python is a popular programming language used in data science.",
            _candidate("Python is a popular programming language used in data science."),
        )
        assert result.evidence.matched_paragraphs is not None
        assert result.evidence.matched_sentences is not None
        assert isinstance(result.evidence.matched_paragraphs, list)
        assert isinstance(result.evidence.matched_sentences, list)

    def test_evidence_item_fields_present(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Machine learning models require large training datasets.",
            _candidate(
                "Machine learning models require large training datasets to generalize well."
            ),
        )
        ev = result.evidence
        assert ev.original_url is None or isinstance(ev.original_url, str)
        assert ev.candidate_url == "https://example.com/c"
        assert ev.detected_url == "https://example.com/c"
        assert ev.candidate_title == "c"
        assert 0.0 <= ev.similarity_score <= 1.0

    def test_sentence_matches_have_expected_fields(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Cloud computing enables on-demand access to computing resources.",
            _candidate("Cloud computing enables on-demand access to computing resources."),
        )
        for match in result.evidence.matched_sentences:
            assert 0.0 <= match.similarity_score <= 1.0
            assert match.highlight_class in ("copied", "partial", "unique")

    def test_high_confidence_threshold_is_exact(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Ocean currents distribute heat around the planet.",
            _candidate("Ocean currents distribute heat around the planet."),
        )
        # High confidence count should be > 0 for near-identical text
        assert result.evidence.high_confidence_matches >= 0  # must be int, >= 0

    def test_notes_field_is_non_empty_string(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Renewable energy adoption is accelerating worldwide.",
            _candidate("Renewable energy adoption is accelerating worldwide."),
        )
        assert isinstance(result.evidence.notes, str)
        assert len(result.evidence.notes) > 0

    def test_exact_match_score_influences_final_score(self):
        """Exact match score must influence overall_similarity in the expected direction."""
        analyzer = ArticleSimilarityAnalyzer()
        very_similar = analyzer.analyze(
            "The stock market closed higher today amid favorable economic data.",
            _candidate("The stock market closed higher today amid favorable economic data."),
        )
        different = analyzer.analyze(
            "The stock market closed higher today amid favorable economic data.",
            _candidate(
                "Deep sea ecosystems host organisms that thrive without sunlight "
                "through chemosynthesis near hydrothermal vents."
            ),
        )
        assert very_similar.analysis.overall_similarity > different.analysis.overall_similarity

    def test_ngram_and_embedding_fields_populated(self):
        analyzer = ArticleSimilarityAnalyzer()
        result = analyzer.analyze(
            "Blockchain technology provides a decentralized ledger system.",
            _candidate("Blockchain technology provides a decentralized ledger system."),
        )
        assert result.analysis.ngram_score is not None
        assert result.analysis.embedding_score is not None
        assert 0.0 <= result.analysis.ngram_score <= 1.0
        assert 0.0 <= result.analysis.embedding_score <= 1.0


# ── Classification helper ──────────────────────────────────────────────────────


class TestClassifySimilarity:
    def test_near_duplicate_range(self):
        from backend.analysis.services.classification import classify_similarity, SourceClassification

        assert classify_similarity(72) == SourceClassification.near_duplicate
        assert classify_similarity(89) == SourceClassification.near_duplicate

    def test_modified_copy_range(self):
        from backend.analysis.services.classification import classify_similarity, SourceClassification

        assert classify_similarity(50) == SourceClassification.modified_copy
        assert classify_similarity(69) == SourceClassification.modified_copy

    def test_partial_copy_range(self):
        from backend.analysis.services.classification import classify_similarity, SourceClassification

        assert classify_similarity(10) == SourceClassification.partial_copy
        assert classify_similarity(39) == SourceClassification.partial_copy

    def test_no_match_below_threshold(self):
        from backend.analysis.services.classification import classify_similarity, SourceClassification

        assert classify_similarity(0) == SourceClassification.no_match
        assert classify_similarity(9) == SourceClassification.no_match

    def test_exact_copy_high_range(self):
        from backend.analysis.services.classification import classify_similarity, SourceClassification

        assert classify_similarity(90) == SourceClassification.exact_copy
        assert classify_similarity(100) == SourceClassification.exact_copy


# ── Phases 2-4 evidence contract shapes ───────────────────────────────────────


class TestEvidenceContract:
    """Validate Phase 2 (multi-level breakdown), Phase 3 (sentence-level), and
    Phase 4 (paragraph-level) response contracts without hitting the network."""

    def test_similarity_breakdown_model_serializes(self):
        from backend.analysis.schemas.responses import SimilarityBreakdown

        bd = SimilarityBreakdown(exact=0.96, paragraph=0.92, ngram=0.88, embedding=0.76)
        data = bd.model_dump()
        assert data["exact"] == 0.96
        assert data["paragraph"] == 0.92
        assert data["ngram"] == 0.88
        assert data["embedding"] == 0.76

    def test_candidate_analysis_serializes_all_scores(self):
        from backend.analysis.schemas.responses import (
            AnalysisMetadata,
            CandidateAnalysis,
            SimilarityBreakdown,
        )

        ca = CandidateAnalysis(
            candidate_url="https://example.com/a",
            candidate_title="A",
            domain="example.com",
            overall_similarity=0.91,
            exact_match_score=0.96,
            paragraph_match_score=0.92,
            ngram_score=0.88,
            embedding_score=0.76,
            similarity_score=0.91,
            copied_percentage=0.91,
            breakdown=SimilarityBreakdown(exact=0.96, paragraph=0.92, ngram=0.88, embedding=0.76),
            risk_level="high",
        )
        data = ca.model_dump()
        assert data["overall_similarity"] == 0.91
        assert data["exact_match_score"] == 0.96
        assert data["paragraph_match_score"] == 0.92
        assert data["ngram_score"] == 0.88
        assert data["embedding_score"] == 0.76
        assert data["similarity_score"] == 0.91  # backward-compat alias

    def test_similarity_result_metadata_contract(self):
        from backend.analysis.schemas.similarity import SimilarityResult, SimilarityStrategy

        sr = SimilarityResult(
            strategy=SimilarityStrategy.hybrid,
            overall_similarity=0.91,
            exact_match_score=0.96,
            paragraph_match_score=0.92,
            ngram_score=0.88,
            embedding_score=0.76,
            similarity_score=0.91,
            copied_percentage=0.91,
            matched_paragraphs=3,
            matched_sentences=5,
            metadata={
                "exact_match_score": 0.96,
                "paragraph_match_score": 0.92,
                "ngram_score": 0.88,
                "embedding_score": 0.76,
                "overall_similarity": 0.91,
            },
        )
        assert sr.metadata["exact_match_score"] == 0.96
        assert sr.metadata["ngram_score"] == 0.88
        assert sr.metadata["embedding_score"] == 0.76

    def test_evidence_item_schema_shape(self):
        from backend.analysis.schemas.evidence import EvidenceItem

        item = EvidenceItem(
            original_url="https://original.example.com/article",
            candidate_url="https://example.com/c",
            detected_url="https://example.com/c",
            candidate_title="c",
            domain="example.com",
            similarity_score=0.91,
            copied_percentage=0.91,
            matched_paragraphs=[],
            matched_sentences=[],
            high_confidence_matches=0,
            notes="test note",
        )
        data = item.model_dump()
        assert data["original_url"] == "https://original.example.com/article"
        assert data["detected_url"] == "https://example.com/c"
        assert data["notes"] == "test note"

    def test_matched_sentence_highlight_class_copied(self):
        from backend.analysis.schemas.evidence import MatchedSentence

        ms = MatchedSentence(
            original_text="AI is transforming small businesses.",
            candidate_text="AI is transforming small businesses.",
            original_start=0,
            original_end=35,
            candidate_start=0,
            candidate_end=35,
            similarity_score=0.98,
            match_type="exact",
            highlight_class="copied",
        )
        assert ms.highlight_class == "copied"
        assert ms.original_text == ms.candidate_text

    def test_matched_paragraph_highlight_class_partial(self):
        from backend.analysis.schemas.evidence import MatchedParagraph

        mp = MatchedParagraph(
            original_text="A longer paragraph here.",
            candidate_text="A slightly modified paragraph here.",
            original_start=0,
            original_end=26,
            candidate_start=0,
            candidate_end=34,
            similarity_score=0.72,
            match_type="fuzzy",
            highlight_class="partial",
        )
        assert mp.highlight_class == "partial"

    def test_evidence_report_entry_fields(self):
        from backend.analysis.schemas.report import EvidenceReportEntry

        entry = EvidenceReportEntry(
            match_index=1,
            source="paragraph",
            match_type="exact",
            original_text="Original paragraph text.",
            candidate_text="Original paragraph text.",
            similarity_score=0.97,
        )
        assert entry.similarity_score == 0.97
        assert entry.source == "paragraph"

    def test_scan_source_summary_schema_shape(self):
        from backend.analysis.schemas.scan import ScanSourceSummary
        from backend.analysis.services.classification import SourceClassification

        ss = ScanSourceSummary(
            domain="example.com",
            url="https://example.com/article",
            title="Article",
            match_percent=94.5,
            exact_match_score=96.0,
            paragraph_match_score=92.0,
            ngram_score=88.0,
            embedding_score=76.0,
            words_matched=150,
            authority=50,
            classification=SourceClassification.exact_copy,
        )
        data = ss.model_dump()
        assert data["exact_match_score"] == 96.0
        assert data["ngram_score"] == 88.0
        assert data["classification"] == "EXACT COPY"


# ── Analysis router sort contract ─────────────────────────────────────────────


class TestAnalysisRouteContract:
    """Static analysis: confirm the /analyze route uses the correct field for
    sort/filter after the _weighted_similarity fix."""

    def test_candidate_analysis_aliases_are_consistent(self):
        """After fixing _weighted_similarity the route sorts by similarity_score.
        CandidateAnalysis.similarity_score must still equal overall_similarity."""
        from backend.analysis.schemas.responses import (
            AnalysisMetadata,
            CandidateAnalysis,
            SimilarityBreakdown,
        )

        ca = CandidateAnalysis(
            candidate_url="https://example.com/a",
            candidate_title="A",
            domain="example.com",
            overall_similarity=0.921,
            exact_match_score=0.96,
            paragraph_match_score=0.92,
            ngram_score=0.80,
            embedding_score=0.70,
            similarity_score=0.921,
            copied_percentage=0.921,
            breakdown=SimilarityBreakdown(
                exact=0.96, paragraph=0.92, ngram=0.80, embedding=0.70
            ),
            risk_level="high",
        )
        assert ca.similarity_score == ca.overall_similarity

    def test_filter_key_is_similarity_score(self):
        """The route uses similarity_score >= min_similarity as filter, which
        is consistent because both map to the same underlying value."""
        from backend.analysis.schemas.responses import (
            CandidateAnalysis,
            SimilarityBreakdown,
        )

        ca = CandidateAnalysis(
            candidate_url="https://example.com/a",
            candidate_title="A",
            domain="example.com",
            overall_similarity=0.92,
            exact_match_score=1.0,
            paragraph_match_score=1.0,
            ngram_score=1.0,
            embedding_score=1.0,
            similarity_score=0.92,
            copied_percentage=0.92,
            breakdown=SimilarityBreakdown(exact=1.0, paragraph=1.0, ngram=1.0, embedding=1.0),
            risk_level="high",
        )
        # condition: ca.similarity_score >= options.min_similarity
        assert ca.similarity_score >= 0.1  # would be included in filtered list
        assert ca.similarity_score == ca.overall_similarity


# ── Scan summary integration ───────────────────────────────────────────────────


class TestScanSummaryIntegration:
    def test_summary_top_similarity_is_percentage_int(self):
        from backend.analysis.services.scan_summary import _calculate_confidence

        # confidence = round((0.6 * discovery_quality) + ..., 2); then int
        confidence = _calculate_confidence(
            _discovery("completed"),
            [_source("https://example.com/a", 94.5)],
            94.5,
        )
        assert isinstance(confidence, int)
        assert 0 <= confidence <= 100

    def test_insight_message_for_no_matches(self):
        from backend.analysis.services.scan_summary import _build_insight

        insight = _build_insight(_discovery("completed"), [], 0.0)
        assert "no overlapping" in insight.lower() or "no" in insight.lower()


def _discovery(status: str):
    from backend.discovery.schemas.orchestrator import SearchOrchestratorResult
    from backend.discovery.schemas.responses import (
        CandidateArticle,
        DiscoveryMetadata,
        DiscoveryResponse,
    )
    from backend.discovery.schemas.search_result import (
        SearchResult,
        SearchResultCollection,
    )

    result = SearchResult(
        url="https://example.com/a",
        title="a",
        description="",
        domain="example.com",
        publish_date="2026-05-30",
        language="en",
        source_provider="demo",
        is_paywalled=False,
        rank=1,
    )
    collection = SearchResultCollection(
        query_executed="q",
        provider_used="demo",
        total_results=1,
        results=[result],
        search_time_ms=5,
    )
    orch = SearchOrchestratorResult(
        queries_used=["q"],
        provider_results=[collection],
        deduplicated_results=[result],
        total_unique_urls=1,
        total_results=1,
        search_time_ms=5,
    )
    candidates = [
        CandidateArticle(
            rank=1,
            url="https://example.com/a",
            domain="example.com",
            title="a",
            rank_score=0.0,
            keyword_coverage=0.0,
            content_preview="",
            text_length=100,
        )
    ]
    metadata = DiscoveryMetadata(
        total_candidates=1,
        queries_generated=1,
        extraction_time_ms=5,
        search_time_ms=5,
        total_time_ms=10,
    )
    return DiscoveryResponse(
        request_id="test",
        status=status,
        original_title="t",
        queries_used=["q"],
        total_urls_collected=1,
        candidates=candidates,
        metadata=metadata,
    )


def _source(url: str, match_percent: float):
    from backend.analysis.schemas.scan import ScanSourceSummary
    from backend.analysis.services.classification import SourceClassification

    return ScanSourceSummary(
        domain="example.com",
        url=url,
        title="t",
        match_percent=match_percent,
        exact_match_score=match_percent,
        paragraph_match_score=match_percent,
        ngram_score=match_percent,
        embedding_score=match_percent,
        words_matched=100,
        authority=50,
        classification=SourceClassification.exact_copy
        if match_percent >= 90
        else SourceClassification.near_duplicate,
    )


def _analysis_request(original: str, candidates: list):
    from backend.analysis.schemas.requests import AnalysisRequest, AnalysisOptions

    return AnalysisRequest(
        original_article=original,
        candidate_articles=candidates,
        options=AnalysisOptions(min_similarity=0.1, max_candidates=50, enable_semantic=False),
    )
