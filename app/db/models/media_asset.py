# File: app/db/models/media_asset.py
"""
Media Asset database model for HideSync.

This module defines the MediaAsset model representing digital files
stored in the system, such as images, documents, and other media.
"""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, TimestampMixin
from app.db.models.tag import media_asset_tags


class MediaAsset(Base, TimestampMixin):
    """
    MediaAsset model representing digital files stored in the system.
    """
    __tablename__ = "media_assets"

    # Use UUID for media assets to allow easier external references
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # File metadata
    file_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # mime type or category
    content_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    storage_location = Column(String(512), nullable=False)  # Path or URI

    # Media attributes
    width = Column(Integer)  # For images and videos
    height = Column(Integer)  # For images and videos
    duration = Column(Integer)  # For audio/video in seconds
    thumbnail = Column(String(255))  # Path to thumbnail if applicable
    alt_text = Column(String(255))  # Accessibility description
    description = Column(Text)

    # Upload information
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id"))

    # Tags relationship - from media_asset_tags association table
    tags = relationship(
        "Tag",
        secondary=media_asset_tags,
        back_populates="media_assets"
    )

    def __repr__(self):
        return f"<MediaAsset(id='{self.id}', file_name='{self.file_name}')>"