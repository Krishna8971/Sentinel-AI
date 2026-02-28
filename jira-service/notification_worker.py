"""
Sentinel AI - Jira Notification Worker
Celery worker with periodic beat task that polls for new scan results
and creates Jira issues for qualifying vulnerabilities.
"""
import logging
from celery import Celery
from celery.schedules import crontab
from config import CELERY_BROKER_URL, POLLING_INTERVAL_SECONDS
from db import (
    init_jira_tables, get_unprocessed_scan_results,
    mark_scan_processed, save_jira_issue,
)
from severity_filter import filter_qualifying_vulnerabilities
from duplicate_checker import find_existing_issue
from jira_client import (
    create_jira_issue, add_comment,
    build_issue_title, build_issue_description,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

celery_app = Celery("jira_worker", broker=CELERY_BROKER_URL, backend=CELERY_BROKER_URL)

celery_app.conf.update(
    beat_schedule={
        "process-new-findings": {
            "task": "notification_worker.process_new_findings",
            "schedule": float(POLLING_INTERVAL_SECONDS),
        },
    },
    timezone="UTC",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)


@celery_app.on_after_configure.connect
def setup_tables(sender, **kwargs):
    try:
        init_jira_tables()
    except Exception as e:
        logger.error(f"Failed to initialize Jira tables on startup: {e}")


@celery_app.task(bind=True, name="notification_worker.process_new_findings")
def process_new_findings(self):
    logger.info("Polling for new scan results...")
    scan_results = get_unprocessed_scan_results()
    if not scan_results:
        logger.info("No unprocessed scan results found.")
        return {"processed": 0, "tickets_created": 0, "comments_added": 0}

    total_created = 0
    total_comments = 0

    for scan in scan_results:
        scan_id = scan["id"]
        repo_name = scan["repo_name"]
        scan_severity = scan["severity"]
        vulnerabilities = scan["vulnerabilities"]

        logger.info(f"Processing scan {scan_id} for {repo_name} ({len(vulnerabilities)} vulns, severity={scan_severity})")
        qualifying = filter_qualifying_vulnerabilities(vulnerabilities, scan_severity)

        for idx, vuln in qualifying:
            endpoint_or_file = vuln.get("path", vuln.get("file_path", "unknown"))
            vuln_type = vuln.get("vulnerability_type", "Unknown")
            existing_key = find_existing_issue(repo_name, endpoint_or_file, vuln_type)

            if existing_key:
                comment = (
                    f"Sentinel AI detected this vulnerability again.\n"
                    f"Scan ID: {scan_id}\nCommit: {scan.get('commit_hash', 'N/A')}\n"
                    f"Confidence: {vuln.get('confidence', 'N/A')}%\n"
                    f"Reasoning: {vuln.get('reasoning', 'N/A')}"
                )
                try:
                    add_comment(existing_key, comment)
                    total_comments += 1
                except Exception as e:
                    logger.error(f"Failed to add comment to {existing_key}: {e}")
            else:
                title = build_issue_title(scan_severity, vuln_type, repo_name)
                description = build_issue_description(vuln, scan)
                try:
                    issue_key = create_jira_issue(title, description, scan_severity)
                    save_jira_issue(
                        scan_result_id=scan_id, finding_index=idx, repo_name=repo_name,
                        vulnerability_type=vuln_type, endpoint_or_file=endpoint_or_file,
                        jira_issue_key=issue_key, severity=scan_severity,
                    )
                    total_created += 1
                except Exception as e:
                    logger.error(f"Failed to create Jira issue for scan {scan_id}, vuln {idx}: {e}")

        mark_scan_processed(scan_id)

    result = {"processed": len(scan_results), "tickets_created": total_created, "comments_added": total_comments}
    logger.info(f"Processing complete: {result}")
    return result


@celery_app.task(bind=True, name="notification_worker.trigger_processing")
def trigger_processing(self):
    return process_new_findings()
