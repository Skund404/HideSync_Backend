# File: app/services/file_storage_service.py

from typing import Dict, Any, List, Optional, BinaryIO, Tuple, Union
from sqlalchemy.orm import Session
import uuid
import os
import mimetypes
import hashlib
import io
import logging
from pathlib import Path
from datetime import datetime
import shutil
from PIL import Image

from app.core.exceptions import StorageException, InvalidPathException
from app.repositories.file_metadata_repository import FileMetadataRepository

logger = logging.getLogger(__name__)


class FileStorageService:
    """
    Service for managing file storage operations in the HideSync system.

    Handles file uploads, downloads, and metadata management, including:
    - Secure file storage with proper organization
    - Thumbnail generation for supported file types
    - File integrity verification
    - Association with system entities
    """

    def __init__(
        self,
        base_path: str,
        metadata_repository=None,
        security_context=None,
        generate_thumbnails: bool = True,
        max_thumbnail_size: Tuple[int, int] = (300, 300),
    ):
        """
        Initialize file storage service with dependencies.

        Args:
            base_path: Base directory for file storage
            metadata_repository: Repository for file metadata
            security_context: Optional security context for authorization
            generate_thumbnails: Whether to generate thumbnails for images
            max_thumbnail_size: Maximum dimensions for thumbnails (width, height)
        """
        self.base_path = Path(base_path)
        self.metadata_repository = metadata_repository
        self.security_context = security_context
        self.generate_thumbnails = generate_thumbnails
        self.max_thumbnail_size = max_thumbnail_size

        # Create basic directory structure
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(self.base_path / "thumbnails", exist_ok=True)

    def store_file(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[Union[str, int]] = None,
        description: Optional[str] = None,
        is_public: bool = False,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store a file and its metadata.

        Args:
            file_data: Binary file content or file-like object
            filename: Original filename
            content_type: MIME type (detected if not provided)
            entity_type: Type of entity this file relates to
            entity_id: ID of related entity
            description: Description of the file
            is_public: Whether the file should be publicly accessible
            user_id: ID of the user uploading the file
            metadata: Additional metadata for the file

        Returns:
            File metadata dictionary

        Raises:
            StorageException: If file storage fails
        """
        try:
            # Convert file-like object to bytes if needed
            if hasattr(file_data, "read"):
                file_data = file_data.read()

            # Generate a unique file ID
            file_id = str(uuid.uuid4())

            # Detect content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = "application/octet-stream"

            # Calculate file hash for integrity verification
            file_hash = hashlib.sha256(file_data).hexdigest()

            # Generate storage paths
            extension = Path(filename).suffix
            if not extension:
                # Try to get extension from content type
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    extension = ext
                else:
                    extension = ".bin"

            storage_path = self._get_storage_path(file_id, extension)

            # Get user_id from security context if not provided
            if (
                user_id is None
                and self.security_context
                and hasattr(self.security_context, "user_id")
            ):
                user_id = self.security_context.user_id

            # Ensure directory exists
            os.makedirs(storage_path.parent, exist_ok=True)

            # Write the file
            with open(storage_path, "wb") as f:
                f.write(file_data)

            # Generate thumbnail if applicable
            thumbnail_path = None
            if self.generate_thumbnails and self._is_image(content_type):
                try:
                    thumbnail_path = self._generate_thumbnail(
                        file_data, file_id, extension
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to generate thumbnail for {file_id}: {str(e)}"
                    )

            # Record file metadata
            file_metadata_data = {
                "file_id": file_id,
                "filename": os.path.basename(storage_path),
                "original_filename": filename,
                "content_type": content_type,
                "size": len(file_data),
                "checksum": file_hash,
                "storage_path": str(storage_path.relative_to(self.base_path)),
                "thumbnail_path": (
                    str(thumbnail_path.relative_to(self.base_path))
                    if thumbnail_path
                    else None
                ),
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id is not None else None,
                "user_id": user_id,
                "description": description,
                "is_public": is_public,
                "metadata": metadata,
            }

            # Store metadata if repository is available
            if self.metadata_repository:
                stored_metadata = self.metadata_repository.create_file_metadata(
                    file_metadata_data
                )
                return stored_metadata.to_dict()

            return file_metadata_data

        except Exception as e:
            logger.error(f"Failed to store file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to store file: {str(e)}")

    def retrieve_file(self, file_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Retrieve a file and its metadata.

        Args:
            file_id: File ID (UUID)

        Returns:
            Tuple of (file_data, metadata)

        Raises:
            StorageException: If file retrieval fails
        """
        try:
            # Get metadata
            if self.metadata_repository:
                metadata = self.metadata_repository.get_by_file_id(file_id)
                if not metadata:
                    raise StorageException(f"File metadata not found: {file_id}")

                metadata_dict = metadata.to_dict()
                storage_path = self.base_path / metadata.storage_path
            else:
                # Try to find the file without metadata
                storage_pattern = f"**/{file_id}.*"
                matching_files = list(self.base_path.glob(storage_pattern))

                if not matching_files:
                    raise StorageException(f"File not found: {file_id}")

                storage_path = matching_files[0]

                # Create basic metadata
                metadata_dict = {
                    "file_id": file_id,
                    "filename": storage_path.name,
                    "original_filename": storage_path.name,
                    "storage_path": str(storage_path.relative_to(self.base_path)),
                }

            # Check if file exists
            if not storage_path.exists():
                raise StorageException(f"File not found at {storage_path}")

            # Read file data
            with open(storage_path, "rb") as f:
                file_data = f.read()

            # Verify file integrity if hash is available
            if "checksum" in metadata_dict:
                current_hash = hashlib.sha256(file_data).hexdigest()
                if current_hash != metadata_dict["checksum"]:
                    logger.warning(f"File integrity check failed for {file_id}")

            return file_data, metadata_dict

        except StorageException:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to retrieve file: {str(e)}")

    def delete_file(self, file_id: str, permanent: bool = False) -> bool:
        """
        Delete a file and its metadata.

        Args:
            file_id: File ID
            permanent: Whether to permanently delete or use soft delete

        Returns:
            True if deleted successfully

        Raises:
            StorageException: If file deletion fails
        """
        try:
            # Get metadata
            metadata = None
            if self.metadata_repository:
                metadata = self.metadata_repository.get_by_file_id(file_id)

            # Find file path
            if metadata and hasattr(metadata, "storage_path"):
                storage_path = self.base_path / metadata.storage_path
                thumbnail_path = (
                    self.base_path / metadata.thumbnail_path
                    if metadata.thumbnail_path
                    else None
                )
            else:
                # Try to find the file without metadata
                storage_pattern = f"**/{file_id}.*"
                matching_files = list(self.base_path.glob(storage_pattern))

                if not matching_files:
                    return False

                storage_path = matching_files[0]
                thumbnail_path = self.base_path / "thumbnails" / storage_path.name

            # Delete the physical file if permanent deletion
            if permanent:
                if storage_path.exists():
                    os.remove(storage_path)

                if thumbnail_path and thumbnail_path.exists():
                    os.remove(thumbnail_path)

            # Update or delete metadata
            if self.metadata_repository and metadata:
                if permanent:
                    self.metadata_repository.permanently_delete(file_id)
                else:
                    self.metadata_repository.mark_as_deleted(file_id)

            return True

        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to delete file: {str(e)}")

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata without retrieving the file.

        Args:
            file_id: File ID

        Returns:
            File metadata dictionary if found, None otherwise
        """
        if not self.metadata_repository:
            return None

        metadata = self.metadata_repository.get_by_file_id(file_id)
        return metadata.to_dict() if metadata else None

    def update_file_metadata(
        self, file_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update file metadata.

        Args:
            file_id: File ID
            updates: Dictionary of metadata fields to update

        Returns:
            Updated metadata dictionary if found, None otherwise

        Raises:
            StorageException: If update fails
        """
        if not self.metadata_repository:
            raise StorageException("Metadata repository not available")

        # Don't allow updating certain fields
        restricted_fields = ["file_id", "filename", "storage_path", "size", "checksum"]
        for field in restricted_fields:
            if field in updates:
                del updates[field]

        # Update metadata
        metadata = self.metadata_repository.update(file_id, updates)
        return metadata.to_dict() if metadata else None

    def associate_with_entity(
        self, file_id: str, entity_type: str, entity_id: Union[str, int]
    ) -> Optional[Dict[str, Any]]:
        """
        Associate a file with an entity.

        Args:
            file_id: File ID
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            Updated metadata dictionary if found, None otherwise
        """
        if not self.metadata_repository:
            return None

        updates = {"entity_type": entity_type, "entity_id": str(entity_id)}

        metadata = self.metadata_repository.update(file_id, updates)
        return metadata.to_dict() if metadata else None

    def get_files_for_entity(
        self,
        entity_type: str,
        entity_id: Union[str, int],
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all files associated with an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            include_deleted: Whether to include soft-deleted files

        Returns:
            List of file metadata dictionaries
        """
        if not self.metadata_repository:
            return []

        files = self.metadata_repository.find_by_entity(entity_type, entity_id)
        return [f.to_dict() for f in files]

    def search_files(
        self,
        search_term: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[Union[str, int]] = None,
        content_type: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search for files based on various criteria.

        Args:
            search_term: Text to search for in filename or description
            entity_type: Optional entity type filter
            entity_id: Optional entity ID filter
            content_type: Optional content type filter
            user_id: Optional user ID filter
            page: Page number
            per_page: Items per page

        Returns:
            Tuple of (list of file metadata dictionaries, total count)
        """
        if not self.metadata_repository:
            return [], 0

        files, total = self.metadata_repository.list_paginated(
            page=page,
            per_page=per_page,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            content_type=content_type,
            search_term=search_term,
        )

        return [f.to_dict() for f in files], total

    def cleanup_orphaned_files(self, days_threshold: int = 7) -> int:
        """
        Delete orphaned files (not associated with any entity and older than threshold).

        Args:
            days_threshold: Number of days to consider a file orphaned

        Returns:
            Number of files deleted

        Raises:
            StorageException: If cleanup fails
        """
        if not self.metadata_repository:
            return 0

        try:
            # Find orphaned files
            orphaned_files = self.metadata_repository.find_orphaned(days_threshold)

            # Delete each file
            deleted_count = 0
            for file in orphaned_files:
                if self.delete_file(file.file_id, permanent=True):
                    deleted_count += 1

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clean up orphaned files: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to clean up orphaned files: {str(e)}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored files.

        Returns:
            Dictionary with stats like total count, total size, counts by type
        """
        if not self.metadata_repository:
            return {
                "total_count": 0,
                "total_size": 0,
                "by_content_type": {},
                "by_entity_type": {},
            }

        return self.metadata_repository.get_storage_stats()

    def _get_storage_path(self, file_id: str, extension: str) -> Path:
        """
        Generate storage path for a file.

        Args:
            file_id: File ID
            extension: File extension

        Returns:
            Path object for the file
        """
        # Create a directory structure based on the first characters of the ID
        # This helps to avoid having too many files in a single directory
        if not extension.startswith("."):
            extension = f".{extension}"

        dir1, dir2 = file_id[:2], file_id[2:4]
        return self.base_path / dir1 / dir2 / f"{file_id}{extension}"

    def _generate_thumbnail(
        self, image_data: bytes, file_id: str, extension: str
    ) -> Path:
        """
        Generate thumbnail for an image.

        Args:
            image_data: Image file data
            file_id: File ID
            extension: File extension

        Returns:
            Path to the thumbnail

        Raises:
            Exception: If thumbnail generation fails
        """
        try:
            # Create thumbnail directory if it doesn't exist
            thumbnail_dir = self.base_path / "thumbnails"
            os.makedirs(thumbnail_dir, exist_ok=True)

            # Generate thumbnail path
            thumbnail_path = thumbnail_dir / f"{file_id}_thumb{extension}"

            # Generate thumbnail
            with io.BytesIO(image_data) as img_file:
                with Image.open(img_file) as img:
                    img.thumbnail(self.max_thumbnail_size)
                    img.save(thumbnail_path)

            return thumbnail_path

        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {str(e)}")
            raise

    def _is_image(self, content_type: str) -> bool:
        """
        Check if a content type is an image.

        Args:
            content_type: MIME type to check

        Returns:
            True if content type is an image, False otherwise
        """
        return content_type.startswith("image/")
