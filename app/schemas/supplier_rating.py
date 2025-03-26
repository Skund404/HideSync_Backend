# File: app/schemas/supplier_rating.py
"""
Supplier rating schemas for the HideSync API.

This module contains Pydantic models for supplier rating management, including
ratings by category, comments, and historical rating data.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator


class SupplierRatingBase(BaseModel):
    """
    Base schema for supplier rating data.
    """
    supplier_id: int = Field(..., description="ID of the supplier being rated")
    previous_rating: int = Field(..., description="Previous rating value")
    new_rating: int = Field(..., description="New rating value from 1-5", ge=1, le=5)
    comments: Optional[str] = Field(None, description="Comments explaining the rating")
    rated_by: Optional[int] = Field(None, description="ID of the user who rated the supplier")


class SupplierRatingCreate(BaseModel):
    """
    Schema for creating a new supplier rating.
    """
    rating: int = Field(..., description="Rating value from 1-5", ge=1, le=5)
    comments: Optional[str] = Field(None, description="Comments explaining the rating")

    @validator("rating")
    def validate_rating(cls, v):
        """Validate rating is within the allowed range."""
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class SupplierRatingUpdate(BaseModel):
    """
    Schema for updating supplier rating information.

    All fields are optional to allow partial updates.
    """
    rating: Optional[int] = Field(None, description="Rating value from 1-5", ge=1, le=5)
    comments: Optional[str] = Field(None, description="Comments explaining the rating")

    @validator("rating")
    def validate_rating(cls, v):
        """Validate rating is within the allowed range if provided."""
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class SupplierRatingInDB(SupplierRatingBase):
    """
    Schema for supplier rating information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the rating")
    rating_date: datetime = Field(..., description="Date when the rating was given")
    created_at: datetime = Field(..., description="Timestamp when the record was created")

    class Config:
        from_attributes = True


class SupplierRatingResponse(SupplierRatingInDB):
    """
    Schema for supplier rating responses in the API.
    """
    pass


class SupplierRatingStatistics(BaseModel):
    """
    Schema for supplier rating statistics.
    """
    average_rating: float = Field(..., description="Average rating value")
    rating_count: int = Field(..., description="Total number of ratings")
    distribution: Dict[int, int] = Field(..., description="Distribution of ratings by value")
    recent_ratings: List[SupplierRatingResponse] = Field([], description="Most recent ratings")
    trend: str = Field("stable", description="Rating trend (improving, declining, stable)")


class SupplierRatingSummary(BaseModel):
    """
    Schema for summarized supplier rating information.
    """
    supplier_id: int = Field(..., description="ID of the supplier")
    current_rating: int = Field(..., description="Current overall rating")
    statistics: SupplierRatingStatistics = Field(..., description="Rating statistics")