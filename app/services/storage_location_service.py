# File: services/storage_location_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    DuplicateEntityException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import StorageLocationType
from app.db.models.storage import (
    StorageLocation,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.repositories.storage_repository import (
    StorageLocationRepository,
    StorageCellRepository,
    StorageAssignmentRepository,
    StorageMoveRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class StorageLocationCreated(DomainEvent):
    """Event emitted when a storage location is created."""

    def __init__(
        self,
        location_id: str,
        location_name: str,
        location_type: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize storage location created event.

        Args:
            location_id: ID of the created storage location
            location_name: Name of the storage location
            location_type: Type of the storage location
            user_id: Optional ID of the user who created the storage location
        """
        super().__init__()
        self.location_id = location_id
        self.location_name = location_name
        self.location_type = location_type
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
        """
        Initialize storage assignment created event.

        Args:
            assignment_id: ID of the created assignment
            material_id: ID of the assigned material
            location_id: ID of the storage location
            quantity: Quantity assigned
            user_id: Optional ID of the user who made the assignment
        """
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
        """
        Initialize storage move created event.

        Args:
            move_id: ID of the created move record
            material_id: ID of the moved material
            from_location_id: Source location ID
            to_location_id: Destination location ID
            quantity: Quantity moved
            user_id: Optional ID of the user who initiated the move
        """
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
        """
        Initialize storage space updated event.

        Args:
            location_id: ID of the storage location
            previous_capacity: Previous capacity value
            new_capacity: New capacity value
            previous_utilized: Previous utilization value
            new_utilized: New utilization value
            user_id: Optional ID of the user who made the update
        """
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
    Service for managing storage locations in the HideSync system.

    Provides functionality for:
    - Storage location creation and management
    - Cell management within locations
    - Material assignments to storage locations
    - Inventory movement tracking
    - Space utilization and optimization
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
        material_service=None,
        inventory_service=None,
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
            material_service: Optional material service for material operations
            inventory_service: Optional inventory service for inventory operations
        """
        self.session = session
        self.repository = location_repository or StorageLocationRepository(session)
        self.cell_repository = cell_repository or StorageCellRepository(session)
        self.assignment_repository = (
            assignment_repository or StorageAssignmentRepository(session)
        )
        self.move_repository = move_repository or StorageMoveRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.material_service = material_service
        self.inventory_service = inventory_service

    @validate_input(validate_storage_location)
    def create_storage_location(self, data: Dict[str, Any]) -> StorageLocation:
        """
        Create a new storage location.

        Args:
            data: Storage location data with name, type, section, etc.

        Returns:
            Created storage location entity

        Raises:
            ValidationException: If validation fails
            DuplicateEntityException: If location with same name already exists
        """
        with self.transaction():
            # Check for duplicate name in the same section
            section = data.get("section")
            name = data.get("name", "")

            if self._location_exists_by_name_and_section(name, section):
                raise DuplicateEntityException(
                    f"Storage location with name '{name}' already exists in section '{section}'",
                    "STORAGE_001",
                    {"field": "name", "value": name, "section": section},
                )

            # Set default values if not provided
            if "status" not in data:
                data["status"] = "ACTIVE"

            if "utilized" not in data:
                data["utilized"] = 0

            # Create storage location
            location = self.repository.create(data)

            # Create cells if dimensions are provided
            if "dimensions" in data and isinstance(data["dimensions"], dict):
                self._create_cells_for_location(location.id, data["dimensions"])

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    StorageLocationCreated(
                        location_id=location.id,
                        location_name=location.name,
                        location_type=location.type,
                        user_id=user_id,
                    )
                )

            return location

    def update_storage_location(
        self, location_id: str, data: Dict[str, Any]
    ) -> StorageLocation:
        """
        Update an existing storage location.

        Args:
            location_id: ID of the storage location
            data: Updated storage location data

        Returns:
            Updated storage location entity

        Raises:
            StorageLocationNotFoundException: If location not found
            ValidationException: If validation fails
            DuplicateEntityException: If name change would create a duplicate
        """
        with self.transaction():
            # Check if location exists
            location = self.get_by_id(location_id)
            if not location:
                from app.core.exceptions import StorageLocationNotFoundException

                raise StorageLocationNotFoundException(location_id)

            # Check for duplicate name if changing name
            if "name" in data and data["name"] != location.name and "section" in data:
                if self._location_exists_by_name_and_section(
                    data["name"], data["section"]
                ):
                    raise DuplicateEntityException(
                        f"Storage location with name '{data['name']}' already exists in section '{data['section']}'",
                        "STORAGE_001",
                        {
                            "field": "name",
                            "value": data["name"],
                            "section": data["section"],
                        },
                    )

            # Check for capacity changes
            previous_capacity = location.capacity
            previous_utilized = location.utilized

            # Update location
            updated_location = self.repository.update(location_id, data)

            # If capacity or utilization changed, publish event
            if ("capacity" in data or "utilized" in data) and self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    StorageSpaceUpdated(
                        location_id=location_id,
                        previous_capacity=previous_capacity,
                        new_capacity=updated_location.capacity,
                        previous_utilized=previous_utilized,
                        new_utilized=updated_location.utilized,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"StorageLocation:{location_id}")
                self.cache_service.invalidate(f"StorageLocation:detail:{location_id}")

            return updated_location

    def get_storage_location_with_details(self, location_id: str) -> Dict[str, Any]:
        """
        Get a storage location with comprehensive details.

        Args:
            location_id: ID of the storage location

        Returns:
            Storage location with cells, assignments, and space utilization

        Raises:
            StorageLocationNotFoundException: If location not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"StorageLocation:detail:{location_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get location
        location = self.get_by_id(location_id)
        if not location:
            from app.core.exceptions import StorageLocationNotFoundException

            raise StorageLocationNotFoundException(location_id)

        # Convert to dict and add related data
        result = location.to_dict()

        # Add cells
        result["cells"] = self._get_cells_for_location(location_id)

        # Add assignments
        result["assignments"] = self._get_assignments_for_location(location_id)

        # Calculate utilization statistics
        result["utilization_stats"] = self._calculate_utilization_statistics(
            location_id
        )

        # Add recent moves
        result["recent_moves"] = self._get_recent_moves_for_location(location_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    @validate_input(validate_storage_assignment)
    def assign_material_to_location(self, data: Dict[str, Any]) -> StorageAssignment:
        """
        Assign a material to a storage location.

        Args:
            data: Assignment data with material ID, location ID, quantity, etc.

        Returns:
            Created storage assignment entity

        Raises:
            ValidationException: If validation fails
            StorageLocationNotFoundException: If location not found
            MaterialNotFoundException: If material not found
            StorageCapacityExceededException: If assignment would exceed location capacity
        """
        with self.transaction():
            # Get location
            location_id = data.get("storage_id")
            location = self.get_by_id(location_id)
            if not location:
                from app.core.exceptions import StorageLocationNotFoundException

                raise StorageLocationNotFoundException(location_id)

            # Check if material exists if material service is available
            material_id = data.get("material_id")
            if self.material_service and material_id:
                material = self.material_service.get_by_id(material_id)
                if not material:
                    from app.core.exceptions import MaterialNotFoundException

                    raise MaterialNotFoundException(material_id)

            # Check capacity constraints
            quantity = data.get("quantity", 0)
            if not self._has_sufficient_capacity(location_id, quantity):
                from app.core.exceptions import StorageCapacityExceededException

                raise StorageCapacityExceededException(
                    f"Assignment would exceed capacity of storage location {location_id}",
                    "STORAGE_002",
                    {
                        "location_id": location_id,
                        "current_utilized": location.utilized,
                        "capacity": location.capacity,
                        "requested_quantity": quantity,
                    },
                )

            # Set assigned date and user if not provided
            if "assigned_date" not in data:
                data["assigned_date"] = datetime.now().isoformat()

            if "assigned_by" not in data and self.security_context:
                data["assigned_by"] = str(self.security_context.current_user.id)

            # Create assignment
            assignment = self.assignment_repository.create(data)

            # Update location utilization
            current_utilized = location.utilized or 0
            self.update_storage_location(
                location_id, {"utilized": current_utilized + quantity}
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    StorageAssignmentCreated(
                        assignment_id=assignment.id,
                        material_id=material_id,
                        location_id=location_id,
                        quantity=quantity,
                        user_id=user_id,
                    )
                )

            # Update material's storage location if material service is available
            if self.material_service and hasattr(
                self.material_service, "update_storage_location"
            ):
                self.material_service.update_storage_location(
                    material_id=material_id, storage_location_id=location_id
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"StorageLocation:detail:{location_id}")

            return assignment

    def remove_material_from_location(self, assignment_id: str) -> bool:
        """
        Remove a material assignment from a storage location.

        Args:
            assignment_id: ID of the assignment to remove

        Returns:
            True if removed successfully

        Raises:
            StorageAssignmentNotFoundException: If assignment not found
        """
        with self.transaction():
            # Get assignment
            assignment = self.assignment_repository.get_by_id(assignment_id)
            if not assignment:
                from app.core.exceptions import StorageAssignmentNotFoundException

                raise StorageAssignmentNotFoundException(assignment_id)

            # Get location
            location_id = assignment.storage_id
            location = self.get_by_id(location_id)
            if not location:
                from app.core.exceptions import StorageLocationNotFoundException

                raise StorageLocationNotFoundException(location_id)

            # Update location utilization
            current_utilized = location.utilized or 0
            quantity = assignment.quantity or 0
            self.update_storage_location(
                location_id, {"utilized": max(0, current_utilized - quantity)}
            )

            # Delete assignment
            success = self.assignment_repository.delete(assignment_id)

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"StorageLocation:detail:{location_id}")

            return success

    @validate_input(validate_storage_move)
    def move_material_between_locations(self, data: Dict[str, Any]) -> StorageMove:
        """
        Move material from one storage location to another.

        Args:
            data: Move data with material ID, source/destination locations, quantity, etc.

        Returns:
            Created storage move entity

        Raises:
            ValidationException: If validation fails
            StorageLocationNotFoundException: If location not found
            MaterialNotFoundException: If material not found
            InsufficientQuantityException: If source has insufficient quantity
            StorageCapacityExceededException: If move would exceed destination capacity
        """
        with self.transaction():
            # Get source location
            from_location_id = data.get("from_storage_id")
            from_location = self.get_by_id(from_location_id)
            if not from_location:
                from app.core.exceptions import StorageLocationNotFoundException

                raise StorageLocationNotFoundException(from_location_id)

            # Get destination location
            to_location_id = data.get("to_storage_id")
            to_location = self.get_by_id(to_location_id)
            if not to_location:
                from app.core.exceptions import StorageLocationNotFoundException

                raise StorageLocationNotFoundException(to_location_id)

            # Check if material exists if material service is available
            material_id = data.get("material_id")
            if self.material_service and material_id:
                material = self.material_service.get_by_id(material_id)
                if not material:
                    from app.core.exceptions import MaterialNotFoundException

                    raise MaterialNotFoundException(material_id)

            # Get current assignment to check quantity
            quantity = data.get("quantity", 0)
            source_assignment = self._get_material_assignment(
                from_location_id, material_id
            )
            if not source_assignment or source_assignment.quantity < quantity:
                from app.core.exceptions import InsufficientQuantityException

                available = source_assignment.quantity if source_assignment else 0
                raise InsufficientQuantityException(
                    f"Insufficient quantity in source location. Requested: {quantity}, Available: {available}",
                    "STORAGE_003",
                    {
                        "material_id": material_id,
                        "location_id": from_location_id,
                        "requested": quantity,
                        "available": available,
                    },
                )

            # Check destination capacity
            if not self._has_sufficient_capacity(to_location_id, quantity):
                from app.core.exceptions import StorageCapacityExceededException

                raise StorageCapacityExceededException(
                    f"Move would exceed capacity of destination location {to_location_id}",
                    "STORAGE_002",
                    {
                        "location_id": to_location_id,
                        "current_utilized": to_location.utilized,
                        "capacity": to_location.capacity,
                        "requested_quantity": quantity,
                    },
                )

            # Set move date and user if not provided
            if "move_date" not in data:
                data["move_date"] = datetime.now().isoformat()

            if "moved_by" not in data and self.security_context:
                data["moved_by"] = str(self.security_context.current_user.id)

            # Create move record
            move = self.move_repository.create(data)

            # Update source location utilization
            self.update_storage_location(
                from_location_id,
                {"utilized": max(0, from_location.utilized - quantity)},
            )

            # Update destination location utilization
            self.update_storage_location(
                to_location_id, {"utilized": (to_location.utilized or 0) + quantity}
            )

            # Update source assignment
            remaining_quantity = source_assignment.quantity - quantity
            if remaining_quantity > 0:
                self.assignment_repository.update(
                    source_assignment.id, {"quantity": remaining_quantity}
                )
            else:
                # Remove assignment if no quantity remains
                self.assignment_repository.delete(source_assignment.id)

            # Create or update destination assignment
            dest_assignment = self._get_material_assignment(to_location_id, material_id)
            if dest_assignment:
                # Update existing assignment
                self.assignment_repository.update(
                    dest_assignment.id,
                    {"quantity": dest_assignment.quantity + quantity},
                )
            else:
                # Create new assignment
                self.assignment_repository.create(
                    {
                        "material_id": material_id,
                        "material_type": data.get("material_type"),
                        "storage_id": to_location_id,
                        "quantity": quantity,
                        "assigned_date": datetime.now().isoformat(),
                        "assigned_by": data.get("moved_by"),
                    }
                )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    StorageMoveCreated(
                        move_id=move.id,
                        material_id=material_id,
                        from_location_id=from_location_id,
                        to_location_id=to_location_id,
                        quantity=quantity,
                        user_id=user_id,
                    )
                )

            # Invalidate caches
            if self.cache_service:
                self.cache_service.invalidate(
                    f"StorageLocation:detail:{from_location_id}"
                )
                self.cache_service.invalidate(
                    f"StorageLocation:detail:{to_location_id}"
                )

            return move

    def get_storage_locations_by_type(
        self, location_type: Union[StorageLocationType, str]
    ) -> List[StorageLocation]:
        """
        Get all storage locations of a specific type.

        Args:
            location_type: Type of storage location to filter by

        Returns:
            List of storage locations matching the type
        """
        # Convert string type to enum value if needed
        if isinstance(location_type, StorageLocationType):
            location_type = location_type.value

        return self.repository.list(type=location_type)

    def get_storage_locations_by_section(self, section: str) -> List[StorageLocation]:
        """
        Get all storage locations in a specific section.

        Args:
            section: Section to filter by

        Returns:
            List of storage locations in the section
        """
        return self.repository.list(section=section)

    def find_suitable_locations(
        self,
        material_type: str,
        quantity: float,
        current_location_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find suitable storage locations for a given material and quantity.

        Args:
            material_type: Type of material to store
            quantity: Quantity to store
            current_location_id: Optional current location ID (to exclude)

        Returns:
            List of suitable locations with available capacity
        """
        # Get all active locations
        locations = self.repository.list(status="ACTIVE")

        # Filter by appropriate location type for material
        material_type_to_location_mapping = {
            "LEATHER": ["SHELF", "DRAWER", "CABINET"],
            "HARDWARE": ["BIN", "DRAWER", "CABINET"],
            "SUPPLIES": ["SHELF", "DRAWER", "CABINET"],
            "THREAD": ["RACK", "CABINET"],
            "TOOL": ["CABINET", "DRAWER", "PEGBOARD"],
        }

        suitable_types = material_type_to_location_mapping.get(
            material_type.upper(), ["SHELF", "DRAWER", "CABINET"]
        )

        suitable_locations = []
        for location in locations:
            # Skip current location
            if current_location_id and location.id == current_location_id:
                continue

            # Check if location type is suitable
            if location.type not in suitable_types:
                continue

            # Check available capacity
            available_capacity = (location.capacity or 0) - (location.utilized or 0)
            if available_capacity >= quantity:
                suitable_locations.append(
                    {
                        "id": location.id,
                        "name": location.name,
                        "type": location.type,
                        "section": location.section,
                        "available_capacity": available_capacity,
                        "utilization_percentage": round(
                            (location.utilized or 0) / (location.capacity or 1) * 100, 1
                        ),
                    }
                )

        # Sort by utilization percentage (ascending)
        return sorted(suitable_locations, key=lambda x: x["utilization_percentage"])

    def get_storage_utilization_overview(self) -> Dict[str, Any]:
        """
        Get overview of storage utilization across all locations.

        Returns:
            Dictionary with utilization statistics
        """
        # Get all locations
        locations = self.repository.list()

        # Calculate overall utilization
        total_capacity = sum(location.capacity or 0 for location in locations)
        total_utilized = sum(location.utilized or 0 for location in locations)

        # Calculate utilization by type
        utilization_by_type = {}
        for location in locations:
            location_type = location.type
            if location_type not in utilization_by_type:
                utilization_by_type[location_type] = {
                    "capacity": 0,
                    "utilized": 0,
                    "count": 0,
                }

            utilization_by_type[location_type]["capacity"] += location.capacity or 0
            utilization_by_type[location_type]["utilized"] += location.utilized or 0
            utilization_by_type[location_type]["count"] += 1

        # Calculate utilization by section
        utilization_by_section = {}
        for location in locations:
            section = location.section
            if section not in utilization_by_section:
                utilization_by_section[section] = {
                    "capacity": 0,
                    "utilized": 0,
                    "count": 0,
                }

            utilization_by_section[section]["capacity"] += location.capacity or 0
            utilization_by_section[section]["utilized"] += location.utilized or 0
            utilization_by_section[section]["count"] += 1

        # Calculate percentages
        for stats in utilization_by_type.values():
            stats["percentage"] = round(
                (
                    (stats["utilized"] / stats["capacity"] * 100)
                    if stats["capacity"] > 0
                    else 0
                ),
                1,
            )

        for stats in utilization_by_section.values():
            stats["percentage"] = round(
                (
                    (stats["utilized"] / stats["capacity"] * 100)
                    if stats["capacity"] > 0
                    else 0
                ),
                1,
            )

        return {
            "total_locations": len(locations),
            "total_capacity": total_capacity,
            "total_utilized": total_utilized,
            "overall_percentage": round(
                (total_utilized / total_capacity * 100) if total_capacity > 0 else 0, 1
            ),
            "by_type": utilization_by_type,
            "by_section": utilization_by_section,
            "locations_at_capacity": self._count_locations_at_capacity_threshold(
                locations, 90
            ),
            "locations_available": self._count_locations_below_capacity_threshold(
                locations, 50
            ),
        }

    def _location_exists_by_name_and_section(self, name: str, section: str) -> bool:
        """
        Check if a storage location with the given name exists in the specified section.

        Args:
            name: Storage location name to check
            section: Section to check

        Returns:
            True if location exists, False otherwise
        """
        existing = self.repository.find_by_name_and_section(name, section)
        return len(existing) > 0

    def _create_cells_for_location(
        self, location_id: str, dimensions: Dict[str, Any]
    ) -> List[StorageCell]:
        """
        Create storage cells for a location based on dimensions.

        Args:
            location_id: ID of the storage location
            dimensions: Dictionary with layout dimensions

        Returns:
            List of created storage cells
        """
        cells = []
        rows = dimensions.get("rows", 1)
        columns = dimensions.get("columns", 1)

        # Create cells in a grid layout
        for row in range(rows):
            for col in range(columns):
                cell_data = {
                    "storage_id": location_id,
                    "position": {"row": row, "column": col},
                    "occupied": False,
                }

                cell = self.cell_repository.create(cell_data)
                cells.append(cell)

        return cells

    def _get_cells_for_location(self, location_id: str) -> List[Dict[str, Any]]:
        """
        Get all cells for a storage location.

        Args:
            location_id: ID of the storage location

        Returns:
            List of cells with their data
        """
        cells = self.cell_repository.list(storage_id=location_id)

        return [
            {
                "id": cell.id,
                "position": cell.position,
                "occupied": cell.occupied,
                "item_id": cell.item_id,
                "item_type": cell.item_type,
                "notes": cell.notes,
            }
            for cell in cells
        ]

    def _get_assignments_for_location(self, location_id: str) -> List[Dict[str, Any]]:
        """
        Get all material assignments for a storage location.

        Args:
            location_id: ID of the storage location

        Returns:
            List of assignments with material details
        """
        assignments = self.assignment_repository.list(storage_id=location_id)

        # Enrich with material details if material service available
        result = []
        for assignment in assignments:
            assignment_dict = {
                "id": assignment.id,
                "material_id": assignment.material_id,
                "material_type": assignment.material_type,
                "quantity": assignment.quantity,
                "assigned_date": (
                    assignment.assigned_date.isoformat()
                    if assignment.assigned_date
                    else None
                ),
                "assigned_by": assignment.assigned_by,
                "notes": assignment.notes,
            }

            # Add material details if available
            if self.material_service and assignment.material_id:
                material = self.material_service.get_by_id(assignment.material_id)
                if material:
                    assignment_dict["material_name"] = material.name
                    assignment_dict["material_unit"] = material.unit

            result.append(assignment_dict)

        return result

    def _get_recent_moves_for_location(
        self, location_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent moves involving a storage location.

        Args:
            location_id: ID of the storage location
            limit: Maximum number of moves to return

        Returns:
            List of recent moves
        """
        # Get moves involving this location (either source or destination)
        source_moves = self.move_repository.list(
            from_storage_id=location_id,
            order_by="move_date",
            order_dir="desc",
            limit=limit,
        )

        dest_moves = self.move_repository.list(
            to_storage_id=location_id,
            order_by="move_date",
            order_dir="desc",
            limit=limit,
        )

        # Combine and sort
        all_moves = sorted(
            list(source_moves) + list(dest_moves),
            key=lambda x: x.move_date if x.move_date else datetime.min,
            reverse=True,
        )[:limit]

        # Convert to dictionaries with direction indicator
        result = []
        for move in all_moves:
            is_outgoing = move.from_storage_id == location_id
            direction = "outgoing" if is_outgoing else "incoming"

            move_dict = {
                "id": move.id,
                "material_id": move.material_id,
                "material_type": move.material_type,
                "from_location_id": move.from_storage_id,
                "to_location_id": move.to_storage_id,
                "quantity": move.quantity,
                "direction": direction,
                "move_date": move.move_date.isoformat() if move.move_date else None,
                "moved_by": move.moved_by,
                "reason": move.reason,
            }

            # Add material details if available
            if self.material_service and move.material_id:
                material = self.material_service.get_by_id(move.material_id)
                if material:
                    move_dict["material_name"] = material.name

            # Add location names
            if move.from_storage_id:
                from_location = self.get_by_id(move.from_storage_id)
                move_dict["from_location_name"] = (
                    from_location.name if from_location else "Unknown"
                )

            if move.to_storage_id:
                to_location = self.get_by_id(move.to_storage_id)
                move_dict["to_location_name"] = (
                    to_location.name if to_location else "Unknown"
                )

            result.append(move_dict)

        return result

    def _calculate_utilization_statistics(self, location_id: str) -> Dict[str, Any]:
        """
        Calculate utilization statistics for a storage location.

        Args:
            location_id: ID of the storage location

        Returns:
            Dictionary with utilization statistics
        """
        location = self.get_by_id(location_id)
        if not location:
            return {
                "capacity": 0,
                "utilized": 0,
                "available": 0,
                "utilization_percentage": 0,
                "material_count": 0,
            }

        capacity = location.capacity or 0
        utilized = location.utilized or 0
        available = max(0, capacity - utilized)
        percentage = round((utilized / capacity * 100) if capacity > 0 else 0, 1)

        # Count distinct materials
        assignments = self.assignment_repository.list(storage_id=location_id)
        material_count = len(assignments)

        # Get last move date
        recent_moves = self._get_recent_moves_for_location(location_id, limit=1)
        last_move_date = recent_moves[0]["move_date"] if recent_moves else None

        return {
            "capacity": capacity,
            "utilized": utilized,
            "available": available,
            "utilization_percentage": percentage,
            "material_count": material_count,
            "last_move_date": last_move_date,
            "is_full": percentage >= 95,
            "is_nearly_full": percentage >= 80 and percentage < 95,
            "is_underutilized": percentage < 30 and capacity > 0,
        }

    def _get_material_assignment(
        self, location_id: str, material_id: int
    ) -> Optional[StorageAssignment]:
        """
        Get the assignment record for a material in a location.

        Args:
            location_id: ID of the storage location
            material_id: ID of the material

        Returns:
            Assignment record if found, None otherwise
        """
        assignments = self.assignment_repository.list(
            storage_id=location_id, material_id=material_id
        )

        return assignments[0] if assignments else None

    def _has_sufficient_capacity(self, location_id: str, quantity: float) -> bool:
        """
        Check if a location has sufficient capacity for a quantity.

        Args:
            location_id: ID of the storage location
            quantity: Quantity to check

        Returns:
            True if location has sufficient capacity, False otherwise
        """
        location = self.get_by_id(location_id)
        if not location:
            return False

        capacity = location.capacity or 0
        utilized = location.utilized or 0

        return (utilized + quantity) <= capacity

    def _count_locations_at_capacity_threshold(
        self, locations: List[StorageLocation], threshold: int
    ) -> int:
        """
        Count locations at or above a capacity utilization threshold.

        Args:
            locations: List of storage locations
            threshold: Percentage threshold

        Returns:
            Count of locations at or above threshold
        """
        count = 0
        for location in locations:
            capacity = location.capacity or 0
            utilized = location.utilized or 0

            if capacity > 0:
                percentage = (utilized / capacity) * 100
                if percentage >= threshold:
                    count += 1

        return count

    def _count_locations_below_capacity_threshold(
        self, locations: List[StorageLocation], threshold: int
    ) -> int:
        """
        Count locations below a capacity utilization threshold.

        Args:
            locations: List of storage locations
            threshold: Percentage threshold

        Returns:
            Count of locations below threshold
        """
        count = 0
        for location in locations:
            capacity = location.capacity or 0
            utilized = location.utilized or 0

            if capacity > 0:
                percentage = (utilized / capacity) * 100
                if percentage < threshold:
                    count += 1

        return count
