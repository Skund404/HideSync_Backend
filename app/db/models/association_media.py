# File: app/db/models/associations.py
"""
Association tables for HideSync.

This module defines association tables that represent many-to-many relationships
between various entities in the system. This includes the MediaAssetTag table
which associates media assets with tags.
"""

from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.models.base import Base, AbstractBase


class MediaAssetTag(AbstractBase):
    """
    Association model connecting MediaAsset and Tag entities.

    This model represents the many-to-many relationship between media assets
    and tags, allowing assets to be labeled with multiple tags and tags to be
    applied to multiple assets.
    """

    __tablename__ = "media_asset_tags"

    # Use UUID string as primary key instead of integer
    id = Column(String(36), primary_key=True)

    # Foreign keys
    media_asset_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_id = Column(
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ensure each tag is only applied once to each asset
    __table_args__ = (
        UniqueConstraint("media_asset_id", "tag_id", name="uq_media_asset_tag"),
    )

    def __repr__(self):
        return f"<MediaAssetTag(asset='{self.media_asset_id}', tag='{self.tag_id}')>"
