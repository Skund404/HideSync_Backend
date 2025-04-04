# File: app/db/models/entity_media.py
import uuid
from typing import Optional

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.models.base import Base, AbstractBase, TimestampMixin
from app.db.models.media_asset import MediaAsset

import logging


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


def update_entity_media(
        self,
        entity_type: str,
        entity_id: str,
        media_asset_id: str,
        media_type: str = "thumbnail",
        display_order: int = 0,
        caption: Optional[str] = None
) -> EntityMedia:
    """
    Update or create an entity media association based on the actual model definition.
    """
    try:
        # Always ensure entity_id is a string
        entity_id_str = str(entity_id)

        # Log the entity details for debugging
        logger.info(f"Working with entity: type={entity_type}, id={entity_id_str}, media_type={media_type}")

        # Check if the association already exists
        association = self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id_str,
            self.model.media_type == media_type
        ).first()

        if association:
            # Update existing association
            logger.info(f"Updating existing association with ID: {association.id}")
            association.media_asset_id = media_asset_id
            association.display_order = display_order
            association.caption = caption
            association.updated_at = datetime.now()
            self.session.commit()
            return association
        else:
            # Create a new entity media association with a UUID for the ID
            new_id = str(uuid.uuid4())
            logger.info(f"Creating new association with ID: {new_id}")

            # Create the entity media instance directly
            from app.db.models.entity_media import EntityMedia
            new_association = EntityMedia(
                id=new_id,
                media_asset_id=media_asset_id,
                entity_type=entity_type,
                entity_id=entity_id_str,  # Explicitly as string
                media_type=media_type,
                display_order=display_order,
                caption=caption,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # Add to session and commit
            self.session.add(new_association)
            self.session.commit()
            logger.info(f"Successfully created association with ID: {new_id}")

            return new_association
    except Exception as e:
        logger.error(f"Error in update_entity_media: {str(e)}", exc_info=True)
        self.session.rollback()
        raise