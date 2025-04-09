# File: app/db/models/media_asset.py
"""
Media Asset database model for HideSync.

This module defines the MediaAsset model which represents digital media files
(images, videos, documents, etc.) stored in the system. It includes metadata about
the file such as size, type, location, and upload information.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, AbstractBase, TimestampMixin, TrackingMixin


class MediaAsset(AbstractBase, TimestampMixin, TrackingMixin):
    """
    MediaAsset model representing digital files stored in the system.

    This model stores metadata about files uploaded to the system, including
    their storage location, size, and type information.
    """

    __tablename__ = "media_assets"

    # Use UUID string as primary key instead of integer
    id = Column(String(36), primary_key=True)

    # File metadata
    file_name = Column(String(255), nullable=False, index=True)
    file_type = Column(String(50), nullable=False, index=True)
    storage_location = Column(String(512), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)

    # Upload information
    uploaded_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    uploaded_by = Column(String(100), nullable=False)

    # Relationships
    tags = relationship(
        "Tag", secondary="media_asset_tags", back_populates="media_assets"
    )

    def __repr__(self):
        return f"<MediaAsset(id='{self.id}', file_name='{self.file_name}')>"
