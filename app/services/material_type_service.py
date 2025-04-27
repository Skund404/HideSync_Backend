# app/services/material_type_service.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.db.models.dynamic_material import MaterialType, PropertyDefinition
from app.repositories.material_type_repository import MaterialTypeRepository
from app.repositories.property_definition_repository import PropertyDefinitionRepository


class MaterialTypeService(BaseService[MaterialType]):
    """
    Service for managing material types in the Dynamic Material Management System.

    Provides functionality for:
    - Managing material type definitions
    - Assigning properties to material types
    - Importing/exporting material type configurations
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            property_repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
    ):
        """
        Initialize MaterialTypeService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            property_repository: Optional property repository
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.repository = repository or MaterialTypeRepository(session)
        self.property_repository = property_repository or PropertyDefinitionRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def get_material_types(
            self,
            skip: int = 0,
            limit: int = 100,
            include_system: bool = True,
            user_tier: str = None
    ) -> List[MaterialType]:
        """
        Get all material types with filtering options.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            include_system: Whether to include system material types
            user_tier: Optional user tier for filtering visible types

        Returns:
            List of material types
        """
        filters = {}

        if not include_system:
            filters["is_system"] = False

        # Filter by user tier if provided
        if user_tier:
            # Add filter for visibility level (matches tier or 'all')
            # This will need to be handled in the repository since
            # it requires an OR condition
            pass

        return self.repository.list_with_properties(skip=skip, limit=limit, **filters)

    def get_material_type(self, id: int) -> Optional[MaterialType]:
        """
        Get a material type by ID.

        Args:
            id: ID of the material type

        Returns:
            Material type if found, None otherwise
        """
        return self.repository.get_by_id_with_properties(id)

    def get_material_type_by_name(self, name: str) -> Optional[MaterialType]:
        """
        Get a material type by name.

        Args:
            name: Name of the material type

        Returns:
            Material type if found, None otherwise
        """
        # Filter by name (case-insensitive)
        material_types = self.repository.list(name=name)
        return material_types[0] if material_types else None

    def create_material_type(self, data: Dict[str, Any], created_by: Optional[int] = None) -> MaterialType:
        """
        Create a new material type.

        Args:
            data: Material type data
            created_by: Optional ID of user creating the type

        Returns:
            Created material type
        """
        # Add created_by if provided
        if created_by:
            data["created_by"] = created_by

        with self.transaction():
            # Create material type with properties
            material_type = self.repository.create_with_properties(data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("material_types:*")

            return material_type

    def update_material_type(self, id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Optional[
        MaterialType]:
        """
        Update an existing material type.

        Args:
            id: ID of the material type to update
            data: Updated material type data
            user_id: Optional ID of the user performing the update

        Returns:
            Updated material type if found, None otherwise
        """
        with self.transaction():
            # Get existing material type
            material_type = self.repository.get_by_id(id)
            if not material_type:
                return None

            # Check if this is a system material type and limit modifications
            if material_type.is_system:
                # For system types, only allow certain fields to be updated
                safe_data = {}
                safe_fields = ["icon", "color_scheme", "ui_config", "translations"]
                for field in safe_fields:
                    if field in data:
                        safe_data[field] = data[field]

                # Replace data with safe subset
                data = safe_data

            # Update material type
            updated_type = self.repository.update_with_properties(id, data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"material_types:{id}")
                self.cache_service.invalidate_pattern("material_types:*")

            return updated_type

    def delete_material_type(self, id: int) -> bool:
        """
        Delete a material type.

        Args:
            id: ID of the material type to delete

        Returns:
            True if deleted, False otherwise
        """
        with self.transaction():
            # Get material type
            material_type = self.repository.get_by_id(id)
            if not material_type:
                return False

            # Prevent deletion of system material types
            if material_type.is_system:
                return False

            # Check if type has materials
            if material_type.materials and len(material_type.materials) > 0:
                return False

            # Delete material type
            result = self.repository.delete(id)

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"material_types:{id}")
                self.cache_service.invalidate_pattern("material_types:*")

            return result

    def export_material_types(self, material_type_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Export material types in a portable format.

        Args:
            material_type_ids: Optional list of specific type IDs to export

        Returns:
            List of material types in export format
        """
        result = []

        # Get material types to export
        if material_type_ids:
            material_types = [
                self.repository.get_by_id_with_properties(type_id)
                for type_id in material_type_ids
                if self.repository.get_by_id_with_properties(type_id)
            ]
        else:
            # Get all non-system types
            material_types = self.repository.list_with_properties(is_system=False)

        # Convert to export format
        for material_type in material_types:
            result.append(self.repository.convert_to_export_format(material_type))

        return result

    def import_material_types(self, data: List[Dict[str, Any]], created_by: Optional[int] = None) -> List[MaterialType]:
        """
        Import material types from export format.

        Args:
            data: List of material types in export format
            created_by: Optional ID of the user importing

        Returns:
            List of imported material types
        """
        imported_types = []

        with self.transaction():
            for item in data:
                # Convert from export format to create format
                create_data = self.repository.convert_from_export_format(item)

                # Add created_by if provided
                if created_by:
                    create_data["created_by"] = created_by

                # Check if a material type with the same name already exists
                existing = self.get_material_type_by_name(create_data.get("name"))
                if existing:
                    # Update existing material type
                    updated = self.repository.update_with_properties(existing.id, create_data)
                    if updated:
                        imported_types.append(updated)
                else:
                    # Create new material type
                    imported = self.repository.create_with_properties(create_data)
                    imported_types.append(imported)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("material_types:*")

        return imported_types