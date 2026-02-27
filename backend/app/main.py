from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .api import github, dashboard, scan
from .models.scan_result import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Sentinel AI")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up and initializing database...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github.router, prefix="/api/github", tags=["github"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(scan.router, prefix="/api/scan", tags=["scan"])

@app.get('/')
def read_root():
    return {"status": "Sentinel AI Auth API is running"}
