# File: app/schemas/shipment.py
"""
Shipment schemas for the HideSync API.

This module contains Pydantic models for shipments, providing validation
and serialization for the HideSync shipment management system.
"""

from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field, validator


class ShipmentBase(BaseModel):
    """
    Base schema for shipment data.

    Contains fields common to shipment creation, updates, and responses.
    """

    sale_id: int = Field(..., description="ID of the sale being shipped")
    shipping_method: Optional[str] = Field(None, description="Shipping method")
    tracking_number: Optional[str] = Field(None, description="Tracking number")
    shipping_cost: Optional[float] = Field(None, description="Cost of shipping", ge=0)


class ShipmentCreate(ShipmentBase):
    """
    Schema for creating a new shipment.
    """

    status: Optional[str] = Field("PENDING", description="Initial shipment status")
    ship_date: Optional[datetime] = Field(None, description="Date when shipped")

    @validator("shipping_cost")
    def shipping_cost_must_be_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Shipping cost cannot be negative")
        return v


class ShipmentUpdate(BaseModel):
    """
    Schema for updating a shipment.

    All fields are optional to allow partial updates.
    """

    shipping_method: Optional[str] = Field(None, description="Shipping method")
    tracking_number: Optional[str] = Field(None, description="Tracking number")
    shipping_cost: Optional[float] = Field(None, description="Cost of shipping", ge=0)
    status: Optional[str] = Field(None, description="Current shipment status")
    ship_date: Optional[datetime] = Field(None, description="Date when shipped")


class ShipmentShip(BaseModel):
    """
    Schema for marking a shipment as shipped.
    """

    tracking_number: str = Field(..., description="Tracking number")
    shipping_method: str = Field(..., description="Shipping method/carrier")
    shipping_cost: float = Field(..., description="Cost of shipping", ge=0)
    ship_date: Optional[datetime] = Field(None, description="Date when shipped")


class TrackingUpdate(BaseModel):
    """
    Schema for updating tracking information.
    """

    tracking_number: str = Field(..., description="New tracking number")
    shipping_provider: str = Field(..., description="Shipping provider/carrier")


class ShipmentInDB(ShipmentBase):
    """
    Schema for shipment information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the shipment")
    status: str = Field(..., description="Current shipment status")
    ship_date: Optional[datetime] = Field(None, description="Date when shipped")
    created_at: datetime = Field(
        ..., description="Timestamp when the shipment was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the shipment was last updated"
    )

    class Config:
        from_attributes = True


class ShipmentResponse(ShipmentInDB):
    """
    Schema for shipment responses in the API.
    """

    sale: Optional[Dict[str, Any]] = Field(
        None, description="Summary of the shipped sale"
    )
    customer_name: Optional[str] = Field(None, description="Name of the customer")
    days_since_shipped: Optional[int] = Field(
        None, description="Days elapsed since shipment"
    )
    tracking_url: Optional[str] = Field(None, description="URL to track the shipment")

    class Config:
        from_attributes = True
