# File: app/services/entity_media_service.py
from typing import List, Optional, Dict, Any
import uuid
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone  # Added timezone

from app.repositories.entity_media_repository import EntityMediaRepository
from app.repositories.media_asset_repository import MediaAssetRepository
from app.db.models.entity_media import EntityMedia
from app.db.models.media_asset import MediaAsset  # Import MediaAsset for type hinting
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

    def _get_media_asset(self, media_asset_id: str) -> Optional[MediaAsset]:
        """Helper to safely get media asset, returns None if not found or error."""
        try:
            return self.media_asset_repository.get_by_id(media_asset_id)
        except Exception as e:
            logger.warning(f"Failed to fetch media asset {media_asset_id}: {str(e)}")
            return None

    def _attach_media_asset(
        self, entity_media_list: List[EntityMedia]
    ) -> List[EntityMedia]:
        """Helper to attach media asset details to a list of EntityMedia."""
        for entity_media in entity_media_list:
            if hasattr(entity_media, "media_asset_id") and entity_media.media_asset_id:
                # Use helper to safely fetch
                media_asset = self._get_media_asset(entity_media.media_asset_id)
                # Attach even if None, so frontend knows it was attempted
                entity_media.media_asset = media_asset
        return entity_media_list

    def delete_entity_media(self, id: str) -> bool:
        """
        Delete an entity media association by its own ID.

        Args:
            id: The ID of the EntityMedia record to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        try:
            # Use the repository's generic delete method
            success = self.entity_media_repository.delete(id)
            if success:
                # Commit is handled by the BaseRepository's delete method if successful
                # self.db.commit() # No explicit commit needed here if repo handles it
                logger.info(f"Successfully deleted entity media record {id}")
            else:
                logger.warning(f"Entity media record {id} not found for deletion.")
            return success
        except Exception as e:
            logger.error(f"Error deleting entity media {id}: {str(e)}", exc_info=True)
            self.db.rollback()  # Rollback on any exception during delete attempt
            raise  # Re-raise the exception after logging and rollback

    def find_by_media_asset_id(self, media_asset_id: str) -> List[EntityMedia]:
        """
        Find all entity media records associated with a specific media asset.

        Args:
            media_asset_id: The ID of the media asset

        Returns:
            List of EntityMedia associations for the media asset
        """
        try:
            entity_media_list = self.entity_media_repository.find_by_media_asset_id(
                media_asset_id
            )
            return self._attach_media_asset(entity_media_list)
        except Exception as e:
            logger.error(
                f"Error finding entity media for asset {media_asset_id}: {str(e)}"
            )
            return []

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[EntityMedia]:
        """
        Get all media associations for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity (expected as string, potentially formatted UUID for supplier)

        Returns:
            List of EntityMedia associations for the entity
        """
        try:
            # Prepare entity ID (primarily for suppliers)
            prepared_id = self._prepare_entity_id(entity_type, entity_id)

            entity_media_list = self.entity_media_repository.get_by_entity(
                entity_type, prepared_id
            )
            return self._attach_media_asset(entity_media_list)
        except Exception as e:
            logger.error(
                f"Error fetching media for {entity_type} {entity_id}: {str(e)}"
            )
            raise

    def get_thumbnail(self, entity_type: str, entity_id: str) -> Optional[EntityMedia]:
        """
        Get the thumbnail media association for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity (expected as string)

        Returns:
            The thumbnail EntityMedia association for the entity, or None if not found
        """
        try:
            # Prepare entity ID (primarily for suppliers)
            prepared_id = self._prepare_entity_id(entity_type, entity_id)

            thumbnail = self.entity_media_repository.get_thumbnail(
                entity_type, prepared_id
            )

            if (
                thumbnail
                and hasattr(thumbnail, "media_asset_id")
                and thumbnail.media_asset_id
            ):
                media_asset = self._get_media_asset(thumbnail.media_asset_id)
                thumbnail.media_asset = media_asset  # Attach even if None

            return thumbnail
        except Exception as e:
            logger.error(
                f"Error fetching thumbnail for {entity_type} {entity_id}: {str(e)}"
            )
            raise

    def get_by_id(self, id: str) -> Optional[EntityMedia]:
        """
        Get an entity media association by ID, ensuring media_asset is attached.

        Args:
            id: The ID of the entity media association

        Returns:
            The EntityMedia association, or None if not found
        """
        try:
            entity_media = self.entity_media_repository.get_by_id(id)

            if (
                entity_media
                and hasattr(entity_media, "media_asset_id")
                and entity_media.media_asset_id
            ):
                media_asset = self._get_media_asset(entity_media.media_asset_id)
                entity_media.media_asset = media_asset  # Attach even if None

            return entity_media
        except Exception as e:
            logger.error(f"Error fetching entity media {id}: {str(e)}")
            raise

    def _prepare_entity_id(self, entity_type: str, entity_id: Any) -> str:
        """
        Formats the entity ID for different entity types, ensuring compatibility with the backend API.

        Args:
            entity_type: The type of entity (supplier, inventory, etc.)
            entity_id: The ID value, which could be a number, string, or other format

        Returns:
            Properly formatted entity ID string for the specific entity type
        """
        entity_id_str = str(entity_id)
        entity_type = entity_type.lower()  # Normalize entity type to lowercase

        # Special handling for supplier IDs
        if entity_type == "supplier":
            # Check if it's already a valid UUID string
            if len(entity_id_str) == 36 and "-" in entity_id_str:
                return entity_id_str  # Assume it's already correct

            # Try to format numeric or simple string IDs
            try:
                # Attempt conversion to int to handle numeric strings and actual ints
                numeric_part = (
                    int(entity_id_val)
                    if (entity_id_val := entity_id) is not None
                    else None
                )
                if numeric_part is not None:
                    # Pad to 12 digits for the last part of the UUID
                    uuid_suffix = str(numeric_part).zfill(12)
                    formatted_id = f"00000000-0000-0000-0000-{uuid_suffix}"
                    if formatted_id != entity_id_str:  # Log only if changed
                        logger.info(
                            f"Formatted supplier entity_id from {entity_id_str} to {formatted_id}"
                        )
                    return formatted_id
            except (ValueError, TypeError):
                # If conversion fails, log a warning but proceed with the original string ID
                logger.warning(
                    f"Could not format supplier entity_id '{entity_id_str}' into standard UUID format. Using original value."
                )

        # Special handling for inventory IDs
        elif entity_type == "inventory":
            # Check if it's already a valid UUID string or has special formatting
            if (
                len(entity_id_str) == 36 and "-" in entity_id_str
            ) or entity_id_str.startswith("inventory-"):
                return entity_id_str  # Assume it's already correct

            # Try to format numeric or simple string IDs
            try:
                # Attempt conversion to int to handle numeric strings and actual ints
                numeric_part = (
                    int(entity_id_val)
                    if (entity_id_val := entity_id) is not None
                    else None
                )
                if numeric_part is not None:
                    # Format: inventory-{padded_id}
                    padded_id = str(numeric_part).zfill(10)
                    formatted_id = f"inventory-{padded_id}"
                    if formatted_id != entity_id_str:  # Log only if changed
                        logger.info(
                            f"Formatted inventory entity_id from {entity_id_str} to {formatted_id}"
                        )
                    return formatted_id
            except (ValueError, TypeError):
                # If conversion fails, log a warning but proceed with the original string ID
                logger.warning(
                    f"Could not format inventory entity_id '{entity_id_str}'. Using original value."
                )

        # Return the original value as string for other types or if formatting failed
        return entity_id_str

    def _prepare_entity_media_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepares entity media data, handling supplier ID formatting."""
        prepared_data = data.copy()

        if "entity_id" in prepared_data and "entity_type" in prepared_data:
            prepared_data["entity_id"] = self._prepare_entity_id(
                prepared_data["entity_type"], prepared_data["entity_id"]
            )

        # Ensure other necessary fields are present or defaulted
        prepared_data.setdefault("media_type", "thumbnail")
        prepared_data.setdefault("display_order", 0)
        prepared_data["caption"] = prepared_data.get(
            "caption"
        )  # Allow None or empty string

        return prepared_data

    def create_entity_media(
        self,
        entity_type: str,
        entity_id: str,
        media_asset_id: str,
        media_type: str = "thumbnail",
        display_order: int = 0,
        caption: Optional[str] = None,
    ) -> EntityMedia:
        """
        Create a new entity media association.

        Args:
            entity_type: The type of entity.
            entity_id: The ID of the entity (will be formatted if supplier).
            media_asset_id: The ID of the media asset.
            media_type: The type of media association.
            display_order: The display order.
            caption: Optional caption.

        Returns:
            The created EntityMedia association with media_asset attached.

        Raises:
            EntityNotFoundException: If the media asset doesn't exist.
            Exception: If creation fails.
        """
        try:
            # Check if the media asset exists
            media_asset = self.media_asset_repository.get_by_id(media_asset_id)
            if not media_asset:
                raise EntityNotFoundException(f"Media asset {media_asset_id} not found")

            # Prepare data (formats supplier ID, ensures string ID, sets defaults)
            data_to_create = self._prepare_entity_media_data(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "media_asset_id": media_asset_id,
                    "media_type": media_type,
                    "display_order": display_order,
                    "caption": caption,
                }
            )

            # Add UUID for the new association record
            data_to_create["id"] = str(uuid.uuid4())
            data_to_create["created_at"] = datetime.now(timezone.utc)
            data_to_create["updated_at"] = data_to_create[
                "created_at"
            ]  # Set updated_at on create

            logger.info(f"Attempting to create EntityMedia with data: {data_to_create}")

            # Use repository's standard ORM create method
            created_association = self.entity_media_repository.create(data_to_create)

            if not created_association:
                raise Exception(
                    "Failed to create entity media association using repository"
                )

            logger.info(
                f"Successfully created entity media association {created_association.id}"
            )

            # Fetch the result again using get_by_id to attach the media_asset
            return self.get_by_id(created_association.id)

        except EntityNotFoundException as e:
            logger.warning(f"Entity not found during creation: {str(e)}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Error creating entity media: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    def update_entity_media(
        self,
        entity_type: str,
        entity_id: str,  # Expect string ID from API
        media_asset_id: str,
        media_type: str = "thumbnail",
        display_order: int = 0,
        caption: Optional[str] = None,
    ) -> EntityMedia:
        """
        Update or create an entity media association using standard repository methods.

        Args:
            entity_type: The type of entity.
            entity_id: The ID of the entity (will be formatted if supplier).
            media_asset_id: The ID of the media asset.
            media_type: The type of media association (e.g., 'thumbnail').
            display_order: The display order.
            caption: Optional caption.

        Returns:
            The updated or created EntityMedia association with media_asset attached.

        Raises:
            EntityNotFoundException: If the media asset doesn't exist.
            Exception: If update/creation fails.
        """
        try:
            # Check if the media asset exists
            media_asset = self.media_asset_repository.get_by_id(media_asset_id)
            if not media_asset:
                raise EntityNotFoundException(f"Media asset {media_asset_id} not found")

            # Prepare data (formats supplier ID, ensures string ID, sets defaults)
            data_to_process = self._prepare_entity_media_data(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "media_asset_id": media_asset_id,
                    "media_type": media_type,
                    "display_order": display_order,
                    "caption": caption,
                }
            )

            logger.info(
                f"Attempting to update/create EntityMedia for {entity_type} {data_to_process['entity_id']} with media type {media_type}"
            )

            # Use the REPOSITORY's update_entity_media method
            # This method should handle find-or-create logic using ORM.
            result = self.entity_media_repository.update_entity_media(
                entity_type=data_to_process["entity_type"],
                entity_id=data_to_process["entity_id"],  # Use prepared ID
                media_asset_id=data_to_process["media_asset_id"],
                media_type=data_to_process["media_type"],
                display_order=data_to_process["display_order"],
                caption=data_to_process["caption"],
            )

            if not result:
                # This case might happen if the repo method returns None on failure
                raise Exception(
                    "Failed to create or update entity media via repository method"
                )

            logger.info(
                f"Successfully updated/created entity media association {result.id}"
            )

            # Fetch the result again using get_by_id to attach the media_asset
            # This ensures consistency regardless of whether it was created or updated.
            final_result = self.get_by_id(result.id)
            if not final_result:
                # Should ideally not happen if get_by_id is robust
                logger.error(
                    f"Could not retrieve entity media {result.id} after update/create."
                )
                raise Exception(
                    f"Failed to retrieve entity media {result.id} post-operation"
                )

            return final_result

        except EntityNotFoundException as e:
            # Re-raise entity not found exceptions
            logger.warning(f"Entity not found: {str(e)}")
            self.db.rollback()
            raise
        except Exception as e:
            # Log and re-raise other exceptions
            logger.error(
                f"Error updating/creating entity media: {str(e)}", exc_info=True
            )
            self.db.rollback()  # Ensure rollback on any error
            raise

    def remove_entity_media(
        self, entity_type: str, entity_id: str, media_type: Optional[str] = None
    ) -> bool:
        """
        Remove media associations for an entity, optionally filtered by media type.

        Args:
            entity_type: The type of entity.
            entity_id: The ID of the entity (will be formatted if supplier).
            media_type: Optional type of media to remove (if None, removes all).

        Returns:
            True if any associations were removed, False otherwise.
        """
        try:
            # Prepare entity ID
            prepared_id = self._prepare_entity_id(entity_type, entity_id)

            logger.info(
                f"Removing media for {entity_type}/{prepared_id}, media_type={media_type}"
            )

            # Use the repository method (assumes repo handles commit)
            deleted_count = self.entity_media_repository.remove_entity_media(
                entity_type=entity_type, entity_id=prepared_id, media_type=media_type
            )
            return deleted_count > 0
        except Exception as e:
            logger.error(
                f"Error removing entity media for {entity_type} {entity_id}: {str(e)}",
                exc_info=True,
            )
            self.db.rollback()
            raise

    def remove_entity_media_by_asset_id(self, media_asset_id: str) -> bool:
        """
        Remove all entity media associations for a specific media asset ID.

        Args:
            media_asset_id: The ID of the media asset to remove associations for.

        Returns:
            bool: True if any associations were removed, False otherwise.
        """
        try:
            # Query for all entity media records with the given media_asset_id
            entity_media_records = self.entity_media_repository.find_by_media_asset_id(
                media_asset_id
            )

            if not entity_media_records:
                logger.info(
                    f"No entity media associations found for asset ID {media_asset_id}"
                )
                return False

            # Delete each association using the service's delete method to ensure proper handling
            count = 0
            for record in entity_media_records:
                if self.delete_entity_media(
                    record.id
                ):  # Use the service's delete method
                    count += 1
                else:
                    # Log if deletion fails for an individual record, but continue
                    logger.warning(
                        f"Failed to delete entity media record {record.id} while removing by asset ID {media_asset_id}"
                    )

            logger.info(
                f"Attempted removal of {len(entity_media_records)} associations for asset {media_asset_id}. Successfully removed: {count}"
            )
            # Return True if we attempted to delete any, even if some failed individually
            return len(entity_media_records) > 0
        except Exception as e:
            logger.error(
                f"Error removing entity media for asset {media_asset_id}: {str(e)}",
                exc_info=True,
            )
            self.db.rollback()  # Rollback if the overall process fails
            raise
