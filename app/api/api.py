# app/api/api.py

from fastapi import APIRouter

from app.api.endpoints import (
    materials,
    # Import existing endpoints
    analytics,
    annotations,
    auth,
    components,
    customers,
    documentation,
    entity_media,
    enums,
    inventory,
    media_assets,
    patterns,
    picking_list,
    platform_integrations,
    presets,
    products,
    project_templates,
    projects,
    purchases,
    qrcode,
    recurring_projects,
    refunds,
    reports,
    roles,
    sales,
    settings,
    shipments,
    storage,
    suppliers,
    tags,
    tools,
    translations,
    users,
    webhooks,
    workflows,
    # Import new dynamic material endpoints
    material_types,
    property_definitions,
    dynamic_materials,
)

api_router = APIRouter()

# Include existing routers
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(annotations.router, prefix="/annotations", tags=["Annotations"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(components.router, prefix="/components", tags=["Components"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(documentation.router, prefix="/documentation", tags=["Documentation"])
api_router.include_router(entity_media.router, prefix="/entity-media", tags=["Entity Media"])
api_router.include_router(enums.router, prefix="/enums", tags=["Enums"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(materials.router, prefix="/materials", tags=["Legacy Materials"])
api_router.include_router(media_assets.router, prefix="/media-assets", tags=["Media Assets"])
api_router.include_router(patterns.router, prefix="/patterns", tags=["Patterns"])
api_router.include_router(picking_list.router, prefix="/picking-lists", tags=["Picking Lists"])
api_router.include_router(platform_integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(project_templates.router, prefix="/project-templates", tags=["Project Templates"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(purchases.router, prefix="/purchases", tags=["Purchases"])
api_router.include_router(qrcode.router, prefix="/qrcode", tags=["QR Code"])
api_router.include_router(recurring_projects.router, prefix="/recurring-projects", tags=["Recurring Projects"])
api_router.include_router(refunds.router, prefix="/refunds", tags=["Refunds"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(sales.router, prefix="/sales", tags=["Sales"])
api_router.include_router(shipments.router, prefix="/shipments", tags=["Shipments"])
api_router.include_router(storage.router, prefix="/storage", tags=["Storage"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
api_router.include_router(tags.router, prefix="/tags", tags=["Tags"])
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])

# Include new dynamic material routers
api_router.include_router(material_types.router, prefix="/material-types", tags=["Material Types"])
api_router.include_router(property_definitions.router, prefix="/property-definitions", tags=["Property Definitions"])
api_router.include_router(dynamic_materials.router, prefix="/dynamic-materials", tags=["Dynamic Materials"])
api_router.include_router(presets.router, prefix="/presets", tags=["presets"])
api_router.include_router(
    workflows.router,
    prefix="/workflows",
    tags=["workflows"]
)
api_router.include_router(
    translations.router,
    prefix="/translations",
    tags=["translations"],
    responses={
        404: {"description": "Translation not found"},
        400: {"description": "Invalid translation data"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    }
)