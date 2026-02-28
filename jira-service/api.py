"""
Sentinel AI - Jira Service API Routes
FastAPI router providing Jira integration management endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db import get_all_jira_issues, get_jira_issues_for_scan, get_jira_stats
from jira_client import check_jira_connectivity

logger = logging.getLogger(__name__)
router = APIRouter()


class JiraConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    project_key: Optional[str] = None
    user_email: Optional[str] = None
    api_token: Optional[str] = None
    issue_type: Optional[str] = None


@router.get("/status")
async def jira_service_status():
    jira_status = check_jira_connectivity()
    return {"service": "running", "jira": jira_status}


@router.get("/issues")
async def list_jira_issues(limit: int = 100):
    issues = get_all_jira_issues(limit=limit)
    for issue in issues:
        for key in ("created_at", "updated_at"):
            if issue.get(key):
                issue[key] = issue[key].isoformat()
    return {"issues": issues, "total": len(issues)}


@router.get("/issues/{scan_id}")
async def get_issues_for_scan(scan_id: int):
    issues = get_jira_issues_for_scan(scan_id)
    for issue in issues:
        for key in ("created_at", "updated_at"):
            if issue.get(key):
                issue[key] = issue[key].isoformat()
    return {"scan_id": scan_id, "issues": issues, "total": len(issues)}


@router.get("/stats")
async def jira_stats():
    return get_jira_stats()


@router.post("/trigger")
async def trigger_processing():
    try:
        from notification_worker import celery_app
        celery_app.send_task("notification_worker.trigger_processing")
        return {"status": "triggered", "message": "Processing task queued."}
    except Exception as e:
        logger.error(f"Failed to trigger processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_jira_config(config: JiraConfigUpdate):
    return {
        "status": "acknowledged",
        "message": "Jira configuration is currently managed via environment variables.",
    }
