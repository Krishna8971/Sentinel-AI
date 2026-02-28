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
