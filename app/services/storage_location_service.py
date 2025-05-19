# File: app/services/storage_location_service.py
"""
Storage Location Service for the Dynamic Material Management System.

This service manages storage locations with dynamic properties, following
the same patterns as the dynamic material system. Provides functionality for:
- Creating and updating storage locations with dynamic properties
- Storage utilization management  
- Searching and filtering storage locations
- Settings-aware response formatting
- Theme integration
"""

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import json
import uuid

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    DuplicateEntityException,
    StorageLocationNotFoundException,
    InsufficientInventoryException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.storage import (
    StorageLocation,
    StorageLocationType,
    StorageLocationTypeProperty,
    StoragePropertyDefinition,
    StorageLocationPropertyValue,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.db.models.dynamic_material import DynamicMaterial, MaterialType
from app.repositories.storage_repository import (
    StorageLocationRepository,
    StorageCellRepository,
    StorageAssignmentRepository,
    StorageMoveRepository,
)
from app.services.base_service import BaseService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


# Domain Events
class StorageLocationDeleted(DomainEvent):
    """Event emitted when a storage location is deleted."""

    def __init__(
            self,
            location_id: str,
            user_id: Optional[int] = None,
    ):
        """Initialize storage location deleted event."""
        super().__init__()
        self.location_id = location_id
        self.user_id = user_id


class StorageLocationCreated(DomainEvent):
    """Event emitted when a storage location is created."""

    def __init__(
            self,
            location_id: str,
            location_name: str,
            location_type_id: int,
            user_id: Optional[int] = None,
    ):
        """Initialize storage location created event."""
        super().__init__()
        self.location_id = location_id
        self.location_name = location_name
        self.location_type_id = location_type_id
        self.user_id = user_id


class StorageAssignmentCreated(DomainEvent):
    """Event emitted when materials are assigned to a storage location."""

    def __init__(
            self,
            assignment_id: str,
            material_id: int,
            location_id: str,
            quantity: float,
            user_id: Optional[int] = None,
    ):
        """Initialize storage assignment created event."""
        super().__init__()
        self.assignment_id = assignment_id
        self.material_id = material_id
        self.location_id = location_id
        self.quantity = quantity
        self.user_id = user_id


class StorageMoveCreated(DomainEvent):
    """Event emitted when material is moved between storage locations."""

    def __init__(
            self,
            move_id: str,
            material_id: int,
            from_location_id: str,
            to_location_id: str,
            quantity: float,
            user_id: Optional[int] = None,
    ):
        """Initialize storage move created event."""
        super().__init__()
        self.move_id = move_id
        self.material_id = material_id
        self.from_location_id = from_location_id
        self.to_location_id = to_location_id
        self.quantity = quantity
        self.user_id = user_id


class StorageSpaceUpdated(DomainEvent):
    """Event emitted when storage capacity or utilization is updated."""

    def __init__(
            self,
            location_id: str,
            previous_capacity: int,
            new_capacity: int,
            previous_utilized: int,
            new_utilized: int,
            user_id: Optional[int] = None,
    ):
        """Initialize storage space updated event."""
        super().__init__()
        self.location_id = location_id
        self.previous_capacity = previous_capacity
        self.new_capacity = new_capacity
        self.previous_utilized = previous_utilized
        self.new_utilized = new_utilized
        self.user_id = user_id


# Validation functions
validate_storage_location = validate_entity(StorageLocation)
validate_storage_cell = validate_entity(StorageCell)
validate_storage_assignment = validate_entity(StorageAssignment)
validate_storage_move = validate_entity(StorageMove)


class StorageLocationService(BaseService[StorageLocation]):
    """
    Service for managing storage locations in the Dynamic Material Management System.

    Updated to follow the same patterns as DynamicMaterialService with:
    - Settings Framework integration
    - Theme System support
    - Dynamic storage location types
    - Event-driven architecture
    - Cache management
    """

    def __init__(
            self,
            session: Session,
            location_repository=None,
            cell_repository=None,
            assignment_repository=None,
            move_repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            settings_service=None,
            property_service=None,
            storage_location_type_service=None,
    ):
        """
        Initialize StorageLocationService with dependencies.

        Args:
            session: Database session for persistence operations
            location_repository: Optional repository for storage locations
            cell_repository: Optional repository for storage cells
            assignment_repository: Optional repository for storage assignments
            move_repository: Optional repository for storage moves
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            settings_service: Optional settings service for user preferences
            property_service: Optional property service for property validation
            storage_location_type_service: Optional storage location type service
        """
        # Initialize the base service first
        super().__init__(
            session=session,
            repository_class=None,  # We'll set repository directly
            security_context=security_context,
            event_bus=event_bus,
            cache_service=cache_service,
        )

        # Set our specific repositories
        self.repository = location_repository or StorageLocationRepository(session)
        self.cell_repository = cell_repository or StorageCellRepository(session)
        self.assignment_repository = (
                assignment_repository or StorageAssignmentRepository(session)
        )
        self.move_repository = move_repository or StorageMoveRepository(session)

        # Set additional service-specific dependencies
        self.settings_service = settings_service
        self.property_service = property_service
        self.storage_location_type_service = storage_location_type_service

    def get_storage_locations(
            self,
            skip: int = 0,
            limit: int = 100,
            storage_location_type_id: Optional[int] = None,
            search: Optional[str] = None,
            status: Optional[str] = None,
            section: Optional[str] = None,
            apply_settings: bool = True,
            search_params: Optional[Dict[str, Any]] = None,
            **filters
    ) -> Tuple[List[StorageLocation], int]:
        """
        Get storage locations with filtering and pagination.
        Follows the same pattern as DynamicMaterialService.get_materials().

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            storage_location_type_id: Optional filter by storage location type
            search: Optional search string for names and descriptions
            status: Optional filter by status
            section: Optional filter by section
            apply_settings: Whether to apply user settings
            search_params: Optional search parameters dict
            **filters: Additional filters

        Returns:
            Tuple of (list of storage locations, total count)
        """
        logger.info(
            f"Getting storage locations with params: type_id={storage_location_type_id}, "
            f"search='{search}', status='{status}', section='{section}'"
        )

        try:
            # Check cache first if available
            cache_key = None
            if self.cache_service:
                params_str = json.dumps({
                    "skip": skip,
                    "limit": limit,
                    "storage_location_type_id": storage_location_type_id,
                    "search": search,
                    "status": status,
                    "section": section,
                    **filters
                }, sort_keys=True)
                cache_key = f"storage_locations:{hash(params_str)}"
                cached = self.cache_service.get(cache_key)
                if cached:
                    logger.info(f"Retrieved {len(cached[0])} storage locations from cache")
                    locations, total = cached
                    if apply_settings and self.security_context and self.settings_service:
                        user_id = getattr(getattr(self.security_context, 'current_user', None), 'id', None)
                        if user_id:
                            locations = self.apply_settings_to_locations(locations, user_id)
                    return locations, total

            # Get locations with properties and relationships
            locations, total = self.repository.list_with_properties(
                skip=skip,
                limit=limit,
                storage_location_type_id=storage_location_type_id,
                search=search,
                status=status,
                section=section,
                **filters
            )

            # Apply settings if requested and security context is available
            if apply_settings and self.security_context and self.settings_service:
                user_id = getattr(getattr(self.security_context, 'current_user', None), 'id', None)
                if user_id:
                    locations = self.apply_settings_to_locations(locations, user_id)

            # Add to cache if available
            if self.cache_service and cache_key:
                self.cache_service.set(
                    cache_key, (locations, total), ttl=300
                )

            logger.info(f"Retrieved {len(locations)} storage locations")
            return locations, total

        except Exception as e:
            logger.error(f"Error fetching storage locations: {e}")
            return [], 0

    def get_storage_location(self, location_id: str) -> Optional[StorageLocation]:
        """
        Get a storage location by ID with its properties.

        Args:
            location_id: ID of the storage location

        Returns:
            Storage location if found, None otherwise
        """
        return self.repository.get_by_id_with_properties(location_id)

    def apply_settings_to_locations(
            self,
            locations: List[StorageLocation],
            user_id: int
    ) -> List[StorageLocation]:
        """
        Apply user settings to storage locations.
        Follows the same pattern as DynamicMaterialService.apply_settings_to_materials().

        Args:
            locations: List of storage locations to apply settings to
            user_id: ID of the user whose settings to apply

        Returns:
            List of storage locations with settings applied
        """
        if not self.settings_service or not locations:
            return locations

        try:
            # Get UI settings for storage
            storage_ui = self.settings_service.get_setting(
                key="storage_ui",
                scope_type="user",
                scope_id=str(user_id)
            )

            # If no settings found, return locations as is
            if not storage_ui:
                return locations

            # Card view settings
            card_view = storage_ui.get("card_view", {})
            show_card_thumbnail = card_view.get("display_thumbnail", True)
            max_card_properties = card_view.get("max_properties", 4)

            # List view settings
            list_view = storage_ui.get("list_view", {})
            list_columns = list_view.get("default_columns", [
                "name", "type", "capacity", "utilized", "section", "status"
            ])
            show_list_thumbnail = list_view.get("show_thumbnail", True)

            # Grid view settings
            grid_view = storage_ui.get("grid_view", {})
            show_utilization_bars = grid_view.get("show_utilization", True)
            show_capacity_indicators = grid_view.get("show_capacity", True)

            # Apply settings to each location
            for location in locations:
                # Create UI settings object if not exists
                if not hasattr(location, "ui_settings"):
                    location.ui_settings = {}

                # Set card view settings
                location.ui_settings["card_view"] = {
                    "max_properties": max_card_properties,
                    "show_thumbnail": show_card_thumbnail,
                    "properties": self._get_card_properties(location, max_card_properties)
                }

                # Set list view settings
                location.ui_settings["list_view"] = {
                    "columns": list_columns,
                    "show_thumbnail": show_list_thumbnail
                }

                # Set grid view settings
                location.ui_settings["grid_view"] = {
                    "show_utilization": show_utilization_bars,
                    "show_capacity": show_capacity_indicators
                }

                # Add theme information
                if location.storage_location_type:
                    location.ui_settings["theme"] = {
                        "color_scheme": location.storage_location_type.color_scheme or "default",
                        "icon": location.storage_location_type.icon or "storage"
                    }

        except Exception as e:
            logger.error(f"Error applying settings to storage locations: {str(e)}")

        return locations

    def _get_card_properties(self, location: StorageLocation, max_props: int) -> List[Dict]:
        """
        Get properties for card view based on settings.
        Similar to DynamicMaterialService._get_card_properties().
        """
        card_props = []

        # Add basic location properties first
        if location.capacity is not None:
            card_props.append({
                "name": "Capacity",
                "value": f"{location.utilized or 0}/{location.capacity}",
                "type": "capacity"
            })

        if location.section:
            card_props.append({
                "name": "Section",
                "value": location.section,
                "type": "section"
            })

        # Add custom properties if available
        if hasattr(location, 'property_values') and location.property_values:
            for prop_value in location.property_values:
                # Check if should be displayed in card view
                show_in_card = True

                # Check if storage location type defines display rules for this property
                if (hasattr(location, 'storage_location_type') and
                        location.storage_location_type and
                        hasattr(location.storage_location_type, 'properties')):
                    for type_prop in location.storage_location_type.properties:
                        if hasattr(type_prop, 'property_id') and type_prop.property_id == prop_value.property_id:
                            if hasattr(type_prop, 'is_displayed_in_card'):
                                show_in_card = type_prop.is_displayed_in_card

                if show_in_card:
                    # Get property definition if available
                    prop_def = getattr(prop_value, 'property', None)

                    card_props.append({
                        "id": getattr(prop_value, 'id', None),
                        "property_id": prop_value.property_id,
                        "name": getattr(prop_def, 'name', f"Property {prop_value.property_id}"),
                        "value": self._get_property_value(prop_value),
                        "type": "custom"
                    })

                    if len(card_props) >= max_props:
                        break

        return card_props[:max_props]

    def _get_property_value(self, prop_value):
        """
        Extract property value from a StorageLocationPropertyValue object.
        Same pattern as DynamicMaterialService._get_property_value().
        """
        # Try to get the value based on data type
        if hasattr(prop_value, 'value_string') and prop_value.value_string is not None:
            return prop_value.value_string
        elif hasattr(prop_value, 'value_number') and prop_value.value_number is not None:
            return prop_value.value_number
        elif hasattr(prop_value, 'value_boolean') and prop_value.value_boolean is not None:
            return "Yes" if prop_value.value_boolean else "No"
        elif hasattr(prop_value, 'value_date') and prop_value.value_date is not None:
            return prop_value.value_date
        elif hasattr(prop_value, 'value_enum_id') and prop_value.value_enum_id is not None:
            return prop_value.value_enum_id
        elif hasattr(prop_value, 'value') and prop_value.value is not None:
            return prop_value.value
        else:
            return None

    @validate_input(validate_storage_location)
    def create_storage_location(
            self,
            data: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> StorageLocation:
        """
        Create a new storage location with dynamic properties.
        Follows the same pattern as DynamicMaterialService.create_material().

        Args:
            data: Storage location data including property values
            user_id: Optional ID of user creating the storage location

        Returns:
            Created storage location

        Raises:
            ValidationException: If storage location data is invalid
            EntityNotFoundException: If storage location type not found
        """
        # Add created_by if provided
        if user_id:
            data["created_by"] = user_id

        # Validate required fields
        required_fields = ["storage_location_type_id", "name"]
        for field in required_fields:
            if not data.get(field):
                raise ValidationException(f"Field '{field}' is required")

        # Get storage location type to validate property values
        storage_location_type_id = data.get("storage_location_type_id")
        storage_location_type = None
        if self.storage_location_type_service:
            storage_location_type = self.storage_location_type_service.get_storage_location_type(
                storage_location_type_id)
        else:
            # Fallback to direct query
            storage_location_type = self.session.query(StorageLocationType).get(storage_location_type_id)

        if not storage_location_type:
            raise EntityNotFoundException(f"Storage location type with ID {storage_location_type_id} not found")

        # Check for duplicate name in the same section
        section = data.get("section")
        name = data.get("name", "")

        if self._location_exists_by_name_and_section(name, section):
            raise DuplicateEntityException(
                f"Storage location with name '{name}' already exists in section '{section}'"
            )

        # Set default values if not provided
        if "status" not in data:
            data["status"] = "ACTIVE"

        if "utilized" not in data:
            data["utilized"] = 0

        # Validate and format property values
        property_values = data.get("property_values", [])
        if self.property_service:
            # Get type properties
            type_properties = []
            for loc_type_prop in storage_location_type.properties:
                prop_def = self.property_service.get_property_definition(loc_type_prop.property_id)
                if prop_def:
                    type_properties.append((loc_type_prop, prop_def))

            # Check required properties
            for type_prop, prop_def in type_properties:
                if type_prop.is_required and not any(pv.get("property_id") == prop_def.id for pv in property_values):
                    raise ValidationException(f"Required property '{prop_def.name}' missing")

            # Validate property values
            validated_properties = []
            for property_value in property_values:
                property_id = property_value.get("property_id")

                # Skip if property is not part of this storage location type
                if not any(tp.property_id == property_id for tp, _ in type_properties):
                    continue

                value = property_value.get("value")

                # Find property definition
                prop_def = next((pd for _, pd in type_properties if pd.id == property_id), None)
                if not prop_def:
                    continue

                # Validate value
                if not self.property_service.validate_property_value(property_id, value):
                    raise ValidationException(f"Invalid value for property '{prop_def.name}'")

                validated_properties.append({
                    "property_id": property_id,
                    "value": value
                })

            # Update property values with validated ones
            data["property_values"] = validated_properties

        with self.transaction():
            # Create storage location with property values
            location = self.repository.create_with_properties(data)

            # Create cells if dimensions are provided
            dimensions = data.get("dimensions")
            if dimensions and isinstance(dimensions, dict):
                self._create_cells_for_location(location.id, dimensions)

            # Publish event if event bus exists
            if self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context and hasattr(self.security_context, 'current_user')
                    else None
                )
                self.event_bus.publish(
                    StorageLocationCreated(
                        location_id=str(location.id),
                        location_name=location.name,
                        location_type_id=storage_location_type_id,
                        user_id=user_id_for_event,
                    )
                )

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("storage_locations:*")
                if storage_location_type_id:
                    self.cache_service.invalidate_pattern(f"storage_locations:type:{storage_location_type_id}:*")

            return location

    def update_storage_location(
            self,
            id: str,
            data: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> Optional[StorageLocation]:
        """
        Update an existing storage location.

        Args:
            id: ID of the storage location to update
            data: Updated storage location data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated storage location if found, None otherwise

        Raises:
            ValidationException: If storage location data is invalid
        """
        with self.transaction():
            # Get existing location
            location = self.repository.get_by_id_with_properties(id)
            if not location:
                return None

            # Cannot change storage location type
            if "storage_location_type_id" in data and data[
                "storage_location_type_id"] != location.storage_location_type_id:
                raise ValidationException("Cannot change storage location type")

            # Validate property values if provided
            if "property_values" in data and self.property_service:
                property_values = data["property_values"]

                # Get storage location type properties
                storage_location_type = location.storage_location_type
                type_properties = []
                for loc_type_prop in storage_location_type.properties:
                    prop_def = self.property_service.get_property_definition(loc_type_prop.property_id)
                    if prop_def:
                        type_properties.append((loc_type_prop, prop_def))

                # Check required properties
                for type_prop, prop_def in type_properties:
                    if type_prop.is_required and not any(
                            pv.get("property_id") == prop_def.id for pv in property_values):
                        # Check if there's an existing value
                        existing_value = next((pv for pv in location.property_values if pv.property_id == prop_def.id),
                                              None)
                        if not existing_value:
                            raise ValidationException(f"Required property '{prop_def.name}' missing")

                # Validate property values
                validated_properties = []
                for property_value in property_values:
                    property_id = property_value.get("property_id")

                    # Skip if property is not part of this storage location type
                    if not any(tp.property_id == property_id for tp, _ in type_properties):
                        continue

                    value = property_value.get("value")

                    # Find property definition
                    prop_def = next((pd for _, pd in type_properties if pd.id == property_id), None)
                    if not prop_def:
                        continue

                    # Validate value
                    if not self.property_service.validate_property_value(property_id, value):
                        raise ValidationException(f"Invalid value for property '{prop_def.name}'")

                    validated_properties.append({
                        "property_id": property_id,
                        "value": value
                    })

                # Update property values with validated ones
                data["property_values"] = validated_properties

            # Update storage location
            updated_location = self.repository.update_with_properties(id, data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"storage_locations:{id}")
                self.cache_service.invalidate_pattern("storage_locations:*")
                self.cache_service.invalidate_pattern(f"storage_locations:type:{location.storage_location_type_id}:*")

            return updated_location

    def delete_storage_location(self, id: str, user_id: Optional[int] = None) -> bool:
        """
        Delete a storage location.

        Args:
            id: ID of the storage location to delete
            user_id: Optional ID of the user performing the deletion

        Returns:
            True if deleted, False otherwise
        """
        with self.transaction():
            # Get location
            location = self.repository.get_by_id(id)
            if not location:
                return False

            # Check if location has any assignments
            assignments = self.assignment_repository.get_assignments_by_storage(id)
            if assignments:
                raise BusinessRuleException(
                    f"Cannot delete storage location '{location.name}' as it has {len(assignments)} active assignments"
                )

            # Get storage location type ID for cache invalidation
            storage_location_type_id = location.storage_location_type_id

            # Delete location
            result = self.repository.delete(id)

            # Publish event if successful
            if result and self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context and hasattr(self.security_context, 'current_user')
                    else None
                )
                self.event_bus.publish(
                    StorageLocationDeleted(
                        location_id=id,
                        user_id=user_id_for_event,
                    )
                )

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"storage_locations:{id}")
                self.cache_service.invalidate_pattern("storage_locations:*")
                self.cache_service.invalidate_pattern(f"storage_locations:type:{storage_location_type_id}:*")

            return result

    def _location_exists_by_name_and_section(
            self, name: str, section: Optional[str]
    ) -> bool:
        """
        Check if a storage location exists with the given name and section.
        """
        if not name:
            return False

        # Create filter criteria
        filters = {"name": name}
        if section:
            filters["section"] = section

        # Check if any location matches the criteria
        existing_locations = self.repository.list(**filters)
        return len(existing_locations) > 0

    def _create_cells_for_location(
            self, location_id: str, dimensions: Dict[str, Any]
    ) -> None:
        """
        Create storage cells for a location based on dimensions.

        Args:
            location_id: ID of the storage location
            dimensions: Dimensions object with width, height, etc.
        """
        width = dimensions.get("width", 0)
        height = dimensions.get("height", 0)

        # Skip if no dimensions
        if not width or not height:
            return

        # Create cells in grid format
        for row in range(1, height + 1):
            for col in range(1, width + 1):
                # Create position information
                position = {"row": row, "column": col}

                # Create cell
                cell_data = {
                    "storage_id": location_id,
                    "position": position,
                    "occupied": False,
                }

                self.cell_repository.create(cell_data)

    # Additional methods following the original service patterns but updated for dynamic system
    def get_storage_cells(self, location_id: str, occupied: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Get cells for a storage location with optional filter and material information.
        """
        logger.info(f"Getting cells for storage location ID: {location_id}")

        try:
            # Query cells directly from repository with material relationships
            cells = self.cell_repository.get_cells_by_storage(location_id)

            # Format cells for API
            formatted_cells = []
            for cell in cells:
                # Basic cell info
                cell_data = {
                    "id": str(getattr(cell, "id", "")),
                    "storage_id": str(getattr(cell, "storage_id", location_id)),
                    "occupied": bool(getattr(cell, "occupied", False)),
                    "material_id": getattr(cell, "material_id", None),
                    "position": cell.position or {"row": 1, "column": 1},
                }

                # Add material information if available via relationship
                if cell.material:
                    cell_data["material"] = {
                        "id": cell.material.id,
                        "name": cell.material.name,
                        "sku": cell.material.sku,
                        "unit": cell.material.unit,
                        "material_type": {
                            "id": cell.material.material_type.id,
                            "name": cell.material.material_type.name
                        } if cell.material.material_type else None
                    }

                # Apply filter if specified
                if occupied is None or cell_data["occupied"] == occupied:
                    formatted_cells.append(cell_data)

            logger.info(f"Retrieved {len(formatted_cells)} cells for location {location_id}")
            return formatted_cells

        except Exception as e:
            logger.error(f"Error getting cells for location {location_id}: {e}")

            # Generate a default grid as fallback
            default_cells = []
            for row in range(1, 5):
                for col in range(1, 5):
                    default_cells.append({
                        "id": f"default_{location_id}_{row}_{col}",
                        "storage_id": str(location_id),
                        "position": {"row": row, "column": col},
                        "occupied": False,
                        "material_id": None,
                    })

            logger.warning(f"Returning default grid with {len(default_cells)} cells")
            return default_cells

    def get_storage_assignments(
            self,
            material_id: Optional[int] = None,
            material_type_id: Optional[int] = None,
            location_id: Optional[str] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get storage assignments with pagination using proper material relationships.
        """
        logger.info(
            f"Getting storage assignments with filters: material_id={material_id}, "
            f"material_type_id={material_type_id}, location_id={location_id}"
        )

        try:
            # Set a safe limit to prevent memory errors
            MAX_RESULTS = 500
            actual_limit = min(limit, MAX_RESULTS)

            # Use repository methods that leverage relationships
            if material_id:
                assignments_db = self.assignment_repository.get_assignments_by_material(material_id)
            elif material_type_id:
                assignments_db = self.assignment_repository.get_assignments_by_material_type(
                    material_type_id, skip=skip, limit=actual_limit
                )
            elif location_id:
                assignments_db = self.assignment_repository.get_assignments_by_storage(location_id)
            else:
                # Get all assignments with pagination
                assignments_db = self.assignment_repository.list(
                    skip=skip, limit=actual_limit
                )

            # Apply manual pagination if not already applied by repository
            if not (material_type_id and skip == 0):
                assignments_db = assignments_db[skip:skip + actual_limit]

            # Process assignments for API
            assignments = []
            for assignment in assignments_db:
                formatted = self._format_assignment_for_api(assignment)
                assignments.append(formatted)

            logger.info(f"Retrieved {len(assignments)} storage assignments")
            return assignments

        except Exception as e:
            logger.error(f"Error fetching storage assignments: {e}")
            return []

    def _format_assignment_for_api(self, assignment) -> Dict[str, Any]:
        """
        Format a storage assignment for API response using relationships.
        """
        if not assignment:
            return None

        # Create base result with safe defaults
        result = {
            "id": str(getattr(assignment, "id", "")),
            "storage_id": str(getattr(assignment, "storage_id", "")),
            "material_id": getattr(assignment, "material_id", None),
            "quantity": float(getattr(assignment, "quantity", 0)),
            "position": assignment.position,
            "assigned_date": None,
            "assigned_by": getattr(assignment, "assigned_by", None),
            "notes": getattr(assignment, "notes", ""),
        }

        # Add material information via relationship
        if assignment.material:
            result["material"] = {
                "id": assignment.material.id,
                "name": assignment.material.name,
                "unit": assignment.material.unit,
                "sku": assignment.material.sku,
                "status": assignment.material.status,
                "material_type": {
                    "id": assignment.material.material_type.id,
                    "name": assignment.material.material_type.name
                } if assignment.material.material_type else None
            }

        # Add location information via relationship
        if assignment.location:
            result["location"] = {
                "id": str(assignment.location.id),
                "name": assignment.location.name,
                "storage_location_type": {
                    "id": assignment.location.storage_location_type.id,
                    "name": assignment.location.storage_location_type.name,
                    "icon": assignment.location.storage_location_type.icon,
                    "color_scheme": assignment.location.storage_location_type.color_scheme
                } if assignment.location.storage_location_type else None,
                "section": assignment.location.section
            }

        # Handle assigned date
        assigned_date = getattr(assignment, "assigned_date", None)
        if assigned_date:
            if hasattr(assigned_date, "isoformat"):
                result["assigned_date"] = assigned_date.isoformat()
            else:
                result["assigned_date"] = str(assigned_date)

        return result

    def get_storage_moves(
            self,
            skip: int = 0,
            limit: int = 100,
            material_id: Optional[int] = None,
            material_type_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get storage moves with optional filtering and pagination using relationships.
        """
        logger.info(
            f"Getting storage moves with filters: material_id={material_id}, "
            f"material_type_id={material_type_id}"
        )

        try:
            # Use repository methods that leverage relationships
            if material_id:
                moves = self.move_repository.get_moves_by_material(
                    material_id, skip=skip, limit=limit
                )
            elif material_type_id:
                moves = self.move_repository.get_moves_by_material_type(
                    material_type_id, skip=skip, limit=limit
                )
            else:
                moves = self.move_repository.list(skip=skip, limit=limit)

            # Format moves for API
            formatted_moves = []
            for move in moves:
                formatted = self._format_move_for_api(move)
                formatted_moves.append(formatted)

            logger.info(f"Retrieved {len(formatted_moves)} storage moves")
            return formatted_moves

        except Exception as e:
            logger.error(f"Error retrieving storage moves: {e}")
            return []

    def _format_move_for_api(self, move) -> Dict[str, Any]:
        """
        Format a storage move for API response using relationships.
        """
        if not move:
            return None

        result = {
            "id": str(getattr(move, "id", "")),
            "material_id": getattr(move, "material_id", None),
            "from_storage_id": str(getattr(move, "from_storage_id", "")),
            "to_storage_id": str(getattr(move, "to_storage_id", "")),
            "quantity": float(getattr(move, "quantity", 0)),
            "move_date": getattr(move, "move_date", None),
            "moved_by": getattr(move, "moved_by", None),
            "reason": getattr(move, "reason", None),
            "notes": getattr(move, "notes", None),
        }

        # Add material information via relationship
        if move.material:
            result["material"] = {
                "id": move.material.id,
                "name": move.material.name,
                "unit": move.material.unit,
                "sku": move.material.sku,
                "material_type": {
                    "id": move.material.material_type.id,
                    "name": move.material.material_type.name
                } if move.material.material_type else None
            }

        # Add location information via relationships
        if move.from_location:
            result["from_location"] = {
                "id": str(move.from_location.id),
                "name": move.from_location.name,
                "storage_location_type": {
                    "name": move.from_location.storage_location_type.name
                } if move.from_location.storage_location_type else None
            }

        if move.to_location:
            result["to_location"] = {
                "id": str(move.to_location.id),
                "name": move.to_location.name,
                "storage_location_type": {
                    "name": move.to_location.storage_location_type.name
                } if move.to_location.storage_location_type else None
            }

        return result

    def create_storage_assignment(
            self,
            assignment_data: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new storage assignment with proper material validation.
        """
        with self.transaction():
            # Extract data
            assignment_dict = (
                assignment_data.dict()
                if hasattr(assignment_data, "dict")
                else dict(assignment_data)
            )

            # Validate material exists using proper query
            material_id = assignment_dict.get("material_id")
            if material_id:
                material = self.session.query(DynamicMaterial).get(material_id)
                if not material:
                    raise EntityNotFoundException(f"Material with ID {material_id} not found")

            # Validate storage location exists
            storage_id = assignment_dict.get("storage_id")
            if storage_id:
                location = self.repository.get_by_id(storage_id)
                if not location:
                    raise EntityNotFoundException(f"Storage location with ID {storage_id} not found")

            # Add assigned_by if provided
            if user_id and "assigned_by" not in assignment_dict:
                assignment_dict["assigned_by"] = str(user_id)

            # Set assigned date if not provided
            if "assigned_date" not in assignment_dict:
                assignment_dict["assigned_date"] = datetime.now().isoformat()

            # Create assignment
            assignment = self.assignment_repository.create(assignment_dict)

            # Update location utilization
            quantity = assignment_dict.get("quantity", 0)
            if location and quantity > 0:
                current_utilized = location.utilized or 0
                self.repository.update(
                    storage_id, {"utilized": current_utilized + 1}  # Count as 1 item regardless of quantity
                )

            # Publish event if event bus exists
            if self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context and hasattr(self.security_context, 'current_user')
                    else None
                )
                self.event_bus.publish(
                    StorageAssignmentCreated(
                        assignment_id=str(assignment.id),
                        material_id=material_id,
                        location_id=storage_id,
                        quantity=quantity,
                        user_id=user_id_for_event,
                    )
                )

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("storage_assignments:*")
                self.cache_service.invalidate_pattern("storage_locations:*")

            # Format assignment for API response
            formatted_assignment = self._format_assignment_for_api(assignment)

            logger.info(
                f"Created storage assignment for material {material_id} in location {storage_id}"
            )
            return formatted_assignment

    def create_storage_move(
            self,
            move_data: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new storage move with proper material validation.
        """
        with self.transaction():
            # Extract data
            move_dict = move_data.dict() if hasattr(move_data, "dict") else dict(move_data)

            # Validate material exists
            material_id = move_dict.get("material_id")
            if material_id:
                material = self.session.query(DynamicMaterial).get(material_id)
                if not material:
                    raise EntityNotFoundException(f"Material with ID {material_id} not found")

            # Validate storage locations exist
            from_storage_id = move_dict.get("from_storage_id")
            to_storage_id = move_dict.get("to_storage_id")

            if from_storage_id:
                from_location = self.repository.get_by_id(from_storage_id)
                if not from_location:
                    raise EntityNotFoundException(f"Source storage location with ID {from_storage_id} not found")

            if to_storage_id:
                to_location = self.repository.get_by_id(to_storage_id)
                if not to_location:
                    raise EntityNotFoundException(f"Destination storage location with ID {to_storage_id} not found")

            # Add moved_by if provided
            if user_id and "moved_by" not in move_dict:
                move_dict["moved_by"] = str(user_id)

            # Set move date if not provided
            if "move_date" not in move_dict:
                move_dict["move_date"] = datetime.now().isoformat()

            # Create move record
            move = self.move_repository.create(move_dict)

            # Execute the actual move (update assignments)
            move.execute_move(self.session)

            # Publish event if event bus exists
            if self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context and hasattr(self.security_context, 'current_user')
                    else None
                )
                self.event_bus.publish(
                    StorageMoveCreated(
                        move_id=str(move.id),
                        material_id=material_id,
                        from_location_id=from_storage_id,
                        to_location_id=to_storage_id,
                        quantity=move_dict.get("quantity", 0),
                        user_id=user_id_for_event,
                    )
                )

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("storage_moves:*")
                self.cache_service.invalidate_pattern("storage_assignments:*")
                self.cache_service.invalidate_pattern("storage_locations:*")

            # Format move for API response
            formatted_move = self._format_move_for_api(move)

            logger.info(
                f"Created storage move for material {material_id} from {from_storage_id} to {to_storage_id}"
            )
            return formatted_move

    def delete_storage_assignment(
            self,
            assignment_id: str,
            user_id: Optional[int] = None
    ) -> bool:
        """
        Delete a storage assignment.
        """
        with self.transaction():
            # Get assignment first to update location utilization
            assignment = self.assignment_repository.get_by_id(assignment_id)
            if not assignment:
                return False

            location_id = assignment.storage_id

            # Delete assignment
            result = self.assignment_repository.delete(assignment_id)

            # Update location utilization
            if result:
                location = self.repository.get_by_id(location_id)
                if location:
                    current_utilized = location.utilized or 0
                    new_utilized = max(0, current_utilized - 1)
                    self.repository.update(location_id, {"utilized": new_utilized})

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate_pattern("storage_assignments:*")
                self.cache_service.invalidate_pattern("storage_locations:*")

            return result

    def get_storage_occupancy_report(
            self,
            section: Optional[str] = None,
            location_type_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a storage occupancy report with accurate utilization calculations.
        Updated to use dynamic storage location types.
        """
        logger.info(
            f"Generating storage occupancy report. Filters: section={section}, type_id={location_type_id}"
        )

        # Initialize results dictionary
        result = {
            "total_locations": 0,
            "total_capacity": 0.0,
            "total_utilized": 0.0,
            "total_items": 0,
            "utilization_percentage": 0.0,
            "overall_usage_percentage": 0.0,
            "items_by_type": {},
            "by_type": {},
            "by_section": {},
            "locations_by_type": {},
            "locations_by_section": {},
            "locations_at_capacity": 0,
            "locations_nearly_empty": 0,
            "most_utilized_locations": [],
            "least_utilized_locations": [],
            "recommendations": [],
        }

        try:
            # Get locations with filters
            filters = {}
            if section:
                filters["section"] = section
            if location_type_id:
                filters["storage_location_type_id"] = location_type_id

            locations, _ = self.get_storage_locations(
                skip=0, limit=10000, apply_settings=False, **filters
            )
            result["total_locations"] = len(locations)

            if not locations:
                logger.warning("No storage locations found matching criteria. Returning empty report.")
                return result

            # Process location statistics
            total_capacity = 0.0
            total_utilized = 0.0
            by_type = {}
            by_section = {}
            locations_by_type = {}
            locations_by_section = {}
            location_utilization_details = {}
            locations_at_capacity = 0
            locations_nearly_empty = 0

            for location in locations:
                loc_id = str(location.id)
                capacity = float(location.capacity or 0)
                utilized = float(location.utilized or 0)

                total_capacity += capacity
                total_utilized += utilized

                utilization_pct = (utilized / capacity * 100) if capacity > 0 else 0.0

                # Store details for sorting later
                location_utilization_details[loc_id] = {
                    "id": loc_id,
                    "name": location.name,
                    "capacity": int(capacity),
                    "utilized": int(utilized),
                    "utilization_percentage": round(utilization_pct, 1),
                }

                # Group by storage location type
                if location.storage_location_type:
                    type_name = location.storage_location_type.name
                    locations_by_type[type_name] = locations_by_type.get(type_name, 0) + 1

                    type_stats = by_type.setdefault(type_name, {
                        "capacity": 0.0,
                        "utilized": 0.0,
                        "locations": 0,
                        "utilization_percentage": 0.0,
                    })
                    type_stats["capacity"] += capacity
                    type_stats["utilized"] += utilized
                    type_stats["locations"] += 1

                # Group by section
                section_name = location.section or "Unknown"
                locations_by_section[section_name] = locations_by_section.get(section_name, 0) + 1

                section_stats = by_section.setdefault(section_name, {
                    "capacity": 0.0,
                    "utilized": 0.0,
                    "locations": 0,
                    "utilization_percentage": 0.0,
                })
                section_stats["capacity"] += capacity
                section_stats["utilized"] += utilized
                section_stats["locations"] += 1

                # Check capacity thresholds
                if capacity > 0:
                    if utilization_pct >= 95:
                        locations_at_capacity += 1
                    elif utilization_pct <= 10:
                        locations_nearly_empty += 1

            # Calculate material type distribution
            try:
                items_by_type_query = (
                    self.session.query(
                        MaterialType.name,
                        func.count(StorageAssignment.material_id.distinct()).label("unique_materials"),
                        func.sum(StorageAssignment.quantity).label("total_quantity")
                    )
                    .join(StorageAssignment.material)
                    .join(DynamicMaterial.material_type)
                    .group_by(MaterialType.name)
                    .all()
                )

                items_by_type_calc = {}
                total_items_count = 0

                for material_type_name, unique_count, total_qty in items_by_type_query:
                    type_name_lower = str(material_type_name).lower()
                    items_by_type_calc[type_name_lower] = {
                        "unique_materials": unique_count,
                        "total_quantity": float(total_qty) if total_qty else 0.0
                    }
                    total_items_count += unique_count

                result["items_by_type"] = items_by_type_calc
                result["total_items"] = total_items_count

            except Exception as e:
                logger.error(f"Error calculating items_by_type: {e}")
                result["items_by_type"] = {"error": "Calculation failed"}
                result["total_items"] = 0

            # Final calculations
            result["total_capacity"] = total_capacity
            result["total_utilized"] = total_utilized
            result["locations_at_capacity"] = locations_at_capacity
            result["locations_nearly_empty"] = locations_nearly_empty

            if total_capacity > 0:
                usage_pct = (total_utilized / total_capacity) * 100
                result["utilization_percentage"] = round(usage_pct, 1)
                result["overall_usage_percentage"] = round(usage_pct, 1)

            # Calculate final percentages for breakdowns
            for stats in by_type.values():
                cap = stats.get("capacity", 0.0)
                ut = stats.get("utilized", 0.0)
                stats["utilization_percentage"] = round((ut / cap) * 100, 1) if cap > 0 else 0.0

            for stats in by_section.values():
                cap = stats.get("capacity", 0.0)
                ut = stats.get("utilized", 0.0)
                stats["utilization_percentage"] = round((ut / cap) * 100, 1) if cap > 0 else 0.0

            result["by_type"] = by_type
            result["by_section"] = by_section
            result["locations_by_type"] = locations_by_type
            result["locations_by_section"] = locations_by_section

            # Sort locations by utilization
            sorted_locations = sorted(
                location_utilization_details.values(),
                key=lambda x: x["utilization_percentage"],
                reverse=True,
            )

            result["most_utilized_locations"] = sorted_locations[:5]
            result["least_utilized_locations"] = [
                                                     loc for loc in reversed(sorted_locations)
                                                     if loc["capacity"] > 0 and loc["utilization_percentage"] > 0
                                                 ][:5]

            # Generate recommendations
            recommendations = []
            usage_pct_final = result["utilization_percentage"]
            if usage_pct_final > 85:
                recommendations.append(
                    "Overall utilization is high. Consider expanding storage or optimizing existing space."
                )
            elif usage_pct_final < 25:
                recommendations.append(
                    "Overall utilization is low. Consider consolidating storage."
                )
            if result["locations_at_capacity"] > 0:
                recommendations.append(
                    f"Address {result['locations_at_capacity']} locations at or near capacity (>=95%)."
                )
            if result["locations_nearly_empty"] > 0:
                recommendations.append(
                    f"Review {result['locations_nearly_empty']} nearly empty locations (<=10%) for potential consolidation."
                )
            result["recommendations"] = recommendations

            logger.info("Generated storage occupancy report successfully.")
            return result

        except Exception as e:
            logger.error(f"Error generating storage occupancy report: {e}", exc_info=True)
            result["recommendations"] = ["Error generating report."]
            return result

    def update_storage_utilization_from_assignments(self) -> Dict[str, Any]:
        """
        Synchronize storage utilization counts based on material assignments.
        """
        logger.info("Synchronizing storage utilization from assignments")

        try:
            # Get all storage assignments
            all_assignments = self.assignment_repository.list()
            logger.info(f"Found {len(all_assignments)} storage assignments")

            # Count assignments per location
            location_counts = {}
            for assignment in all_assignments:
                loc_id = getattr(assignment, "storage_id", None)
                if loc_id:
                    location_counts[loc_id] = location_counts.get(loc_id, 0) + 1

            # Update each storage location's utilized count
            updated_count = 0
            updated_locations = []

            for loc_id, count in location_counts.items():
                try:
                    loc = self.repository.get_by_id(loc_id)
                    if loc:
                        # Remember previous value for logging
                        previous_count = loc.utilized or 0

                        # Update the count
                        self.repository.update(loc_id, {"utilized": count})

                        updated_count += 1
                        updated_locations.append({
                            "id": loc_id,
                            "name": getattr(loc, "name", "Unknown"),
                            "previous_count": previous_count,
                            "new_count": count,
                        })

                        logger.debug(
                            f"Updated location {getattr(loc, 'name', 'Unknown')} (ID: {loc_id}): "
                            f"utilized from {previous_count} to {count}"
                        )
                except Exception as loc_error:
                    logger.error(f"Error updating location {loc_id}: {loc_error}")

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate_pattern("storage_locations:*")

            logger.info(f"Successfully updated utilization for {updated_count} storage locations")

            return {
                "updated_count": updated_count,
                "updated_locations": updated_locations,
            }

        except Exception as e:
            logger.error(f"Error synchronizing storage utilization: {e}", exc_info=True)
            raise