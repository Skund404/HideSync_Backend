# File: app/repositories/storage_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from datetime import datetime

from app.db.models.storage import (
    StorageLocation,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.db.models.enums import StorageLocationType
from app.repositories.base_repository import BaseRepository


class StorageLocationRepository(BaseRepository[StorageLocation]):
    """
    Repository for StorageLocation entity operations.

    Provides methods for managing storage locations, including
    capacity tracking, utilization reporting, and location hierarchy.
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

    def get_storage_by_type(
        self, storage_type: StorageLocationType, skip: int = 0, limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get storage locations by type.

        Args:
            storage_type (StorageLocationType): The storage type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageLocation]: List of storage locations of the specified type
        """
        query = self.session.query(self.model).filter(self.model.type == storage_type)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_storage_by_section(
        self, section: str, skip: int = 0, limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get storage locations by section.

        Args:
            section (str): The section to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageLocation]: List of storage locations in the specified section
        """
        query = self.session.query(self.model).filter(self.model.section == section)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_available_storage(
        self, skip: int = 0, limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get storage locations with available capacity.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageLocation]: List of storage locations with available capacity
        """
        query = self.session.query(self.model).filter(
            self.model.utilized < self.model.capacity
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_child_locations(
        self, parent_id: str, skip: int = 0, limit: int = 100
    ) -> List[StorageLocation]:
        """
        Get child storage locations of a parent location.

        Args:
            parent_id (str): ID of the parent storage location
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageLocation]: List of child storage locations
        """
        query = self.session.query(self.model).filter(
            self.model.parentStorage == parent_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_storage_utilization(
        self, storage_id: str, change: int
    ) -> Optional[StorageLocation]:
        """
        Update a storage location's utilization.

        Args:
            storage_id (str): ID of the storage location
            change (int): Amount to add (positive) or subtract (negative) from utilization

        Returns:
            Optional[StorageLocation]: Updated storage location if found, None otherwise
        """
        storage = self.get_by_id(storage_id)
        if not storage:
            return None

        # Update utilization, ensuring it doesn't exceed capacity or go below 0
        storage.utilized = max(0, min(storage.capacity, storage.utilized + change))

        # Update lastModified timestamp
        storage.lastModified = datetime.now().isoformat()

        self.session.commit()
        self.session.refresh(storage)
        return self._decrypt_sensitive_fields(storage)

    def search_storage_locations(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[StorageLocation]:
        """
        Search for storage locations by name or description.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageLocation]: List of matching storage locations
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_storage_utilization_summary(self) -> Dict[str, Any]:
        """
        Get a summary of storage utilization across all locations.

        Returns:
            Dict[str, Any]: Dictionary with storage utilization statistics
        """
        total_capacity = self.session.query(func.sum(self.model.capacity)).scalar() or 0
        total_utilized = self.session.query(func.sum(self.model.utilized)).scalar() or 0

        # Get utilization by type
        type_utilization = (
            self.session.query(
                self.model.type,
                func.sum(self.model.capacity).label("capacity"),
                func.sum(self.model.utilized).label("utilized"),
            )
            .group_by(self.model.type)
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
                    "type": str(item.type),
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
                    "section": str(item.section),
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


class StorageCellRepository(BaseRepository[StorageCell]):
    """
    Repository for StorageCell entity operations.

    Manages individual storage cells within a storage location,
    including cell occupancy and item placement.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the StorageCellRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = StorageCell

    def get_cells_by_storage(self, storage_id: str) -> List[StorageCell]:
        """
        Get all cells for a specific storage location.

        Args:
            storage_id (str): ID of the storage location

        Returns:
            List[StorageCell]: List of cells in the storage location
        """
        query = self.session.query(self.model).filter(
            self.model.storageId == storage_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_occupied_cells(self, storage_id: str) -> List[StorageCell]:
        """
        Get occupied cells in a storage location.

        Args:
            storage_id (str): ID of the storage location

        Returns:
            List[StorageCell]: List of occupied cells
        """
        query = self.session.query(self.model).filter(
            and_(self.model.storageId == storage_id, self.model.occupied == True)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_empty_cells(self, storage_id: str) -> List[StorageCell]:
        """
        Get empty cells in a storage location.

        Args:
            storage_id (str): ID of the storage location

        Returns:
            List[StorageCell]: List of empty cells
        """
        query = self.session.query(self.model).filter(
            and_(self.model.storageId == storage_id, self.model.occupied == False)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def assign_cell(
        self, storage_id: str, position: Dict[str, Any], item_id: int, item_type: str
    ) -> Optional[StorageCell]:
        """
        Assign an item to a cell.

        Args:
            storage_id (str): ID of the storage location
            position (Dict[str, Any]): Position of the cell
            item_id (int): ID of the item to assign
            item_type (str): Type of the item

        Returns:
            Optional[StorageCell]: Updated cell if found, None otherwise
        """
        # Get the cell by position
        cell = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.storageId == storage_id, self.model.position == position
                )
            )
            .first()
        )

        if not cell:
            # Create a new cell if it doesn't exist
            cell = StorageCell(
                storageId=storage_id,
                position=position,
                itemId=item_id,
                itemType=item_type,
                occupied=True,
            )
            self.session.add(cell)
        else:
            # Update the existing cell
            cell.itemId = item_id
            cell.itemType = item_type
            cell.occupied = True

        self.session.commit()
        self.session.refresh(cell)
        return self._decrypt_sensitive_fields(cell)

    def clear_cell(
        self, storage_id: str, position: Dict[str, Any]
    ) -> Optional[StorageCell]:
        """
        Clear a cell (mark as unoccupied).

        Args:
            storage_id (str): ID of the storage location
            position (Dict[str, Any]): Position of the cell

        Returns:
            Optional[StorageCell]: Updated cell if found, None otherwise
        """
        cell = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.storageId == storage_id, self.model.position == position
                )
            )
            .first()
        )

        if not cell:
            return None

        cell.itemId = None
        cell.itemType = None
        cell.occupied = False

        self.session.commit()
        self.session.refresh(cell)
        return self._decrypt_sensitive_fields(cell)


class StorageAssignmentRepository(BaseRepository[StorageAssignment]):
    """
    Repository for StorageAssignment entity operations.

    Manages relationships between materials and their storage locations,
    tracking where materials are stored and how they're organized.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the StorageAssignmentRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = StorageAssignment

    def get_assignments_by_material(
        self, material_id: int, material_type: str
    ) -> List[StorageAssignment]:
        """
        Get storage assignments for a specific material.

        Args:
            material_id (int): ID of the material
            material_type (str): Type of the material

        Returns:
            List[StorageAssignment]: List of storage assignments for the material
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.materialId == material_id,
                self.model.materialType == material_type,
            )
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_assignments_by_storage(self, storage_id: str) -> List[StorageAssignment]:
        """
        Get all assignments in a specific storage location.

        Args:
            storage_id (str): ID of the storage location

        Returns:
            List[StorageAssignment]: List of assignments in the storage location
        """
        query = self.session.query(self.model).filter(
            self.model.storageId == storage_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_assignment(
        self,
        material_id: int,
        material_type: str,
        storage_id: str,
        position: Dict[str, Any],
        quantity: float,
        assigned_by: str,
    ) -> StorageAssignment:
        """
        Create a new storage assignment.

        Args:
            material_id (int): ID of the material
            material_type (str): Type of the material
            storage_id (str): ID of the storage location
            position (Dict[str, Any]): Position within the storage location
            quantity (float): Quantity of material assigned
            assigned_by (str): Name or ID of the user making the assignment

        Returns:
            StorageAssignment: The created assignment
        """
        assignment_data = {
            "materialId": material_id,
            "materialType": material_type,
            "storageId": storage_id,
            "position": position,
            "quantity": quantity,
            "assignedDate": datetime.now().isoformat(),
            "assignedBy": assigned_by,
        }

        return self.create(assignment_data)

    def update_assignment_quantity(
        self, assignment_id: str, quantity: float
    ) -> Optional[StorageAssignment]:
        """
        Update the quantity of a storage assignment.

        Args:
            assignment_id (str): ID of the assignment
            quantity (float): New quantity value

        Returns:
            Optional[StorageAssignment]: Updated assignment if found, None otherwise
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None

        assignment.quantity = quantity

        self.session.commit()
        self.session.refresh(assignment)
        return self._decrypt_sensitive_fields(assignment)


class StorageMoveRepository(BaseRepository[StorageMove]):
    """
    Repository for StorageMove entity operations.

    Tracks the movement of materials between storage locations,
    providing a history of storage transfers and relocations.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the StorageMoveRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = StorageMove

    def get_moves_by_material(
        self, material_id: int, material_type: str, skip: int = 0, limit: int = 100
    ) -> List[StorageMove]:
        """
        Get storage moves for a specific material.

        Args:
            material_id (int): ID of the material
            material_type (str): Type of the material
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageMove]: List of storage moves for the material
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.materialId == material_id,
                self.model.materialType == material_type,
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_moves_by_storage(
        self, storage_id: str, is_source: bool = True, skip: int = 0, limit: int = 100
    ) -> List[StorageMove]:
        """
        Get storage moves involving a specific storage location.

        Args:
            storage_id (str): ID of the storage location
            is_source (bool): If True, get moves from this location; if False, get moves to this location
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageMove]: List of storage moves involving the location
        """
        if is_source:
            query = self.session.query(self.model).filter(
                self.model.fromStorageId == storage_id
            )
        else:
            query = self.session.query(self.model).filter(
                self.model.toStorageId == storage_id
            )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_moves(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[StorageMove]:
        """
        Get recent storage moves.

        Args:
            days (int): Number of days to look back
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[StorageMove]: List of recent storage moves
        """
        cutoff_date = (
            datetime.now().isoformat()
        )  # This assumes moveDate is stored as ISO format

        query = (
            self.session.query(self.model)
            .filter(self.model.moveDate >= cutoff_date)
            .order_by(self.model.moveDate.desc())
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_move(
        self,
        material_id: int,
        material_type: str,
        from_storage_id: str,
        to_storage_id: str,
        quantity: float,
        moved_by: str,
        reason: str = None,
    ) -> StorageMove:
        """
        Create a new storage move record.

        Args:
            material_id (int): ID of the material
            material_type (str): Type of the material
            from_storage_id (str): ID of the source storage location
            to_storage_id (str): ID of the destination storage location
            quantity (float): Quantity being moved
            moved_by (str): Name or ID of the user making the move
            reason (str, optional): Reason for the move

        Returns:
            StorageMove: The created move record
        """
        move_data = {
            "materialId": material_id,
            "materialType": material_type,
            "fromStorageId": from_storage_id,
            "toStorageId": to_storage_id,
            "quantity": quantity,
            "moveDate": datetime.now().isoformat(),
            "movedBy": moved_by,
            "reason": reason,
        }

        return self.create(move_data)
