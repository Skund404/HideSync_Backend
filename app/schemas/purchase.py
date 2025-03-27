# File: app/schemas/purchase.py
"""
Purchase data schemas for the HideSync API.

This module defines Pydantic models for validating purchase-related requests
and responses, ensuring consistent data handling across the API.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, validator, root_validator

from app.db.models.enums import PurchaseStatus, PaymentStatus


# Base Models
class PurchaseItemBase(BaseModel):
    """Base model for purchase items."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Item name/description"
    )
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    price: float = Field(..., ge=0, description="Unit price")
    item_type: Optional[str] = Field(
        None, max_length=50, description="Type of item (material, tool, etc.)"
    )
    material_type: Optional[str] = Field(
        None, max_length=50, description="Type of material"
    )
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measurement")
    notes: Optional[str] = Field(None, description="Additional notes")

    @root_validator
    def calculate_total(cls, values):
        """Calculate total based on price and quantity."""
        price = values.get("price")
        quantity = values.get("quantity")
        if price is not None and quantity is not None:
            values["total"] = price * quantity
        return values


class PurchaseBase(BaseModel):
    """Base model for purchases."""

    supplier_id: int = Field(..., gt=0, description="ID of the associated supplier")
    supplier: Optional[str] = Field(
        None, max_length=255, description="Name of the supplier (denormalized)"
    )
    date: Optional[datetime] = Field(None, description="Order creation date")
    delivery_date: Optional[datetime] = Field(
        None, description="Expected delivery date"
    )
    status: Optional[str] = Field(None, description="Purchase order status")
    payment_status: Optional[str] = Field(None, description="Payment status")
    notes: Optional[str] = Field(None, description="Additional notes")
    invoice: Optional[str] = Field(
        None, max_length=100, description="Invoice reference"
    )


# Create Models
class PurchaseItemCreate(PurchaseItemBase):
    """Model for creating purchase items."""

    material_id: Optional[int] = Field(
        None, gt=0, description="ID of the associated material"
    )


class PurchaseCreate(PurchaseBase):
    """Model for creating purchases."""

    items: Optional[List[PurchaseItemCreate]] = Field(
        None, description="Purchase order items"
    )


# Update Models
class PurchaseItemUpdate(BaseModel):
    """Model for updating purchase items."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Item name/description"
    )
    quantity: Optional[int] = Field(None, gt=0, description="Quantity ordered")
    price: Optional[float] = Field(None, ge=0, description="Unit price")
    item_type: Optional[str] = Field(
        None, max_length=50, description="Type of item (material, tool, etc.)"
    )
    material_type: Optional[str] = Field(
        None, max_length=50, description="Type of material"
    )
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measurement")
    notes: Optional[str] = Field(None, description="Additional notes")
    material_id: Optional[int] = Field(
        None, gt=0, description="ID of the associated material"
    )

    @root_validator
    def calculate_total(cls, values):
        """Calculate total if price or quantity is updated."""
        price = values.get("price")
        quantity = values.get("quantity")
        if price is not None and quantity is not None:
            values["total"] = price * quantity
        return values


class PurchaseUpdate(BaseModel):
    """Model for updating purchases."""

    supplier_id: Optional[int] = Field(
        None, gt=0, description="ID of the associated supplier"
    )
    supplier: Optional[str] = Field(
        None, max_length=255, description="Name of the supplier (denormalized)"
    )
    date: Optional[datetime] = Field(None, description="Order creation date")
    delivery_date: Optional[datetime] = Field(
        None, description="Expected delivery date"
    )
    status: Optional[str] = Field(None, description="Purchase order status")
    payment_status: Optional[str] = Field(None, description="Payment status")
    notes: Optional[str] = Field(None, description="Additional notes")
    invoice: Optional[str] = Field(
        None, max_length=100, description="Invoice reference"
    )


# Response Models
class PurchaseItemResponse(PurchaseItemBase):
    """Response model for purchase items."""

    id: int
    purchase_id: int
    total: float
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
        from_attributes = True


class PurchaseResponse(PurchaseBase):
    """Response model for purchases."""

    id: str
    total: float
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    is_overdue: bool
    days_outstanding: Optional[int]
    items: Optional[List[PurchaseItemResponse]]

    class Config:
        orm_mode = True
        from_attributes = True


# List Response Models
class PurchaseItemListResponse(BaseModel):
    """Response model for lists of purchase items."""

    items: List[PurchaseItemResponse]
    total: int


class PurchaseListResponse(BaseModel):
    """Response model for lists of purchases."""

    items: List[PurchaseResponse]
    total: int
    skip: int
    limit: int


# Additional Models for Purchase Management
class PurchaseReceiveItemData(BaseModel):
    """Model for receiving a purchase item."""

    item_id: int = Field(..., gt=0, description="ID of the purchase item")
    quantity_received: int = Field(..., gt=0, description="Quantity received")
    quality_check: Optional[bool] = Field(
        True, description="Whether quality check passed"
    )
    notes: Optional[str] = Field(None, description="Additional notes")


class PurchaseReceiveData(BaseModel):
    """Model for receiving a purchase."""

    items: List[PurchaseReceiveItemData] = Field(
        ..., min_items=1, description="Items received"
    )
    receipt_date: Optional[datetime] = Field(None, description="Date of receipt")
    receipt_number: Optional[str] = Field(
        None, max_length=100, description="Receipt reference number"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
