# File: app/services/material_service.py

from typing import List, Optional, Dict, Any, Union, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import time

from app.services.base_service import BaseService
from app.db.models.material import (
    Material,
    LeatherMaterial,
    HardwareMaterial,
    SuppliesMaterial,
    WoodMaterial,  # Import WoodMaterial from the material module
)

from app.db.models.enums import (
    MaterialType,
    MaterialStatus,
    InventoryStatus,
    WoodType,
    WoodGrain,
    WoodFinish,
)
from app.repositories.material_repository import MaterialRepository
from app.core.exceptions import (
    EntityNotFoundException,
    MaterialNotFoundException,
    InsufficientInventoryException,
    ValidationException,
    ConcurrentModificationException,
    BusinessRuleException,
)
from app.core.events import DomainEvent
from app.core.validation import validate_input, validate_entity
from app.schemas.material import MaterialSearchParams
from app.services.settings_service import SettingsService


# Define domain events
class MaterialCreated(DomainEvent):
    """Event emitted when a material is created."""

    def __init__(
            self, material_id: int, material_type: str, user_id: Optional[int] = None
    ):
        """
        Initialize material created event.

        Args:
            material_id: ID of the created material
            material_type: Type of the created material
            user_id: Optional ID of the user who created the material
        """
        super().__init__()
        self.material_id = material_id
        self.material_type = material_type
        self.user_id = user_id


class MaterialUpdated(DomainEvent):
    """Event emitted when a material is updated."""

    def __init__(
            self, material_id: int, changes: Dict[str, Any], user_id: Optional[int] = None
    ):
        """
        Initialize material updated event.

        Args:
            material_id: ID of the updated material
            changes: Dictionary of changed fields with old and new values
            user_id: Optional ID of the user who updated the material
        """
        super().__init__()
        self.material_id = material_id
        self.changes = changes
        self.user_id = user_id


class MaterialDeleted(DomainEvent):
    """Event emitted when a material is deleted."""

    def __init__(self, material_id: int, user_id: Optional[int] = None):
        """
        Initialize material deleted event.

        Args:
            material_id: ID of the deleted material
            user_id: Optional ID of the user who deleted the material
        """
        super().__init__()
        self.material_id = material_id
        self.user_id = user_id


class MaterialStockChanged(DomainEvent):
    """Event emitted when material stock level changes."""

    def __init__(
            self,
            material_id: int,
            previous_quantity: float,
            new_quantity: float,
            reason: str,
            user_id: Optional[int] = None,
    ):
        """
        Initialize material stock changed event.

        Args:
            material_id: ID of the material
            previous_quantity: Previous quantity
            new_quantity: New quantity
            reason: Reason for the stock change
            user_id: Optional ID of the user who changed the stock
        """
        super().__init__()
        self.material_id = material_id
        self.previous_quantity = previous_quantity
        self.new_quantity = new_quantity
        self.change = new_quantity - previous_quantity
        self.reason = reason
        self.user_id = user_id


# Validation functions
validate_material = validate_entity(Material)
validate_leather_material = validate_entity(LeatherMaterial)
validate_hardware_material = validate_entity(HardwareMaterial)
validate_supplies_material = validate_entity(SuppliesMaterial)
validate_wood_material = validate_entity(WoodMaterial)  # Add validation function for wood materials


class MaterialService(BaseService[Material]):
    """
    Service for managing materials in the HideSync system.

    Provides functionality for:
    - Material inventory management
    - Material categorization
    - Tracking material usage
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            key_service=None,
            settings_service=None,
    ):
        """
        Initialize MaterialService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            key_service: Optional key service for encryption/decryption
            settings_service: Optional settings service for user settings
        """
        self.session = session
        self.repository = repository or MaterialRepository(session, key_service)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.key_service = key_service
        self.settings_service = settings_service

    @validate_input(validate_wood_material)
    def create_wood_material(self, data: Dict[str, Any]) -> WoodMaterial:
        """
        Create a wood material with type-specific validation.

        Args:
            data: Wood material data

        Returns:
            Created wood material entity

        Raises:
            ValidationException: If data validation fails
        """
        data["material_type"] = MaterialType.WOOD.value
        return self.repository.create_wood(data)

    def get_materials(
            self,
            skip: int = 0,
            limit: int = 100,
            search_params: Optional[MaterialSearchParams] = None,
            apply_settings: bool = True
    ) -> List[Material]:
        """
        Retrieve materials with optional filtering and pagination.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            search_params: Optional search parameters for filtering
                - material_type: Optional filter by material type
                - quality: Optional filter by material quality
                - in_stock: Optional filter by stock availability
                - search: Optional search term for name
            apply_settings: Whether to apply user settings to results

        Returns:
            List of material records matching the criteria
        """
        # Default empty search params if None
        search_params = search_params or MaterialSearchParams()

        # If search term is provided, use search_materials method
        if search_params.search:
            materials = self.repository.search_materials(
                query=search_params.search, skip=skip, limit=limit
            )
        else:
            # Create filter criteria based on search params
            filters = {}

            # Add material_type filter if provided
            if search_params.material_type:
                filters["material_type"] = search_params.material_type

            # Add quality filter if provided
            if search_params.quality:
                filters["quality"] = search_params.quality

            # Add in_stock filter if provided
            if search_params.in_stock is not None:
                if search_params.in_stock:
                    filters["status"] = InventoryStatus.IN_STOCK
                else:
                    # If not in_stock, look for both OUT_OF_STOCK and LOW_STOCK
                    # This needs to be handled specially since it's not a simple equality
                    return self.repository.get_materials_by_status(
                        status=[InventoryStatus.OUT_OF_STOCK, InventoryStatus.LOW_STOCK],
                        skip=skip,
                        limit=limit,
                    )

            # Use the BaseService list method which will use repository.list under the hood
            materials = self.list(skip=skip, limit=limit, **filters)

        # Apply settings if requested and security context is available
        if apply_settings and self.security_context and self.settings_service:
            user_id = getattr(getattr(self.security_context, 'current_user', None), 'id', None)
            if user_id:
                materials = self.apply_settings_to_materials(materials, user_id)

        return materials

    def apply_settings_to_materials(self, materials: List[Material], user_id: int) -> List[Material]:
        """
        Apply user settings to materials.

        Args:
            materials: List of materials to apply settings to
            user_id: ID of the user whose settings to apply

        Returns:
            List of materials with settings applied
        """
        if not self.settings_service or not materials:
            return materials

        try:
            # Get materials settings
            material_ui = self.settings_service.get_setting(
                key="material_ui",
                scope_type="user",
                scope_id=str(user_id)
            )

            # System settings (for defaults)
            material_system = self.settings_service.get_setting(
                key="material_system",
                scope_type="system",
                scope_id="1"
            )

            # If no settings found, return materials as is
            if not material_ui:
                return materials

            # Extract list view settings
            list_view = material_ui.get("list_view", {})
            list_columns = list_view.get("default_columns", ["name", "sku", "quantity", "unit", "supplier"])
            show_list_thumbnail = list_view.get("show_thumbnail", True)

            # Get default material type
            default_material_type = "supplies"
            if material_system and "default_units" in material_system:
                material_system_settings = material_system.get("system", {})
                default_material_type = material_system_settings.get("default_material_type", "supplies")

            # Apply settings to each material
            for material in materials:
                # Add ui_settings property if not exists
                if not hasattr(material, "ui_settings"):
                    material.ui_settings = {}

                # Apply default material type if needed
                if not getattr(material, "material_type", None):
                    material.material_type = default_material_type

                # Apply list view settings
                material.ui_settings["list_view"] = {
                    "columns": list_columns,
                    "show_thumbnail": show_list_thumbnail
                }

                # Apply any system-wide settings like units
                if material_system:
                    default_units = material_system.get("default_units", {})
                    # Could use these for formatting values with proper units
                    material.ui_settings["default_units"] = default_units
        except Exception as e:
            # Log error but don't fail if settings can't be applied
            print(f"Error applying settings: {str(e)}")

        return materials

    def get_material(self, material_id: int) -> Material:
        """
        Get detailed information about a specific material.

        Args:
            material_id: ID of the material to retrieve

        Returns:
            Material information

        Raises:
            EntityNotFoundException: If the material doesn't exist
        """
        # Use the BaseService get_by_id method
        material = self.get_by_id(material_id)
        if not material:
            raise EntityNotFoundException(f"Material with ID {material_id} not found")
        return material

    def update_material(
            self, material_id: int, data: Dict[str, Any], user_id: Optional[int] = None
    ) -> Material:
        """
        Update a material.

        Args:
            material_id: ID of the material to update
            data: Updated material data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated material information

        Raises:
            EntityNotFoundException: If the material doesn't exist
        """
        # Store user_id in security context if provided
        original_user = None
        if user_id and self.security_context:
            original_user = getattr(self.security_context, "current_user", None)
            self.security_context.current_user = type("User", (), {"id": user_id})

        try:
            # Use the BaseService update method
            updated = self.update(material_id, data)
            if not updated:
                raise EntityNotFoundException(
                    f"Material with ID {material_id} not found"
                )
            return updated
        finally:
            # Restore original user in security context
            if user_id and self.security_context and original_user:
                self.security_context.current_user = original_user

    def delete_material(self, material_id: int, user_id: Optional[int] = None) -> None:
        """
        Delete a material.

        Args:
            material_id: ID of the material to delete
            user_id: Optional ID of the user performing the deletion

        Raises:
            EntityNotFoundException: If the material doesn't exist
        """
        # Store user_id in security context if provided
        original_user = None
        if user_id and self.security_context:
            original_user = getattr(self.security_context, "current_user", None)
            self.security_context.current_user = type("User", (), {"id": user_id})

        try:
            # Check if material exists first
            material = self.get_by_id(material_id)
            if not material:
                raise EntityNotFoundException(
                    f"Material with ID {material_id} not found"
                )

            # Use BaseService delete method
            result = self.delete(material_id)
            if not result:
                raise EntityNotFoundException(
                    f"Material with ID {material_id} not found"
                )
        finally:
            # Restore original user in security context
            if user_id and self.security_context and original_user:
                self.security_context.current_user = original_user

    def adjust_stock(
            self,
            material_id: int,
            quantity: float,
            notes: Optional[str] = None,
            user_id: Optional[int] = None,
    ) -> Material:
        """
        Adjust the stock quantity of a material.

        Args:
            material_id: ID of the material
            quantity: Quantity to add (positive) or remove (negative)
            notes: Optional notes for this adjustment
            user_id: Optional ID of the user making the adjustment

        Returns:
            Updated material information

        Raises:
            EntityNotFoundException: If the material doesn't exist
            InsufficientInventoryException: If adjustment would result in negative inventory
        """
        # Store user_id in security context if provided
        original_user = None
        if user_id and self.security_context:
            original_user = getattr(self.security_context, "current_user", None)
            self.security_context.current_user = type("User", (), {"id": user_id})

        try:
            # Set reason from notes or default
            reason = notes if notes else "Manual inventory adjustment"

            # Use the existing adjust_inventory method
            return self.adjust_inventory(
                material_id=material_id,
                quantity_change=quantity,
                reason=reason,
                project_id=None,  # No project associated with manual adjustment
            )
        finally:
            # Restore original user in security context
            if user_id and self.security_context and original_user:
                self.security_context.current_user = original_user

    @validate_input(validate_material)
    def create_material(
            self, data: Dict[str, Any], user_id: Optional[int] = None
    ) -> Material:
        """
        Create a new material with type-specific handling.

        Args:
            data: Material data with required fields
            user_id: Optional ID of the user creating the material

        Returns:
            Created material entity

        Raises:
            ValidationException: If data validation fails
        """
        original_user = None
        if user_id and self.security_context:
            original_user = getattr(self.security_context, "current_user", None)
            self.security_context.current_user = type("User", (), {"id": user_id})

        try:
            material_type = data.get("material_type") or data.get("materialType")
            with self.transaction():
                if material_type == MaterialType.LEATHER.value:
                    material = self.create_leather_material(data)
                elif material_type == MaterialType.HARDWARE.value:
                    material = self.create_hardware_material(data)
                elif material_type == MaterialType.SUPPLIES.value:
                    material = self.create_supplies_material(data)
                elif material_type == MaterialType.WOOD.value:
                    material = self.create_wood_material(data)
                else:
                    material = self.repository.create(data)

                # Publish event if event bus exists
                if self.event_bus:
                    user_id = (
                        self.security_context.current_user.id
                        if self.security_context
                        else None
                    )
                    self.event_bus.publish(
                        MaterialCreated(
                            material_id=material.id,
                            material_type=getattr(material, "material_type", None),
                            user_id=user_id,
                        )
                    )

                return material
        finally:
            if user_id and self.security_context and original_user:
                self.security_context.current_user = original_user

    @validate_input(validate_leather_material)
    def create_leather_material(self, data: Dict[str, Any]) -> LeatherMaterial:
        """
        Create a leather material with type-specific validation.

        Args:
            data: Leather material data

        Returns:
            Created leather material entity

        Raises:
            ValidationException: If data validation fails
        """
        data["material_type"] = MaterialType.LEATHER.value
        return self.repository.create_leather(data)

    @validate_input(validate_hardware_material)
    def create_hardware_material(self, data: Dict[str, Any]) -> HardwareMaterial:
        """
        Create a hardware material with type-specific validation.

        Args:
            data: Hardware material data

        Returns:
            Created hardware material entity

        Raises:
            ValidationException: If data validation fails
        """
        data["material_type"] = MaterialType.HARDWARE.value
        return self.repository.create_hardware(data)

    @validate_input(validate_supplies_material)
    def create_supplies_material(self, data: Dict[str, Any]) -> SuppliesMaterial:
        """
        Create a supplies material with type-specific validation.

        Args:
            data: Supplies material data

        Returns:
            Created supplies material entity

        Raises:
            ValidationException: If data validation fails
        """
        data["material_type"] = MaterialType.SUPPLIES.value
        return self.repository.create_supplies(data)

    def adjust_inventory(
            self,
            material_id: int,
            quantity_change: float,
            reason: str,
            project_id: Optional[int] = None,
    ) -> Material:
        """
        Adjust inventory level for a material.

        Args:
            material_id: Material ID
            quantity_change: Amount to change (positive or negative)
            reason: Reason for adjustment
            project_id: Optional related project ID

        Returns:
            Updated material

        Raises:
            MaterialNotFoundException: If material not found
            InsufficientInventoryException: If quantity would become negative
        """
        with self.transaction():
            material = self.repository.get_by_id(material_id)

            if not material:
                raise MaterialNotFoundException(material_id)

            # Store previous quantity for event
            previous_quantity = material.quantity

            # Calculate new quantity
            new_quantity = previous_quantity + quantity_change

            # Check for negative inventory
            if new_quantity < 0:
                raise InsufficientInventoryException(
                    material_id, abs(quantity_change), previous_quantity
                )

            # Update material status based on new quantity
            if new_quantity == 0:
                new_status = InventoryStatus.OUT_OF_STOCK.value
            elif new_quantity <= material.reorder_point:
                new_status = InventoryStatus.LOW_STOCK.value
            else:
                new_status = InventoryStatus.IN_STOCK.value

            # Update material
            updated = self.repository.update(
                material_id, {"quantity": new_quantity, "status": new_status}
            )

            # Record inventory transaction
            self._record_inventory_transaction(
                material_id=material_id,
                quantity_change=quantity_change,
                reason=reason,
                project_id=project_id,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    MaterialStockChanged(
                        material_id=material_id,
                        previous_quantity=previous_quantity,
                        new_quantity=new_quantity,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Material:{material_id}")

            return updated

    def adjust_inventory_with_optimistic_locking(
            self,
            material_id: int,
            quantity_change: float,
            version: int,
            reason: str,
            project_id: Optional[int] = None,
            max_retries: int = 3,
    ) -> Material:
        """
        Adjust inventory with optimistic locking to prevent conflicts.

        Args:
            material_id: Material ID
            quantity_change: Amount to change (positive or negative)
            version: Expected version of the material
            reason: Reason for adjustment
            project_id: Optional related project ID
            max_retries: Maximum retry attempts on version conflict

        Returns:
            Updated material

        Raises:
            MaterialNotFoundException: If material not found
            InsufficientInventoryException: If quantity would become negative
            ConcurrentModificationException: On version conflict after retries
        """
        retry_count = 0

        while retry_count < max_retries:
            try:
                with self.transaction():
                    material = self.repository.get_by_id(material_id)

                    if not material:
                        raise MaterialNotFoundException(material_id)

                    if material.version != version:
                        raise ConcurrentModificationException(
                            f"Material version mismatch: expected {version}, found {material.version}",
                            expected_version=version,
                            actual_version=material.version,
                        )

                    # Store previous quantity for event
                    previous_quantity = material.quantity

                    # Calculate new quantity
                    new_quantity = previous_quantity + quantity_change

                    # Check for negative inventory
                    if new_quantity < 0:
                        raise InsufficientInventoryException(
                            material_id, abs(quantity_change), previous_quantity
                        )

                    # Update material status based on new quantity
                    if new_quantity == 0:
                        new_status = InventoryStatus.OUT_OF_STOCK.value
                    elif new_quantity <= material.reorder_point:
                        new_status = InventoryStatus.LOW_STOCK.value
                    else:
                        new_status = InventoryStatus.IN_STOCK.value

                    # Update material
                    updated = self.repository.update(
                        material_id,
                        {
                            "quantity": new_quantity,
                            "status": new_status,
                            "version": version + 1,  # Increment version
                        },
                    )

                    # Record inventory transaction
                    self._record_inventory_transaction(
                        material_id=material_id,
                        quantity_change=quantity_change,
                        reason=reason,
                        project_id=project_id,
                    )

                    # Publish event if event bus exists
                    if self.event_bus:
                        user_id = (
                            self.security_context.current_user.id
                            if self.security_context
                            else None
                        )
                        self.event_bus.publish(
                            MaterialStockChanged(
                                material_id=material_id,
                                previous_quantity=previous_quantity,
                                new_quantity=new_quantity,
                                reason=reason,
                                user_id=user_id,
                            )
                        )

                    # Invalidate cache if cache service exists
                    if self.cache_service:
                        self.cache_service.invalidate(f"Material:{material_id}")

                    return updated

            except ConcurrentModificationException:
                # Retry with exponential backoff
                retry_count += 1
                if retry_count >= max_retries:
                    raise

                # Wait with exponential backoff
                time.sleep(0.1 * (2 ** retry_count))

                # Refresh material for next attempt
                material = self.repository.get_by_id(material_id)
                if material:
                    version = material.version

        raise ConcurrentModificationException(
            "Max retries exceeded for concurrent modification"
        )

    def get_low_stock_materials(
            self, threshold_percentage: float = 20.0
    ) -> List[Material]:
        """
        Get materials that are low in stock (below reorder threshold).

        Args:
            threshold_percentage: Percentage threshold (default 20%)

        Returns:
            List of materials below their reorder point
        """
        return self.repository.get_low_stock_materials()

    def get_materials_by_storage_location(self, location_id: int) -> List[Material]:
        """
        Get materials stored at a specific location.

        Args:
            location_id: Storage location ID

        Returns:
            List of materials at the specified location
        """
        return self.repository.find_by_storage_location(location_id)

    def get_material_with_supplier_info(self, material_id: int) -> Dict[str, Any]:
        """
        Get material with supplier information.

        Args:
            material_id: Material ID

        Returns:
            Material with supplier information

        Raises:
            MaterialNotFoundException: If material not found
        """
        material = self.repository.get_by_id_with_supplier(material_id)
        if not material:
            raise MaterialNotFoundException(material_id)
        return material

    def search_materials(
            self,
            query: str,
            material_type: Optional[str] = None,
            sort_by: str = "name",
            limit: int = 50,
    ) -> List[Material]:
        """
        Search materials by query string.

        Args:
            query: Search query string
            material_type: Optional material type filter
            sort_by: Field to sort by
            limit: Maximum number of results

        Returns:
            List of materials matching the search criteria
        """
        return self.repository.search_materials(query, skip=0, limit=limit)

    def calculate_material_usage_statistics(
            self,
            material_id: int,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate usage statistics for a material.

        Args:
            material_id: Material ID
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            Dictionary with usage statistics

        Raises:
            MaterialNotFoundException: If material not found
        """
        material = self.repository.get_by_id(material_id)
        if not material:
            raise MaterialNotFoundException(material_id)

        # Calculate various usage statistics
        usages = self.repository.get_material_usages(material_id, start_date, end_date)
        total_used = sum(
            usage.get("quantity_change", 0)
            for usage in usages
            if usage.get("quantity_change", 0) < 0
        )

        return {
            "material_id": material_id,
            "material_name": material.name,
            "total_used": abs(total_used),
            "usage_count": len(usages),
            "current_quantity": material.quantity,
            "usages": usages,
        }

    def _record_inventory_transaction(
            self,
            material_id: int,
            quantity_change: float,
            reason: str,
            project_id: Optional[int] = None,
    ) -> None:
        """
        Record an inventory transaction in the transaction log.

        Args:
            material_id: Material ID
            quantity_change: Quantity change (positive or negative)
            reason: Reason for the transaction
            project_id: Optional related project ID
        """
        # Implementation depends on transaction logging model
        # This would create a record in inventory_transactions table
        transaction_data = {
            "material_id": material_id,
            "quantity_change": quantity_change,
            "reason": reason,
            "project_id": project_id,
            "transaction_date": datetime.now(),
            "user_id": (
                self.security_context.current_user.id if self.security_context else None
            ),
        }

        # Use a repository to create the transaction record
        # For now, this is a placeholder as we haven't implemented the inventory_transaction repository
        # self.transaction_repository.create(transaction_data)
        pass

    def _create_created_event(self, entity: Material) -> DomainEvent:
        """
        Create event for material creation.

        Args:
            entity: Created material entity

        Returns:
            MaterialCreated event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return MaterialCreated(
            material_id=entity.id, material_type=entity.material_type, user_id=user_id
        )

    def _create_updated_event(
            self, original: Material, updated: Material
    ) -> DomainEvent:
        """
        Create event for material update.

        Args:
            original: Original material entity
            updated: Updated material entity

        Returns:
            MaterialUpdated event
        """
        changes = {}
        for key, new_value in updated.__dict__.items():
            if key.startswith("_"):
                continue
            old_value = getattr(original, key, None)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}

        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return MaterialUpdated(material_id=updated.id, changes=changes, user_id=user_id)

    def _create_deleted_event(self, entity: Material) -> DomainEvent:
        """
        Create event for material deletion.

        Args:
            entity: Deleted material entity

        Returns:
            MaterialDeleted event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return MaterialDeleted(material_id=entity.id, user_id=user_id)