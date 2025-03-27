# File: app/schemas/annotation.py
"""
Annotation schema definitions for HideSync.

This module defines Pydantic models for annotation data validation,
serialization, and documentation.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


class AnnotationBase(BaseModel):
    """Base class for annotation schemas with common fields."""

    entity_type: str = Field(
        ..., description="Type of entity this annotation is attached to"
    )
    entity_id: int = Field(
        ..., ge=1, description="ID of the entity this annotation is attached to"
    )
    content: str = Field(..., description="Annotation content")
    visibility: str = Field(
        "private", description="Annotation visibility (private, team, public)"
    )


class AnnotationCreate(AnnotationBase):
    """Schema for creating a new annotation."""

    tags: Optional[List[str]] = Field(
        None, description="List of tags for the annotation"
    )

    @validator("visibility")
    def validate_visibility(cls, v):
        allowed_values = ["private", "team", "public"]
        if v not in allowed_values:
            raise ValueError(f"Visibility must be one of {allowed_values}")
        return v


class AnnotationUpdate(BaseModel):
    """Schema for updating an annotation."""

    content: Optional[str] = Field(None, description="Updated annotation content")
    visibility: Optional[str] = Field(None, description="Updated annotation visibility")
    tags: Optional[List[str]] = Field(None, description="Updated list of tags")

    @validator("visibility")
    def validate_visibility(cls, v):
        if v is not None:
            allowed_values = ["private", "team", "public"]
            if v not in allowed_values:
                raise ValueError(f"Visibility must be one of {allowed_values}")
        return v

    class Config:
        """Configuration for the schema."""

        validate_assignment = True


class AnnotationInDBBase(AnnotationBase):
    """Base class for annotation schemas with database fields."""

    id: int
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    tags: Optional[List[str]] = None

    class Config:
        """Configuration for the schema."""

        orm_mode = True


class Annotation(AnnotationInDBBase):
    """Schema for annotation responses."""

    pass


class AnnotationSearchParams(BaseModel):
    """Schema for annotation search parameters."""

    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    created_by: Optional[int] = None
    search: Optional[str] = None
    visibility: Optional[str] = None
    tags: Optional[List[str]] = None
