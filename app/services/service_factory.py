# File: app/services/service_factory.py
"""
Factory for creating service instances in HideSync.

This module provides a centralized factory for creating service instances,
ensuring consistent initialization and dependency injection.
"""

from typing import Optional, Any, Dict, Type
from sqlalchemy.orm import Session

from app.repositories import communication_repository
from app.services.base_service import BaseService
from app.core.events import EventBus
from app.core.key_manager import KeyManager as KeyService


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

    def get_material_service(self) -> "MaterialService":
        """
        Get a MaterialService instance.

        Returns:
            MaterialService instance with all dependencies
        """
        from app.services.material_service import MaterialService
        from app.repositories.material_repository import MaterialRepository

        # Return cached instance if available
        if "material_service" in self._service_instances:
            return self._service_instances["material_service"]

        # Create material repository
        material_repository = MaterialRepository(self.session, self.key_service)

        # Create and cache material service
        service = MaterialService(
            session=self.session,
            repository=material_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            key_service=self.key_service,
        )

        self._service_instances["material_service"] = service
        return service

    def get_project_service(self) -> "ProjectService":
        """
        Get a ProjectService instance.

        Returns:
            ProjectService instance with all dependencies
        """
        from app.services.project_service import ProjectService
        from app.repositories.project_repository import ProjectRepository
        from app.repositories.timeline_task_repository import TimelineTaskRepository

        # Return cached instance if available
        if "project_service" in self._service_instances:
            return self._service_instances["project_service"]

        # Create repositories
        project_repository = ProjectRepository(self.session)
        timeline_task_repository = TimelineTaskRepository(self.session)

        # Create and cache project service
        service = ProjectService(
            session=self.session,
            repository=project_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            material_service=self.get_material_service(),
            timeline_task_repository=timeline_task_repository,
            customer_repository=None,  # Will be initialized lazily if needed
        )

        self._service_instances["project_service"] = service
        return service

    def get_customer_service(self) -> "CustomerService":
        """
        Get a CustomerService instance.

        Returns:
            CustomerService instance with all dependencies
        """
        from app.services.customer_service import CustomerService
        from app.repositories.customer_repository import CustomerRepository
        from app.repositories.communication_repository import (
            CommunicationRepository,
        )

        # Return cached instance if available
        if "customer_service" in self._service_instances:
            return self._service_instances["customer_service"]

        # Create repositories
        customer_repository = CustomerRepository(self.session, self.key_service)

        # Create and cache customer service
        service = CustomerService(
            session=self.session,
            repository=customer_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            key_service=self.key_service,
            communication_repository=communication_repository,
        )

        self._service_instances["customer_service"] = service
        return service

    def get_sale_service(self) -> "SaleService":
        """
        Get a SaleService instance.

        Returns:
            SaleService instance with all dependencies
        """
        from app.services.sale_service import SaleService
        from app.repositories.sale_repository import SaleRepository

        # Return cached instance if available
        if "sale_service" in self._service_instances:
            return self._service_instances["sale_service"]

        # Create sale repository
        sale_repository = SaleRepository(self.session)

        # Create and cache sale service
        service = SaleService(
            session=self.session,
            repository=sale_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            customer_service=self.get_customer_service(),
            product_service=None,  # Will be initialized lazily if needed
        )

        self._service_instances["sale_service"] = service
        return service

    def get_purchase_service(self) -> "PurchaseService":
        """
        Get a PurchaseService instance.

        Returns:
            PurchaseService instance with all dependencies
        """
        from app.services.purchase_service import PurchaseService
        from app.repositories.purchase_repository import PurchaseRepository

        # Return cached instance if available
        if "purchase_service" in self._service_instances:
            return self._service_instances["purchase_service"]

        # Create purchase repository
        purchase_repository = PurchaseRepository(self.session)

        # Create and cache purchase service
        service = PurchaseService(
            session=self.session,
            repository=purchase_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            supplier_service=None,  # Will be initialized lazily if needed
            material_service=self.get_material_service(),
        )

        self._service_instances["purchase_service"] = service
        return service

    def get_supplier_service(self) -> "SupplierService":
        """
        Get a SupplierService instance.

        Returns:
            SupplierService instance with all dependencies
        """
        from app.services.supplier_service import SupplierService
        from app.repositories.supplier_repository import SupplierRepository

        # Return cached instance if available
        if "supplier_service" in self._service_instances:
            return self._service_instances["supplier_service"]

        # Create supplier repository
        supplier_repository = SupplierRepository(self.session, self.key_service)

        # Create and cache supplier service
        service = SupplierService(
            session=self.session,
            repository=supplier_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            key_service=self.key_service,
        )

        self._service_instances["supplier_service"] = service
        return service

    def get_storage_location_service(self) -> "StorageLocationService":
        """
        Get a StorageLocationService instance with a fresh session.

        Returns:
            StorageLocationService instance with all dependencies
        """
        from app.services.storage_location_service import StorageLocationService
        from app.repositories.storage_repository import (
            StorageLocationRepository,
            StorageCellRepository,
            StorageAssignmentRepository,
            StorageMoveRepository,
        )
        from app.db.session import get_db

        # Create a new session specifically for this service
        new_session = get_db()

        # Create repositories with the new session
        storage_location_repository = StorageLocationRepository(new_session)
        storage_cell_repository = StorageCellRepository(new_session)
        storage_assignment_repository = StorageAssignmentRepository(new_session)
        storage_move_repository = StorageMoveRepository(new_session)

        # Create storage location service with the new session
        service = StorageLocationService(
            session=new_session,
            location_repository=storage_location_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            cell_repository=storage_cell_repository,
            assignment_repository=storage_assignment_repository,
            move_repository=storage_move_repository,
            material_service=self.get_material_service(),
        )

        # Note: We do NOT cache this service instance since it has a unique session
        return service

    def get_entity_media_service(self) -> "EntityMediaService":
        """
        Get an EntityMediaService instance.

        Returns:
            EntityMediaService instance with all dependencies
        """
        from app.services.entity_media_service import EntityMediaService
        from app.repositories.entity_media_repository import EntityMediaRepository
        from app.repositories.media_asset_repository import MediaAssetRepository

        # Return cached instance if available
        if "entity_media_service" in self._service_instances:
            return self._service_instances["entity_media_service"]

        # Create repositories
        entity_media_repository = EntityMediaRepository(self.session, self.key_service)
        media_asset_repository = MediaAssetRepository(self.session, self.key_service)

        # Create and cache entity media service
        service = EntityMediaService(
            db=self.session, encryption_service=self.key_service
        )

        self._service_instances["entity_media_service"] = service
        return service

    def get_file_storage_service(
        self, base_path: str = "./storage"
    ) -> "FileStorageService":
        """
        Get a FileStorageService instance.

        Args:
            base_path: Base storage directory

        Returns:
            FileStorageService instance with all dependencies
        """
        from app.services.storage_service import FileStorageService
        from app.repositories.file_metadata_repository import FileMetadataRepository

        # For file storage, we don't cache because base_path can change

        # Create file metadata repository
        metadata_repository = FileMetadataRepository(self.session)

        # Create file storage service
        return FileStorageService(
            base_path=base_path,
            metadata_repository=metadata_repository,
            security_context=self.security_context,
        )

    def get_dashboard_service(self) -> "DashboardService":
        """
        Get a DashboardService instance.

        Returns:
            DashboardService instance with all dependencies
        """
        from app.services.dashboard_service import DashboardService

        # Return cached instance if available
        if "dashboard_service" in self._service_instances:
            return self._service_instances["dashboard_service"]

        # Create and cache dashboard service
        service = DashboardService(
            session=self.session,
            service_factory=self,
            cache_service=self.cache_service,
            metrics_service=None,  # Will be initialized lazily if needed
        )

        self._service_instances["dashboard_service"] = service
        return service

    def get_tool_service(self) -> "ToolService":
        """
        Get a ToolService instance.

        Returns:
            ToolService instance with all dependencies
        """
        from app.services.tool_service import ToolService
        from app.repositories.tool_repository import (
            ToolRepository,
            ToolMaintenanceRepository,
            ToolCheckoutRepository,
        )

        # Return cached instance if available
        if "tool_service" in self._service_instances:
            return self._service_instances["tool_service"]

        # Create repositories
        tool_repository = ToolRepository(self.session)
        maintenance_repository = ToolMaintenanceRepository(self.session)
        checkout_repository = ToolCheckoutRepository(self.session)

        # Create and cache tool service
        service = ToolService(
            session=self.session,
            repository=tool_repository,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            maintenance_repository=maintenance_repository,
            checkout_repository=checkout_repository,
        )

        self._service_instances["tool_service"] = service
        return service

    def get_media_asset_service(self) -> "MediaAssetService":
        """
        Get a MediaAssetService instance.

        Returns:
            MediaAssetService instance with all dependencies
        """
        from app.services.media_asset_service import MediaAssetService
        from app.repositories.media_asset_repository import MediaAssetRepository

        # Return cached instance if available
        if "media_asset_service" in self._service_instances:
            return self._service_instances["media_asset_service"]

        # Create and cache media asset service
        service = MediaAssetService(
            session=self.session, file_storage_service=self.file_storage_service
        )

        self._service_instances["media_asset_service"] = service
        return service

    def get_tag_service(self) -> "TagService":
        """
        Get a TagService instance.

        Returns:
            TagService instance with all dependencies
        """
        from app.services.tag_service import TagService
        from app.repositories.tag_repository import TagRepository

        # Return cached instance if available
        if "tag_service" in self._service_instances:
            return self._service_instances["tag_service"]

        # Create and cache tag service
        service = TagService(session=self.session)

        self._service_instances["tag_service"] = service
        return service

    def get_service(self, service_class: Type[BaseService], **kwargs) -> BaseService:
        """
        Get a service instance of the specified class.

        This is a generic method for getting services not covered by specific methods.

        Args:
            service_class: Service class to instantiate
            **kwargs: Additional arguments to pass to the service constructor

        Returns:
            Instance of the requested service
        """
        # Get service name
        service_name = service_class.__name__

        # Return cached instance if available
        if service_name in self._service_instances:
            return self._service_instances[service_name]

        # Create service instance with standard dependencies
        service = service_class(
            session=self.session,
            security_context=self.security_context,
            event_bus=self.event_bus,
            cache_service=self.cache_service,
            **kwargs
        )

        # Cache the service instance
        self._service_instances[service_name] = service

        return service
