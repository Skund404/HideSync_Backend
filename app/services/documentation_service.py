# File: app/services/documentation_service.py
"""
Documentation service implementation for HideSync.

This service handles all operations related to documentation resources and categories,
including CRUD operations and specialized queries for the knowledge base system.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
import uuid
from sqlalchemy.orm import Session

from app.db.models.documentation import DocumentationResource as DocumentationResourceModel
from app.db.models.documentation import DocumentationCategory as DocumentationCategoryModel
from app.schemas.documentation import (
    DocumentationCategory,
    DocumentationCategoryCreate,
    DocumentationCategoryList,
    DocumentationCategoryUpdate,
    DocumentationCategoryWithResources,
    DocumentationResource,
    DocumentationResourceCreate,
    DocumentationResourceList,
    DocumentationResourceResponse,
    DocumentationResourceUpdate,
    DocumentationSearchParams,
)


class DocumentationService:
    """
    Service for managing documentation resources and categories.

    This service provides business logic for all documentation-related operations,
    including creating, retrieving, updating, and deleting documentation resources
    and categories, as well as specialized search functionality.
    """

    def __init__(self, db: Session):
        """
        Initialize the documentation service with a database session.

        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db

    # Resource Methods
    def list_resources(
            self,
            skip: int = 0,
            limit: int = 100,
            search_params: Optional[DocumentationSearchParams] = None
    ) -> DocumentationResourceList:
        """
        List documentation resources with optional filtering.

        Args:
            skip (int): Number of resources to skip for pagination
            limit (int): Maximum number of resources to return
            search_params (DocumentationSearchParams): Search parameters for filtering

        Returns:
            DocumentationResourceList: Paginated list of documentation resources
        """
        query = self.db.query(DocumentationResourceModel)

        total = query.count()

        # Apply search filters if provided
        if search_params:
            if search_params.category:
                query = query.filter(DocumentationResourceModel.category == search_params.category)

            if search_params.type:
                query = query.filter(DocumentationResourceModel.type == search_params.type)

            if search_params.skill_level:
                query = query.filter(DocumentationResourceModel.skill_level == search_params.skill_level)

            if search_params.search:
                search_term = f"%{search_params.search}%"
                query = query.filter(
                    DocumentationResourceModel.title.ilike(search_term) |
                    DocumentationResourceModel.description.ilike(search_term) |
                    DocumentationResourceModel.content.ilike(search_term)
                )

            if search_params.tags and len(search_params.tags) > 0:
                for tag in search_params.tags:
                    query = query.filter(DocumentationResourceModel.tags.contains([tag]))

        # Calculate pagination values
        pages = (total + limit - 1) // limit if limit > 0 else 1
        page = (skip // limit) + 1 if limit > 0 else 1

        # Get paginated results
        resources = query.offset(skip).limit(limit).all()

        # Convert to response models with additional fields
        resource_responses = []
        for resource in resources:
            response = DocumentationResourceResponse.model_validate(resource)

            # Get category name if available
            if resource.category:
                category = self.db.query(DocumentationCategoryModel).filter(
                    DocumentationCategoryModel.id == resource.category
                ).first()
                if category:
                    response.category_name = category.name

            # Get related resource titles
            if resource.related_resources:
                related_titles = []
                related_resources = self.db.query(DocumentationResourceModel).filter(
                    DocumentationResourceModel.id.in_(resource.related_resources)
                ).all()

                for related in related_resources:
                    related_titles.append(related.title)

                response.related_titles = related_titles

            resource_responses.append(response)

        return DocumentationResourceList(
            items=resource_responses,
            total=total,
            page=page,
            size=limit,
            pages=pages
        )

    def create_resource(self, resource: DocumentationResourceCreate) -> DocumentationResource:
        """
        Create a new documentation resource.

        Args:
            resource (DocumentationResourceCreate): Resource data to create

        Returns:
            DocumentationResource: Created resource
        """
        resource_id = str(uuid.uuid4())
        resource_dict = resource.model_dump()

        # Add metadata
        resource_dict["id"] = resource_id
        resource_dict["last_updated"] = datetime.now().isoformat()

        # Create DB model
        db_resource = DocumentationResourceModel(**resource_dict)

        # Add to database
        self.db.add(db_resource)
        self.db.commit()
        self.db.refresh(db_resource)

        # Return with additional fields
        result = DocumentationResource.model_validate(db_resource)

        # Get category name if available
        if db_resource.category:
            category = self.db.query(DocumentationCategoryModel).filter(
                DocumentationCategoryModel.id == db_resource.category
            ).first()
            if category:
                result.category_name = category.name

        return result

    def get_resource(self, resource_id: str) -> Optional[DocumentationResource]:
        """
        Get a documentation resource by ID.

        Args:
            resource_id (str): ID of the resource to retrieve

        Returns:
            Optional[DocumentationResource]: Resource if found, None otherwise
        """
        resource = self.db.query(DocumentationResourceModel).filter(
            DocumentationResourceModel.id == resource_id
        ).first()

        if not resource:
            return None

        result = DocumentationResource.model_validate(resource)

        # Get category name if available
        if resource.category:
            category = self.db.query(DocumentationCategoryModel).filter(
                DocumentationCategoryModel.id == resource.category
            ).first()
            if category:
                result.category_name = category.name

        # Get related resource titles
        if resource.related_resources:
            related_titles = []
            related_resources = self.db.query(DocumentationResourceModel).filter(
                DocumentationResourceModel.id.in_(resource.related_resources)
            ).all()

            for related in related_resources:
                related_titles.append(related.title)

            result.related_titles = related_titles

        return result

    def update_resource(
            self, resource_id: str, resource_update: DocumentationResourceUpdate
    ) -> DocumentationResource:
        """
        Update a documentation resource.

        Args:
            resource_id (str): ID of the resource to update
            resource_update (DocumentationResourceUpdate): Updated resource data

        Returns:
            DocumentationResource: Updated resource

        Raises:
            ValueError: If validation fails
        """
        resource = self.db.query(DocumentationResourceModel).filter(
            DocumentationResourceModel.id == resource_id
        ).first()

        if not resource:
            return None

        # Get update data, excluding None values
        update_data = {k: v for k, v in resource_update.model_dump().items() if v is not None}

        # Update timestamp
        update_data["last_updated"] = datetime.now().isoformat()

        # Handle author field separately if provided
        author = update_data.pop("author", None)

        # If content is being updated and author is provided, use update_content method
        if "content" in update_data and author:
            resource.update_content(update_data.pop("content"), author)

        # Update category relationships if category is being updated
        if "category" in update_data:
            category_id = update_data["category"]
            if category_id:
                # Find the category
                category = self.db.query(DocumentationCategoryModel).filter(
                    DocumentationCategoryModel.id == category_id
                ).first()

                if category:
                    # Clear existing categories and add the new primary one
                    resource.categories = [category]

                    # Use the model's add_to_category method
                    resource.add_to_category(category_id)

        # Update remaining fields
        for key, value in update_data.items():
            setattr(resource, key, value)

        # Commit changes
        self.db.commit()
        self.db.refresh(resource)

        # Return with additional fields
        result = DocumentationResource.model_validate(resource)

        # Get category name if available
        if resource.category:
            category = self.db.query(DocumentationCategoryModel).filter(
                DocumentationCategoryModel.id == resource.category
            ).first()
            if category:
                result.category_name = category.name

        # Get related resource titles
        if resource.related_resources:
            related_titles = []
            related_resources = self.db.query(DocumentationResourceModel).filter(
                DocumentationResourceModel.id.in_(resource.related_resources)
            ).all()

            for related in related_resources:
                related_titles.append(related.title)

            result.related_titles = related_titles

        # Add calculated properties from the model
        result.word_count = resource.word_count
        result.reading_time = resource.reading_time_minutes

        return result

    def delete_resource(self, resource_id: str) -> bool:
        """
        Delete a documentation resource.

        Args:
            resource_id (str): ID of the resource to delete

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        resource = self.db.query(DocumentationResourceModel).filter(
            DocumentationResourceModel.id == resource_id
        ).first()

        if not resource:
            return False

        # Remove resource from all categories
        if resource.categories:
            resource.categories = []

        # Check if resource is referenced by any category via JSON field
        categories = self.db.query(DocumentationCategoryModel).all()
        for category in categories:
            if category.resources and resource_id in category.resources:
                # Remove resource from category
                category.resources.remove(resource_id)

        # Delete resource
        self.db.delete(resource)
        self.db.commit()

        return True

    # Category Methods
    def list_categories(self) -> DocumentationCategoryList:
        """
        List all documentation categories.

        Returns:
            DocumentationCategoryList: Paginated list of documentation categories
        """
        categories = self.db.query(DocumentationCategoryModel).all()

        # Convert to response models with additional fields
        category_responses = []
        for category in categories:
            response = DocumentationCategory.model_validate(category)

            # Add computed properties
            response.resource_count = category.resource_count
            response.has_subcategories = category.has_subcategories

            category_responses.append(response)

        return DocumentationCategoryList(
            items=category_responses,
            total=len(categories)
        )

    def create_category(self, category: DocumentationCategoryCreate) -> DocumentationCategory:
        """
        Create a new documentation category.

        Args:
            category (DocumentationCategoryCreate): Category data to create

        Returns:
            DocumentationCategory: Created category
        """
        category_dict = category.model_dump()

        # Create DB model
        db_category = DocumentationCategoryModel(**category_dict)

        # Add to database
        self.db.add(db_category)
        self.db.commit()
        self.db.refresh(db_category)

        # Convert to response model with additional fields
        result = DocumentationCategory.model_validate(db_category)
        result.resource_count = db_category.resource_count
        result.has_subcategories = db_category.has_subcategories

        return result

    def get_category(self, category_id: str) -> Optional[DocumentationCategory]:
        """
        Get a documentation category by ID.

        Args:
            category_id (str): ID of the category to retrieve

        Returns:
            Optional[DocumentationCategory]: Category if found, None otherwise
        """
        category = self.db.query(DocumentationCategoryModel).filter(
            DocumentationCategoryModel.id == category_id
        ).first()

        if not category:
            return None

        # Convert to response model with additional fields
        result = DocumentationCategory.model_validate(category)
        result.resource_count = category.resource_count
        result.has_subcategories = category.has_subcategories

        return result

    def get_category_with_resources(self, category_id: str) -> Optional[DocumentationCategoryWithResources]:
        """
        Get a documentation category with its resources.

        Args:
            category_id (str): ID of the category to retrieve

        Returns:
            Optional[DocumentationCategoryWithResources]: Category with resources if found, None otherwise
        """
        category = self.db.query(DocumentationCategoryModel).filter(
            DocumentationCategoryModel.id == category_id
        ).first()

        if not category:
            return None

        result = DocumentationCategoryWithResources.model_validate(category)
        result.resource_count = category.resource_count
        result.has_subcategories = category.has_subcategories

        # Get resources for this category - use both relationship and resources JSON field
        resource_ids = set()

        # From relationship
        if hasattr(category, "resources_rel") and category.resources_rel:
            for resource in category.resources_rel:
                resource_ids.add(resource.id)

        # From JSON field
        if category.resources:
            if isinstance(category.resources, list):
                resource_ids.update(category.resources)
            elif isinstance(category.resources, str):
                import json
                try:
                    resources_list = json.loads(category.resources)
                    resource_ids.update(resources_list)
                except:
                    pass

        if resource_ids:
            resources = self.db.query(DocumentationResourceModel).filter(
                DocumentationResourceModel.id.in_(resource_ids)
            ).all()

            resource_responses = []
            for resource in resources:
                response = DocumentationResourceResponse.model_validate(resource)
                response.category_name = category.name

                # Add computed properties
                response.word_count = resource.word_count
                response.reading_time = resource.reading_time_minutes

                # Get related resource titles
                if resource.related_resources:
                    related_titles = []
                    related_ids = []

                    if isinstance(resource.related_resources, list):
                        related_ids = resource.related_resources
                    elif isinstance(resource.related_resources, str):
                        try:
                            related_ids = json.loads(resource.related_resources)
                        except:
                            related_ids = []

                    if related_ids:
                        related_resources = self.db.query(DocumentationResourceModel).filter(
                            DocumentationResourceModel.id.in_(related_ids)
                        ).all()

                        for related in related_resources:
                            related_titles.append(related.title)

                        response.related_titles = related_titles

                resource_responses.append(response)

            result.resources_list = resource_responses

        return result

    def update_category(self, category_id: str, category_update: DocumentationCategoryUpdate) -> DocumentationCategory:
        """
        Update a documentation category.

        Args:
            category_id (str): ID of the category to update
            category_update (DocumentationCategoryUpdate): Updated category data

        Returns:
            DocumentationCategory: Updated category
        """
        category = self.db.query(DocumentationCategoryModel).filter(
            DocumentationCategoryModel.id == category_id
        ).first()

        if not category:
            return None

        # Get update data, excluding None values
        update_data = {k: v for k, v in category_update.model_dump().items() if v is not None}

        # Update category
        for key, value in update_data.items():
            setattr(category, key, value)

        # Commit changes
        self.db.commit()
        self.db.refresh(category)

        # Convert to response model with additional fields
        result = DocumentationCategory.model_validate(category)
        result.resource_count = category.resource_count
        result.has_subcategories = category.has_subcategories

        return result

    def delete_category(self, category_id: str) -> bool:
        """
        Delete a documentation category.

        Args:
            category_id (str): ID of the category to delete

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        category = self.db.query(DocumentationCategoryModel).filter(
            DocumentationCategoryModel.id == category_id
        ).first()

        if not category:
            return False

        # Check if category has subcategories
        if category.subcategories and len(category.subcategories) > 0:
            # Update subcategories to remove parent reference
            for subcategory in category.subcategories:
                subcategory.parent_id = None

        # Remove resources from this category
        if hasattr(category, "resources_rel") and category.resources_rel:
            category.resources_rel = []

        # Clear JSON resources field
        category.resources = []

        # Delete category
        self.db.delete(category)
        self.db.commit()

        return True