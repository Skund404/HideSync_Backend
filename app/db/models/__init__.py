# File: app/db/models/__init__.py
"""
Initializes the models package for SQLAlchemy declarative base.

This file imports all necessary model classes and enums into the
`app.db.models` namespace. This ensures that SQLAlchemy's metadata
is populated with all table definitions when `Base.metadata.create_all()`
is called.
"""

# Import the Base for declarative models
from app.db.models.base import Base

# Import all Enums defined in enums.py
from app.db.models.enums import (
    SaleStatus,
    PaymentStatus,
    PurchaseStatus,
    CustomerStatus,
    CustomerTier,
    CustomerSource,
    InventoryStatus,
    MaterialType,
    MaterialQualityGrade,
    HardwareType,
    HardwareMaterialEnum,  # Correct import name
    HardwareFinish,
    LeatherType,
    LeatherFinish,
    ProjectType,
    ProjectStatus,
    SkillLevel,
    ComponentType,
    ToolCategory,
    EdgeFinishType,
    TransactionType,
    InventoryAdjustmentType,
    SupplierStatus,
    StorageLocationType,
    MeasurementUnit,
    QualityGrade,
    PickingListStatus,
    ToolListStatus,
    CommunicationChannel,
    CommunicationType,
    MaterialStatus,
    PatternFileType,
    FulfillmentStatus,
    UserRole,
)

# Create alias for backward compatibility
HardwareMaterial = HardwareMaterialEnum

# Import Enums defined within documentation.py
from app.db.models.documentation import (
    DocumentationType,
    DocumentationStatus,
)

# Import Core Models
from app.db.models.user import User
from app.db.models.role import Role, Permission
from app.db.models.password_reset import PasswordResetToken
from app.db.models.annotation import Annotation

# Import Business Entity Models
from app.db.models.customer import Customer
from app.db.models.supplier import Supplier
from app.db.models.supplier_history import SupplierHistory
from app.db.models.supplier_rating import SupplierRating

# Import Inventory & Material Models
from app.db.models.material import (
    Material,
    LeatherMaterial,
    HardwareMaterial as HardwareMaterialModel,  # Alias class to avoid enum conflict
    SuppliesMaterial,
)
from app.db.models.inventory import Inventory, InventoryTransaction
from app.db.models.product import Product
from app.db.models.storage import (
    StorageLocation,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.db.models.tool import Tool, ToolMaintenance, ToolCheckout

# Import Design & Project Models
from app.db.models.pattern import Pattern  # Only Pattern is in pattern.py
from app.db.models.component import Component, ComponentMaterial
from app.db.models.project import (
    Project,
    ProjectComponent,
    ProjectTemplate,  # Correctly imported from project.py
    ProjectTemplateComponent,  # Correctly imported from project.py
)
from app.db.models.timeline_task import TimelineTask
from app.db.models.recurring_project import (
    RecurrencePattern,
    RecurringProject,
    GeneratedProject,
)

# Import Sales & Purchase Models
from app.db.models.sales import Sale, SaleItem
from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.shipment import Shipment
from app.db.models.refund import Refund

# Import Operational Models
from app.db.models.picking_list import PickingList, PickingListItem
from app.db.models.platform_integration import PlatformIntegration, SyncEvent
from app.db.models.communication import CustomerCommunication

# Import Media & Asset Management Models
from app.db.models.media_asset import MediaAsset
from app.db.models.entity_media import EntityMedia  # Add this import
from app.db.models.tag import Tag
from app.db.models.association_media import MediaAssetTag

# Import Documentation & Utility Models
from app.db.models.documentation import (
    DocumentationCategory,
    DocumentationResource,
    ApplicationContext,
    ContextualHelpMapping,
    # Enums already imported above
)
from app.db.models.file_metadata import FileMetadata

# Define __all__ for explicit namespace export
__all__ = [
    # Base
    "Base",
    # Core Models
    "User",
    "Role",
    "Permission",
    "PasswordResetToken",
    "Annotation",
    # Business Entity Models
    "Customer",
    "Supplier",
    "SupplierHistory",
    "SupplierRating",
    # Inventory & Material Models
    "Material",
    "LeatherMaterial",
    "HardwareMaterialModel",  # Use aliased class name
    "SuppliesMaterial",
    "Inventory",
    "InventoryTransaction",
    "Product",
    "StorageLocation",
    "StorageCell",
    "StorageAssignment",
    "StorageMove",
    "Tool",
    "ToolMaintenance",
    "ToolCheckout",
    # Design & Project Models
    "Pattern",
    "Component",
    "ComponentMaterial",
    "Project",
    "ProjectComponent",
    "ProjectTemplate",  # Correctly exported
    "ProjectTemplateComponent",  # Correctly exported
    "TimelineTask",
    "RecurrencePattern",
    "RecurringProject",
    "GeneratedProject",
    # Sales & Purchase Models
    "Sale",
    "SaleItem",
    "Purchase",
    "PurchaseItem",
    "Shipment",
    "Refund",
    # Operational Models
    "PickingList",
    "PickingListItem",
    "PlatformIntegration",
    "SyncEvent",
    "CustomerCommunication",
    # Media & Asset Management Models
    "MediaAsset",
    "EntityMedia",  # Add this to __all__
    "Tag",
    "MediaAssetTag",
    # Documentation & Utility Models
    "DocumentationCategory",
    "DocumentationResource",
    "ApplicationContext",
    "ContextualHelpMapping",
    "FileMetadata",
    # Enums (Exporting all imported enums)
    "SaleStatus",
    "PaymentStatus",
    "PurchaseStatus",
    "CustomerStatus",
    "CustomerTier",
    "CustomerSource",
    "InventoryStatus",
    "MaterialType",
    "MaterialQualityGrade",
    "HardwareType",
    "HardwareMaterial",  # Still export HardwareMaterial for backward compatibility
    "HardwareMaterialEnum",  # Also export the original enum name
    "HardwareFinish",
    "LeatherType",
    "LeatherFinish",
    "ProjectType",
    "ProjectStatus",
    "SkillLevel",
    "ComponentType",
    "ToolCategory",
    "EdgeFinishType",
    "TransactionType",
    "InventoryAdjustmentType",
    "SupplierStatus",
    "StorageLocationType",
    "MeasurementUnit",
    "QualityGrade",
    "PickingListStatus",
    "ToolListStatus",
    "CommunicationChannel",
    "CommunicationType",
    "MaterialStatus",
    "PatternFileType",
    "FulfillmentStatus",
    "UserRole",
    "DocumentationType",
    "DocumentationStatus",
]