# File: app/repositories/tag_repository.py
"""
Repository for Tag entities in HideSync.

This module provides data access operations for tags, implementing
the repository pattern to abstract database operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import or_, and_, desc, asc
from sqlalchemy.orm import Session, joinedload
import uuid

from app.db.models.tag import Tag
from app.db.models.association_media import MediaAssetTag
from app.repositories.base_repository import BaseRepository


class TagRepository(BaseRepository[Tag]):
    """
    Repository for Tag entity operations.

    Provides methods for creating, retrieving, updating, and deleting
    tags, with support for filtering and pagination.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Tag

    def create_with_id(self, data: Dict[str, Any]) -> Tag:
        """
        Create a new tag with a generated UUID.

        Args:
            data: Dictionary of tag attributes

        Returns:
            The created tag
        """
        # Generate a UUID for the new tag if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        return self.create(data)

    def get_by_name(self, name: str) -> Optional[Tag]:
        """
        Get a tag by its name.

        Args:
            name: The name of the tag

        Returns:
            The tag if found, None otherwise
        """
        entity = self.session.query(self.model).filter(self.model.name == name).first()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_by_id_with_assets(self, id: str) -> Optional[Tag]:
        """
        Get a tag by ID with its media assets eagerly loaded.

        Args:
            id: The UUID of the tag

        Returns:
            The tag with media assets if found, None otherwise
        """
        query = self.session.query(self.model). \
            options(joinedload(self.model.media_assets)). \
            filter(self.model.id == id)

        entity = query.first()

        return self._decrypt_sensitive_fields(entity) if entity else None

    def search_tags(
            self,
            search_params: Dict[str, Any],
            skip: int = 0,
            limit: int = 100,
            sort_by: str = "name",
            sort_dir: str = "asc"
    ) -> Tuple[List[Tag], int]:
        """
        Search for tags with filtering, sorting, and pagination.

        Args:
            search_params: Dictionary of search parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            Tuple of (list of matching tags, total count)
        """
        query = self.session.query(self.model)

        # Apply filters based on search parameters
        if search_params:
            if name := search_params.get('name'):
                query = query.filter(self.model.name.ilike(f"%{name}%"))

            if search := search_params.get('search'):
                # Search across multiple fields
                query = query.filter(
                    or_(
                        self.model.name.ilike(f"%{search}%"),
                        self.model.description.ilike(f"%{search}%")
                    )
                )

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        if hasattr(self.model, sort_by):
            if sort_dir.lower() == 'desc':
                query = query.order_by(desc(getattr(self.model, sort_by)))
            else:
                query = query.order_by(asc(getattr(self.model, sort_by)))

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute query
        tags = query.all()

        # Decrypt sensitive fields if applicable
        tags = [self._decrypt_sensitive_fields(tag) for tag in tags]

        return tags, total

    def get_tags_by_asset(self, asset_id: str) -> List[Tag]:
        """
        Get all tags associated with a specific media asset.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            List of tags associated with the media asset
        """
        query = self.session.query(self.model). \
            join(MediaAssetTag, MediaAssetTag.tag_id == self.model.id). \
            filter(MediaAssetTag.media_asset_id == asset_id)

        tags = query.all()

        return [self._decrypt_sensitive_fields(tag) for tag in tags]

    def get_asset_count_by_tag(self, tag_id: str) -> int:
        """
        Get the number of media assets associated with a specific tag.

        Args:
            tag_id: The UUID of the tag

        Returns:
            Number of associated media assets
        """
        return self.session.query(MediaAssetTag). \
            filter(MediaAssetTag.tag_id == tag_id). \
            count()