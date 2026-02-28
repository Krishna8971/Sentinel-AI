"""
Minimal Prometheus metrics endpoint stub.
"""
from fastapi import Request
from fastapi.responses import PlainTextResponse


async def metrics_endpoint(request: Request):
    """Expose basic Prometheus-compatible metrics."""
    return PlainTextResponse(
        "# HELP sentinel_redteam_up Red Team service is up\n"
        "# TYPE sentinel_redteam_up gauge\n"
        "sentinel_redteam_up 1\n"
    )
