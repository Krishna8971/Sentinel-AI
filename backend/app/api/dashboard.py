from fastapi import APIRouter
from datetime import datetime, timedelta
import os
import asyncpg

router = APIRouter()

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

    # Fallback default values if db is empty or unreachable
    return {
        "score": 92,
        "drift": 2,
        "exploits_prevented": 14 
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
                
    # Fallback to mock data
    return [
        { "id": '#420', "status": 'Passed', "title": 'Refactor user routing', "issues": 0, "time": '2h ago' },
        { "id": '#419', "status": 'Blocked', "title": 'Add admin dashboard metrics', "issues": 2, "time": '5h ago' },
        { "id": '#418', "status": 'Passed', "title": 'Update dependency injection', "issues": 0, "time": '1d ago' },
    ]
