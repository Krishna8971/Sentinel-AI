from fastapi import APIRouter
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ScanRequest(BaseModel):
    github_url: str

@router.post("/")
async def trigger_manual_scan(request: ScanRequest):
    """
    Manually trigger a security scan by providing a GitHub URL.
    This simulates the webhook behavior for MVP testing purposes.
    """
    url = request.github_url
    repo_name = url.split("github.com/")[-1] if "github.com/" in url else url
    
    # Actually trigger the Celery worker via message broker
    try:
        import celery
        import os
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        app = celery.Celery('worker', broker=redis_url)
        app.send_task('celery_worker.run_security_scan', args=[repo_name, "main", None, "latest"])
    except Exception as e:
        logger.error(f"Failed to queue task: {e}")
    
    logger.info(f"Manual scan triggered for {repo_name}")
    
    return {"status": "success", "message": f"Scan triggered for {repo_name}", "repo": repo_name}
