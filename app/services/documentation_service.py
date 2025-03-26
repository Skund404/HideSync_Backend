# File: app/services/documentation_service.py
"""
Documentation service for the HideSync system.

This module provides service layer implementation for the documentation system,
including business logic for managing documentation resources, categories,
application contexts, and contextual help mappings.
"""

from typing import List, Dict, Any, Optional, Tuple, Union, cast
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from app.db.models.documentation import (
    DocumentationResource,
    DocumentationCategory,
    ApplicationContext,
    ContextualHelpMapping,
    DocumentationType,
    DocumentationStatus,
)
from app.db.models.enums import SkillLevel
from app.repositories.documentation_repository import (
    DocumentationResourceRepository,
    DocumentationCategoryRepository,
    ApplicationContextRepository,
    ContextualHelpMappingRepository,
)
from app.schemas.documentation import (
    DocumentationResourceCreate,
    DocumentationResourceUpdate,
    DocumentationCategoryCreate,
    DocumentationCategoryUpdate,
    ApplicationContextCreate,
    ApplicationContextUpdate,
    ContextualHelpMappingCreate,
    ContextualHelpMappingUpdate,
    DocumentationSearchParams,
)
from app.services.base_service import BaseService


class DocumentationService(BaseService):
    """
    Service for documentation system operations.

    This service provides business logic for managing documentation resources,
    categories, application contexts, and contextual help mappings. It enforces
    business rules and coordinates operations across multiple repositories.
    """

    def __init__(self, db: Session):
        """
        Initialize the DocumentationService.

        Args:
            db: Database session
        """
        super().__init__()
        self.db = db
        self.resource_repository = DocumentationResourceRepository(db)
        self.category_repository = DocumentationCategoryRepository(db)
        self.context_repository = ApplicationContextRepository(db)
        self.mapping_repository = ContextualHelpMappingRepository(db)

    # Resource Methods

    def get_resource(self, resource_id: str) -> Optional[DocumentationResource]:
        """
        Get a documentation resource by ID.

        Args:
            resource_id: Resource ID

        Returns:
            The resource or None if not found
        """
        return self.resource_repository.get_by_id(resource_id)

    def create_resource(
        self, resource_data: DocumentationResourceCreate
    ) -> DocumentationResource:
        """
        Create a new documentation resource.

        Args:
            resource_data: Resource data

        Returns:
            The created resource
        """
        # Convert Pydantic model to dict
        data = resource_data.dict(exclude_unset=True)

        # Set defaults for missing values
        if "author_id" not in data or not data["author_id"]:
            data["author_id"] = "system"  # Default author

        return self.resource_repository.create(data)

    def update_resource(
        self, resource_id: str, resource_data: DocumentationResourceUpdate
    ) -> Optional[DocumentationResource]:
        """
        Update an existing documentation resource.

        Args:
            resource_id: Resource ID
            resource_data: Updated resource data

        Returns:
            The updated resource or None if not found
        """
        # Convert Pydantic model to dict
        data = resource_data.dict(exclude_unset=True, exclude_none=True)

        return self.resource_repository.update(resource_id, data)

    def delete_resource(self, resource_id: str) -> bool:
        """
        Delete a documentation resource.

        Args:
            resource_id: Resource ID

        Returns:
            True if deleted, False if not found
        """
        resource = self.resource_repository.get_by_id(resource_id)
        if not resource:
            return False

        # Delete the resource
        self.resource_repository.delete(resource_id)
        return True

    def search_resources(
        self, search_params: DocumentationSearchParams
    ) -> Tuple[List[DocumentationResource], int]:
        """
        Search for documentation resources with various filters.

        Args:
            search_params: Search parameters

        Returns:
            Tuple of (list of matching resources, total count)
        """
        # Extract parameters from the search params
        params = search_params.dict(exclude_unset=True, exclude_none=True)

        # Default pagination values
        skip = (params.get("page", 1) - 1) * params.get("size", 20)
        limit = params.get("size", 20)

        # Extract specific search parameters
        search = params.get("search")
        category_id = params.get("category_id")
        resource_type = params.get("type")
        skill_level = params.get("skill_level")
        status = params.get("status")
        tags = params.get("tags")
        sort_by = params.get("sort_by", "updated_at")
        sort_order = params.get("sort_order", "desc")

        # Perform the search
        return self.resource_repository.search_resources(
            search=search,
            category_id=category_id,
            resource_type=resource_type,
            skill_level=skill_level,
            status=status,
            tags=tags,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_recent_resources(self, limit: int = 10) -> List[DocumentationResource]:
        """
        Get recently updated documentation resources.

        Args:
            limit: Maximum number of resources to return

        Returns:
            List of recently updated resources
        """
        return self.resource_repository.get_recently_updated_resources(limit=limit)

    # Category Methods

    def get_category(self, category_id: str) -> Optional[DocumentationCategory]:
        """
        Get a documentation category by ID.

        Args:
            category_id: Category ID

        Returns:
            The category or None if not found
        """
        return self.category_repository.get_by_id(category_id)

    def get_category_by_slug(self, slug: str) -> Optional[DocumentationCategory]:
        """
        Get a documentation category by slug.

        Args:
            slug: Category slug

        Returns:
            The category or None if not found
        """
        return self.category_repository.get_by_slug(slug)

    def create_category(
        self, category_data: DocumentationCategoryCreate
    ) -> DocumentationCategory:
        """
        Create a new documentation category.

        Args:
            category_data: Category data

        Returns:
            The created category
        """
        # Convert Pydantic model to dict
        data = category_data.dict(exclude_unset=True)

        # Check if slug is already taken
        existing = self.category_repository.get_by_slug(data["slug"])
        if existing:
            # Append a unique identifier to make the slug unique
            data["slug"] = f"{data['slug']}-{uuid.uuid4().hex[:8]}"

        return self.category_repository.create(data)

    def update_category(
        self, category_id: str, category_data: DocumentationCategoryUpdate
    ) -> Optional[DocumentationCategory]:
        """
        Update an existing documentation category.

        Args:
            category_id: Category ID
            category_data: Updated category data

        Returns:
            The updated category or None if not found
        """
        # Convert Pydantic model to dict
        data = category_data.dict(exclude_unset=True, exclude_none=True)

        # If slug is being updated, check if it's already taken
        if "slug" in data:
            existing = self.category_repository.get_by_slug(data["slug"])
            if existing and existing.id != category_id:
                # Append a unique identifier to make the slug unique
                data["slug"] = f"{data['slug']}-{uuid.uuid4().hex[:8]}"

        return self.category_repository.update(category_id, data)

    def delete_category(self, category_id: str) -> bool:
        """
        Delete a documentation category.

        Args:
            category_id: Category ID

        Returns:
            True if deleted, False if not found
        """
        category = self.category_repository.get_by_id(category_id)
        if not category:
            return False

        # Check if category has subcategories
        if category.subcategories and len(category.subcategories) > 0:
            raise ValueError("Cannot delete category with subcategories")

        # Delete the category
        self.category_repository.delete(category_id)
        return True

    def get_category_hierarchy(self) -> List[DocumentationCategory]:
        """
        Get the complete category hierarchy.

        Returns:
            List of top-level categories with their subcategories loaded
        """
        return self.category_repository.get_category_hierarchy()

    def get_category_with_resources(
        self, category_id: str, page: int = 1, size: int = 20
    ) -> Optional[DocumentationCategory]:
        """
        Get a category with its resources.

        Args:
            category_id: Category ID
            page: Page number
            size: Page size

        Returns:
            The category with resources or None if not found
        """
        skip = (page - 1) * size
        return self.category_repository.get_category_with_resources(
            category_id=category_id, skip=skip, limit=size
        )

    def assign_resource_to_category(
        self, category_id: str, resource_id: str, display_order: int = 0
    ) -> bool:
        """
        Assign a resource to a category.

        Args:
            category_id: Category ID
            resource_id: Resource ID
            display_order: Display order for this resource in the category

        Returns:
            True if successful, False if either entity not found
        """
        return self.category_repository.assign_resource_to_category(
            category_id=category_id,
            resource_id=resource_id,
            display_order=display_order,
        )

    def remove_resource_from_category(self, category_id: str, resource_id: str) -> bool:
        """
        Remove a resource from a category.

        Args:
            category_id: Category ID
            resource_id: Resource ID

        Returns:
            True if successful, False if either entity not found
        """
        return self.category_repository.remove_resource_from_category(
            category_id=category_id, resource_id=resource_id
        )

    # Application Context Methods

    def get_application_context(self, context_id: str) -> Optional[ApplicationContext]:
        """
        Get an application context by ID.

        Args:
            context_id: Context ID

        Returns:
            The context or None if not found
        """
        return self.context_repository.get_by_id(context_id)

    def get_application_context_by_key(
        self, context_key: str
    ) -> Optional[ApplicationContext]:
        """
        Get an application context by key.

        Args:
            context_key: Context key

        Returns:
            The context or None if not found
        """
        return self.context_repository.get_by_context_key(context_key)

    def create_application_context(
        self, context_data: ApplicationContextCreate
    ) -> ApplicationContext:
        """
        Create a new application context.

        Args:
            context_data: Context data

        Returns:
            The created context
        """
        # Convert Pydantic model to dict
        data = context_data.dict(exclude_unset=True)

        # Check if context key is already taken
        existing = self.context_repository.get_by_context_key(data["context_key"])
        if existing:
            raise ValueError(f"Context key '{data['context_key']}' is already in use")

        return self.context_repository.create(data)

    def update_application_context(
        self, context_id: str, context_data: ApplicationContextUpdate
    ) -> Optional[ApplicationContext]:
        """
        Update an existing application context.

        Args:
            context_id: Context ID
            context_data: Updated context data

        Returns:
            The updated context or None if not found
        """
        # Convert Pydantic model to dict
        data = context_data.dict(exclude_unset=True, exclude_none=True)

        # If context_key is being updated, check if it's already taken
        if "context_key" in data:
            existing = self.context_repository.get_by_context_key(data["context_key"])
            if existing and existing.id != context_id:
                raise ValueError(
                    f"Context key '{data['context_key']}' is already in use"
                )

        return self.context_repository.update(context_id, data)

    def delete_application_context(self, context_id: str) -> bool:
        """
        Delete an application context.

        Args:
            context_id: Context ID

        Returns:
            True if deleted, False if not found
        """
        context = self.context_repository.get_by_id(context_id)
        if not context:
            return False

        # Delete the context (mappings will be cascade deleted)
        self.context_repository.delete(context_id)
        return True

    def get_all_application_contexts(
        self, page: int = 1, size: int = 20
    ) -> Tuple[List[ApplicationContext], int]:
        """
        Get all application contexts with pagination.

        Args:
            page: Page number
            size: Page size

        Returns:
            Tuple of (list of contexts, total count)
        """
        skip = (page - 1) * size
        return self.context_repository.get_all_contexts(skip=skip, limit=size)

    # Contextual Help Methods

    def create_contextual_help_mapping(
        self, mapping_data: ContextualHelpMappingCreate
    ) -> ContextualHelpMapping:
        """
        Create a new contextual help mapping.

        Args:
            mapping_data: Mapping data

        Returns:
            The created mapping
        """
        # Convert Pydantic model to dict
        data = mapping_data.dict(exclude_unset=True)

        # Validate that the resource exists
        resource = self.resource_repository.get_by_id(data["resource_id"])
        if not resource:
            raise ValueError(f"Resource with ID '{data['resource_id']}' not found")

        # Validate that the context exists
        context = self.context_repository.get_by_context_key(data["context_key"])
        if not context:
            raise ValueError(
                f"Application context with key '{data['context_key']}' not found"
            )

        return self.mapping_repository.create(data)

    def update_contextual_help_mapping(
        self, mapping_id: str, mapping_data: ContextualHelpMappingUpdate
    ) -> Optional[ContextualHelpMapping]:
        """
        Update an existing contextual help mapping.

        Args:
            mapping_id: Mapping ID
            mapping_data: Updated mapping data

        Returns:
            The updated mapping or None if not found
        """
        # Convert Pydantic model to dict
        data = mapping_data.dict(exclude_unset=True, exclude_none=True)

        return self.mapping_repository.update(mapping_id, data)

    def delete_contextual_help_mapping(self, mapping_id: str) -> bool:
        """
        Delete a contextual help mapping.

        Args:
            mapping_id: Mapping ID

        Returns:
            True if deleted, False if not found
        """
        mapping = self.mapping_repository.get_by_id(mapping_id)
        if not mapping:
            return False

        # Delete the mapping
        self.mapping_repository.delete(mapping_id)
        return True

    def remove_contextual_help_mapping_by_keys(
        self, resource_id: str, context_key: str
    ) -> bool:
        """
        Remove a contextual help mapping by resource ID and context key.

        Args:
            resource_id: Resource ID
            context_key: Context key

        Returns:
            True if deleted, False if not found
        """
        return self.mapping_repository.delete_mapping(resource_id, context_key)

    def get_contextual_help(
        self, context_key: str, limit: int = 5
    ) -> Tuple[List[DocumentationResource], Optional[ApplicationContext]]:
        """
        Get contextual help resources for a specific application context.

        Args:
            context_key: Context key
            limit: Maximum number of resources to return

        Returns:
            Tuple of (list of relevant resources, context)
        """
        # Get the context if it exists
        context = self.context_repository.get_by_context_key(context_key)

        # Get relevant resources
        resources = self.mapping_repository.get_contextual_help_resources(
            context_key=context_key, limit=limit
        )

        return resources, context
