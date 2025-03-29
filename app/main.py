# File: app/main.py
"""
Main application file for HideSync.

This module initializes the FastAPI application, configures middleware,
and includes API routers.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from app.api.api import api_router
from app.core.config import settings
from app.core.metrics_middleware import MetricsMiddleware
from app.core.events import setup_event_handlers

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi")

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for the HideSync leather crafting ERP system",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Set up CORS - THIS MUST BE THE FIRST MIDDLEWARE
# Debug the CORS origins setting
origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
logger.info(f"Configured CORS origins: {origins}")

# If no origins are configured, allow localhost:3000 as fallback
if not origins:
    fallback_origins = ["http://localhost:3000", "http://192.168.178.37:3000"]
    logger.warning(f"No CORS origins configured, using fallbacks: {fallback_origins}")
    origins = fallback_origins

# Add the CORS middleware FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # 24 hours
)


# Log requests AFTER CORS middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    # For OPTIONS requests, log the headers
    if request.method == "OPTIONS":
        logger.debug(f"OPTIONS request headers: {dict(request.headers)}")
    response = await call_next(request)
    logger.info(f"Outgoing response: {response.status_code}")
    return response


# Add metrics middleware
app.add_middleware(MetricsMiddleware)


# Add security headers middleware (AFTER CORS)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    async def dispatch(self, request, call_next):
        # Skip preflight OPTIONS requests for CORS
        if request.method == "OPTIONS":
            response = await call_next(request)
            return response

        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        if settings.PRODUCTION:
            # HSTS for production only
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

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