# File: app/core/metrics_middleware.py

from typing import Callable, Dict, Any
import time
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import (
    gauge,
    counter,
    histogram,
    timer,
    ACTIVE_REQUESTS,
    REQUEST_LATENCY,
    ERROR_COUNT,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect metrics for HTTP requests.

    Tracks request counts, durations, error rates, etc.
    """

    def __init__(self, app: ASGIApp, exclude_paths: list[str] = None):
        """
        Initialize metrics middleware.

        Args:
            app: ASGI application
            exclude_paths: List of paths to exclude from metrics
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/metrics", "/healthz", "/favicon.ico"]

        # Initialize request metrics
        self.request_counter = counter("http.requests.total", "Total HTTP requests")
        self.request_timer = timer(
            "http.requests.duration", "HTTP request duration in seconds"
        )
        self.status_counters = {}

        # Request size metrics
        self.request_size = histogram(
            "http.requests.size",
            "HTTP request size in bytes",
            buckets=[64, 256, 1024, 4096, 16384, 65536, 262144, 1048576],
        )

        # Response size metrics
        self.response_size = histogram(
            "http.responses.size",
            "HTTP response size in bytes",
            buckets=[64, 256, 1024, 4096, 16384, 65536, 262144, 1048576],
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process an incoming request and collect metrics.

        Args:
            request: HTTP request
            call_next: Next middleware in chain

        Returns:
            HTTP response
        """
        # Skip metrics for excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)

        # Track metrics
        start_time = time.time()

        # Increment active requests
        ACTIVE_REQUESTS.increment()

        # Create tags for this request
        tags = {"method": request.method, "path": path}

        # Increment request counter with tags
        self.request_counter.increment()

        # Track request size
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                self.request_size.observe(int(content_length))
            except (ValueError, TypeError):
                pass

        try:
            # Process request
            response = await call_next(request)

            # Add status code to tags
            status_code = response.status_code
            tags["status_code"] = str(status_code)

            # Track status code
            status_class = f"{status_code // 100}xx"
            if status_class not in self.status_counters:
                self.status_counters[status_class] = counter(
                    f"http.requests.status.{status_class}",
                    f"HTTP {status_class} responses",
                )
            self.status_counters[status_class].increment()

            if status_code >= 400:
                # Count errors (4xx and 5xx)
                ERROR_COUNT.increment()

            # Track response size
            resp_content_length = response.headers.get("content-length")
            if resp_content_length:
                try:
                    self.response_size.observe(int(resp_content_length))
                except (ValueError, TypeError):
                    pass

            return response
        except Exception as e:
            # Count unhandled exceptions
            ERROR_COUNT.increment()

            # Add error tag
            tags["error"] = type(e).__name__

            # Re-raise exception
            raise
        finally:
            # Record request duration
            duration = time.time() - start_time
            REQUEST_LATENCY.observe(duration)
            self.request_timer.observe(duration)

            # Decrement active requests
            ACTIVE_REQUESTS.decrement()


def add_metrics_middleware(app: FastAPI) -> None:
    """
    Add metrics middleware to FastAPI application.

    Args:
        app: FastAPI application
    """
    app.add_middleware(MetricsMiddleware)


def add_metrics_endpoint(app: FastAPI, endpoint: str = "/metrics") -> None:
    """
    Add metrics endpoint to FastAPI application.

    Args:
        app: FastAPI application
        endpoint: Endpoint path for metrics
    """

    @app.get(endpoint)
    async def metrics():
        """Endpoint for exposing Prometheus metrics."""
        # Get Prometheus exporter if available
        from app.core.metrics import get_registry

        registry = get_registry()
        for exporter in registry._exporters:
            if hasattr(exporter, "get_metrics_text"):
                return Response(
                    content=exporter.get_metrics_text(), media_type="text/plain"
                )

        # Fall back to JSON if no Prometheus exporter
        metrics_list = [m.to_dict() for m in registry.get_all_metrics()]
        return {"metrics": metrics_list}


def setup_metrics(app: FastAPI) -> None:
    """
    Set up metrics collection for FastAPI application.

    Args:
        app: FastAPI application
    """
    add_metrics_middleware(app)
    add_metrics_endpoint(app)
