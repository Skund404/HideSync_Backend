# File: app/schemas/supplier.py
"""
Supplier schemas for the HideSync API.

This module contains Pydantic models for supplier management, including suppliers,
supplier ratings, and supplier history.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, EmailStr, Field, validator

from app.db.models.enums import SupplierStatus


class SupplierBase(BaseModel):
    """
    Base schema for supplier data shared across different operations.
    """

    name: str = Field(
        ..., description="Name of the supplier", min_length=1, max_length=100
    )
    category: Optional[str] = Field(
        None, description="Primary category (LEATHER, HARDWARE, SUPPLIES, MIXED)"
    )
    contact_name: Optional[str] = Field(None, description="Name of primary contact")
    email: Optional[EmailStr] = Field(None, description="Email address of the supplier")
    phone: Optional[str] = Field(None, description="Phone number of the supplier")
    address: Optional[str] = Field(None, description="Physical address of the supplier")
    website: Optional[str] = Field(None, description="Website URL")
    rating: Optional[int] = Field(None, description="Rating from 1-5", ge=1, le=5)
    status: Optional[SupplierStatus] = Field(
        SupplierStatus.ACTIVE, description="Current status of the supplier"
    )
    notes: Optional[str] = Field(
        None, description="Additional notes about the supplier"
    )
    material_categories: Optional[List[str]] = Field(
        None, description="Categories of materials supplied"
    )
    logo: Optional[str] = Field(None, description="URL or path to supplier logo")
    payment_terms: Optional[str] = Field(
        None, description="Payment terms offered by the supplier"
    )
    min_order_amount: Optional[str] = Field(
        None, description="Minimum order amount if any"
    )
    lead_time: Optional[str] = Field(None, description="Typical lead time for orders")


class SupplierCreate(SupplierBase):
    """
    Schema for creating a new supplier.
    """

    @validator("phone")
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v is not None:
            # Remove non-digit characters for standardization
            digits_only = "".join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError("Phone number must have at least 10 digits")
        return v


class SupplierUpdate(BaseModel):
    """
    Schema for updating supplier information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Name of the supplier", min_length=1, max_length=100
    )
    category: Optional[str] = Field(
        None, description="Primary category (LEATHER, HARDWARE, SUPPLIES, MIXED)"
    )
    contact_name: Optional[str] = Field(None, description="Name of primary contact")
    email: Optional[EmailStr] = Field(None, description="Email address of the supplier")
    phone: Optional[str] = Field(None, description="Phone number of the supplier")
    address: Optional[str] = Field(None, description="Physical address of the supplier")
    website: Optional[str] = Field(None, description="Website URL")
    rating: Optional[int] = Field(None, description="Rating from 1-5", ge=1, le=5)
    status: Optional[SupplierStatus] = Field(
        None, description="Current status of the supplier"
    )
    notes: Optional[str] = Field(
        None, description="Additional notes about the supplier"
    )
    material_categories: Optional[List[str]] = Field(
        None, description="Categories of materials supplied"
    )
    logo: Optional[str] = Field(None, description="URL or path to supplier logo")
    payment_terms: Optional[str] = Field(
        None, description="Payment terms offered by the supplier"
    )
    min_order_amount: Optional[str] = Field(
        None, description="Minimum order amount if any"
    )
    lead_time: Optional[str] = Field(None, description="Typical lead time for orders")

    @validator("phone")
    def validate_phone(cls, v):
        """Validate phone number format if provided."""
        if v is not None:
            # Remove non-digit characters for standardization
            digits_only = "".join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError("Phone number must have at least 10 digits")
        return v


class SupplierInDB(SupplierBase):
    """
    Schema for supplier information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the supplier")
    created_at: datetime = Field(
        ..., description="Timestamp when the supplier was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the supplier was last updated"
    )
    last_order_date: Optional[str] = Field(
        None, description="Date of the most recent order"
    )

    class Config:
        from_attributes = True


class SupplierRatingBase(BaseModel):
    """
    Base schema for supplier rating data.
    """

    supplier_id: int = Field(..., description="ID of the supplier being rated")
    rating: int = Field(..., description="Rating value from 1-5", ge=1, le=5)
    category: Optional[str] = Field(
        None, description="Category being rated (quality, delivery, etc.)"
    )
    comments: Optional[str] = Field(None, description="Comments about the rating")


class SupplierRatingCreate(SupplierRatingBase):
    """
    Schema for creating a new supplier rating.
    """

    pass


class SupplierRatingUpdate(BaseModel):
    """
    Schema for updating supplier rating information.

    All fields are optional to allow partial updates.
    """

    rating: Optional[int] = Field(None, description="Rating value from 1-5", ge=1, le=5)
    category: Optional[str] = Field(
        None, description="Category being rated (quality, delivery, etc.)"
    )
    comments: Optional[str] = Field(None, description="Comments about the rating")


class SupplierRatingInDB(SupplierRatingBase):
    """
    Schema for supplier rating information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the rating")
    created_at: datetime = Field(
        ..., description="Timestamp when the rating was created"
    )

    class Config:
        from_attributes = True


class SupplierHistoryBase(BaseModel):
    """
    Base schema for supplier history data.
    """

    supplier_id: int = Field(..., description="ID of the supplier")
    event_type: str = Field(
        ..., description="Type of event (ORDER, STATUS_CHANGE, etc.)"
    )
    description: str = Field(..., description="Description of the event")
    reference_id: Optional[str] = Field(
        None, description="ID of a related entity (purchase order, etc.)"
    )


class SupplierHistoryCreate(SupplierHistoryBase):
    """
    Schema for creating a new supplier history entry.
    """

    pass


class SupplierHistoryInDB(SupplierHistoryBase):
    """
    Schema for supplier history information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the history entry")
    created_at: datetime = Field(
        ..., description="Timestamp when the entry was created"
    )

    class Config:
        from_attributes = True


class SupplierResponse(SupplierInDB):
    """
    Schema for supplier responses in the API.

    Extends the base schema with additional calculated or derived fields.
    """

    average_rating: Optional[float] = Field(
        None, description="Average rating across all categories"
    )
    total_orders: Optional[int] = Field(
        None, description="Total number of orders placed with this supplier"
    )
    total_spent: Optional[float] = Field(
        None, description="Total amount spent with this supplier"
    )
    reliability_score: Optional[float] = Field(
        None, description="Calculated reliability score"
    )
    days_since_last_order: Optional[int] = Field(
        None, description="Days since the last order was placed"
    )

    class Config:
        from_attributes = True


class SupplierDetailResponse(SupplierResponse):
    """
    Schema for detailed supplier responses in the API.

    Includes ratings and recent history in addition to supplier details.
    """

    ratings: List[SupplierRatingInDB] = Field(
        [], description="Recent ratings for this supplier"
    )
    history: List[SupplierHistoryInDB] = Field(
        [], description="Recent history entries for this supplier"
    )
    available_materials: Optional[List[Dict[str, Any]]] = Field(
        None, description="Materials available from this supplier"
    )

    class Config:
        from_attributes = True


class SupplierList(BaseModel):
    """
    Schema for paginated supplier list responses.
    """

    items: List[SupplierResponse]
    total: int = Field(..., description="Total number of suppliers matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")
