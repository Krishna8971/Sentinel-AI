"""
Pydantic schemas for Finding API requests and responses.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FindingBase(BaseModel):
    """Base schema for Finding."""
    title: str = Field(..., max_length=255, description="Finding title")
    description: Optional[str] = Field(None, description="Detailed description")
    severity: str = Field("medium", description="Severity level: critical, high, medium, low, info")
    category: Optional[str] = Field(None, max_length=100, description="Category: BOLA, privilege_escalation, etc.")
    endpoint: Optional[str] = Field(None, max_length=500, description="Affected endpoint")
    method: Optional[str] = Field(None, max_length=10, description="HTTP method")
    evidence: Optional[str] = Field(None, description="Evidence of the vulnerability")
    recommendation: Optional[str] = Field(None, description="Remediation recommendation")
    scan_id: Optional[int] = Field(None, description="Related scan ID")


class FindingCreate(FindingBase):
    """Schema for creating a new finding."""
    pass


class FindingUpdate(BaseModel):
    """Schema for updating an existing finding."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = Field(None, description="Status: open, confirmed, fixed, false_positive")
    category: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None


class FindingResponse(FindingBase):
    """Schema for finding response."""
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
