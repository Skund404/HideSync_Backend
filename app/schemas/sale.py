# File: app/schemas/sale.py
"""
Sale schemas for the HideSync API.

This module contains Pydantic models for sales and sale items, providing validation
and serialization for the HideSync sales management system.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, root_validator
from uuid import UUID

from app.db.models.enums import SaleStatus, PaymentStatus, FulfillmentStatus


class SaleItemBase(BaseModel):
    """
    Base schema for sale item data.

    Contains fields common to sale item creation, updates, and responses.
    """
    quantity: int = Field(..., description="Quantity of items", gt=0)
    price: float = Field(..., description="Price per unit", ge=0)
    name: str = Field(..., description="Item name or description")
    type: Optional[str] = Field(None, description="Item type (CUSTOM, PRODUCTION, etc.)")
    sku: Optional[str] = Field(None, description="Stock keeping unit identifier")
    product_id: Optional[int] = Field(None, description="Reference to a product if applicable")
    project_id: Optional[int] = Field(None, description="Reference to a project if applicable")
    pattern_id: Optional[int] = Field(None, description="Reference to a pattern if applicable")
    notes: Optional[str] = Field(None, description="Additional notes about the item")


class SaleItemCreate(SaleItemBase):
    """
    Schema for creating a new sale item.
    """
    tax: Optional[float] = Field(0.0, description="Tax amount for this item")

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @validator('price')
    def price_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError('Price cannot be negative')
        return v


class SaleItemUpdate(BaseModel):
    """
    Schema for updating a sale item.

    All fields are optional to allow partial updates.
    """
    quantity: Optional[int] = Field(None, description="Quantity of items", gt=0)
    price: Optional[float] = Field(None, description="Price per unit", ge=0)
    tax: Optional[float] = Field(None, description="Tax amount for this item")
    name: Optional[str] = Field(None, description="Item name or description")
    type: Optional[str] = Field(None, description="Item type (CUSTOM, PRODUCTION, etc.)")
    sku: Optional[str] = Field(None, description="Stock keeping unit identifier")
    product_id: Optional[int] = Field(None, description="Reference to a product if applicable")
    project_id: Optional[int] = Field(None, description="Reference to a project if applicable")
    pattern_id: Optional[int] = Field(None, description="Reference to a pattern if applicable")
    notes: Optional[str] = Field(None, description="Additional notes about the item")


class SaleItemInDB(SaleItemBase):
    """
    Schema for sale item information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the sale item")
    sale_id: int = Field(..., description="ID of the sale this item belongs to")
    tax: float = Field(..., description="Tax amount for this item")

    class Config:
        orm_mode = True


class SaleBase(BaseModel):
    """
    Base schema for sale data shared across different operations.
    """
    customer_id: int = Field(..., description="ID of the customer making the purchase")
    due_date: Optional[datetime] = Field(None, description="Due date for the order")
    subtotal: Optional[float] = Field(None, description="Subtotal amount before taxes and fees")
    taxes: Optional[float] = Field(None, description="Tax amount")
    shipping: Optional[float] = Field(None, description="Shipping cost")
    platform_fees: Optional[float] = Field(None, description="Fees from selling platforms")
    total_amount: Optional[float] = Field(None, description="Total order amount")
    net_revenue: Optional[float] = Field(None, description="Net revenue after fees")
    deposit_amount: Optional[float] = Field(None, description="Initial deposit amount")
    balance_due: Optional[float] = Field(None, description="Remaining balance to be paid")
    status: Optional[SaleStatus] = Field(None, description="Current status of the sale")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status")
    fulfillment_status: Optional[FulfillmentStatus] = Field(None, description="Fulfillment status")
    channel: Optional[str] = Field(None, description="Sales channel (e.g., SHOPIFY, ETSY, DIRECT)")
    platform_order_id: Optional[str] = Field(None, description="Order ID from external platform")
    marketplace_data: Optional[Dict[str, Any]] = Field(None, description="Additional data from marketplaces")
    shipping_method: Optional[str] = Field(None, description="Method of shipping")
    shipping_provider: Optional[str] = Field(None, description="Shipping provider")
    tracking_number: Optional[str] = Field(None, description="Tracking number for the shipment")
    tags: Optional[List[str]] = Field(None, description="Tags associated with the sale")
    notes: Optional[str] = Field(None, description="Additional notes about the sale")
    customization: Optional[str] = Field(None, description="Custom instructions or specifications")


class SaleCreate(SaleBase):
    """
    Schema for creating a new sale.
    """
    items: List[SaleItemCreate] = Field(..., description="Items included in the sale")
    status: SaleStatus = Field(SaleStatus.INQUIRY, description="Initial status of the sale")
    payment_status: PaymentStatus = Field(PaymentStatus.PENDING, description="Initial payment status")
    fulfillment_status: FulfillmentStatus = Field(FulfillmentStatus.PENDING, description="Initial fulfillment status")

    @root_validator
    def calculate_totals(cls, values):
        """
        Calculate totals based on item prices and quantities if not provided.
        """
        if values.get('items') and (values.get('subtotal') is None or values.get('total_amount') is None):
            items = values.get('items', [])
            subtotal = sum(item.price * item.quantity for item in items)

            # Set subtotal if not provided
            if values.get('subtotal') is None:
                values['subtotal'] = subtotal

            # Calculate total if not provided
            if values.get('total_amount') is None:
                taxes = values.get('taxes', 0) or 0
                shipping = values.get('shipping', 0) or 0
                platform_fees = values.get('platform_fees', 0) or 0

                values['total_amount'] = subtotal + taxes + shipping + platform_fees

            # Calculate balance due if not provided
            if values.get('balance_due') is None:
                total = values.get('total_amount', 0)
                deposit = values.get('deposit_amount', 0) or 0
                values['balance_due'] = total - deposit

        return values


class SaleUpdate(BaseModel):
    """
    Schema for updating sale information.

    All fields are optional to allow partial updates.
    """
    customer_id: Optional[int] = Field(None, description="ID of the customer making the purchase")
    due_date: Optional[datetime] = Field(None, description="Due date for the order")
    completed_date: Optional[datetime] = Field(None, description="Date when the order was completed")
    subtotal: Optional[float] = Field(None, description="Subtotal amount before taxes and fees")
    taxes: Optional[float] = Field(None, description="Tax amount")
    shipping: Optional[float] = Field(None, description="Shipping cost")
    platform_fees: Optional[float] = Field(None, description="Fees from selling platforms")
    total_amount: Optional[float] = Field(None, description="Total order amount")
    net_revenue: Optional[float] = Field(None, description="Net revenue after fees")
    deposit_amount: Optional[float] = Field(None, description="Initial deposit amount")
    balance_due: Optional[float] = Field(None, description="Remaining balance to be paid")
    status: Optional[SaleStatus] = Field(None, description="Current status of the sale")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status")
    fulfillment_status: Optional[FulfillmentStatus] = Field(None, description="Fulfillment status")
    channel: Optional[str] = Field(None, description="Sales channel (e.g., SHOPIFY, ETSY, DIRECT)")
    platform_order_id: Optional[str] = Field(None, description="Order ID from external platform")
    marketplace_data: Optional[Dict[str, Any]] = Field(None, description="Additional data from marketplaces")
    shipping_method: Optional[str] = Field(None, description="Method of shipping")
    shipping_provider: Optional[str] = Field(None, description="Shipping provider")
    tracking_number: Optional[str] = Field(None, description="Tracking number for the shipment")
    tags: Optional[List[str]] = Field(None, description="Tags associated with the sale")
    notes: Optional[str] = Field(None, description="Additional notes about the sale")
    customization: Optional[str] = Field(None, description="Custom instructions or specifications")

    @root_validator
    def update_balance_due(cls, values):
        """
        Recalculate balance due if relevant fields are updated.
        """
        # Check if we're updating financial values
        financial_updates = any(values.get(field) is not None for field in
                                ['total_amount', 'deposit_amount'])

        if financial_updates:
            total = values.get('total_amount')
            deposit = values.get('deposit_amount')

            # Only recalculate if we have both values
            if total is not None and deposit is not None:
                values['balance_due'] = total - deposit

        return values


class SaleItemResponse(SaleItemInDB):
    """
    Schema for sale item responses in the API.
    """
    # Can include additional derived fields here
    line_total: float = Field(..., description="Total price for this line item (price × quantity)")

    class Config:
        orm_mode = True


class SaleInDB(SaleBase):
    """
    Schema for sale information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the sale")
    created_at: datetime = Field(..., description="Timestamp when the sale was created")
    completed_date: Optional[datetime] = Field(None, description="Date when the order was completed")
    updated_at: datetime = Field(..., description="Timestamp when the sale was last updated")

    class Config:
        orm_mode = True


class SaleResponse(SaleInDB):
    """
    Schema for sale responses in the API.
    """
    items: List[SaleItemResponse] = Field(..., description="Items included in the sale")
    customer_name: Optional[str] = Field(None, description="Name of the customer")
    days_since_creation: Optional[int] = Field(None, description="Days elapsed since the sale was created")

    class Config:
        orm_mode = True


class SaleList(BaseModel):
    """
    Schema for paginated sale list responses.
    """
    items: List[SaleResponse]
    total: int = Field(..., description="Total number of sales matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")