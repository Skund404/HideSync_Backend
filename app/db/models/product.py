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

import json
import logging  # Add logging import if not already present

logger = logging.getLogger(__name__)  # Define logger for the warning
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
        cascade="save-update, merge",  # Don't delete sale items if product deleted
        passive_deletes=True,  # If SaleItem.product_id FK has ON DELETE SET NULL/RESTRICT
    )

    # --- End Relationships ---

    # --- Calculated Properties ---
    @hybrid_property
    def profit_margin(self) -> Optional[float]:
        """Calculate profit margin percentage: (Price - Cost) / Price"""
        if self.selling_price and self.total_cost and self.selling_price != 0:
            margin = ((self.selling_price - self.total_cost) / self.selling_price) * 100
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
        inv_record = self.inventory

        current_status = None
        quantity = 0.0  # Default quantity
        storage_location = None  # Default location
        if inv_record:
            quantity = getattr(inv_record, "quantity", 0.0)
            # Handle status potentially being None or not having a name
            status_obj = getattr(inv_record, "status", None)
            current_status = (
                status_obj.name if status_obj and hasattr(status_obj, "name") else None
            )
            storage_location = getattr(inv_record, "storage_location", None)

        # --- FIX: Use snake_case for timestamp attributes ---
        created_at_iso = (
            self.created_at.isoformat()
            if hasattr(self, "created_at") and self.created_at
            else None
        )
        updated_at_iso = (
            self.updated_at.isoformat()
            if hasattr(self, "updated_at") and self.updated_at
            else None
        )
        last_sold_iso = (
            self.last_sold.isoformat()
            if hasattr(self, "last_sold") and self.last_sold
            else None
        )
        # --- END FIX ---

        # --- FIX: Handle potential None for product_type ---
        product_type_name = (
            self.product_type.name
            if hasattr(self, "product_type")
            and self.product_type
            and hasattr(self.product_type, "name")
            else None
        )
        # --- END FIX ---

        # --- FIX: Safely access cost breakdown ---
        cost_breakdown_dict = None
        if hasattr(self, "cost_breakdown") and self.cost_breakdown:
            try:
                # Assuming cost_breakdown is stored as JSON string
                cost_breakdown_dict = (
                    json.loads(self.cost_breakdown)
                    if isinstance(self.cost_breakdown, str)
                    else self.cost_breakdown
                )
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    f"Could not parse cost_breakdown JSON for product {self.id}"
                )
                cost_breakdown_dict = {}  # Or None, or keep original string?
        # --- END FIX ---

        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "productType": product_type_name,  # Use safe variable
            "description": self.description,
            "color": self.color,
            "dimensions": self.dimensions,
            "weight": self.weight,
            # Inventory fields
            "quantity": quantity,
            "status": current_status,
            "storage_location": storage_location,
            "reorder_point": self.reorder_point,
            # Pricing and Metrics
            "sellingPrice": self.selling_price,  # Use camelCase keys for consistency with frontend/schema if needed
            "totalCost": self.total_cost,
            "profitMargin": self.profit_margin,  # Use hybrid property
            "lastSold": last_sold_iso,  # Use safe variable
            "salesVelocity": self.sales_velocity,
            # Metadata
            "thumbnail": self.thumbnail,
            "notes": self.notes,
            "batchNumber": self.batch_number,
            "customizations": self.customizations,  # Assume already JSON serializable or list/dict
            "materials": self.materials,  # Assume already JSON serializable or list/dict
            "costBreakdown": cost_breakdown_dict,  # Use parsed dict
            # Timestamps and FKs
            "createdAt": created_at_iso,  # Use camelCase key for API consistency
            "updatedAt": updated_at_iso,  # Use camelCase key for API consistency
            "patternId": self.pattern_id,
            "projectId": self.project_id,
            # Add any other fields required by ProductResponse schema
            "is_active": getattr(
                self, "is_active", None
            ),  # Example if is_active exists
            "uuid": getattr(self, "uuid", None),  # Example if uuid exists
        }

    def __repr__(self) -> str:
        """Return string representation of the Product."""
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"
