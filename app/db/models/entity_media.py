# File: app/db/models/entity_media.py
import uuid
from typing import Optional

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, AbstractBase, TimestampMixin
from app.db.models.media_asset import MediaAsset

import logging
logger = logging.getLogger(__name__)

class EntityMedia(AbstractBase, TimestampMixin):
    """
    Association model that connects MediaAsset instances to various entity types.

    This model uses a polymorphic pattern to allow media assets to be associated
    with any entity type (Material, Tool, Supplier, etc.) using a discriminator.
    """
    __tablename__ = "entity_media"

    # Primary key
    id = Column(String(36), primary_key=True)

    # Media asset reference
    media_asset_id = Column(String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)

    # Entity reference (polymorphic)
    entity_type = Column(String(50), nullable=False, index=True)  # "material", "tool", "supplier", etc.
    entity_id = Column(String(36), nullable=False, index=True)

    # Relationship type
    media_type = Column(String(50), default="thumbnail")  # "thumbnail", "gallery", "document", etc.

    # Display order (for multiple images)
    display_order = Column(Integer, default=0)

    # Caption or description
    caption = Column(String(255))

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    media_asset = relationship("MediaAsset", backref="entity_associations")

    # Ensure entity + media asset + media type combination is unique
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "media_asset_id", "media_type", name="uq_entity_media_type"),
    )

    def __repr__(self):
        return f"<EntityMedia(id='{self.id}', entity_type='{self.entity_type}', entity_id='{self.entity_id}', media_type='{self.media_type}')>"


