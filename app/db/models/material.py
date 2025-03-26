# File: app/db/models/material.py
"""
Material models for the Leathercraft ERP system.

This module defines the Material model and its specialized subtypes:
- LeatherMaterial: For leather inventory
- HardwareMaterial: For hardware components like buckles, rivets, etc.
- SuppliesMaterial: For other supplies like thread, dye, etc.

The models use SQLAlchemy's single-table inheritance to represent the
different material types, with a discriminator column to identify the type.
"""

from __future__ import annotations  # Allows type hinting models defined later

from decimal import Decimal
from typing import Any, ClassVar, Dict, List, Optional, Set

from sqlalchemy import (
    JSON,  # Added JSON if needed by base classes
    Boolean,
    Column,
    DateTime,  # Added DateTime if needed by base classes
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,  # <<< Added import
)
# <<< Added imports
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import foreign, relationship, validates

# Assuming these base classes and enums are correctly defined elsewhere
from app.db.models.base import (
    AbstractBase,
    CostingMixin,
    TimestampMixin,
    ValidationMixin,
)
from app.db.models.enums import (
    HardwareFinish,
    HardwareMaterial as HardwareMaterialEnum,
    HardwareType,
    InventoryStatus,
    LeatherFinish,
    LeatherType,
    MaterialQualityGrade,
    MaterialType,  # Assuming MaterialType is defined if needed
    MeasurementUnit,
)


# Forward declarations if needed
# class Inventory: pass
# class Supplier: pass
# class ComponentMaterial: pass
# class PickingListItem: pass


class Material(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Base Material model for inventory items.
    ... (rest of docstring) ...
    """

    __tablename__ = "materials"
    __validated_fields__: ClassVar[Set[str]] = {"name", "quantity", "reorder_point"}

    # --- Primary Key ---
    # IMPORTANT: Ensure Integer matches Inventory.item_id type
    id = Column(Integer, primary_key=True)

    # Basic information
    name = Column(String(255), nullable=False)
    material_type = Column(String(50), nullable=False)  # Discriminator column

    # Inventory information
    status = Column(Enum(InventoryStatus), default=InventoryStatus.IN_STOCK)
    quantity = Column(Float, default=0)
    unit = Column(Enum(MeasurementUnit), nullable=False)
    quality = Column(Enum(MaterialQualityGrade), default=MaterialQualityGrade.STANDARD)

    # Supplier information
    # Ensure Integer matches Supplier.id type
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier = Column(String(255)) # Denormalized name
    sku = Column(String(100), index=True)
    description = Column(Text)

    # Inventory management
    reorder_point = Column(Float, default=0)
    supplier_sku = Column(String(100))
    last_purchased = Column(String(50))  # Consider using DateTime type
    storage_location = Column(String(100))
    notes = Column(Text)
    thumbnail = Column(String(255))  # URL or path to thumbnail image

    # Inheritance configuration
    __mapper_args__ = {
        "polymorphic_on": material_type,
        "polymorphic_identity": "material", # Base identity
    }

    # --- RELATIONSHIPS ---

    # Relationship to ComponentMaterial (One-to-Many)
    component_materials = relationship("ComponentMaterial", back_populates="material")

    # Relationship to Supplier (Many-to-One)
    supplier_rel = relationship("Supplier", back_populates="materials")

    # Relationship to PickingListItem (One-to-Many)
    picking_list_items = relationship(
        "PickingListItem", back_populates="material", cascade="save-update, merge" # Avoid deleting items if material deleted
    )

    # --- ADD THIS RELATIONSHIP ---
    # One-to-One relationship TO Inventory
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='material', foreign(Inventory.item_id)==Material.id)",
        back_populates="material",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
        passive_deletes=True,
        overlaps="inventory",  # <<< ADD THIS
    )
    # --- END ADDED RELATIONSHIP ---

    # --- End Relationships ---


    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """Validate quantity and update status based on reorder point."""
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        # Use a default value if reorder_point is None
        reorder_point = self.reorder_point if self.reorder_point is not None else 0.0

        if quantity <= 0:
            self.status = InventoryStatus.OUT_OF_STOCK
        elif quantity <= reorder_point:
            self.status = InventoryStatus.LOW_STOCK
        else:
            self.status = InventoryStatus.IN_STOCK

        return quantity

    @validates("reorder_point")
    def validate_reorder_point(self, key: str, value: float) -> float:
        """Validate reorder point (cannot be negative)."""
        if value < 0:
            raise ValueError("Reorder point cannot be negative")
        return value

    @hybrid_property
    def value(self) -> Optional[float]:
        """Calculate the total value of this material in inventory."""
        # Assumes CostingMixin provides self.cost_price
        if not hasattr(self, "cost_price") or self.cost_price is None:
            return None
        return self.quantity * self.cost_price

    def to_dict(self) -> Dict[str, Any]:
        """Convert Material instance to a dictionary."""
        result = super().to_dict()

        # Convert enum values to strings for serialization
        if self.status:
            result["status"] = self.status.name
        if self.unit:
            result["unit"] = self.unit.name
        if self.quality:
            result["quality"] = self.quality.name

        # Add calculated properties
        result["value"] = self.value

        # Add inventory specific details if needed (pulled via relationship)
        inv_record = self.inventory
        if inv_record:
             result["inventory_quantity"] = inv_record.quantity # Example
             result["inventory_status"] = inv_record.status.name if inv_record.status else None # Example
             result["storage_location"] = inv_record.storage_location # Example

        return result

    def __repr__(self) -> str:
        """Return string representation of the Material."""
        # Use self.id which should be populated after flush/commit
        return f"<Material(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.material_type}', quantity={self.quantity})>"


# --- Subclasses remain the same, inheriting the new 'inventory' relationship ---

class LeatherMaterial(Material):
    """Specialized Material model for leather inventory."""
    __mapper_args__ = {"polymorphic_identity": "leather"}

    # Leather-specific attributes
    leather_type = Column(Enum(LeatherType))
    tannage = Column(String(50))
    animal_source = Column(String(50))
    thickness = Column(Float)  # in mm
    area = Column(Float)  # in square feet/meters
    is_full_hide = Column(Boolean, default=False)
    color = Column(String(50))
    finish = Column(Enum(LeatherFinish))
    grade = Column(String(20))

    def __repr__(self) -> str:
        return f"<LeatherMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.leather_type.name if self.leather_type else None}', thickness={self.thickness})>"


class HardwareMaterial(Material):
    """Specialized Material model for hardware inventory."""
    __mapper_args__ = {"polymorphic_identity": "hardware"}

    # Hardware-specific attributes
    hardware_type = Column(Enum(HardwareType))
    hardware_material = Column(Enum(HardwareMaterialEnum))
    hardware_finish = Column(Enum(HardwareFinish))
    size = Column(String(50))
    hardware_color = Column(String(50))

    def __repr__(self) -> str:
        return f"<HardwareMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.hardware_type.name if self.hardware_type else None}')>"


class SuppliesMaterial(Material):
    """Specialized Material model for supplies inventory."""
    __mapper_args__ = {"polymorphic_identity": "supplies"}

    # Supplies-specific attributes
    supplies_material_type = Column(String(50))
    supplies_color = Column(String(50))
    thread_thickness = Column(String(50))
    material_composition = Column(String(100))
    volume = Column(Float)
    length = Column(Float)
    drying_time = Column(String(50))
    application_method = Column(String(100))
    supplies_finish = Column(String(50))

    def __repr__(self) -> str:
        return f"<SuppliesMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.supplies_material_type}')>"

