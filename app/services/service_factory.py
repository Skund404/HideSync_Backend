# app/services/service_factory.py
"""
Factory for creating service instances in HideSync.

This module provides a centralized factory for creating service instances,
ensuring consistent initialization and dependency injection.
"""

from typing import Optional, Any, Dict, Type
from sqlalchemy.orm import Session

# Removed unused imports to clean up
# from app.repositories import communication_repository
from app.services.base_service import BaseService
from app.core.events import EventBus
from app.core.key_manager import KeyManager as KeyService # Assuming KeyManager is the correct name

# Import EnumService
from app.services.enum_service import EnumService

class ServiceFactory:
    """
    Factory for creating service instances with proper dependencies.

    This factory ensures that services are created with consistent dependencies
    and provides a single point for service instantiation.
    """

    def __init__(
        self,
        session: Session,
        security_context=None,
        event_bus=None,
        cache_service=None,
        key_service=None,
        file_storage_service=None,
    ):
        """
        Initialize the service factory with dependencies.

        Args:
            session: Database session for persistence operations
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            key_service: Optional key service for encryption/decryption
            file_storage_service: Optional service for file storage operations
        """
        self.session = session
        self.security_context = security_context
        self.event_bus = event_bus or EventBus()
        self.cache_service = cache_service
        self.key_service = key_service or KeyService()
        self.file_storage_service = file_storage_service

        # Service instance cache for singleton services
        self._service_instances: Dict[str, Any] = {}

    # --- Add EnumService getter ---
    def get_enum_service(self) -> "EnumService":
        """
        Get an EnumService instance.

        Returns:
            EnumService instance with the database session.
        """
        # EnumService typically doesn't need complex dependencies beyond the session
        # Return cached instance if available
        if "enum_service" in self._service_instances:
            return self._service_instances["enum_service"]

        # Create and cache enum service
        # It only needs the db session based on its current implementation
        service = EnumService(db=self.session)

        self._service_instances["enum_service"] = service
        return service
    # --- End EnumService getter ---

    def get_material_service(self) -> "MaterialService":
        """Get a MaterialService instance."""
        from app.services.material_service import MaterialService
        from app.repositories.material_repository import MaterialRepository
        if "material_service" in self._service_instances:
            return self._service_instances["material_service"]
        material_repository = MaterialRepository(self.session, self.key_service)
        service = MaterialService(
            session=self.session, repository=material_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, key_service=self.key_service
        )
        self._service_instances["material_service"] = service
        return service

    def get_project_service(self) -> "ProjectService":
        """Get a ProjectService instance."""
        # NOTE: Ensure ProjectService dependencies are correctly handled if they change
        from app.services.project_service import ProjectService
        from app.repositories.project_repository import ProjectRepository
        from app.repositories.timeline_task_repository import TimelineTaskRepository
        if "project_service" in self._service_instances:
            return self._service_instances["project_service"]
        project_repository = ProjectRepository(self.session)
        timeline_task_repository = TimelineTaskRepository(self.session)
        service = ProjectService(
            session=self.session, repository=project_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, material_service=self.get_material_service(),
            timeline_task_repository=timeline_task_repository,
            customer_repository=None # Assuming lazy init or specific dependency injection elsewhere
        )
        self._service_instances["project_service"] = service
        return service

    def get_customer_service(self) -> "CustomerService":
        """Get a CustomerService instance."""
        from app.services.customer_service import CustomerService
        from app.repositories.customer_repository import CustomerRepository
        from app.repositories.communication_repository import CommunicationRepository # Import correct repo
        if "customer_service" in self._service_instances:
            return self._service_instances["customer_service"]
        customer_repository = CustomerRepository(self.session, self.key_service)
        communication_repository = CommunicationRepository(self.session, self.key_service) # Instantiate repo
        service = CustomerService(
            session=self.session, repository=customer_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, key_service=self.key_service,
            communication_repository=communication_repository # Pass instantiated repo
        )
        self._service_instances["customer_service"] = service
        return service

    def get_sale_service(self) -> "SaleService":
        """Get a SaleService instance."""
        # NOTE: Correctly initialize dependencies if needed
        from app.services.sale_service import SaleService
        from app.repositories.sale_repository import SaleRepository
        if "sale_service" in self._service_instances:
            return self._service_instances["sale_service"]
        sale_repository = SaleRepository(self.session)
        service = SaleService(
            session=self.session, repository=sale_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, customer_service=self.get_customer_service(),
            product_service=None # Assuming lazy init
        )
        self._service_instances["sale_service"] = service
        return service

    def get_purchase_service(self) -> "PurchaseService":
        """Get a PurchaseService instance."""
        # NOTE: Correctly initialize dependencies if needed
        from app.services.purchase_service import PurchaseService
        from app.repositories.purchase_repository import PurchaseRepository
        if "purchase_service" in self._service_instances:
            return self._service_instances["purchase_service"]
        purchase_repository = PurchaseRepository(self.session)
        service = PurchaseService(
            session=self.session, repository=purchase_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, supplier_service=None, # Assuming lazy init
            material_service=self.get_material_service()
        )
        self._service_instances["purchase_service"] = service
        return service

    def get_supplier_service(self) -> "SupplierService":
        """Get a SupplierService instance."""
        from app.services.supplier_service import SupplierService
        from app.repositories.supplier_repository import SupplierRepository
        if "supplier_service" in self._service_instances:
            return self._service_instances["supplier_service"]
        supplier_repository = SupplierRepository(self.session, self.key_service)
        service = SupplierService(
            session=self.session, repository=supplier_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, key_service=self.key_service
        )
        self._service_instances["supplier_service"] = service
        return service

    # NOTE: StorageLocationService creation looks unusual with a new session.
    # Ensure this is intended behavior. Usually, all services share the same request session.
    # If a separate session is truly needed, the 'get_db' dependency might need careful handling.
    def get_storage_location_service(self) -> "StorageLocationService":
        """Get a StorageLocationService instance."""
        from app.services.storage_location_service import StorageLocationService
        from app.repositories.storage_repository import (
            StorageLocationRepository, StorageCellRepository,
            StorageAssignmentRepository, StorageMoveRepository
        )
        # Removed get_db import, assuming self.session is the intended session
        # If a truly separate session is required, review dependency injection strategy
        storage_location_repository = StorageLocationRepository(self.session)
        storage_cell_repository = StorageCellRepository(self.session)
        storage_assignment_repository = StorageAssignmentRepository(self.session)
        storage_move_repository = StorageMoveRepository(self.session)
        service = StorageLocationService(
            session=self.session, # Use the factory's session
            location_repository=storage_location_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, cell_repository=storage_cell_repository,
            assignment_repository=storage_assignment_repository, move_repository=storage_move_repository,
            material_service=self.get_material_service()
        )
        # Typically cache this service unless there's a strong reason not to
        if "storage_location_service" not in self._service_instances:
             self._service_instances["storage_location_service"] = service
        return self._service_instances["storage_location_service"]


    def get_entity_media_service(self) -> "EntityMediaService":
        """Get an EntityMediaService instance."""
        # NOTE: EntityMediaService signature might differ, adjust as needed
        from app.services.entity_media_service import EntityMediaService
        # from app.repositories.entity_media_repository import EntityMediaRepository # Not used in original?
        # from app.repositories.media_asset_repository import MediaAssetRepository # Not used in original?
        if "entity_media_service" in self._service_instances:
            return self._service_instances["entity_media_service"]
        # Assuming the original service only needed db and encryption
        service = EntityMediaService(
            db=self.session, encryption_service=self.key_service
        )
        self._service_instances["entity_media_service"] = service
        return service

    # File storage service is often configured differently, not cached is fine
    def get_file_storage_service(self, base_path: Optional[str] = None) -> "FileStorageService":
        """Get a FileStorageService instance."""
        from app.services.storage_service import FileStorageService # Renamed from original? Check path/name
        from app.repositories.file_metadata_repository import FileMetadataRepository
        from app.core.config import settings # Get default path from settings if needed

        effective_base_path = base_path or settings.MEDIA_ASSETS_BASE_PATH # Example: Use settings
        metadata_repository = FileMetadataRepository(self.session)
        return FileStorageService(
            base_path=effective_base_path,
            metadata_repository=metadata_repository,
            security_context=self.security_context,
        )

    def get_dashboard_service(self) -> "DashboardService":
        """Get a DashboardService instance."""
        from app.services.dashboard_service import DashboardService
        if "dashboard_service" in self._service_instances:
            return self._service_instances["dashboard_service"]
        service = DashboardService(
            session=self.session, service_factory=self,
            cache_service=self.cache_service,
            metrics_service=None # Assuming lazy init
        )
        self._service_instances["dashboard_service"] = service
        return service

    def get_tool_service(self) -> "ToolService":
        """Get a ToolService instance."""
        from app.services.tool_service import ToolService
        from app.repositories.tool_repository import (
            ToolRepository, ToolMaintenanceRepository, ToolCheckoutRepository
        )
        if "tool_service" in self._service_instances:
            return self._service_instances["tool_service"]
        tool_repository = ToolRepository(self.session)
        maintenance_repository = ToolMaintenanceRepository(self.session)
        checkout_repository = ToolCheckoutRepository(self.session)
        service = ToolService(
            session=self.session, repository=tool_repository,
            security_context=self.security_context, event_bus=self.event_bus,
            cache_service=self.cache_service, maintenance_repository=maintenance_repository,
            checkout_repository=checkout_repository
        )
        self._service_instances["tool_service"] = service
        return service

    def get_media_asset_service(self) -> "MediaAssetService":
        """Get a MediaAssetService instance."""
        from app.services.media_asset_service import MediaAssetService
        # from app.repositories.media_asset_repository import MediaAssetRepository # Repo not used?
        if "media_asset_service" in self._service_instances:
            return self._service_instances["media_asset_service"]
        # Assuming it needs the file storage service now
        effective_file_storage = self.file_storage_service or self.get_file_storage_service()
        service = MediaAssetService(
             session=self.session, file_storage_service=effective_file_storage
        )
        self._service_instances["media_asset_service"] = service
        return service

    def get_tag_service(self) -> "TagService":
        """Get a TagService instance."""
        from app.services.tag_service import TagService
        # from app.repositories.tag_repository import TagRepository # Repo not used?
        if "tag_service" in self._service_instances:
            return self._service_instances["tag_service"]
        service = TagService(session=self.session) # Assuming simple init
        self._service_instances["tag_service"] = service
        return service

    # --- Generic Service Getter (Use with caution) ---
    def get_service(self, service_class: Type[BaseService], **kwargs) -> BaseService:
        """
        Generic method for getting services not covered by specific methods.
        It's better to have explicit getters for maintainability.
        """
        service_name = service_class.__name__
        if service_name in self._service_instances:
            return self._service_instances[service_name]

        # Basic default dependencies, might need adjustment based on actual service
        service = service_class(
            session=self.session,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            key_service=self.key_service,
            file_storage_service=self.file_storage_service,
            **kwargs # Pass any extra args needed
        )
        self._service_instances[service_name] = service
        return service