# File: app/db/models/tag.py
"""
Tag database model for HideSync.

This module defines the Tag model which represents categorization labels that can
be applied to various entities in the system, particularly media assets.
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, AbstractBase, TimestampMixin


class Tag(AbstractBase, TimestampMixin):
    """
    Tag model for categorizing and labeling system entities.

    Tags can be applied to various entities in the system to enable
    filtering, organization, and improved searchability.
    """

    __tablename__ = "tags"

    # Use UUID string as primary key instead of integer
    id = Column(String(36), primary_key=True)

    # Tag properties
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code (e.g., #FF5733)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    media_assets = relationship(
        "MediaAsset",
        secondary="media_asset_tags",
        back_populates="tags"
    )

    def __repr__(self):
        return f"<Tag(id='{self.id}', name='{self.name}')>"