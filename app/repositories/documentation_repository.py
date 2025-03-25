# File: app/repositories/documentation_repository.py
"""
Repository classes for the HideSync documentation system.

This module contains repository implementations for the documentation entities,
including categories, resources, application contexts, and contextual help mappings.
"""

from typing import List, Optional, Dict, Any, Tuple, Union, cast
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy import or_, and_, desc, asc, func, sql, text
from datetime import datetime
import uuid

from app.db.models.documentation import (
    DocumentationResource,
    DocumentationCategory,
    ApplicationContext,
    ContextualHelpMapping,
    DocumentationType,
    DocumentationStatus,
)
from app.db.models.enums import SkillLevel
from app.repositories.base_repository import BaseRepository


class DocumentationResourceRepository(BaseRepository[DocumentationResource]):
    """
    Repository for DocumentationResource entity operations.

    Handles retrieval and management of documentation resources,
    including guides, tutorials, and reference materials.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the DocumentationResourceRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = DocumentationResource

    def create(self, data: Dict[str, Any]) -> DocumentationResource:
        """
        Create a new documentation resource.

        Args:
            data: Dictionary with resource data

        Returns:
            The created resource
        """
        # Extract category_ids from data if present
        category_ids = data.pop("category_ids", None)

        # Generate UUID if not provided
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Set created_at and updated_at if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow()
        if "updated_at" not in data:
            data["updated_at"] = datetime.utcnow()

        # Create resource
        resource = DocumentationResource(**data)
        self.session.add(resource)

        # Associate with categories if provided
        if category_ids:
            categories = (
                self.session.query(DocumentationCategory)
                .filter(DocumentationCategory.id.in_(category_ids))
                .all()
            )
            resource.categories = categories

        self.session.commit()
        self.session.refresh(resource)
        return self._decrypt_sensitive_fields(resource)

    def update(self, id: str, data: Dict[str, Any]) -> Optional[DocumentationResource]:
        """
        Update an existing documentation resource.

        Args:
            id: Resource ID
            data: Dictionary with updated resource data

        Returns:
            The updated resource or None if not found
        """
        resource = self.get_by_id(id)
        if not resource:
            return None

        # Extract category_ids from data if present
        category_ids = data.pop("category_ids", None)

        # Update resource attributes
        for key, value in data.items():
            if hasattr(resource, key):
                setattr(resource, key, value)

        # Update updated_at timestamp
        resource.updated_at = datetime.utcnow()

        # Update category associations if provided
        if category_ids is not None:
            categories = (
                self.session.query(DocumentationCategory)
                .filter(DocumentationCategory.id.in_(category_ids))
                .all()
            )
            resource.categories = categories

        self.session.commit()
        self.session.refresh(resource)
        return self._decrypt_sensitive_fields(resource)

    def get_by_id(self, id: str) -> Optional[DocumentationResource]:
        """
        Get a documentation resource by ID with its categories.

        Args:
            id: Resource ID

        Returns:
            The resource with categories or None if not found
        """
        query = (
            self.session.query(self.model)
            .options(
                selectinload(self.model.categories),
                selectinload(self.model.contextual_help_mappings),
            )
            .filter(self.model.id == id)
        )

        entity = query.first()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_resources_by_category(
        self, category_id: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by category.

        Args:
            category_id: The category ID to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of resources in the specified category
        """
        query = (
            self.session.query(self.model)
            .join(self.model.categories)
            .filter(DocumentationCategory.id == category_id)
            .order_by(desc(self.model.updated_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_type(
        self, resource_type: DocumentationType, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by type.

        Args:
            resource_type: The resource type to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of resources of the specified type
        """
        query = self.session.query(self.model).filter(self.model.type == resource_type)
        query = query.order_by(desc(self.model.updated_at))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_skill_level(
        self, skill_level: SkillLevel, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by skill level.

        Args:
            skill_level: The skill level to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of resources for the specified skill level
        """
        query = self.session.query(self.model).filter(
            self.model.skill_level == skill_level
        )
        query = query.order_by(desc(self.model.updated_at))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_tags(
        self, tags: List[str], skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by tags.

        Args:
            tags: List of tags to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of resources with any of the specified tags
        """
        query = self.session.query(self.model)

        # Filter by any of the provided tags
        # Note: This implementation assumes tags are stored as a JSON array
        for tag in tags:
            query = query.filter(self.model.tags.contains(tag))

        query = query.order_by(desc(self.model.updated_at))
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_author(
        self, author_id: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by author.

        Args:
            author_id: The author ID to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of resources by the specified author
        """
        query = self.session.query(self.model).filter(self.model.author_id == author_id)
        query = query.order_by(desc(self.model.updated_at))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recently_updated_resources(
        self, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get recently updated documentation resources.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of recently updated resources
        """
        query = self.session.query(self.model).order_by(desc(self.model.updated_at))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_all_resources(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> Tuple[List[DocumentationResource], int]:
        """
        Get all resources with pagination and sorting.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            Tuple of (list of resources, total count)
        """
        # Build query
        query = self.session.query(self.model)

        # Get total count
        total = query.count()

        # Apply sorting
        if hasattr(self.model, sort_by):
            sort_column = getattr(self.model, sort_by)
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))
        else:
            # Default sorting
            query = query.order_by(desc(self.model.updated_at))

        # Apply pagination
        entities = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(entity) for entity in entities], total

    def search_resources(
        self,
        search: Optional[str] = None,
        category_id: Optional[str] = None,
        resource_type: Optional[DocumentationType] = None,
        skill_level: Optional[SkillLevel] = None,
        status: Optional[DocumentationStatus] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> Tuple[List[DocumentationResource], int]:
        """
        Search for documentation resources with various filters.

        Args:
            search: Search term for title, description, or content
            category_id: Filter by category ID
            resource_type: Filter by resource type
            skill_level: Filter by skill level
            status: Filter by publication status
            tags: Filter by tags
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            Tuple of (list of matching resources, total count)
        """
        # Start building the query
        query = self.session.query(self.model).distinct()

        # Apply text search if provided
        if search:
            search_filter = or_(
                self.model.title.ilike(f"%{search}%"),
                self.model.description.ilike(f"%{search}%"),
                self.model.content.ilike(f"%{search}%"),
            )
            query = query.filter(search_filter)

        # Apply category filter if provided
        if category_id:
            query = query.join(self.model.categories).filter(
                DocumentationCategory.id == category_id
            )

        # Apply type filter if provided
        if resource_type:
            query = query.filter(self.model.type == resource_type)

        # Apply skill level filter if provided
        if skill_level:
            query = query.filter(self.model.skill_level == skill_level)

        # Apply status filter if provided
        if status:
            query = query.filter(self.model.status == status)

        # Apply tag filters if provided
        if tags:
            for tag in tags:
                query = query.filter(self.model.tags.contains(tag))

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        if hasattr(self.model, sort_by):
            sort_column = getattr(self.model, sort_by)
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))
        else:
            # Default sorting
            query = query.order_by(desc(self.model.updated_at))

        # Apply pagination
        entities = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(entity) for entity in entities], total


class DocumentationCategoryRepository(BaseRepository[DocumentationCategory]):
    """
    Repository for DocumentationCategory entity operations.

    Manages documentation categories, which organize documentation
    resources into logical groups for easier discovery.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the DocumentationCategoryRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = DocumentationCategory

    def create(self, data: Dict[str, Any]) -> DocumentationCategory:
        """
        Create a new documentation category.

        Args:
            data: Dictionary with category data

        Returns:
            The created category
        """
        # Generate UUID if not provided
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Set created_at and updated_at if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow()
        if "updated_at" not in data:
            data["updated_at"] = datetime.utcnow()

        category = DocumentationCategory(**data)
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        return self._decrypt_sensitive_fields(category)

    def update(self, id: str, data: Dict[str, Any]) -> Optional[DocumentationCategory]:
        """
        Update an existing documentation category.

        Args:
            id: Category ID
            data: Dictionary with updated category data

        Returns:
            The updated category or None if not found
        """
        category = self.get_by_id(id)
        if not category:
            return None

        # Update category attributes
        for key, value in data.items():
            if hasattr(category, key):
                setattr(category, key, value)

        # Update updated_at timestamp
        category.updated_at = datetime.utcnow()

        self.session.commit()
        self.session.refresh(category)
        return self._decrypt_sensitive_fields(category)

    def get_by_id(self, id: str) -> Optional[DocumentationCategory]:
        """
        Get a documentation category by ID with its subcategories.

        Args:
            id: Category ID

        Returns:
            The category with subcategories or None if not found
        """
        query = (
            self.session.query(self.model)
            .options(
                selectinload(self.model.subcategories),
                selectinload(self.model.resources),
            )
            .filter(self.model.id == id)
        )

        entity = query.first()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_by_slug(self, slug: str) -> Optional[DocumentationCategory]:
        """
        Get a documentation category by slug.

        Args:
            slug: Category slug

        Returns:
            The category or None if not found
        """
        query = self.session.query(self.model).filter(self.model.slug == slug)

        entity = query.first()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_top_level_categories(self) -> List[DocumentationCategory]:
        """
        Get all top-level categories (those without a parent).

        Returns:
            List of top-level categories
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.parent_category_id == None)
            .order_by(self.model.display_order)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_category_with_resources(
        self, category_id: str, skip: int = 0, limit: int = 100
    ) -> Optional[DocumentationCategory]:
        """
        Get a category with its associated resources.

        Args:
            category_id: ID of the category
            skip: Number of resources to skip
            limit: Maximum number of resources to return

        Returns:
            Category with resources if found, None otherwise
        """
        category = self.get_by_id(category_id)
        if not category:
            return None

        # Get paginated resources for this category
        resource_repo = DocumentationResourceRepository(self.session)
        resources = resource_repo.get_resources_by_category(category_id, skip, limit)

        # Attach resources to category for the response
        category.resources = resources

        return category

    def search_categories(
        self, query_text: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[DocumentationCategory], int]:
        """
        Search for categories by name or description.

        Args:
            query_text: The search query
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of matching categories, total count)
        """
        query = (
            self.session.query(self.model)
            .filter(
                or_(
                    self.model.name.ilike(f"%{query_text}%"),
                    self.model.description.ilike(f"%{query_text}%"),
                )
            )
            .order_by(self.model.display_order)
        )

        # Get total count
        total = query.count()

        # Apply pagination
        entities = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(entity) for entity in entities], total

    def get_category_hierarchy(self) -> List[DocumentationCategory]:
        """
        Get the complete category hierarchy.

        Returns:
            List of top-level categories with their subcategories loaded
        """
        # Get all top-level categories with eager loading of subcategories
        query = (
            self.session.query(self.model)
            .filter(self.model.parent_category_id == None)
            .options(
                selectinload(self.model.subcategories).selectinload(
                    self.model.subcategories
                ),
                selectinload(self.model.resources),
            )
            .order_by(self.model.display_order)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def assign_resource_to_category(
        self, category_id: str, resource_id: str, display_order: int = 0
    ) -> bool:
        """
        Assign a resource to a category.

        Args:
            category_id: ID of the category
            resource_id: ID of the resource
            display_order: Display order for this resource in the category

        Returns:
            True if successful, False if either entity not found
        """
        category = self.get_by_id(category_id)
        if not category:
            return False

        resource_repo = DocumentationResourceRepository(self.session)
        resource = resource_repo.get_by_id(resource_id)
        if not resource:
            return False

        # Add resource to category if not already there
        if resource not in category.resources:
            category.resources.append(resource)

        self.session.commit()
        return True

    def remove_resource_from_category(self, category_id: str, resource_id: str) -> bool:
        """
        Remove a resource from a category.

        Args:
            category_id: ID of the category
            resource_id: ID of the resource

        Returns:
            True if successful, False if either entity not found
        """
        category = self.get_by_id(category_id)
        if not category:
            return False

        resource_repo = DocumentationResourceRepository(self.session)
        resource = resource_repo.get_by_id(resource_id)
        if not resource:
            return False

        # Remove resource from category if present
        if resource in category.resources:
            category.resources.remove(resource)

        self.session.commit()
        return True


class ApplicationContextRepository(BaseRepository[ApplicationContext]):
    """
    Repository for ApplicationContext entity operations.

    Manages application UI contexts that can be linked to documentation resources
    for contextual help.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ApplicationContextRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ApplicationContext

    def create(self, data: Dict[str, Any]) -> ApplicationContext:
        """
        Create a new application context.

        Args:
            data: Dictionary with context data

        Returns:
            The created context
        """
        # Generate UUID if not provided
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Set created_at and updated_at if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow()
        if "updated_at" not in data:
            data["updated_at"] = datetime.utcnow()

        context = ApplicationContext(**data)
        self.session.add(context)
        self.session.commit()
        self.session.refresh(context)
        return self._decrypt_sensitive_fields(context)

    def update(self, id: str, data: Dict[str, Any]) -> Optional[ApplicationContext]:
        """
        Update an existing application context.

        Args:
            id: Context ID
            data: Dictionary with updated context data

        Returns:
            The updated context or None if not found
        """
        context = self.get_by_id(id)
        if not context:
            return None

        # Update context attributes
        for key, value in data.items():
            if hasattr(context, key):
                setattr(context, key, value)

        # Update updated_at timestamp
        context.updated_at = datetime.utcnow()

        self.session.commit()
        self.session.refresh(context)
        return self._decrypt_sensitive_fields(context)

    def get_by_context_key(self, context_key: str) -> Optional[ApplicationContext]:
        """
        Get an application context by its context key.

        Args:
            context_key: The context key

        Returns:
            The context or None if not found
        """
        query = self.session.query(self.model).filter(
            self.model.context_key == context_key
        )

        entity = query.first()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_all_contexts(
        self, skip: int = 0, limit: int = 100
    ) -> Tuple[List[ApplicationContext], int]:
        """
        Get all application contexts with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of contexts, total count)
        """
        query = self.session.query(self.model).order_by(self.model.name)

        # Get total count
        total = query.count()

        # Apply pagination
        entities = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(entity) for entity in entities], total

    def search_contexts(
        self, search: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[ApplicationContext], int]:
        """
        Search for application contexts.

        Args:
            search: Search term
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of matching contexts, total count)
        """
        query = (
            self.session.query(self.model)
            .filter(
                or_(
                    self.model.name.ilike(f"%{search}%"),
                    self.model.description.ilike(f"%{search}%"),
                    self.model.context_key.ilike(f"%{search}%"),
                    self.model.route.ilike(f"%{search}%"),
                )
            )
            .order_by(self.model.name)
        )

        # Get total count
        total = query.count()

        # Apply pagination
        entities = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(entity) for entity in entities], total


class ContextualHelpMappingRepository(BaseRepository[ContextualHelpMapping]):
    """
    Repository for ContextualHelpMapping entity operations.

    Manages mappings between documentation resources and application contexts
    for contextual help functionality.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ContextualHelpMappingRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ContextualHelpMapping

    def create(self, data: Dict[str, Any]) -> ContextualHelpMapping:
        """
        Create a new contextual help mapping.

        Args:
            data: Dictionary with mapping data

        Returns:
            The created mapping
        """
        # Generate UUID if not provided
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Set created_at if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow()

        mapping = ContextualHelpMapping(**data)
        self.session.add(mapping)
        self.session.commit()
        self.session.refresh(mapping)
        return self._decrypt_sensitive_fields(mapping)

    def update(self, id: str, data: Dict[str, Any]) -> Optional[ContextualHelpMapping]:
        """
        Update an existing contextual help mapping.

        Args:
            id: Mapping ID
            data: Dictionary with updated mapping data

        Returns:
            The updated mapping or None if not found
        """
        mapping = self.get_by_id(id)
        if not mapping:
            return None

        # Update mapping attributes
        for key, value in data.items():
            if hasattr(mapping, key):
                setattr(mapping, key, value)

        self.session.commit()
        self.session.refresh(mapping)
        return self._decrypt_sensitive_fields(mapping)

    def get_mappings_by_context_key(
        self, context_key: str
    ) -> List[ContextualHelpMapping]:
        """
        Get all mappings for a specific context key.

        Args:
            context_key: The context key

        Returns:
            List of mappings for this context
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.context_key == context_key, self.model.is_active == True)
            .order_by(desc(self.model.relevance_score))
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_mappings_by_resource_id(
        self, resource_id: str
    ) -> List[ContextualHelpMapping]:
        """
        Get all mappings for a specific resource.

        Args:
            resource_id: The resource ID

        Returns:
            List of mappings for this resource
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.resource_id == resource_id)
            .order_by(desc(self.model.relevance_score))
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_contextual_help_resources(
        self, context_key: str, limit: int = 5
    ) -> List[DocumentationResource]:
        """
        Get documentation resources relevant to a specific context.

        Args:
            context_key: The context key
            limit: Maximum number of resources to return

        Returns:
            List of relevant documentation resources
        """
        query = (
            self.session.query(DocumentationResource)
            .join(ContextualHelpMapping)
            .filter(
                ContextualHelpMapping.context_key == context_key,
                ContextualHelpMapping.is_active == True,
                DocumentationResource.is_public == True,
                DocumentationResource.status == DocumentationStatus.PUBLISHED,
            )
            .order_by(desc(ContextualHelpMapping.relevance_score))
            .limit(limit)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def delete_mapping(self, resource_id: str, context_key: str) -> bool:
        """
        Delete a contextual help mapping.

        Args:
            resource_id: The resource ID
            context_key: The context key

        Returns:
            True if deleted, False if not found
        """
        mapping = (
            self.session.query(self.model)
            .filter(
                self.model.resource_id == resource_id,
                self.model.context_key == context_key,
            )
            .first()
        )

        if not mapping:
            return False

        self.session.delete(mapping)
        self.session.commit()
        return True
