import logging

import httpx
from fastapi import APIRouter

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    admin_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.admin_base_url}/health")
            admin_status = "ok" if resp.status_code == 200 else "unhealthy"
    except Exception:
        admin_status = "unreachable"
        logger.warning("admin health check failed: base_url=%s", settings.admin_base_url)

    return {
        "status": "ok" if admin_status == "ok" else "degraded",
        "admin": admin_status,
        "model": settings.llm_model,
    }
