# File: app/db/models/entity_media.py
"""
Entity Media model for associating media assets with various entities.

This module defines the EntityMedia model which creates a polymorphic
relationship between media assets and any entity type in the system.
"""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, TimestampMixin


class EntityMedia(Base, TimestampMixin):
    """
    Association model for connecting media assets to various entity types.
    """
    __tablename__ = "entity_media"

    # Primary key with UUID for easier external referencing
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Media asset reference
    media_asset_id = Column(String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)

    # Entity reference (polymorphic)
    entity_type = Column(String(50), nullable=False, index=True)  # 'material', 'product', etc.
    entity_id = Column(String(36), nullable=False, index=True)  # ID in the entity table

    # Media type and properties
    media_type = Column(String(50), default="image")  # 'image', 'document', 'video', etc.
    is_primary = Column(Boolean, default=False)  # Primary media for the entity
    display_order = Column(Integer, default=0)  # For ordering in galleries
    caption = Column(String(255))  # Optional caption

    # Relationships
    media_asset = relationship("MediaAsset")

    # Constraints to ensure only one primary media per entity
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "is_primary",
                         name="uq_entity_primary_media",
                         sqlite_where=is_primary),
        UniqueConstraint("entity_type", "entity_id", "media_asset_id",
                         name="uq_entity_media_asset"),
    )