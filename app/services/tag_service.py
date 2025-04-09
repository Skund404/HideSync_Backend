# File: app/services/tag_service.py
"""
Service for managing tags in HideSync.

This module provides business logic for creating, retrieving, updating,
and deleting tags used for categorizing media assets and other entities.
"""

from typing import Dict, List, Optional, Any, Tuple
import uuid
from sqlalchemy.orm import Session
import logging

from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    DuplicateEntityException,
)
from app.services.base_service import BaseService
from app.repositories.tag_repository import TagRepository
from app.repositories.media_asset_tag_repository import MediaAssetTagRepository
from app.db.models.tag import Tag

logger = logging.getLogger(__name__)


class TagService(BaseService[Tag]):
    """
    Service for tag business operations.

    Provides methods for managing tags and their relationships
    with other entities in the system.
    """

    def __init__(self, session: Session):
        """
        Initialize the service with dependencies.

        Args:
            session: Database session for persistence operations
        """
        super().__init__(session, TagRepository)
        self.media_asset_tag_repository = MediaAssetTagRepository(session)

    def get_tag(self, tag_id: str) -> Optional[Tag]:
        """
        Get a tag by ID.

        Args:
            tag_id: The UUID of the tag

        Returns:
            The tag if found, None otherwise
        """
        return self.repository.get_by_id_with_assets(tag_id)

    def list_tags(
        self,
        skip: int = 0,
        limit: int = 100,
        search_params: Optional[Dict[str, Any]] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
        estimate_count: bool = True,
    ) -> Tuple[List[Tag], int]:
        """
        List tags with filtering, sorting, and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search_params: Dictionary of search parameters
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            estimate_count: Whether to use faster but approximate count method

        Returns:
            Tuple of (list of matching tags, total count)
        """
        tags, total = self.repository.search_tags(
            search_params or {},
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            estimate_count=estimate_count,
        )

        return tags, total

    def create_tag(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Tag:
        """
        Create a new tag.

        Args:
            name: Name of the tag
            description: Optional description of the tag
            color: Optional color code for the tag (hex format)

        Returns:
            The created tag

        Raises:
            DuplicateEntityException: If a tag with the same name already exists
        """
        # Check if a tag with the same name already exists
        existing = self.repository.get_by_name(name)
        if existing:
            raise DuplicateEntityException(f"Tag with name '{name}' already exists")

        # Create the tag
        tag_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "color": color,
        }

        return self.repository.create(tag_data)

    def update_tag(
        self,
        tag_id: str,
        data: Dict[str, Any],
    ) -> Optional[Tag]:
        """
        Update a tag.

        Args:
            tag_id: The UUID of the tag
            data: Dictionary of fields to update

        Returns:
            The updated tag if found, None otherwise

        Raises:
            DuplicateEntityException: If updating would create a duplicate name
            BusinessRuleException: If update violates business rules
        """
        tag = self.repository.get_by_id(tag_id)
        if not tag:
            return None

        # If updating name, check for duplicates
        if "name" in data and data["name"] != tag.name:
            existing = self.repository.get_by_name(data["name"])
            if existing:
                raise DuplicateEntityException(
                    f"Tag with name '{data['name']}' already exists"
                )

        # Update the tag
        return self.repository.update(tag_id, data)

    def delete_tag(self, tag_id: str) -> bool:
        """
        Delete a tag and all its associations.

        Args:
            tag_id: The UUID of the tag

        Returns:
            True if the tag was deleted, False otherwise
        """
        tag = self.repository.get_by_id(tag_id)
        if not tag:
            return False

        # Delete all associations and the tag itself in a transaction
        with self.transaction():
            # Delete tag associations
            self.media_asset_tag_repository.delete_by_tag(tag_id)

            # Delete the tag
            return self.repository.delete(tag_id)

    def get_tags_by_asset(self, asset_id: str) -> List[Tag]:
        """
        Get all tags for a specific media asset.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            List of tags associated with the media asset
        """
        return self.repository.get_tags_by_asset(asset_id)

    def get_asset_count_by_tag(self, tag_id: str) -> int:
        """
        Get the number of media assets associated with a specific tag.

        Args:
            tag_id: The UUID of the tag

        Returns:
            Number of associated media assets
        """
        return self.repository.get_asset_count_by_tag(tag_id)

    def find_or_create_tag(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Tag:
        """
        Find a tag by name or create it if it doesn't exist.

        Args:
            name: Name of the tag
            description: Optional description of the tag
            color: Optional color code for the tag (hex format)

        Returns:
            The existing or newly created tag
        """
        existing = self.repository.get_by_name(name)
        if existing:
            return existing

        return self.create_tag(name, description, color)
