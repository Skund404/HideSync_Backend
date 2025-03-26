# File: app/db/models/__init__.py

from app.db.models.base import Base
from app.db.models.enums import SkillLevel, ProjectStatus, ProjectType  # Ensure correct Enums are imported first
from app.db.models.user import User  # Ensure users are imported early

# Import the Sale models *before* Project models
from app.db.models.sales import Sale, SaleItem

# Non-relational models
from app.db.models.communication import CustomerCommunication
from app.db.models.component import Component, ComponentMaterial
from app.db.models.customer import Customer
from app.db.models.documentation import (
    DocumentationCategory,
    DocumentationResource,
)
from app.db.models.file_metadata import FileMetadata
from app.db.models.inventory import Inventory, InventoryTransaction, Product

# Import Pattern from its module (if Pattern truly belongs there)
from app.db.models.pattern import Pattern

# Import project models from project.py (including ProjectTemplate models)
from app.db.models.project import (
    Project,
    ProjectComponent,
    ProjectTemplate,
    ProjectTemplateComponent
)

from app.db.models.picking_list import PickingList, PickingListItem
from app.db.models.platform_integration import PlatformIntegration, SyncEvent
from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.recurring_project import (
    RecurrencePattern,
    RecurringProject,
    GeneratedProject,
)
from app.db.models.refund import Refund  # Corrected Import
from app.db.models.shipment import Shipment
from app.db.models.storage import (
    StorageLocation,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.db.models.supplier import Supplier
from app.db.models.supplier_history import SupplierHistory
from app.db.models.supplier_rating import SupplierRating
from app.db.models.timeline_task import TimelineTask
from app.db.models.tool import Tool, ToolMaintenance, ToolCheckout
