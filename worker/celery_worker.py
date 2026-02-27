import os
import httpx
import asyncio
import json
import zipfile
import tempfile
import psycopg2
from typing import List, Dict, Any
from pathlib import Path
from celery import Celery
import logging

from core.ast_parser import parse_fastapi_code, extract_all_functions
from core.consensus_engine import analyze_endpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
celery_app = Celery("worker", broker=redis_url, backend=redis_url)

DB_USER = os.getenv("POSTGRES_USER", "sentinel_db_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
DB_NAME = os.getenv("POSTGRES_DB", "sentinel_db")
DB_HOST = os.getenv("POSTGRES_HOST", "db")

SKIP_DIRS = {'__pycache__', '.git', 'venv', 'env', '.venv', 'node_modules', 'migrations', 'tests', 'test'}
SKIP_FILES = {'setup.py', 'conftest.py'}

# Keywords that indicate a function is worth analyzing for auth issues
AUTH_KEYWORDS = {
    'user', 'admin', 'role', 'permission', 'auth', 'token',
    'db.query', 'session.query', '.get(', '.filter(',
    'current_user', 'user_id', 'owner', 'access', 'privilege',
    'delete', 'update', 'create', 'write', 'modify',
    'Depends', 'HTTPException', 'status_code',
}

def is_security_relevant(item: Dict[str, Any]) -> bool:
    """Returns True if this function is worth sending to the LLM."""
    # Always analyze FastAPI endpoints
    if item.get("is_endpoint"):
        return True
    code = (item.get("code") or "").lower()
    # Skip tiny functions (< 5 lines)
    if len(code.splitlines()) < 5:
        return False
    # Only analyze if auth-relevant keywords present
    return any(kw in code for kw in AUTH_KEYWORDS)


def calculate_score(vulnerabilities: List[Dict]) -> dict:
    base_score = 100
    for vuln in vulnerabilities:
        v_type = vuln.get("vulnerability_type", "None")
        conf = int(vuln.get("confidence", 50))
        weight = {
            "BOLA": 25, "IDOR": 20,
            "Privilege Escalation": 20, "Missing Authentication": 15,
            "Missing Role Guard": 10, "Inconsistent Middleware": 8,
        }.get(v_type, 5)
        base_score -= int(weight * conf / 100)
    final_score = max(0, min(100, base_score))
    severity = "Low"
    if final_score <= 30: severity = "Critical"
    elif final_score <= 60: severity = "High"
    elif final_score <= 80: severity = "Medium"
    return {"score": final_score, "severity": severity}


@celery_app.task(bind=True)
def run_security_scan(self, repo_name: str, branch: str = "main", diff_url: str = None, commit_hash: str = "latest"):
    logger.info(f"Starting security scan for {repo_name}...")

    # 1. Download repo zip
    zip_url = f"https://github.com/{repo_name}/archive/refs/heads/{branch}.zip"
    try:
        r = httpx.get(zip_url, follow_redirects=True, timeout=60.0)
        if r.status_code == 404 and branch == "main":
            logger.info("main not found, trying master...")
            zip_url = f"https://github.com/{repo_name}/archive/refs/heads/master.zip"
            r = httpx.get(zip_url, follow_redirects=True, timeout=60.0)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to download {repo_name}: {e}")
        return {"status": "error", "message": str(e)}

    all_items = []  # unified list of endpoints + functions to analyze

    # 2. Extract and parse every Python file
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "repo.zip")
        with open(zip_path, "wb") as f:
            f.write(r.content)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
        except zipfile.BadZipFile:
            logger.error("Invalid zip file")
            return {"status": "error", "message": "Invalid zip"}

        endpoint_keys = set()

        for py_file in Path(tmpdir).rglob("*.py"):
            # Skip unwanted directories and files
            parts = set(py_file.parts)
            if parts & SKIP_DIRS:
                continue
            if py_file.name in SKIP_FILES:
                continue

            rel_path = str(py_file.relative_to(tmpdir))
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                if not code.strip():
                    continue

                # FastAPI endpoints (highest priority)
                try:
                    endpoints = parse_fastapi_code(code)
                    for ep in endpoints:
                        ep["file_path"] = rel_path
                        ep["is_endpoint"] = True
                        key = f"{ep['method']}:{ep['path']}"
                        endpoint_keys.add(key)
                        all_items.append(ep)
                except Exception:
                    pass

                # All other functions in this file
                try:
                    funcs = extract_all_functions(code, rel_path)
                    for fn in funcs:
                        # Don't re-add functions already captured as endpoints
                        key = f"FUNCTION:{fn['function_name']}:{rel_path}"
                        if key not in endpoint_keys:
                            endpoint_keys.add(key)
                            all_items.append(fn)
                except Exception:
                    pass

            except Exception as e:
                logger.warning(f"Error reading {py_file}: {e}")

    logger.info(f"Total items found: {len(all_items)} ({repo_name})")

    # Pre-filter: only analyze security-relevant items
    relevant_items = [item for item in all_items if is_security_relevant(item)]
    logger.info(f"Security-relevant items to analyze: {len(relevant_items)} (skipped {len(all_items) - len(relevant_items)} trivial functions)")

    if not relevant_items:
        score_data = {"score": 100, "severity": "Low"}
        final_vulns = []
    else:
        # Semaphore limits concurrent LLM calls to avoid overwhelming Mistral
        SEM = asyncio.Semaphore(5)

        async def analyze_with_semaphore(item):
            async with SEM:
                return await analyze_endpoint(item)

        async def run_all():
            tasks = [analyze_with_semaphore(item) for item in relevant_items]
            return await asyncio.gather(*tasks, return_exceptions=True)

        ai_results = asyncio.run(run_all())

        # 4. Collect confirmed vulnerabilities
        final_vulns = []
        for i, res in enumerate(ai_results):
            if isinstance(res, Exception):
                logger.warning(f"Analysis exception for item {i}: {res}")
                continue
            if res.get("status") in ("consensus", "gemini_validated", "judged", "fallback_mistral"):
                verdict = res.get("result", {})
                if verdict.get("has_vulnerability") and verdict.get("confidence", 0) > 55:
                    item = relevant_items[i]
                    final_vulns.append({
                        "function_name": item.get("function_name", ""),
                        "path": item.get("path", ""),
                        "method": item.get("method", ""),
                        "file_path": item.get("file_path", ""),
                        "vulnerability_type": verdict.get("vulnerability_type", "Unknown"),
                        "confidence": verdict.get("confidence", 0),
                        "reasoning": verdict.get("reasoning", ""),
                        "validated_by": res.get("status", "")
                    })

        score_data = calculate_score(final_vulns)

    logger.info(f"Scan complete: {len(final_vulns)} vulnerabilities, score={score_data['score']}")

    # 5. Save to Postgres
    try:
        conn = psycopg2.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, database=DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO scan_results (repo_name, commit_hash, auth_integrity_score, drift_delta, severity, vulnerabilities) VALUES (%s, %s, %s, %s, %s, %s)",
            (repo_name, commit_hash, score_data["score"], len(all_items), score_data["severity"], json.dumps(final_vulns))
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Results saved for {repo_name}")
    except Exception as e:
        logger.error(f"Failed to save results: {e}")

    return {"status": "success", "score": score_data["score"], "vulnerabilities_found": len(final_vulns)}
