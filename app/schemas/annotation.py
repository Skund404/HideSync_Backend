# File: app/schemas/annotation.py
"""
Annotation schema definitions for HideSync.

This module defines Pydantic models for annotation data validation,
serialization, and documentation.
"""

from typing import Optional, List
from datetime import datetime
# Import necessary components from Pydantic v2
from pydantic import BaseModel, Field, ConfigDict, field_validator


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

    # Updated validator syntax for Pydantic v2
    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        allowed_values = ["private", "team", "public"]
        if v not in allowed_values:
            raise ValueError(f"Visibility must be one of {allowed_values}")
        return v


class AnnotationUpdate(BaseModel):
    """Schema for updating an annotation."""

    content: Optional[str] = Field(None, description="Updated annotation content")
    visibility: Optional[str] = Field(None, description="Updated annotation visibility")
    tags: Optional[List[str]] = Field(None, description="Updated list of tags")

    # Updated validator syntax for Pydantic v2
    @field_validator("visibility")
    @classmethod
    def validate_visibility_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed_values = ["private", "team", "public"]
            if v not in allowed_values:
                raise ValueError(f"Visibility must be one of {allowed_values}")
        return v

    # Pydantic v2 config (validate_assignment is True by default if needed)
    model_config = ConfigDict(
        validate_assignment=True,
        # Add other settings if needed, e.g., extra='ignore'
    )


class AnnotationInDBBase(AnnotationBase):
    """Base class for annotation schemas with database fields."""

    id: int
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    tags: Optional[List[str]] = None

    # Pydantic v2 config to enable reading from ORM attributes
    model_config = ConfigDict(
        from_attributes=True,
    )


class Annotation(AnnotationInDBBase):
    """Schema for annotation responses."""

    # Inherits model_config from AnnotationInDBBase
    pass


class AnnotationSearchParams(BaseModel):
    """Schema for annotation search parameters."""

    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    created_by: Optional[int] = None
    search: Optional[str] = None # Renamed from content_search for consistency? Check usage
    visibility: Optional[str] = None
    tags: Optional[List[str]] = None

    # No ORM mode needed here as it's for input parameters
