# File: app/services/storage_property_definition_service.py
"""
Storage Property Definition Service for the Dynamic Material Management System.

This service manages storage property definitions, following the same patterns
as PropertyDefinitionService. Provides functionality for:
- Creating and updating property definitions for storage locations
- Validation and type management
- Enum option handling
- Translation management
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import json

from app.services.base_service import BaseService
from app.db.models.storage import (
    StoragePropertyDefinition,
    StoragePropertyDefinitionTranslation,
    StoragePropertyEnumOption,
    StoragePropertyEnumMapping,
)
from app.db.models.dynamic_enum import EnumType
from app.repositories.storage_repository import StoragePropertyDefinitionRepository
from app.core.exceptions import EntityNotFoundException, ValidationException, DuplicateEntityException
from app.services.settings_service import SettingsService


class StoragePropertyDefinitionService(BaseService[StoragePropertyDefinition]):
    """
    Service for managing storage property definitions in the Dynamic Material Management System.

    Follows the same patterns as PropertyDefinitionService with:
    - Dynamic property types
    - Enum handling
    - Translation support
    - Validation rules
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            enum_service=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            settings_service=None,
    ):
        """
        Initialize StoragePropertyDefinitionService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            enum_service: Optional enum service for dynamic enum handling
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            settings_service: Optional settings service for user settings
        """
        self.session = session
        self.repository = repository or StoragePropertyDefinitionRepository(session)
        self.enum_service = enum_service
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.settings_service = settings_service

    def get_property_definitions(
            self,
            skip: int = 0,
            limit: int = 100,
            data_type: Optional[str] = None,
            group_name: Optional[str] = None,
            search: Optional[str] = None,
            **filters
    ) -> Tuple[List[StoragePropertyDefinition], int]:
        """
        Get storage property definitions with filtering and pagination.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            data_type: Optional filter by data type
            group_name: Optional filter by group name
            search: Optional search string for names
            **filters: Additional filters

        Returns:
            Tuple of (list of property definitions, total count)
        """
        return self.repository.list_with_translations(
            skip=skip,
            limit=limit,
            data_type=data_type,
            group_name=group_name,
            search=search,
            **filters
        )

    def get_property_definition(self, property_id: int) -> Optional[StoragePropertyDefinition]:
        """
        Get a storage property definition by ID.

        Args:
            property_id: ID of the property definition

        Returns:
            Property definition if found, None otherwise
        """
        return self.repository.get_by_id_with_translations(property_id)

    def create_property_definition(
            self,
            data: Dict[str, Any],
            created_by: Optional[int] = None
    ) -> StoragePropertyDefinition:
        """
        Create a new storage property definition.

        Args:
            data: Property definition data
            created_by: Optional ID of user creating the property

        Returns:
            Created property definition

        Raises:
            ValidationException: If property data is invalid
            DuplicateEntityException: If property name already exists
        """
        # Add created_by if provided
        if created_by:
            data["created_by"] = created_by

        # Validate required fields
        required_fields = ["name", "data_type"]
        for field in required_fields:
            if not data.get(field):
                raise ValidationException(f"Field '{field}' is required")

        # Check for duplicate name
        name = data.get("name", "")
        existing_properties = self.repository.list(name=name)
        if existing_properties:
            raise DuplicateEntityException(f"Storage property definition with name '{name}' already exists")

        # Validate data type
        valid_data_types = ['string', 'number', 'boolean', 'enum', 'date', 'reference', 'file']
        data_type = data.get("data_type")
        if data_type not in valid_data_types:
            raise ValidationException(f"data_type must be one of: {', '.join(valid_data_types)}")

        # Handle enum configuration
        if data_type == 'enum':
            enum_type_id = data.get("enum_type_id")
            enum_options = data.get("enum_options")

            if not enum_type_id and not enum_options:
                raise ValidationException("Either enum_type_id or enum_options must be provided for enum properties")

            # Validate enum type if provided
            if enum_type_id and self.enum_service:
                enum_type = self.enum_service.get_enum_type(enum_type_id)
                if not enum_type:
                    raise ValidationException(f"Enum type with ID {enum_type_id} not found")

        with self.transaction():
            # Create property definition
            property_def = self.repository.create_with_translations(data)

            # Emit event if event bus is available
            if self.event_bus:
                self.event_bus.publish({
                    "type": "storage_property_definition.created",
                    "property_id": property_def.id,
                    "name": property_def.name,
                    "data_type": property_def.data_type,
                    "created_by": created_by,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("storage_property_definitions:*")

            return property_def

    def update_property_definition(
            self,
            id: int,
            data: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> Optional[StoragePropertyDefinition]:
        """
        Update an existing storage property definition.

        Args:
            id: ID of the property definition to update
            data: Updated property data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated property definition if found, None otherwise

        Raises:
            ValidationException: If property data is invalid
        """
        with self.transaction():
            # Get existing property
            property_def = self.repository.get_by_id_with_translations(id)
            if not property_def:
                return None

            # Cannot change name or data type if it would affect existing usage
            if "name" in data and data["name"] != property_def.name:
                existing_properties = self.repository.list(name=data["name"])
                if existing_properties:
                    raise ValidationException(f"Storage property definition with name '{data['name']}' already exists")

            if "data_type" in data and data["data_type"] != property_def.data_type:
                raise ValidationException("Cannot change data type of existing property definition")

            # Handle enum configuration updates
            data_type = property_def.data_type
            if data_type == 'enum':
                enum_type_id = data.get("enum_type_id")
                if enum_type_id and self.enum_service:
                    enum_type = self.enum_service.get_enum_type(enum_type_id)
                    if not enum_type:
                        raise ValidationException(f"Enum type with ID {enum_type_id} not found")

            # Update property
            updated_property = self.repository.update_with_translations(id, data)

            # Emit event if event bus is available
            if self.event_bus:
                self.event_bus.publish({
                    "type": "storage_property_definition.updated",
                    "property_id": id,
                    "updated_by": user_id,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"storage_property_definitions:{id}")
                self.cache_service.invalidate_pattern("storage_property_definitions:*")

            return updated_property

    def delete_property_definition(self, id: int) -> bool:
        """
        Delete a storage property definition.

        Args:
            id: ID of the property definition to delete

        Returns:
            True if deleted, False otherwise

        Raises:
            ValidationException: If property is in use
        """
        with self.transaction():
            # Get property
            property_def = self.repository.get_by_id(id)
            if not property_def:
                return False

            # Check if property is used by any storage location types
            from app.db.models.storage import StorageLocationTypeProperty
            usage_count = self.session.query(StorageLocationTypeProperty).filter(
                StorageLocationTypeProperty.property_id == id
            ).count()

            if usage_count > 0:
                raise ValidationException(
                    f"Cannot delete property '{property_def.name}' as it is used by {usage_count} storage location types"
                )

            # Delete property
            result = self.repository.delete(id)

            # Emit event if successful
            if result and self.event_bus:
                self.event_bus.publish({
                    "type": "storage_property_definition.deleted",
                    "property_id": id,
                    "name": property_def.name,
                    "timestamp": datetime.now().isoformat()
                })

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"storage_property_definitions:{id}")
                self.cache_service.invalidate_pattern("storage_property_definitions:*")

            return result

    def validate_property_value(self, property_id: int, value: Any) -> bool:
        """
        Validate a property value against its definition.

        Args:
            property_id: ID of the property definition
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        property_def = self.get_property_definition(property_id)
        if not property_def:
            return False

        # Basic type validation
        data_type = property_def.data_type

        if data_type == 'string':
            if not isinstance(value, str):
                return False
        elif data_type == 'number':
            if not isinstance(value, (int, float)):
                return False
        elif data_type == 'boolean':
            if not isinstance(value, bool):
                return False
        elif data_type == 'date':
            # Accept ISO date strings
            if not isinstance(value, str):
                return False
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return False
        elif data_type == 'enum':
            # Validate against enum options
            if hasattr(property_def, 'enum_options') and property_def.enum_options:
                valid_values = [option.value for option in property_def.enum_options]
                if value not in valid_values:
                    return False
        elif data_type == 'file':
            # Accept file IDs or URLs
            if not isinstance(value, str):
                return False
        elif data_type == 'reference':
            # Accept integer IDs
            if not isinstance(value, int):
                return False

        # Apply validation rules if present
        validation_rules = property_def.validation_rules
        if validation_rules:
            if data_type == 'string':
                min_length = validation_rules.get('min_length')
                max_length = validation_rules.get('max_length')
                if min_length and len(value) < min_length:
                    return False
                if max_length and len(value) > max_length:
                    return False
            elif data_type == 'number':
                min_value = validation_rules.get('min_value')
                max_value = validation_rules.get('max_value')
                if min_value is not None and value < min_value:
                    return False
                if max_value is not None and value > max_value:
                    return False

        return True

    def get_property_by_name(self, name: str) -> Optional[StoragePropertyDefinition]:
        """
        Get a storage property definition by name.

        Args:
            name: Name of the property definition

        Returns:
            Property definition if found, None otherwise
        """
        properties = self.repository.list(name=name)
        return properties[0] if properties else None

    def search_properties(self, query: str, skip: int = 0, limit: int = 100) -> List[StoragePropertyDefinition]:
        """
        Search for storage property definitions by name.

        Args:
            query: Search query string
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of matching property definitions
        """
        properties, _ = self.repository.list_with_translations(
            skip=skip,
            limit=limit,
            search=query
        )
        return properties

    def get_properties_by_group(self, group_name: str) -> List[StoragePropertyDefinition]:
        """
        Get all storage property definitions in a specific group.

        Args:
            group_name: Name of the property group

        Returns:
            List of property definitions in the group
        """
        properties, _ = self.repository.list_with_translations(
            skip=0,
            limit=1000,
            group_name=group_name
        )
        return properties

    def get_properties_by_type(self, data_type: str) -> List[StoragePropertyDefinition]:
        """
        Get all storage property definitions of a specific data type.

        Args:
            data_type: Data type to filter by

        Returns:
            List of property definitions of the specified type
        """
        properties, _ = self.repository.list_with_translations(
            skip=0,
            limit=1000,
            data_type=data_type
        )
        return properties

    def create_default_properties(self) -> List[StoragePropertyDefinition]:
        """
        Create default system storage property definitions.

        Returns:
            List of created default properties
        """
        default_properties = [
            {
                "name": "material",
                "data_type": "string",
                "group_name": "Physical Properties",
                "is_system": True,
                "validation_rules": {"max_length": 100},
                "translations": {
                    "en": {
                        "display_name": "Material",
                        "description": "Primary material the storage is made from"
                    }
                }
            },
            {
                "name": "finish",
                "data_type": "string",
                "group_name": "Physical Properties",
                "is_system": True,
                "validation_rules": {"max_length": 50},
                "translations": {
                    "en": {
                        "display_name": "Finish",
                        "description": "Surface finish or coating"
                    }
                }
            },
            {
                "name": "locking",
                "data_type": "boolean",
                "group_name": "Security",
                "is_system": True,
                "translations": {
                    "en": {
                        "display_name": "Locking",
                        "description": "Whether the storage location has a lock"
                    }
                }
            },
            {
                "name": "climate_controlled",
                "data_type": "boolean",
                "group_name": "Environment",
                "is_system": True,
                "translations": {
                    "en": {
                        "display_name": "Climate Controlled",
                        "description": "Whether the storage has climate control"
                    }
                }
            },
            {
                "name": "weight_capacity_kg",
                "data_type": "number",
                "group_name": "Capacity",
                "unit": "kg",
                "is_system": True,
                "validation_rules": {"min_value": 0},
                "translations": {
                    "en": {
                        "display_name": "Weight Capacity",
                        "description": "Maximum weight capacity in kilograms"
                    }
                }
            },
            {
                "name": "access_level",
                "data_type": "enum",
                "group_name": "Security",
                "is_system": True,
                "enum_options": [
                    {"value": "public", "display_value": "Public Access"},
                    {"value": "restricted", "display_value": "Restricted Access"},
                    {"value": "admin", "display_value": "Admin Only"}
                ],
                "translations": {
                    "en": {
                        "display_name": "Access Level",
                        "description": "Required access level for this storage location"
                    }
                }
            },
            {
                "name": "installation_date",
                "data_type": "date",
                "group_name": "Maintenance",
                "is_system": True,
                "translations": {
                    "en": {
                        "display_name": "Installation Date",
                        "description": "Date when the storage was installed"
                    }
                }
            },
            {
                "name": "manufacturer",
                "data_type": "string",
                "group_name": "Details",
                "is_system": True,
                "validation_rules": {"max_length": 100},
                "translations": {
                    "en": {
                        "display_name": "Manufacturer",
                        "description": "Manufacturer of the storage unit"
                    }
                }
            },
            {
                "name": "model_number",
                "data_type": "string",
                "group_name": "Details",
                "is_system": True,
                "validation_rules": {"max_length": 50},
                "translations": {
                    "en": {
                        "display_name": "Model Number",
                        "description": "Model or part number"
                    }
                }
            },
            {
                "name": "fire_rated",
                "data_type": "boolean",
                "group_name": "Safety",
                "is_system": True,
                "translations": {
                    "en": {
                        "display_name": "Fire Rated",
                        "description": "Whether the storage is fire-rated"
                    }
                }
            }
        ]

        created_properties = []

        for property_data in default_properties:
            try:
                # Check if property already exists
                existing = self.get_property_by_name(property_data["name"])
                if not existing:
                    created_property = self.create_property_definition(property_data, created_by=None)
                    created_properties.append(created_property)
            except Exception as e:
                print(f"Error creating default storage property '{property_data['name']}': {e}")

        return created_properties

    def get_enum_options(self, property_id: int) -> List[Dict[str, Any]]:
        """
        Get enum options for a property.

        Args:
            property_id: ID of the property definition

        Returns:
            List of enum options
        """
        property_def = self.get_property_definition(property_id)
        if not property_def or property_def.data_type != 'enum':
            return []

        options = []

        # Get custom enum options
        if hasattr(property_def, 'enum_options') and property_def.enum_options:
            for option in property_def.enum_options:
                options.append({
                    "value": option.value,
                    "display_value": option.display_value,
                    "color": option.color,
                    "display_order": option.display_order
                })

        # Get enum type options if using dynamic enum
        elif property_def.enum_type_id and self.enum_service:
            enum_values = self.enum_service.get_enum_values(property_def.enum_type_id)
            for enum_value in enum_values:
                options.append({
                    "value": enum_value.value,
                    "display_value": enum_value.display_value,
                    "color": getattr(enum_value, 'color', None),
                    "display_order": getattr(enum_value, 'display_order', 0)
                })

        return sorted(options, key=lambda x: x.get('display_order', 0))