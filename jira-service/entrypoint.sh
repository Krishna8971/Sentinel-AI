#!/bin/bash
set -e

echo "Starting Sentinel AI Jira Notification Service..."

# Start Celery beat + worker in background
celery -A notification_worker.celery_app worker --beat --loglevel=info &

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8001
