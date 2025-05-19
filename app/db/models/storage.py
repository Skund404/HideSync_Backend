# File: app/db/models/storage.py
"""
Storage management models for the Dynamic Material Management System.

This module defines models for managing physical storage locations with dynamic properties,
following the same patterns as the dynamic material system. Updated to support:
- Dynamic storage location types via enum system
- Custom properties for storage locations
- Internationalization support
- Theme and UI configuration
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
    UniqueConstraint,
    DateTime,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import json

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin


class StorageLocationType(AbstractBase, TimestampMixin):
    """
    Defines a type of storage location with customizable properties.
    Follows the same pattern as MaterialType in the dynamic material system.
    """
    __tablename__ = "storage_location_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    icon = Column(String(50))
    color_scheme = Column(String(50))
    _ui_config = Column("ui_config", Text)
    _storage_config = Column("storage_config", Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_system = Column(Boolean, default=False)
    visibility_level = Column(String(50), default="all")  # all, admin, or specific tier

    # Relationships
    properties = relationship(
        "StorageLocationTypeProperty",
        back_populates="storage_location_type",
        cascade="all, delete-orphan"
    )
    translations = relationship(
        "StorageLocationTypeTranslation",
        back_populates="storage_location_type",
        cascade="all, delete-orphan"
    )
    storage_locations = relationship(
        "StorageLocation",
        back_populates="storage_location_type",
        cascade="all, delete-orphan"
    )

    # JSON property handlers
    @property
    def ui_config(self):
        if self._ui_config:
            try:
                return json.loads(self._ui_config)
            except:
                return {}
        return {}

    @ui_config.setter
    def ui_config(self, value):
        if value is not None:
            self._ui_config = json.dumps(value)
        else:
            self._ui_config = None

    @property
    def storage_config(self):
        if self._storage_config:
            try:
                return json.loads(self._storage_config)
            except:
                return {}
        return {}

    @storage_config.setter
    def storage_config(self, value):
        if value is not None:
            self._storage_config = json.dumps(value)
        else:
            self._storage_config = None

    def get_display_name(self, locale="en"):
        """Get the localized display name"""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or name
        return self.translations[0].display_name if self.translations else self.name


class StorageLocationTypeTranslation(AbstractBase):
    """
    Translations for storage location types.
    """
    __tablename__ = "storage_location_type_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    storage_location_type_id = Column(Integer, ForeignKey("storage_location_types.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)  # e.g., 'en', 'fr', 'es'
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    storage_location_type = relationship("StorageLocationType", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('storage_location_type_id', 'locale', name='uq_storage_location_type_translation'),
    )


class StoragePropertyDefinition(AbstractBase, TimestampMixin):
    """
    Definition of a property that can be assigned to storage location types.
    Follows the same pattern as PropertyDefinition in the dynamic material system.
    """
    __tablename__ = "storage_property_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    data_type = Column(String(50), nullable=False)  # string, number, boolean, enum, date, file, etc.
    group_name = Column(String(100))
    unit = Column(String(50))
    is_required = Column(Boolean, default=False)
    has_multiple_values = Column(Boolean, default=False)
    _validation_rules = Column("validation_rules", Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_system = Column(Boolean, default=False)
    enum_type_id = Column(Integer, ForeignKey("enum_types.id"))

    # Relationships
    translations = relationship(
        "StoragePropertyDefinitionTranslation",
        back_populates="property",
        cascade="all, delete-orphan"
    )
    enum_options = relationship(
        "StoragePropertyEnumOption",
        back_populates="property",
        cascade="all, delete-orphan"
    )
    enum_mappings = relationship(
        "StoragePropertyEnumMapping",
        back_populates="property",
        cascade="all, delete-orphan"
    )
    enum_type = relationship("EnumType")
    storage_location_type_properties = relationship(
        "StorageLocationTypeProperty",
        back_populates="property"
    )

    # JSON property handlers
    @property
    def validation_rules(self):
        if self._validation_rules:
            try:
                return json.loads(self._validation_rules)
            except:
                return {}
        return {}

    @validation_rules.setter
    def validation_rules(self, value):
        if value is not None:
            self._validation_rules = json.dumps(value)
        else:
            self._validation_rules = None

    def get_display_name(self, locale="en"):
        """Get the localized display name"""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or name
        return self.translations[0].display_name if self.translations else self.name


class StoragePropertyDefinitionTranslation(AbstractBase):
    """
    Translations for storage property definitions.
    """
    __tablename__ = "storage_property_definition_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey("storage_property_definitions.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)  # e.g., 'en', 'fr', 'es'
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    property = relationship("StoragePropertyDefinition", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('property_id', 'locale', name='uq_storage_property_definition_translation'),
    )


class StoragePropertyEnumOption(AbstractBase):
    """
    Custom enum options for storage property definitions with enum data type.
    """
    __tablename__ = "storage_property_enum_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey("storage_property_definitions.id", ondelete="CASCADE"), nullable=False)
    value = Column(String(100), nullable=False)
    display_value = Column(String(255), nullable=False)
    color = Column(String(50))
    display_order = Column(Integer, default=0)

    # Relationships
    property = relationship("StoragePropertyDefinition", back_populates="enum_options")

    # Constraints
    __table_args__ = (
        UniqueConstraint('property_id', 'value', name='uq_storage_property_enum_option'),
    )


class StoragePropertyEnumMapping(AbstractBase):
    """
    Maps a storage property to an enum type from the dynamic enum system.
    """
    __tablename__ = "storage_property_enum_mappings"

    property_id = Column(Integer, ForeignKey("storage_property_definitions.id", ondelete="CASCADE"), primary_key=True)
    enum_type_id = Column(Integer, ForeignKey("enum_types.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    property = relationship("StoragePropertyDefinition", back_populates="enum_mappings")
    enum_type = relationship("EnumType")


class StorageLocationTypeProperty(AbstractBase):
    """
    Junction table that associates properties with storage location types
    and defines their configuration within that storage location type.
    """
    __tablename__ = "storage_location_type_properties"

    storage_location_type_id = Column(Integer, ForeignKey("storage_location_types.id", ondelete="CASCADE"), primary_key=True)
    property_id = Column(Integer, ForeignKey("storage_property_definitions.id", ondelete="CASCADE"), primary_key=True)
    display_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    is_filterable = Column(Boolean, default=True)
    is_displayed_in_list = Column(Boolean, default=True)
    is_displayed_in_card = Column(Boolean, default=True)
    _default_value = Column("default_value", Text)

    # Relationships
    storage_location_type = relationship("StorageLocationType", back_populates="properties")
    property = relationship("StoragePropertyDefinition", back_populates="storage_location_type_properties")

    # JSON property handlers
    @property
    def default_value(self):
        if self._default_value:
            try:
                return json.loads(self._default_value)
            except:
                return None
        return None

    @default_value.setter
    def default_value(self, value):
        if value is not None:
            self._default_value = json.dumps(value)
        else:
            self._default_value = None


class StorageLocation(AbstractBase, ValidationMixin, TimestampMixin):
    """
    StorageLocation model representing physical storage units with dynamic properties.
    Updated to follow the dynamic material system patterns.

    This model defines physical storage locations such as cabinets,
    shelves, drawers, etc., including their capacity and organization.

    Attributes:
        name: Location name/description
        storage_location_type_id: ID of the storage location type (dynamic)
        section: Organizational section
        description: Detailed description
        dimensions: Physical dimensions (JSON)
        capacity: Storage capacity
        utilized: Amount of capacity currently used
        status: Current status
        last_modified: Last modification date
        notes: Additional notes
        parent_storage_id: Parent storage location ID
    """

    __tablename__ = "storage_locations"
    __validated_fields__: ClassVar[Set[str]] = {"name", "storage_location_type_id"}

    # Basic information
    name = Column(String(100), nullable=False)
    storage_location_type_id = Column(Integer, ForeignKey("storage_location_types.id"), nullable=False)
    section = Column(String(100))  # MAIN_WORKSHOP, TOOL_ROOM, STORAGE_ROOM, etc.
    description = Column(Text)

    # Physical properties (JSON stored as TEXT for SQLite compatibility)
    _dimensions = Column("dimensions", Text)
    capacity = Column(Integer)
    utilized = Column(Integer, default=0)

    # Status and metadata
    status = Column(String(50), default="ACTIVE")  # ACTIVE, FULL, MAINTENANCE
    last_modified = Column(String(50))  # ISO date string
    notes = Column(Text)
    parent_storage_id = Column(String(100), ForeignKey("storage_locations.id"))
    created_by = Column(Integer, ForeignKey("users.id"))

    # Configuration (JSON stored as TEXT)
    _ui_config = Column("ui_config", Text)
    _storage_config = Column("storage_config", Text)

    # Relationships
    storage_location_type = relationship("StorageLocationType", back_populates="storage_locations")
    property_values = relationship(
        "StorageLocationPropertyValue",
        back_populates="storage_location",
        cascade="all, delete-orphan"
    )
    translations = relationship(
        "StorageLocationTranslation",
        back_populates="storage_location",
        cascade="all, delete-orphan"
    )
    cells = relationship(
        "StorageCell",
        back_populates="location",
        cascade="all, delete-orphan"
    )
    assignments = relationship(
        "StorageAssignment",
        back_populates="location",
        cascade="all, delete-orphan"
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
    parent_storage = relationship("StorageLocation", remote_side=[id])
    child_storages = relationship("StorageLocation", back_populates="parent_storage")

    # JSON property handlers (following dynamic material pattern)
    @property
    def dimensions(self):
        if self._dimensions:
            try:
                return json.loads(self._dimensions)
            except:
                return {}
        return {}

    @dimensions.setter
    def dimensions(self, value):
        if value is not None:
            self._dimensions = json.dumps(value)
        else:
            self._dimensions = None

    @property
    def ui_config(self):
        if self._ui_config:
            try:
                return json.loads(self._ui_config)
            except:
                return {}
        return {}

    @ui_config.setter
    def ui_config(self, value):
        if value is not None:
            self._ui_config = json.dumps(value)
        else:
            self._ui_config = None

    @property
    def storage_config(self):
        if self._storage_config:
            try:
                return json.loads(self._storage_config)
            except:
                return {}
        return {}

    @storage_config.setter
    def storage_config(self, value):
        if value is not None:
            self._storage_config = json.dumps(value)
        else:
            self._storage_config = None

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

    @hybrid_property
    def assigned_materials(self):
        """Get all materials assigned to this location."""
        return [assignment.material for assignment in self.assignments if assignment.material]

    @hybrid_property
    def material_types_stored(self):
        """Get distinct material types stored in this location."""
        material_types = set()
        for assignment in self.assignments:
            if assignment.material and assignment.material.material_type:
                material_types.add(assignment.material.material_type)
        return list(material_types)

    def get_display_name(self, locale="en"):
        """Get the localized display name"""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or name
        return self.translations[0].display_name if self.translations else self.name

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

        # Include type information via relationship
        if self.storage_location_type:
            result["storage_location_type"] = {
                "id": self.storage_location_type.id,
                "name": self.storage_location_type.name,
                "icon": self.storage_location_type.icon,
                "color_scheme": self.storage_location_type.color_scheme
            }

        # Add calculated properties
        result["available_capacity"] = self.available_capacity
        result["utilization_percentage"] = self.utilization_percentage
        result["dimensions"] = self.dimensions
        result["ui_config"] = self.ui_config
        result["storage_config"] = self.storage_config

        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageLocation."""
        type_name = self.storage_location_type.name if self.storage_location_type else "Unknown"
        return f"<StorageLocation(id={self.id}, name='{self.name}', type={type_name}, utilized={self.utilized}/{self.capacity})>"


class StorageLocationTranslation(AbstractBase):
    """
    Translations for storage locations.
    """
    __tablename__ = "storage_location_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    storage_location_id = Column(String(36), ForeignKey("storage_locations.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)  # e.g., 'en', 'fr', 'es'
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    storage_location = relationship("StorageLocation", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('storage_location_id', 'locale', name='uq_storage_location_translation'),
    )


class StorageLocationPropertyValue(AbstractBase):
    """
    Stores property values for storage locations based on their property definitions.
    Uses a polymorphic storage approach to store different data types.
    Follows the same pattern as MaterialPropertyValue.
    """
    __tablename__ = "storage_location_property_values"

    storage_location_id = Column(String(36), ForeignKey("storage_locations.id", ondelete="CASCADE"), primary_key=True)
    property_id = Column(Integer, ForeignKey("storage_property_definitions.id"), primary_key=True)

    # Polymorphic storage for different data types
    value_string = Column(Text)
    value_number = Column(Float)
    value_boolean = Column(Boolean)
    value_date = Column(String(50))  # Store as ISO string for SQLite compatibility
    value_enum_id = Column(Integer)  # References an enum value in the respective enum table
    value_file_id = Column(String(100))  # Reference to file/media asset
    value_reference_id = Column(Integer)  # Reference to another entity

    # Relationships
    storage_location = relationship("StorageLocation", back_populates="property_values")
    property = relationship("StoragePropertyDefinition")


class StorageCell(AbstractBase, ValidationMixin):
    """
    StorageCell model representing individual cells within a storage location.
    Updated to be material-specific instead of generic item storage.

    Attributes:
        storage_id: ID of the parent storage location
        position: Position information
        material_id: ID of the stored material (FK to DynamicMaterial)
        occupied: Whether the cell is occupied
        notes: Additional notes
    """

    __tablename__ = "storage_cells"
    __validated_fields__: ClassVar[Set[str]] = {"storage_id"}

    # Relationships
    storage_id = Column(String(36), ForeignKey("storage_locations.id"), nullable=False)

    # Cell information (JSON stored as TEXT)
    _position = Column("position", Text)  # {"row": 1, "column": 2, "level": 3}

    # Updated: Proper foreign key to DynamicMaterial instead of generic item
    material_id = Column(Integer, ForeignKey("dynamic_materials.id", ondelete="SET NULL"))
    occupied = Column(Boolean, default=False)
    notes = Column(String(255))

    # Relationships
    location = relationship("StorageLocation", back_populates="cells")
    material = relationship("DynamicMaterial", back_populates="storage_cells")

    # JSON property handler
    @property
    def position(self):
        if self._position:
            try:
                return json.loads(self._position)
            except:
                return {}
        return {}

    @position.setter
    def position(self, value):
        if value is not None:
            self._position = json.dumps(value)
        else:
            self._position = None

    @hybrid_property
    def label(self) -> str:
        """
        Generate a human-readable cell label.

        Returns:
            Human-readable cell label based on position
        """
        if not self.position:
            return f"Cell {self.id}"

        pos = self.position

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

        return f"Cell {self.id}"

    def assign_material(self, material_id: int) -> None:
        """
        Assign a material to this cell.

        Args:
            material_id: ID of the material

        Raises:
            ValueError: If cell is already occupied
        """
        if self.occupied:
            raise ValueError(f"Cell {self.label} is already occupied")

        self.material_id = material_id
        self.occupied = True

        # Update parent storage location
        if self.location and hasattr(self.location, "add_item"):
            self.location.add_item(1)

    def clear(self) -> None:
        """
        Clear this cell.
        """
        was_occupied = self.occupied

        self.material_id = None
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

        # Add calculated properties
        result["label"] = self.label
        result["position"] = self.position

        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageCell."""
        return f"<StorageCell(id={self.id}, storage_id={self.storage_id}, occupied={self.occupied})>"


class StorageAssignment(AbstractBase, ValidationMixin, TimestampMixin):
    """
    StorageAssignment model for tracking material placements.
    Updated to use proper foreign key relationships with DynamicMaterial.

    Attributes:
        material_id: ID of the assigned material (FK to DynamicMaterial)
        storage_id: ID of the storage location
        position: Position information
        quantity: Assigned quantity
        assigned_date: Date of assignment
        assigned_by: Person who made the assignment
        notes: Additional notes
    """

    __tablename__ = "storage_assignments"
    __validated_fields__: ClassVar[Set[str]] = {"material_id", "storage_id", "quantity"}

    # Material information - Updated with proper foreign key
    material_id = Column(Integer, ForeignKey("dynamic_materials.id", ondelete="CASCADE"), nullable=False)

    # Storage information
    storage_id = Column(String(36), ForeignKey("storage_locations.id"), nullable=False)
    _position = Column("position", Text)  # JSON stored as TEXT

    # Assignment details
    quantity = Column(Float, nullable=False)
    assigned_date = Column(String(50))  # ISO date string
    assigned_by = Column(String(100))
    notes = Column(String(255))

    # Relationships
    material = relationship("DynamicMaterial", back_populates="storage_assignments")
    location = relationship("StorageLocation", back_populates="assignments")

    # JSON property handler
    @property
    def position(self):
        if self._position:
            try:
                return json.loads(self._position)
            except:
                return {}
        return {}

    @position.setter
    def position(self, value):
        if value is not None:
            self._position = json.dumps(value)
        else:
            self._position = None

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

    @hybrid_property
    def material_type_name(self) -> Optional[str]:
        """Get the material type name through the relationship."""
        if self.material and self.material.material_type:
            return self.material.material_type.name
        return None

    @hybrid_property
    def material_name(self) -> Optional[str]:
        """Get the material name through the relationship."""
        return self.material.name if self.material else None

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
        result["position"] = self.position
        return result

    def __repr__(self) -> str:
        """Return string representation of the StorageAssignment."""
        return f"<StorageAssignment(id={self.id}, material_id={self.material_id}, storage_id={self.storage_id}, quantity={self.quantity})>"


class StorageMove(AbstractBase, ValidationMixin, TimestampMixin):
    """
    StorageMove model for tracking material movements.
    Updated to use proper foreign key relationships with DynamicMaterial.

    Attributes:
        material_id: ID of the moved material (FK to DynamicMaterial)
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

    # Material information - Updated with proper foreign key
    material_id = Column(Integer, ForeignKey("dynamic_materials.id", ondelete="CASCADE"), nullable=False)

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
    material = relationship("DynamicMaterial", back_populates="storage_moves")
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

    @hybrid_property
    def material_type_name(self) -> Optional[str]:
        """Get the material type name through the relationship."""
        if self.material and self.material.material_type:
            return self.material.material_type.name
        return None

    @hybrid_property
    def material_name(self) -> Optional[str]:
        """Get the material name through the relationship."""
        return self.material.name if self.material else None

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
                    StorageAssignment.storage_id == self.to_storage_id,
                )
            )
            .first()
        )

        if not dest_assignment:
            dest_assignment = StorageAssignment(
                material_id=self.material_id,
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