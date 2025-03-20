# File: app/db/models/__init__.py

from app.db.models.base import Base
from app.db.models.communication import CustomerCommunication
from app.db.models.component import Component, ComponentMaterial
from app.db.models.customer import Customer
from app.db.models.documentation import (
    DocumentationCategory,
    DocumentationResource,
    Refund,
)
from app.db.models.file_metadata import FileMetadata
from app.db.models.inventory import Inventory, InventoryTransaction, Product
from app.db.models.material import (
    Material,
    LeatherMaterial,
    HardwareMaterial,
    SuppliesMaterial,
)
from app.db.models.pattern import Pattern, ProjectTemplate, ProjectTemplateComponent
from app.db.models.picking_list import PickingList, PickingListItem
from app.db.models.platform_integration import PlatformIntegration, SyncEvent
from app.db.models.project import Project, ProjectComponent
from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.recurring_project import (
    RecurrencePattern,
    RecurringProject,
    GeneratedProject,
)
from app.db.models.sales import Sale, SaleItem
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
from app.db.models.user import User
