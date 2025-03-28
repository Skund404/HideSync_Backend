# File: app/services/storage_service.py

from typing import Dict, Any, List, Optional, BinaryIO, Tuple, Union
from sqlalchemy.orm import Session
import uuid
import os
import mimetypes
from pathlib import Path
import hashlib
import shutil
from datetime import datetime
import logging

from app.core.exceptions import StorageException, InvalidPathException

logger = logging.getLogger(__name__)


class FileStorageService:
    """
    Service for managing file storage operations.

    Handles file uploads, downloads, and metadata management.
    """

    def __init__(self, base_path: str, metadata_repository=None, security_context=None):
        """
        Initialize file storage service.

        Args:
            base_path: Base directory for file storage
            metadata_repository: Repository for file metadata
            security_context: Optional security context for authorization
        """
        self.base_path = Path(base_path)
        self.metadata_repository = metadata_repository
        self.security_context = security_context

        # Ensure storage directory exists
        os.makedirs(self.base_path, exist_ok=True)

    def store_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store a file and its metadata.

        Args:
            file_data: Binary file content
            filename: Original filename
            content_type: MIME type (detected if not provided)
            metadata: Additional metadata

        Returns:
            File metadata including ID and path

        Raises:
            StorageException: If file storage fails
        """
        try:
            # Generate file ID
            file_id = str(uuid.uuid4())

            # Detect content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = "application/octet-stream"

            # Calculate file hash for integrity verification
            file_hash = hashlib.sha256(file_data).hexdigest()

            # Generate storage path
            extension = Path(filename).suffix
            storage_path = self._get_storage_path(file_id, extension)

            # Save the file
            os.makedirs(storage_path.parent, exist_ok=True)
            with open(storage_path, "wb") as f:
                f.write(file_data)

            # Create and store metadata
            file_metadata = {
                "id": file_id,
                "original_filename": filename,
                "content_type": content_type,
                "size": len(file_data),
                "hash": file_hash,
                "storage_path": str(storage_path.relative_to(self.base_path)),
                "created_at": datetime.now().isoformat(),
                "created_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    and hasattr(self.security_context, "current_user")
                    else None
                ),
                **(metadata or {}),
            }

            # Store metadata if repository is available
            if self.metadata_repository:
                self.metadata_repository.create(file_metadata)

            return file_metadata

        except Exception as e:
            logger.error(f"Failed to store file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to store file: {str(e)}", "STORAGE_001")

    def retrieve_file(self, file_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Retrieve a file and its metadata.

        Args:
            file_id: File ID

        Returns:
            Tuple of (file_data, metadata)

        Raises:
            StorageException: If file retrieval fails
        """
        try:
            # Get metadata
            if self.metadata_repository:
                metadata = self.metadata_repository.get_by_id(file_id)
                if not metadata:
                    raise StorageException(
                        f"File metadata not found: {file_id}", "STORAGE_002"
                    )

                storage_path = self.base_path / metadata["storage_path"]
            else:
                # Try to find the file without metadata
                storage_pattern = f"**/{file_id}.*"
                matching_files = list(self.base_path.glob(storage_pattern))

                if not matching_files:
                    raise StorageException(f"File not found: {file_id}", "STORAGE_002")

                storage_path = matching_files[0]

                # Create basic metadata
                metadata = {
                    "id": file_id,
                    "original_filename": storage_path.name,
                    "storage_path": str(storage_path.relative_to(self.base_path)),
                }

            # Read file data
            with open(storage_path, "rb") as f:
                file_data = f.read()

            # Verify file integrity if hash is available
            if "hash" in metadata:
                current_hash = hashlib.sha256(file_data).hexdigest()
                if current_hash != metadata["hash"]:
                    raise StorageException(
                        f"File integrity check failed: {file_id}", "STORAGE_003"
                    )

            return file_data, metadata

        except StorageException:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to retrieve file: {str(e)}", "STORAGE_004")

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file and its metadata.

        Args:
            file_id: File ID

        Returns:
            True if deleted successfully

        Raises:
            StorageException: If file deletion fails
        """
        try:
            # Get metadata
            metadata = None
            if self.metadata_repository:
                metadata = self.metadata_repository.get_by_id(file_id)

            # Find the file
            if metadata and "storage_path" in metadata:
                storage_path = self.base_path / metadata["storage_path"]
            else:
                # Try to find the file without metadata
                storage_pattern = f"**/{file_id}.*"
                matching_files = list(self.base_path.glob(storage_pattern))

                if not matching_files:
                    return False

                storage_path = matching_files[0]

            # Delete the file
            if storage_path.exists():
                os.remove(storage_path)

            # Delete metadata if repository is available
            if self.metadata_repository and metadata:
                self.metadata_repository.delete(file_id)

            return True

        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to delete file: {str(e)}", "STORAGE_005")

    def list_files(
        self,
        directory: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List files with optional filtering.

        Args:
            directory: Optional subdirectory path
            file_type: Optional file type filter (MIME type)
            limit: Maximum number of files to return
            offset: Number of files to skip

        Returns:
            List of file metadata

        Raises:
            StorageException: If file listing fails
            InvalidPathException: If directory path is invalid
        """
        try:
            # Check if we're using metadata repository
            if self.metadata_repository:
                # Build filters
                filters = {}
                if directory:
                    filters["directory"] = directory
                if file_type:
                    filters["content_type"] = file_type

                # Get files from repository
                return self.metadata_repository.list(
                    skip=offset, limit=limit, **filters
                )
            else:
                # Manual file system traversal
                search_path = self.base_path
                if directory:
                    # Validate directory path
                    directory_path = Path(directory)
                    if ".." in directory_path.parts:
                        raise InvalidPathException("Invalid directory path")

                    search_path = self.base_path / directory_path

                if not search_path.exists() or not search_path.is_dir():
                    return []

                # List files
                files = []
                for file_path in search_path.glob("**/*"):
                    if file_path.is_file():
                        # Skip hidden files
                        if file_path.name.startswith("."):
                            continue

                        # Filter by file type if specified
                        if file_type:
                            mime_type, _ = mimetypes.guess_type(file_path.name)
                            if mime_type != file_type:
                                continue

                        # Create basic metadata
                        rel_path = file_path.relative_to(self.base_path)
                        files.append(
                            {
                                "id": file_path.stem,
                                "original_filename": file_path.name,
                                "storage_path": str(rel_path),
                                "size": file_path.stat().st_size,
                                "created_at": datetime.fromtimestamp(
                                    file_path.stat().st_ctime
                                ).isoformat(),
                            }
                        )

                # Apply pagination
                return files[offset : offset + limit]

        except InvalidPathException:
            raise
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to list files: {str(e)}", "STORAGE_006")

    def create_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        Create a new directory.

        Args:
            directory_path: Directory path to create

        Returns:
            Directory metadata

        Raises:
            StorageException: If directory creation fails
            InvalidPathException: If directory path is invalid
        """
        try:
            # Validate directory path
            dir_path = Path(directory_path)
            if ".." in dir_path.parts:
                raise InvalidPathException("Invalid directory path")

            # Create full path
            full_path = self.base_path / dir_path

            # Create directory
            os.makedirs(full_path, exist_ok=True)

            return {
                "path": directory_path,
                "created_at": datetime.now().isoformat(),
                "created_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    and hasattr(self.security_context, "current_user")
                    else None
                ),
            }

        except InvalidPathException:
            raise
        except Exception as e:
            logger.error(f"Failed to create directory: {str(e)}", exc_info=True)
            raise StorageException(
                f"Failed to create directory: {str(e)}", "STORAGE_007"
            )

    def copy_file(
        self, file_id: str, new_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a copy of a file.

        Args:
            file_id: File ID to copy
            new_filename: Optional new filename

        Returns:
            Metadata of the new file

        Raises:
            StorageException: If file copy fails
        """
        try:
            # Retrieve original file
            file_data, metadata = self.retrieve_file(file_id)

            # Determine new filename
            if not new_filename:
                original_name = metadata.get("original_filename", "")
                name_parts = original_name.rsplit(".", 1)

                if len(name_parts) > 1:
                    new_filename = f"{name_parts[0]}_copy.{name_parts[1]}"
                else:
                    new_filename = f"{original_name}_copy"

            # Create copy of metadata
            new_metadata = metadata.copy() if isinstance(metadata, dict) else {}
            if "id" in new_metadata:
                del new_metadata["id"]
            if "storage_path" in new_metadata:
                del new_metadata["storage_path"]
            if "hash" in new_metadata:
                del new_metadata["hash"]
            if "created_at" in new_metadata:
                del new_metadata["created_at"]

            # Store new file
            return self.store_file(
                file_data=file_data,
                filename=new_filename,
                content_type=metadata.get("content_type"),
                metadata=new_metadata,
            )

        except Exception as e:
            logger.error(f"Failed to copy file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to copy file: {str(e)}", "STORAGE_008")

    def move_file(self, file_id: str, new_directory: str) -> Dict[str, Any]:
        """
        Move a file to a different directory.

        Args:
            file_id: File ID to move
            new_directory: New directory path

        Returns:
            Updated file metadata

        Raises:
            StorageException: If file move fails
            InvalidPathException: If directory path is invalid
        """
        try:
            # Validate directory path
            dir_path = Path(new_directory)
            if ".." in dir_path.parts:
                raise InvalidPathException("Invalid directory path")

            # Get metadata
            if not self.metadata_repository:
                raise StorageException(
                    "Metadata repository required for move operation", "STORAGE_009"
                )

            metadata = self.metadata_repository.get_by_id(file_id)
            if not metadata:
                raise StorageException(
                    f"File metadata not found: {file_id}", "STORAGE_002"
                )

            # Get current storage path
            current_path = self.base_path / metadata["storage_path"]

            # Create new directory if it doesn't exist
            new_dir_full_path = self.base_path / dir_path
            os.makedirs(new_dir_full_path, exist_ok=True)

            # Generate new path
            filename = Path(metadata["storage_path"]).name
            new_path = new_dir_full_path / filename

            # Move the file
            shutil.move(str(current_path), str(new_path))

            # Update metadata
            new_relative_path = new_path.relative_to(self.base_path)
            updated_metadata = {
                "storage_path": str(new_relative_path),
                "updated_at": datetime.now().isoformat(),
                "updated_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    and hasattr(self.security_context, "current_user")
                    else None
                ),
            }

            # Update in repository
            self.metadata_repository.update(file_id, updated_metadata)

            # Get updated metadata
            return self.metadata_repository.get_by_id(file_id)

        except InvalidPathException:
            raise
        except Exception as e:
            logger.error(f"Failed to move file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to move file: {str(e)}", "STORAGE_010")

    def rename_file(self, file_id: str, new_filename: str) -> Dict[str, Any]:
        """
        Rename a file.

        Args:
            file_id: File ID to rename
            new_filename: New filename

        Returns:
            Updated file metadata

        Raises:
            StorageException: If file rename fails
        """
        try:
            # Get metadata
            if not self.metadata_repository:
                raise StorageException(
                    "Metadata repository required for rename operation", "STORAGE_011"
                )

            metadata = self.metadata_repository.get_by_id(file_id)
            if not metadata:
                raise StorageException(
                    f"File metadata not found: {file_id}", "STORAGE_002"
                )

            # Get current storage path
            current_path = self.base_path / metadata["storage_path"]

            # Generate new path (same directory, new name)
            directory = current_path.parent
            extension = current_path.suffix

            # Ensure the new filename has the same extension
            if not new_filename.endswith(extension):
                new_filename = f"{new_filename}{extension}"

            new_path = directory / new_filename

            # Rename the file
            os.rename(current_path, new_path)

            # Update metadata
            new_relative_path = new_path.relative_to(self.base_path)
            updated_metadata = {
                "original_filename": new_filename,
                "storage_path": str(new_relative_path),
                "updated_at": datetime.now().isoformat(),
                "updated_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    and hasattr(self.security_context, "current_user")
                    else None
                ),
            }

            # Update in repository
            self.metadata_repository.update(file_id, updated_metadata)

            # Get updated metadata
            return self.metadata_repository.get_by_id(file_id)

        except Exception as e:
            logger.error(f"Failed to rename file: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to rename file: {str(e)}", "STORAGE_012")

    # Add these methods to the StorageLocationService class

    def get_storage_locations(self, skip: int = 0, limit: int = 100, search_params=None):
        """
        Retrieve storage locations with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search_params: Optional search parameters

        Returns:
            List of storage locations matching the criteria
        """
        filters = {}

        if search_params:
            if search_params.type:
                filters["type"] = search_params.type
            if search_params.section:
                filters["section"] = search_params.section
            if search_params.status:
                filters["status"] = search_params.status
            if search_params.search:
                filters["search"] = search_params.search

        return self.repository.list(skip=skip, limit=limit, **filters)

    def get_storage_location(self, location_id: str):
        """
        Get a specific storage location by ID.

        Args:
            location_id: ID of the storage location to retrieve

        Returns:
            Storage location if found

        Raises:
            EntityNotFoundException: If the storage location doesn't exist
        """
        location = self.repository.get_by_id(location_id)
        if not location:
            from app.core.exceptions import EntityNotFoundException
            raise EntityNotFoundException("Storage location", location_id)
        return location

    def get_storage_cells(self, location_id: str, occupied: bool = None):
        """
        Get storage cells for a specific location.

        Args:
            location_id: ID of the storage location
            occupied: Optional filter by occupancy status

        Returns:
            List of cells in the location

        Raises:
            EntityNotFoundException: If the storage location doesn't exist
        """
        # Check if the location exists
        location = self.repository.get_by_id(location_id)
        if not location:
            from app.core.exceptions import EntityNotFoundException
            raise EntityNotFoundException("Storage location", location_id)

        # Get cells with filter if provided
        filters = {"storage_id": location_id}
        if occupied is not None:
            filters["occupied"] = occupied

        return self.cell_repository.list(**filters)

    def create_storage_cell(self, location_id: str, cell_data, user_id=None):
        """
        Create a new storage cell in a location.

        Args:
            location_id: ID of the storage location
            cell_data: Cell creation data
            user_id: ID of the user creating the cell

        Returns:
            Created storage cell

        Raises:
            EntityNotFoundException: If the storage location doesn't exist
        """
        # Check if the location exists
        location = self.repository.get_by_id(location_id)
        if not location:
            from app.core.exceptions import EntityNotFoundException
            raise EntityNotFoundException("Storage location", location_id)

        # Prepare cell data
        cell_data_dict = cell_data.dict() if hasattr(cell_data, "dict") else dict(cell_data)
        cell_data_dict["storage_id"] = location_id

        # Create cell
        return self.cell_repository.create(cell_data_dict)

    def get_storage_assignments(self, item_id=None, item_type=None, location_id=None):
        """
        Get storage assignments with optional filtering.

        Args:
            item_id: Optional filter by item ID
            item_type: Optional filter by item type
            location_id: Optional filter by storage location ID

        Returns:
            List of assignments matching the criteria
        """
        filters = {}
        if item_id is not None:
            filters["material_id"] = item_id
        if item_type is not None:
            filters["material_type"] = item_type
        if location_id is not None:
            filters["storage_id"] = location_id

        return self.assignment_repository.list(**filters)

    def create_storage_assignment(self, assignment_data, user_id=None):
        """
        Create a new storage assignment.

        Args:
            assignment_data: Assignment creation data
            user_id: ID of the user creating the assignment

        Returns:
            Created storage assignment

        Raises:
            EntityNotFoundException: If related entities don't exist
        """
        # Extract data
        assignment_dict = assignment_data.dict() if hasattr(assignment_data, "dict") else dict(assignment_data)

        # Add assigned_by if provided
        if user_id and "assigned_by" not in assignment_dict:
            assignment_dict["assigned_by"] = str(user_id)

        # Set assigned date if not provided
        if "assigned_date" not in assignment_dict:
            from datetime import datetime
            assignment_dict["assigned_date"] = datetime.now().isoformat()

        # Make sure location exists
        storage_id = assignment_dict.get("storage_id")
        if storage_id:
            location = self.repository.get_by_id(storage_id)
            if not location:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("Storage location", storage_id)

        return self.assign_material_to_location(assignment_dict)

    def delete_storage_assignment(self, assignment_id, user_id=None):
        """
        Delete a storage assignment.

        Args:
            assignment_id: ID of the assignment to delete
            user_id: ID of the user deleting the assignment

        Returns:
            True if successfully deleted

        Raises:
            EntityNotFoundException: If the assignment doesn't exist
        """
        return self.remove_material_from_location(assignment_id)

    def get_storage_moves(self, skip=0, limit=100, item_id=None, item_type=None):
        """
        Get storage moves with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            item_id: Optional filter by item ID
            item_type: Optional filter by item type

        Returns:
            List of moves matching the criteria
        """
        filters = {}
        if item_id is not None:
            filters["material_id"] = item_id
        if item_type is not None:
            filters["material_type"] = item_type

        return self.move_repository.list(skip=skip, limit=limit, **filters)

    def create_storage_move(self, move_data, user_id=None):
        """
        Create a new storage move.

        Args:
            move_data: Move creation data
            user_id: ID of the user creating the move

        Returns:
            Created storage move

        Raises:
            EntityNotFoundException: If related entities don't exist
        """
        # Extract data
        move_dict = move_data.dict() if hasattr(move_data, "dict") else dict(move_data)

        # Add moved_by if provided
        if user_id and "moved_by" not in move_dict:
            move_dict["moved_by"] = str(user_id)

        # Set move date if not provided
        if "move_date" not in move_dict:
            from datetime import datetime
            move_dict["move_date"] = datetime.now().isoformat()

        return self.move_material_between_locations(move_dict)

    def get_storage_occupancy_report(self, section=None, location_type=None):
        # ... existing code ...

        # Add new fields
        most_utilized_locations = sorted(
            locations,
            key=lambda loc: (loc.utilized or 0) / (loc.capacity or 1) if loc.capacity else 0,
            reverse=True
        )[:5]  # Top 5 most utilized locations

        least_utilized_locations = sorted(
            locations,
            key=lambda loc: (loc.utilized or 0) / (loc.capacity or 1) if loc.capacity else 0
        )[:5]  # Top 5 least utilized locations

        recommendations = []
        if locations_at_capacity > len(locations) * 0.3:
            recommendations.append("Consider expanding storage capacity")

        if locations_nearly_empty > len(locations) * 0.3:
            recommendations.append("Optimize storage allocation")

        return {
            # ... existing fields ...
            "overall_usage_percentage": (
                total_utilized / total_capacity * 100
                if total_capacity > 0 else 0
            ),
            "locations_by_type": types,
            "locations_by_section": sections,
            "most_utilized_locations": [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "utilization_percentage": (loc.utilized or 0) / (loc.capacity or 1) * 100
                } for loc in most_utilized_locations
            ],
            "least_utilized_locations": [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "utilization_percentage": (loc.utilized or 0) / (loc.capacity or 1) * 100
                } for loc in least_utilized_locations
            ],
            "recommendations": recommendations
        }

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
