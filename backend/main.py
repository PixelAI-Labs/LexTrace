"""
CopyGuard Backend — FastAPI Application Entry Point.

Discovery Service  —  AI-Powered Article Piracy Detection
Tech stack: FastAPI · Python 3.11+ · Google Custom Search API · Trafilatura
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.config import Settings, settings
from backend.discovery.schemas.requests import DiscoveryRequest
from backend.discovery.schemas.responses import (
    DiscoveryMetadata,
    DiscoveryResponse,
)
from backend.discovery.services.candidate_collector import (
    CandidateCollector,
    CollectorConfig,
)
from backend.discovery.services.search_orchestrator import (
    SearchOrchestrator,
    build_orchestrator_config,
)

# ── Phase 8: Analysis Service ─────────────────────────────────────────────────
from backend.analysis.schemas.dmca import DmcaNotice, DmcaRequest
from backend.analysis.schemas.report import EvidenceReport, ReportFormat
from backend.analysis.schemas.requests import AnalysisOptions, AnalysisRequest, CandidateInput
from backend.analysis.schemas.responses import AnalysisResponse
from backend.analysis.schemas.scan import ScanSummary
from backend.analysis.services.article_similarity import ArticleSimilarityAnalyzer
from backend.analysis.services.dependencies import (
    get_analyzer,
    get_dmca_generator,
    get_report_generator,
    get_risk_service,
)
from backend.analysis.services.dmca_generator import DmcaGeneratorService
from backend.analysis.services.evidence_report import EvidenceReportGenerator
from backend.analysis.services.risk_assessment import RiskAssessmentService
from backend.analysis.services.scan_summary import build_scan_summary
from backend.api.router import router as analysis_router
from backend.api.v1.analyze import analyze as analyze_candidates

logger = logging.getLogger("backend.main")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    logger.info("CopyGuard Backend starting — version 0.1.0")
    logger.info(f"Config (redacted): {settings.to_public_dict()}")
    yield
    logger.info("CopyGuard Backend shutting down")


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------

def _build_settings() -> Settings:
    """Return the application settings singleton."""
    return settings


def build_search_orchestrator(
    settings_obj: Annotated[Settings, Depends(_build_settings)],
) -> SearchOrchestrator:
    """Build a SearchOrchestrator instance from settings."""
    return SearchOrchestrator(settings_obj=settings_obj)


def build_candidate_collector(
    settings_obj: Annotated[Settings, Depends(_build_settings)],
) -> CandidateCollector:
    """Build a CandidateCollector instance from settings."""
    cfg = CollectorConfig.from_settings(settings_obj)
    return CandidateCollector(config=cfg)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CopyGuard API",
    description=(
        "AI-Powered Article Piracy Detection — "
        "Discovery, Similarity Analysis, Risk Assessment & DMCA Generation"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Phase 8: mount analysis routes (/api/v1/analyze, /api/v1/report, /api/v1/dmca)
app.include_router(analysis_router)


# ---------------------------------------------------------------------------
# Discovery endpoint
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/discover",
    response_model=DiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover suspected article copies",
    tags=["discovery"],
    response_description=(
        "Ranked list of candidate articles suspected of being infringing copies "
        "of the submitted article."
    ),
)
async def discover(
    req: DiscoveryRequest,
    orchestrator: Annotated[SearchOrchestrator, Depends(build_search_orchestrator)],
    collector: Annotated[CandidateCollector, Depends(build_candidate_collector)],
) -> DiscoveryResponse:
    """
    Discover suspected pirated copies of an article.

    Accepts raw article text (and optionally a title or source URL),
    generates targeted search queries, and returns a ranked list of
    candidate articles suspected of being infringing copies.
    """
    total_start_ms = int(time.perf_counter() * 1000)
    request_id = str(uuid.uuid4())

    # ── 1. Orchestrate search ─────────────────────────────────────────────
    orchestrator_config = build_orchestrator_config(
        settings_obj=settings,
        max_candidates=req.options.max_candidates,
        search_depth=req.options.search_depth,
    )

    try:
        orchestrator_result = await orchestrator.run(
            article_text=req.article_text,
            title=req.title,
            config=orchestrator_config,
        )
    except Exception as exc:
        logger.exception("SearchOrchestrator.run() failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search orchestration failed. Please retry.",
        ) from exc

    search_time_ms = orchestrator_result.search_time_ms

    # ── 2. Collect and extract candidates ─────────────────────────────────
    extraction_time_ms = 0
    candidates: list = []
    queries_used = orchestrator_result.queries_used
    total_urls_collected = orchestrator_result.total_unique_urls

    if req.options.include_content:
        try:
            collection_result = await collector.collect(orchestrator_result)
        except Exception as exc:
            logger.exception("CandidateCollector.collect() failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Content extraction failed. Please retry.",
            ) from exc

        candidates = collection_result.candidates
        extraction_time_ms = collection_result.statistics.extraction_time_ms
    else:
        collection_result = None

    total_time_ms = int(time.perf_counter() * 1000) - total_start_ms

    # ── 3. Determine overall status ────────────────────────────────────────
    stats = collection_result.statistics if collection_result else None
    if candidates:
        discovery_status: str = "completed"
    elif stats and (stats.failed_extractions > 0 or stats.empty_extractions > 0):
        discovery_status = "partial"
    elif total_urls_collected == 0:
        discovery_status = "failed"
    else:
        discovery_status = "completed"

    return DiscoveryResponse(
        request_id=request_id,
        status=discovery_status,
        original_title=req.title,
        queries_used=queries_used,
        total_urls_collected=total_urls_collected,
        candidates=candidates,
        metadata=DiscoveryMetadata(
            total_candidates=len(candidates),
            queries_generated=len(queries_used),
            extraction_time_ms=extraction_time_ms,
            search_time_ms=search_time_ms,
            total_time_ms=total_time_ms,
        ),
    )


# ---------------------------------------------------------------------------
# Scan endpoint (discovery -> analysis -> report -> dmca)
# ---------------------------------------------------------------------------

class ScanRequest(DiscoveryRequest):
    """POST /scan request body."""

    analysis_options: AnalysisOptions = Field(
        default_factory=AnalysisOptions,
        description="Analysis tuning options. Safe to omit.",
    )
    report_format: ReportFormat = Field(
        default=ReportFormat.text,
        description="Desired evidence report output format.",
    )
    dmca_request: DmcaRequest | None = Field(
        default=None,
        description="Optional DMCA notice inputs. When provided, a notice is generated.",
    )


class ScanResponse(BaseModel):
    """POST /scan response body."""

    discovery: DiscoveryResponse = Field(..., description="Discovery results.")
    analysis: AnalysisResponse = Field(..., description="Similarity, evidence, and risk outputs.")
    summary: ScanSummary = Field(
        ...,
        description="Canonical scan summary used by the frontend for similarity, confidence, and source grouping.",
    )
    report: EvidenceReport | None = Field(
        default=None,
        description="Generated evidence report for the top candidate.",
    )
    dmca_notice: DmcaNotice | None = Field(
        default=None,
        description="Generated DMCA notice when dmca_request is provided.",
    )


@app.post(
    "/api/v1/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Run discovery + analysis + report in one call",
    tags=["scan"],
)
async def scan(
    req: ScanRequest,
    orchestrator: Annotated[SearchOrchestrator, Depends(build_search_orchestrator)],
    collector: Annotated[CandidateCollector, Depends(build_candidate_collector)],
    analyzer: Annotated[ArticleSimilarityAnalyzer, Depends(get_analyzer)],
    risk_service: Annotated[RiskAssessmentService, Depends(get_risk_service)],
    report_generator: Annotated[EvidenceReportGenerator, Depends(get_report_generator)],
    dmca_generator: Annotated[DmcaGeneratorService, Depends(get_dmca_generator)],
) -> ScanResponse:
    print("--- DEBUG START ---", flush=True)
    print(f"1. Received Input Content: {req.article_text[:100]}...", flush=True)

    discovery_options = req.options.model_copy(update={"include_content": True})
    discovery_request = DiscoveryRequest(
        article_text=req.article_text,
        title=req.title,
        source_url=req.source_url,
        options=discovery_options,
    )
    discovery_response = await discover(
        discovery_request,
        orchestrator,
        collector,
    )

    print(
        f"2. Discovered Candidates Count: {len(discovery_response.candidates)} "
        f"(urls collected: {discovery_response.total_urls_collected})",
        flush=True,
    )
    if discovery_response.candidates:
        preview = discovery_response.candidates[0]
        print(
            f"   First candidate: url={preview.url!r} content_len={len(preview.content or '')}",
            flush=True,
        )

    candidate_inputs = [
        CandidateInput(
            url=candidate.url,
            title=candidate.title,
            content=candidate.content,
            domain=candidate.domain,
        )
        for candidate in discovery_response.candidates
        if candidate.content
    ]

    print(f"   Candidate inputs with content: {len(candidate_inputs)}", flush=True)

    if candidate_inputs:
        analysis_request = AnalysisRequest(
            original_article=req.article_text,
            original_url=req.source_url,
            candidate_articles=candidate_inputs,
            options=req.analysis_options,
        )
        analysis_response = analyze_candidates(
            analysis_request,
            analyzer,
            risk_service,
        )
    else:
        analysis_response = AnalysisResponse(
            results=[],
            evidence=None,
            risk_assessment=None,
        )

    print(
        f"3. Analysis Engine Output: results={len(analysis_response.results)} "
        f"top_similarity="
        f"{max((r.similarity_score for r in analysis_response.results), default=0.0):.3f}",
        flush=True,
    )
    print("--- DEBUG END ---", flush=True)

    summary = build_scan_summary(
        original_article=req.article_text,
        discovery=discovery_response,
        analysis=analysis_response,
    )

    report = None
    dmca_notice = None
    if (
        analysis_response.results
        and analysis_response.risk_assessment
        and analysis_response.evidence
    ):
        top_candidate = max(
            analysis_response.results,
            key=lambda item: item.similarity_score,
        )
        report = report_generator.generate(
            top_candidate,
            analysis_response.evidence,
            analysis_response.risk_assessment,
            report_format=req.report_format,
        )
        if req.dmca_request:
            dmca_notice = dmca_generator.generate(
                req.dmca_request,
                analysis_response.risk_assessment,
                analysis_response.evidence,
                analysis=top_candidate,
            )

    return ScanResponse(
        discovery=discovery_response,
        analysis=analysis_response,
        summary=summary,
        report=report,
        dmca_notice=dmca_notice,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/health",
    summary="Service health check",
    tags=["health"],
)
async def health():
    """Lightweight health check returning dependency status."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "CopyGuard",
        "dependencies": {
            "google_search": (
                "configured"
                if settings.google.api_key
                else "missing_api_key"
            ),
            "content_extraction": "ok",
            "analysis_service": "ok",
        },
    }


# ---------------------------------------------------------------------------
# Legacy stub endpoints (replaced in later phases)
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    article_text: str


class DMCARequest(BaseModel):
    evidence_id: str


class _DMCAReportRequest(BaseModel):
    url: str
    evidence_id: str


@app.post("/scan", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def start_scan(req: ScanRequest):
    return {"detail": "Not implemented — use POST /api/v1/discover"}


@app.get("/scan/{scan_id}/progress", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def scan_progress(scan_id: str):
    return {"detail": "Not implemented"}


@app.get("/scan/{scan_id}/candidates", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def scan_candidates(scan_id: str):
    return {"detail": "Not implemented"}


@app.get("/scan/{scan_id}/results", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def scan_results(scan_id: str):
    return {"detail": "Not implemented"}


@app.get("/report/{report_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def get_report(report_id: str):
    return {"detail": "Not implemented"}


@app.post("/dmca/generate", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def generate_dmca(req: DMCARequest):
    return {"detail": "Not implemented — use POST /api/v1/dmca"}


@app.post("/api/v1/dmca/report", status_code=status.HTTP_501_NOT_IMPLEMENTED, tags=["legacy"])
async def create_dmca_report(req: _DMCAReportRequest):
    """Replaced by POST /api/v1/dmca (Phase 8)."""
    return {"detail": "Not implemented — use POST /api/v1/dmca"}


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"X-Request-ID": request.headers.get("X-Request-ID", "")},
    )


@app.exception_handler(Exception)
async def uncaught_exception_handler(request, exc: Exception):
    logger.exception("Uncaught exception in request %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
        headers={"X-Request-ID": request.headers.get("X-Request-ID", "")},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.reload,
    )