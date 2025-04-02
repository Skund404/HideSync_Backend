# File: app/repositories/tag_repository.py
"""
Repository for Tag entities in HideSync.

This module provides data access operations for tags, implementing
the repository pattern to abstract database operations.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import or_, and_, desc, asc, func
from sqlalchemy.orm import Session, joinedload
import uuid
from sqlalchemy.sql import text
from app.db.models.tag import Tag
from app.db.models.association_media import MediaAssetTag
from app.repositories.base_repository import BaseRepository


from sqlalchemy.sql import text

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
            sort_dir: str = "asc",
            estimate_count: bool = True
    ) -> Tuple[List[Tag], int]:
        import logging
        from sqlalchemy.sql import func
        logger = logging.getLogger(__name__)
        """
        Search for tags with filtering, sorting, and pagination.

        Args:
            search_params: Dictionary of search parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            estimate_count: If True, use faster but approximate count method

        Returns:
            Tuple of (list of matching tags, total count)
        """
        # Start with base query
        query = self.session.query(Tag)

        # Apply filters
        if search_params:
            # Filter by name
            if "name" in search_params and search_params["name"]:
                query = query.filter(Tag.name.ilike(f"%{search_params['name']}%"))

            # Filter by search term (if applicable)
            if "search" in search_params and search_params["search"]:
                search_term = search_params["search"]
                query = query.filter(
                    or_(
                        Tag.name.ilike(f"%{search_term}%"),
                        Tag.description.ilike(f"%{search_term}%")
                    )
                )

        # Get total count before pagination, using a more efficient approach
        try:
            # For more efficient counting, use optimized approach
            if estimate_count:
                # Option 1: Fast approximate count
                count_query = self.session.execute(
                    text(f"SELECT COUNT(1) FROM {Tag.__tablename__}")
                )
                total = count_query.scalar() or 0
            else:
                # Option 2: Exact count with optimized query
                count_query = query.with_entities(func.count(Tag.id))
                total = count_query.scalar() or 0
        except MemoryError:
            # Fallback if we still encounter memory errors
            import gc
            gc.collect()  # Force garbage collection

            # Return a reasonable estimate and warning
            total = limit * 10  # Assume at least 10 pages worth
            logger.warning(f"Memory error during count operation, using estimated total: {total}")
        except Exception as e:
            logger.error(f"Error in tag count query: {e}")
            total = 0  # Default to zero in case of errors

        # Apply sorting
        if sort_dir.lower() == "asc":
            query = query.order_by(getattr(Tag, sort_by).asc())
        else:
            query = query.order_by(getattr(Tag, sort_by).desc())

        # Apply pagination - never skip this step to ensure memory safety
        if limit is None or limit > 500:
            limit = 500  # Hard safety limit
            logger.warning("Limiting query results to 500 for memory safety")

        query = query.offset(skip).limit(limit)

        # Execute query and fetch results
        try:
            tags = query.all()
        except Exception as e:
            logger.error(f"Error fetching tags: {e}")
            tags = []  # Return empty list on error

        return tags, total

    def get_tag_count(self) -> int:
        """
        Get the total count of tags.

        Returns:
            Integer count of tags
        """
        try:
            # Use text() to explicitly declare textual SQL
            result = self.session.execute(text("SELECT COUNT(1) FROM tags"))
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error in tag count query: {str(e)}")
            return 0

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