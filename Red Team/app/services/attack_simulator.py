"""
Attack simulation service for Red Team Agent.
Fetches vulnerabilities from the main Sentinel backend and simulates attacks.
Supports per-model filtering: Qwen, Mistral, or combined (all).
"""
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.finding import Finding

logger = structlog.get_logger(__name__)
settings = get_settings()

# Which `validated_by` values indicate each model participated in the verdict
_MODEL_TAGS = {
    "mistral": {"fallback_mistral", "consensus", "judged", "gemini_validated"},
    "qwen":    {"consensus", "judged", "gemini_validated"},
}


class AttackSimulator:
    """Simulates attacks based on discovered vulnerabilities."""
    
    # Attack templates for different vulnerability types
    ATTACK_TEMPLATES = {
        "BOLA": [
            {"name": "IDOR User Enumeration", "description": "Attempt to access other users' resources by manipulating IDs"},
            {"name": "Horizontal Privilege Escalation", "description": "Access resources belonging to same-level users"},
            {"name": "Object Reference Manipulation", "description": "Modify object references to access unauthorized data"},
        ],
        "privilege_escalation": [
            {"name": "Vertical Privilege Escalation", "description": "Attempt to elevate to admin/higher role"},
            {"name": "Role Bypass Attack", "description": "Bypass role checks to access privileged functions"},
            {"name": "Token Manipulation", "description": "Modify JWT/session tokens to gain elevated access"},
        ],
        "authentication": [
            {"name": "Session Fixation", "description": "Force victim to use attacker-controlled session"},
            {"name": "Credential Stuffing Simulation", "description": "Test rate limiting on login endpoints"},
            {"name": "Token Replay Attack", "description": "Reuse captured authentication tokens"},
        ],
        "authorization": [
            {"name": "Missing Function Level Access Control", "description": "Access admin functions without proper authorization"},
            {"name": "Forced Browsing", "description": "Access restricted endpoints directly"},
            {"name": "Parameter Tampering", "description": "Modify request parameters to bypass authorization"},
        ],
        "default": [
            {"name": "Generic Security Probe", "description": "General security testing of the endpoint"},
            {"name": "Input Validation Test", "description": "Test input handling and validation"},
        ],
    }
    
    def __init__(self, backend_url: str = None):
        self.backend_url = backend_url or settings.analysis_backend_url
        
    async def fetch_vulnerabilities(self, model: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch vulnerabilities from the main Sentinel backend.
        
        Args:
            model: Optional filter — "qwen" | "mistral" to return only
                   vulnerabilities that the given model participated in detecting.
                   None returns all vulnerabilities.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.backend_url}/api/dashboard/vulnerabilities")
                if response.status_code == 200:
                    all_vulns = response.json()
                    if model and model in _MODEL_TAGS:
                        tags = _MODEL_TAGS[model]
                        filtered = [
                            v for v in all_vulns
                            if v.get("validated_by", "") in tags
                        ]
                        logger.info("fetched_vulnerabilities_for_model",
                                    model=model, total=len(all_vulns), filtered=len(filtered))
                        return filtered
                    return all_vulns
                logger.warning("fetch_vulnerabilities_failed", status=response.status_code)
        except Exception as e:
            logger.error("fetch_vulnerabilities_error", error=str(e))
        return []
    
    async def fetch_recent_scans(self) -> List[Dict[str, Any]]:
        """Fetch recent scans from the main backend."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.backend_url}/api/dashboard/recent_scans")
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error("fetch_scans_error", error=str(e))
        return []
    
    def _categorize_vulnerability(self, vuln: Dict[str, Any]) -> str:
        """Categorize vulnerability to select appropriate attack template."""
        vuln_str = str(vuln).lower()
        
        if any(term in vuln_str for term in ["bola", "idor", "object reference", "insecure direct"]):
            return "BOLA"
        elif any(term in vuln_str for term in ["privilege", "escalation", "role"]):
            return "privilege_escalation"
        elif any(term in vuln_str for term in ["auth", "login", "session", "token", "jwt"]):
            return "authentication"
        elif any(term in vuln_str for term in ["access control", "authorization", "forbidden"]):
            return "authorization"
        return "default"
    
    def _generate_attack_result(
        self,
        attack: Dict[str, Any],
        vuln: Dict[str, Any],
        model_source: str = "combined",
    ) -> Dict[str, Any]:
        """Generate simulated attack result."""
        severity = vuln.get("severity", "medium").lower()
        success_probability = {
            "critical": 0.85,
            "high": 0.70,
            "medium": 0.50,
            "low": 0.30,
            "info": 0.10,
        }.get(severity, 0.50)
        
        success = random.random() < success_probability
        
        return {
            "attack_name": attack["name"],
            "attack_description": attack["description"],
            "target_endpoint": vuln.get("endpoint", vuln.get("route", vuln.get("path", "Unknown"))),
            "target_method": vuln.get("method", "GET"),
            "vulnerability_title": vuln.get("title", vuln.get("vulnerability_type", vuln.get("name", "Unknown Vulnerability"))),
            "original_severity": severity,
            "attack_successful": success,
            "exploitation_difficulty": (
                "Easy" if success_probability > 0.6
                else "Medium" if success_probability > 0.3
                else "Hard"
            ),
            "simulated_at": datetime.utcnow().isoformat(),
            "recommendation": vuln.get("recommendation", "Review and implement proper access controls"),
            "model_source": model_source,
            "validated_by": vuln.get("validated_by", "unknown"),
            "confidence": vuln.get("confidence", 0),
        }
    
    async def simulate_attacks(
        self,
        vulns: List[Dict[str, Any]] = None,
        model_source: str = "combined",
    ) -> List[Dict[str, Any]]:
        """
        Run attack simulations against discovered vulnerabilities.
        
        Args:
            vulns: Optional list of vulnerabilities. If None, fetches from backend.
            model_source: Label for the model that produced the findings ("qwen", "mistral", "combined").
            
        Returns:
            List of attack simulation results (each tagged with model_source).
        """
        if vulns is None:
            vulns = await self.fetch_vulnerabilities()
        
        if not vulns:
            logger.info("no_vulnerabilities_to_attack", model=model_source)
            return []
        
        results = []
        logger.info("starting_attack_simulation", vulnerability_count=len(vulns), model=model_source)
        
        for vuln in vulns:
            category = self._categorize_vulnerability(vuln)
            attacks = self.ATTACK_TEMPLATES.get(category, self.ATTACK_TEMPLATES["default"])
            
            selected_attacks = random.sample(attacks, min(len(attacks), random.randint(1, 2)))
            
            for attack in selected_attacks:
                await asyncio.sleep(0.1)
                result = self._generate_attack_result(attack, vuln, model_source=model_source)
                results.append(result)
                
                logger.info(
                    "attack_simulated",
                    attack=attack["name"],
                    target=result["target_endpoint"],
                    success=result["attack_successful"],
                    model=model_source,
                )
        
        logger.info(
            "attack_simulation_complete",
            total_attacks=len(results),
            successful=sum(1 for r in results if r["attack_successful"]),
            model=model_source,
        )
        
        return results

    async def simulate_attacks_for_model(self, model: str) -> List[Dict[str, Any]]:
        """
        Fetch vulnerabilities attributed to a specific model and simulate attacks.
        
        Args:
            model: "qwen" or "mistral"
        Returns:
            List of attack results tagged with model_source=model.
        """
        vulns = await self.fetch_vulnerabilities(model=model)
        return await self.simulate_attacks(vulns=vulns, model_source=model)

    async def run_full_red_team_cycle(self, db: AsyncSession = None) -> Dict[str, Any]:
        """
        Run a complete red team cycle:
        1. Fetch ALL vulnerabilities from analysis (both models)
        2. Simulate attacks
        3. Store findings (if db session provided)
        4. Return summary
        """
        logger.info("starting_red_team_cycle")
        
        vulns = await self.fetch_vulnerabilities()
        scans = await self.fetch_recent_scans()
        attack_results = await self.simulate_attacks(vulns, model_source="combined")
        
        findings_created = 0
        if db and attack_results:
            for result in attack_results:
                if result["attack_successful"]:
                    finding = Finding(
                        title=f"Exploitable: {result['vulnerability_title']}",
                        description=f"Attack '{result['attack_name']}' succeeded against {result['target_endpoint']}",
                        severity=result["original_severity"],
                        status="open",
                        category=result["attack_name"],
                        endpoint=result["target_endpoint"],
                        method=result["target_method"],
                        evidence=f"Simulated attack successful. Difficulty: {result['exploitation_difficulty']}. Model: {result['model_source']}",
                        recommendation=result["recommendation"],
                    )
                    db.add(finding)
                    findings_created += 1
            
            if findings_created > 0:
                await db.commit()
        
        successful_attacks = [r for r in attack_results if r["attack_successful"]]
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "model_source": "combined",
            "summary": {
                "vulnerabilities_analyzed": len(vulns),
                "recent_scans_found": len(scans),
                "total_attacks_simulated": len(attack_results),
                "successful_attacks": len(successful_attacks),
                "findings_created": findings_created,
            },
            "attack_results": attack_results,
            "high_risk_findings": [
                r for r in successful_attacks
                if r["original_severity"] in ["critical", "high"]
            ],
        }

    async def run_model_red_team_cycle(self, model: str, db: AsyncSession = None) -> Dict[str, Any]:
        """
        Run a red team cycle scoped to vulnerabilities found by a specific model.
        
        Args:
            model: "qwen" or "mistral"
            db: Optional DB session for persisting findings.
        Returns:
            Full cycle result dict with model_source set.
        """
        logger.info("starting_model_red_team_cycle", model=model)
        
        vulns = await self.fetch_vulnerabilities(model=model)
        scans = await self.fetch_recent_scans()
        attack_results = await self.simulate_attacks(vulns, model_source=model)
        
        findings_created = 0
        if db and attack_results:
            for result in attack_results:
                if result["attack_successful"]:
                    finding = Finding(
                        title=f"[{model.upper()}] Exploitable: {result['vulnerability_title']}",
                        description=f"[{model.upper()}] Attack '{result['attack_name']}' succeeded against {result['target_endpoint']}",
                        severity=result["original_severity"],
                        status="open",
                        category=result["attack_name"],
                        endpoint=result["target_endpoint"],
                        method=result["target_method"],
                        evidence=f"Simulated attack successful. Difficulty: {result['exploitation_difficulty']}. Source model: {model}",
                        recommendation=result["recommendation"],
                    )
                    db.add(finding)
                    findings_created += 1
            
            if findings_created > 0:
                await db.commit()
        
        successful_attacks = [r for r in attack_results if r["attack_successful"]]
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "model_source": model,
            "summary": {
                "model": model,
                "vulnerabilities_analyzed": len(vulns),
                "recent_scans_found": len(scans),
                "total_attacks_simulated": len(attack_results),
                "successful_attacks": len(successful_attacks),
                "findings_created": findings_created,
            },
            "attack_results": attack_results,
            "high_risk_findings": [
                r for r in successful_attacks
                if r["original_severity"] in ["critical", "high"]
            ],
        }
