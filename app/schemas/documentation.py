# File: app/schemas/documentation.py
"""
Documentation schemas for the HideSync API.

This module contains Pydantic models for documentation resources and categories,
supporting the knowledge base functionality in the application.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator

from app.db.models.enums import SkillLevel


class DocumentationCategoryBase(BaseModel):
    """
    Base schema for documentation category data.
    """
    name: str = Field(..., description="Name of the category", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Description of the category")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    resources: Optional[List[str]] = Field(None, description="IDs of resources in this category")


class DocumentationCategoryCreate(DocumentationCategoryBase):
    """
    Schema for creating a new documentation category.
    """
    pass


class DocumentationCategoryUpdate(BaseModel):
    """
    Schema for updating documentation category information.

    All fields are optional to allow partial updates.
    """
    name: Optional[str] = Field(None, description="Name of the category", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Description of the category")
    icon: Optional[str] = Field(None, description="Icon identifier for the category")
    resources: Optional[List[str]] = Field(None, description="IDs of resources in this category")


class DocumentationCategoryInDB(DocumentationCategoryBase):
    """
    Schema for documentation category information as stored in the database.
    """
    id: str = Field(..., description="Unique identifier for the category")

    class Config:
        orm_mode = True


class DocumentationResourceBase(BaseModel):
    """
    Base schema for documentation resource data.
    """
    title: str = Field(..., description="Title of the resource", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Brief description of the resource")
    content: str = Field(..., description="Full content of the resource")
    category: Optional[str] = Field(None, description="Primary category")
    type: Optional[str] = Field(None, description="Type of resource (GUIDE, TUTORIAL, REFERENCE)")
    skill_level: Optional[SkillLevel] = Field(None, description="Required skill level for this content")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the resource")
    related_resources: Optional[List[str]] = Field(None, description="IDs of related resources")
    contextual_help_keys: Optional[List[str]] = Field(None, description="Context keys for help system integration")
    videos: Optional[Dict[str, Any]] = Field(None, description="Associated video content")


class DocumentationResourceCreate(DocumentationResourceBase):
    """
    Schema for creating a new documentation resource.
    """
    author: Optional[str] = Field(None, description="Author of the resource")


class DocumentationResourceUpdate(BaseModel):
    """
    Schema for updating documentation resource information.

    All fields are optional to allow partial updates.
    """
    title: Optional[str] = Field(None, description="Title of the resource", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Brief description of the resource")
    content: Optional[str] = Field(None, description="Full content of the resource")
    category: Optional[str] = Field(None, description="Primary category")
    type: Optional[str] = Field(None, description="Type of resource (GUIDE, TUTORIAL, REFERENCE)")
    skill_level: Optional[SkillLevel] = Field(None, description="Required skill level for this content")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the resource")
    related_resources: Optional[List[str]] = Field(None, description="IDs of related resources")
    author: Optional[str] = Field(None, description="Author of the resource")
    contextual_help_keys: Optional[List[str]] = Field(None, description="Context keys for help system integration")
    videos: Optional[Dict[str, Any]] = Field(None, description="Associated video content")


class DocumentationResourceInDB(DocumentationResourceBase):
    """
    Schema for documentation resource information as stored in the database.
    """
    id: str = Field(..., description="Unique identifier for the resource")
    author: Optional[str] = Field(None, description="Author of the resource")
    last_updated: str = Field(..., description="Timestamp when the resource was last updated")

    class Config:
        orm_mode = True


class DocumentationResourceResponse(DocumentationResourceInDB):
    """
    Schema for documentation resource responses in the API.
    """
    category_name: Optional[str] = Field(None, description="Name of the primary category")
    related_titles: Optional[List[str]] = Field(None, description="Titles of related resources")

    class Config:
        orm_mode = True


class DocumentationResourceList(BaseModel):
    """
    Schema for paginated documentation resource list responses.
    """
    items: List[DocumentationResourceResponse]
    total: int = Field(..., description="Total number of resources matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class DocumentationCategoryWithResources(DocumentationCategoryInDB):
    """
    Schema for documentation category responses that include their resources.
    """
    resources_list: List[DocumentationResourceResponse] = Field([], description="Resources in this category")

    class Config:
        orm_mode = True


class DocumentationCategoryList(BaseModel):
    """
    Schema for paginated documentation category list responses.
    """
    items: List[DocumentationCategoryInDB]
    total: int = Field(..., description="Total number of categories")

    class Config:
        orm_mode = True


class RefundBase(BaseModel):
    """
    Base schema for refund data.
    """
    sale_id: int = Field(..., description="ID of the sale being refunded")
    refund_date: datetime = Field(..., description="Date of the refund")
    refund_amount: float = Field(..., description="Amount refunded", gt=0)
    reason: str = Field(..., description="Reason for the refund")
    status: str = Field(..., description="Status of the refund")


class RefundCreate(RefundBase):
    """
    Schema for creating a new refund.
    """

    @validator('refund_amount')
    def validate_refund_amount(cls, v):
        if v <= 0:
            raise ValueError('Refund amount must be positive')
        return v


class RefundUpdate(BaseModel):
    """
    Schema for updating refund information.

    All fields are optional to allow partial updates.
    """
    refund_date: Optional[datetime] = Field(None, description="Date of the refund")
    refund_amount: Optional[float] = Field(None, description="Amount refunded", gt=0)
    reason: Optional[str] = Field(None, description="Reason for the refund")
    status: Optional[str] = Field(None, description="Status of the refund")

    @validator('refund_amount')
    def validate_refund_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Refund amount must be positive')
        return v


class RefundInDB(RefundBase):
    """
    Schema for refund information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the refund")

    class Config:
        orm_mode = True


class RefundResponse(RefundInDB):
    """
    Schema for refund responses in the API.
    """
    sale_order_number: Optional[str] = Field(None, description="Order number of the associated sale")
    customer_name: Optional[str] = Field(None, description="Name of the customer")

    class Config:
        orm_mode = True


class RefundList(BaseModel):
    """
    Schema for paginated refund list responses.
    """
    items: List[RefundResponse]
    total: int = Field(..., description="Total number of refunds matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")