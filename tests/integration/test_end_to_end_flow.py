"""Integration validation for the discovery -> analysis -> report -> dmca flow."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.discovery.schemas.candidate_collection import (
    CandidateCollectionResult,
    CollectionStatistics,
)
from backend.discovery.schemas.orchestrator import SearchOrchestratorResult
from backend.discovery.schemas.responses import CandidateArticle
from backend.discovery.schemas.search_result import SearchResult, SearchResultCollection
from backend.main import app, build_candidate_collector, build_search_orchestrator


ORIGINAL_TEXT = (
    "In 2026, local newsrooms are experimenting with small language models to speed up "
    "fact checking and source tracking. A typical workflow starts with a reporter drafting "
    "a story, then an editor runs the draft through a verification checklist that flags "
    "claims and missing citations."
)

COPIED_TEXT = (
    "In 2026, local newsrooms are experimenting with small language models to speed up "
    "fact checking and source tracking. A typical workflow starts with a reporter drafting "
    "a story, then an editor runs the draft through a verification checklist that flags "
    "claims and missing citations."
)


class FakeSearchOrchestrator:
    """Return a single deterministic search result."""

    async def run(self, article_text: str, *, title: str | None = None, config=None):
        result = SearchResult(
            url="https://example.com/copied",
            title="Copied Demo Article",
            description="A copied demo article.",
            domain="example.com",
            publish_date="2026-05-30",
            language="en",
            source_provider="demo",
            is_paywalled=False,
            rank=1,
        )
        collection = SearchResultCollection(
            query_executed="demo query",
            provider_used="demo",
            total_results=1,
            results=[result],
            search_time_ms=5,
        )
        return SearchOrchestratorResult(
            queries_used=["demo query"],
            provider_results=[collection],
            deduplicated_results=[result],
            total_unique_urls=1,
            total_results=1,
            search_time_ms=5,
        )


class FakeCandidateCollector:
    """Return a single deterministic candidate with content."""

    async def collect(self, orchestrator_result: SearchOrchestratorResult):
        candidate = CandidateArticle(
            rank=1,
            url="https://example.com/copied",
            domain="example.com",
            title="Copied Demo Article",
            rank_score=0.0,
            keyword_coverage=0.0,
            content_preview=COPIED_TEXT[:120],
            content=COPIED_TEXT,
            text_length=len(COPIED_TEXT.split()),
            publish_date="2026-05-30",
            language="en",
        )
        stats = CollectionStatistics(
            total_urls=1,
            successful_extractions=1,
            failed_extractions=0,
            empty_extractions=0,
            extraction_time_ms=5,
        )
        return CandidateCollectionResult(
            candidates=[candidate],
            failures=[],
            statistics=stats,
            queries_used=orchestrator_result.queries_used,
            total_urls_collected=orchestrator_result.total_unique_urls,
        )


def test_TC8_5_end_to_end_flow():
    client = TestClient(app)
    app.dependency_overrides[build_search_orchestrator] = lambda: FakeSearchOrchestrator()
    app.dependency_overrides[build_candidate_collector] = lambda: FakeCandidateCollector()

    try:
        discovery_payload = {
            "article_text": ORIGINAL_TEXT * 2,
            "title": "Demo Article",
            "options": {
                "max_candidates": 3,
                "search_depth": "shallow",
                "include_content": True,
            },
        }
        discovery_response = client.post("/api/v1/discover", json=discovery_payload)
        assert discovery_response.status_code == 200
        discovery_data = discovery_response.json()
        assert discovery_data["candidates"]
        candidate = discovery_data["candidates"][0]
        assert candidate["content"]

        analysis_payload = {
            "original_article": ORIGINAL_TEXT * 2,
            "candidate_articles": [
                {
                    "url": candidate["url"],
                    "title": candidate["title"],
                    "content": candidate["content"],
                    "domain": candidate["domain"],
                }
            ],
            "options": {
                "min_similarity": 0.1,
                "max_candidates": 5,
                "enable_semantic": False,
            },
        }
        analysis_response = client.post("/api/v1/analyze", json=analysis_payload)
        assert analysis_response.status_code == 200
        analysis_data = analysis_response.json()
        assert analysis_data["results"]
        assert analysis_data["risk_assessment"]

        report_payload = {
            "analysis": analysis_data["results"][0],
            "evidence": analysis_data["evidence"],
            "assessment": analysis_data["risk_assessment"],
            "format": "text",
        }
        report_response = client.post("/api/v1/report", json=report_payload)
        assert report_response.status_code == 200
        report_data = report_response.json()
        assert report_data["content"]

        dmca_payload = {
            "dmca_request": {
                "creator_name": "Demo Publisher",
                "creator_email": "legal@example.com",
                "creator_address": "123 Demo Street, Test City, CA 90000",
                "original_url": "https://original.example.com/article",
                "infringing_url": candidate["url"],
            },
            "assessment": analysis_data["risk_assessment"],
            "evidence": analysis_data["evidence"],
            "analysis": analysis_data["results"][0],
            "template_name": "dmca_standard.txt",
        }
        dmca_response = client.post("/api/v1/dmca", json=dmca_payload)
        assert dmca_response.status_code == 200
        dmca_data = dmca_response.json()
        assert dmca_data["body"]

        scan_payload = {
            "article_text": ORIGINAL_TEXT * 2,
            "title": "Demo Article",
            "options": {
                "max_candidates": 3,
                "search_depth": "shallow",
                "include_content": True,
            },
            "analysis_options": {
                "min_similarity": 0.1,
                "max_candidates": 5,
                "enable_semantic": False,
            },
            "report_format": "text",
            "dmca_request": dmca_payload["dmca_request"],
        }
        scan_response = client.post("/api/v1/scan", json=scan_payload)
        assert scan_response.status_code == 200
        scan_data = scan_response.json()
        assert scan_data["discovery"]["candidates"]
        assert scan_data["analysis"]["results"]
        assert scan_data["report"]["content"]
        assert scan_data["dmca_notice"]["body"]
    finally:
        app.dependency_overrides.clear()
