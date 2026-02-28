"""
Sentinel AI - Jira Service Database Layer
Manages jira_issues and jira_integration_config tables.
Does NOT modify any existing Sentinel tables.
"""
import psycopg2
import psycopg2.extras
import json
import logging
from datetime import datetime
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST
)

logger = logging.getLogger(__name__)


def get_db_connection():
    """Returns a new psycopg2 connection."""
    return psycopg2.connect(
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
        host=POSTGRES_HOST,
    )


def init_jira_tables():
    """
    Creates the Jira-specific tables if they don't exist.
    Does NOT touch scan_results or any other existing table.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jira_integration_config (
                id SERIAL PRIMARY KEY,
                base_url VARCHAR(512),
                project_key VARCHAR(50),
                api_token TEXT,
                user_email VARCHAR(255),
                issue_type VARCHAR(100) DEFAULT 'Bug',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jira_issues (
                id SERIAL PRIMARY KEY,
                scan_result_id INTEGER,
                finding_index INTEGER,
                repo_name VARCHAR(255),
                vulnerability_type VARCHAR(255),
                endpoint_or_file VARCHAR(512),
                jira_issue_key VARCHAR(50),
                jira_status VARCHAR(50) DEFAULT 'Open',
                severity VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_jira_issues_lookup
            ON jira_issues (repo_name, endpoint_or_file, vulnerability_type, jira_status)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_jira_issues_scan
            ON jira_issues (scan_result_id, finding_index)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jira_processed_scans (
                id SERIAL PRIMARY KEY,
                scan_result_id INTEGER UNIQUE,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("Jira tables initialized successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize Jira tables: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def get_unprocessed_scan_results():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT sr.id, sr.repo_name, sr.commit_hash, sr.timestamp,
                   sr.auth_integrity_score, sr.severity, sr.vulnerabilities
            FROM scan_results sr
            LEFT JOIN jira_processed_scans jps ON sr.id = jps.scan_result_id
            WHERE jps.id IS NULL
              AND sr.severity IN ('High', 'Critical')
            ORDER BY sr.timestamp ASC
            LIMIT 50
        """)
        rows = cur.fetchall()
        results = []
        for row in rows:
            row = dict(row)
            vulns = row.get("vulnerabilities")
            if isinstance(vulns, str):
                try:
                    vulns = json.loads(vulns)
                except Exception:
                    vulns = []
            row["vulnerabilities"] = vulns or []
            results.append(row)
        return results
    except Exception as e:
        logger.error(f"Error fetching unprocessed scan results: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def mark_scan_processed(scan_result_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO jira_processed_scans (scan_result_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (scan_result_id,),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking scan {scan_result_id} as processed: {e}")
    finally:
        cur.close()
        conn.close()


def save_jira_issue(scan_result_id, finding_index, repo_name, vulnerability_type,
                    endpoint_or_file, jira_issue_key, severity):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO jira_issues
                (scan_result_id, finding_index, repo_name, vulnerability_type,
                 endpoint_or_file, jira_issue_key, severity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (scan_result_id, finding_index, repo_name, vulnerability_type,
              endpoint_or_file, jira_issue_key, severity))
        conn.commit()
        logger.info(f"Saved Jira issue {jira_issue_key} for scan {scan_result_id}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving Jira issue: {e}")
    finally:
        cur.close()
        conn.close()


def get_all_jira_issues(limit=100):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT id, scan_result_id, finding_index, repo_name,
                   vulnerability_type, endpoint_or_file, jira_issue_key,
                   jira_status, severity, created_at, updated_at
            FROM jira_issues
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching Jira issues: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_jira_issues_for_scan(scan_result_id: int):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT id, scan_result_id, finding_index, repo_name,
                   vulnerability_type, endpoint_or_file, jira_issue_key,
                   jira_status, severity, created_at, updated_at
            FROM jira_issues
            WHERE scan_result_id = %s
            ORDER BY created_at DESC
        """, (scan_result_id,))
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching Jira issues for scan {scan_result_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_jira_stats():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE severity = 'Critical') AS total_critical,
                COUNT(*) FILTER (WHERE severity = 'High') AS total_major,
                COUNT(*) FILTER (WHERE jira_status = 'Open') AS open_tickets,
                COUNT(*) FILTER (WHERE jira_status NOT IN ('Open')) AS resolved_tickets,
                COUNT(*) AS total_tickets
            FROM jira_issues
        """)
        row = cur.fetchone()
        return dict(row) if row else {
            "total_critical": 0, "total_major": 0,
            "open_tickets": 0, "resolved_tickets": 0, "total_tickets": 0,
        }
    except Exception as e:
        logger.error(f"Error fetching Jira stats: {e}")
        return {
            "total_critical": 0, "total_major": 0,
            "open_tickets": 0, "resolved_tickets": 0, "total_tickets": 0,
        }
    finally:
        cur.close()
        conn.close()
