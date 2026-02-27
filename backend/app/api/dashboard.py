from fastapi import APIRouter
from datetime import datetime, timedelta
import os
import asyncpg
import httpx

router = APIRouter()

MISTRAL_API_BASE_URL = os.getenv("MISTRAL_API_BASE_URL", "http://host.docker.internal:1234/v1")
QWEN_API_BASE_URL = os.getenv("QWEN_API_BASE_URL", "http://host.docker.internal:1235/v1")

DB_USER = os.getenv("POSTGRES_USER", "sentinel_db_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
DB_NAME = os.getenv("POSTGRES_DB", "sentinel_db")
DB_HOST = os.getenv("POSTGRES_HOST", "db")

async def get_db_connection():
    try:
        return await asyncpg.connect(user=DB_USER, password=DB_PASS, database=DB_NAME, host=DB_HOST)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@router.get("/stats")
async def get_dashboard_stats():
    conn = await get_db_connection()
    if conn:
        try:
            # Get latest score
            latest_score = await conn.fetchval('SELECT auth_integrity_score FROM scan_results ORDER BY timestamp DESC LIMIT 1')
            total_scans = await conn.fetchval('SELECT COUNT(*) FROM scan_results')
            high_vulns = await conn.fetchval("SELECT COUNT(*) FROM scan_results WHERE severity IN ('High', 'Critical')")
            
            await conn.close()
            
            if latest_score is not None:
                return {
                    "score": latest_score,
                    "drift": total_scans, # Mocking drift as total scans for now
                    "exploits_prevented": high_vulns or 0 
                }
        except Exception:
            if not conn.is_closed():
                await conn.close()

    # Return zeroed default values if db is empty or unreachable
    return {
        "score": 100, # A safe default score
        "drift": 0,
        "exploits_prevented": 0 
    }

@router.get("/recent_scans")
async def get_recent_scans():
    conn = await get_db_connection()
    if conn:
        try:
            scans = await conn.fetch('SELECT repo_name, commit_hash, timestamp, severity, auth_integrity_score FROM scan_results ORDER BY timestamp DESC LIMIT 5')
            await conn.close()
            
            if scans:
                result = []
                for s in scans:
                    issues = 0 if s['severity'] == "Low" else (2 if s['severity'] == "Medium" else 5)
                    result.append({
                        "id": f"#{s['commit_hash'][:6]}",
                        "status": "Passed" if s['auth_integrity_score'] >= 80 else "Blocked",
                        "title": f"Scan for {s['repo_name']}",
                        "issues": issues,
                        "time": s['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                    })
                return result
        except Exception:
            if not conn.is_closed():
                await conn.close()
                
    # Return empty list if no scans exist
    return []

@router.get("/vulnerabilities")
async def get_vulnerabilities():
    conn = await get_db_connection()
    if conn:
        try:
            rows = await conn.fetch(
                'SELECT repo_name, vulnerabilities, timestamp, auth_integrity_score, severity FROM scan_results ORDER BY timestamp DESC LIMIT 10'
            )
            await conn.close()
            result = []
            for row in rows:
                vulns = row['vulnerabilities']
                if isinstance(vulns, str):
                    import json
                    vulns = json.loads(vulns)
                for v in (vulns or []):
                    v['repo'] = row['repo_name']
                    v['scan_score'] = row['auth_integrity_score']
                    v['scan_time'] = row['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                    result.append(v)
            return result
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            if not conn.is_closed():
                await conn.close()
    return []

@router.delete("/reset")
async def reset_dashboard_stats():
    conn = await get_db_connection()
    if conn:
        try:
            await conn.execute('DELETE FROM scan_results')
            await conn.close()
            return {"status": "success", "message": "Database wiped."}
        except Exception as e:
            if not conn.is_closed():
                await conn.close()
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Database disconnected"}

@router.get("/ai_status")
async def get_ai_status():
    async def check_node(url: str):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{url}/models", timeout=3.0)
                return res.status_code == 200
        except Exception:
            return False
            
    mistral_ok = await check_node(MISTRAL_API_BASE_URL)
    qwen_ok = await check_node(QWEN_API_BASE_URL)
    
    return {
        "mistral": "online" if mistral_ok else "offline",
        "qwen": "online" if qwen_ok else "offline"
    }
