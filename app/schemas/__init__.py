# File: app/schemas/__init__.py
"""
Schemas package for the HideSync API.

This module exports Pydantic models used for request validation,
response serialization, and data transfer throughout the application.
It directly imports all classes from the compatibility layer.
"""

# Import all classes from the compatibility layer
from .compatibility import *

# Required for proper IDE imports and type hints
__all__ = [
    "Token",
    "TokenPayload",
    "TokenRefresh",  # Add this
    "User",
    "UserCreate",
    "UserUpdate",
    "UserBase",
    "UserWithPermissions",
    "UserPasswordReset",  # Add this
    "UserPasswordChange",  # Add this
    "UserPasswordResetConfirm",  # Add this
    "UserListParams",
    # "PasswordReset",  # Remove this as it's in user.py
    # "PasswordChange",  # Remove this as it's in user.py
    # ... (rest of your existing schema names)
    "Customer",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerSearchParams",
    "CustomerWithSales",
    "Sale",
    "SaleCreate",
    "SaleUpdate",
    "SaleSearchParams",
    "SaleWithDetails",
    "SaleItem",
    "SaleItemCreate",
    "SaleStatusUpdate",
    "PaymentUpdate",
    "Material",
    "MaterialCreate",
    "MaterialUpdate",
    "MaterialSearchParams",
    "MaterialWithInventory",
    "ProjectComponent",
    "ProjectComponentCreate",
    "TimelineTask",
    "TimelineTaskCreate",
    "TimelineTaskUpdate",
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectSearchParams",
    "ProjectWithDetails",
    "Inventory",
    "InventoryTransaction",
    "InventoryTransactionCreate",
    "InventorySearchParams",
    "InventoryAdjustment",
    "StockLevelReport",
    "StorageLocation",
    "StorageLocationCreate",
    "StorageLocationUpdate",
    "StorageCell",
    "StorageCellCreate",
    "StorageAssignment",
    "StorageAssignmentCreate",
    "StorageMove",
    "StorageMoveCreate",
    "StorageSearchParams",
    "StorageOccupancyReport",
    "Supplier",
    "SupplierCreate",
    "SupplierUpdate",
    "SupplierRating",
    "SupplierRatingCreate",
    "SupplierHistory",
    "SupplierHistoryCreate",
    "SupplierSearchParams",
    "SupplierWithDetails",
    "PurchaseHistorySummary",
    "Tool",
    "ToolCreate",
    "ToolUpdate",
    "ToolMaintenance",
    "ToolMaintenanceCreate",
    "ToolMaintenanceUpdate",
    "ToolCheckout",
    "ToolCheckoutCreate",
    "ToolSearchParams",
    "MaintenanceScheduleItem",
    "MaintenanceSchedule",
    "DocumentationResource",
    "DocumentationResourceCreate",
    "DocumentationResourceUpdate",
    "DocumentationCategory",
    "DocumentationCategoryCreate",
    "DocumentationCategoryUpdate",
    "DocumentationSearchParams",
    "Refund",
    "RefundCreate",
    "RefundUpdate",
    "ComponentBase",
    "ComponentCreate",
    "ComponentUpdate",
    "ComponentMaterialBase",
    "ComponentMaterialCreate",
    "ComponentMaterialResponse",
    "ComponentResponse",
    "ComponentListResponse",
    "PatternBase",
    "PatternCreate",
    "PatternUpdate",
    "PatternResponse",
    "PatternListResponse",
    "ProjectTemplateComponentBase",
    "ProjectTemplateComponentCreate",
    "ProjectTemplateComponentResponse",
    "ProjectTemplateBase",
    "ProjectTemplateCreate",
    "ProjectTemplateResponse",
    "PurchaseItemBase",
    "PurchaseItemCreate",
    "PurchaseItemUpdate",
    "PurchaseItemResponse",
    "PurchaseItemListResponse",
    "PurchaseReceiveItemData",
    "PurchaseReceiveData",
    "PurchaseBase",
    "PurchaseCreate",
    "PurchaseUpdate",
    "PurchaseResponse",
    "PurchaseListResponse",
]
