# File: app/db/models/sales.py
"""
Sales models for the Leathercraft ERP system.

This module defines the Sale and SaleItem models, which represent
customer purchases and order items. These models track financial
transactions, fulfillment status, and relationships to projects.
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
    DateTime,
    JSON,
    ARRAY,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import ARRAY as PostgresArray

from app.db.models.base import (
    AbstractBase,
    ValidationMixin,
    CostingMixin,
    TimestampMixin,
)
from app.db.models.enums import SaleStatus, PaymentStatus


class Sale(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """
    Sale model representing customer orders and purchases.

    This model tracks all aspects of a sale, including customer information,
    financial details, fulfillment status, and related projects.

    Attributes:
        customer_id: ID of the associated customer
        created_at: Date/time when the sale was created
        due_date: Due date for completion
        completed_date: Actual completion date
        subtotal: Subtotal amount
        taxes: Tax amount
        shipping: Shipping costs
        platform_fees: Fees from sales platforms
        total_amount: Total sale amount
        net_revenue: Net revenue after fees
        deposit_amount: Deposit amount received
        balance_due: Remaining balance
        status: Current sale status
        payment_status: Payment status
        fulfillment_status: Fulfillment status
        channel: Sales channel
        platform_order_id: Order ID from external platform
        marketplace_data: Additional data from marketplace
        shipping_method: Shipping method
        shipping_provider: Shipping provider
        tracking_number: Tracking number
        tags: Tags for categorization
        notes: Additional notes
        customization: Custom requirements
    """

    __tablename__ = "sales"
    __validated_fields__: ClassVar[Set[str]] = {
        "total_amount",
        "deposit_amount",
        "customer_id",
    }

    # Customer information
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    # Dates
    due_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)

    # Financial information
    subtotal = Column(Float, default=0)
    taxes = Column(Float, default=0)
    shipping = Column(Float, default=0)
    platform_fees = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    net_revenue = Column(Float, default=0)
    deposit_amount = Column(Float, default=0)
    balance_due = Column(Float, default=0)

    # Status information
    status = Column(Enum(SaleStatus), default=SaleStatus.INQUIRY)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    fulfillment_status = Column(String(50), default="PENDING")

    # Channel and platform information
    channel = Column(String(50))
    platform_order_id = Column(String(100))
    marketplace_data = Column(JSON, nullable=True)

    # Shipping information
    shipping_method = Column(String(100))
    shipping_provider = Column(String(100))
    tracking_number = Column(String(100))

    # Additional information
    # Using String[] for PostgreSQL or JSON for SQLite compatibility
    tags = Column(JSON, nullable=True)  # Will be converted to/from list in code
    notes = Column(Text)
    customization = Column(Text)

    # Relationships
    customer = relationship("Customer", back_populates="sales")
    items = relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan"
    )
    projects = relationship("Project", back_populates="sale")
    picking_list = relationship("PickingList", back_populates="sale", uselist=False)
    shipment = relationship("Shipment", back_populates="sale", uselist=False)
    refund = relationship("Refund", back_populates="sale", uselist=False)

    @validates("customer_id")
    def validate_customer_id(self, key: str, customer_id: int) -> int:
        """
        Validate customer ID.

        Args:
            key: Field name ('customer_id')
            customer_id: Customer ID to validate

        Returns:
            Validated customer ID

        Raises:
            ValueError: If customer ID is invalid
        """
        if not customer_id or customer_id <= 0:
            raise ValueError("Valid customer ID is required")
        return customer_id

    @validates("total_amount", "deposit_amount")
    def validate_amounts(self, key: str, amount: float) -> float:
        """
        Validate monetary amounts.

        Args:
            key: Field name ('total_amount' or 'deposit_amount')
            amount: Amount to validate

        Returns:
            Validated amount

        Raises:
            ValueError: If amount is negative
        """
        if amount < 0:
            raise ValueError(f"{key} cannot be negative")

        # Update balance due if appropriate
        if (
            key in ("total_amount", "deposit_amount")
            and hasattr(self, "total_amount")
            and hasattr(self, "deposit_amount")
        ):
            if self.total_amount is not None and self.deposit_amount is not None:
                self.balance_due = self.total_amount - self.deposit_amount

        return amount

    @hybrid_property
    def is_paid(self) -> bool:
        """
        Check if the sale is fully paid.

        Returns:
            True if fully paid, False otherwise
        """
        if self.total_amount is None or self.total_amount == 0:
            return False

        return self.balance_due <= 0 or self.payment_status == PaymentStatus.PAID

    @hybrid_property
    def profit_margin(self) -> Optional[float]:
        """
        Calculate profit margin percentage.

        Returns:
            Profit margin as percentage, or None if cost information is missing
        """
        if not self.total_amount or not self.cost_price or self.total_amount == 0:
            return None

        profit = self.total_amount - self.cost_price
        return (profit / self.total_amount) * 100

    def record_payment(
        self, amount: float, payment_method: str, user: str, notes: Optional[str] = None
    ) -> None:
        """
        Record a payment against this sale.

        Args:
            amount: Payment amount
            payment_method: Method of payment
            user: User recording the payment
            notes: Additional payment notes
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        # Update financial information
        old_deposit = self.deposit_amount or 0
        self.deposit_amount = old_deposit + amount
        self.balance_due = self.total_amount - self.deposit_amount

        # Update payment status
        if self.balance_due <= 0:
            self.payment_status = PaymentStatus.PAID
        elif self.deposit_amount > 0:
            self.payment_status = PaymentStatus.PARTIALLY_PAID

        # Record the payment in history
        if hasattr(self, "record_change"):
            self.record_change(
                user,
                {
                    "action": "payment",
                    "amount": amount,
                    "payment_method": payment_method,
                    "previous_deposit": old_deposit,
                    "new_deposit": self.deposit_amount,
                    "new_balance": self.balance_due,
                    "notes": notes,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    def update_status(
        self, new_status: SaleStatus, user: str, notes: Optional[str] = None
    ) -> None:
        """
        Update sale status with audit trail.

        Args:
            new_status: New sale status
            user: User making the change
            notes: Optional notes about the status change
        """
        old_status = self.status
        self.status = new_status

        # Handle status-specific actions
        if new_status == SaleStatus.COMPLETED:
            self.completed_date = datetime.now()

        # Record the change in history
        if hasattr(self, "record_change"):
            self.record_change(
                user,
                {
                    "field": "status",
                    "old_value": old_status.name if old_status else None,
                    "new_value": new_status.name,
                    "notes": notes,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Sale instance to a dictionary.

        Returns:
            Dictionary representation of the sale
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.status:
            result["status"] = self.status.name
        if self.payment_status:
            result["payment_status"] = self.payment_status.name

        # Handle tags (stored as JSON)
        if self.tags and isinstance(self.tags, str):
            import json

            try:
                result["tags"] = json.loads(self.tags)
            except:
                result["tags"] = []

        # Add calculated properties
        result["is_paid"] = self.is_paid
        result["profit_margin"] = self.profit_margin

        return result

    def __repr__(self) -> str:
        """Return string representation of the Sale."""
        return f"<Sale(id={self.id}, customer_id={self.customer_id}, total={self.total_amount}, status={self.status})>"


class SaleItem(AbstractBase, ValidationMixin):
    """
    SaleItem model representing individual items in a sale.

    This model tracks individual line items within a sale, including
    product information, pricing, and quantities.

    Attributes:
        sale_id: ID of the parent sale
        quantity: Quantity ordered
        price: Unit price
        tax: Tax amount
        name: Item name/description
        type: Item type (e.g., CUSTOM, PRODUCTION)
        sku: Stock keeping unit
        product_id: ID of the associated product (if applicable)
        project_id: ID of the associated project (if applicable)
        pattern_id: ID of the associated pattern (if applicable)
        notes: Additional notes
    """

    __tablename__ = "sale_items"
    __validated_fields__: ClassVar[Set[str]] = {"quantity", "price"}

    # Relationships
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)

    # Item information
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    tax = Column(Float, default=0)
    name = Column(String(255), nullable=False)
    type = Column(String(50))
    sku = Column(String(100))

    # Related entities
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)

    # Additional information
    notes = Column(Text)

    # Relationships
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")
    project = relationship("Project", back_populates="sale_items")
    pattern = relationship("Pattern", back_populates="sale_items")

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: int) -> int:
        """
        Validate item quantity.

        Args:
            key: Field name ('quantity')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is less than 1
        """
        if quantity < 1:
            raise ValueError("Item quantity must be at least 1")
        return quantity

    @validates("price")
    def validate_price(self, key: str, price: float) -> float:
        """
        Validate item price.

        Args:
            key: Field name ('price')
            price: Price to validate

        Returns:
            Validated price

        Raises:
            ValueError: If price is negative
        """
        if price < 0:
            raise ValueError("Item price cannot be negative")
        return price

    @hybrid_property
    def subtotal(self) -> float:
        """
        Calculate subtotal for this item.

        Returns:
            Subtotal (price * quantity)
        """
        return self.price * self.quantity

    @hybrid_property
    def total(self) -> float:
        """
        Calculate total for this item including tax.

        Returns:
            Total (subtotal + tax)
        """
        return self.subtotal + self.tax

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert SaleItem instance to a dictionary.

        Returns:
            Dictionary representation of the sale item
        """
        result = super().to_dict()

        # Add calculated properties
        result["subtotal"] = self.subtotal
        result["total"] = self.total

        return result

    def __repr__(self) -> str:
        """Return string representation of the SaleItem."""
        return f"<SaleItem(id={self.id}, sale_id={self.sale_id}, name='{self.name}', quantity={self.quantity}, price={self.price})>"
