import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import audit, health, sessions
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.database import initialize_database
from app.graphs.checkpointer import close_checkpointer, get_checkpointer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    await get_checkpointer()
    try:
        yield
    finally:
        await close_checkpointer()


_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    window = 60.0
    timestamps = _rate_limit_store[client_ip]
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < window]
    if len(_rate_limit_store[client_ip]) >= settings.rate_limit_per_minute:
        return False
    _rate_limit_store[client_ip].append(now)
    return True


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Agent service orchestrating read-only admin capabilities via LangGraph.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path == "/api/agent/sessions" and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            if not _check_rate_limit(client_ip):
                logger.warning("rate limit exceeded: ip=%s", client_ip)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "RATE_LIMITED", "retryAfter": 60},
                )
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(sessions.router, prefix="/api/agent", tags=["agent-sessions"])
    app.include_router(audit.router, prefix="/api/agent", tags=["agent-audit"])

    return app


app = create_app()
