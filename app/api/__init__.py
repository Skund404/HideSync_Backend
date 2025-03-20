# File: app/api/__init__.py
"""
API package for HideSync.

This package contains the API layer for the HideSync application,
including endpoints, dependencies, and routing configuration.
"""

from app.api import deps, endpoints
from app.api.api import api_router