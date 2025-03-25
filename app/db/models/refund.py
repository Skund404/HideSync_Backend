# File: app/db/models/refund.py
"""
Refund model for the HideSync system.

This module defines the Refund model representing customer refunds
for sales, tracking amount, reason, and processing status.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import PaymentStatus


class Refund(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Refund model representing customer refunds for sales.

    This model tracks refunds issued to customers, including the amount,
    reason, and processing status.

    Attributes:
        sale_id: ID of the associated sale
        refund_date: Date when the refund was processed
        refund_amount: Amount refunded
        reason: Reason for the refund
        status: Current refund status
        transaction_id: External transaction ID for the refund
        payment_method: Method used for the refund
        processed_by: ID of the user who processed the refund
        notes: Additional notes about the refund
    """

    __tablename__ = "refunds"
    __validated_fields__: ClassVar[Set[str]] = {"sale_id", "refund_amount"}

    # Relationships
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)

    # Refund information
    refund_date = Column(DateTime, default=datetime.now)
    refund_amount = Column(Float, nullable=False)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), default="PENDING")
    transaction_id = Column(String(100))
    payment_method = Column(String(100))
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text)

    # Relationships
    sale = relationship("Sale", back_populates="refund")
    processor = relationship("User", foreign_keys=[processed_by])

    @validates("refund_amount")
    def validate_refund_amount(self, key: str, amount: float) -> float:
        """
        Validate refund amount.

        Args:
            key: Field name ('refund_amount')
            amount: Refund amount to validate

        Returns:
            Validated refund amount

        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Refund amount must be positive")
        return amount

    def process_refund(
            self,
            transaction_id: str,
            payment_method: str,
            processor_id: Optional[int] = None,
            notes: Optional[str] = None,
    ) -> None:
        """
        Mark the refund as processed with transaction details.

        Args:
            transaction_id: Transaction ID from payment processor
            payment_method: Method used for the refund
            processor_id: ID of the user processing the refund
            notes: Additional notes about the refund
        """
        self.transaction_id = transaction_id
        self.payment_method = payment_method
        self.status = "PROCESSED"
        self.refund_date = datetime.now()

        if processor_id:
            self.processed_by = processor_id

        if notes:
            self.notes = notes

        # Update sale status if available
        if (
                self.sale
                and hasattr(self.sale, "payment_status")
                and hasattr(self.sale, "total_amount")
        ):
            # If refund is complete (full refund), update sale payment status
            if self.refund_amount >= self.sale.total_amount * 0.99:  # Allow small differences
                self.sale.payment_status = PaymentStatus.REFUNDED

            # If partial refund, we could handle it differently
            elif self.sale.payment_status != PaymentStatus.REFUNDED:
                self.sale.payment_status = PaymentStatus.PARTIALLY_REFUNDED

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Refund instance to a dictionary.

        Returns:
            Dictionary representation of the refund
        """
        result = super().to_dict()
        return result

    def __repr__(self) -> str:
        """Return string representation of the Refund."""
        return (
            f"<Refund(id={self.id}, sale_id={self.sale_id}, "
            f"amount={self.refund_amount}, status='{self.status}')>"
        )