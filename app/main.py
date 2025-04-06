# File: app/main.py
"""
Main application file for HideSync.

This module initializes the FastAPI application, configures middleware,
includes API routers, and sets up global exception handlers.
"""

from fastapi import FastAPI, Request, status # Add status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError # Import this
from fastapi.responses import JSONResponse # Import this
from fastapi.encoders import jsonable_encoder # Import this
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
logger = logging.getLogger("fastapi") # Use "fastapi" or your project name

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
# Ensure origins are strings, handle potential None or empty list
origins_raw = settings.BACKEND_CORS_ORIGINS or []
origins = [str(origin) for origin in origins_raw if origin] # Filter out empty/None
logger.info(f"Raw CORS origins from settings: {origins_raw}")
logger.info(f"Processed CORS origins: {origins}")

# If no origins are configured, allow localhost and specific dev IP as fallback
if not origins:
    # Use explicit IP and localhost for development
    fallback_origins = [
        "http://localhost:3000",          # Local frontend dev
        "http://127.0.0.1:3000",         # Alternative local frontend dev
        "http://192.168.178.37:3000",    # Specific dev machine access
        # Add local backend URLs if needed for testing directly
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://192.168.178.37:8001",
        ]
    logger.warning(f"No CORS origins configured in settings, using development fallbacks: {fallback_origins}")
    origins = fallback_origins

# Add the CORS middleware FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Use the processed origins list
    allow_credentials=True,
    allow_methods=["*"], # Allows all standard methods
    allow_headers=["*"], # Allows all headers
    expose_headers=["Content-Disposition", "X-Total-Count"], # Example custom headers
    max_age=86400, # Cache preflight response for 24 hours
)

# --- NEW: Add Validation Error Handler ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles Pydantic RequestValidationErrors, logging details and returning 422.
    """
    error_details = jsonable_encoder(exc.errors()) # Use jsonable_encoder for complex types
    # Log the detailed validation errors for backend debugging
    logger.error(f"--- Request Validation Error ---")
    logger.error(f"URL: {request.method} {request.url}")
    try:
        # Attempt to read and log the request body
        body = await request.json()
        # Be mindful of logging sensitive data in production
        logger.error(f"Request Body: {json.dumps(body, indent=2)}")
    except json.JSONDecodeError:
        logger.error("Request Body: Could not parse as JSON (or empty body).")
    except Exception as e:
        logger.error(f"Request Body: Error reading body - {e}")

    logger.error(f"Validation Errors:\n{json.dumps(error_details, indent=2)}")
    logger.error(f"--- End Validation Error ---")

    # Return the details in the response for frontend debugging/handling
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        # Return structure consistent with FastAPI's default
        content={"detail": error_details},
    )
# --- END: Validation Error Handler ---


# Log requests AFTER CORS middleware and BEFORE other processing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs incoming request method/URL and outgoing response code."""
    # Skip logging OPTIONS requests if they are too noisy
    # if request.method == "OPTIONS":
    #     return await call_next(request)

    start_time = datetime.now()
    logger.info(f"-> Request: {request.method} {request.url}")
    # Log headers if needed for debugging (be careful with sensitive info)
    # logger.debug(f"   Headers: {dict(request.headers)}")

    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"<- Response: {response.status_code} ({process_time:.4f}s)")
        # Log response headers if needed
        # logger.debug(f"   Response Headers: {dict(response.headers)}")
        return response
    except Exception as e:
        # Log unhandled exceptions that occur during request processing
        process_time = (datetime.now() - start_time).total_seconds()
        logger.exception(f"!! Error during request processing for {request.method} {request.url} ({process_time:.4f}s): {e}")
        # Re-raise the exception so FastAPI's default handler can return a 500 response
        raise e


# Add metrics middleware
app.add_middleware(MetricsMiddleware)


# Add security headers middleware (generally placed after logging/metrics but before routing logic)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add common security headers to responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers - Apply even to OPTIONS for consistency? Check spec.
        # Usually applied to actual content responses.
        if request.method != "OPTIONS": # Apply only to non-preflight requests
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            # response.headers["X-XSS-Protection"] = "1; mode=block" # Deprecated in modern browsers
            # Consider Content-Security-Policy instead for more robust protection
            # response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none';"

            # Referrer-Policy is often useful
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            if settings.PRODUCTION:
                # HSTS for production only, over HTTPS
                if request.url.scheme == "https":
                    response.headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains; preload" # Added preload
                    )

        return response

app.add_middleware(SecurityHeadersMiddleware)


# Set up event handlers (e.g., for startup/shutdown)
# Ensure this doesn't interfere with middleware order if it adds routes/etc.
setup_event_handlers(app)


# Include the API router - This should generally be one of the last things added
app.include_router(api_router, prefix=settings.API_V1_STR)


# Root and Health Check Endpoints
@app.get("/", tags=["Root"], summary="API Root Endpoint")
def read_root():
    """Provides basic API information and links to documentation."""
    return {
        "message": "Welcome to HideSync API",
        "project_name": settings.PROJECT_NAME,
        "version": "1.0.0", # Consider making version dynamic
        "environment": settings.ENVIRONMENT,
        "docs_url": app.docs_url,
        "redoc_url": app.redoc_url,
        "openapi_url": app.openapi_url,
    }

@app.get("/health", tags=["Health"], summary="API Health Check")
def health_check():
    """Returns the operational status of the API."""
    # In a real app, you might check DB connection, external services, etc.
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# Example of how to run (if this file is executed directly)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")