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

# Removed uuid import as it was only used by the removed table
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Dict, List, Optional, Set

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    # Removed Table import as it's no longer used here
    # Removed UniqueConstraint import as it was only used by the removed table
    and_,
)
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
    MaterialType,
    MeasurementUnit,
    SkillLevel # Added SkillLevel if needed by other imports, check usage
)

# --- REMOVED Association Table Definition ---
# The documentation_category_assignment table definition was removed from here.
# It should be defined only once, likely in the file containing the
# DocumentationCategory and DocumentationResource models.


class Material(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Base Material model for inventory items.

    Attributes:
        id: Primary key.
        name: Name of the material.
        material_type: Discriminator for subtypes (leather, hardware, supplies).
        status: Current inventory status (e.g., IN_STOCK).
        quantity: Current quantity on hand.
        unit: Unit of measurement (e.g., SQUARE_FOOT, PIECE).
        quality: Quality grade (e.g., STANDARD, PREMIUM).
        supplier_id: Foreign key to the Supplier.
        supplier: Denormalized supplier name.
        sku: Stock Keeping Unit identifier.
        description: Detailed description of the material.
        reorder_point: Quantity level at which to reorder.
        supplier_sku: Supplier's SKU for this material.
        cost_price: The purchase cost per unit (from CostingMixin).
        price: The selling price per unit.
        last_purchased: Date of the last purchase (consider DateTime).
        storage_location: Primary storage location identifier.
        notes: Additional notes about the material.
        thumbnail: URL or path to a thumbnail image.
    """

    __tablename__ = "materials"
    __validated_fields__: ClassVar[Set[str]] = {"name", "quantity", "reorder_point", "price"} # Added price

    # --- Primary Key ---
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
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier = Column(String(255)) # Denormalized name
    sku = Column(String(100), index=True)
    description = Column(Text)

    # Inventory management
    reorder_point = Column(Float, default=0)
    supplier_sku = Column(String(100))

    # --- Pricing ---
    # cost_price is inherited from CostingMixin
    price = Column(Float, default=0.0) # Selling price per unit

    # --- Other ---
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
    component_materials = relationship("ComponentMaterial", back_populates="material")
    supplier_rel = relationship("Supplier", back_populates="materials")
    picking_list_items = relationship(
        "PickingListItem", back_populates="material", cascade="save-update, merge"
    )
    # Assuming Inventory model exists and relationship is needed
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='material', foreign(Inventory.item_id)==Material.id)",
        back_populates="material",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
        passive_deletes=True,
        # overlaps="inventory", # Removed overlaps if causing issues, check necessity
    )
    # --- End Relationships ---


    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """Validate quantity and update status based on reorder point."""
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        reorder_point = self.reorder_point if self.reorder_point is not None else 0.0
        if quantity <= 0: self.status = InventoryStatus.OUT_OF_STOCK
        elif quantity <= reorder_point: self.status = InventoryStatus.LOW_STOCK
        else: self.status = InventoryStatus.IN_STOCK
        return quantity

    @validates("reorder_point")
    def validate_reorder_point(self, key: str, value: float) -> float:
        """Validate reorder point (cannot be negative)."""
        if value < 0: raise ValueError("Reorder point cannot be negative")
        return value

    @validates("price")
    def validate_price(self, key: str, value: float) -> float:
        """Validate selling price (cannot be negative)."""
        if value < 0: raise ValueError("Selling price cannot be negative")
        return value

    @hybrid_property
    def value(self) -> Optional[float]:
        """Calculate the total cost value of this material in inventory."""
        # Ensure cost_price exists and is not None before calculation
        cost_price = getattr(self, "cost_price", None)
        if cost_price is None: return None
        # Ensure quantity is not None
        quantity = self.quantity if self.quantity is not None else 0.0
        return quantity * cost_price

    @hybrid_property
    def total_selling_value(self) -> Optional[float]:
        """Calculate the total selling value of this material in inventory."""
        if self.price is None: return None
        # Ensure quantity is not None
        quantity = self.quantity if self.quantity is not None else 0.0
        return quantity * self.price

    def to_dict(self) -> Dict[str, Any]:
        """Convert Material instance to a dictionary."""
        result = super().to_dict() # Assumes base class has a to_dict
        if self.status: result["status"] = self.status.name
        if self.unit: result["unit"] = self.unit.name
        if self.quality: result["quality"] = self.quality.name
        result["value"] = self.value
        result["total_selling_value"] = self.total_selling_value
        inv_record = self.inventory
        if inv_record:
             result["inventory_quantity"] = inv_record.quantity
             result["inventory_status"] = inv_record.status.name if inv_record.status else None
             # Prefer inventory's storage location if available
             result["storage_location"] = inv_record.storage_location or self.storage_location
        else:
             result["storage_location"] = self.storage_location # Fallback to material's field
        return result

    def __repr__(self) -> str:
        """Return string representation of the Material."""
        return f"<Material(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.material_type}', quantity={self.quantity})>"


# --- Subclasses ---

class LeatherMaterial(Material):
    """Specialized Material model for leather inventory."""
    __mapper_args__ = {"polymorphic_identity": "leather"}
    leather_type = Column(Enum(LeatherType))
    tannage = Column(String(50))
    animal_source = Column(String(50))
    thickness = Column(Float)
    area = Column(Float)
    is_full_hide = Column(Boolean, default=False)
    color = Column(String(50))
    finish = Column(Enum(LeatherFinish))
    grade = Column(String(20))
    def __repr__(self) -> str:
        return f"<LeatherMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.leather_type.name if self.leather_type else None}', thickness={self.thickness})>"

class HardwareMaterial(Material):
    """Specialized Material model for hardware inventory."""
    __mapper_args__ = {"polymorphic_identity": "hardware"}
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
