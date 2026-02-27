from fastapi import APIRouter
import asyncpg
import os
import json

router = APIRouter()

DB_USER = os.getenv("POSTGRES_USER", "sentinel_db_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
DB_NAME = os.getenv("POSTGRES_DB", "sentinel_db")
DB_HOST = os.getenv("POSTGRES_HOST", "db")

async def get_db():
    try:
        return await asyncpg.connect(user=DB_USER, password=DB_PASS, database=DB_NAME, host=DB_HOST)
    except Exception:
        return None

@router.get("/data")
async def get_graph_data():
    """
    Returns a lightweight graph of scanned functions/routes with their vulnerability status.
    Reads directly from Postgres scan_results — no Neo4j needed.
    """
    conn = await get_db()
    if not conn:
        return {"nodes": [], "stats": {"total": 0, "vulnerable": 0, "clean": 0}}

    try:
        rows = await conn.fetch(
            "SELECT repo_name, vulnerabilities FROM scan_results ORDER BY timestamp DESC LIMIT 5"
        )
        await conn.close()
    except Exception:
        await conn.close()
        return {"nodes": [], "stats": {"total": 0, "vulnerable": 0, "clean": 0}}

    nodes = []
    seen = set()

    for row in rows:
        repo = row["repo_name"]
        vulns = row["vulnerabilities"]
        if isinstance(vulns, str):
            try:
                vulns = json.loads(vulns)
            except Exception:
                vulns = []
        if not vulns:
            vulns = []

        for v in vulns:
            fn = v.get("function_name", "")
            path = v.get("path", "")
            method = v.get("method", "FUNCTION")
            key = f"{repo}:{fn}:{path}"
            if key in seen:
                continue
            seen.add(key)
            nodes.append({
                "id": key,
                "label": f"{method} {path}" if path else fn,
                "function_name": fn,
                "repo": repo,
                "status": "vulnerable",
                "vuln_type": v.get("vulnerability_type", "Unknown"),
                "confidence": v.get("confidence", 0),
                "reasoning": v.get("reasoning", ""),
                "file_path": v.get("file_path", ""),
            })

    total = len(nodes)
    vulnerable = sum(1 for n in nodes if n["status"] == "vulnerable")

    return {
        "nodes": nodes,
        "stats": {
            "total": total,
            "vulnerable": vulnerable,
            "clean": total - vulnerable
        }
    }
