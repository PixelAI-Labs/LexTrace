"""Analysis API — top-level router.

Mount this router onto the FastAPI application:

    from backend.analysis.api.router import router as analysis_router
    app.include_router(analysis_router)
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1.analyze import router as analyze_router
from backend.api.v1.dmca import router as dmca_router
from backend.api.v1.report import router as report_router

router = APIRouter()
router.include_router(analyze_router)
router.include_router(report_router)
router.include_router(dmca_router)

__all__ = ["router"]