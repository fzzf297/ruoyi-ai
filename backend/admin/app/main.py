from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin_auth, admin_interfaces, admin_pages, admin_projects, app_public, health
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Independent management backend for page and app interface configuration.",
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

    app.include_router(health.router)
    app.include_router(admin_auth.router, prefix="/api/admin/auth", tags=["admin-auth"])
    app.include_router(admin_projects.router, prefix="/api/admin/projects", tags=["admin-projects"])
    app.include_router(admin_pages.router, prefix="/api/admin", tags=["admin-pages"])
    app.include_router(admin_interfaces.router, prefix="/api/admin", tags=["admin-interfaces"])
    app.include_router(app_public.router, prefix="/api/app", tags=["app-config"])

    return app


app = create_app()
