# File: app/db/models/inventory.py
"""
Inventory and Product models for the Leathercraft ERP system.

This module defines the Inventory model for tracking stock levels and the
Product model for finished/sellable items. These models support inventory
management, stock control, and product catalog functionality.
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
    DateTime,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import (
    AbstractBase,
    ValidationMixin,
    TimestampMixin,
    CostingMixin,
)
from app.db.models.enums import (
    InventoryStatus,
    MeasurementUnit,
    InventoryAdjustmentType,
    TransactionType,
)


class Inventory(AbstractBase, ValidationMixin):
    """
    Inventory model for tracking stock levels of materials, products, and tools.

    This model provides a unified view of all inventory items, allowing for
    consistent stock management across different item types.

    Attributes:
        item_type: Type of inventory item (material/product/tool)
        item_id: Reference ID to the specific item
        quantity: Current quantity in stock
        status: Current inventory status
        storage_location: Location where item is stored
    """

    __tablename__ = "inventory"
    __validated_fields__: ClassVar[Set[str]] = {"quantity"}

    # Item identification
    item_type = Column(String(50), nullable=False)  # 'material', 'product', 'tool'
    item_id = Column(Integer, nullable=False)

    # Inventory information
    quantity = Column(Float, default=0)
    status = Column(Enum(InventoryStatus), default=InventoryStatus.IN_STOCK)
    storage_location = Column(String(100))

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
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
        elif quantity <= 5:  # Example threshold, should be item-specific
            self.status = InventoryStatus.LOW_STOCK
        else:
            self.status = InventoryStatus.IN_STOCK

        return quantity

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Inventory instance to a dictionary.

        Returns:
            Dictionary representation of the inventory record
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.status:
            result["status"] = self.status.name

        return result

    def __repr__(self) -> str:
        """Return string representation of the Inventory item."""
        return f"<Inventory(id={self.id}, item_type='{self.item_type}', item_id={self.item_id}, quantity={self.quantity})>"


class InventoryTransaction(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Inventory Transaction model for tracking stock movements and adjustments.

    This model records all changes to inventory quantities, including purchases,
    sales, transfers, adjustments, and other stock movements. Each transaction
    provides an audit trail of who changed what, when, and why.

    Attributes:
        item_type: Type of inventory item (material/product/tool)
        item_id: Reference ID to the specific item
        quantity: Transaction quantity (positive for additions, negative for reductions)
        transaction_type: Type of transaction (purchase, sale, adjustment, etc.)
        adjustment_type: Specific type of adjustment, if applicable
        project_id: Related project, if applicable
        sale_id: Related sale, if applicable
        purchase_id: Related purchase, if applicable
        from_location: Source location for transfers
        to_location: Destination location for transfers
        performed_by: User who performed the transaction
        notes: Additional notes about the transaction
        transaction_date: Date and time when transaction occurred
    """

    __tablename__ = "inventory_transactions"
    __validated_fields__: ClassVar[Set[str]] = {"quantity"}

    # Item identification
    item_type = Column(String(50), nullable=False)  # 'material', 'product', 'tool'
    item_id = Column(Integer, nullable=False)

    # Transaction details
    quantity = Column(Float, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    adjustment_type = Column(Enum(InventoryAdjustmentType), nullable=True)

    # Related entities
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)

    # Location information
    from_location = Column(String(100), nullable=True)
    to_location = Column(String(100), nullable=True)

    # Audit information
    performed_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    transaction_date = Column(DateTime, default=datetime.now)

    # Relationships
    project = relationship("Project", foreign_keys=[project_id])
    sale = relationship("Sale", foreign_keys=[sale_id])
    purchase = relationship("Purchase", foreign_keys=[purchase_id])

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """
        Validate transaction quantity.

        Args:
            key: Field name ('quantity')
            quantity: Quantity value to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is zero
        """
        if quantity == 0:
            raise ValueError("Transaction quantity cannot be zero")
        return quantity

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert InventoryTransaction instance to a dictionary.

        Returns:
            Dictionary representation of the transaction
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.transaction_type:
            result["transaction_type"] = self.transaction_type.name

        if self.adjustment_type:
            result["adjustment_type"] = self.adjustment_type.name

        return result

    def __repr__(self) -> str:
        """Return string representation of the InventoryTransaction."""
        return f"<InventoryTransaction(id={self.id}, type='{self.transaction_type}', item_type='{self.item_type}', item_id={self.item_id}, quantity={self.quantity})>"


class Product(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Product model for finished/sellable items.

    This model represents products available for sale, including both custom
    and production items. It tracks product information, pricing, inventory,
    and relationships to patterns and materials.

    Attributes:
        name: Product name
        product_type: Type of product
        sku: Stock keeping unit
        description: Product description
        materials: List of materials used
        color: Color description
        dimensions: Product dimensions
        weight: Product weight
        pattern_id: Associated pattern
        status: Product status
        quantity: Quantity in stock
        reorder_point: Reorder threshold
        storage_location: Storage location
        thumbnail: Product image
        cost_breakdown: Detailed cost breakdown
        total_cost: Total production cost
        selling_price: Retail price
        profit_margin: Calculated profit margin
        last_sold: Date last sold
        sales_velocity: Sales rate
        project_id: Associated project (if custom)
        batch_number: Production batch
        customizations: Available customizations
        notes: Additional notes
    """

    __tablename__ = "products"
    __validated_fields__: ClassVar[Set[str]] = {"name", "sku", "selling_price"}

    # Basic information
    name = Column(String(255), nullable=False)
    product_type = Column(String(50))
    sku = Column(String(100), unique=True, index=True)
    description = Column(Text)

    # Physical properties
    materials = Column(JSON)  # List of material IDs or names
    color = Column(String(50))
    dimensions = Column(String(100))
    weight = Column(Float)

    # Relationships
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)

    # Inventory information
    status = Column(String(50), default="ACTIVE")
    quantity = Column(Integer, default=0)
    reorder_point = Column(Integer, default=5)
    storage_location = Column(String(100))

    # Media
    thumbnail = Column(String(255))

    # Pricing and costs
    # Note: cost_price, retail_price inherited from CostingMixin
    cost_breakdown = Column(JSON)
    total_cost = Column(Float)
    selling_price = Column(Float)
    profit_margin = Column(Float)

    # Sales information
    last_sold = Column(String(50))  # ISO date
    sales_velocity = Column(Float)  # Units sold per time period

    # Production information
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    batch_number = Column(String(50))
    customizations = Column(JSON)
    notes = Column(Text)

    # Relationships
    pattern = relationship("Pattern", back_populates="products")
    project = relationship("Project", back_populates="products")
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='product', Inventory.item_id==Product.id)",
        foreign_keys="[Inventory.item_id]",
        viewonly=True,
    )
    sale_items = relationship("SaleItem", back_populates="product")

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate product name.

        Args:
            key: Field name ('name')
            name: Product name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 3:
            raise ValueError("Product name must be at least 3 characters")
        return name.strip()

    @validates("sku")
    def validate_sku(self, key: str, sku: str) -> str:
        """
        Validate product SKU.

        Args:
            key: Field name ('sku')
            sku: SKU to validate

        Returns:
            Validated SKU

        Raises:
            ValueError: If SKU is invalid
        """
        if not sku or len(sku.strip()) < 2:
            raise ValueError("SKU must be at least 2 characters")
        return sku.strip().upper()  # Standardize SKUs as uppercase

    @validates("selling_price")
    def validate_selling_price(self, key: str, price: float) -> float:
        """
        Validate selling price and update profit margin.

        Args:
            key: Field name ('selling_price')
            price: Price to validate

        Returns:
            Validated price

        Raises:
            ValueError: If price is negative
        """
        if price < 0:
            raise ValueError("Selling price cannot be negative")

        # Calculate profit margin if cost information is available
        if price > 0 and self.total_cost and self.total_cost > 0:
            self.profit_margin = ((price - self.total_cost) / price) * 100

        return price

    def sync_inventory(self, session) -> None:
        """
        Synchronize product with its inventory record.

        Args:
            session: SQLAlchemy session
        """
        # Find existing inventory record or create new one
        inventory = (
            session.query(Inventory)
            .filter(Inventory.item_type == "product", Inventory.item_id == self.id)
            .first()
        )

        if not inventory:
            inventory = Inventory(
                item_type="product",
                item_id=self.id,
                quantity=self.quantity,
                storage_location=self.storage_location,
            )
            session.add(inventory)
        else:
            inventory.quantity = self.quantity
            inventory.storage_location = self.storage_location

        # Update inventory status based on quantity and reorder point
        if self.quantity <= 0:
            inventory.status = InventoryStatus.OUT_OF_STOCK
        elif self.quantity <= self.reorder_point:
            inventory.status = InventoryStatus.LOW_STOCK
        else:
            inventory.status = InventoryStatus.IN_STOCK

    def is_in_stock(self) -> bool:
        """
        Check if product is in stock.

        Returns:
            True if product quantity > 0, False otherwise
        """
        return self.quantity > 0

    def needs_reorder(self) -> bool:
        """
        Check if product needs to be reordered.

        Returns:
            True if quantity <= reorder_point, False otherwise
        """
        return self.quantity <= self.reorder_point

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Product instance to a dictionary.

        Returns:
            Dictionary representation of the product
        """
        result = super().to_dict()

        # Handle JSON fields
        for field in ["materials", "cost_breakdown", "customizations"]:
            if isinstance(result.get(field), str):
                import json

                try:
                    result[field] = json.loads(result[field])
                except:
                    result[field] = []

        # Add calculated properties
        result["is_in_stock"] = self.is_in_stock()
        result["needs_reorder"] = self.needs_reorder()

        return result

    def __repr__(self) -> str:
        """Return string representation of the Product."""
        return f"<Product(id={self.id}, name='{self.name}', sku='{self.sku}', quantity={self.quantity})>"
