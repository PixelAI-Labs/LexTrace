"""DMCA models for the Analysis Service."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.analysis.schemas.risk import RiskLevel


class DmcaRequest(BaseModel):
    """Inputs required to generate a DMCA notice."""

    creator_name: str = Field(..., min_length=1, description="Name of the copyright holder.")
    creator_email: str = Field(..., min_length=3, description="Contact email for the copyright holder.")
    creator_address: str = Field(..., min_length=3, description="Mailing address for the copyright holder.")
    original_url: str = Field(..., min_length=3, description="URL of the original work.")
    infringing_url: str = Field(..., min_length=3, description="URL of the infringing copy.")


class DmcaNotice(BaseModel):
    """Generated DMCA notice payload."""

    subject: str = Field(..., description="Subject line for the DMCA notice.")
    body: str = Field(..., description="DMCA notice body in plain text.")
    summary: str = Field(..., description="Short summary of the notice content.")
    risk_level: RiskLevel = Field(..., description="Risk level associated with the infringement.")
