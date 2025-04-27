# app/main.py
"""
Main application file for HideSync.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import logging
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict
import os

from app.api.api import api_router
from app.core.config import settings
from app.core.metrics_middleware import MetricsMiddleware
from app.core.events import setup_event_handlers
from scripts.register_material_settings import register_settings

# --- Logging Configuration ---
LOG_LEVEL_NAME = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("app")
logger.setLevel(LOG_LEVEL)

logging.getLogger("app.services.tool_service").setLevel(logging.DEBUG)

logger.info(f"Configured root logger ('{logger.name}') effective level: {logger.getEffectiveLevel()} ({logging.getLevelName(logger.getEffectiveLevel())})")
tool_service_logger = logging.getLogger('app.services.tool_service')
logger.info(f"Configured ToolService logger ('{tool_service_logger.name}') effective level: {tool_service_logger.getEffectiveLevel()} ({logging.getLevelName(tool_service_logger.getEffectiveLevel())})")
# --- END: Logging Configuration ---

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
origins_raw = settings.BACKEND_CORS_ORIGINS or []
origins = [str(origin) for origin in origins_raw if origin]
logger.info(f"Raw CORS origins from settings: {origins_raw}")
logger.info(f"Processed CORS origins: {origins}")

if not origins:
    fallback_origins = [
        "http://localhost:3000", "http://127.0.0.1:3000", "http://192.168.178.37:3000",
        "http://localhost:8001", "http://127.0.0.1:8001", "http://192.168.178.37:8001",
    ]
    logger.warning(
        f"No CORS origins configured in settings, using development fallbacks: {fallback_origins}"
    )
    origins = fallback_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
    max_age=86400,
)

# --- Validation Error Handler ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = jsonable_encoder(exc.errors())
    logger.error(f"--- Request Validation Error ---")
    logger.error(f"URL: {request.method} {request.url}")
    try:
        body = await request.json()
        logger.error(f"Request Body: {json.dumps(body, indent=2)}")
    except json.JSONDecodeError:
        logger.error("Request Body: Could not parse as JSON (or empty body).")
    except Exception as e:
        logger.error(f"Request Body: Error reading body - {e}")
    logger.error(f"Validation Errors:\n{json.dumps(error_details, indent=2)}")
    logger.error(f"--- End Validation Error ---")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": error_details},
    )

# Log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    logger.info(f"-> Request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"<- Response: {response.status_code} ({process_time:.4f}s)")
        return response
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.exception(
            f"!! Error during request processing for {request.method} {request.url.path} ({process_time:.4f}s): {e}"
        )
        raise e

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Add security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method != "OPTIONS":
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            if settings.PRODUCTION and request.url.scheme == "https":
                 response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Set up event handlers
setup_event_handlers(app)

# Register settings on startup
@app.on_event("startup")
async def register_material_settings_on_startup():
    """Register material settings during application startup."""
    try:
        logger.info("Registering material settings...")
        result = register_settings()
        logger.info(f"Successfully registered {len(result) if result else 0} material settings")
    except Exception as e:
        logger.error(f"Error registering material settings: {e}")

# Include the API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Root and Health Check Endpoints
@app.get("/", tags=["Root"], summary="API Root Endpoint")
def read_root():
    """Provides basic API information and links to documentation."""
    return {
        "message": "Welcome to HideSync API",
        "project_name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs_url": app.docs_url,
        "redoc_url": app.redoc_url,
        "openapi_url": app.openapi_url,
    }

@app.get("/health", tags=["Health"], summary="API Health Check")
def health_check():
    """Returns the operational status of the API."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}