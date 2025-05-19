# File: app/services/storage_location_type_service.py
"""
Storage Location Type Service for the Dynamic Material Management System.

This service manages storage location types with dynamic properties, following
the same patterns as MaterialTypeService. Provides functionality for:
- Creating and updating storage location types with dynamic properties
- Property assignment and validation
- Translation management
- Settings integration
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import json

from app.services.base_service import BaseService
from app.db.models.storage import (
    StorageLocationType,
    StorageLocationTypeProperty,
    StorageLocationTypeTranslation,
    StoragePropertyDefinition,
)
from app.repositories.storage_repository import StorageLocationTypeRepository
from app.core.exceptions import EntityNotFoundException, ValidationException, DuplicateEntityException
from app.services.settings_service import SettingsService


class StorageLocationTypeService(BaseService[StorageLocationType]):
    """
    Service for managing storage location types in the Dynamic Material Management System.

    Follows the same patterns as MaterialTypeService with:
    - Dynamic property management
    - Translation support
    - Settings integration
    - Validation and business rules
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            property_service=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            settings_service=None,
    ):
        """
        Initialize StorageLocationTypeService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            property_service: Optional PropertyDefinitionService for property validation
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            settings_service: Optional settings service for user settings
        """
        self.session = session
        self.repository = repository or StorageLocationTypeRepository(session)
        self.property_service = property_service
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.settings_service = settings_service

    def get_storage_location_types(
            self,
            skip: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
            visibility_level: Optional[str] = None,
            apply_settings: bool = True,
            **filters
    ) -> Tuple[List[StorageLocationType], int]:
        """
        Get storage location types with filtering and pagination.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            search: Optional search string for names
            visibility_level: Optional filter by visibility level
            apply_settings: Whether to apply user settings
            **filters: Additional filters

        Returns:
            Tuple of (list of storage location types, total count)
        """
        types, total = self.repository.list_with_properties(
            skip=skip,
            limit=limit,
            search=search,
            visibility_level=visibility_level,
            **filters
        )

        # Apply settings if requested and security context is available
        if apply_settings and self.security_context and self.settings_service:
            user_id = getattr(getattr(self.security_context, 'current_user', None), 'id', None)
            if user_id:
                types = self.apply_settings_to_types(types, user_id)

        return types, total

    def get_storage_location_type(self, type_id: int) -> Optional[StorageLocationType]:
        """
        Get a storage location type by ID.

        Args:
            type_id: ID of the storage location type

        Returns:
            Storage location type if found, None otherwise
        """
        return self.repository.get_by_id_with_properties(type_id)

    def create_storage_location_type(
            self,
            data: Dict[str, Any],
            created_by: Optional[int] = None
    ) -> StorageLocationType:
        """
        Create a new storage location type with properties.

        Args:
            data: Storage location type data including properties
            created_by: Optional ID of user creating the type

        Returns:
            Created storage location type

        Raises:
            ValidationException: If type data is invalid
            DuplicateEntityException: If type name already exists
        """
        # Add created_by if provided
        if created_by:
            data["created_by"] = created_by

        # Validate required fields
        required_fields = ["name"]
        for field in required_fields:
            if not data.get(field):
                raise ValidationException(f"Field '{field}' is required")

        # Check for duplicate name
        name = data.get("name", "")
        existing_types = self.repository.list(name=name)
        if existing_types:
            raise DuplicateEntityException(f"Storage location type with name '{name}' already exists")

        # Set default values if not provided
        if "visibility_level" not in data:
            data["visibility_level"] = "all"

        # Validate and format properties
        properties = data.get("properties", [])
        if self.property_service and properties:
            # Validate property assignments
            validated_properties = []
            for property_assignment in properties:
                property_id = property_assignment.get("property_id")

                # Verify property exists
                if not self.property_service.get_property_definition(property_id):
                    raise ValidationException(f"Property with ID {property_id} not found")

                validated_properties.append(property_assignment)

            data["properties"] = validated_properties

        with self.transaction():
            # Create storage location type
            type_obj = self.repository.create_with_properties(data)

            # Emit event if event bus is available
            if self.event_bus:
                self.event_bus.publish({
                    "type": "storage_location_type.created",
                    "storage_location_type_id": type_obj.id,
                    "name": type_obj.name,
                    "created_by": created_by,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("storage_location_types:*")

            return type_obj

    def update_storage_location_type(
            self,
            id: int,
            data: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> Optional[StorageLocationType]:
        """
        Update an existing storage location type.

        Args:
            id: ID of the storage location type to update
            data: Updated type data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated storage location type if found, None otherwise

        Raises:
            ValidationException: If type data is invalid
        """
        with self.transaction():
            # Get existing type
            type_obj = self.repository.get_by_id_with_properties(id)
            if not type_obj:
                return None

            # Cannot change name if it would create a duplicate
            if "name" in data and data["name"] != type_obj.name:
                existing_types = self.repository.list(name=data["name"])
                if existing_types:
                    raise ValidationException(f"Storage location type with name '{data['name']}' already exists")

            # Validate properties if provided
            if "properties" in data and self.property_service:
                properties = data["properties"]
                validated_properties = []

                for property_assignment in properties:
                    property_id = property_assignment.get("property_id")

                    # Verify property exists
                    if not self.property_service.get_property_definition(property_id):
                        raise ValidationException(f"Property with ID {property_id} not found")

                    validated_properties.append(property_assignment)

                data["properties"] = validated_properties

            # Update type
            updated_type = self.repository.update_with_properties(id, data)

            # Emit event if event bus is available
            if self.event_bus:
                self.event_bus.publish({
                    "type": "storage_location_type.updated",
                    "storage_location_type_id": id,
                    "updated_by": user_id,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"storage_location_types:{id}")
                self.cache_service.invalidate_pattern("storage_location_types:*")

            return updated_type

    def delete_storage_location_type(self, id: int) -> bool:
        """
        Delete a storage location type.

        Args:
            id: ID of the storage location type to delete

        Returns:
            True if deleted, False otherwise

        Raises:
            ValidationException: If type has associated storage locations
        """
        with self.transaction():
            # Get type
            type_obj = self.repository.get_by_id(id)
            if not type_obj:
                return False

            # Check if type has any storage locations
            if hasattr(type_obj, 'storage_locations') and type_obj.storage_locations:
                raise ValidationException(
                    f"Cannot delete storage location type '{type_obj.name}' as it has {len(type_obj.storage_locations)} associated storage locations"
                )

            # Delete type
            result = self.repository.delete(id)

            # Emit event if successful
            if result and self.event_bus:
                self.event_bus.publish({
                    "type": "storage_location_type.deleted",
                    "storage_location_type_id": id,
                    "name": type_obj.name,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"storage_location_types:{id}")
                self.cache_service.invalidate_pattern("storage_location_types:*")

            return result

    def apply_settings_to_types(
            self,
            types: List[StorageLocationType],
            user_id: int
    ) -> List[StorageLocationType]:
        """
        Apply user settings to storage location types.

        Args:
            types: List of storage location types to apply settings to
            user_id: ID of the user whose settings to apply

        Returns:
            List of storage location types with settings applied
        """
        if not self.settings_service or not types:
            return types

        try:
            # Get UI settings for storage location types
            storage_type_ui = self.settings_service.get_setting(
                key="storage_type_ui",
                scope_type="user",
                scope_id=str(user_id)
            )

            # If no settings found, return types as is
            if not storage_type_ui:
                return types

            # Card view settings
            card_view = storage_type_ui.get("card_view", {})
            show_card_thumbnail = card_view.get("display_thumbnail", True)
            max_card_properties = card_view.get("max_properties", 4)

            # List view settings
            list_view = storage_type_ui.get("list_view", {})
            list_columns = list_view.get("default_columns", [
                "name", "icon", "storage_locations_count", "visibility_level"
            ])
            show_list_thumbnail = list_view.get("show_thumbnail", True)

            # Apply settings to each type
            for type_obj in types:
                # Create UI settings object if not exists
                if not hasattr(type_obj, "ui_settings"):
                    type_obj.ui_settings = {}

                # Set card view settings
                type_obj.ui_settings["card_view"] = {
                    "max_properties": max_card_properties,
                    "show_thumbnail": show_card_thumbnail,
                    "properties": self._get_card_properties(type_obj, max_card_properties)
                }

                # Set list view settings
                type_obj.ui_settings["list_view"] = {
                    "columns": list_columns,
                    "show_thumbnail": show_list_thumbnail
                }

                # Add theme information
                type_obj.ui_settings["theme"] = {
                    "color_scheme": type_obj.color_scheme or "default",
                    "icon": type_obj.icon or "storage-type"
                }

        except Exception as e:
            # Log error but don't fail if settings can't be applied
            print(f"Error applying settings to storage location types: {str(e)}")

        return types

    def _get_card_properties(self, type_obj: StorageLocationType, max_props: int) -> List[Dict]:
        """Get properties for card view based on settings."""
        card_props = []

        # Add basic type information
        if hasattr(type_obj, 'storage_locations') and type_obj.storage_locations:
            card_props.append({
                "name": "Locations",
                "value": str(len(type_obj.storage_locations)),
                "type": "count"
            })

        if type_obj.visibility_level:
            card_props.append({
                "name": "Visibility",
                "value": type_obj.visibility_level.title(),
                "type": "visibility"
            })

        # Add type-specific properties if available
        if hasattr(type_obj, 'properties') and type_obj.properties:
            properties_count = len(type_obj.properties)
            card_props.append({
                "name": "Custom Properties",
                "value": str(properties_count),
                "type": "properties"
            })

        return card_props[:max_props]

    def get_type_by_name(self, name: str) -> Optional[StorageLocationType]:
        """
        Get a storage location type by name.

        Args:
            name: Name of the storage location type

        Returns:
            Storage location type if found, None otherwise
        """
        types = self.repository.list(name=name)
        return types[0] if types else None

    def search_types(self, query: str, skip: int = 0, limit: int = 100) -> List[StorageLocationType]:
        """
        Search for storage location types by name.

        Args:
            query: Search query string
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of matching storage location types
        """
        types, _ = self.repository.list_with_properties(
            skip=skip,
            limit=limit,
            search=query
        )
        return types

    def get_system_types(self) -> List[StorageLocationType]:
        """
        Get all system-defined storage location types.

        Returns:
            List of system storage location types
        """
        types, _ = self.repository.list_with_properties(
            skip=0,
            limit=1000,
            is_system=True
        )
        return types

    def create_default_types(self) -> List[StorageLocationType]:
        """
        Create default system storage location types.

        Returns:
            List of created default types
        """
        default_types = [
            {
                "name": "cabinet",
                "icon": "cabinet",
                "color_scheme": "brown",
                "is_system": True,
                "visibility_level": "all",
                "ui_config": {
                    "default_dimensions": {"width": 4, "height": 6, "depth": 2},
                    "supports_cells": True,
                    "supports_shelves": True
                },
                "storage_config": {
                    "default_capacity": 24,
                    "capacity_unit": "items",
                    "supports_locking": True
                },
                "translations": {
                    "en": {
                        "display_name": "Cabinet",
                        "description": "Enclosed storage cabinet with doors"
                    }
                }
            },
            {
                "name": "shelf",
                "icon": "shelf",
                "color_scheme": "gray",
                "is_system": True,
                "visibility_level": "all",
                "ui_config": {
                    "default_dimensions": {"width": 6, "height": 1, "depth": 1},
                    "supports_cells": False,
                    "supports_shelves": False
                },
                "storage_config": {
                    "default_capacity": 12,
                    "capacity_unit": "items",
                    "supports_locking": False
                },
                "translations": {
                    "en": {
                        "display_name": "Shelf",
                        "description": "Open shelf storage"
                    }
                }
            },
            {
                "name": "drawer",
                "icon": "drawer",
                "color_scheme": "blue",
                "is_system": True,
                "visibility_level": "all",
                "ui_config": {
                    "default_dimensions": {"width": 3, "height": 4, "depth": 1},
                    "supports_cells": True,
                    "supports_shelves": False
                },
                "storage_config": {
                    "default_capacity": 12,
                    "capacity_unit": "items",
                    "supports_locking": True
                },
                "translations": {
                    "en": {
                        "display_name": "Drawer",
                        "description": "Pull-out drawer storage"
                    }
                }
            },
            {
                "name": "rack",
                "icon": "rack",
                "color_scheme": "green",
                "is_system": True,
                "visibility_level": "all",
                "ui_config": {
                    "default_dimensions": {"width": 8, "height": 10, "depth": 2},
                    "supports_cells": False,
                    "supports_shelves": True
                },
                "storage_config": {
                    "default_capacity": 40,
                    "capacity_unit": "items",
                    "supports_locking": False
                },
                "translations": {
                    "en": {
                        "display_name": "Rack",
                        "description": "Large rack storage system"
                    }
                }
            },
            {
                "name": "bin",
                "icon": "bin",
                "color_scheme": "orange",
                "is_system": True,
                "visibility_level": "all",
                "ui_config": {
                    "default_dimensions": {"width": 2, "height": 2, "depth": 1},
                    "supports_cells": False,
                    "supports_shelves": False
                },
                "storage_config": {
                    "default_capacity": 4,
                    "capacity_unit": "items",
                    "supports_locking": False
                },
                "translations": {
                    "en": {
                        "display_name": "Bin",
                        "description": "Small storage bin or container"
                    }
                }
            }
        ]

        created_types = []

        for type_data in default_types:
            try:
                # Check if type already exists
                existing = self.get_type_by_name(type_data["name"])
                if not existing:
                    created_type = self.create_storage_location_type(type_data, created_by=None)
                    created_types.append(created_type)
            except Exception as e:
                print(f"Error creating default storage location type '{type_data['name']}': {e}")

        return created_types

    def assign_property(
            self,
            type_id: int,
            property_id: int,
            assignment_config: Dict[str, Any]
    ) -> bool:
        """
        Assign a property to a storage location type.

        Args:
            type_id: ID of the storage location type
            property_id: ID of the property to assign
            assignment_config: Configuration for the property assignment

        Returns:
            True if assigned successfully

        Raises:
            EntityNotFoundException: If type or property not found
            ValidationException: If assignment is invalid
        """
        # Get type
        type_obj = self.repository.get_by_id(type_id)
        if not type_obj:
            raise EntityNotFoundException(f"Storage location type with ID {type_id} not found")

        # Get property
        if self.property_service:
            property_def = self.property_service.get_property_definition(property_id)
            if not property_def:
                raise EntityNotFoundException(f"Property with ID {property_id} not found")

        # Create property assignment
        assignment = StorageLocationTypeProperty(
            storage_location_type_id=type_id,
            property_id=property_id,
            display_order=assignment_config.get("display_order", 0),
            is_required=assignment_config.get("is_required", False),
            is_filterable=assignment_config.get("is_filterable", True),
            is_displayed_in_list=assignment_config.get("is_displayed_in_list", True),
            is_displayed_in_card=assignment_config.get("is_displayed_in_card", True),
            default_value=assignment_config.get("default_value")
        )

        self.session.add(assignment)
        self.session.commit()

        # Invalidate cache if needed
        if self.cache_service:
            self.cache_service.invalidate(f"storage_location_types:{type_id}")
            self.cache_service.invalidate_pattern("storage_location_types:*")

        return True

    def remove_property(self, type_id: int, property_id: int) -> bool:
        """
        Remove a property from a storage location type.

        Args:
            type_id: ID of the storage location type
            property_id: ID of the property to remove

        Returns:
            True if removed successfully
        """
        assignment = self.session.query(StorageLocationTypeProperty).filter(
            StorageLocationTypeProperty.storage_location_type_id == type_id,
            StorageLocationTypeProperty.property_id == property_id
        ).first()

        if assignment:
            self.session.delete(assignment)
            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"storage_location_types:{type_id}")
                self.cache_service.invalidate_pattern("storage_location_types:*")

            return True

        return False