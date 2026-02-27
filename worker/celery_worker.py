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

from core.ast_parser import parse_fastapi_code
from core.consensus_engine import analyze_endpoint_parallel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
celery_app = Celery("worker", broker=redis_url, backend=redis_url)

# DB config
DB_USER = os.getenv("POSTGRES_USER", "sentinel_db_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
DB_NAME = os.getenv("POSTGRES_DB", "sentinel_db")
DB_HOST = os.getenv("POSTGRES_HOST", "db")

def calculate_score(vulnerabilities: List[Dict]) -> dict:
    base_score = 100
    critical_count = 0
    high_count = 0
    
    for vuln in vulnerabilities:
        v_type = vuln.get("vulnerability_type", "None")
        conf = int(vuln.get("confidence", 50))
        if v_type == "BOLA":
            critical_count += 1
            base_score -= 20
        elif v_type == "Privilege Escalation":
            high_count += 1
            base_score -= 15
        elif v_type != "None":
            base_score -= 5
            
        base_score += int((100 - conf) / 10) 
        
    final_score = max(0, min(100, base_score))
    
    severity = "Low"
    if final_score <= 30: severity = "Critical"
    elif final_score <= 60: severity = "High"
    elif final_score <= 80: severity = "Medium"
        
    return {"score": final_score, "severity": severity}

@celery_app.task
def run_security_scan(repo_name: str, branch: str = "main", diff_url: str = None, commit_hash: str = "latest"):
    logger.info(f"Starting security scan for {repo_name}...")
    
    # 1. Download Repo
    zip_url = f"https://github.com/{repo_name}/archive/refs/heads/{branch}.zip"
    
    # Synchronous because Celery task is sync
    try:
        r = httpx.get(zip_url, follow_redirects=True, timeout=30.0)
        if r.status_code == 404 and branch == "main":
            logger.info("main branch not found, trying master...")
            zip_url = f"https://github.com/{repo_name}/archive/refs/heads/master.zip"
            r = httpx.get(zip_url, follow_redirects=True, timeout=30.0)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to download repository {repo_name}: {e}")
        return {"status": "error", "message": "Failed to download repository."}
        
    endpoints = []
    
    # 2. Extract and Parse AST
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "repo.zip")
        with open(zip_path, "wb") as f:
            f.write(r.content)
            
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)
        except zipfile.BadZipFile:
            logger.error("Invalid zip file received from GitHub")
            return {"status": "error"}
            
        # Parse all python files
        for py_file in Path(tmpdir).rglob("*.py"):
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
                try:
                    found_endpoints = parse_fastapi_code(code)
                    endpoints.extend(found_endpoints)
                except Exception as e:
                    logger.warning(f"Error parsing AST in {py_file}: {e}")
                    
    logger.info(f"Worker found {len(endpoints)} FastAPI endpoints in {repo_name}")
    
    if not endpoints:
        score_data = {"score": 100, "severity": "Low"}
        final_vulns = []
    else:
        # 3. Analyze all endpoints with AI Model Consensus
        async def run_all():
            tasks = [analyze_endpoint_parallel(ep) for ep in endpoints]
            return await asyncio.gather(*tasks)
            
        ai_results = asyncio.run(run_all())
        
        # 4. Filter vulnerabilities
        final_vulns = []
        for i, res in enumerate(ai_results):
            if res.get("status") in ["consensus", "judged", "fallback_qwen", "fallback_mistral"]:
                verdict = res.get("result", {})
                if verdict.get("has_vulnerability"):
                    ep = endpoints[i]
                    final_vulns.append({
                        "function_name": ep["function_name"],
                        "path": ep["path"],
                        "method": ep["method"],
                        "vulnerability_type": verdict.get("vulnerability_type", "Unknown"),
                        "confidence": verdict.get("confidence", 80),
                        "reasoning": verdict.get("reasoning", "")
                    })
                    
        score_data = calculate_score(final_vulns)
        
    # 5. Save to Postgres
    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            database=DB_NAME
        )
        cur = conn.cursor()
        
        insert_query = """
            INSERT INTO scan_results 
            (repo_name, commit_hash, auth_integrity_score, drift_delta, severity, vulnerabilities)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(insert_query, (
            repo_name,
            commit_hash,
            score_data["score"],
            len(endpoints),  # Drift simulated as number of routes identified
            score_data["severity"],
            json.dumps(final_vulns)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Successfully saved scan results for {repo_name}")
    except Exception as e:
        logger.error(f"Failed to save results to Postgres: {e}")
        
    return {"status": "success", "score": score_data["score"]}
