# File: app/services/entity_media_service.py
from typing import List, Optional, Dict, Any
import uuid
import logging
from sqlalchemy.orm import Session

from app.repositories.entity_media_repository import EntityMediaRepository
from app.repositories.media_asset_repository import MediaAssetRepository
from app.db.models.entity_media import EntityMedia
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

logger = logging.getLogger(__name__)


class EntityMediaService:
    """Service for handling entity media operations."""

    def __init__(self, db: Session, encryption_service=None):
        """Initialize the service with database session and optional services."""
        self.db = db
        self.encryption_service = encryption_service
        self.entity_media_repository = EntityMediaRepository(db, encryption_service)
        self.media_asset_repository = MediaAssetRepository(db, encryption_service)

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[EntityMedia]:
        """
        Get all media associations for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity

        Returns:
            List of EntityMedia associations for the entity
        """
        try:
            # Fetch all entity media
            entity_media_list = self.entity_media_repository.get_by_entity(entity_type, entity_id)

            # Enhance with media asset data
            for entity_media in entity_media_list:
                if hasattr(entity_media, 'media_asset_id') and entity_media.media_asset_id:
                    try:
                        media_asset = self.media_asset_repository.get_by_id(entity_media.media_asset_id)
                        entity_media.media_asset = media_asset
                    except Exception as e:
                        logger.warning(f"Failed to fetch media asset {entity_media.media_asset_id}: {str(e)}")

            return entity_media_list
        except Exception as e:
            logger.error(f"Error fetching media for {entity_type} {entity_id}: {str(e)}")
            raise

    def get_thumbnail(self, entity_type: str, entity_id: str) -> Optional[EntityMedia]:
        """
        Get the thumbnail media association for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity

        Returns:
            The thumbnail EntityMedia association for the entity, or None if not found
        """
        try:
            # Fetch thumbnail
            thumbnail = self.entity_media_repository.get_thumbnail(entity_type, entity_id)

            # Enhance with media asset data if thumbnail exists
            if thumbnail and hasattr(thumbnail, 'media_asset_id') and thumbnail.media_asset_id:
                try:
                    media_asset = self.media_asset_repository.get_by_id(thumbnail.media_asset_id)
                    thumbnail.media_asset = media_asset
                except Exception as e:
                    logger.warning(f"Failed to fetch media asset {thumbnail.media_asset_id}: {str(e)}")

            return thumbnail
        except Exception as e:
            logger.error(f"Error fetching thumbnail for {entity_type} {entity_id}: {str(e)}")
            raise

    def get_by_id(self, id: str) -> Optional[EntityMedia]:
        """
        Get an entity media association by ID.

        Args:
            id: The ID of the entity media association

        Returns:
            The EntityMedia association, or None if not found
        """
        try:
            # Fetch entity media by ID
            entity_media = self.entity_media_repository.get_by_id(id)

            # Enhance with media asset data if it exists
            if entity_media and hasattr(entity_media, 'media_asset_id') and entity_media.media_asset_id:
                try:
                    media_asset = self.media_asset_repository.get_by_id(entity_media.media_asset_id)
                    entity_media.media_asset = media_asset
                except Exception as e:
                    logger.warning(f"Failed to fetch media asset {entity_media.media_asset_id}: {str(e)}")

            return entity_media
        except Exception as e:
            logger.error(f"Error fetching entity media {id}: {str(e)}")
            raise

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
        Update or create an entity media association.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity
            media_asset_id: The ID of the media asset
            media_type: The type of media association (thumbnail, gallery, etc.)
            display_order: The display order for the media
            caption: Optional caption for the media

        Returns:
            The updated or created EntityMedia association
        """
        try:
            # Validate that the media asset exists
            media_asset = self.media_asset_repository.get_by_id(media_asset_id)
            if not media_asset:
                raise EntityNotFoundException(f"Media asset {media_asset_id} not found")

            # Update or create the entity media association
            entity_media = self.entity_media_repository.update_entity_media(
                entity_type=entity_type,
                entity_id=entity_id,
                media_asset_id=media_asset_id,
                media_type=media_type,
                display_order=display_order,
                caption=caption
            )

            # Attach the media asset to the response
            entity_media.media_asset = media_asset

            return entity_media
        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error updating entity media: {str(e)}")
            raise BusinessRuleException(f"Failed to update entity media: {str(e)}")

    def delete_entity_media(self, id: str) -> bool:
        """
        Delete an entity media association by ID.

        Args:
            id: The ID of the entity media association

        Returns:
            True if the association was deleted, False otherwise
        """
        try:
            # First check if the entity media exists
            entity_media = self.entity_media_repository.get_by_id(id)
            if not entity_media:
                return False

            # Delete the entity media
            self.entity_media_repository.delete(id)
            return True
        except Exception as e:
            logger.error(f"Error deleting entity media {id}: {str(e)}")
            raise

    def remove_entity_media(self, entity_type: str, entity_id: str, media_type: Optional[str] = None) -> bool:
        """
        Remove media associations for an entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity
            media_type: Optional type of media to remove (if None, removes all)

        Returns:
            True if associations were removed, False otherwise
        """
        try:
            return self.entity_media_repository.remove_entity_media(entity_type, entity_id, media_type)
        except Exception as e:
            logger.error(f"Error removing media for {entity_type} {entity_id}: {str(e)}")
            raise