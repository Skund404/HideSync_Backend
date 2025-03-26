# File: app/db/models/product.py
"""
Defines the Product model for the ERP system.
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
    and_,  # <<< Added import
)
from sqlalchemy.ext.hybrid import hybrid_property
# <<< Added imports
from sqlalchemy.orm import foreign, relationship, validates

# Assuming these base classes and enums are correctly defined elsewhere
from app.db.models.base import (
    AbstractBase,
    CostingMixin,
    TimestampMixin,
    ValidationMixin,
)
from app.db.models.enums import (
    InventoryStatus,  # Keep if used for default/fallback
    ProjectType,
)


# Forward declaration for type hinting if models are in the same file or circular imports
# class Inventory: pass
# class Pattern: pass
# class Project: pass
# class SaleItem: pass


class Product(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Represents finished products available for sale or use in projects.

    Contains descriptive information, pricing, links to patterns/projects,
    and crucially, a one-to-one relationship to its Inventory record for
    stock tracking.
    """

    __tablename__ = "products"

    # --- Primary Key ---
    # IMPORTANT: Ensure Integer matches Inventory.item_id type
    id = Column(Integer, primary_key=True)

    # --- Foreign Keys (as per ER Diagram) ---
    # Ensure Integer matches PK type of Pattern and Project
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    # --- Basic Product Information ---
    name = Column(String(255), nullable=False)
    product_type = Column(Enum(ProjectType), nullable=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # --- Attributes ---
    materials = Column(JSON, nullable=True, comment="List of material IDs or details")
    color = Column(String(50), nullable=True)
    dimensions = Column(String(100), nullable=True)
    weight = Column(Float, nullable=True)
    thumbnail = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    batch_number = Column(String(50), nullable=True)
    customizations = Column(JSON, nullable=True)

    # --- Inventory Control Characteristic ---
    # Reorder point is a property of the product itself
    reorder_point = Column(Integer, nullable=True, default=0)

    # --- Pricing ---
    cost_breakdown = Column(JSON, nullable=True)
    total_cost = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)

    # --- Sales Metrics ---
    last_sold = Column(DateTime, nullable=True)
    sales_velocity = Column(Float, nullable=True)

    # --- RELATIONSHIPS (Matching ER Diagram) ---

    # One-to-One relationship TO Inventory (Product owns its Inventory record)
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='product', foreign(Inventory.item_id)==Product.id)",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
        passive_deletes=True,
        overlaps="inventory",  # <<< ADD THIS
    )

    # Many-to-One relationship FROM Product TO Pattern
    pattern = relationship(
        "Pattern",
        back_populates="products",  # Assumes Pattern has 'products' list
        foreign_keys=[pattern_id],
    )

    # Many-to-One relationship FROM Product TO Project
    project = relationship(
        "Project",
        back_populates="products",  # Assumes Project has 'products' list
        foreign_keys=[project_id],
    )

    # One-to-Many relationship FROM Product TO SaleItem
    sale_items = relationship(
        "SaleItem",
        back_populates="product",  # Assumes SaleItem has 'product' reference
        cascade="save-update, merge", # Don't delete sale items if product deleted
        passive_deletes=True, # If SaleItem.product_id FK has ON DELETE SET NULL/RESTRICT
    )

    # --- End Relationships ---

    # --- Calculated Properties ---
    @hybrid_property
    def profit_margin(self) -> Optional[float]:
        """Calculate profit margin percentage: (Price - Cost) / Price"""
        if self.selling_price and self.total_cost and self.selling_price != 0:
            margin = (
                (self.selling_price - self.total_cost) / self.selling_price
            ) * 100
            return round(margin, 2)
        return None

    # --- Validators ---
    @validates("sku")
    def validate_sku(self, key: str, sku: str) -> str:
        """Validate and normalize SKU."""
        if not sku or len(sku.strip()) == 0:
            raise ValueError("SKU cannot be empty")
        return sku.strip().upper()

    # Removed validate_quantity as Inventory should manage this

    # --- Methods ---
    def update_sales_metrics(self, sale_amount: float) -> None:
        """Update sales-related metrics after a sale."""
        self.last_sold = datetime.utcnow()
        # Simple moving average - adjust as needed
        current_velocity = self.sales_velocity if self.sales_velocity else 0
        self.sales_velocity = (current_velocity + sale_amount) / 2

    def to_dict(self) -> Dict[str, Any]:
        """Convert Product instance to dictionary representation."""
        inv_record = self.inventory  # Access via relationship

        # Determine status safely, falling back if inventory isn't loaded/present
        current_status = None
        if inv_record and inv_record.status:
            current_status = inv_record.status.name
        # elif self.status: # Fallback if you kept status on Product
        #     current_status = self.status.name

        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "product_type": self.product_type.name if self.product_type else None,
            "description": self.description,
            "color": self.color,
            "dimensions": self.dimensions,
            "weight": self.weight,
            # Get current stock info from the related Inventory record
            "quantity": inv_record.quantity if inv_record else 0,
            "status": current_status,
            "storage_location": inv_record.storage_location
            if inv_record
            else None,
            "reorder_point": self.reorder_point, # Characteristic of the product
            # Pricing and Metrics
            "selling_price": self.selling_price,
            "total_cost": self.total_cost,
            "profit_margin": self.profit_margin, # Use hybrid property
            "last_sold": self.last_sold.isoformat() if self.last_sold else None,
            "sales_velocity": self.sales_velocity,
            # Metadata
            "thumbnail": self.thumbnail,
            "notes": self.notes,
            "batch_number": self.batch_number,
            "customizations": self.customizations,
            "materials": self.materials,
            # Timestamps and FKs
            "created_at": self.createdAt.isoformat() if self.createdAt else None,
            "updated_at": self.updatedAt.isoformat() if self.updatedAt else None,
            "pattern_id": self.pattern_id,
            "project_id": self.project_id,
        }

    def __repr__(self) -> str:
        """Return string representation of the Product."""
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"

