"""
Sentinel AI - Jira Notification Service
FastAPI application entrypoint.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import router as jira_router
from db import init_jira_tables

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sentinel AI - Jira Notification Service",
    description="Post-scan Jira issue creation for Major/Critical vulnerabilities.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jira_router, prefix="/api/jira", tags=["jira"])


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Jira Notification Service...")
    try:
        init_jira_tables()
        logger.info("Jira tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Jira tables: {e}")


@app.get("/")
def read_root():
    return {"service": "Sentinel AI - Jira Notification Service", "status": "running"}
