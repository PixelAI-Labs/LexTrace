"""Risk assessment models for the Analysis Service."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk classification for infringement likelihood."""

    low = "low"
    medium = "medium"
    high = "high"


class RiskAssessment(BaseModel):
    """Risk assessment output derived from similarity and evidence signals."""

    risk_level: RiskLevel = Field(..., description="Overall infringement risk level.")
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the risk assessment (0.0 to 1.0).",
    )
    reasoning: list[str] = Field(
        default_factory=list,
        description="Human-readable reasoning for the assigned risk level.",
    )
