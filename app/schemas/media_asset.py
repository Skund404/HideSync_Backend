# File: app/schemas/media_asset.py
"""
Schemas for MediaAsset entities in the HideSync API.

This module provides Pydantic models for validating and serializing
media asset data throughout the API layer.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid

from app.schemas.tag import TagResponse


class MediaAssetBase(BaseModel):
    """
    Base schema with common media asset attributes.
    """
    file_name: str = Field(..., description="Name of the file")
    file_type: str = Field(..., description="Type or extension of the file")
    content_type: str = Field(..., description="MIME type of the file")


class MediaAssetCreate(MediaAssetBase):
    """
    Schema for creating a new media asset.

    Storage location and file size are typically determined after upload,
    not in the initial request.
    """
    uploaded_by: str = Field(..., description="User who uploaded the file")
    tag_ids: Optional[List[str]] = Field(default=None, description="List of tag IDs to assign")

    @validator('file_name')
    def validate_file_name(cls, v):
        if len(v) > 255:
            raise ValueError("File name cannot exceed 255 characters")
        return v

    @validator('file_type')
    def validate_file_type(cls, v):
        allowed_types = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.csv', '.xlsx', '.svg']
        if not any(v.lower().endswith(ext) for ext in allowed_types):
            raise ValueError(f"File type must be one of {', '.join(allowed_types)}")
        return v


class MediaAssetUpdate(BaseModel):
    """
    Schema for updating an existing media asset.

    All fields are optional to allow partial updates.
    """
    file_name: Optional[str] = Field(None, description="Name of the file")
    tag_ids: Optional[List[str]] = Field(None, description="List of tag IDs to assign")


class MediaAssetResponse(MediaAssetBase):
    """
    Schema for media asset responses from the API.
    """
    id: str = Field(..., description="Unique identifier for the media asset")
    storage_location: str = Field(..., description="Location where the file is stored")
    file_size_bytes: int = Field(..., description="Size of the file in bytes")
    uploaded_at: datetime = Field(..., description="When the file was uploaded")
    uploaded_by: str = Field(..., description="User who uploaded the file")
    created_at: datetime = Field(..., description="When the record was created")
    updated_at: datetime = Field(..., description="When the record was last updated")
    tags: Optional[List[TagResponse]] = Field(None, description="Tags assigned to this asset")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MediaAssetWithTags(MediaAssetResponse):
    """
    Schema for media asset with eagerly loaded tags.
    """
    tags: List[TagResponse] = Field(default_factory=list, description="Tags assigned to this asset")


class MediaAssetListResponse(BaseModel):
    """
    Schema for paginated list of media assets.
    """
    items: List[MediaAssetResponse] = Field(..., description="List of media assets")
    total: int = Field(..., description="Total number of assets matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class MediaAssetSearchParams(BaseModel):
    """
    Schema for media asset search parameters.
    """
    file_name: Optional[str] = Field(None, description="Search by file name")
    file_type: Optional[str] = Field(None, description="Filter by file type/extension")
    tag_ids: Optional[List[str]] = Field(None, description="Filter by tag IDs")
    uploaded_by: Optional[str] = Field(None, description="Filter by uploader")
    uploaded_after: Optional[datetime] = Field(None, description="Filter by upload date (after)")
    uploaded_before: Optional[datetime] = Field(None, description="Filter by upload date (before)")
    search: Optional[str] = Field(None, description="General search term")


class MediaAssetUploadComplete(BaseModel):
    """
    Schema for completing a media asset upload.
    """
    storage_location: str = Field(..., description="Where the file is stored")
    file_size_bytes: int = Field(..., description="Size of the file in bytes")
    content_type: str = Field(..., description="MIME type of the file")