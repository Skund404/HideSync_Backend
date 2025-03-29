# File: app/services/media_asset_service.py
"""
Service for managing media assets in HideSync.

This module provides business logic for creating, retrieving, updating,
and deleting media assets, as well as handling file uploads and tag associations.
"""

from typing import Dict, List, Optional, Any, BinaryIO, Tuple, Union
from datetime import datetime
import uuid
import os
import mimetypes
from sqlalchemy.orm import Session
import logging

from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    FileStorageException,
)
from app.services.base_service import BaseService
from app.repositories.media_asset_repository import MediaAssetRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.media_asset_tag_repository import MediaAssetTagRepository
from app.services.file_storage_service import FileStorageService
from app.db.models.media_asset import MediaAsset

logger = logging.getLogger(__name__)


class MediaAssetService(BaseService[MediaAsset]):
    """
    Service for media asset business operations.

    Provides methods for managing media assets and their related operations,
    including file handling and tag associations.
    """

    def __init__(
            self,
            session: Session,
            file_storage_service: Optional[FileStorageService] = None,
    ):
        """
        Initialize the service with dependencies.

        Args:
            session: Database session for persistence operations
            file_storage_service: Service for file storage operations
        """
        super().__init__(session, MediaAssetRepository)
        self.tag_repository = TagRepository(session)
        self.asset_tag_repository = MediaAssetTagRepository(session)
        self.file_storage_service = file_storage_service

    def get_media_asset(self, asset_id: str) -> Optional[MediaAsset]:
        """
        Get a media asset by ID.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            The media asset if found, None otherwise
        """
        return self.repository.get_by_id_with_tags(asset_id)

    def list_media_assets(
            self,
            skip: int = 0,
            limit: int = 100,
            search_params: Optional[Dict[str, Any]] = None,
            sort_by: str = "uploaded_at",
            sort_dir: str = "desc",
    ) -> Tuple[List[MediaAsset], int]:
        """
        List media assets with filtering, sorting, and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search_params: Dictionary of search parameters
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            Tuple of (list of matching assets, total count)
        """
        assets, total = self.repository.search_assets(
            search_params or {},
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        return assets, total

    def create_media_asset(
            self,
            file_name: str,
            file_type: str,
            content_type: str,
            uploaded_by: str,
            tag_ids: Optional[List[str]] = None,
    ) -> MediaAsset:
        """
        Create a new media asset record (without file content).

        Args:
            file_name: Name of the file
            file_type: Type or extension of the file
            content_type: MIME type of the file
            uploaded_by: User who uploaded the file
            tag_ids: Optional list of tag IDs to associate

        Returns:
            The created media asset
        """
        asset_id = str(uuid.uuid4())

        # Create the media asset
        asset_data = {
            "id": asset_id,
            "file_name": file_name,
            "file_type": file_type,
            "content_type": content_type,
            "storage_location": "",  # Will be updated after file upload
            "file_size_bytes": 0,  # Will be updated after file upload
            "uploaded_by": uploaded_by,
            "uploaded_at": datetime.now(),
        }

        with self.transaction():
            # Create the asset
            asset = self.repository.create(asset_data)

            # Add tags if provided
            if tag_ids:
                for tag_id in tag_ids:
                    # Verify that the tag exists
                    tag = self.tag_repository.get_by_id(tag_id)
                    if not tag:
                        raise EntityNotFoundException(f"Tag with ID {tag_id} not found")

                    # Create the association
                    self.asset_tag_repository.create_with_id({
                        "media_asset_id": asset_id,
                        "tag_id": tag_id,
                    })

            return asset

    def upload_file(
            self,
            asset_id: str,
            file_content: BinaryIO,
            update_content_type: Optional[str] = None,
    ) -> MediaAsset:
        """
        Upload file content for an existing media asset.

        Args:
            asset_id: The UUID of the media asset
            file_content: The file content as a binary stream
            update_content_type: Optional content type to update

        Returns:
            The updated media asset

        Raises:
            EntityNotFoundException: If the asset is not found
            FileStorageException: If file upload fails
        """
        asset = self.repository.get_by_id(asset_id)
        if not asset:
            raise EntityNotFoundException(f"Media asset with ID {asset_id} not found")

        if self.file_storage_service is None:
            raise BusinessRuleException("File storage service is not configured")

        # Determine storage location
        storage_path = f"media_assets/{asset_id}/{asset.file_name}"

        # Upload the file
        try:
            uploaded_file = self.file_storage_service.upload_file(
                storage_path, file_content
            )

            # Update the asset with storage information
            update_data = {
                "storage_location": uploaded_file.storage_location,
                "file_size_bytes": uploaded_file.size,
            }

            # Update content type if provided
            if update_content_type:
                update_data["content_type"] = update_content_type

            # Update the asset
            return self.repository.update(asset_id, update_data)

        except Exception as e:
            logger.error(f"Failed to upload file for asset {asset_id}: {str(e)}")
            raise FileStorageException(f"Failed to upload file: {str(e)}")

    def create_media_asset_with_content(
            self,
            file_name: str,
            file_content: BinaryIO,
            uploaded_by: str,
            content_type: Optional[str] = None,
            tag_ids: Optional[List[str]] = None,
    ) -> MediaAsset:
        """
        Create a new media asset with file content in a single operation.

        Args:
            file_name: Name of the file
            file_content: The file content as a binary stream
            uploaded_by: User who uploaded the file
            content_type: Optional MIME type of the file (detected if not provided)
            tag_ids: Optional list of tag IDs to associate

        Returns:
            The created media asset

        Raises:
            FileStorageException: If file upload fails
        """
        # Determine file type from name
        file_type = os.path.splitext(file_name)[1].lower()

        # Determine content type if not provided
        if not content_type:
            content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'

        # Create the asset record
        asset = self.create_media_asset(
            file_name=file_name,
            file_type=file_type,
            content_type=content_type,
            uploaded_by=uploaded_by,
            tag_ids=tag_ids,
        )

        # Upload the file content
        return self.upload_file(asset.id, file_content)

    def update_media_asset(
            self,
            asset_id: str,
            data: Dict[str, Any],
            user_id: Optional[str] = None,
    ) -> Optional[MediaAsset]:
        """
        Update a media asset.

        Args:
            asset_id: The UUID of the media asset
            data: Dictionary of fields to update
            user_id: Optional ID of the user performing the update

        Returns:
            The updated media asset if found, None otherwise

        Raises:
            BusinessRuleException: If update violates business rules
        """
        asset = self.repository.get_by_id(asset_id)
        if not asset:
            return None

        update_data = {}

        # Handle fields that can be updated
        if "file_name" in data:
            update_data["file_name"] = data["file_name"]

        # Handle tag updates in a transaction
        with self.transaction():
            # Update the asset fields
            if update_data:
                asset = self.repository.update(asset_id, update_data)

            # Update tags if provided
            if "tag_ids" in data and data["tag_ids"] is not None:
                self._update_asset_tags(asset_id, data["tag_ids"])

            return self.repository.get_by_id_with_tags(asset_id)

    def delete_media_asset(self, asset_id: str) -> bool:
        """
        Delete a media asset and its file.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            True if the asset was deleted, False otherwise
        """
        asset = self.repository.get_by_id(asset_id)
        if not asset:
            return False

        # Delete the file if a storage service is configured
        if self.file_storage_service and asset.storage_location:
            try:
                self.file_storage_service.delete_file(asset.storage_location)
            except Exception as e:
                logger.error(f"Failed to delete file for asset {asset_id}: {str(e)}")
                # Continue with database deletion even if file deletion fails

        # Delete all tag associations and the asset itself in a transaction
        with self.transaction():
            # Delete tag associations
            self.asset_tag_repository.delete_by_asset(asset_id)

            # Delete the asset
            return self.repository.delete(asset_id)

    def get_file_content(self, asset_id: str) -> BinaryIO:
        """
        Get the file content for a media asset.

        Args:
            asset_id: The UUID of the media asset

        Returns:
            The file content as a binary stream

        Raises:
            EntityNotFoundException: If the asset is not found
            FileStorageException: If file retrieval fails
        """
        asset = self.repository.get_by_id(asset_id)
        if not asset:
            raise EntityNotFoundException(f"Media asset with ID {asset_id} not found")

        if not asset.storage_location:
            raise BusinessRuleException(f"No file content for asset {asset_id}")

        if self.file_storage_service is None:
            raise BusinessRuleException("File storage service is not configured")

        try:
            return self.file_storage_service.get_file(asset.storage_location)
        except Exception as e:
            logger.error(f"Failed to retrieve file for asset {asset_id}: {str(e)}")
            raise FileStorageException(f"Failed to retrieve file: {str(e)}")

    def add_tags_to_asset(self, asset_id: str, tag_ids: List[str]) -> MediaAsset:
        """
        Add tags to a media asset.

        Args:
            asset_id: The UUID of the media asset
            tag_ids: List of tag UUIDs to add

        Returns:
            The updated media asset

        Raises:
            EntityNotFoundException: If the asset is not found
        """
        asset = self.repository.get_by_id(asset_id)
        if not asset:
            raise EntityNotFoundException(f"Media asset with ID {asset_id} not found")

        with self.transaction():
            for tag_id in tag_ids:
                # Verify that the tag exists
                tag = self.tag_repository.get_by_id(tag_id)
                if not tag:
                    raise EntityNotFoundException(f"Tag with ID {tag_id} not found")

                # Check if the association already exists
                existing = self.asset_tag_repository.get_by_asset_and_tag(asset_id, tag_id)
                if not existing:
                    # Create the association
                    self.asset_tag_repository.create_with_id({
                        "media_asset_id": asset_id,
                        "tag_id": tag_id,
                    })

            return self.repository.get_by_id_with_tags(asset_id)

    def remove_tags_from_asset(self, asset_id: str, tag_ids: List[str]) -> MediaAsset:
        """
        Remove tags from a media asset.

        Args:
            asset_id: The UUID of the media asset
            tag_ids: List of tag UUIDs to remove

        Returns:
            The updated media asset

        Raises:
            EntityNotFoundException: If the asset is not found
        """
        asset = self.repository.get_by_id(asset_id)
        if not asset:
            raise EntityNotFoundException(f"Media asset with ID {asset_id} not found")

        with self.transaction():
            for tag_id in tag_ids:
                # Delete the association
                self.asset_tag_repository.delete_by_asset_and_tag(asset_id, tag_id)

            return self.repository.get_by_id_with_tags(asset_id)

    def get_assets_by_tag(
            self, tag_id: str, skip: int = 0, limit: int = 100
    ) -> List[MediaAsset]:
        """
        Get all media assets with a specific tag.

        Args:
            tag_id: The UUID of the tag
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of media assets with the specified tag

        Raises:
            EntityNotFoundException: If the tag is not found
        """
        tag = self.tag_repository.get_by_id(tag_id)
        if not tag:
            raise EntityNotFoundException(f"Tag with ID {tag_id} not found")

        return self.repository.get_assets_by_tag(tag_id, skip, limit)

    def _update_asset_tags(self, asset_id: str, tag_ids: List[str]) -> None:
        """
        Update the tags for a media asset by replacing all existing tags.

        Args:
            asset_id: The UUID of the media asset
            tag_ids: List of tag UUIDs to assign

        Raises:
            EntityNotFoundException: If any tag is not found
        """
        # Verify all tags exist first
        for tag_id in tag_ids:
            tag = self.tag_repository.get_by_id(tag_id)
            if not tag:
                raise EntityNotFoundException(f"Tag with ID {tag_id} not found")

        # Get current tag associations
        current_associations = self.asset_tag_repository.get_by_asset(asset_id)
        current_tag_ids = [assoc.tag_id for assoc in current_associations]

        # Determine tags to add and remove
        tags_to_add = [tag_id for tag_id in tag_ids if tag_id not in current_tag_ids]
        tags_to_remove = [tag_id for tag_id in current_tag_ids if tag_id not in tag_ids]

        # Remove tags that are no longer associated
        for tag_id in tags_to_remove:
            self.asset_tag_repository.delete_by_asset_and_tag(asset_id, tag_id)

        # Add new tag associations
        for tag_id in tags_to_add:
            self.asset_tag_repository.create_with_id({
                "media_asset_id": asset_id,
                "tag_id": tag_id,
            })