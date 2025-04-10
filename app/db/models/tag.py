# File: app/db/models/tag.py
"""
Tag database model for HideSync.

This module defines the Tag model which represents categorization labels that can
be applied to various entities in the system, particularly media assets.
"""

import uuid  # <-- Import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

# Assuming AbstractBase and TimestampMixin are correctly defined in base.py
from app.db.models.base import AbstractBase, TimestampMixin


class Tag(AbstractBase, TimestampMixin):
    """
    Tag model for categorizing and labeling system entities.

    Tags can be applied to various entities in the system to enable
    filtering, organization, and improved searchability.
    """

    __tablename__ = "tags"

    # Use UUID string as primary key instead of integer
    # *** FIXED: Added default UUID generator ***
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Tag properties
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code (e.g., #FF5733)

    # created_at and updated_at are handled by TimestampMixin

    # Relationships
    # Assumes 'media_asset_tags' table and MediaAsset model are defined elsewhere
    # and use String(36) for their keys.
    media_assets = relationship(
        "MediaAsset", secondary="media_asset_tags", back_populates="tags"
    )

    def __repr__(self):
        # Use getattr for safety before ID is assigned during object creation
        return f"<Tag(id='{getattr(self, 'id', None)}', name='{self.name}')>"

    def to_dict(self):
        """Convert Tag instance to a dictionary."""
        # Assuming AbstractBase or TimestampMixin provides a base to_dict()
        result = super().to_dict() if hasattr(super(), "to_dict") else {}

        # Ensure essential fields are present if base to_dict is missing/incomplete
        # (id might be handled by AbstractBase.to_dict if it includes PK)
        if "id" not in result:
            result["id"] = self.id
        if "name" not in result:
            result["name"] = self.name
        if "description" not in result:
            result["description"] = self.description
        if "color" not in result:
            result["color"] = self.color

        # Ensure timestamps are ISO format strings if handled manually
        if "created_at" in result and isinstance(result["created_at"], datetime):
            result["created_at"] = result["created_at"].isoformat()
        if "updated_at" in result and isinstance(result["updated_at"], datetime):
            result["updated_at"] = result["updated_at"].isoformat()

        return result