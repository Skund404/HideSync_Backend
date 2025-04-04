# File: app/services/entity_media_service.py
from typing import List, Optional, Dict, Any
import uuid
import logging
from sqlalchemy.orm import Session
from datetime import datetime

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

    def find_by_media_asset_id(self, media_asset_id: str) -> List[EntityMedia]:
        """
        Find all entity media records associated with a specific media asset.

        Args:
            media_asset_id: The ID of the media asset

        Returns:
            List of EntityMedia associations for the media asset
        """
        try:
            # Use the repository method to find entity media records by media asset ID
            entity_media_list = self.entity_media_repository.find_by_media_asset_id(media_asset_id)

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
            logger.error(f"Error finding entity media for asset {media_asset_id}: {str(e)}")
            return []

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
            # Always ensure entity_id is a string
            entity_id_str = str(entity_id)

            # Fetch all entity media
            entity_media_list = self.entity_media_repository.get_by_entity(entity_type, entity_id_str)

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
            # Always ensure entity_id is a string
            entity_id_str = str(entity_id)

            # Fetch thumbnail
            thumbnail = self.entity_media_repository.get_thumbnail(entity_type, entity_id_str)

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
        Update or create an entity media association, with diagnostic info.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity
            media_asset_id: The ID of the media asset
            media_type: The type of media (default is "thumbnail")
            display_order: The display order of the media (default is 0)
            caption: Optional caption for the media

        Returns:
            The updated or created EntityMedia association
        """
        try:
            # Check if the media asset exists
            media_asset = self.media_asset_repository.get_by_id(media_asset_id)
            if not media_asset:
                raise EntityNotFoundException(f"Media asset {media_asset_id} not found")

            logger.info(f"Creating entity media with diagnostic approach: {entity_type}/{entity_id}/{media_type}")

            # Check for existing thumbnail first
            existing = None
            try:
                existing = self.get_thumbnail(entity_type, entity_id)
            except Exception as e:
                logger.warning(f"Error checking for existing thumbnail: {str(e)}")

            if existing:
                logger.info(f"Found existing thumbnail with ID {existing.id}, will try to update it")
                try:
                    # Update existing instead of creating new
                    existing.media_asset_id = media_asset_id
                    existing.display_order = display_order
                    existing.caption = caption
                    self.db.commit()
                    logger.info(f"Successfully updated existing thumbnail {existing.id}")
                    return existing
                except Exception as e:
                    logger.error(f"Error updating existing thumbnail: {str(e)}")
                    # Continue to create new

            # Use the diagnostic approach for creation
            result = self.entity_media_repository.create_entity_media_direct(
                entity_type=entity_type,
                entity_id=entity_id,
                media_asset_id=media_asset_id,
                media_type=media_type,
                display_order=display_order,
                caption=caption
            )

            if not result:
                raise Exception("Failed to create entity media")

            return result

        except EntityNotFoundException as e:
            # Re-raise entity not found exceptions
            logger.warning(f"Entity not found: {str(e)}")
            raise
        except Exception as e:
            # Log and re-raise other exceptions
            logger.error(f"Error updating entity media: {str(e)}", exc_info=True)
            raise

    def remove_entity_media(self, entity_type: str, entity_id: str, media_type: Optional[str] = None) -> bool:
        """
        Remove media associations for an entity, optionally filtered by media type.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity
            media_type: Optional type of media to remove (if None, removes all)

        Returns:
            True if any associations were removed, False otherwise
        """
        try:
            # Always ensure entity_id is a string for consistency
            entity_id_str = str(entity_id)

            logger.info(f"Removing media for {entity_type}/{entity_id_str}, media_type={media_type}")

            # Use the repository method
            return self.entity_media_repository.remove_entity_media(
                entity_type=entity_type,
                entity_id=entity_id_str,
                media_type=media_type
            )
        except Exception as e:
            logger.error(f"Error removing entity media for {entity_type} {entity_id}: {str(e)}", exc_info=True)
            raise

    def remove_entity_media_by_asset_id(self, media_asset_id: str) -> bool:
        """
        Remove all entity media associations for a specific media asset ID.

        Args:
            media_asset_id: The ID of the media asset to remove associations for

        Returns:
            bool: True if any associations were removed, False otherwise
        """
        try:
            # Query for all entity media records with the given media_asset_id
            entity_media_records = self.entity_media_repository.find_by_media_asset_id(media_asset_id)

            if not entity_media_records:
                logger.info(f"No entity media associations found for asset ID {media_asset_id}")
                return False

            # Delete each association
            count = 0
            for record in entity_media_records:
                self.entity_media_repository.delete(record.id)
                count += 1

            logger.info(f"Removed {count} entity media associations for media asset {media_asset_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing entity media for asset {media_asset_id}: {str(e)}", exc_info=True)
            raise