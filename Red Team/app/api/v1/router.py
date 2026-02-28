"""
API v1 Router for Sentinel AI Red Team Agent.
Aggregates all v1 API endpoints.
"""
from fastapi import APIRouter

from app.api.v1.findings import router as findings_router
from app.api.v1.attacks import router as attacks_router

router = APIRouter(prefix="/api/v1", tags=["Red Team API v1"])

# Include sub-routers
router.include_router(findings_router)
router.include_router(attacks_router)


@router.get("/status")
async def api_status():
    """Check API v1 status."""
    return {
        "api_version": "v1",
        "status": "operational",
        "service": "sentinel-redteam",
    }
