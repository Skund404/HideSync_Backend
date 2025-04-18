# File: app/api/api.py
"""
API router configuration for HideSync.

This module defines the main API router and includes all sub-routers
for different domains of the application.
"""

from fastapi import APIRouter


from app.api.endpoints import (
    auth,
    customers,
    materials,
    entity_media,
    projects,
    inventory,
    products,
    sales,
    suppliers,
    tools,
    platform_integrations,
    documentation,
    storage,
    media_assets,
    tags,
    enums,  # <-- Import the enums router
)
from app.core.config import settings

# Create the main API router
api_router = APIRouter()

# --- Include domain-specific routers ---

# Core Features
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(enums.router, prefix="/enums", tags=["Enums"]) # <-- Add the enums router here
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
api_router.include_router(materials.router, prefix="/materials", tags=["Materials"])
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(storage.router, prefix="/storage", tags=["Storage"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(sales.router, prefix="/sales", tags=["Sales"])

# Supporting Features
api_router.include_router(tags.router, prefix="/tags", tags=["Tags"])
api_router.include_router(
    media_assets.router, prefix="/media-assets", tags=["Media Assets"]
)
api_router.include_router(
    entity_media.router, prefix="/entity-media", tags=["Entity Media"] # Changed tag slightly
)
api_router.include_router(
    platform_integrations.router, prefix="/integrations", tags=["Platform Integrations"]
)
api_router.include_router(
    documentation.router, prefix="/documentation", tags=["Documentation"]
)

# --- End of Router Includes ---