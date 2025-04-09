# File: app/repositories/entity_media_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime, timezone  # Added timezone

from app.repositories.base_repository import BaseRepository
from app.db.models.entity_media import EntityMedia

logger = logging.getLogger(__name__)


class EntityMediaRepository(BaseRepository[EntityMedia]):
    """
    Repository for EntityMedia ORM operations in the HideSync system.

    Manages associations between media assets and various entity types using SQLAlchemy.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the EntityMediaRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = EntityMedia

    def find_by_media_asset_id(self, media_asset_id: str) -> List[EntityMedia]:
        """
        Find all entity media records associated with a specific media asset ID.

        Args:
            media_asset_id: The ID (UUID string) of the media asset.

        Returns:
            List[EntityMedia]: List of matching entity media records.
        """
        # Decryption is handled by the BaseRepository's query methods if configured
        return (
            self.session.query(self.model)
            .filter(self.model.media_asset_id == media_asset_id)
            .all()
        )

    def create_with_id(self, data: Dict[str, Any]) -> EntityMedia:
        """
        Create a new entity media association, generating a UUID if needed.
        Expects 'entity_id' to be a correctly formatted string (UUID).
        """
        if "id" not in data or not data["id"]:
            data["id"] = str(uuid.uuid4())

        # Ensure entity_id is a string (should already be handled by service, but safe check)
        if "entity_id" in data:
            data["entity_id"] = str(data["entity_id"])

        # Set timestamps if not provided
        now = datetime.now(timezone.utc)
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)

        logger.info(f"Repository creating EntityMedia with data: {data}")
        # Use the base repository's create method which handles ORM object creation and session add/commit
        return self.create(data)

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[EntityMedia]:
        """
        Get all media associations for a specific entity.
        Expects 'entity_id' to be a correctly formatted string (UUID).

        Args:
            entity_type: The type of entity (e.g., "supplier").
            entity_id: The ID (UUID string) of the entity.

        Returns:
            List of EntityMedia associations for the entity, ordered by display_order.
        """
        # Decryption handled by BaseRepository query methods if applicable
        query = (
            self.session.query(self.model)
            .filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id,  # Direct string comparison
            )
            .order_by(self.model.display_order)
        )

        return query.all()

    def get_thumbnail(self, entity_type: str, entity_id: str) -> Optional[EntityMedia]:
        """
        Get the 'thumbnail' media association for a specific entity.
        Expects 'entity_id' to be a correctly formatted string (UUID).

        Args:
            entity_type: The type of entity.
            entity_id: The ID (UUID string) of the entity.

        Returns:
            The thumbnail EntityMedia association, or None if not found.
        """
        # Decryption handled by BaseRepository query methods if applicable
        return (
            self.session.query(self.model)
            .filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id,  # Direct string comparison
                self.model.media_type == "thumbnail",
            )
            .first()
        )

    def update_entity_media(
        self,
        entity_type: str,
        entity_id: str,  # Expects correctly formatted string UUID
        media_asset_id: str,
        media_type: str = "thumbnail",
        display_order: int = 0,
        caption: Optional[str] = None,
    ) -> EntityMedia:
        """
        Update an existing entity media association or create it if it doesn't exist
        based on entity_type, entity_id, and media_type. Uses standard ORM operations.

        Args:
            entity_type: Type of the entity.
            entity_id: ID (UUID string) of the entity.
            media_asset_id: ID of the associated media asset.
            media_type: Type of the association (e.g., 'thumbnail').
            display_order: Display order.
            caption: Optional caption.

        Returns:
            The updated or newly created EntityMedia object.
        """
        try:
            # Look for an existing association for this specific entity and media type
            # Note: This assumes only ONE record per (entity_type, entity_id, media_type)
            # If multiple are possible (e.g., gallery), this logic might need adjustment
            # based on how updates should behave (e.g., update the first found?).
            # The unique constraint might prevent duplicates anyway.
            association = (
                self.session.query(self.model)
                .filter(
                    self.model.entity_type == entity_type,
                    self.model.entity_id == entity_id,
                    self.model.media_type == media_type,
                )
                .first()
            )

            now = datetime.now(timezone.utc)

            if association:
                # Update existing association
                logger.info(
                    f"Updating existing EntityMedia association ID: {association.id}"
                )
                association.media_asset_id = media_asset_id
                association.display_order = display_order
                association.caption = caption
                association.updated_at = now  # Update timestamp
                # Commit is handled by BaseRepository context or service layer transaction
                self.session.flush()  # Ensure changes are reflected before returning
                return association
            else:
                # Create a new entity media association
                new_id = str(uuid.uuid4())
                logger.info(f"Creating new EntityMedia association with ID: {new_id}")

                new_association_data = {
                    "id": new_id,
                    "media_asset_id": media_asset_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,  # Use the prepared string ID
                    "media_type": media_type,
                    "display_order": display_order,
                    "caption": caption,
                    "created_at": now,
                    "updated_at": now,
                }
                # Use the base 'create' which handles ORM object creation and session add
                return self.create(new_association_data)

        except Exception as e:
            # Rollback should be handled by the service layer's transaction context
            logger.error(
                f"Repository error in update_entity_media: {str(e)}", exc_info=True
            )
            raise  # Re-raise for service layer to handle transaction

    def remove_entity_media(
        self, entity_type: str, entity_id: str, media_type: Optional[str] = None
    ) -> int:
        """
        Remove media associations for an entity using ORM delete.
        Expects 'entity_id' to be a correctly formatted string (UUID).

        Args:
            entity_type: The type of entity.
            entity_id: The ID (UUID string) of the entity.
            media_type: Optional type of media to remove (if None, removes all for the entity).

        Returns:
            Number of associations deleted.
        """
        try:
            query = self.session.query(self.model).filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id,  # Direct string comparison
            )

            if media_type:
                query = query.filter(self.model.media_type == media_type)

            # Perform bulk delete
            # synchronize_session=False is generally faster for bulk deletes but requires careful session management.
            # 'fetch' might be safer if triggers or complex relationships exist.
            # BaseRepository delete might handle this, confirm its implementation.
            count = query.delete(synchronize_session=False)
            # Commit is handled by BaseRepository context or service layer transaction
            logger.info(
                f"Deleted {count} EntityMedia associations for {entity_type}:{entity_id} (media_type: {media_type})"
            )
            return count
        except Exception as e:
            # Rollback should be handled by the service layer's transaction context
            logger.error(
                f"Repository error in remove_entity_media: {str(e)}", exc_info=True
            )
            raise  # Re-raise for service layer to handle transaction
