"""
Sentinel AI - Duplicate Checker
Prevents duplicate Jira tickets for the same vulnerability.
"""
import psycopg2.extras
import logging
from db import get_db_connection

logger = logging.getLogger(__name__)


def find_existing_issue(repo_name: str, endpoint_or_file: str, vulnerability_type: str) -> str | None:
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT jira_issue_key
            FROM jira_issues
            WHERE repo_name = %s
              AND endpoint_or_file = %s
              AND vulnerability_type = %s
              AND jira_status = 'Open'
            LIMIT 1
        """, (repo_name, endpoint_or_file, vulnerability_type))
        row = cur.fetchone()
        if row:
            logger.info(f"Duplicate found: {row['jira_issue_key']} for {repo_name}/{endpoint_or_file}/{vulnerability_type}")
            return row["jira_issue_key"]
        return None
    except Exception as e:
        logger.error(f"Error checking for duplicate Jira issue: {e}")
        return None
    finally:
        cur.close()
        conn.close()
