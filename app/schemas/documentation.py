# File: app/schemas/documentation.py
"""
Documentation schemas for the HideSync API.

This module contains Pydantic models for documentation resources, categories,
application contexts, and contextual help mappings, supporting the knowledge base
and contextual help functionality in the application.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator

from app.db.models.enums import SkillLevel


class DocumentationType(str, Enum):
    """Enumeration of documentation resource types."""

    GUIDE = "GUIDE"
    TUTORIAL = "TUTORIAL"
    REFERENCE = "REFERENCE"
    FAQ = "FAQ"
    TROUBLESHOOTING = "TROUBLESHOOTING"


class DocumentationStatus(str, Enum):
    """Enumeration of documentation resource statuses."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


# Documentation Category Schemas
class DocumentationCategoryBase(BaseModel):
    """
    Base schema for documentation category data.
    """

    name: str = Field(
        ..., description="Name of the category", min_length=1, max_length=100
    )
    description: Optional[str] = Field(None, description="Description of the category")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    slug: str = Field(
        ...,
        description="URL-friendly identifier for the category",
        min_length=1,
        max_length=100,
    )
    display_order: Optional[int] = Field(
        0, description="Order in which to display this category"
    )
    is_public: Optional[bool] = Field(
        True, description="Whether this category is publicly visible"
    )


class DocumentationCategoryCreate(DocumentationCategoryBase):
    """
    Schema for creating a new documentation category.
    """

    parent_category_id: Optional[str] = Field(
        None, description="ID of the parent category (for hierarchical organization)"
    )


class DocumentationCategoryUpdate(BaseModel):
    """
    Schema for updating documentation category information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Name of the category", min_length=1, max_length=100
    )
    description: Optional[str] = Field(None, description="Description of the category")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    slug: Optional[str] = Field(
        None,
        description="URL-friendly identifier for the category",
        min_length=1,
        max_length=100,
    )
    display_order: Optional[int] = Field(
        None, description="Order in which to display this category"
    )
    is_public: Optional[bool] = Field(
        None, description="Whether this category is publicly visible"
    )
    parent_category_id: Optional[str] = Field(
        None, description="ID of the parent category (for hierarchical organization)"
    )


class DocumentationCategoryInDB(DocumentationCategoryBase):
    """
    Schema for documentation category information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the category")
    parent_category_id: Optional[str] = Field(
        None, description="ID of the parent category (for hierarchical organization)"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the category was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the category was last updated"
    )

    class Config:
        from_attributes = True


class DocumentationCategory(DocumentationCategoryInDB):
    """
    Schema for documentation category responses in the API.
    """

    resource_count: int = Field(0, description="Number of resources in this category")
    has_subcategories: bool = Field(
        False, description="Whether this category has subcategories"
    )


# Documentation Resource Schemas
class DocumentationResourceBase(BaseModel):
    """
    Base schema for documentation resource data.
    """

    title: str = Field(
        ..., description="Title of the resource", min_length=1, max_length=200
    )
    description: Optional[str] = Field(
        None, description="Brief description of the resource"
    )
    content: str = Field(..., description="Full content of the resource")
    type: DocumentationType = Field(
        ...,
        description="Type of resource (GUIDE, TUTORIAL, REFERENCE, FAQ, TROUBLESHOOTING)",
    )
    skill_level: Optional[SkillLevel] = Field(
        None, description="Required skill level for this content"
    )
    version: Optional[str] = Field(None, description="Version of the resource")
    tags: Optional[List[str]] = Field(
        None, description="Tags for categorizing the resource"
    )
    related_resource_ids: Optional[List[str]] = Field(
        None, description="IDs of related resources"
    )
    is_public: Optional[bool] = Field(
        True, description="Whether this resource is publicly visible"
    )
    thumbnail_url: Optional[str] = Field(
        None, description="URL to the resource thumbnail image"
    )
    media_attachments: Optional[Dict[str, Any]] = Field(
        None, description="Associated media content (videos, images, etc.)"
    )
    status: Optional[DocumentationStatus] = Field(
        DocumentationStatus.PUBLISHED, description="Publication status"
    )


class DocumentationResourceCreate(DocumentationResourceBase):
    """
    Schema for creating a new documentation resource.
    """

    author_id: Optional[str] = Field(None, description="ID of the author")
    category_ids: Optional[List[str]] = Field(
        None, description="IDs of categories to assign this resource to"
    )


class DocumentationResourceUpdate(BaseModel):
    """
    Schema for updating documentation resource information.

    All fields are optional to allow partial updates.
    """

    title: Optional[str] = Field(
        None, description="Title of the resource", min_length=1, max_length=200
    )
    description: Optional[str] = Field(
        None, description="Brief description of the resource"
    )
    content: Optional[str] = Field(None, description="Full content of the resource")
    type: Optional[DocumentationType] = Field(
        None,
        description="Type of resource (GUIDE, TUTORIAL, REFERENCE, FAQ, TROUBLESHOOTING)",
    )
    skill_level: Optional[SkillLevel] = Field(
        None, description="Required skill level for this content"
    )
    version: Optional[str] = Field(None, description="Version of the resource")
    tags: Optional[List[str]] = Field(
        None, description="Tags for categorizing the resource"
    )
    related_resource_ids: Optional[List[str]] = Field(
        None, description="IDs of related resources"
    )
    author_id: Optional[str] = Field(None, description="ID of the author")
    is_public: Optional[bool] = Field(
        None, description="Whether this resource is publicly visible"
    )
    thumbnail_url: Optional[str] = Field(
        None, description="URL to the resource thumbnail image"
    )
    media_attachments: Optional[Dict[str, Any]] = Field(
        None, description="Associated media content (videos, images, etc.)"
    )
    status: Optional[DocumentationStatus] = Field(
        None, description="Publication status"
    )
    category_ids: Optional[List[str]] = Field(
        None, description="IDs of categories to assign this resource to"
    )


class DocumentationResourceInDB(DocumentationResourceBase):
    """
    Schema for documentation resource information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the resource")
    author_id: Optional[str] = Field(None, description="ID of the author")
    created_at: datetime = Field(
        ..., description="Timestamp when the resource was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the resource was last updated"
    )

    class Config:
        from_attributes = True


class DocumentationResourceResponse(DocumentationResourceInDB):
    """
    Schema for documentation resource responses in the API with additional fields.
    """

    categories: Optional[List[DocumentationCategory]] = Field(
        None, description="Categories this resource belongs to"
    )
    word_count: int = Field(0, description="Number of words in the content")
    reading_time_minutes: int = Field(
        1, description="Estimated reading time in minutes"
    )

    class Config:
        from_attributes = True


# Application Context Schemas
class ApplicationContextBase(BaseModel):
    """
    Base schema for application context data.
    """

    context_key: str = Field(
        ...,
        description="Unique identifier key for this UI context",
        min_length=2,
        max_length=100,
    )
    name: str = Field(
        ...,
        description="Human-readable name for this context",
        min_length=2,
        max_length=100,
    )
    description: Optional[str] = Field(
        None, description="Description of this UI context"
    )
    route: Optional[str] = Field(None, description="Associated application route")
    component_path: Optional[str] = Field(
        None, description="Path to the React component"
    )


class ApplicationContextCreate(ApplicationContextBase):
    """
    Schema for creating a new application context.
    """

    pass


class ApplicationContextUpdate(BaseModel):
    """
    Schema for updating application context information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None,
        description="Human-readable name for this context",
        min_length=2,
        max_length=100,
    )
    description: Optional[str] = Field(
        None, description="Description of this UI context"
    )
    route: Optional[str] = Field(None, description="Associated application route")
    component_path: Optional[str] = Field(
        None, description="Path to the React component"
    )


class ApplicationContextInDB(ApplicationContextBase):
    """
    Schema for application context information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the context")
    created_at: datetime = Field(
        ..., description="Timestamp when the context was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the context was last updated"
    )

    class Config:
        from_attributes = True


class ApplicationContext(ApplicationContextInDB):
    """
    Schema for application context responses in the API.
    """

    pass


# Contextual Help Mapping Schemas
class ContextualHelpMappingBase(BaseModel):
    """
    Base schema for contextual help mapping data.
    """

    resource_id: str = Field(..., description="ID of the documentation resource")
    context_key: str = Field(..., description="Key of the application context")
    relevance_score: Optional[int] = Field(
        50, description="Relevance score (1-100) for sorting results", ge=1, le=100
    )
    is_active: Optional[bool] = Field(
        True, description="Whether this mapping is active"
    )


class ContextualHelpMappingCreate(ContextualHelpMappingBase):
    """
    Schema for creating a new contextual help mapping.
    """

    pass


class ContextualHelpMappingUpdate(BaseModel):
    """
    Schema for updating contextual help mapping information.

    All fields are optional to allow partial updates.
    """

    relevance_score: Optional[int] = Field(
        None, description="Relevance score (1-100) for sorting results", ge=1, le=100
    )
    is_active: Optional[bool] = Field(
        None, description="Whether this mapping is active"
    )


class ContextualHelpMappingInDB(ContextualHelpMappingBase):
    """
    Schema for contextual help mapping information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the mapping")
    created_at: datetime = Field(
        ..., description="Timestamp when the mapping was created"
    )

    class Config:
        from_attributes = True


class ContextualHelpMapping(ContextualHelpMappingInDB):
    """
    Schema for contextual help mapping responses in the API.
    """

    pass


class ContextualHelpResponse(BaseModel):
    """
    Schema for responses to contextual help queries.
    """

    context_key: str = Field(..., description="Context key that was queried")
    context_name: str = Field(..., description="Name of the context")
    resources: List[DocumentationResourceResponse] = Field(
        [], description="Relevant documentation resources"
    )


# List response schemas
class DocumentationResourceList(BaseModel):
    """
    Schema for paginated documentation resource list responses.
    """

    items: List[DocumentationResourceResponse]
    total: int = Field(..., description="Total number of resources matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class DocumentationCategoryTree(DocumentationCategory):
    """
    Schema for hierarchical documentation category responses.
    """

    subcategories: List["DocumentationCategoryTree"] = Field(
        [], description="Subcategories"
    )
    resources: Optional[List[DocumentationResourceResponse]] = Field(
        None, description="Resources in this category"
    )


DocumentationCategoryTree.update_forward_refs()


class DocumentationCategoryWithResources(DocumentationCategory):
    """
    Schema for documentation category responses that include their resources.
    """

    resources: List[DocumentationResourceResponse] = Field(
        [], description="Resources in this category"
    )

    class Config:
        from_attributes = True


class DocumentationCategoryList(BaseModel):
    """
    Schema for paginated documentation category list responses.
    """

    items: List[DocumentationCategory]
    total: int = Field(..., description="Total number of categories")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class ApplicationContextList(BaseModel):
    """
    Schema for paginated application context list responses.
    """

    items: List[ApplicationContext]
    total: int = Field(..., description="Total number of contexts")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class DocumentationSearchParams(BaseModel):
    """
    Schema for documentation search parameters.
    """

    category_id: Optional[str] = Field(None, description="Filter by category ID")
    type: Optional[DocumentationType] = Field(
        None, description="Filter by resource type"
    )
    skill_level: Optional[SkillLevel] = Field(None, description="Filter by skill level")
    status: Optional[DocumentationStatus] = Field(
        None, description="Filter by publication status"
    )
    search: Optional[str] = Field(None, description="Search term")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    page: Optional[int] = Field(1, description="Page number", ge=1)
    size: Optional[int] = Field(20, description="Page size", ge=1, le=100)
    sort_by: Optional[str] = Field("updated_at", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc or desc)")
