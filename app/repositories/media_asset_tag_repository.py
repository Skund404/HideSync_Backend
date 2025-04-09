# File: app/repositories/media_asset_tag_repository.py
"""
Repository for MediaAssetTag associations in HideSync.

This module provides data access operations for the many-to-many
relationship between media assets and tags.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid

from app.db.models.association_media import MediaAssetTag
from app.repositories.base_repository import BaseRepository


class MediaAssetTagRepository(BaseRepository[MediaAssetTag]):
    """
    Repository for MediaAssetTag entity operations.

    Provides methods for creating, retrieving, and deleting the
    associations between media assets and tags.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = MediaAssetTag

    def create_with_id(self, data: Dict[str, Any]) -> MediaAssetTag:
        """
        Create a new association with a generated UUID.

        Args:
            data: Dictionary of association attributes

        Returns:
            The created association
        """
        # Generate a UUID for the new association if not provided
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        return self.create(data)

    def get_by_asset_and_tag(
        self, asset_id: str, tag_id: str
    ) -> Optional[MediaAssetTag]:
        """
        Get an association by asset ID and tag ID.

        Args:
            asset_id: The UUID of the media asset
            tag_id: The UUID of the tag

        Returns:
            The association if found, None otherwise
        """
        entity = (
            self.session.query(self.model)
            .filter(self.model.media_asset_id == asset_id, self.model.tag_id == tag_id)
            .first()
        )

        return self._decrypt_sensitive_fields(entity) if entity else None

    def delete_by_asset_and_tag(self, asset_id: str, tag_id: str) -> bool:
        """
        Delete an association by asset ID and tag ID.

        Args:
            asset_id: The UUID of the media asset
            tag_id: The UUID of the tag

        Returns:
            True if the association was deleted, False otherwise
        """
        result = (
            self.session.query(self.model)
            .filter(self.model.media_asset_id == asset_id, self.model.tag_id == tag_id)
            .delete(synchronize_session=False)
        )

        return result > 0

    def get_by_asset(self, asset_id: str) -> List[MediaAssetTag]:
        """
        Get all associations for a specific media asset.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            List of associations for the media asset
        """
        entities = (
            self.session.query(self.model)
            .filter(self.model.media_asset_id == asset_id)
            .all()
        )

        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_by_tag(self, tag_id: str) -> List[MediaAssetTag]:
        """
        Get all associations for a specific tag.

        Args:
            tag_id: The UUID of the tag

        Returns:
            List of associations for the tag
        """
        entities = (
            self.session.query(self.model).filter(self.model.tag_id == tag_id).all()
        )

        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def delete_by_asset(self, asset_id: str) -> int:
        """
        Delete all associations for a specific media asset.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            Number of associations deleted
        """
        return (
            self.session.query(self.model)
            .filter(self.model.media_asset_id == asset_id)
            .delete(synchronize_session=False)
        )

    def delete_by_tag(self, tag_id: str) -> int:
        """
        Delete all associations for a specific tag.

        Args:
            tag_id: The UUID of the tag

        Returns:
            Number of associations deleted
        """
        return (
            self.session.query(self.model)
            .filter(self.model.tag_id == tag_id)
            .delete(synchronize_session=False)
        )
