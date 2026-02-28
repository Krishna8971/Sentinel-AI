"""
Sentinel AI - Severity Filter
Filters vulnerabilities to only those that qualify for Jira ticket creation.
"""
import logging
from config import QUALIFYING_SEVERITIES

logger = logging.getLogger(__name__)

CRITICAL_VULN_TYPES = {"BOLA", "IDOR", "Missing Authentication", "Privilege Escalation"}
MAJOR_VULN_TYPES = {"Missing Role Guard", "Inconsistent Middleware"}
HIGH_CONFIDENCE_THRESHOLD = 55


def is_qualifying_vulnerability(vuln: dict, scan_severity: str) -> bool:
    if scan_severity not in QUALIFYING_SEVERITIES:
        return False
    confidence = vuln.get("confidence", 0)
    if isinstance(confidence, str):
        try:
            confidence = int(confidence)
        except ValueError:
            confidence = 0
    if confidence < HIGH_CONFIDENCE_THRESHOLD:
        return False
    vuln_type = vuln.get("vulnerability_type", "")
    if vuln_type in CRITICAL_VULN_TYPES or vuln_type in MAJOR_VULN_TYPES:
        return True
    if scan_severity == "Critical":
        return True
    return False


def filter_qualifying_vulnerabilities(vulnerabilities: list, scan_severity: str) -> list:
    qualifying = []
    for i, vuln in enumerate(vulnerabilities):
        if is_qualifying_vulnerability(vuln, scan_severity):
            qualifying.append((i, vuln))
    logger.info(f"Severity filter: {len(qualifying)}/{len(vulnerabilities)} qualify (scan severity: {scan_severity})")
    return qualifying
