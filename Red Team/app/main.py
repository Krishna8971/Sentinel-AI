"""
Sentinel AI Red Team API — main application entry point.
"""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_redis, engine
from app.observability.metrics import metrics_endpoint
from app.observability.telemetry import setup_telemetry

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("sentinel_api_starting", env=settings.environment)

    # Create tables on startup in development (production: use alembic)
    if settings.environment == "development":
        from app.database import Base
        import app.models  # noqa: F401 — ensure models are registered
        from app.core.audit_log import AuditLog  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_created")

    yield

    # Cleanup
    await close_redis()
    await engine.dispose()
    logger.info("sentinel_api_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sentinel AI Red Team API",
        description=(
            "Autonomous red-teaming agent for authentication and authorization "
            "vulnerability detection. Phase 2 of the Sentinel AI platform."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        # Skip auth for health, metrics, and docs endpoints
        public_paths = {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json", "/", "/dashboard", "/analysis", "/redteam", "/favicon.ico"}
        if request.url.path in public_paths or request.url.path.startswith("/assets/") or request.url.path.startswith("/api/"):
            return await call_next(request)

        api_key = request.headers.get(settings.api_key_header, "")
        if api_key != settings.api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API key"},
            )
        return await call_next(request)

    # ── Frontend (built React app) ────────────────────────────────────────────
    static_dir = Path(__file__).parent / "static_frontend"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
        @app.get("/analysis", response_class=HTMLResponse, include_in_schema=False)
        @app.get("/redteam", response_class=HTMLResponse, include_in_schema=False)
        async def frontend():
            return HTMLResponse(content=(static_dir / "index.html").read_text())

    # ── Routes ────────────────────────────────────────────────────────────────

    from app.api.v1.router import router as v1_router
    app.include_router(v1_router)

    # ── Analysis Agent Proxy ──────────────────────────────────────────────────
    ANALYSIS_BACKEND = settings.analysis_backend_url

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
    async def proxy_to_analysis(path: str, request: Request):
        url = f"{ANALYSIS_BACKEND}/api/{path}"
        params = dict(request.query_params)
        body = await request.body()
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ("host", "content-length")}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                params=params,
                content=body,
                headers=headers,
            )
        return Response(content=resp.content, status_code=resp.status_code,
                        media_type=resp.headers.get("content-type"))

    # ── System ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"], summary="Liveness probe")
    async def health():
        return {"status": "ok", "service": "sentinel-ai-red-team", "version": "2.0.0"}

    @app.get("/ready", tags=["System"], summary="Readiness probe")
    async def ready():
        # Check DB connectivity
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception as exc:
            logger.error("readiness_check_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not reachable",
            )

    app.get("/metrics", tags=["System"], summary="Prometheus metrics")(metrics_endpoint)

    # ── Telemetry ────────────────────────────────────────────────────────────
    setup_telemetry(app)

    return app


app = create_app()
