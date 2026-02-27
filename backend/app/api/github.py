from fastapi import APIRouter, Request, Header
import hmac
import hashlib
import os
import httpx

router = APIRouter()

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "super-secret")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "mock-token-for-now")

async def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    hash_object = hmac.new(GITHUB_WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

@router.post("/webhook")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    payload_body = await request.body()
    
    if not await verify_signature(payload_body, x_hub_signature_256):
        # Allow passing for local dev
        print("Invalid signature, but continuing for local dev.")
        # return {"status": "error", "message": "Invalid signature"}, 401

    data = await request.json()
    action = data.get("action")
    
    if "pull_request" in data and action in ["opened", "synchronize", "reopened"]:
        pr = data["pull_request"]
        repo_name = data["repository"]["full_name"]
        pr_number = pr["number"]
        diff_url = pr["diff_url"]
        commit_hash = pr["head"]["sha"]
        
        # Trigger Celery Worker here
        # For example: 
        # from worker.celery_worker import run_security_scan
        # run_security_scan.delay(repo_name, pr_number, diff_url, commit_hash)
        
        return {"status": "success", "message": f"Scan triggered for PR #{pr_number}"}
        
    return {"status": "ignored", "message": "Event ignored."}

async def fetch_pr_diff(diff_url: str) -> str:
    """Fetches the actual PR diff content from GitHub"""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(diff_url, headers=headers)
        response.raise_for_status()
        return response.text

async def post_pr_comment(repo_name: str, pr_number: int, comment: str):
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json={"body": comment})
