# File: app/repositories/file_metadata_repository.py

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from app.repositories.base_repository import BaseRepository
from app.db.models.file_metadata import FileMetadata


class FileMetadataRepository(BaseRepository[FileMetadata]):
    """
    Repository for file metadata operations in the HideSync system.

    Provides methods for creating, retrieving, updating, and deleting file metadata,
    as well as specialized queries for file-specific needs.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the FileMetadataRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, FileMetadata, encryption_service)

    def create_file_metadata(self, data: Dict[str, Any]) -> FileMetadata:
        """
        Create a new file metadata record.

        Args:
            data: File metadata information including filename, size, path, etc.

        Returns:
            Created FileMetadata instance
        """
        return self.create(data)

    def get_by_file_id(self, file_id: str) -> Optional[FileMetadata]:
        """
        Get file metadata by unique file_id.

        Args:
            file_id: UUID of the file

        Returns:
            FileMetadata if found, None otherwise
        """
        return (
            self.session.query(FileMetadata)
            .filter(FileMetadata.file_id == file_id, FileMetadata.is_deleted == False)
            .first()
        )

    def find_by_entity(
        self, entity_type: str, entity_id: Union[str, int]
    ) -> List[FileMetadata]:
        """
        Find all files associated with a specific entity.

        Args:
            entity_type: Type of entity (e.g., 'pattern', 'project')
            entity_id: ID of the entity

        Returns:
            List of FileMetadata instances
        """
        return (
            self.session.query(FileMetadata)
            .filter(
                FileMetadata.entity_type == entity_type,
                FileMetadata.entity_id == str(entity_id),
                FileMetadata.is_deleted == False,
            )
            .order_by(desc(FileMetadata.created_at))
            .all()
        )

    def find_by_content_type(
        self, content_type: str, limit: int = 100
    ) -> List[FileMetadata]:
        """
        Find files by content type.

        Args:
            content_type: MIME type to filter by
            limit: Maximum number of results

        Returns:
            List of FileMetadata instances
        """
        # Allow for wildcard search (e.g., 'image/*')
        if content_type.endswith("/*"):
            base_type = content_type.split("/")[0]
            filter_clause = FileMetadata.content_type.like(f"{base_type}/%")
        else:
            filter_clause = FileMetadata.content_type == content_type

        return (
            self.session.query(FileMetadata)
            .filter(filter_clause, FileMetadata.is_deleted == False)
            .order_by(desc(FileMetadata.created_at))
            .limit(limit)
            .all()
        )

    def find_recent(self, limit: int = 20) -> List[FileMetadata]:
        """
        Find recently uploaded files.

        Args:
            limit: Maximum number of results

        Returns:
            List of FileMetadata instances
        """
        return (
            self.session.query(FileMetadata)
            .filter(FileMetadata.is_deleted == False)
            .order_by(desc(FileMetadata.created_at))
            .limit(limit)
            .all()
        )

    def get_by_checksum(self, checksum: str) -> List[FileMetadata]:
        """
        Find files with a specific checksum.

        Useful for identifying duplicate files.

        Args:
            checksum: File checksum hash

        Returns:
            List of FileMetadata instances with the given checksum
        """
        return (
            self.session.query(FileMetadata)
            .filter(FileMetadata.checksum == checksum, FileMetadata.is_deleted == False)
            .all()
        )

    def mark_as_deleted(self, file_id: str) -> Optional[FileMetadata]:
        """
        Mark a file as deleted (soft delete).

        Args:
            file_id: UUID of the file

        Returns:
            Updated FileMetadata if found, None otherwise
        """
        file_metadata = self.get_by_file_id(file_id)
        if file_metadata:
            file_metadata.is_deleted = True
            file_metadata.deleted_at = datetime.now()
            self.session.commit()
            return file_metadata
        return None

    def permanently_delete(self, file_id: str) -> bool:
        """
        Permanently delete file metadata.

        Args:
            file_id: UUID of the file

        Returns:
            True if deleted, False if not found
        """
        file_metadata = self.get_by_file_id(file_id)
        if file_metadata:
            self.session.delete(file_metadata)
            self.session.commit()
            return True
        return False

    def update_metadata(
        self, file_id: str, metadata: Dict[str, Any]
    ) -> Optional[FileMetadata]:
        """
        Update the additional metadata for a file.

        Args:
            file_id: UUID of the file
            metadata: Additional metadata to store

        Returns:
            Updated FileMetadata if found, None otherwise
        """
        file_metadata = self.get_by_file_id(file_id)
        if file_metadata:
            # Merge with existing metadata if present
            if file_metadata.metadata and isinstance(file_metadata.metadata, dict):
                file_metadata.metadata.update(metadata)
            else:
                file_metadata.metadata = metadata

            self.session.commit()
            return file_metadata
        return None

    def find_orphaned(self, days_threshold: int = 7) -> List[FileMetadata]:
        """
        Find orphaned files (not associated with any entity and older than threshold).

        Args:
            days_threshold: Number of days to consider a file orphaned

        Returns:
            List of orphaned FileMetadata instances
        """
        threshold_date = datetime.now() - timedelta(days=days_threshold)

        return (
            self.session.query(FileMetadata)
            .filter(
                FileMetadata.entity_type.is_(None),
                FileMetadata.entity_id.is_(None),
                FileMetadata.created_at < threshold_date,
                FileMetadata.is_deleted == False,
            )
            .all()
        )

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored files.

        Returns:
            Dictionary with stats like total count, total size, counts by type
        """
        total_count = (
            self.session.query(func.count(FileMetadata.id))
            .filter(FileMetadata.is_deleted == False)
            .scalar()
            or 0
        )

        total_size = (
            self.session.query(func.sum(FileMetadata.size))
            .filter(FileMetadata.is_deleted == False)
            .scalar()
            or 0
        )

        # Get counts by content type
        type_counts = (
            self.session.query(FileMetadata.content_type, func.count(FileMetadata.id))
            .filter(FileMetadata.is_deleted == False)
            .group_by(FileMetadata.content_type)
            .all()
        )

        # Get counts by entity type
        entity_counts = (
            self.session.query(FileMetadata.entity_type, func.count(FileMetadata.id))
            .filter(
                FileMetadata.entity_type.isnot(None), FileMetadata.is_deleted == False
            )
            .group_by(FileMetadata.entity_type)
            .all()
        )

        return {
            "total_count": total_count,
            "total_size": total_size,
            "by_content_type": {t[0]: t[1] for t in type_counts},
            "by_entity_type": {t[0]: t[1] for t in entity_counts},
        }

    def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        content_type: Optional[str] = None,
        search_term: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[List[FileMetadata], int]:
        """
        Get paginated list of file metadata with filtering options.

        Args:
            page: Page number (1-indexed)
            per_page: Number of items per page
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            content_type: Filter by content type
            search_term: Search in filename and description
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            Tuple of (list of FileMetadata, total count)
        """
        query = self.session.query(FileMetadata).filter(
            FileMetadata.is_deleted == False
        )

        # Apply filters
        if entity_type:
            query = query.filter(FileMetadata.entity_type == entity_type)

        if entity_id:
            query = query.filter(FileMetadata.entity_id == entity_id)

        if content_type:
            if content_type.endswith("/*"):
                base_type = content_type.split("/")[0]
                query = query.filter(FileMetadata.content_type.like(f"{base_type}/%"))
            else:
                query = query.filter(FileMetadata.content_type == content_type)

        if search_term:
            search_term = f"%{search_term}%"
            query = query.filter(
                or_(
                    FileMetadata.filename.ilike(search_term),
                    FileMetadata.original_filename.ilike(search_term),
                    FileMetadata.description.ilike(search_term),
                )
            )

        # Get total count
        total = query.count()

        # Apply sorting
        if sort_dir.lower() == "asc":
            query = query.order_by(getattr(FileMetadata, sort_by))
        else:
            query = query.order_by(desc(getattr(FileMetadata, sort_by)))

        # Apply pagination
        query = query.offset((page - 1) * per_page).limit(per_page)

        return query.all(), total
