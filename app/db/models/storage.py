# File: app/db/models/storage.py
"""
Storage management models for the Leathercraft ERP system.

This module defines models for managing physical storage locations,
cells, and inventory assignments. It includes StorageLocation for
defining storage units, StorageCell for individual storage spaces,
StorageAssignment for item placements, and StorageMove for tracking
movement of items between locations.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Enum,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import StorageLocationType


class StorageLocation(AbstractBase, ValidationMixin, TimestampMixin):
    """
    StorageLocation model representing physical storage units.

    This model defines physical storage locations such as cabinets,
    shelves, drawers, etc., including their capacity and organization.

    Attributes:
        name: Location name/description
        type: Type of storage location
        section: Organizational section
        description: Detailed description
        dimensions: Physical dimensions
        capacity: Storage capacity
        utilized: Amount of capacity currently used
        status: Current status
        last_modified: Last modification date
        notes: Additional notes
        parent_storage: Parent storage location
    """

    __tablename__ = "storage_locations"
    __validated_fields__: ClassVar[Set[str]] = {"name", "type"}

    # Basic information
    name = Column(String(100), nullable=False)
    type = Column(Enum(StorageLocationType), nullable=False)
    section = Column(String(100))  # MAIN_WORKSHOP, TOOL_ROOM, STORAGE_ROOM, etc.
    description = Column(Text)

    # Physical properties
    dimensions = Column(
        JSON, nullable=True
    )  # {"width": 100, "height": 200, "depth": 50}
    capacity = Column(Integer)
    utilized = Column(Integer, default=0)

    # Status
    status = Column(String(50), default="ACTIVE")  # ACTIVE, FULL, MAINTENANCE
    last_modified = Column(String(50))  # ISO date string
    notes = Column(Text)
    parent_storage = Column(String(100))

    # Relationships
    cells = relationship(
        "StorageCell", back_populates="location", cascade="all, delete-orphan"
    )
    assignments = relationship(
        "StorageAssignment", back_populates="location", cascade="all, delete-orphan"
    )
    moves_from = relationship(
        "StorageMove",
        foreign_keys="StorageMove.from_storage_id",
        back_populates="from_location",
    )
    moves_to = relationship(
        "StorageMove",
        foreign_keys="StorageMove.to_storage_id",
        back_populates="to_location",
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate storage location name.

        Args:
            key: Field name ('name')
            name: Location name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Storage location name must be at least 2 characters")
        return name.strip()

    @validates("utilized")
    def validate_utilized(self, key: str, utilized: int) -> int:
        """
        Validate utilized capacity.

        Args:
            key: Field name ('utilized')
            utilized: Utilized capacity to validate

        Returns:
            Validated utilized capacity

        Raises:
            ValueError: If utilized is negative or exceeds capacity
        """
        if utilized < 0:
            raise ValueError("Utilized capacity cannot be negative")

        if self.capacity is not None and utilized > self.capacity:
            raise ValueError("Utilized capacity cannot exceed total capacity")

        # Update status based on capacity
        if self.capacity:
            if utilized >= self.capacity:
                self.status = "FULL"
            elif utilized > 0:
                self.status = "ACTIVE"
            else:
                self.status = "EMPTY"

        # Update last modified
        self.last_modified = datetime.now().isoformat()

        return utilized

    @hybrid_property
    def available_capacity(self) -> Optional[int]:
        """
        Calculate available capacity.

        Returns:
            Available capacity, or None if capacity is not set
        """
        if self.capacity is None:
            return None
        return max(0, self.capacity - self.utilized)

    @hybrid_property
    def utilization_percentage(self) -> Optional[float]:
        """
        Calculate utilization percentage.

        Returns:
            Utilization percentage, or None if capacity is not set
        """
        if not self.capacity:
            return None
        return (self.utilized / self.capacity) * 100

    def add_item(self, quantity: int = 1) -> bool:
        """
        Add an item to this location.

        Args:
            quantity: Number of items to add

        Returns:
            True if added successfully, False if insufficient space
        """
        if self.capacity and (self.utilized + quantity > self.capacity):
            return False

        self.utilized += quantity
        self.last_modified = datetime.now().isoformat()
        return True

    def remove_item(self, quantity: int = 1) -> bool:
        """
        Remove an item from this location.

        Args:
            quantity: Number of items to remove

        Returns:
            True if removed successfully, False if insufficient items
        """
        if self.utilized < quantity:
            return False

        self.utilized -= quantity
        self.last_modified = datetime.now().isoformat()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert StorageLocation instance to a dictionary.

        Returns:
            Dictionary representation of the storage location
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.type:
            result["type"] = self.type.name

        # Handle JSON fields
        if isinstance(result.get("dimensions"), str):
            import json

            try:
                result["dimensions"] = json.loads(result["dimensions"])
            except:
                result["dimensions"] = {}

        # Add calculated properties
        result["available_capacity"] = self.available_capacity
        result["utilization_percentage"] = self.utilization_percentage

        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageLocation."""
        return f"<StorageLocation(id={self.id}, name='{self.name}', type={self.type}, utilized={self.utilized}/{self.capacity})>"


class StorageCell(AbstractBase, ValidationMixin):
    """
    StorageCell model representing individual cells within a storage location.

    This model defines individual storage spaces within a larger storage
    location, allowing for precise item placement and tracking.

    Attributes:
        storage_id: ID of the parent storage location
        position: Position information
        item_id: ID of the stored item
        item_type: Type of stored item
        occupied: Whether the cell is occupied
        notes: Additional notes
    """

    __tablename__ = "storage_cells"
    __validated_fields__: ClassVar[Set[str]] = {"storage_id"}

    # Relationships
    storage_id = Column(String(36), ForeignKey("storage_locations.id"), nullable=False)

    # Cell information
    position = Column(
        JSON, nullable=True
    )  # {"row": 1, "column": 2, "level": 3} or {"x": 10, "y": 20, "z": 30}
    item_id = Column(Integer)
    item_type = Column(String(50))
    occupied = Column(Boolean, default=False)
    notes = Column(String(255))

    # Relationships
    location = relationship("StorageLocation", back_populates="cells")

    @hybrid_property
    def label(self) -> str:
        """
        Generate a human-readable cell label.

        Returns:
            Human-readable cell label based on position
        """
        if not self.position:
            return f"Cell {self.id}"

        # Convert position to label
        try:
            import json

            pos = (
                self.position
                if isinstance(self.position, dict)
                else json.loads(self.position)
            )

            if "row" in pos and "column" in pos:
                row = pos.get("row")
                col = pos.get("column")
                level = pos.get("level", "")

                # Convert column number to letter (1=A, 2=B, etc.)
                if isinstance(col, int) and col > 0:
                    col_letter = chr(64 + min(col, 26))  # Limit to A-Z
                else:
                    col_letter = str(col)

                level_str = f"-{level}" if level else ""
                return f"{row}{col_letter}{level_str}"

            elif "x" in pos and "y" in pos:
                x = pos.get("x")
                y = pos.get("y")
                z = pos.get("z", "")

                z_str = f"-{z}" if z else ""
                return f"{x}-{y}{z_str}"

        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        return f"Cell {self.id}"

    def assign_item(self, item_id: int, item_type: str) -> None:
        """
        Assign an item to this cell.

        Args:
            item_id: ID of the item
            item_type: Type of the item

        Raises:
            ValueError: If cell is already occupied
        """
        if self.occupied:
            raise ValueError(f"Cell {self.label} is already occupied")

        self.item_id = item_id
        self.item_type = item_type
        self.occupied = True

        # Update parent storage location
        if self.location and hasattr(self.location, "add_item"):
            self.location.add_item(1)

    def clear(self) -> None:
        """
        Clear this cell.
        """
        was_occupied = self.occupied

        self.item_id = None
        self.item_type = None
        self.occupied = False

        # Update parent storage location
        if was_occupied and self.location and hasattr(self.location, "remove_item"):
            self.location.remove_item(1)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert StorageCell instance to a dictionary.

        Returns:
            Dictionary representation of the storage cell
        """
        result = super().to_dict()

        # Handle JSON fields
        if isinstance(result.get("position"), str):
            import json

            try:
                result["position"] = json.loads(result["position"])
            except:
                result["position"] = {}

        # Add calculated properties
        result["label"] = self.label

        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageCell."""
        return f"<StorageCell(id={self.id}, storage_id={self.storage_id}, occupied={self.occupied})>"


class StorageAssignment(AbstractBase, ValidationMixin, TimestampMixin):
    """
    StorageAssignment model for tracking item placements.

    This model tracks assignments of materials and other items to
    storage locations, including quantities and placement details.

    Attributes:
        material_id: ID of the assigned material
        material_type: Type of material
        storage_id: ID of the storage location
        position: Position information
        quantity: Assigned quantity
        assigned_date: Date of assignment
        assigned_by: Person who made the assignment
        notes: Additional notes
    """

    __tablename__ = "storage_assignments"
    __validated_fields__: ClassVar[Set[str]] = {"material_id", "storage_id", "quantity"}

    # Material information
    material_id = Column(Integer, nullable=False)
    material_type = Column(String(50), nullable=False)

    # Storage information
    storage_id = Column(String(36), ForeignKey("storage_locations.id"), nullable=False)
    position = Column(
        JSON, nullable=True
    )  # {"row": 1, "column": 2, "level": 3} or {"x": 10, "y": 20}

    # Assignment details
    quantity = Column(Float, nullable=False)
    assigned_date = Column(String(50))  # ISO date string
    assigned_by = Column(String(100))
    notes = Column(String(255))

    # Relationships
    location = relationship("StorageLocation", back_populates="assignments")

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """
        Validate assignment quantity.

        Args:
            key: Field name ('quantity')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is negative
        """
        if quantity < 0:
            raise ValueError("Assignment quantity cannot be negative")
        return quantity

    def update_quantity(self, new_quantity: float, updated_by: str) -> float:
        """
        Update the assigned quantity.

        Args:
            new_quantity: New quantity
            updated_by: Person making the update

        Returns:
            Quantity change (new - old)

        Raises:
            ValueError: If new quantity is negative
        """
        if new_quantity < 0:
            raise ValueError("Assignment quantity cannot be negative")

        old_quantity = self.quantity
        self.quantity = new_quantity
        self.assigned_by = updated_by
        self.assigned_date = datetime.now().isoformat()

        # Update notes
        quantity_note = (
            f"Quantity updated from {old_quantity} to {new_quantity} by {updated_by}"
        )
        if self.notes:
            self.notes += f"; {quantity_note}"
        else:
            self.notes = quantity_note

        return new_quantity - old_quantity

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert StorageAssignment instance to a dictionary.

        Returns:
            Dictionary representation of the storage assignment
        """
        result = super().to_dict()

        # Handle JSON fields
        if isinstance(result.get("position"), str):
            import json

            try:
                result["position"] = json.loads(result["position"])
            except:
                result["position"] = {}

        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageAssignment."""
        return f"<StorageAssignment(id={self.id}, material_id={self.material_id}, storage_id={self.storage_id}, quantity={self.quantity})>"


class StorageMove(AbstractBase, ValidationMixin, TimestampMixin):
    """
    StorageMove model for tracking item movements.

    This model records movements of materials between storage locations,
    providing an audit trail of inventory movements.

    Attributes:
        material_id: ID of the moved material
        material_type: Type of material
        from_storage_id: Source storage location ID
        to_storage_id: Destination storage location ID
        quantity: Moved quantity
        move_date: Date of movement
        moved_by: Person who made the move
        reason: Reason for the move
        notes: Additional notes
    """

    __tablename__ = "storage_moves"
    __validated_fields__: ClassVar[Set[str]] = {
        "material_id",
        "from_storage_id",
        "to_storage_id",
        "quantity",
    }

    # Material information
    material_id = Column(Integer, nullable=False)
    material_type = Column(String(50), nullable=False)

    # Storage information
    from_storage_id = Column(
        String(36), ForeignKey("storage_locations.id"), nullable=False
    )
    to_storage_id = Column(
        String(36), ForeignKey("storage_locations.id"), nullable=False
    )

    # Move details
    quantity = Column(Float, nullable=False)
    move_date = Column(String(50))  # ISO date string
    moved_by = Column(String(100))
    reason = Column(String(255))
    notes = Column(String(255))

    # Relationships
    from_location = relationship(
        "StorageLocation", foreign_keys=[from_storage_id], back_populates="moves_from"
    )
    to_location = relationship(
        "StorageLocation", foreign_keys=[to_storage_id], back_populates="moves_to"
    )

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """
        Validate move quantity.

        Args:
            key: Field name ('quantity')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is not positive
        """
        if quantity <= 0:
            raise ValueError("Move quantity must be positive")
        return quantity

    @validates("from_storage_id", "to_storage_id")
    def validate_storage_ids(self, key: str, storage_id: str) -> str:
        """
        Validate storage IDs.

        Args:
            key: Field name
            storage_id: Storage ID to validate

        Returns:
            Validated storage ID

        Raises:
            ValueError: If from_storage_id equals to_storage_id
        """
        if (
            key == "to_storage_id"
            and hasattr(self, "from_storage_id")
            and self.from_storage_id == storage_id
        ):
            raise ValueError(
                "Source and destination storage locations must be different"
            )
        return storage_id

    def execute_move(self, session) -> None:
        """
        Execute the move in storage assignments.

        Args:
            session: SQLAlchemy session

        Returns:
            True if move was executed successfully, False otherwise
        """
        from sqlalchemy import and_

        # Find source assignment
        source_assignment = (
            session.query(StorageAssignment)
            .filter(
                and_(
                    StorageAssignment.material_id == self.material_id,
                    StorageAssignment.material_type == self.material_type,
                    StorageAssignment.storage_id == self.from_storage_id,
                )
            )
            .first()
        )

        # Verify source has enough quantity
        if not source_assignment or source_assignment.quantity < self.quantity:
            raise ValueError("Source location does not have enough quantity")

        # Find or create destination assignment
        dest_assignment = (
            session.query(StorageAssignment)
            .filter(
                and_(
                    StorageAssignment.material_id == self.material_id,
                    StorageAssignment.material_type == self.material_type,
                    StorageAssignment.storage_id == self.to_storage_id,
                )
            )
            .first()
        )

        if not dest_assignment:
            dest_assignment = StorageAssignment(
                material_id=self.material_id,
                material_type=self.material_type,
                storage_id=self.to_storage_id,
                quantity=0,
                assigned_date=datetime.now().isoformat(),
                assigned_by=self.moved_by,
            )
            session.add(dest_assignment)

        # Update quantities
        source_assignment.quantity -= self.quantity
        dest_assignment.quantity += self.quantity

        # Set move date
        self.move_date = datetime.now().isoformat()

        # Update storage locations
        if self.from_location and hasattr(self.from_location, "remove_item"):
            self.from_location.remove_item(1)

        if self.to_location and hasattr(self.to_location, "add_item"):
            self.to_location.add_item(1)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert StorageMove instance to a dictionary.

        Returns:
            Dictionary representation of the storage move
        """
        result = super().to_dict()

        # Add source and destination names if available
        if hasattr(self, "from_location") and self.from_location:
            result["from_location_name"] = self.from_location.name

        if hasattr(self, "to_location") and self.to_location:
            result["to_location_name"] = self.to_location.name

        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageMove."""
        return f"<StorageMove(id={self.id}, material_id={self.material_id}, from={self.from_storage_id}, to={self.to_storage_id}, quantity={self.quantity})>"
