"""
POS Service — Health Check Endpoint.
Used for monitoring, Docker health checks, and load balancer probes.
"""
from fastapi import APIRouter
from sqlalchemy import text
from models.database import engine
from config import config
from loguru import logger

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Returns service status and basic info."""
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "pos-service",
        "pier": config.PIER_NAME,
        "database": "connected" if db_ok else "error",
    }
