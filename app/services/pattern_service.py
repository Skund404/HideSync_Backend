# File: services/pattern_service.py

"""
Pattern management service for the HideSync system.

This module provides comprehensive functionality for managing leatherworking patterns,
including creation, versioning, component association, and categorization. It serves
as the business logic layer for pattern-related operations, enabling craftspeople to
organize, share, and utilize their design patterns effectively.

Key features:
- Pattern creation and management with versioning
- File handling for SVG/PDF pattern files and thumbnails
- Component association and management
- Categorization by skill level, project type, and tags
- Pattern searching and filtering
- Public/private visibility control
- Pattern cloning and customization

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with other
services like ComponentService for component management.
"""

from typing import List, Optional, Dict, Any, Union, BinaryIO
from datetime import datetime
import logging
import json
import uuid
import os
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    ConcurrentOperationException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import ProjectType, SkillLevel, PatternFileType

# Import Pattern model from its file
from app.db.models.pattern import Pattern

# Import ProjectTemplate models from the project model file
from app.db.models.project import ProjectTemplate, ProjectTemplateComponent
from app.repositories.pattern_repository import (
    PatternRepository,
    ProjectTemplateRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class PatternCreated(DomainEvent):
    """Event emitted when a pattern is created."""

    def __init__(
        self,
        pattern_id: int,
        name: str,
        project_type: str,
        author_id: Optional[int] = None,
    ):
        """
        Initialize pattern created event.

        Args:
            pattern_id: ID of the created pattern
            name: Name of the pattern
            project_type: Type of project the pattern is for
            author_id: Optional ID of the user who created the pattern
        """
        super().__init__()
        self.pattern_id = pattern_id
        self.name = name
        self.project_type = project_type
        self.author_id = author_id


class PatternUpdated(DomainEvent):
    """Event emitted when a pattern is updated."""

    def __init__(
        self, pattern_id: int, name: str, version: str, user_id: Optional[int] = None
    ):
        """
        Initialize pattern updated event.

        Args:
            pattern_id: ID of the updated pattern
            name: Name of the pattern
            version: New version of the pattern
            user_id: Optional ID of the user who updated the pattern
        """
        super().__init__()
        self.pattern_id = pattern_id
        self.name = name
        self.version = version
        self.user_id = user_id


class PatternDeleted(DomainEvent):
    """Event emitted when a pattern is deleted."""

    def __init__(self, pattern_id: int, name: str, user_id: Optional[int] = None):
        """
        Initialize pattern deleted event.

        Args:
            pattern_id: ID of the deleted pattern
            name: Name of the pattern
            user_id: Optional ID of the user who deleted the pattern
        """
        super().__init__()
        self.pattern_id = pattern_id
        self.name = name
        self.user_id = user_id


class PatternComponentAdded(DomainEvent):
    """Event emitted when a component is added to a pattern."""

    def __init__(
        self,
        pattern_id: int,
        component_id: int,
        component_name: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize component added event.

        Args:
            pattern_id: ID of the pattern
            component_id: ID of the added component
            component_name: Name of the component
            user_id: Optional ID of the user who added the component
        """
        super().__init__()
        self.pattern_id = pattern_id
        self.component_id = component_id
        self.component_name = component_name
        self.user_id = user_id


class TemplateCreated(DomainEvent):
    """Event emitted when a project template is created."""

    def __init__(
        self,
        template_id: str,
        name: str,
        project_type: str,
        pattern_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize template created event.

        Args:
            template_id: ID of the created template
            name: Name of the template
            project_type: Type of project the template is for
            pattern_id: Optional ID of the pattern used for the template
            user_id: Optional ID of the user who created the template
        """
        super().__init__()
        self.template_id = template_id
        self.name = name
        self.project_type = project_type
        self.pattern_id = pattern_id
        self.user_id = user_id


# Validation functions
validate_pattern = validate_entity(Pattern)
validate_project_template = validate_entity(ProjectTemplate)
validate_template_component = validate_entity(ProjectTemplateComponent)


class PatternService(BaseService[Pattern]):
    """
    Service for managing patterns in the HideSync system.

    Provides functionality for:
    - Pattern creation and management with versioning
    - File handling for SVG/PDF pattern files and thumbnails
    - Component association and management
    - Categorization by skill level, project type, and tags
    - Pattern searching and filtering
    - Public/private visibility control
    - Pattern cloning and customization
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        template_repository=None,
        component_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        file_storage_service=None,
        component_service=None,
    ):
        """
        Initialize PatternService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for patterns
            template_repository: Optional repository for project templates
            component_repository: Optional repository for components
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            file_storage_service: Optional service for file storage
            component_service: Optional service for component management
        """
        self.session = session
        self.repository = repository or PatternRepository(session)
        self.template_repository = template_repository or ProjectTemplateRepository(
            session
        )
        self.component_repository = component_repository
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.file_storage_service = file_storage_service
        self.component_service = component_service

    @validate_input(validate_pattern)
    def create_pattern(
        self, data: Dict[str, Any], file_data: Optional[bytes] = None
    ) -> Pattern:
        """
        Create a new pattern.

        Args:
            data: Pattern data with required fields
                Required fields:
                - name: Pattern name
                - projectType: Type of project (WALLET, BAG, BELT, etc.)
                - skillLevel: Required skill level
                - fileType: Type of pattern file (SVG, PDF, IMAGE)
                Optional fields:
                - description: Pattern description
                - tags: List of tags for searching
                - authorName: Name of pattern creator
                - isPublic: Whether pattern is publicly accessible
            file_data: Optional binary data for the pattern file

        Returns:
            Created pattern entity

        Raises:
            ValidationException: If validation fails
        """
        with self.transaction():
            # Set default values if not provided
            if "version" not in data:
                data["version"] = "1.0.0"

            if "isPublic" not in data:
                data["isPublic"] = False

            if "isFavorite" not in data:
                data["isFavorite"] = False

            if "createdAt" not in data:
                data["createdAt"] = datetime.now()

            if "modifiedAt" not in data:
                data["modifiedAt"] = datetime.now()

            # Handle author name from security context if available
            if "authorName" not in data and self.security_context:
                user = self.security_context.current_user
                if user and hasattr(user, "name"):
                    data["authorName"] = user.name

            # Convert tags array to string if needed
            if "tags" in data and isinstance(data["tags"], list):
                data["tags"] = json.dumps(data["tags"])

            # Store pattern file if provided
            if file_data and self.file_storage_service:
                file_type = data.get("fileType", "PDF")
                extension = self._get_file_extension(file_type)

                file_metadata = self.file_storage_service.store_file(
                    file_data=file_data,
                    filename=f"{data['name']}{extension}",
                    content_type=self._get_mime_type(file_type),
                    metadata={
                        "pattern_name": data["name"],
                        "pattern_type": data.get("projectType"),
                        "version": data["version"],
                    },
                )

                # Update data with file path
                data["filePath"] = file_metadata.get("storage_path")

            # Create pattern
            pattern = self.repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PatternCreated(
                        pattern_id=pattern.id,
                        name=pattern.name,
                        project_type=pattern.projectType,
                        author_id=user_id,
                    )
                )

            return pattern

    def update_pattern(
        self,
        pattern_id: int,
        data: Dict[str, Any],
        file_data: Optional[bytes] = None,
        increment_version: bool = False,
    ) -> Pattern:
        """
        Update an existing pattern.

        Args:
            pattern_id: ID of the pattern to update
            data: Updated pattern data
            file_data: Optional binary data for updated pattern file
            increment_version: Whether to increment the pattern version

        Returns:
            Updated pattern entity

        Raises:
            EntityNotFoundException: If pattern not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Update version if requested
            if increment_version and "version" in pattern.__dict__:
                current_version = pattern.version
                data["version"] = self._increment_version(current_version)

            # Always update modification time
            data["modifiedAt"] = datetime.now()

            # Convert tags array to string if needed
            if "tags" in data and isinstance(data["tags"], list):
                data["tags"] = json.dumps(data["tags"])

            # Store pattern file if provided
            if file_data and self.file_storage_service:
                file_type = data.get("fileType", pattern.fileType)
                extension = self._get_file_extension(file_type)

                file_metadata = self.file_storage_service.store_file(
                    file_data=file_data,
                    filename=f"{data.get('name', pattern.name)}{extension}",
                    content_type=self._get_mime_type(file_type),
                    metadata={
                        "pattern_name": data.get("name", pattern.name),
                        "pattern_type": data.get("projectType", pattern.projectType),
                        "version": data.get("version", pattern.version),
                    },
                )

                # Update data with file path
                data["filePath"] = file_metadata.get("storage_path")

            # Update pattern
            updated_pattern = self.repository.update(pattern_id, data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PatternUpdated(
                        pattern_id=pattern_id,
                        name=updated_pattern.name,
                        version=updated_pattern.version,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Pattern:{pattern_id}")
                self.cache_service.invalidate(f"Pattern:detail:{pattern_id}")

            return updated_pattern

    def clone_pattern(
        self,
        pattern_id: int,
        new_name: str,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> Pattern:
        """
        Clone an existing pattern to create a new one.

        Args:
            pattern_id: ID of the pattern to clone
            new_name: Name for the new pattern
            custom_data: Optional custom data to override in the new pattern

        Returns:
            Newly created pattern entity

        Raises:
            EntityNotFoundException: If source pattern not found
        """
        with self.transaction():
            # Check if source pattern exists
            source_pattern = self.get_pattern_with_details(pattern_id)
            if not source_pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Create new pattern data from source pattern
            new_pattern_data = {
                "name": new_name,
                "description": source_pattern.get("description", ""),
                "skillLevel": source_pattern.get("skillLevel"),
                "fileType": source_pattern.get("fileType"),
                "projectType": source_pattern.get("projectType"),
                "estimatedTime": source_pattern.get("estimatedTime"),
                "estimatedDifficulty": source_pattern.get("estimatedDifficulty"),
                "tags": source_pattern.get("tags"),
                "isPublic": False,  # Default to private for cloned patterns
                "isFavorite": False,
                "version": "1.0.0",  # Reset version for new pattern
                "authorName": (
                    self.security_context.current_user.name
                    if self.security_context
                    and hasattr(self.security_context.current_user, "name")
                    else "Unknown"
                ),
            }

            # Override with custom data if provided
            if custom_data:
                new_pattern_data.update(custom_data)

            # Create new pattern
            new_pattern = self.create_pattern(new_pattern_data)

            # Clone file if source pattern has a file and file storage service is available
            if (
                "filePath" in source_pattern
                and source_pattern["filePath"]
                and self.file_storage_service
            ):
                try:
                    # Get source file data
                    source_file_data, _ = self.file_storage_service.retrieve_file(
                        source_pattern["filePath"]
                    )

                    # Store file for new pattern
                    self.update_pattern(new_pattern.id, {}, file_data=source_file_data)
                except Exception as e:
                    logger.warning(f"Failed to clone pattern file: {str(e)}")

            # If component service is available, clone components
            if self.component_service and "components" in source_pattern:
                for component in source_pattern["components"]:
                    # Clone component with new pattern ID
                    cloned_component = self.component_service.clone_component(
                        component.get("id"), {"patternId": new_pattern.id}
                    )

                    # Publish component added event
                    if self.event_bus:
                        user_id = (
                            self.security_context.current_user.id
                            if self.security_context
                            else None
                        )
                        self.event_bus.publish(
                            PatternComponentAdded(
                                pattern_id=new_pattern.id,
                                component_id=cloned_component.id,
                                component_name=cloned_component.name,
                                user_id=user_id,
                            )
                        )

            return new_pattern

    def delete_pattern(self, pattern_id: int) -> bool:
        """
        Delete a pattern.

        Args:
            pattern_id: ID of the pattern to delete

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If pattern not found
            BusinessRuleException: If pattern is in use by projects or products
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Check if pattern is in use by projects or products
            if self._is_pattern_in_use(pattern_id):
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Cannot delete pattern that is in use by projects or products",
                    "PATTERN_001",
                )

            # Store pattern name for event
            pattern_name = pattern.name

            # Delete pattern file if file storage service is available
            if (
                hasattr(pattern, "filePath")
                and pattern.filePath
                and self.file_storage_service
            ):
                try:
                    self.file_storage_service.delete_file(pattern.filePath)
                except Exception as e:
                    logger.warning(f"Failed to delete pattern file: {str(e)}")

            # Delete pattern
            result = self.repository.delete(pattern_id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PatternDeleted(
                        pattern_id=pattern_id, name=pattern_name, user_id=user_id
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Pattern:{pattern_id}")
                self.cache_service.invalidate(f"Pattern:detail:{pattern_id}")

            return result

    def get_pattern_with_details(self, pattern_id: int) -> Dict[str, Any]:
        """
        Get a pattern with comprehensive details including components.

        Args:
            pattern_id: ID of the pattern

        Returns:
            Pattern with component details

        Raises:
            EntityNotFoundException: If pattern not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Pattern:detail:{pattern_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get pattern
        pattern = self.get_by_id(pattern_id)
        if not pattern:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("Pattern", pattern_id)

        # Convert to dict
        result = pattern.to_dict()

        # Parse tags if they're stored as JSON
        if "tags" in result and result["tags"]:
            try:
                result["tags"] = json.loads(result["tags"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, leave as is or convert to list if string
                if isinstance(result["tags"], str) and "," in result["tags"]:
                    result["tags"] = [tag.strip() for tag in result["tags"].split(",")]
                elif isinstance(result["tags"], str):
                    result["tags"] = [result["tags"]]

        # Get pattern file URL if file_storage_service is available
        if "filePath" in result and result["filePath"] and self.file_storage_service:
            if hasattr(self.file_storage_service, "get_file_url"):
                result["fileUrl"] = self.file_storage_service.get_file_url(
                    result["filePath"]
                )

        # Get thumbnail URL if available
        if "thumbnail" in result and result["thumbnail"] and self.file_storage_service:
            if hasattr(self.file_storage_service, "get_file_url"):
                result["thumbnailUrl"] = self.file_storage_service.get_file_url(
                    result["thumbnail"]
                )

        # Get components if component_repository is available
        if self.component_repository:
            components = self.component_repository.list(patternId=pattern_id)
            result["components"] = [component.to_dict() for component in components]

        # Get project templates that use this pattern
        if self.template_repository:
            templates = self.template_repository.find_by_pattern_id(pattern_id)
            result["templates"] = [template.to_dict() for template in templates]

        # Get usage statistics
        result["usage_stats"] = self._get_pattern_usage_stats(pattern_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def upload_pattern_file(
        self,
        pattern_id: int,
        file_data: bytes,
        file_name: str,
        content_type: Optional[str] = None,
    ) -> Pattern:
        """
        Upload or replace a pattern file.

        Args:
            pattern_id: ID of the pattern
            file_data: Binary file content
            file_name: Original filename
            content_type: Optional content type

        Returns:
            Updated pattern entity

        Raises:
            EntityNotFoundException: If pattern not found
            ValidationException: If file type is invalid
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Validate file type
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext not in [".svg", ".pdf", ".png", ".jpg", ".jpeg"]:
                raise ValidationException(
                    "Invalid pattern file type",
                    {"file": ["File must be SVG, PDF, or image format"]},
                )

            # Determine file type from extension
            file_type = None
            if file_ext == ".svg":
                file_type = "SVG"
            elif file_ext == ".pdf":
                file_type = "PDF"
            else:
                file_type = "IMAGE"

            # Store file
            if self.file_storage_service:
                file_metadata = self.file_storage_service.store_file(
                    file_data=file_data,
                    filename=file_name,
                    content_type=content_type,
                    metadata={
                        "pattern_id": pattern_id,
                        "pattern_name": pattern.name,
                        "pattern_type": (
                            pattern.projectType
                            if hasattr(pattern, "projectType")
                            else None
                        ),
                        "version": (
                            pattern.version if hasattr(pattern, "version") else None
                        ),
                    },
                )

                # Update pattern with file path and type
                return self.update_pattern(
                    pattern_id,
                    {
                        "filePath": file_metadata.get("storage_path"),
                        "fileType": file_type,
                    },
                    increment_version=True,
                )
            else:
                logger.warning(
                    "File storage service not available for pattern file upload"
                )

                # Just update the file type
                return self.update_pattern(
                    pattern_id, {"fileType": file_type}, increment_version=True
                )

    def upload_pattern_thumbnail(
        self,
        pattern_id: int,
        image_data: bytes,
        file_name: str,
        content_type: Optional[str] = None,
    ) -> Pattern:
        """
        Upload or replace a pattern thumbnail image.

        Args:
            pattern_id: ID of the pattern
            image_data: Binary image content
            file_name: Original filename
            content_type: Optional content type

        Returns:
            Updated pattern entity

        Raises:
            EntityNotFoundException: If pattern not found
            ValidationException: If image type is invalid
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Validate image type
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                raise ValidationException(
                    "Invalid thumbnail image type",
                    {"thumbnail": ["Image must be PNG, JPEG, GIF or WebP format"]},
                )

            # Store thumbnail
            if self.file_storage_service:
                thumb_filename = f"thumb_{pattern_id}_{file_name}"

                thumbnail_metadata = self.file_storage_service.store_file(
                    file_data=image_data,
                    filename=thumb_filename,
                    content_type=content_type,
                    metadata={
                        "pattern_id": pattern_id,
                        "pattern_name": pattern.name,
                        "type": "thumbnail",
                    },
                )

                # Update pattern with thumbnail path
                return self.update_pattern(
                    pattern_id,
                    {"thumbnail": thumbnail_metadata.get("storage_path")},
                    increment_version=False,
                )
            else:
                logger.warning(
                    "File storage service not available for pattern thumbnail upload"
                )
                return pattern

    def get_patterns_by_project_type(
        self, project_type: Union[ProjectType, str]
    ) -> List[Pattern]:
        """
        Get patterns by project type.

        Args:
            project_type: Type of project

        Returns:
            List of patterns for the specified project type
        """
        # Convert string to enum if needed
        if isinstance(project_type, str):
            try:
                project_type = ProjectType[project_type.upper()]
                project_type = project_type.value
            except (KeyError, AttributeError):
                pass

        return self.repository.list(projectType=project_type)

    def get_patterns_by_skill_level(
        self, skill_level: Union[SkillLevel, str], max_level: bool = False
    ) -> List[Pattern]:
        """
        Get patterns by skill level.

        Args:
            skill_level: Skill level to filter by
            max_level: If True, return patterns up to and including the specified level

        Returns:
            List of patterns for the specified skill level
        """
        # Convert string to enum if needed
        if isinstance(skill_level, str):
            try:
                skill_level = SkillLevel[skill_level.upper()]
                skill_level = skill_level.value
            except (KeyError, AttributeError):
                pass

        if max_level:
            # This would need to be implemented in the repository
            # For now, we'll just get all patterns and filter
            all_patterns = self.repository.list()

            # Create a mapping of skill levels to numerical values
            skill_order = {
                "ABSOLUTE_BEGINNER": 0,
                "NOVICE": 1,
                "BEGINNER": 2,
                "INTERMEDIATE": 3,
                "ADVANCED": 4,
                "EXPERT": 5,
                "MASTER": 6,
            }

            # Get numerical value for target skill level
            target_value = skill_order.get(skill_level, 999)

            # Filter patterns
            return [
                p
                for p in all_patterns
                if skill_order.get(p.skillLevel, 0) <= target_value
            ]
        else:
            return self.repository.list(skillLevel=skill_level)

    def search_patterns(
        self,
        query: str,
        project_type: Optional[str] = None,
        skill_level: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
        is_public: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Search for patterns based on various criteria.

        Args:
            query: Search query for pattern name and description
            project_type: Optional project type filter
            skill_level: Optional skill level filter
            tags: Optional tags filter
            author: Optional author filter
            is_public: Optional filter for public/private patterns
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            Dictionary with search results and total count
        """
        filters = {}

        if project_type:
            filters["projectType"] = project_type

        if skill_level:
            filters["skillLevel"] = skill_level

        if author:
            filters["authorName"] = author

        if is_public is not None:
            filters["isPublic"] = is_public

        # Repository would implement search functionality
        # This is a simplified example
        if hasattr(self.repository, "search"):
            results, total = self.repository.search(
                query=query, tags=tags, limit=limit, offset=offset, **filters
            )
        else:
            # Fallback to basic filter
            results = self.repository.list(limit=limit, offset=offset, **filters)
            total = len(results)

        return {
            "items": [p.to_dict() for p in results],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def toggle_favorite(self, pattern_id: int, is_favorite: bool) -> Pattern:
        """
        Toggle favorite status for a pattern.

        Args:
            pattern_id: ID of the pattern
            is_favorite: New favorite status

        Returns:
            Updated pattern entity

        Raises:
            EntityNotFoundException: If pattern not found
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Update favorite status
            return self.update_pattern(
                pattern_id, {"isFavorite": is_favorite}, increment_version=False
            )

    def toggle_public(self, pattern_id: int, is_public: bool) -> Pattern:
        """
        Toggle public status for a pattern.

        Args:
            pattern_id: ID of the pattern
            is_public: New public status

        Returns:
            Updated pattern entity

        Raises:
            EntityNotFoundException: If pattern not found
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

            # Update public status
            return self.update_pattern(
                pattern_id, {"isPublic": is_public}, increment_version=False
            )

    @validate_input(validate_project_template)
    def create_project_template(self, data: Dict[str, Any]) -> ProjectTemplate:
        """
        Create a new project template from a pattern.

        Args:
            data: Template data with required fields
                Required fields:
                - name: Template name
                - projectType: Type of project
                - skillLevel: Required skill level
                Optional fields:
                - patternId: ID of the pattern to use
                - description: Template description
                - estimatedDuration: Estimated time in hours
                - estimatedCost: Estimated cost
                - isPublic: Whether template is publicly accessible
                - tags: List of tags for searching
                - components: List of component specifications

        Returns:
            Created project template entity

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If referenced pattern not found
        """
        with self.transaction():
            # Generate ID if not provided
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # Set default values if not provided
            if "version" not in data:
                data["version"] = "1.0.0"

            if "isPublic" not in data:
                data["isPublic"] = False

            if "createdAt" not in data:
                data["createdAt"] = datetime.now()

            if "updatedAt" not in data:
                data["updatedAt"] = datetime.now()

            # Check if pattern exists if pattern ID is provided
            pattern_id = data.get("patternId")
            if pattern_id:
                pattern = self.get_by_id(pattern_id)
                if not pattern:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Pattern", pattern_id)

            # Convert tags array to string if needed
            if "tags" in data and isinstance(data["tags"], list):
                data["tags"] = json.dumps(data["tags"])

            # Extract components for later creation
            components = data.pop("components", [])

            # Create template
            template = self.template_repository.create(data)

            # Add components if provided
            for component_data in components:
                component_data["templateId"] = template.id
                if "id" not in component_data:
                    component_data["id"] = str(uuid.uuid4())

                self.template_repository.add_component(component_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    TemplateCreated(
                        template_id=template.id,
                        name=template.name,
                        project_type=template.projectType,
                        pattern_id=pattern_id,
                        user_id=user_id,
                    )
                )

            return template

    def update_project_template(
        self, template_id: str, data: Dict[str, Any]
    ) -> ProjectTemplate:
        """
        Update an existing project template.

        Args:
            template_id: ID of the template to update
            data: Updated template data

        Returns:
            Updated project template entity

        Raises:
            EntityNotFoundException: If template not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if template exists
            template = self.template_repository.get_by_id(template_id)
            if not template:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("ProjectTemplate", template_id)

            # Always update modification time
            data["updatedAt"] = datetime.now()

            # Convert tags array to string if needed
            if "tags" in data and isinstance(data["tags"], list):
                data["tags"] = json.dumps(data["tags"])

            # Update template
            updated_template = self.template_repository.update(template_id, data)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"ProjectTemplate:{template_id}")
                self.cache_service.invalidate(f"ProjectTemplate:detail:{template_id}")

            return updated_template

    def get_template_with_details(self, template_id: str) -> Dict[str, Any]:
        """
        Get a project template with comprehensive details.

        Args:
            template_id: ID of the template

        Returns:
            Template with component details

        Raises:
            EntityNotFoundException: If template not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"ProjectTemplate:detail:{template_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get template
        template = self.template_repository.get_by_id(template_id)
        if not template:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("ProjectTemplate", template_id)

        # Convert to dict
        result = template.to_dict()

        # Parse tags if they're stored as JSON
        if "tags" in result and result["tags"]:
            try:
                result["tags"] = json.loads(result["tags"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, leave as is or convert to list if string
                if isinstance(result["tags"], str) and "," in result["tags"]:
                    result["tags"] = [tag.strip() for tag in result["tags"].split(",")]
                elif isinstance(result["tags"], str):
                    result["tags"] = [result["tags"]]

        # Get associated pattern if available
        if "patternId" in result and result["patternId"]:
            try:
                pattern = self.get_by_id(result["patternId"])
                if pattern:
                    result["pattern"] = {
                        "id": pattern.id,
                        "name": pattern.name,
                        "description": (
                            pattern.description
                            if hasattr(pattern, "description")
                            else None
                        ),
                        "skillLevel": (
                            pattern.skillLevel
                            if hasattr(pattern, "skillLevel")
                            else None
                        ),
                        "fileType": (
                            pattern.fileType if hasattr(pattern, "fileType") else None
                        ),
                        "thumbnail": (
                            pattern.thumbnail if hasattr(pattern, "thumbnail") else None
                        ),
                    }
            except Exception as e:
                logger.warning(f"Failed to get pattern for template: {str(e)}")

        # Get components
        components = self.template_repository.get_template_components(template_id)
        result["components"] = [component.to_dict() for component in components]

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def find_templates_by_pattern(self, pattern_id: int) -> List[ProjectTemplate]:
        """
        Find project templates that use a specific pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            List of project templates using the pattern
        """
        if hasattr(self.template_repository, "find_by_pattern_id"):
            return self.template_repository.find_by_pattern_id(pattern_id)
        else:
            # Fallback to generic filter
            return self.template_repository.list(patternId=pattern_id)

    def _increment_version(self, current_version: str) -> str:
        """
        Increment a version string (semver format).

        Args:
            current_version: Current version string (e.g., "1.0.0")

        Returns:
            Incremented version string
        """
        try:
            # Split version into components
            major, minor, patch = current_version.split(".")

            # Increment patch version
            patch = str(int(patch) + 1)

            return f"{major}.{minor}.{patch}"
        except Exception:
            # If version format is invalid, return a default
            return "1.0.1"

    def _get_file_extension(self, file_type: str) -> str:
        """
        Get file extension for a pattern file type.

        Args:
            file_type: Pattern file type

        Returns:
            File extension including the dot
        """
        file_type = file_type.upper() if isinstance(file_type, str) else file_type

        if file_type == "SVG":
            return ".svg"
        elif file_type == "PDF":
            return ".pdf"
        else:  # IMAGE
            return ".png"

    def _get_mime_type(self, file_type: str) -> str:
        """
        Get MIME type for a pattern file type.

        Args:
            file_type: Pattern file type

        Returns:
            MIME type string
        """
        file_type = file_type.upper() if isinstance(file_type, str) else file_type

        if file_type == "SVG":
            return "image/svg+xml"
        elif file_type == "PDF":
            return "application/pdf"
        else:  # IMAGE
            return "image/png"

    def _is_pattern_in_use(self, pattern_id: int) -> bool:
        """
        Check if a pattern is in use by projects or products.

        Args:
            pattern_id: ID of the pattern

        Returns:
            True if pattern is in use
        """
        # Check if pattern is used by any templates
        templates = self.find_templates_by_pattern(pattern_id)
        if templates:
            return True

        # In a real implementation, we would also check projects and products
        # This would require access to those repositories

        return False

    def _get_pattern_usage_stats(self, pattern_id: int) -> Dict[str, Any]:
        """
        Get usage statistics for a pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            Dictionary with usage statistics
        """
        # This would integrate with other services to get usage stats
        # For now, return placeholder data
        return {
            "project_count": 0,
            "template_count": len(self.find_templates_by_pattern(pattern_id)),
            "product_count": 0,
            "download_count": 0,
            "favorite_count": 0,
            "last_used": None,
        }
