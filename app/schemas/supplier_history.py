# File: app/schemas/supplier_history.py
"""
Supplier history schemas for the HideSync API.

This module contains Pydantic models for supplier history tracking, including
status changes, interactions, and other significant events.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SupplierHistoryBase(BaseModel):
    """
    Base schema for supplier history data.
    """

    supplier_id: int = Field(..., description="ID of the supplier")
    previous_status: str = Field(..., description="Previous status of the supplier")
    new_status: str = Field(..., description="New status of the supplier")
    reason: Optional[str] = Field(None, description="Reason for the status change")
    changed_by: Optional[int] = Field(None, description="ID of the user who made the change")


class SupplierHistoryCreate(SupplierHistoryBase):
    """
    Schema for creating a new supplier history entry.
    """
    pass


class SupplierHistoryUpdate(BaseModel):
    """
    Schema for updating supplier history information.

    All fields are optional to allow partial updates.
    """
    reason: Optional[str] = Field(None, description="Reason for the status change")


class SupplierHistoryInDB(SupplierHistoryBase):
    """
    Schema for supplier history information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the history entry")
    change_date: datetime = Field(..., description="Date when the status was changed")
    created_at: datetime = Field(..., description="Timestamp when the entry was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the entry was last updated")

    class Config:
        from_attributes = True


class SupplierHistoryResponse(SupplierHistoryInDB):
    """
    Schema for supplier history responses in the API.
    """
    pass


class SupplierEventBase(BaseModel):
    """
    Base schema for generic supplier event data.
    """
    supplier_id: int = Field(..., description="ID of the supplier")
    event_type: str = Field(..., description="Type of event (ORDER, RATING_CHANGE, etc.)")
    description: str = Field(..., description="Description of the event")
    reference_id: Optional[str] = Field(None, description="ID of a related entity (purchase order, etc.)")
    created_by: Optional[int] = Field(None, description="ID of the user who created the event")


class SupplierEventCreate(SupplierEventBase):
    """
    Schema for creating a new supplier event entry.
    """
    pass


class SupplierEventInDB(SupplierEventBase):
    """
    Schema for supplier event information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the event")
    created_at: datetime = Field(..., description="Timestamp when the event was created")

    class Config:
        from_attributes = True