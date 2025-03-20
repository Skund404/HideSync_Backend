from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    Float,
    DateTime,
    JSON,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates

from app.db.models.base import (
    AbstractBase,
    ValidationMixin,
    CostingMixin,
    TimestampMixin,
)
from app.db.models.enums import InventoryStatus, ProjectType


class Product(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Represents finished products in the leathercraft business inventory.

    Tracks product details, inventory, pricing, and sales-related information.
    """

    __tablename__ = "products"

    # Basic Product Information
    name = Column(String(255), nullable=False)
    product_type = Column(Enum(ProjectType), nullable=True)
    sku = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    # Material and Physical Attributes
    materials = Column(JSON, nullable=True, comment="List of material IDs or details")
    color = Column(String(50), nullable=True)
    dimensions = Column(String(100), nullable=True)
    weight = Column(Float, nullable=True)

    # Inventory and Tracking
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)
    status = Column(
        Enum(InventoryStatus), nullable=False, default=InventoryStatus.IN_STOCK
    )
    quantity = Column(Integer, default=0)
    reorder_point = Column(Integer, nullable=True)
    storage_location = Column(String(255), nullable=True)

    # Pricing and Financial Tracking
    total_cost = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    profitMargin = Column(Float, nullable=True)
    cost_breakdown = Column(JSON, nullable=True)

    # Sales and Performance Metrics
    last_sold = Column(DateTime, nullable=True)
    sales_velocity = Column(Float, nullable=True)

    # Additional Metadata
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    batch_number = Column(String(50), nullable=True)
    customizations = Column(JSON, nullable=True)
    thumbnail = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    pattern = relationship("Pattern", back_populates="products")
    project = relationship("Project", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False)

    @validates("sku")
    def validate_sku(self, key: str, sku: str) -> str:
        """
        Validate and normalize SKU.

        Args:
            key: The attribute name being validated
            sku: The SKU value to validate

        Returns:
            Validated and normalized SKU

        Raises:
            ValueError: If SKU is invalid
        """
        if not sku or len(sku.strip()) == 0:
            raise ValueError("SKU cannot be empty")

        # Normalize: remove whitespace, convert to uppercase
        normalized_sku = sku.strip().upper()

        # Optional: Add SKU format validation if needed
        # Example: Ensure SKU follows a specific pattern
        # if not re.match(r'^[A-Z]{2}\d{4}$', normalized_sku):
        #     raise ValueError("SKU must follow format: 2 letters followed by 4 digits")

        return normalized_sku

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: int) -> int:
        """
        Validate product quantity and update status accordingly.

        Args:
            key: The attribute name being validated
            quantity: The quantity to validate

        Returns:
            Validated quantity
        """
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        # Update status based on quantity
        if quantity == 0:
            self.status = InventoryStatus.OUT_OF_STOCK
        elif quantity <= self.reorder_point or 0:
            self.status = InventoryStatus.LOW_STOCK
        else:
            self.status = InventoryStatus.IN_STOCK

        return quantity

    def calculate_profit_margin(self) -> float:
        """
        Calculate profit margin based on cost and selling price.

        Returns:
            Profit margin percentage
        """
        if not self.total_cost or not self.selling_price or self.total_cost == 0:
            return 0.0

        margin = ((self.selling_price - self.total_cost) / self.total_cost) * 100
        return round(margin, 2)

    def update_sales_metrics(self, sale_amount: float) -> None:
        """
        Update sales-related metrics after a sale.

        Args:
            sale_amount: Amount of the sale
        """
        self.last_sold = datetime.utcnow()

        # Basic sales velocity calculation (can be made more sophisticated)
        if not self.sales_velocity:
            self.sales_velocity = sale_amount
        else:
            # Simple moving average
            self.sales_velocity = (self.sales_velocity + sale_amount) / 2

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Product instance to dictionary representation.

        Returns:
            Dictionary with product details
        """
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "product_type": self.product_type.name if self.product_type else None,
            "description": self.description,
            "color": self.color,
            "dimensions": self.dimensions,
            "weight": self.weight,
            "quantity": self.quantity,
            "status": self.status.name if self.status else None,
            "selling_price": self.selling_price,
            "total_cost": self.total_cost,
            "profit_margin": self.calculate_profit_margin(),
            "last_sold": self.last_sold.isoformat() if self.last_sold else None,
            "created_at": self.createdAt.isoformat() if self.createdAt else None,
            "updated_at": self.updatedAt.isoformat() if self.updatedAt else None,
        }
