"""
CopyGuard Backend — FastAPI Application Entry Point.

Discovery Service  —  AI-Powered Article Piracy Detection
Tech stack: FastAPI · Python 3.11+ · Google Custom Search API · Trafilatura
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.discovery.schemas.requests import DiscoveryRequest
from backend.discovery.schemas.responses import (
    CandidateArticle,
    DiscoveryMetadata,
    DiscoveryResponse,
)
from backend.discovery.services.query_generator import as_config


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Startup: log configuration (secrets redacted)
    import logging
    logger = logging.getLogger("backend.main")
    logger.info("CopyGuard Discovery Service starting — version 0.1.0")
    logger.info(f"Config (redacted): {settings.to_public_dict()}")
    yield
    # Shutdown
    logger.info("CopyGuard Discovery Service shutting down")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CopyGuard API",
    description="AI-Powered Article Piracy Detection — Discovery Service",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Discovery endpoint
# ---------------------------------------------------------------------------

@app.post("/api/v1/discover", response_model=DiscoveryResponse)
async def discover(req: DiscoveryRequest) -> DiscoveryResponse:
    """
    Discover suspected pirated copies of an article.

    Accepts raw article text (and optionally a title or source URL),
    generates targeted Google search queries, and returns a ranked
    list of candidate articles suspected of being infringing copies.
    """
    # Record timings
    total_start = time.perf_counter()

    # Build query generator config from settings
    config = as_config(
        max_queries=settings.discovery.max_queries_per_discovery,
        keyword_top_k=20,
    )

    # Generate search queries
    search_start = time.perf_counter()
    queries = _generate_queries(req, config)
    search_elapsed_ms = int((time.perf_counter() - search_start) * 1000)

    # TODO (Phase 3–5): Execute searches, extract content, rank candidates
    # For now, return query list with placeholder candidates
    extraction_elapsed_ms = 0
    total_elapsed_ms = int((time.perf_counter() - total_start) * 1000)

    return DiscoveryResponse(
        request_id=str(uuid.uuid4()),
        status="completed" if queries else "failed",
        original_title=req.title,
        queries_used=queries,
        total_urls_collected=0,
        candidates=[],
        metadata=DiscoveryMetadata(
            total_candidates=0,
            queries_generated=len(queries),
            extraction_time_ms=extraction_elapsed_ms,
            search_time_ms=search_elapsed_ms,
            total_time_ms=total_elapsed_ms,
        ),
    )


def _generate_queries(req: DiscoveryRequest, config) -> list[str]:
    """Generate Google search queries from the discovery request."""
    try:
        from backend.discovery.services.query_generator import generate_queries
        return generate_queries(
            req.article_text,
            config,
            title=req.title,
            search_depth=req.options.search_depth,
        )
    except Exception:
        # Fail fast on query generation errors rather than returning partial
        return []


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
async def health():
    """Lightweight health check returning dependency status."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "CopyGuard Discovery",
        "dependencies": {
            "google_search": "configured" if settings.google.api_key else "missing_api_key",
            "content_extraction": "ok",
        },
    }


# ---------------------------------------------------------------------------
# Legacy API stubs (to be migrated to dedicated services)
# ---------------------------------------------------------------------------

from pydantic import BaseModel

class ScanRequest(BaseModel):
    article_text: str

class DMCARequest(BaseModel):
    evidence_id: str

@app.post("/scan")
async def start_scan(req: ScanRequest):
    return {"id": "scan_123", "status": "started"}

@app.get("/scan/{scan_id}/progress")
async def scan_progress(scan_id: str):
    return {"id": scan_id, "progress": 50, "status": "in_progress"}

@app.get("/scan/{scan_id}/candidates")
async def scan_candidates(scan_id: str):
    return {"id": scan_id, "candidates": []}

@app.get("/scan/{scan_id}/results")
async def scan_results(scan_id: str):
    return {"id": scan_id, "similarity_score": 0.85, "evidence": []}

@app.get("/report/{report_id}")
async def get_report(report_id: str):
    return {"id": report_id, "download_url": "http://localhost:8000/reports/pdf"}

@app.post("/dmca/generate")
async def generate_dmca(req: DMCARequest):
    return {"status": "success", "dmca_text": "DMCA Notice..."}


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