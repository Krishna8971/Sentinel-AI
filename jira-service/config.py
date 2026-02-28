"""
Sentinel AI - Jira Notification Service Configuration
Loads all settings from environment variables.
"""
import os

# --- Database ---
POSTGRES_USER = os.getenv("POSTGRES_USER", "sentinel_db_admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "sentinel_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")

# --- Redis / Celery ---
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")

# --- Jira ---
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://your-domain.atlassian.net")
JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SENT")
JIRA_ISSUE_TYPE = os.getenv("JIRA_ISSUE_TYPE", "Bug")

# --- Service ---
POLLING_INTERVAL_SECONDS = int(os.getenv("JIRA_POLLING_INTERVAL", "30"))
SERVICE_PORT = int(os.getenv("JIRA_SERVICE_PORT", "8001"))

# --- Severity thresholds that qualify for Jira ticket creation ---
QUALIFYING_SEVERITIES = {"High", "Critical"}

# --- Priority mapping from Sentinel severity to Jira priority ---
PRIORITY_MAP = {
    "Critical": "Highest",
    "High": "High",
}
