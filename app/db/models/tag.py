# app/db/models/tag.py
"""
Tag model for the HideSync system.

This module defines the Tag model for categorizing objects in the system,
along with translations to support multiple languages.
"""

import uuid
from sqlalchemy import Column, String, ForeignKey, Table, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, TimestampMixin

# Association table for materials and tags
material_tags = Table(
    "material_tags",
    Base.metadata,
    Column("material_id", Integer, ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for media assets and tags
media_asset_tags = Table(
    "media_asset_tags",
    Base.metadata,
    Column("media_asset_id", String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base, TimestampMixin):
    """
    Tag model for categorizing and organizing entities within the system.
    """
    __tablename__ = "tags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Relationships
    translations = relationship(
        "TagTranslation",
        back_populates="tag",
        cascade="all, delete-orphan"
    )

    # Media assets tagged with this tag
    media_assets = relationship(
        "MediaAsset",
        secondary=media_asset_tags,
        back_populates="tags"
    )

    # Materials tagged with this tag
    materials = relationship(
        "Material",
        secondary=material_tags,
        back_populates="tags"
    )

    def get_display_name(self, locale="en"):
        """Get the localized tag name."""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or original name
        return self.translations[0].name if self.translations else self.name

    def __repr__(self):
        return f"<Tag(id='{self.id}', name='{self.name}')>"


class TagTranslation(Base):
    """
    Translations for tags to support multiple languages.
    """
    __tablename__ = "tag_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_id = Column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)  # e.g., 'en', 'fr', 'es'
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Relationships
    tag = relationship("Tag", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tag_id', 'locale', name='uq_tag_translation'),
    )