# File: app/db/models/inventory.py
"""
Inventory, InventoryTransaction, and Product models for the ERP system.

Defines models for tracking stock levels (Inventory), recording stock movements
(InventoryTransaction), and managing finished goods (Product), including their
relationships as per the system's ER diagram.
"""

from __future__ import annotations  # Allows type hinting models defined later

from datetime import datetime
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

# Assuming these base classes and enums are correctly defined elsewhere
from app.db.models.base import (
    AbstractBase,
    CostingMixin,
    TimestampMixin,
    ValidationMixin,
)
from app.db.models.enums import (
    InventoryAdjustmentType,
    InventoryStatus,
    MeasurementUnit,  # Assuming MeasurementUnit is defined if needed
    ProjectType,
    TransactionType,
)


# Forward declaration for type hinting if models are in the same file
# class Material: pass
# class Tool: pass
# class Pattern: pass
# class Project: pass
# class SaleItem: pass
# class Sale: pass
# class Purchase: pass


class Inventory(AbstractBase, ValidationMixin):
    """
    Inventory model tracking stock levels (one-to-one with item).

    This table uses polymorphism (item_type, item_id) to link to Product,
    Material, or Tool records, representing the single inventory entry
    for that specific item.

    Attributes:
        item_type: Discriminator ('product', 'material', 'tool').
        item_id: FK value pointing to Product.id, Material.id, or Tool.id.
        quantity: Current quantity in stock.
        status: Current inventory status (e.g., IN_STOCK, LOW_STOCK).
        storage_location: Physical location identifier.
    """

    __tablename__ = "inventory"
    __validated_fields__: ClassVar[Set[str]] = {"quantity"}

    # Polymorphic Key - links this record to ONE Product, Material, or Tool
    item_type = Column(String(50), nullable=False, index=True)
    # IMPORTANT: Ensure Integer matches the PK type of Product, Material, Tool
    item_id = Column(Integer, nullable=False, index=True)

    # Stock Details
    quantity = Column(Float, default=0)
    status = Column(Enum(InventoryStatus), default=InventoryStatus.IN_STOCK)
    storage_location = Column(String(100))

    # --- RELATIONSHIPS (Back-references for the polymorphic one-to-one) ---
    # These allow navigating from an Inventory record back to the specific
    # Product, Material, or Tool it represents.

    product = relationship(
        "Product",
        primaryjoin="and_(Inventory.item_type=='product', foreign(Inventory.item_id)==Product.id)",
        back_populates="inventory",  # Links to Product.inventory
        uselist=False,
        viewonly=True,  # Recommended for polymorphic backrefs
        lazy="joined",
    )

    material = relationship(
        "Material",
        primaryjoin="and_(Inventory.item_type=='material', foreign(Inventory.item_id)==Material.id)",
        back_populates="inventory",  # Assumes Material model has 'inventory'
        uselist=False,
        viewonly=True,
        lazy="joined",
    )

    tool = relationship(
        "Tool",
        primaryjoin="and_(Inventory.item_type=='tool', foreign(Inventory.item_id)==Tool.id)",
        back_populates="inventory",  # Assumes Tool model has 'inventory'
        uselist=False,
        viewonly=True,
        lazy="joined",
    )

    # --- End Relationships ---

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """Validate quantity and update status."""
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        # Determine reorder point from the related item, if possible
        reorder_point = 0
        related_item = self.product or self.material or self.tool
        if related_item and hasattr(related_item, "reorder_point"):
            reorder_point = getattr(related_item, "reorder_point", 0) or 0

        # Update status based on quantity and reorder point
        if quantity <= 0:
            self.status = InventoryStatus.OUT_OF_STOCK
        elif quantity <= reorder_point:
            self.status = InventoryStatus.LOW_STOCK
        else:
            self.status = InventoryStatus.IN_STOCK

        return quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert Inventory instance to a dictionary."""
        result = super().to_dict()
        if self.status:
            result["status"] = self.status.name
        # Add related item info if needed, e.g.:
        # item = self.product or self.material or self.tool
        # result["item_name"] = item.name if item else "N/A"
        return result

    def __repr__(self) -> str:
        """Return string representation of the Inventory item."""
        return f"<Inventory(id={self.id}, item_type='{self.item_type}', item_id={self.item_id}, quantity={self.quantity})>"


class InventoryTransaction(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Tracks stock movements and adjustments for inventory items.

    Records additions (e.g., purchases, production) and reductions (e.g., sales,
    usage, adjustments) to inventory quantities, providing an audit trail.
    """

    __tablename__ = "inventory_transactions"
    __validated_fields__: ClassVar[Set[str]] = {"quantity"}

    # Item identification (references the item whose stock changed)
    item_type = Column(String(50), nullable=False, index=True)
    # IMPORTANT: Ensure Integer matches PK type of Product/Material/Tool
    item_id = Column(Integer, nullable=False, index=True)

    # Transaction details
    quantity = Column(
        Float, nullable=False, comment="Positive for increase, negative for decrease"
    )
    transaction_type = Column(Enum(TransactionType), nullable=False)
    adjustment_type = Column(Enum(InventoryAdjustmentType), nullable=True)

    # Related entities (Context for the transaction)
    # Ensure Integer matches PK type of Project, Sale, Purchase
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)

    # Location information (For transfers or location-specific adjustments)
    from_location = Column(String(100), nullable=True)
    to_location = Column(String(100), nullable=True)

    # Audit information
    performed_by = Column(String(100), nullable=True)  # User ID or name
    notes = Column(Text, nullable=True)
    transaction_date = Column(DateTime, default=datetime.now)

    # Relationships (Simple FK lookups)
    # No back_populates needed unless Project/Sale/Purchase need lists of transactions
    project = relationship("Project", foreign_keys=[project_id])
    sale = relationship("Sale", foreign_keys=[sale_id])
    purchase = relationship("Purchase", foreign_keys=[purchase_id])

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """Validate transaction quantity (cannot be zero)."""
        if quantity == 0:
            raise ValueError("Transaction quantity cannot be zero")
        return quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert InventoryTransaction instance to a dictionary."""
        result = super().to_dict()
        if self.transaction_type:
            result["transaction_type"] = self.transaction_type.name
        if self.adjustment_type:
            result["adjustment_type"] = self.adjustment_type.name
        return result

    def __repr__(self) -> str:
        """Return string representation of the InventoryTransaction."""
        return f"<InventoryTransaction(id={self.id}, type='{self.transaction_type}', item_type='{self.item_type}', item_id={self.item_id}, quantity={self.quantity})>"
