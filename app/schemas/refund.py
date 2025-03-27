# File: app/schemas/refund.py
"""
Refund schemas for the HideSync API.

This module contains Pydantic models for refunds, providing validation
and serialization for the HideSync refund management system.
"""

from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field, validator


class RefundBase(BaseModel):
    """
    Base schema for refund data.

    Contains fields common to refund creation, updates, and responses.
    """

    sale_id: int = Field(..., description="ID of the sale being refunded")
    refund_amount: float = Field(..., description="Amount to refund", gt=0)
    reason: str = Field(..., description="Reason for the refund")
    notes: Optional[str] = Field(None, description="Additional notes about the refund")


class RefundCreate(RefundBase):
    """
    Schema for creating a new refund.
    """

    transaction_id: Optional[str] = Field(None, description="External transaction ID")
    payment_method: Optional[str] = Field(
        None, description="Method used for the refund"
    )

    @validator("refund_amount")
    def refund_amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Refund amount must be positive")
        return v


class RefundUpdate(BaseModel):
    """
    Schema for updating a refund.

    All fields are optional to allow partial updates.
    """

    status: Optional[str] = Field(None, description="Current refund status")
    transaction_id: Optional[str] = Field(None, description="External transaction ID")
    payment_method: Optional[str] = Field(
        None, description="Method used for the refund"
    )
    notes: Optional[str] = Field(None, description="Additional notes about the refund")


class RefundProcess(BaseModel):
    """
    Schema for processing a refund.
    """

    transaction_id: str = Field(
        ..., description="Transaction ID from payment processor"
    )
    payment_method: str = Field(..., description="Method used for the refund")
    notes: Optional[str] = Field(
        None, description="Additional notes about the refund processing"
    )


class RefundCancel(BaseModel):
    """
    Schema for canceling a refund.
    """

    reason: str = Field(..., description="Reason for canceling the refund")


class RefundInDB(RefundBase):
    """
    Schema for refund information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the refund")
    refund_date: datetime = Field(..., description="Date when the refund was recorded")
    status: str = Field(..., description="Current refund status")
    transaction_id: Optional[str] = Field(None, description="External transaction ID")
    payment_method: Optional[str] = Field(
        None, description="Method used for the refund"
    )
    processed_by: Optional[int] = Field(
        None, description="ID of the user who processed the refund"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the refund was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the refund was last updated"
    )

    class Config:
        from_attributes = True


class RefundResponse(RefundInDB):
    """
    Schema for refund responses in the API.
    """

    sale: Optional[Dict[str, Any]] = Field(
        None, description="Summary of the refunded sale"
    )
    processor_name: Optional[str] = Field(
        None, description="Name of the user who processed the refund"
    )
    days_since_created: Optional[int] = Field(
        None, description="Days elapsed since the refund was created"
    )

    class Config:
        from_attributes = True
