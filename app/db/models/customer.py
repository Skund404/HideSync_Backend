# File: app/db/models/customer.py
"""
Customer model for the Leathercraft ERP system.

This module defines the Customer model, which represents clients and customers
of the leathercraft business. It includes personal information, classification,
and relationship data for tracking customer interactions and sales.
"""

from typing import List, Optional, Dict, Any, Set, ClassVar
from datetime import datetime

from sqlalchemy import Column, String, Text, Enum, Integer, ForeignKey, Table
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, AuditMixin, TimestampMixin
from app.db.models.enums import CustomerStatus, CustomerTier, CustomerSource

# Define the many-to-many relationship table for Customer-PlatformIntegration
customer_platform_integration = Table(
    "customer_platform_integration",
    AbstractBase.metadata,
    Column("customer_id", Integer, ForeignKey("customers.id"), primary_key=True),
    Column(
        "platform_integration_id",
        Integer,
        ForeignKey("platform_integrations.id"),
        primary_key=True,
    ),
)


class Customer(AbstractBase, ValidationMixin, AuditMixin, TimestampMixin):
    """
    Customer model representing clients of the leathercraft business.

    This model stores all customer information including contact details,
    categorization (status, tier, source), and relationship data for
    tracking customer interactions and sales.
    """

    __tablename__ = "customers"
    __validated_fields__: ClassVar[Set[str]] = {"email", "phone", "name"}

    # Basic information
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(50))

    # Classification
    status = Column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE)
    tier = Column(Enum(CustomerTier), default=CustomerTier.STANDARD)
    source = Column(Enum(CustomerSource))

    # Additional information
    company_name = Column(String(255))
    address = Column(String(500))
    notes = Column(Text)

    # For GDPR compliance: sensitive fields that should be handled carefully
    SENSITIVE_FIELDS = ["email", "phone", "address"]

    # Relationships
    sales = relationship("Sale", back_populates="customer")
    platform_integrations = relationship(
        "PlatformIntegration",
        secondary=customer_platform_integration,
        back_populates="customers",
    )
    communications = relationship(
        "CustomerCommunication", back_populates="customer", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate the customer name.

        Args:
            key: Field name ('name')
            name: Customer name to validate

        Returns:
            The validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Customer name must be at least 2 characters")
        return name.strip()

    def __repr__(self) -> str:
        """Return string representation of the Customer."""
        return f"<Customer(id={self.id}, name='{self.name}', email='{self.email}', status={self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Customer instance to a dictionary.

        Returns:
            Dictionary representation of the customer
        """
        result = super().to_dict()

        # Convert enum values to strings for serialization
        if self.status:
            result["status"] = self.status.name
        if self.tier:
            result["tier"] = self.tier.name
        if self.source:
            result["source"] = self.source.name

        # Don't include relationship data to avoid circular references
        result.pop("sales", None)
        result.pop("platform_integrations", None)
        result.pop("communications", None)

        return result

    def record_interaction(self, interaction_type: str, notes: str, user: str) -> None:
        """
        Record a customer interaction in the audit trail.

        Args:
            interaction_type: Type of interaction (e.g., 'email', 'phone', 'meeting')
            notes: Notes about the interaction
            user: User who recorded the interaction
        """
        self.record_change(
            user,
            {
                "interaction_type": interaction_type,
                "interaction_notes": notes,
                "interaction_date": datetime.now().isoformat(),
            },
        )

    def update_tier(self, new_tier: CustomerTier, reason: str, user: str) -> None:
        """
        Update customer tier with audit trail.

        Args:
            new_tier: New customer tier
            reason: Reason for the tier change
            user: User who made the change
        """
        old_tier = self.tier
        self.tier = new_tier

        self.record_change(
            user,
            {
                "field": "tier",
                "old_value": old_tier.name if old_tier else None,
                "new_value": new_tier.name,
                "reason": reason,
            },
        )
