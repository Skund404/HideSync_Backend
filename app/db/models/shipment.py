# File: app/db/models/shipment.py
"""
Shipment model for the Leathercraft ERP system.

This module defines the Shipment model representing outbound shipments
to customers, tracking shipping methods, costs, and statuses.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin


class Shipment(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Shipment model representing outbound shipments to customers.

    This model tracks shipping information for customer orders, including
    carrier, tracking, costs, and status updates.

    Attributes:
        sale_id: ID of the associated sale
        tracking_number: Carrier tracking number
        shipping_method: Shipping method used
        shipping_cost: Cost of shipping
        ship_date: Date of shipment
        status: Current shipment status
    """

    __tablename__ = "shipments"
    __validated_fields__: ClassVar[Set[str]] = {"sale_id"}

    # Relationships
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)

    # Shipping information
    tracking_number = Column(String(100))
    shipping_method = Column(String(100))
    shipping_cost = Column(Float, default=0)
    ship_date = Column(DateTime)
    status = Column(String(50), default="PENDING")

    # Relationships
    sale = relationship("Sale", back_populates="shipment")

    @validates("shipping_cost")
    def validate_shipping_cost(self, key: str, cost: float) -> float:
        """
        Validate shipping cost.

        Args:
            key: Field name ('shipping_cost')
            cost: Shipping cost to validate

        Returns:
            Validated shipping cost

        Raises:
            ValueError: If cost is negative
        """
        if cost < 0:
            raise ValueError("Shipping cost cannot be negative")
        return cost

    def mark_shipped(
        self,
        tracking_number: str,
        method: str,
        cost: float,
        date: Optional[datetime] = None,
    ) -> None:
        """
        Mark shipment as shipped with details.

        Args:
            tracking_number: Carrier tracking number
            method: Shipping method used
            cost: Shipping cost
            date: Ship date (defaults to now)
        """
        self.tracking_number = tracking_number
        self.shipping_method = method
        self.shipping_cost = cost
        self.ship_date = date or datetime.now()
        self.status = "SHIPPED"

        # Update sale status if available
        if (
            self.sale
            and hasattr(self.sale, "status")
            and hasattr(self.sale, "update_status")
        ):
            from app.db.models.enums import SaleStatus

            if self.sale.status != SaleStatus.SHIPPED:
                self.sale.update_status(
                    SaleStatus.SHIPPED,
                    "system",
                    f"Order shipped via {method}, tracking: {tracking_number}",
                )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Shipment instance to a dictionary.

        Returns:
            Dictionary representation of the shipment
        """
        result = super().to_dict()

        # Add tracking URL based on shipping method
        if self.tracking_number and self.shipping_method:
            if "UPS" in self.shipping_method.upper():
                result["tracking_url"] = (
                    f"https://www.ups.com/track?tracknum={self.tracking_number}"
                )
            elif "FEDEX" in self.shipping_method.upper():
                result["tracking_url"] = (
                    f"https://www.fedex.com/fedextrack/?trknbr={self.tracking_number}"
                )
            elif "USPS" in self.shipping_method.upper():
                result["tracking_url"] = (
                    f"https://tools.usps.com/go/TrackConfirmAction?tLabels={self.tracking_number}"
                )

        return result

    def __repr__(self) -> str:
        """Return string representation of the Shipment."""
        return (
            f"<Shipment(id={self.id}, sale_id={self.sale_id}, status='{self.status}')>"
        )
