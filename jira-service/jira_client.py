"""
Sentinel AI - Jira API Client
Handles creation of Jira issues and adding comments.
Uses Jira REST API **v2** (accepts wiki-markup text, no ADF required).
Includes retry logic with exponential backoff.
Auto-discovers valid issue types from the project.
"""
import httpx
import logging
import time
from config import (
    JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN,
    JIRA_PROJECT_KEY, JIRA_ISSUE_TYPE, PRIORITY_MAP,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2


def _get_auth():
    return (JIRA_USER_EMAIL, JIRA_API_TOKEN)


def _get_headers():
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _retry_request(method, url, **kwargs):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=10.0) as client:
                response = getattr(client, method)(
                    url, auth=_get_auth(), headers=_get_headers(), **kwargs,
                )
                if response.status_code >= 400:
                    logger.error(f"Jira API {response.status_code} response body: {response.text}")
                response.raise_for_status()
                return response
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.warning(f"Jira API attempt {attempt}/{MAX_RETRIES} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
    logger.error(f"Jira API request failed after {MAX_RETRIES} attempts: {last_error}")
    raise last_error


def build_issue_title(severity: str, risk_type: str, repo_name: str) -> str:
    return f"[Sentinel] {severity} - {risk_type} - {repo_name}"


def build_issue_description(vuln: dict, scan_data: dict) -> str:
    lines = [
        f"*Vulnerability Type:* {vuln.get('vulnerability_type', 'Unknown')}",
        f"*Severity Level:* {scan_data.get('severity', 'Unknown')}",
        f"*Risk Score:* {scan_data.get('auth_integrity_score', 'N/A')}",
        f"*Affected Endpoint / File:* {vuln.get('path', vuln.get('file_path', 'N/A'))}",
        "",
        "*Attack Path Explanation:*",
        f"{vuln.get('reasoning', 'No details available.')}",
        "",
        f"*Function:* {vuln.get('function_name', 'N/A')}",
        f"*Method:* {vuln.get('method', 'N/A')}",
        f"*Confidence:* {vuln.get('confidence', 'N/A')}%",
        "",
        f"*Repository:* {scan_data.get('repo_name', 'N/A')}",
        f"*Commit Hash:* {scan_data.get('commit_hash', 'N/A')}",
        f"*Scan ID:* {scan_data.get('id', 'N/A')}",
        "",
        "----",
        "_Generated automatically by Sentinel AI Jira Integration_",
    ]
    return "\n".join(lines)


# Cached issue type ID for the project (discovered once, reused)
_cached_issue_type_id = None


def _discover_issue_type_id():
    global _cached_issue_type_id
    if _cached_issue_type_id is not None:
        return _cached_issue_type_id

    url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/2/project/{JIRA_PROJECT_KEY}"
    try:
        response = _retry_request("get", url)
        project_data = response.json()
        issue_types = project_data.get("issueTypes", [])

        if not issue_types:
            logger.warning("No issue types found for project, falling back to 'Task'")
            _cached_issue_type_id = {"name": "Task"}
            return _cached_issue_type_id

        for it in issue_types:
            if it.get("name", "").lower() == JIRA_ISSUE_TYPE.lower():
                _cached_issue_type_id = {"id": it["id"]}
                logger.info(f"Using configured issue type: {it['name']} (id={it['id']})")
                return _cached_issue_type_id

        for it in issue_types:
            if not it.get("subtask", False):
                _cached_issue_type_id = {"id": it["id"]}
                logger.info(f"Configured type '{JIRA_ISSUE_TYPE}' not found. Using: {it['name']} (id={it['id']})")
                return _cached_issue_type_id

        first = issue_types[0]
        _cached_issue_type_id = {"id": first["id"]}
        logger.info(f"Using first available issue type: {first['name']} (id={first['id']})")
        return _cached_issue_type_id

    except Exception as e:
        logger.error(f"Failed to discover issue types: {e}. Falling back to 'Task'.")
        _cached_issue_type_id = {"name": "Task"}
        return _cached_issue_type_id


def create_jira_issue(title: str, description: str, severity: str) -> str:
    url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/2/issue"
    priority_name = PRIORITY_MAP.get(severity, "High")
    issue_type = _discover_issue_type_id()

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": title,
            "description": description,
            "issuetype": issue_type,
            "priority": {"name": priority_name},
        }
    }

    logger.info(f"Creating Jira issue: {title}")
    response = _retry_request("post", url, json=payload)
    data = response.json()
    issue_key = data.get("key", "UNKNOWN")
    logger.info(f"Created Jira issue: {issue_key}")
    return issue_key


def add_comment(issue_key: str, comment_text: str):
    url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/2/issue/{issue_key}/comment"
    payload = {"body": comment_text}
    _retry_request("post", url, json=payload)
    logger.info(f"Added comment to Jira issue {issue_key}")


def check_jira_connectivity() -> dict:
    if not JIRA_API_TOKEN or not JIRA_USER_EMAIL:
        return {"status": "not_configured", "message": "Jira credentials not set in environment."}
    try:
        url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/2/myself"
        response = _retry_request("get", url)
        user_data = response.json()
        return {
            "status": "connected",
            "user": user_data.get("displayName", "Unknown"),
            "email": user_data.get("emailAddress", "Unknown"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
