# File: app/schemas/tag.py
"""
Schemas for Tag entities in the HideSync API.

This module provides Pydantic models for validating and serializing
tag data throughout the API layer.
"""

from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re
import uuid


class TagBase(BaseModel):
    """
    Base schema with common tag attributes.
    """
    name: str = Field(..., description="Name of the tag")
    description: Optional[str] = Field(None, description="Description of the tag")
    color: Optional[str] = Field(None, description="Color code for the tag (hex format)")


class TagCreate(TagBase):
    """
    Schema for creating a new tag.
    """

    @validator('name')
    def validate_name(cls, v):
        if len(v) > 100:
            raise ValueError("Tag name cannot exceed 100 characters")
        return v

    @validator('color')
    def validate_color(cls, v):
        if v is not None:
            hex_pattern = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
            if not hex_pattern.match(v):
                raise ValueError("Color must be a valid hex code (e.g., #FF5733)")
        return v


class TagUpdate(BaseModel):
    """
    Schema for updating an existing tag.

    All fields are optional to allow partial updates.
    """
    name: Optional[str] = Field(None, description="Name of the tag")
    description: Optional[str] = Field(None, description="Description of the tag")
    color: Optional[str] = Field(None, description="Color code for the tag (hex format)")

    @validator('name')
    def validate_name(cls, v):
        if v is not None and len(v) > 100:
            raise ValueError("Tag name cannot exceed 100 characters")
        return v

    @validator('color')
    def validate_color(cls, v):
        if v is not None:
            hex_pattern = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
            if not hex_pattern.match(v):
                raise ValueError("Color must be a valid hex code (e.g., #FF5733)")
        return v


class TagResponse(TagBase):
    """
    Schema for tag responses from the API.
    """
    id: str = Field(..., description="Unique identifier for the tag")
    created_at: datetime = Field(..., description="When the tag was created")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TagListResponse(BaseModel):
    """
    Schema for paginated list of tags.
    """
    items: List[TagResponse] = Field(..., description="List of tags")
    total: int = Field(..., description="Total number of tags matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class TagSearchParams(BaseModel):
    """
    Schema for tag search parameters.
    """
    name: Optional[str] = Field(None, description="Search by tag name")
    search: Optional[str] = Field(None, description="General search term")