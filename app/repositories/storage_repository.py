# File: app/repositories/storage_repository.py
"""
Storage Repository Layer for the Dynamic Material Management System.

This module provides data access for storage entities following the same patterns
as the dynamic material repository. Updated to support:
- Dynamic storage location types via enum system
- Custom properties for storage locations
- Proper relationship queries with DynamicMaterial
- Settings-aware data retrieval
- Enhanced filtering and pagination
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from datetime import datetime

from app.db.models.storage import (
    StorageLocation,
    StorageLocationType,
    StorageLocationTypeProperty,
    StoragePropertyDefinition,
    StorageLocationPropertyValue,
    StorageLocationTranslation,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.db.models.dynamic_material import DynamicMaterial, MaterialType
from app.repositories.base_repository import BaseRepository


class StorageLocationRepository(BaseRepository[StorageLocation]):
    """
    Repository for StorageLocation entity operations.

    Updated to follow the dynamic material repository patterns with:
    - Dynamic storage location types support
    - Property-based filtering and querying
    - Proper relationship eager loading
    - Settings-aware data retrieval
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the StorageLocationRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = StorageLocation

    def list_with_properties(
            self,
            skip: int = 0,
            limit: int = 100,
            storage_location_type_id: Optional[int] = None,
            search: Optional[str] = None,
            status: Optional[str] = None,
            section: Optional[str] = None,
            **filters
    ) -> Tuple[List[StorageLocation], int]:
        """
        List storage locations with their properties, following the same pattern
        as DynamicMaterialRepository.list_with_properties().

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            storage_location_type_id: Optional filter by storage location type
            search: Optional search string for names and descriptions
            status: Optional filter by status
            section: Optional filter by section
            **filters: Additional filters

        Returns:
            Tuple of (list of storage locations, total count)
        """
        query = self.session.query(self.model)

        # Apply storage location type filter
        if storage_location_type_id:
            query = query.filter(self.model.storage_location_type_id == storage_location_type_id)

        # Apply search filter
        if search:
            query = query.filter(or_(
                self.model.name.ilike(f"%{search}%"),
                self.model.description.ilike(f"%{search}%"),
                self.model.section.ilike(f"%{search}%"),
                self.model.notes.ilike(f"%{search}%")
            ))

        # Apply status filter
        if status:
            query = query.filter(self.model.status == status)

        # Apply section filter
        if section:
            query = query.filter(self.model.section == section)

        # Apply other filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Get total count before pagination
        total_count = query.count()

        # Apply eager loading of related entities
        query = query.options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values).joinedload(StorageLocationPropertyValue.property),
            joinedload(self.model.translations)
        )

        # Apply pagination and ordering
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result], total_count

    def get_by_id_with_properties(self, id: str) -> Optional[StorageLocation]:
        """
        Get a storage location by ID with eager loading of related properties.
        Follows the same pattern as DynamicMaterialRepository.get_by_id_with_properties().

        Args:
            id: ID of the storage location

        Returns:
            Storage location if found, None otherwise
        """
        item = self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values).joinedload(StorageLocationPropertyValue.property),
            joinedload(self.model.translations),
            joinedload(self.model.cells),
            joinedload(self.model.assignments).joinedload(StorageAssignment.material)
        ).first()

        return self._decrypt_sensitive_fields(item) if item else None

    def create_with_properties(self, data: Dict[str, Any]) -> StorageLocation:
        """
        Create a storage location with its property values.
        Follows the same pattern as DynamicMaterialRepository.create_with_properties().

        Args:
            data: Storage location data including property values

        Returns:
            Created storage location
        """
        # Extract nested data
        property_values_data = data.pop('property_values', [])
        translations_data = data.pop('translations', {})

        # Create the storage location
        location = self.model(**data)
        self.session.add(location)
        self.session.flush()  # Get the ID

        # Create property values
        for prop_value in property_values_data:
            property_id = prop_value.get('property_id')
            if not property_id:
                continue

            # Get property definition to determine data type
            property_def = self.session.query(StoragePropertyDefinition).get(property_id)
            if not property_def:
                continue

            # Create property value with the appropriate value field
            value = prop_value.get('value')
            property_value = StorageLocationPropertyValue(
                storage_location_id=str(location.id),
                property_id=property_id
            )

            # Set the value in the appropriate field based on data type
            if property_def.data_type == 'string':
                property_value.value_string = value
            elif property_def.data_type == 'number':
                property_value.value_number = value
            elif property_def.data_type == 'boolean':
                property_value.value_boolean = value
            elif property_def.data_type == 'date':
                property_value.value_date = value
            elif property_def.data_type == 'enum':
                property_value.value_enum_id = value
            elif property_def.data_type == 'file':
                property_value.value_file_id = value
            elif property_def.data_type == 'reference':
                property_value.value_reference_id = value

            self.session.add(property_value)

        # Add translations if provided
        for locale, translation_data in translations_data.items():
            translation = StorageLocationTranslation(
                storage_location_id=str(location.id),
                locale=locale,
                display_name=translation_data.get('display_name', location.name),
                description=translation_data.get('description')
            )
            self.session.add(translation)

        self.session.commit()
        self.session.refresh(location)

        return location

    def update_with_properties(self, id: str, data: Dict[str, Any]) -> Optional[StorageLocation]:
        """
        Update a storage location with its property values.
        Follows the same pattern as DynamicMaterialRepository.update_with_properties().

        Args:
            id: ID of the storage location to update
            data: Updated storage location data

        Returns:
            Updated storage location if found, None otherwise
        """
        location = self.get_by_id(id)
        if not location:
            return None

        # Extract nested data
        property_values_data = data.pop('property_values', None)
        translations_data = data.pop('translations', None)

        # Update base fields
        for key, value in data.items():
            if hasattr(location, key):
                setattr(location, key, value)

        # Update property values if provided
        if property_values_data is not None:
            # Get existing property values
            existing_values = {
                pv.property_id: pv for pv in location.property_values
            }

            # Process each property value
            for prop_value in property_values_data:
                property_id = prop_value.get('property_id')
                if not property_id:
                    continue

                # Get property definition to determine data type
                property_def = self.session.query(StoragePropertyDefinition).get(property_id)
                if not property_def:
                    continue

                value = prop_value.get('value')
                if property_id in existing_values:
                    # Update existing property value
                    property_value = existing_values[property_id]

                    # Reset all value fields
                    property_value.value_string = None
                    property_value.value_number = None
                    property_value.value_boolean = None
                    property_value.value_date = None
                    property_value.value_enum_id = None
                    property_value.value_file_id = None
                    property_value.value_reference_id = None

                    # Set the appropriate field
                    if property_def.data_type == 'string':
                        property_value.value_string = value
                    elif property_def.data_type == 'number':
                        property_value.value_number = value
                    elif property_def.data_type == 'boolean':
                        property_value.value_boolean = value
                    elif property_def.data_type == 'date':
                        property_value.value_date = value
                    elif property_def.data_type == 'enum':
                        property_value.value_enum_id = value
                    elif property_def.data_type == 'file':
                        property_value.value_file_id = value
                    elif property_def.data_type == 'reference':
                        property_value.value_reference_id = value
                else:
                    # Create new property value
                    property_value = StorageLocationPropertyValue(
                        storage_location_id=str(location.id),
                        property_id=property_id
                    )

                    # Set the appropriate field
                    if property_def.data_type == 'string':
                        property_value.value_string = value
                    elif property_def.data_type == 'number':
                        property_value.value_number = value
                    elif property_def.data_type == 'boolean':
                        property_value.value_boolean = value
                    elif property_def.data_type == 'date':
                        property_value.value_date = value
                    elif property_def.data_type == 'enum':
                        property_value.value_enum_id = value
                    elif property_def.data_type == 'file':
                        property_value.value_file_id = value
                    elif property_def.data_type == 'reference':
                        property_value.value_reference_id = value

                    self.session.add(property_value)

        # Update translations if provided
        if translations_data is not None:
            # Get existing translations
            existing_translations = {
                t.locale: t for t in location.translations
            }

            for locale, translation_data in translations_data.items():
                if locale in existing_translations:
                    # Update existing translation
                    translation = existing_translations[locale]
                    translation.display_name = translation_data.get('display_name', location.name)
                    translation.description = translation_data.get('description')
                else:
                    # Create new translation
                    translation = StorageLocationTranslation(
                        storage_location_id=str(location.id),
                        locale=locale,
                        display_name=translation_data.get('display_name', location.name),
                        description=translation_data.get('description')
                    )
                    self.session.add(translation)

        self.session.commit()
        self.session.refresh(location)

        return location

    def get_by_storage_location_type(
            self,
            storage_location_type_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get storage locations by storage location type.

        Args:
            storage_location_type_id: The storage location type ID to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage locations of the specified type
        """
        query = self.session.query(self.model).filter(
            self.model.storage_location_type_id == storage_location_type_id
        ).options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_by_section(
            self,
            section: str,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get storage locations by section.

        Args:
            section: The section to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage locations in the specified section
        """
        query = self.session.query(self.model).filter(
            self.model.section == section
        ).options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_available_storage(
            self,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get storage locations with available capacity.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage locations with available capacity
        """
        query = self.session.query(self.model).filter(
            self.model.utilized < self.model.capacity
        ).options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_child_locations(
            self,
            parent_id: str,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get child storage locations of a parent location.

        Args:
            parent_id: ID of the parent storage location
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of child storage locations
        """
        query = self.session.query(self.model).filter(
            self.model.parent_storage_id == parent_id
        ).options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_storage_utilization(
            self,
            storage_id: str,
            change: int
    ) -> Optional[StorageLocation]:
        """
        Update a storage location's utilization.

        Args:
            storage_id: ID of the storage location
            change: Amount to add (positive) or subtract (negative) from utilization

        Returns:
            Updated storage location if found, None otherwise
        """
        storage = self.get_by_id(storage_id)
        if not storage:
            return None

        # Update utilization, ensuring it doesn't exceed capacity or go below 0
        new_utilized = max(0, storage.utilized + change)
        if storage.capacity is not None:
            new_utilized = min(storage.capacity, new_utilized)

        storage.utilized = new_utilized

        # Update lastModified timestamp
        storage.last_modified = datetime.now().isoformat()

        self.session.commit()
        self.session.refresh(storage)
        return self._decrypt_sensitive_fields(storage)

    def search_storage_locations(
            self,
            query: str,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageLocation]:
        """
        Search for storage locations by name, description, or section.

        Args:
            query: The search query
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of matching storage locations
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
                self.model.section.ilike(f"%{query}%"),
                self.model.notes.ilike(f"%{query}%")
            )
        ).options(
            joinedload(self.model.storage_location_type),
            joinedload(self.model.property_values)
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_storage_utilization_summary(self) -> Dict[str, Any]:
        """
        Get a summary of storage utilization across all locations.
        Updated to use dynamic storage location types.

        Returns:
            Dict with storage utilization statistics
        """
        total_capacity = self.session.query(func.sum(self.model.capacity)).scalar() or 0
        total_utilized = self.session.query(func.sum(self.model.utilized)).scalar() or 0

        # Get utilization by storage location type
        type_utilization = (
            self.session.query(
                StorageLocationType.name,
                func.sum(self.model.capacity).label("capacity"),
                func.sum(self.model.utilized).label("utilized"),
            )
            .join(self.model.storage_location_type)
            .group_by(StorageLocationType.name)
            .all()
        )

        # Get utilization by section
        section_utilization = (
            self.session.query(
                self.model.section,
                func.sum(self.model.capacity).label("capacity"),
                func.sum(self.model.utilized).label("utilized"),
            )
            .group_by(self.model.section)
            .all()
        )

        # Build the summary dictionary
        summary = {
            "total_capacity": total_capacity,
            "total_utilized": total_utilized,
            "utilization_percentage": (
                (total_utilized / total_capacity * 100) if total_capacity > 0 else 0
            ),
            "by_type": [
                {
                    "type": str(item.name),
                    "capacity": item.capacity,
                    "utilized": item.utilized,
                    "percentage": (
                        (item.utilized / item.capacity * 100)
                        if item.capacity > 0
                        else 0
                    ),
                }
                for item in type_utilization
            ],
            "by_section": [
                {
                    "section": str(item.section or "Unknown"),
                    "capacity": item.capacity,
                    "utilized": item.utilized,
                    "percentage": (
                        (item.utilized / item.capacity * 100)
                        if item.capacity > 0
                        else 0
                    ),
                }
                for item in section_utilization
            ],
        }

        return summary


class StorageLocationTypeRepository(BaseRepository[StorageLocationType]):
    """
    Repository for StorageLocationType entity operations.
    Follows the same patterns as MaterialType repository.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the StorageLocationTypeRepository."""
        super().__init__(session, encryption_service)
        self.model = StorageLocationType

    def list_with_properties(
            self,
            skip: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
            visibility_level: Optional[str] = None,
            **filters
    ) -> Tuple[List[StorageLocationType], int]:
        """
        List storage location types with their properties.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            search: Optional search string for names
            visibility_level: Optional filter by visibility level
            **filters: Additional filters

        Returns:
            Tuple of (list of storage location types, total count)
        """
        query = self.session.query(self.model)

        # Apply search filter
        if search:
            query = query.filter(
                self.model.name.ilike(f"%{search}%")
            )

        # Apply visibility filter
        if visibility_level:
            query = query.filter(self.model.visibility_level == visibility_level)

        # Apply other filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Get total count before pagination
        total_count = query.count()

        # Apply eager loading of related entities
        query = query.options(
            joinedload(self.model.properties).joinedload(StorageLocationTypeProperty.property),
            joinedload(self.model.translations)
        )

        # Apply pagination and ordering
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result], total_count

    def get_by_id_with_properties(self, id: int) -> Optional[StorageLocationType]:
        """
        Get a storage location type by ID with eager loading of related properties.

        Args:
            id: ID of the storage location type

        Returns:
            Storage location type if found, None otherwise
        """
        item = self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.properties).joinedload(StorageLocationTypeProperty.property),
            joinedload(self.model.translations),
            joinedload(self.model.storage_locations)
        ).first()

        return self._decrypt_sensitive_fields(item) if item else None


class StorageCellRepository(BaseRepository[StorageCell]):
    """
    Repository for StorageCell entity operations.
    Updated to support dynamic material relationships.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the StorageCellRepository."""
        super().__init__(session, encryption_service)
        self.model = StorageCell

    def get_cells_by_storage(self, storage_id: str) -> List[StorageCell]:
        """
        Get all cells for a specific storage location with material information.

        Args:
            storage_id: ID of the storage location

        Returns:
            List of cells in the storage location
        """
        query = self.session.query(self.model).filter(
            self.model.storage_id == storage_id
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_occupied_cells(self, storage_id: str) -> List[StorageCell]:
        """
        Get occupied cells in a storage location with material information.

        Args:
            storage_id: ID of the storage location

        Returns:
            List of occupied cells
        """
        query = self.session.query(self.model).filter(
            and_(self.model.storage_id == storage_id, self.model.occupied == True)
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_empty_cells(self, storage_id: str) -> List[StorageCell]:
        """
        Get empty cells in a storage location.

        Args:
            storage_id: ID of the storage location

        Returns:
            List of empty cells
        """
        query = self.session.query(self.model).filter(
            and_(self.model.storage_id == storage_id, self.model.occupied == False)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def assign_cell(
            self,
            storage_id: str,
            position: Dict[str, Any],
            material_id: int
    ) -> Optional[StorageCell]:
        """
        Assign a material to a cell.

        Args:
            storage_id: ID of the storage location
            position: Position of the cell
            material_id: ID of the material to assign

        Returns:
            Updated cell if found, None otherwise
        """
        # Get the cell by position
        cell = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.storage_id == storage_id,
                    self.model._position == str(position)  # JSON comparison
                )
            )
            .first()
        )

        if not cell:
            # Create a new cell if it doesn't exist
            cell = StorageCell(
                storage_id=storage_id,
                position=position,
                material_id=material_id,
                occupied=True,
            )
            self.session.add(cell)
        else:
            # Update the existing cell
            cell.material_id = material_id
            cell.occupied = True

        self.session.commit()
        self.session.refresh(cell)
        return self._decrypt_sensitive_fields(cell)

    def clear_cell(
            self,
            storage_id: str,
            position: Dict[str, Any]
    ) -> Optional[StorageCell]:
        """
        Clear a cell (mark as unoccupied).

        Args:
            storage_id: ID of the storage location
            position: Position of the cell

        Returns:
            Updated cell if found, None otherwise
        """
        cell = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.storage_id == storage_id,
                    self.model._position == str(position)  # JSON comparison
                )
            )
            .first()
        )

        if not cell:
            return None

        cell.material_id = None
        cell.occupied = False

        self.session.commit()
        self.session.refresh(cell)
        return self._decrypt_sensitive_fields(cell)


class StorageAssignmentRepository(BaseRepository[StorageAssignment]):
    """
    Repository for StorageAssignment entity operations.
    Updated to use proper DynamicMaterial relationships.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the StorageAssignmentRepository."""
        super().__init__(session, encryption_service)
        self.model = StorageAssignment

    def get_assignments_by_material(self, material_id: int) -> List[StorageAssignment]:
        """
        Get storage assignments for a specific material with location and material type info.

        Args:
            material_id: ID of the material

        Returns:
            List of storage assignments for the material
        """
        query = self.session.query(self.model).filter(
            self.model.material_id == material_id
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
            joinedload(self.model.location).joinedload(StorageLocation.storage_location_type)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_assignments_by_material_type(
            self,
            material_type_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageAssignment]:
        """
        Get storage assignments for materials of a specific type.

        Args:
            material_type_id: ID of the material type
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage assignments for the material type
        """
        query = self.session.query(self.model).join(
            self.model.material
        ).filter(
            DynamicMaterial.material_type_id == material_type_id
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
            joinedload(self.model.location).joinedload(StorageLocation.storage_location_type)
        ).offset(skip).limit(limit)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_assignments_by_storage(self, storage_id: str) -> List[StorageAssignment]:
        """
        Get all assignments in a specific storage location with material info.

        Args:
            storage_id: ID of the storage location

        Returns:
            List of assignments in the storage location
        """
        query = self.session.query(self.model).filter(
            self.model.storage_id == storage_id
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
            joinedload(self.model.location).joinedload(StorageLocation.storage_location_type)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_assignment(
            self,
            material_id: int,
            storage_id: str,
            position: Dict[str, Any],
            quantity: float,
            assigned_by: str,
    ) -> StorageAssignment:
        """
        Create a new storage assignment.

        Args:
            material_id: ID of the material
            storage_id: ID of the storage location
            position: Position within the storage location
            quantity: Quantity of material assigned
            assigned_by: Name or ID of the user making the assignment

        Returns:
            The created assignment
        """
        assignment_data = {
            "material_id": material_id,
            "storage_id": storage_id,
            "position": position,
            "quantity": quantity,
            "assigned_date": datetime.now().isoformat(),
            "assigned_by": assigned_by,
        }

        return self.create(assignment_data)

    def update_assignment_quantity(
            self,
            assignment_id: str,
            quantity: float
    ) -> Optional[StorageAssignment]:
        """
        Update the quantity of a storage assignment.

        Args:
            assignment_id: ID of the assignment
            quantity: New quantity value

        Returns:
            Updated assignment if found, None otherwise
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None

        assignment.quantity = quantity

        self.session.commit()
        self.session.refresh(assignment)
        return self._decrypt_sensitive_fields(assignment)

    def get_material_types_summary(self) -> Dict[str, Any]:
        """
        Get summary of materials by type currently in storage.
        Updated to use proper DynamicMaterial relationships.

        Returns:
            Summary with material type statistics
        """
        # Query to get material type counts and quantities
        query = (
            self.session.query(
                MaterialType.name,
                MaterialType.id,
                func.count(self.model.material_id.distinct()).label("material_count"),
                func.sum(self.model.quantity).label("total_quantity")
            )
            .join(self.model.material)
            .join(DynamicMaterial.material_type)
            .group_by(MaterialType.id, MaterialType.name)
            .all()
        )

        # Convert to dictionary
        summary = {}
        for row in query:
            summary[row.name.lower()] = {
                "material_type_id": row.id,
                "material_type_name": row.name,
                "unique_materials": row.material_count,
                "total_quantity": float(row.total_quantity) if row.total_quantity else 0.0
            }

        return summary


class StorageMoveRepository(BaseRepository[StorageMove]):
    """
    Repository for StorageMove entity operations.
    Updated to use proper DynamicMaterial relationships.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the StorageMoveRepository."""
        super().__init__(session, encryption_service)
        self.model = StorageMove

    def get_moves_by_material(
            self,
            material_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageMove]:
        """
        Get storage moves for a specific material with location and material type info.

        Args:
            material_id: ID of the material
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage moves for the material
        """
        query = self.session.query(self.model).filter(
            self.model.material_id == material_id
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
            joinedload(self.model.from_location).joinedload(StorageLocation.storage_location_type),
            joinedload(self.model.to_location).joinedload(StorageLocation.storage_location_type)
        ).offset(skip).limit(limit)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_moves_by_material_type(
            self,
            material_type_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageMove]:
        """
        Get storage moves for materials of a specific type.

        Args:
            material_type_id: ID of the material type
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage moves for the material type
        """
        query = self.session.query(self.model).join(
            self.model.material
        ).filter(
            DynamicMaterial.material_type_id == material_type_id
        ).options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
            joinedload(self.model.from_location).joinedload(StorageLocation.storage_location_type),
            joinedload(self.model.to_location).joinedload(StorageLocation.storage_location_type)
        ).offset(skip).limit(limit)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_moves_by_storage(
            self,
            storage_id: str,
            is_source: bool = True,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageMove]:
        """
        Get storage moves involving a specific storage location.

        Args:
            storage_id: ID of the storage location
            is_source: If True, get moves from this location; if False, get moves to this location
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of storage moves involving the location
        """
        if is_source:
            query = self.session.query(self.model).filter(
                self.model.from_storage_id == storage_id
            )
        else:
            query = self.session.query(self.model).filter(
                self.model.to_storage_id == storage_id
            )

        query = query.options(
            joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
            joinedload(self.model.from_location).joinedload(StorageLocation.storage_location_type),
            joinedload(self.model.to_location).joinedload(StorageLocation.storage_location_type)
        ).offset(skip).limit(limit)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_moves(
            self,
            days: int = 7,
            skip: int = 0,
            limit: int = 100
    ) -> List[StorageMove]:
        """
        Get recent storage moves with material and location information.

        Args:
            days: Number of days to look back
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of recent storage moves
        """
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        query = (
            self.session.query(self.model)
            .filter(self.model.move_date >= cutoff_date)
            .options(
                joinedload(self.model.material).joinedload(DynamicMaterial.material_type),
                joinedload(self.model.from_location).joinedload(StorageLocation.storage_location_type),
                joinedload(self.model.to_location).joinedload(StorageLocation.storage_location_type)
            )
            .order_by(self.model.move_date.desc())
            .offset(skip).limit(limit)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_move(
            self,
            material_id: int,
            from_storage_id: str,
            to_storage_id: str,
            quantity: float,
            moved_by: str,
            reason: str = None,
    ) -> StorageMove:
        """
        Create a new storage move record.

        Args:
            material_id: ID of the material
            from_storage_id: ID of the source storage location
            to_storage_id: ID of the destination storage location
            quantity: Quantity being moved
            moved_by: Name or ID of the user making the move
            reason: Reason for the move

        Returns:
            The created move record
        """
        move_data = {
            "material_id": material_id,
            "from_storage_id": from_storage_id,
            "to_storage_id": to_storage_id,
            "quantity": quantity,
            "move_date": datetime.now().isoformat(),
            "moved_by": moved_by,
            "reason": reason,
        }

        return self.create(move_data)


class StoragePropertyDefinitionRepository(BaseRepository[StoragePropertyDefinition]):
    """
    Repository for StoragePropertyDefinition entity operations.
    Follows the same patterns as PropertyDefinition repository.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the StoragePropertyDefinitionRepository."""
        super().__init__(session, encryption_service)
        self.model = StoragePropertyDefinition

    def list_with_translations(
            self,
            skip: int = 0,
            limit: int = 100,
            data_type: Optional[str] = None,
            group_name: Optional[str] = None,
            search: Optional[str] = None,
            **filters
    ) -> Tuple[List[StoragePropertyDefinition], int]:
        """
        List storage property definitions with their translations.

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
        query = self.session.query(self.model)

        # Apply filters
        if data_type:
            query = query.filter(self.model.data_type == data_type)
        if group_name:
            query = query.filter(self.model.group_name == group_name)
        if search:
            query = query.filter(self.model.name.ilike(f"%{search}%"))

        # Apply other filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Get total count before pagination
        total_count = query.count()

        # Apply eager loading
        query = query.options(
            joinedload(self.model.translations),
            joinedload(self.model.enum_options),
            joinedload(self.model.enum_mappings)
        )

        # Apply pagination and ordering
        query = query.order_by(self.model.name).offset(skip).limit(limit)

        # Execute query
        result = query.all()

        return [self._decrypt_sensitive_fields(item) for item in result], total_count

    def get_by_id_with_translations(self, id: int) -> Optional[StoragePropertyDefinition]:
        """
        Get a storage property definition by ID with translations and options.

        Args:
            id: ID of the property definition

        Returns:
            Property definition if found, None otherwise
        """
        item = self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.translations),
            joinedload(self.model.enum_options),
            joinedload(self.model.enum_mappings)
        ).first()

        return self._decrypt_sensitive_fields(item) if item else None