# File: app/api/api.py
"""
Main API router configuration for HideSync.

This module sets up the main API router and includes all endpoint routers
for different resources in the application.
"""

from fastapi import APIRouter

# Import all endpoint routers
from app.api.endpoints import (
    projects,
    project_templates,
    customers,
    sales,
    components,
    materials,
    inventory,
    patterns,
    users,
    auth,
    reports,
    recurring_projects,
    roles,
    platform_integrations,
    picking_list,
    shipments,
    suppliers,
    storage,
    tools,
    refunds,
    documentation,
    webhooks,
    annotations
)

# Create the main API router
api_router = APIRouter()

# Include routers with appropriate prefixes
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(project_templates.router, prefix="/project-templates", tags=["project-templates"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(sales.router, prefix="/sales", tags=["sales"])
api_router.include_router(components.router, prefix="/components", tags=["components"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(patterns.router, prefix="/patterns", tags=["patterns"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(recurring_projects.router, prefix="/recurring-projects", tags=["recurring-projects"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(platform_integrations.router, prefix="/platform-integrations", tags=["platform-integrations"])
api_router.include_router(picking_list.router, prefix="/picking-lists", tags=["picking-lists"])
api_router.include_router(shipments.router, prefix="/shipments", tags=["shipments"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(refunds.router, prefix="/refunds", tags=["refunds"])
api_router.include_router(documentation.router, prefix="/documentation", tags=["documentation"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(annotations.router, prefix="/annotations", tags=["annotations"])

