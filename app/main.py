# File: app/main.py
"""
Main application file for HideSync.

This module initializes the FastAPI application, configures middleware,
and includes API routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.api import api_router
from app.core.config import settings
from app.core.metrics_middleware import MetricsMiddleware
from app.core.events import setup_event_handlers

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for the HideSync leather crafting ERP system",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Set up CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add metrics middleware
app.add_middleware(MetricsMiddleware)


# Add security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        if settings.PRODUCTION:
            # HSTS for production only
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


app.add_middleware(SecurityHeadersMiddleware)

# Set up event handlers
setup_event_handlers(app)

# Include the API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    """
    Root endpoint.

    Returns:
        Basic information about the API
    """
    return {
        "message": "Welcome to HideSync API",
        "version": "1.0.0",
        "docs": f"{settings.API_V1_STR}/docs",
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        Health status of the API
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
    }