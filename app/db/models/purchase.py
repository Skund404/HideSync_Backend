# File: app/db/models/purchase.py
"""
Purchase models for the Leathercraft ERP system.

This module defines the Purchase and PurchaseItem models, representing
supplier orders and their line items. These models track material acquisition,
order fulfillment, and payment status.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import Column, String, Text, Float, Enum, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import PurchaseStatus, PaymentStatus


class Purchase(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Purchase model representing supplier orders.

    This model tracks orders placed with suppliers, including materials,
    quantities, costs, delivery, and payment information.

    Attributes:
        supplier_id: ID of the associated supplier
        supplier: Name of the supplier (denormalized)
        date: Order creation date
        delivery_date: Expected delivery date
        status: Purchase order status
        total: Total order amount
        payment_status: Payment status
        notes: Additional notes
        invoice: Invoice reference
    """

    __tablename__ = "purchases"
    __validated_fields__: ClassVar[Set[str]] = {"supplier_id", "total"}

    # Supplier information
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    supplier = Column(String(255))  # Denormalized supplier name

    # Dates
    date = Column(DateTime)
    delivery_date = Column(DateTime)

    # Status and financial information
    status = Column(Enum(PurchaseStatus), default=PurchaseStatus.PLANNING)
    total = Column(Float, default=0)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)

    # Additional information
    notes = Column(Text)
    invoice = Column(String(100))

    # Relationships
    supplier_rel = relationship("Supplier", back_populates="purchases")
    items = relationship(
        "PurchaseItem", back_populates="purchase", cascade="all, delete-orphan"
    )

    @validates("supplier_id")
    def validate_supplier_id(self, key: str, supplier_id: int) -> int:
        """
        Validate supplier ID.

        Args:
            key: Field name ('supplier_id')
            supplier_id: Supplier ID to validate

        Returns:
            Validated supplier ID

        Raises:
            ValueError: If supplier ID is invalid
        """
        if not supplier_id or supplier_id <= 0:
            raise ValueError("Valid supplier ID is required")
        return supplier_id

    @validates("total")
    def validate_total(self, key: str, total: float) -> float:
        """
        Validate order total.

        Args:
            key: Field name ('total')
            total: Total amount to validate

        Returns:
            Validated total amount

        Raises:
            ValueError: If total is negative
        """
        if total < 0:
            raise ValueError("Total amount cannot be negative")
        return total

    @hybrid_property
    def is_overdue(self) -> bool:
        """
        Check if the order is overdue.

        Returns:
            True if the order is overdue, False otherwise
        """
        if not self.delivery_date:
            return False

        return (
            datetime.now() > self.delivery_date
            and not self.status == PurchaseStatus.RECEIVED
        )

    @hybrid_property
    def days_outstanding(self) -> Optional[int]:
        """
        Calculate days since order was placed.

        Returns:
            Number of days since order date, or None if no date
        """
        if not self.date:
            return None

        delta = datetime.now() - self.date
        return delta.days

    def update_status(
        self, new_status: PurchaseStatus, user: str, notes: Optional[str] = None
    ) -> None:
        """
        Update purchase status with audit trail.

        Args:
            new_status: New purchase status
            user: User making the change
            notes: Optional notes about the status change
        """
        old_status = self.status
        self.status = new_status

        # Status-specific actions
        if new_status == PurchaseStatus.RECEIVED:
            self.delivery_date = datetime.now()

        # Record the change in history
        if hasattr(self, "record_change"):
            self.record_change(
                user,
                {
                    "field": "status",
                    "old_value": old_status.name if old_status else None,
                    "new_value": new_status.name,
                    "notes": notes,
                },
            )

    def calculate_total(self) -> float:
        """
        Calculate total amount from items.

        Returns:
            Calculated total amount
        """
        total = sum(item.total for item in self.items if item.total is not None)
        self.total = total
        return total

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Purchase instance to a dictionary.

        Returns:
            Dictionary representation of the purchase
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.status:
            result["status"] = self.status.name
        if self.payment_status:
            result["payment_status"] = self.payment_status.name

        # Add calculated properties
        result["is_overdue"] = self.is_overdue
        result["days_outstanding"] = self.days_outstanding

        return result

    def __repr__(self) -> str:
        """Return string representation of the Purchase."""
        return f"<Purchase(id={self.id}, supplier_id={self.supplier_id}, total={self.total}, status={self.status})>"


class PurchaseItem(AbstractBase, ValidationMixin):
    """
    PurchaseItem model representing items in a purchase order.

    This model tracks individual line items within a purchase, including
    material information, quantities, and pricing.

    Attributes:
        purchase_id: ID of the parent purchase
        name: Item name/description
        quantity: Quantity ordered
        price: Unit price
        total: Total cost
        item_type: Type of item
        material_type: Type of material
        unit: Unit of measurement
        notes: Additional notes
    """

    __tablename__ = "purchase_items"
    __validated_fields__: ClassVar[Set[str]] = {"purchase_id", "quantity", "price"}

    # Relationships
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)

    # Item information
    name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    total = Column(Float)

    # Classification
    item_type = Column(String(50))  # material, tool, etc.
    material_type = Column(String(50))
    unit = Column(String(50))

    # Additional information
    notes = Column(Text)

    # Relationships
    purchase = relationship("Purchase", back_populates="items")

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
            raise ValueError("Quantity must be at least 1")
        return quantity

    @validates("price")
    def validate_price(self, key: str, price: float) -> float:
        """
        Validate item price and update total.

        Args:
            key: Field name ('price')
            price: Price to validate

        Returns:
            Validated price

        Raises:
            ValueError: If price is negative
        """
        if price < 0:
            raise ValueError("Price cannot be negative")

        # Update total if quantity is available
        if hasattr(self, "quantity") and self.quantity is not None:
            self.total = price * self.quantity

        return price

    def __repr__(self) -> str:
        """Return string representation of the PurchaseItem."""
        return f"<PurchaseItem(id={self.id}, purchase_id={self.purchase_id}, name='{self.name}', quantity={self.quantity})>"
