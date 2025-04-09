# File: app/repositories/repository_factory.py

from sqlalchemy.orm import Session

from app.repositories.customer_repository import CustomerRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.sale_repository import SaleRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.storage_repository import (
    StorageLocationRepository,
    StorageCellRepository,
    StorageAssignmentRepository,
    StorageMoveRepository,
)
from app.repositories.pattern_repository import (
    PatternRepository,
    ProjectTemplateRepository,
)
from app.repositories.tool_repository import (
    ToolRepository,
    ToolMaintenanceRepository,
    ToolCheckoutRepository,
)
from app.repositories.platform_integration_repository import (
    PlatformIntegrationRepository,
    SyncEventRepository,
)
from app.repositories.component_repository import (
    ComponentRepository,
    ComponentMaterialRepository,
)
from app.repositories.documentation_repository import (
    DocumentationResourceRepository,
    DocumentationCategoryRepository,
    ApplicationContextRepository,
    ContextualHelpMappingRepository,
)
from app.repositories.picking_list_repository import (
    PickingListRepository,
    PickingListItemRepository,
)
from app.repositories.purchase_repository import (
    PurchaseRepository,
    PurchaseItemRepository,
)
from app.repositories.recurring_project_repository import (
    RecurringProjectRepository,
    RecurrencePatternRepository,
    GeneratedProjectRepository,
)
from app.repositories.shipment_repository import ShipmentRepository
from app.repositories.timeline_task_repository import TimelineTaskRepository
from app.repositories.refund_repository import RefundRepository

# New imports
from app.repositories.communication_repository import CommunicationRepository
from app.repositories.customer_communication_repository import (
    CustomerCommunicationRepository,
)
from app.repositories.file_metadata_repository import FileMetadataRepository
from app.repositories.inventory_transaction_repository import (
    InventoryTransactionRepository,
)
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.role_repository import RoleRepository, PermissionRepository
from app.repositories.supplier_history_repository import SupplierHistoryRepository
from app.repositories.supplier_rating_repository import SupplierRatingRepository
from app.repositories.user_repository import UserRepository

# Media Asset Management Repositories
from app.repositories.media_asset_repository import MediaAssetRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.media_asset_tag_repository import MediaAssetTagRepository


class RepositoryFactory:
    """
    Factory for creating repository instances.

    Centralizes repository creation and ensures consistent initialization
    by providing a single point for setting up encryption services and
    database sessions for repositories.

    All repositories use the same database session and optional encryption
    service, ensuring consistent transaction management and data security.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the repository factory.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        self.session = session
        self.encryption_service = encryption_service

    # Customer repositories
    def create_customer_repository(self) -> CustomerRepository:
        """Create a CustomerRepository instance."""
        return CustomerRepository(self.session, self.encryption_service)

    # Material repositories
    def create_material_repository(self) -> MaterialRepository:
        """Create a MaterialRepository instance."""
        return MaterialRepository(self.session, self.encryption_service)

    # Project repositories
    def create_project_repository(self) -> ProjectRepository:
        """Create a ProjectRepository instance."""
        return ProjectRepository(self.session, self.encryption_service)

    # Sales repositories
    def create_sale_repository(self) -> SaleRepository:
        """Create a SaleRepository instance."""
        return SaleRepository(self.session, self.encryption_service)

    # Inventory repositories
    def create_inventory_repository(self) -> InventoryRepository:
        """Create an InventoryRepository instance."""
        return InventoryRepository(self.session, self.encryption_service)

    def create_product_repository(self) -> ProductRepository:
        """Create a ProductRepository instance."""
        return ProductRepository(self.session, self.encryption_service)

    # Supplier repositories
    def create_supplier_repository(self) -> SupplierRepository:
        """Create a SupplierRepository instance."""
        return SupplierRepository(self.session, self.encryption_service)

    # Storage repositories
    def create_storage_location_repository(self) -> StorageLocationRepository:
        """Create a StorageLocationRepository instance."""
        return StorageLocationRepository(self.session, self.encryption_service)

    def create_storage_cell_repository(self) -> StorageCellRepository:
        """Create a StorageCellRepository instance."""
        return StorageCellRepository(self.session, self.encryption_service)

    def create_storage_assignment_repository(self) -> StorageAssignmentRepository:
        """Create a StorageAssignmentRepository instance."""
        return StorageAssignmentRepository(self.session, self.encryption_service)

    def create_storage_move_repository(self) -> StorageMoveRepository:
        """Create a StorageMoveRepository instance."""
        return StorageMoveRepository(self.session, self.encryption_service)

    # Pattern repositories
    def create_pattern_repository(self) -> PatternRepository:
        """Create a PatternRepository instance."""
        return PatternRepository(self.session, self.encryption_service)

    def create_project_template_repository(self) -> ProjectTemplateRepository:
        """Create a ProjectTemplateRepository instance."""
        return ProjectTemplateRepository(self.session, self.encryption_service)

    # Tool repositories
    def create_tool_repository(self) -> ToolRepository:
        """Create a ToolRepository instance."""
        return ToolRepository(self.session, self.encryption_service)

    def create_tool_maintenance_repository(self) -> ToolMaintenanceRepository:
        """Create a ToolMaintenanceRepository instance."""
        return ToolMaintenanceRepository(self.session, self.encryption_service)

    def create_tool_checkout_repository(self) -> ToolCheckoutRepository:
        """Create a ToolCheckoutRepository instance."""
        return ToolCheckoutRepository(self.session, self.encryption_service)

    # Platform integration repositories
    def create_platform_integration_repository(self) -> PlatformIntegrationRepository:
        """Create a PlatformIntegrationRepository instance."""
        return PlatformIntegrationRepository(self.session, self.encryption_service)

    def create_sync_event_repository(self) -> SyncEventRepository:
        """Create a SyncEventRepository instance."""
        return SyncEventRepository(self.session, self.encryption_service)

    # Component repositories
    def create_component_repository(self) -> ComponentRepository:
        """Create a ComponentRepository instance."""
        return ComponentRepository(self.session, self.encryption_service)

    def create_component_material_repository(self) -> ComponentMaterialRepository:
        """Create a ComponentMaterialRepository instance."""
        return ComponentMaterialRepository(self.session, self.encryption_service)

    # Documentation repositories
    def create_documentation_resource_repository(
        self,
    ) -> DocumentationResourceRepository:
        """Create a DocumentationResourceRepository instance."""
        return DocumentationResourceRepository(self.session, self.encryption_service)

    def create_documentation_category_repository(
        self,
    ) -> DocumentationCategoryRepository:
        """Create a DocumentationCategoryRepository instance."""
        return DocumentationCategoryRepository(self.session, self.encryption_service)

    def create_application_context_repository(
        self,
    ) -> ApplicationContextRepository:
        """Create an ApplicationContextRepository instance."""
        return ApplicationContextRepository(self.session, self.encryption_service)

    def create_contextual_help_mapping_repository(
        self,
    ) -> ContextualHelpMappingRepository:
        """Create a ContextualHelpMappingRepository instance."""
        return ContextualHelpMappingRepository(self.session, self.encryption_service)

    def create_refund_repository(self) -> RefundRepository:
        """Create a RefundRepository instance."""
        return RefundRepository(self.session, self.encryption_service)

    # Picking list repositories
    def create_picking_list_repository(self) -> PickingListRepository:
        """Create a PickingListRepository instance."""
        return PickingListRepository(self.session, self.encryption_service)

    def create_picking_list_item_repository(self) -> PickingListItemRepository:
        """Create a PickingListItemRepository instance."""
        return PickingListItemRepository(self.session, self.encryption_service)

    # Purchase repositories
    def create_purchase_repository(self) -> PurchaseRepository:
        """Create a PurchaseRepository instance."""
        return PurchaseRepository(self.session, self.encryption_service)

    def create_purchase_item_repository(self) -> PurchaseItemRepository:
        """Create a PurchaseItemRepository instance."""
        return PurchaseItemRepository(self.session, self.encryption_service)

    # Recurring project repositories
    def create_recurring_project_repository(self) -> RecurringProjectRepository:
        """Create a RecurringProjectRepository instance."""
        return RecurringProjectRepository(self.session, self.encryption_service)

    def create_recurrence_pattern_repository(self) -> RecurrencePatternRepository:
        """Create a RecurrencePatternRepository instance."""
        return RecurrencePatternRepository(self.session, self.encryption_service)

    def create_generated_project_repository(self) -> GeneratedProjectRepository:
        """Create a GeneratedProjectRepository instance."""
        return GeneratedProjectRepository(self.session, self.encryption_service)

    # Shipment repositories
    def create_shipment_repository(self) -> ShipmentRepository:
        """Create a ShipmentRepository instance."""
        return ShipmentRepository(self.session, self.encryption_service)

    # Timeline task repositories
    def create_timeline_task_repository(self) -> TimelineTaskRepository:
        """Create a TimelineTaskRepository instance."""
        return TimelineTaskRepository(self.session, self.encryption_service)

    # Communications repositories
    def create_communication_repository(self) -> CommunicationRepository:
        """Create a CommunicationRepository instance."""
        return CommunicationRepository(self.session, self.encryption_service)

    def create_customer_communication_repository(
        self,
    ) -> CustomerCommunicationRepository:
        """Create a CustomerCommunicationRepository instance."""
        return CustomerCommunicationRepository(self.session, self.encryption_service)

    # File metadata repositories
    def create_file_metadata_repository(self) -> FileMetadataRepository:
        """Create a FileMetadataRepository instance."""
        return FileMetadataRepository(self.session, self.encryption_service)

    # Inventory transaction repositories
    def create_inventory_transaction_repository(self) -> InventoryTransactionRepository:
        """Create an InventoryTransactionRepository instance."""
        return InventoryTransactionRepository(self.session, self.encryption_service)

    # Password reset repositories
    def create_password_reset_repository(self) -> PasswordResetRepository:
        """Create a PasswordResetRepository instance."""
        return PasswordResetRepository(self.session, self.encryption_service)

    # Role and permission repositories
    def create_role_repository(self) -> RoleRepository:
        """Create a RoleRepository instance."""
        return RoleRepository(self.session, self.encryption_service)

    def create_permission_repository(self) -> PermissionRepository:
        """Create a PermissionRepository instance."""
        return PermissionRepository(self.session, self.encryption_service)

    # Supplier history repositories
    def create_supplier_history_repository(self) -> SupplierHistoryRepository:
        """Create a SupplierHistoryRepository instance."""
        return SupplierHistoryRepository(self.session, self.encryption_service)

    # Supplier rating repositories
    def create_supplier_rating_repository(self) -> SupplierRatingRepository:
        """Create a SupplierRatingRepository instance."""
        return SupplierRatingRepository(self.session, self.encryption_service)

    # User repositories
    def create_user_repository(self) -> UserRepository:
        """Create a UserRepository instance."""
        return UserRepository(self.session, self.encryption_service)

    # Media Asset Management repositories
    def create_media_asset_repository(self) -> MediaAssetRepository:
        """Create a MediaAssetRepository instance."""
        return MediaAssetRepository(self.session, self.encryption_service)

    def create_tag_repository(self) -> TagRepository:
        """Create a TagRepository instance."""
        return TagRepository(self.session, self.encryption_service)

    def create_media_asset_tag_repository(self) -> MediaAssetTagRepository:
        """Create a MediaAssetTagRepository instance."""
        return MediaAssetTagRepository(self.session, self.encryption_service)
