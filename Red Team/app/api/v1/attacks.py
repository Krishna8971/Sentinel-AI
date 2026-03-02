"""
Red Team Attack API endpoints.
Orchestrates attack simulations against discovered vulnerabilities.

Endpoints:
  POST /api/v1/attacks/simulate          — combined (Mistral + Qwen)
  POST /api/v1/attacks/simulate/qwen     — Qwen-attributed vulnerabilities only
  POST /api/v1/attacks/simulate/mistral  — Mistral-attributed vulnerabilities only
  GET  /api/v1/attacks/model-status      — live health of both AI models
  GET  /api/v1/attacks/status            — service status
  GET  /api/v1/attacks/vulnerabilities   — list vulnerabilities
  GET  /api/v1/attacks/scans             — list recent scans
"""
from typing import Optional, Literal

import httpx
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq

from app.config import get_settings
from app.database import get_db
from app.services.attack_simulator import AttackSimulator

router = APIRouter(prefix="/attacks", tags=["Red Team Attacks"])
settings = get_settings()


class AttackConfig(BaseModel):
    """Configuration for attack simulation."""
    target_repo: Optional[str] = None
    attack_categories: Optional[list] = None
    store_findings: bool = True


# ── Combined (all models) ─────────────────────────────────────────────────────

@router.post("/simulate")
async def simulate_attacks(
    config: Optional[AttackConfig] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Run attack simulations using ALL vulnerabilities from both Mistral and Qwen.

    1. Fetches all vulnerabilities from the main Sentinel backend
    2. Simulates various attack vectors based on vulnerability types
    3. Stores successful exploits as findings
    """
    simulator = AttackSimulator()
    store_db = db if (config is None or config.store_findings) else None
    return await simulator.run_full_red_team_cycle(db=store_db)


# ── Per-model endpoints ───────────────────────────────────────────────────────

@router.post("/simulate/qwen")
async def simulate_attacks_qwen(
    config: Optional[AttackConfig] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Run attack simulations using ONLY vulnerabilities detected by the Qwen model.

    Filters to vulnerabilities where Qwen participated in the verdict
    (validated_by in: consensus, judged, gemini_validated).
    Attack results are tagged with model_source='qwen'.
    """
    simulator = AttackSimulator()
    store_db = db if (config is None or config.store_findings) else None
    return await simulator.run_model_red_team_cycle(model="qwen", db=store_db)


@router.post("/simulate/mistral")
async def simulate_attacks_mistral(
    config: Optional[AttackConfig] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Run attack simulations using ONLY vulnerabilities detected by the Mistral model.

    Filters to vulnerabilities where Mistral participated in the verdict
    (validated_by in: fallback_mistral, consensus, judged, gemini_validated).
    Attack results are tagged with model_source='mistral'.
    """
    simulator = AttackSimulator()
    store_db = db if (config is None or config.store_findings) else None
    return await simulator.run_model_red_team_cycle(model="mistral", db=store_db)


# ── Model health ──────────────────────────────────────────────────────────────

@router.get("/model-status")
async def get_model_status():
    """
    Check live connectivity of both AI model backends (Mistral and Qwen).
    Used by the frontend to show model status badges.
    """
    async def check(url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{url}/models")
                return "online" if res.status_code == 200 else "offline"
        except Exception:
            return "offline"

    mistral_status = await check(settings.mistral_api_url)
    qwen_status = await check(settings.qwen_api_url)

    return {
        "mistral": mistral_status,
        "qwen": qwen_status,
    }


# ── Service status & data listing ─────────────────────────────────────────────

@router.get("/status")
async def get_attack_status():
    """Get red team attack service status."""
    simulator = AttackSimulator()
    try:
        vulns = await simulator.fetch_vulnerabilities()
        scans = await simulator.fetch_recent_scans()
        backend_connected = True
    except Exception:
        vulns = []
        scans = []
        backend_connected = False

    return {
        "service": "red-team-attack-simulator",
        "status": "operational",
        "backend_connected": backend_connected,
        "vulnerabilities_available": len(vulns),
        "recent_scans_available": len(scans),
    }


@router.get("/vulnerabilities")
async def list_vulnerabilities(model: Optional[Literal["qwen", "mistral"]] = None):
    """
    List vulnerabilities from the main Sentinel backend.
    Pass ?model=qwen or ?model=mistral to filter by model.
    """
    simulator = AttackSimulator()
    vulns = await simulator.fetch_vulnerabilities(model=model)
    return {
        "count": len(vulns),
        "model_filter": model,
        "vulnerabilities": vulns,
    }


@router.get("/scans")
async def list_recent_scans():
    """List recent scans from the main Sentinel backend."""
    simulator = AttackSimulator()
    scans = await simulator.fetch_recent_scans()
    return {
        "count": len(scans),
        "scans": scans,
    }


# ── AI Code Fix Generation ────────────────────────────────────────────────────

class FixRequest(BaseModel):
    attack_name: str
    attack_description: str
    target_endpoint: str
    target_method: str
    vulnerability_title: str
    recommendation: str

@router.post("/generate-fix")
async def generate_fix(req: FixRequest):
    """
    Use Groq (Llama 3) to generate a code snippet fix for a specific
    vulnerability that was successfully exploited during red teaming.
    """
    if not settings.groq_api_key:
        return {"fix": "Error: GROQ_API_KEY is not configured in the environment."}

    client = AsyncGroq(api_key=settings.groq_api_key)
    
    prompt = f"""You are a senior security engineer. A vulnerability was found and successfully exploited in our web application.
Please provide a concise, unified code snippet in Python (FastAPI/SQLAlchemy) to fix this issue.
Do NOT output any conversational text, markdown formatting, or explanations. ONLY output the raw Python code snippet that patches the issue.

Vulnerability: {req.vulnerability_title}
Endpoint: {req.target_method} {req.target_endpoint}
Exploit Used: {req.attack_name}
Exploit Details: {req.attack_description}
Security Recommendation: {req.recommendation}

Provide the code fix:"""

    try:
        completion = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a senior security engineer. Output only valid raw code without markdown backticks or explanations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        
        fix_code = completion.choices[0].message.content.strip()
        
        # Sometimes models still wrap in markdown despite prompt instructions, so strip it
        if fix_code.startswith("```"):
            lines = fix_code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            fix_code = "\n".join(lines).strip()
            
        return {"fix": fix_code}
    except Exception as e:
        return {"fix": f"Error generating fix from Groq: {str(e)}"}
