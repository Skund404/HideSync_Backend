# File: app/repositories/entity_media_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid

from app.repositories.base_repository import BaseRepository
from app.db.models.entity_media import EntityMedia


class EntityMediaRepository(BaseRepository[EntityMedia]):
    """
    Repository for EntityMedia operations in the HideSync system.

    This repository manages associations between media assets and various entity types.
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
        Find all entity media records associated with a specific media asset.

        Args:
            media_asset_id: The ID of the media asset

        Returns:
            List[EntityMedia]: List of entity media records
        """
        return self.session.query(self.model).filter(self.model.media_asset_id == media_asset_id).all()

    def create_with_id(self, data: Dict[str, Any]) -> EntityMedia:
        """
        Create a new entity media association with a generated UUID.

        Args:
            data: Dictionary of entity media attributes

        Returns:
            The created entity media association
        """
        # Generate a UUID for the new association if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        return self.create(data)

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[EntityMedia]:
        """
        Get all media associations for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity

        Returns:
            List of EntityMedia associations for the entity
        """
        query = self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id
        ).order_by(self.model.display_order)

        return query.all()

    def get_thumbnail(self, entity_type: str, entity_id: str) -> Optional[EntityMedia]:
        """
        Get the thumbnail media association for a specific entity.

        Args:
            entity_type: The type of entity (material, tool, supplier, etc.)
            entity_id: The ID of the entity

        Returns:
            The thumbnail EntityMedia association for the entity, or None if not found
        """
        return self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id,
            self.model.media_type == "thumbnail"
        ).first()

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
        # Check if the association already exists
        association = self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id,
            self.model.media_type == media_type
        ).first()

        if association:
            # Update existing association
            association.media_asset_id = media_asset_id
            association.display_order = display_order
            association.caption = caption
            self.session.commit()
            return association
        else:
            # Create new association
            data = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "media_asset_id": media_asset_id,
                "media_type": media_type,
                "display_order": display_order,
                "caption": caption
            }
            return self.create_with_id(data)

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
        query = self.session.query(self.model).filter(
            self.model.entity_type == entity_type,
            self.model.entity_id == entity_id
        )

        if media_type:
            query = query.filter(self.model.media_type == media_type)

        count = query.delete(synchronize_session=False)
        self.session.commit()

        return count > 0