# File: app/db/models/material.py
"""
Material models for the Leathercraft ERP system.

This module defines the Material model and its specialized subtypes:
- LeatherMaterial: For leather inventory
- HardwareMaterial: For hardware components like buckles, rivets, etc.
- SuppliesMaterial: For other supplies like thread, dye, etc.
- WoodMaterial: For wood inventory

The models use SQLAlchemy's single-table inheritance to represent the
different material types, with a discriminator column to identify the type.
"""

from __future__ import annotations

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
    and_,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import foreign, relationship, validates

from app.db.models.base import (
    AbstractBase,
    CostingMixin,
    TimestampMixin,
    ValidationMixin,
)
from app.db.models.enums import (
    HardwareFinish,
    HardwareMaterialEnum,
    HardwareType,
    InventoryStatus,
    LeatherFinish,
    LeatherType,
    MaterialQualityGrade,
    MaterialType,
    MeasurementUnit,
    SkillLevel,
    WoodType,
    WoodGrain,
    WoodFinish,
)


class Material(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Base Material model for inventory items.

    Attributes:
        id: Primary key.
        name: Name of the material.
        material_type: Discriminator for subtypes (leather, hardware, supplies, wood).
        ... (see below for all fields)
    """

    __tablename__ = "materials"
    __validated_fields__: ClassVar[Set[str]] = {
        "name",
        "quantity",
        "reorder_point",
        "price",
    }

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
    supplier = Column(String(255))
    sku = Column(String(100), index=True)
    description = Column(Text)

    # Inventory management
    reorder_point = Column(Float, default=0)
    supplier_sku = Column(String(100))

    # --- Pricing ---
    price = Column(Float, default=0.0)  # Selling price per unit

    # --- Other ---
    last_purchased = Column(String(50))
    storage_location = Column(String(100))
    notes = Column(Text)
    thumbnail = Column(String(255))

    # --- Leather-specific fields ---
    leather_type = Column(Enum(LeatherType), nullable=True)
    tannage = Column(String(50), nullable=True)
    animal_source = Column(String(50), nullable=True)
    leather_thickness = Column(Float, nullable=True)
    area = Column(Float, nullable=True)
    is_full_hide = Column(Boolean, default=False)
    leather_color = Column(String(50), nullable=True)
    leather_finish = Column(Enum(LeatherFinish), nullable=True)
    leather_grade = Column(String(20), nullable=True)

    # --- Hardware-specific fields ---
    hardware_type = Column(Enum(HardwareType), nullable=True)
    hardware_material = Column(Enum(HardwareMaterialEnum), nullable=True)
    hardware_finish = Column(Enum(HardwareFinish), nullable=True)
    hardware_size = Column(String(50), nullable=True)
    hardware_color = Column(String(50), nullable=True)

    # --- Supplies-specific fields ---
    supplies_material_type = Column(String(50), nullable=True)
    supplies_color = Column(String(50), nullable=True)
    thread_thickness = Column(String(50), nullable=True)
    material_composition = Column(String(100), nullable=True)
    volume = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    drying_time = Column(String(50), nullable=True)
    application_method = Column(String(100), nullable=True)
    supplies_finish = Column(String(50), nullable=True)

    # --- Wood-specific fields ---
    wood_type = Column(Enum(WoodType), nullable=True)
    wood_grain = Column(Enum(WoodGrain), nullable=True)
    wood_finish = Column(Enum(WoodFinish), nullable=True)
    wood_color = Column(String(50), nullable=True)
    thickness = Column(Float, nullable=True)  # Used for wood, leather, etc.
    width = Column(Float, nullable=True)
    # length is already defined above

    # Inheritance configuration
    __mapper_args__ = {
        "polymorphic_on": material_type,
        "polymorphic_identity": "material",
    }

    # --- RELATIONSHIPS ---
    component_materials = relationship("ComponentMaterial", back_populates="material")
    supplier_rel = relationship("Supplier", back_populates="materials")
    picking_list_items = relationship(
        "PickingListItem", back_populates="material", cascade="save-update, merge"
    )
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='material', foreign(Inventory.item_id)==Material.id)",
        back_populates="material",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
        passive_deletes=True,
    )

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        reorder_point = self.reorder_point if self.reorder_point is not None else 0.0
        if quantity <= 0:
            self.status = InventoryStatus.OUT_OF_STOCK
        elif quantity <= reorder_point:
            self.status = InventoryStatus.LOW_STOCK
        else:
            self.status = InventoryStatus.IN_STOCK
        return quantity

    @validates("reorder_point")
    def validate_reorder_point(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value < 0:
            raise ValueError("Reorder point cannot be negative")
        return value

    @validates("price")
    def validate_price(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value < 0:
            raise ValueError("Selling price cannot be negative")
        return value

    @hybrid_property
    def value(self) -> Optional[float]:
        cost_price = getattr(self, "cost_price", None)
        if cost_price is None:
            return None
        quantity = self.quantity if self.quantity is not None else 0.0
        return quantity * cost_price

    @hybrid_property
    def total_selling_value(self) -> Optional[float]:
        if self.price is None:
            return None
        quantity = self.quantity if self.quantity is not None else 0.0
        return quantity * self.price

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if hasattr(super(), "to_dict"):
            result = super().to_dict()
        else:
            for c in self.__table__.columns:
                result[c.name] = getattr(self, c.name)
        if self.status:
            result["status"] = self.status.name
        if self.unit:
            result["unit"] = self.unit.name
        if self.quality:
            result["quality"] = self.quality.name
        result["value"] = self.value
        result["total_selling_value"] = self.total_selling_value
        inv_record = self.inventory
        if inv_record:
            result["inventory_quantity"] = inv_record.quantity
            result["inventory_status"] = (
                inv_record.status.name if inv_record.status else None
            )
            result["storage_location"] = (
                    inv_record.storage_location or self.storage_location
            )
        else:
            result["storage_location"] = self.storage_location
            result["inventory_quantity"] = None
            result["inventory_status"] = None
        return result

    def __repr__(self) -> str:
        return (
            f"<Material(id={getattr(self, 'id', None)}, name='{self.name}', "
            f"type='{self.material_type}', quantity={self.quantity}, "
            f"wood_type={self.wood_type}, leather_type={self.leather_type}, "
            f"hardware_type={self.hardware_type})>"
        )


# --- Subclasses (no columns, just identity and optional __repr__) ---

class LeatherMaterial(Material):
    __mapper_args__ = {"polymorphic_identity": "leather"}

    def __repr__(self) -> str:
        return f"<LeatherMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.leather_type}', thickness={self.leather_thickness})>"


class HardwareMaterial(Material):
    __mapper_args__ = {"polymorphic_identity": "hardware"}

    def __repr__(self) -> str:
        return f"<HardwareMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.hardware_type}')>"


class SuppliesMaterial(Material):
    __mapper_args__ = {"polymorphic_identity": "supplies"}

    def __repr__(self) -> str:
        return f"<SuppliesMaterial(id={getattr(self, 'id', None)}, name='{self.name}', type='{self.supplies_material_type}')>"


class WoodMaterial(Material):
    """
    Wood material subclass.

    This class represents wood materials in the inventory system.
    All wood-specific fields are defined in the base Material class.
    """
    __mapper_args__ = {"polymorphic_identity": "wood"}

    def __repr__(self) -> str:
        return (
            f"<WoodMaterial(id={getattr(self, 'id', None)}, name='{self.name}', "
            f"wood_type='{self.wood_type}', grain='{self.wood_grain}', "
            f"thickness={self.thickness}, length={self.length}, width={self.width}, "
            f"finish='{self.wood_finish}', color='{self.wood_color}')>"
        )