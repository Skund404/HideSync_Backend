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

from typing import Optional, List, Dict, Any, ClassVar, Set
from decimal import Decimal

from sqlalchemy import Column, String, Text, Float, Enum, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import (
    AbstractBase,
    ValidationMixin,
    CostingMixin,
    TimestampMixin,
)
from app.db.models.enums import (
    MaterialType,
    MaterialQualityGrade,
    InventoryStatus,
    LeatherType,
    LeatherFinish,
    HardwareType,
    HardwareMaterial as HardwareMaterialEnum,
    HardwareFinish,
    MeasurementUnit,
)


class Material(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Base Material model for inventory items.

    This class represents all materials used in leatherworking projects,
    with common attributes shared across all material types. It uses
    SQLAlchemy's single-table inheritance to support specialized material types.

    Attributes:
        name: Material name/description
        material_type: Type discriminator for inheritance
        status: Current inventory status
        quantity: Current quantity in stock
        unit: Unit of measurement
        quality: Quality grade
        supplier_id: Reference to supplier
        supplier: Name of the supplier (denormalized for convenience)
        sku: Stock keeping unit (internal)
        description: Detailed description
        reorder_point: Quantity threshold for reordering
        supplier_sku: Supplier's SKU for this material
        last_purchased: Date last purchased
        storage_location: Storage location identifier
        notes: Additional notes
    """

    __tablename__ = "materials"
    __validated_fields__: ClassVar[Set[str]] = {"name", "quantity", "reorder_point"}

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
    last_purchased = Column(String(50))  # ISO date string
    storage_location = Column(String(100))
    notes = Column(Text)
    thumbnail = Column(String(255))  # URL or path to thumbnail image

    # Inheritance configuration
    __mapper_args__ = {
        "polymorphic_on": material_type,
        "polymorphic_identity": "material",
    }

    # Relationships
    component_materials = relationship("ComponentMaterial", back_populates="material")
    supplier_rel = relationship("Supplier", back_populates="materials")
    picking_list_items = relationship(
        "PickingListItem", back_populates="material", cascade="all, delete-orphan"
    )

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
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
        """
        Validate and update quantity, updating status if needed.

        Args:
            key: Field name ('quantity')
            quantity: New quantity value

        Returns:
            Validated quantity
        """
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        # Update status based on quantity
        if quantity <= 0:
            self.status = InventoryStatus.OUT_OF_STOCK
        elif quantity <= self.reorder_point:
            self.status = InventoryStatus.LOW_STOCK
        else:
            self.status = InventoryStatus.IN_STOCK

        return quantity

    @validates("reorder_point")
    def validate_reorder_point(self, key: str, value: float) -> float:
        """
        Validate reorder point.

        Args:
            key: Field name ('reorder_point')
            value: New reorder point value

        Returns:
            Validated reorder point
        """
        if value < 0:
            raise ValueError("Reorder point cannot be negative")
        return value

    @hybrid_property
    def value(self) -> Optional[float]:
        """
        Calculate the total value of this material in inventory.

        Returns:
            Total value (quantity * cost_price) or None if cost_price is not set
        """
        if self.cost_price is None:
            return None
        return self.quantity * self.cost_price

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Material instance to a dictionary.

        Returns:
            Dictionary representation of the material
        """
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

        return result

    def __repr__(self) -> str:
        """Return string representation of the Material."""
        return f"<Material(id={self.id}, name='{self.name}', type='{self.material_type}', quantity={self.quantity})>"


class LeatherMaterial(Material):
    """
    Specialized Material model for leather inventory.

    This class extends the base Material model with leather-specific attributes.

    Attributes:
        leather_type: Type of leather
        tannage: Tanning method
        animal_source: Animal source
        thickness: Thickness in mm
        area: Area in square feet/meters
        is_full_hide: Whether this is a full hide
        color: Color description
        finish: Finish type
        grade: Quality grade
    """

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
        """Return string representation of the LeatherMaterial."""
        return f"<LeatherMaterial(id={self.id}, name='{self.name}', type='{self.leather_type.name if self.leather_type else None}', thickness={self.thickness})>"


class HardwareMaterial(Material):
    """
    Specialized Material model for hardware inventory.

    This class extends the base Material model with hardware-specific attributes.

    Attributes:
        hardware_type: Type of hardware
        hardware_material: Material the hardware is made of
        hardware_finish: Finish type
        size: Size specification
        hardware_color: Color description
    """

    __mapper_args__ = {"polymorphic_identity": "hardware"}

    # Hardware-specific attributes
    hardware_type = Column(Enum(HardwareType))
    hardware_material = Column(Enum(HardwareMaterialEnum))
    hardware_finish = Column(Enum(HardwareFinish))
    size = Column(String(50))
    hardware_color = Column(String(50))

    def __repr__(self) -> str:
        """Return string representation of the HardwareMaterial."""
        return f"<HardwareMaterial(id={self.id}, name='{self.name}', type='{self.hardware_type.name if self.hardware_type else None}')>"


class SuppliesMaterial(Material):
    """
    Specialized Material model for supplies inventory.

    This class extends the base Material model with supplies-specific attributes.

    Attributes:
        supplies_material_type: Type of supply material
        supplies_color: Color description
        thread_thickness: Thread thickness (for thread)
        material_composition: Material composition description
        volume: Volume (for liquids)
        length: Length (for thread, cord, etc.)
        drying_time: Drying time (for adhesives, dyes, etc.)
        application_method: Application method
        supplies_finish: Finish type
    """

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
        """Return string representation of the SuppliesMaterial."""
        return f"<SuppliesMaterial(id={self.id}, name='{self.name}', type='{self.supplies_material_type}')>"
