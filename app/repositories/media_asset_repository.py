# File: app/repositories/media_asset_repository.py
"""
Repository for MediaAsset entities in HideSync.

This module provides data access operations for media assets, implementing
the repository pattern to abstract database operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import or_, and_, desc, asc, func
from sqlalchemy.orm import Session, joinedload
import uuid
from datetime import datetime
from sqlalchemy.sql import text
from app.db.models.media_asset import MediaAsset
from app.db.models.tag import Tag

from app.repositories.base_repository import BaseRepository
from app.db.models.association_media import MediaAssetTag
import logging
logger = logging.getLogger(__name__)

class MediaAssetRepository(BaseRepository[MediaAsset]):
    """
    Repository for MediaAsset entity operations.

    Provides methods for creating, retrieving, updating, and deleting
    media assets, with support for filtering and pagination.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = MediaAsset

    def create_with_id(self, data: Dict[str, Any]) -> MediaAsset:
        """
        Create a new media asset with a generated UUID.

        Args:
            data: Dictionary of media asset attributes

        Returns:
            The created media asset
        """
        # Generate a UUID for the new asset if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        return self.create(data)

    def get_by_id_with_tags(self, id: str) -> Optional[MediaAsset]:
        """
        Get a media asset by ID with its tags (with safer loading strategy).

        Args:
            id: The UUID of the media asset

        Returns:
            The media asset with tags if found, None otherwise
        """
        # First get the asset without eager loading to avoid SQLCipher compatibility issues
        asset = self.session.query(self.model).filter(self.model.id == id).first()

        if not asset:
            return None

        # Then manually load tags with a separate query to avoid memory errors
        try:
            # Make sure we're using the correct column names based on your database schema
            # Check if the association table uses 'tag_id' (most likely) or 'tags_id'
            tag_records = self.session.query(MediaAssetTag).filter(
                MediaAssetTag.media_asset_id == id
            ).all()

            if tag_records:
                # Get the tag IDs
                tag_ids = [record.tag_id for record in tag_records]

                # Fetch the actual tag objects
                tags = self.session.query(Tag).filter(Tag.id.in_(tag_ids)).all()

                # Manually set the tags attribute
                asset.tags = tags
            else:
                asset.tags = []

            return self._decrypt_sensitive_fields(asset)
        except Exception as e:
            # Log the error but return the asset without tags rather than failing completely
            logger.error(f"Error loading tags for asset {id}: {str(e)}")
            asset.tags = []  # Set empty tags list
            return self._decrypt_sensitive_fields(asset)

    def search_assets(
            self,
            search_params: Dict[str, Any],
            skip: int = 0,
            limit: int = 100,
            sort_by: str = "uploaded_at",
            sort_dir: str = "desc",
            estimate_count: bool = False,
    ) -> Tuple[List[MediaAsset], int]:
        """
        Search for media assets with filtering, sorting, and pagination.

        Args:
            search_params: Dictionary of search parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            estimate_count: Whether to use estimation for count query

        Returns:
            Tuple of (list of matching assets, total count)
        """
        query = self.session.query(self.model)

        # Apply filters based on search parameters
        if search_params:
            if file_name := search_params.get('file_name'):
                query = query.filter(self.model.file_name.ilike(f"%{file_name}%"))

            if file_type := search_params.get('file_type'):
                query = query.filter(self.model.file_type == file_type)

            if uploaded_by := search_params.get('uploaded_by'):
                query = query.filter(self.model.uploaded_by == uploaded_by)

            if uploaded_after := search_params.get('uploaded_after'):
                query = query.filter(self.model.uploaded_at >= uploaded_after)

            if uploaded_before := search_params.get('uploaded_before'):
                query = query.filter(self.model.uploaded_at <= uploaded_before)

            if tag_ids := search_params.get('tag_ids'):
                # Get assets that have all the specified tags
                for tag_id in tag_ids:
                    subquery = self.session.query(MediaAssetTag.media_asset_id). \
                        filter(MediaAssetTag.tag_id == tag_id)
                    query = query.filter(self.model.id.in_(subquery))

            if search := search_params.get('search'):
                # Search across multiple fields
                query = query.filter(
                    or_(
                        self.model.file_name.ilike(f"%{search}%"),
                        self.model.file_type.ilike(f"%{search}%"),
                        self.model.uploaded_by.ilike(f"%{search}%")
                    )
                )

        # Get total count before pagination, with optional estimation
        try:
            if estimate_count:
                # Use faster approximation for large datasets
                count_result = self.session.execute(
                    text("SELECT COUNT(*) FROM (SELECT 1 FROM media_assets LIMIT 1000)")
                ).scalar()
                total = count_result or 0

                # If count is at limit, indicate it's an estimate
                if total >= 1000:
                    total = 1000
            else:
                # Use full count
                total = query.count()
        except Exception as e:
            logger.error(f"Error getting count: {e}")
            total = 0

        # Apply sorting
        if hasattr(self.model, sort_by):
            if sort_dir.lower() == 'desc':
                query = query.order_by(desc(getattr(self.model, sort_by)))
            else:
                query = query.order_by(asc(getattr(self.model, sort_by)))

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute query with error handling
        try:
            assets = query.all()
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            assets = []

        # Decrypt sensitive fields if applicable
        assets = [self._decrypt_sensitive_fields(asset) for asset in assets]

        return assets, total

    def add_tags_to_asset(self, asset_id: str, tag_ids: List[str]) -> None:
        """
        Add tags to a media asset.

        Args:
            asset_id: The UUID of the media asset
            tag_ids: List of tag UUIDs to add

        Raises:
            Exception: If a database error occurs
        """
        asset = self.get_by_id(asset_id)
        if not asset:
            return

        for tag_id in tag_ids:
            # Check if the association already exists
            existing = self.session.query(MediaAssetTag). \
                filter(
                MediaAssetTag.media_asset_id == asset_id,
                MediaAssetTag.tag_id == tag_id
            ).first()

            if not existing:
                # Create new association
                association = MediaAssetTag(
                    id=str(uuid.uuid4()),
                    media_asset_id=asset_id,
                    tag_id=tag_id
                )
                self.session.add(association)

    def remove_tags_from_asset(self, asset_id: str, tag_ids: List[str]) -> None:
        """
        Remove tags from a media asset.

        Args:
            asset_id: The UUID of the media asset
            tag_ids: List of tag UUIDs to remove

        Raises:
            Exception: If a database error occurs
        """
        # Delete the associations
        self.session.query(MediaAssetTag). \
            filter(
            MediaAssetTag.media_asset_id == asset_id,
            MediaAssetTag.tag_id.in_(tag_ids)
        ).delete(synchronize_session=False)

    def get_assets_by_tag(self, tag_id: str, skip: int = 0, limit: int = 100) -> List[MediaAsset]:
        """
        Get all media assets with a specific tag.

        Args:
            tag_id: The UUID of the tag
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of media assets with the specified tag
        """
        query = self.session.query(self.model). \
            join(MediaAssetTag, MediaAssetTag.media_asset_id == self.model.id). \
            filter(MediaAssetTag.tag_id == tag_id). \
            offset(skip).limit(limit)

        assets = query.all()

        return [self._decrypt_sensitive_fields(asset) for asset in assets]