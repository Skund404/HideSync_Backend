# app/services/property_definition_service.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.db.models.dynamic_material import PropertyDefinition, PropertyEnumOption
from app.repositories.property_definition_repository import PropertyDefinitionRepository


class PropertyDefinitionService(BaseService[PropertyDefinition]):
    """
    Service for managing property definitions in the Dynamic Material Management System.

    Provides functionality for:
    - Managing property definitions
    - Creating and updating property enum options
    - Validating property data
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            enum_service=None,
    ):
        """
        Initialize PropertyDefinitionService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            enum_service: Optional enum service for enum integration
        """
        self.session = session
        self.repository = repository or PropertyDefinitionRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.enum_service = enum_service

    def get_property_definitions(
            self,
            skip: int = 0,
            limit: int = 100,
            include_system: bool = True,
            data_type: Optional[str] = None,
    ) -> List[PropertyDefinition]:
        """
        Get all property definitions with filtering options.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            include_system: Whether to include system properties
            data_type: Optional filter by data type

        Returns:
            List of property definitions
        """
        filters = {}

        if not include_system:
            filters["is_system"] = False

        if data_type:
            filters["data_type"] = data_type

        return self.repository.list_with_translations(skip=skip, limit=limit, **filters)

    def get_property_definition(self, id: int) -> Optional[PropertyDefinition]:
        """
        Get a property definition by ID.

        Args:
            id: ID of the property definition

        Returns:
            Property definition if found, None otherwise
        """
        return self.repository.get_by_id_with_translations(id)

    def get_property_definition_by_name(self, name: str) -> Optional[PropertyDefinition]:
        """
        Get a property definition by name.

        Args:
            name: Name of the property definition

        Returns:
            Property definition if found, None otherwise
        """
        # Filter by name (case-insensitive)
        properties = self.repository.list(name=name)
        return properties[0] if properties else None

    def create_property_definition(self, data: Dict[str, Any], created_by: Optional[int] = None) -> PropertyDefinition:
        """
        Create a new property definition.

        Args:
            data: Property definition data
            created_by: Optional ID of user creating the property

        Returns:
            Created property definition
        """
        # Add created_by if provided
        if created_by:
            data["created_by"] = created_by

        # Validate data_type
        data_type = data.get("data_type")
        if not data_type:
            raise ValueError("data_type is required")

        # Check enum configuration
        if data_type == "enum":
            if not data.get("enum_type_id") and not data.get("enum_options"):
                raise ValueError("enum_type_id or enum_options must be provided for enum properties")

        with self.transaction():
            # Create property definition
            property_def = self.repository.create_with_translations(data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("property_definitions:*")

            return property_def

    def update_property_definition(self, id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Optional[
        PropertyDefinition]:
        """
        Update an existing property definition.

        Args:
            id: ID of the property definition to update
            data: Updated property definition data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated property definition if found, None otherwise
        """
        with self.transaction():
            # Get existing property definition
            property_def = self.repository.get_by_id(id)
            if not property_def:
                return None

            # Check if this is a system property and limit modifications
            if property_def.is_system:
                # For system properties, only allow certain fields to be updated
                safe_data = {}
                safe_fields = ["validation_rules", "translations"]
                for field in safe_fields:
                    if field in data:
                        safe_data[field] = data[field]

                # Replace data with safe subset
                data = safe_data

            # Check enum configuration
            if property_def.data_type == "enum" and "enum_options" in data and property_def.enum_type_id:
                # Can't add custom enum options if using enum type
                data.pop("enum_options")

            # Update property definition
            updated_property = self.repository.update_with_translations(id, data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"property_definitions:{id}")
                self.cache_service.invalidate_pattern("property_definitions:*")

            return updated_property

    def delete_property_definition(self, id: int) -> bool:
        """
        Delete a property definition.

        Args:
            id: ID of the property definition to delete

        Returns:
            True if deleted, False otherwise
        """
        with self.transaction():
            # Get property definition
            property_def = self.repository.get_by_id(id)
            if not property_def:
                return False

            # Prevent deletion of system properties
            if property_def.is_system:
                return False

            # Check if property is used by any material types
            if property_def.material_types and len(property_def.material_types) > 0:
                return False

            # Delete property definition
            result = self.repository.delete(id)

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"property_definitions:{id}")
                self.cache_service.invalidate_pattern("property_definitions:*")

            return result

    def add_enum_option(self, property_id: int, value: str, display_value: str, color: Optional[str] = None,
                        display_order: Optional[int] = None) -> Optional[PropertyEnumOption]:
        """
        Add an enum option to a property.

        Args:
            property_id: ID of the property
            value: Unique value code for the option
            display_value: Display text for the option
            color: Optional color for the option
            display_order: Optional display order

        Returns:
            Created enum option if successful, None otherwise
        """
        with self.transaction():
            # Check if property exists and is an enum type
            property_def = self.repository.get_by_id(property_id)
            if not property_def or property_def.data_type != "enum":
                return None

            # Cannot add custom options if using enum type
            if property_def.enum_type_id:
                return None

            # Add enum option
            enum_option = self.repository.add_enum_option(
                property_id=property_id,
                value=value,
                display_value=display_value,
                color=color,
                display_order=display_order
            )

            # Invalidate cache if needed
            if self.cache_service and enum_option:
                self.cache_service.invalidate(f"property_definitions:{property_id}")
                self.cache_service.invalidate_pattern("property_definitions:*")

            return enum_option

    def delete_enum_option(self, property_id: int, option_id: int) -> bool:
        """
        Delete an enum option from a property.

        Args:
            property_id: ID of the property
            option_id: ID of the enum option

        Returns:
            True if deleted, False otherwise
        """
        with self.transaction():
            # Check if property exists and is an enum type
            property_def = self.repository.get_by_id(property_id)
            if not property_def or property_def.data_type != "enum":
                return False

            # Cannot delete options if using enum type
            if property_def.enum_type_id:
                return False

            # Get the option
            option = self.session.query(PropertyEnumOption).filter(
                PropertyEnumOption.id == option_id,
                PropertyEnumOption.property_id == property_id
            ).first()

            if not option:
                return False

            # Delete the option
            self.session.delete(option)
            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"property_definitions:{property_id}")
                self.cache_service.invalidate_pattern("property_definitions:*")

            return True

    def get_enum_values(self, property_id: int, locale: str = "en") -> List[Dict[str, Any]]:
        """
        Get enum values for a property.

        Args:
            property_id: ID of the property
            locale: Locale for translation

        Returns:
            List of enum values
        """
        property_def = self.repository.get_by_id_with_translations(property_id)
        if not property_def or property_def.data_type != "enum":
            return []

        # Return values based on source (enum type or custom options)
        if property_def.enum_type_id and self.enum_service:
            # Use dynamic enum system
            enum_type = property_def.enum_type
            if not enum_type:
                return []

            return self.enum_service.get_enum_values(enum_type.system_name, locale)
        else:
            # Use custom property enum options
            return [
                {
                    "id": option.id,
                    "value": option.value,
                    "display_value": option.display_value,
                    "color": option.color,
                    "display_order": option.display_order
                }
                for option in property_def.enum_options
            ]

    def validate_property_value(self, property_id: int, value: Any) -> bool:
        """
        Validate a value against a property's constraints.

        Args:
            property_id: ID of the property
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        property_def = self.repository.get_by_id(property_id)
        if not property_def:
            return False

        # Skip validation if value is None and property is not required
        if value is None:
            return not property_def.is_required

        # Validate based on data type
        data_type = property_def.data_type

        if data_type == "string":
            if not isinstance(value, str):
                return False

            # Check validation rules
            rules = property_def.validation_rules or {}
            if "min_length" in rules and len(value) < rules["min_length"]:
                return False
            if "max_length" in rules and len(value) > rules["max_length"]:
                return False
            if "pattern" in rules and not re.match(rules["pattern"], value):
                return False

            return True

        elif data_type == "number":
            if not isinstance(value, (int, float)):
                return False

            # Check validation rules
            rules = property_def.validation_rules or {}
            if "min" in rules and value < rules["min"]:
                return False
            if "max" in rules and value > rules["max"]:
                return False

            return True

        elif data_type == "boolean":
            return isinstance(value, bool)

        elif data_type == "date":
            # Accept ISO date strings
            if isinstance(value, str):
                try:
                    # Try to parse as ISO date
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return True
                except ValueError:
                    return False

            # Accept date objects
            return isinstance(value, (datetime.date, datetime.datetime))

        elif data_type == "enum":
            # For enum, validate that the value exists
            if property_def.enum_type_id and self.enum_service:
                # Value should be a valid enum value ID or code
                enum_values = self.enum_service.get_enum_values(property_def.enum_type.system_name)
                return any(str(v["id"]) == str(value) or v["value"] == value for v in enum_values)
            else:
                # Check against custom enum options
                return self.session.query(PropertyEnumOption).filter(
                    PropertyEnumOption.property_id == property_id,
                    PropertyEnumOption.id == value
                ).count() > 0

        elif data_type == "file":
            # For file, just check that it's a string (ID/URL)
            return isinstance(value, str)

        elif data_type == "reference":
            # For reference, check that it's a valid ID
            return isinstance(value, int) and value > 0

        return False