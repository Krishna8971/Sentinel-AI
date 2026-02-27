from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class VulnerabilityDetail(BaseModel):
    function_name: str
    path: str
    method: str
    vulnerability_type: str
    confidence: int
    reasoning: str

class RepoScanResult(BaseModel):
    repo_name: str
    commit_hash: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    auth_integrity_score: int
    drift_delta: int
    vulnerabilities: List[VulnerabilityDetail] = []
    
class RiskScoringEngine:
    @staticmethod
    def calculate_score(vulnerabilities: List[VulnerabilityDetail]) -> dict:
        """
        Calculates a risk score from 0-100 based on vulnerabilities found.
        100 = Perfect security, no vulns
        0 = Critical vulnerabilities everywhere
        """
        base_score = 100
        critical_count = 0
        high_count = 0
        
        for vuln in vulnerabilities:
            if vuln.vulnerability_type == "BOLA":
                critical_count += 1
                base_score -= 20
            elif vuln.vulnerability_type == "Privilege Escalation":
                high_count += 1
                base_score -= 15
            else:
                base_score -= 5
                
            # Factor in confidence
            base_score += int((100 - vuln.confidence) / 10) # Less confidence = less penalty
            
        final_score = max(0, min(100, base_score))
        
        severity = "Low"
        if final_score <= 30:
            severity = "Critical"
        elif final_score <= 60:
            severity = "High"
        elif final_score <= 80:
            severity = "Medium"
            
        return {
            "score": final_score,
            "severity": severity,
            "critical_issues": critical_count,
            "high_issues": high_count
        }

# PostgreSQL Database Setup stub for asyncpg
import asyncpg
import os

DB_USER = os.getenv("POSTGRES_USER", "sentinel_db_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
DB_NAME = os.getenv("POSTGRES_DB", "sentinel_db")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")

async def init_db():
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, database=DB_NAME, host=DB_HOST)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS scan_results (
            id SERIAL PRIMARY KEY,
            repo_name VARCHAR(255) NOT NULL,
            commit_hash VARCHAR(255) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auth_integrity_score INTEGER,
            drift_delta INTEGER,
            severity VARCHAR(50),
            vulnerabilities JSONB
        )
    ''')
    await conn.close()
