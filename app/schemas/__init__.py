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
    # Authentication
    'Token', 'TokenPayload',
    'User', 'UserCreate', 'UserUpdate', 'UserBase', 'UserWithPermissions',
    'PasswordReset', 'PasswordChange',

    # Customers
    'Customer', 'CustomerCreate', 'CustomerUpdate', 'CustomerSearchParams', 'CustomerWithSales',

    # Sales
    'Sale', 'SaleCreate', 'SaleUpdate', 'SaleSearchParams', 'SaleWithDetails',
    'SaleItem', 'SaleItemCreate', 'SaleStatusUpdate', 'PaymentUpdate',

    # Materials
    'Material', 'MaterialCreate', 'MaterialUpdate', 'MaterialSearchParams', 'MaterialWithInventory',

    # Projects
    'Project', 'ProjectCreate', 'ProjectUpdate', 'ProjectSearchParams', 'ProjectWithDetails',
    'ProjectComponent', 'ProjectComponentCreate', 'TimelineTask', 'TimelineTaskCreate', 'TimelineTaskUpdate',

    # Inventory
    'Inventory', 'InventoryTransaction', 'InventoryTransactionCreate', 'InventorySearchParams',
    'InventoryAdjustment', 'StockLevelReport',

    # Storage
    'StorageLocation', 'StorageLocationCreate', 'StorageLocationUpdate', 'StorageSearchParams',
    'StorageCell', 'StorageCellCreate', 'StorageAssignment', 'StorageAssignmentCreate',
    'StorageMove', 'StorageMoveCreate', 'StorageOccupancyReport',

    # Suppliers
    'Supplier', 'SupplierCreate', 'SupplierUpdate', 'SupplierSearchParams', 'SupplierWithDetails',
    'SupplierRating', 'SupplierRatingCreate', 'SupplierHistory', 'SupplierHistoryCreate',
    'PurchaseHistorySummary',

    # Tools
    'Tool', 'ToolCreate', 'ToolUpdate', 'ToolSearchParams',
    'ToolMaintenance', 'ToolMaintenanceCreate', 'ToolMaintenanceUpdate',
    'ToolCheckout', 'ToolCheckoutCreate', 'MaintenanceSchedule', 'MaintenanceScheduleItem',

    # Documentation
    'DocumentationResource', 'DocumentationResourceCreate', 'DocumentationResourceUpdate',
    'DocumentationCategory', 'DocumentationCategoryCreate', 'DocumentationCategoryUpdate',
    'DocumentationSearchParams', 'Refund', 'RefundCreate', 'RefundUpdate',
]