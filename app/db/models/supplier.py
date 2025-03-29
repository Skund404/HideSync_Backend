# File: app/db/models/supplier.py
"""
Supplier model for the Leathercraft ERP system.

This module defines the Supplier model representing vendors and suppliers
of materials, hardware, and tools. It tracks supplier information, status,
and relationships to materials and purchases.
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
    Boolean, Index,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import SupplierStatus
from app.core.validation import validate_phone


class Supplier(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Supplier model representing vendors and material sources.

    This model tracks all information about suppliers, including contact details,
    performance metrics, and purchasing history.

    Attributes:
        name: Supplier business name
        category: Business category (LEATHER/HARDWARE/SUPPLIES/MIXED)
        contact_name: Primary contact person
        email: Contact email
        phone: Contact phone number
        address: Business address
        website: Business website
        rating: Supplier rating (1-5)
        status: Supplier status
        notes: Additional notes
        material_categories: Categories of materials supplied
        logo: Company logo image path/URL
        last_order_date: Date of last order
        payment_terms: Payment terms
        min_order_amount: Minimum order amount
        lead_time: Typical lead time
    """

    __tablename__ = "suppliers"
    __validated_fields__: ClassVar[Set[str]] = {"name", "email", "phone"}
    __table_args__ = (
        Index('idx_supplier_name', 'name'),
        Index('idx_supplier_category', 'category'),
        Index('idx_supplier_status', 'status'),
        # Add other indexes as needed
    )
    # Basic information
    name = Column(String(255), nullable=False)
    category = Column(String(50))  # LEATHER/HARDWARE/SUPPLIES/MIXED
    contact_name = Column(String(100))
    email = Column(String(255))
    phone = Column(
        String(20),  # Adjust length as needed
        nullable=True,  # Or False if phone is required
        info={'validator': validate_phone}
    )
    address = Column(String(500))
    website = Column(String(255))

    # Performance metrics
    rating = Column(Integer)  # 1-5 scale
    status = Column(
        Enum(SupplierStatus, name='supplier_status_enum'),
        nullable=False,
        default=SupplierStatus.ACTIVE
    )
    notes = Column(Text)

    # Categorization
    material_categories = Column(JSON, nullable=True)  # List of categories
    logo = Column(String(255))  # Path to logo image

    # Business details
    last_order_date = Column(String(50))  # ISO date string
    payment_terms = Column(String(100))
    min_order_amount = Column(String(50))
    lead_time = Column(String(50))

    # Relationships
    materials = relationship("Material", back_populates="supplier_rel")
    purchases = relationship("Purchase", back_populates="supplier_rel")
    tools = relationship("Tool", back_populates="supplier_rel")
    status_history = relationship(
        "SupplierHistory", back_populates="supplier", cascade="all, delete-orphan"
    )
    rating_history = relationship(
        "SupplierRating", back_populates="supplier", cascade="all, delete-orphan"
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate supplier name.

        Args:
            key: Field name ('name')
            name: Supplier name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Supplier name must be at least 2 characters")
        return name.strip()

    @validates("rating")
    def validate_rating(self, key: str, rating: Optional[int]) -> Optional[int]:
        """
        Validate supplier rating.

        Args:
            key: Field name ('rating')
            rating: Rating to validate

        Returns:
            Validated rating

        Raises:
            ValueError: If rating is not between 1 and 5
        """
        if rating is not None and (rating < 1 or rating > 5):
            raise ValueError("Rating must be between 1 and 5")
        return rating

    @hybrid_property
    def average_lead_time_days(self) -> Optional[int]:
        """
        Calculate average lead time from purchases.

        Returns:
            Average lead time in days, or None if no purchases
        """
        if not self.purchases:
            return None

        purchases_with_delivery = [
            p for p in self.purchases if p.delivery_date and p.date
        ]

        if not purchases_with_delivery:
            return None

        total_days = sum(
            (p.delivery_date - p.date).days for p in purchases_with_delivery
        )
        return total_days // len(purchases_with_delivery)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Supplier instance to a dictionary.

        Returns:
            Dictionary representation of the supplier
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.status:
            result["status"] = self.status.name

        # Handle JSON fields
        if isinstance(result.get("material_categories"), str):
            import json

            try:
                result["material_categories"] = json.loads(
                    result["material_categories"]
                )
            except:
                result["material_categories"] = []

        return result

    def __repr__(self) -> str:
        """Return string representation of the Supplier."""
        return f"<Supplier(id={self.id}, name='{self.name}', status={self.status})>"
