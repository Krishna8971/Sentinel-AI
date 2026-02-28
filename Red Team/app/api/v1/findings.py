"""
Findings API endpoints for Red Team Agent.
Manages security findings discovered during red team operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.finding import Finding
from app.schemas.finding import FindingCreate, FindingResponse, FindingUpdate

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("/", response_model=List[FindingResponse])
async def list_findings(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all security findings with optional filters."""
    query = select(Finding).offset(offset).limit(limit)
    
    if severity:
        query = query.where(Finding.severity == severity)
    if status:
        query = query.where(Finding.status == status)
    
    result = await db.execute(query)
    findings = result.scalars().all()
    return findings


@router.post("/", response_model=FindingResponse, status_code=201)
async def create_finding(
    finding: FindingCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new security finding."""
    db_finding = Finding(**finding.model_dump())
    db.add(db_finding)
    await db.commit()
    await db.refresh(db_finding)
    return db_finding


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific finding by ID."""
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    return finding


@router.patch("/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: int,
    finding_update: FindingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a finding's status or details."""
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    update_data = finding_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(finding, field, value)
    
    await db.commit()
    await db.refresh(finding)
    return finding


@router.delete("/{finding_id}", status_code=204)
async def delete_finding(
    finding_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a finding."""
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    await db.delete(finding)
    await db.commit()
