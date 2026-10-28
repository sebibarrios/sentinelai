import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.csrf import RequireCustomHeaderMiddleware
from app.core.errors import register_error_handlers
from app.core.headers import SecurityHeadersMiddleware
from app.core.proxy_auth import RequireProxySecretMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO)

    app = FastAPI(
        title="SentinelAI API",
        version="0.1.0",
        description="Security log ingestion, threat detection, incident management, AI analysis.",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
    )

    # In production the browser reaches the API through the Next.js proxy (same origin),
    # so CORS only matters for local development tools.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )

    app.add_middleware(RequireCustomHeaderMiddleware)
    app.add_middleware(RequireProxySecretMiddleware)
    # Added last so it wraps everything, including error and CORS responses.
    app.add_middleware(SecurityHeadersMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
