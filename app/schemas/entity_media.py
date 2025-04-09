# File: app/schemas/entity_media.py
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.media_asset import MediaAssetResponse


class EntityMediaBase(BaseModel):
    """Base schema for entity media associations."""

    entity_type: str = Field(
        ..., description="Type of entity (material, tool, supplier, etc.)"
    )
    entity_id: str = Field(..., description="ID of the entity")
    media_asset_id: str = Field(..., description="ID of the media asset")
    media_type: str = Field(
        "thumbnail", description="Type of media (thumbnail, gallery, etc.)"
    )
    display_order: int = Field(0, description="Display order for the media")
    caption: Optional[str] = Field(None, description="Optional caption or description")


class EntityMediaCreate(EntityMediaBase):
    """Schema for creating a new entity media association."""

    pass


class EntityMediaUpdate(BaseModel):
    """Schema for updating an entity media association."""

    media_asset_id: Optional[str] = Field(None, description="ID of the media asset")
    media_type: Optional[str] = Field(
        None, description="Type of media (thumbnail, gallery, etc.)"
    )
    display_order: Optional[int] = Field(
        None, description="Display order for the media"
    )
    caption: Optional[str] = Field(None, description="Optional caption or description")


class EntityMediaInDB(EntityMediaBase):
    """Schema for entity media data as stored in the database."""

    id: str = Field(..., description="Unique ID of the entity media association")
    created_at: datetime = Field(
        ..., description="Timestamp when the association was created"
    )

    class Config:
        orm_mode = True


class EntityMediaResponse(EntityMediaInDB):
    """Schema for entity media response, including the associated media asset."""

    media_asset: Optional[MediaAssetResponse] = Field(
        None, description="The associated media asset"
    )


class EntityMediaListResponse(BaseModel):
    """Schema for a paginated list of entity media associations."""

    items: List[EntityMediaResponse]
    total: int
    page: int
    size: int
    pages: int
