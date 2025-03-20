# File: app/db/models/file_metadata.py

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship, validates
from datetime import datetime
import uuid

from app.db.models.base import AbstractBase, TimestampMixin, ValidationMixin


class FileMetadata(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Metadata for files stored in the HideSync system.

    Tracks information about files stored in the file system, including
    original filename, storage path, size, and associations with entities.
    """

    __tablename__ = "file_meta_data"

    # File identification
    file_id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False, default=0)
    checksum = Column(String(255))  # For integrity verification

    # Storage information
    storage_path = Column(String(512), nullable=False)
    public_url = Column(String(512))
    thumbnail_path = Column(String(512))

    # Ownership and association
    entity_type = Column(String(50))  # Type of entity this file relates to
    entity_id = Column(String(50))  # ID of related entity
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    description = Column(Text)

    # Accessibility
    is_public = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Additional metadata
    meta_data = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="files")

    @validates("content_type")
    def validate_content_type(self, key, value):
        """Validate and normalize content type."""
        if not value:
            return "application/octet-stream"
        return value.lower()

    @validates("file_id")
    def validate_file_id(self, key, value):
        """Ensure file_id is a valid UUID."""
        if not value:
            return str(uuid.uuid4())
        try:
            uuid.UUID(value)
            return value
        except (ValueError, AttributeError):
            return str(uuid.uuid4())

    def to_dict(self):
        """Convert file metadata to dictionary."""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "size": self.size,
            "checksum": self.checksum,
            "storage_path": self.storage_path,
            "public_url": self.public_url,
            "thumbnail_path": self.thumbnail_path,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "description": self.description,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "meta_data": self.meta_data,
        }
