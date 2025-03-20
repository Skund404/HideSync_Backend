# File: app/schemas/search_params.py
"""
Search parameter schemas for the HideSync API.

This module contains Pydantic models for search and filtering parameters
used across various API endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CustomerSearchParams(BaseModel):
    """
    Search parameters for filtering customer records.
    """
    status: Optional[str] = Field(None, description="Filter by customer status")
    tier: Optional[str] = Field(None, description="Filter by customer tier")
    search: Optional[str] = Field(None, description="Search term for name or email")
    source: Optional[str] = Field(None, description="Filter by customer source")
    min_total_spent: Optional[float] = Field(None, description="Minimum total spent")
    max_total_spent: Optional[float] = Field(None, description="Maximum total spent")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class MaterialSearchParams(BaseModel):
    """
    Search parameters for filtering material records.
    """
    material_type: Optional[str] = Field(None, description="Filter by material type")
    quality: Optional[str] = Field(None, description="Filter by material quality")
    in_stock: Optional[bool] = Field(None, description="Filter by availability")
    search: Optional[str] = Field(None, description="Search term for name")
    supplier_id: Optional[int] = Field(None, description="Filter by supplier ID")
    min_price: Optional[float] = Field(None, description="Minimum price")
    max_price: Optional[float] = Field(None, description="Maximum price")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class InventorySearchParams(BaseModel):
    """
    Search parameters for filtering inventory records.
    """
    status: Optional[str] = Field(None, description="Filter by inventory status")
    location: Optional[str] = Field(None, description="Filter by storage location")
    item_type: Optional[str] = Field(None, description="Filter by item type (material/product/tool)")
    search: Optional[str] = Field(None, description="Search term for item name")
    below_reorder_point: Optional[bool] = Field(None, description="Filter items below reorder point")
    supplier_id: Optional[int] = Field(None, description="Filter by supplier ID")


class ProjectSearchParams(BaseModel):
    """
    Search parameters for filtering project records.
    """
    status: Optional[str] = Field(None, description="Filter by project status")
    type: Optional[str] = Field(None, description="Filter by project type")
    customer_id: Optional[int] = Field(None, description="Filter by customer ID")
    search: Optional[str] = Field(None, description="Search term for project name")
    start_date_from: Optional[str] = Field(None, description="Filter by start date (from)")
    start_date_to: Optional[str] = Field(None, description="Filter by start date (to)")
    due_date_from: Optional[str] = Field(None, description="Filter by due date (from)")
    due_date_to: Optional[str] = Field(None, description="Filter by due date (to)")
    template_id: Optional[int] = Field(None, description="Filter by template ID")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class SaleSearchParams(BaseModel):
    """
    Search parameters for filtering sale records.
    """
    status: Optional[str] = Field(None, description="Filter by sale status")
    customer_id: Optional[int] = Field(None, description="Filter by customer ID")
    start_date: Optional[str] = Field(None, description="Filter by start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Filter by end date (YYYY-MM-DD)")
    payment_status: Optional[str] = Field(None, description="Filter by payment status")
    fulfillment_status: Optional[str] = Field(None, description="Filter by fulfillment status")
    search: Optional[str] = Field(None, description="Search term")
    min_total: Optional[float] = Field(None, description="Minimum sale total")
    max_total: Optional[float] = Field(None, description="Maximum sale total")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    platform: Optional[str] = Field(None, description="Filter by sales platform")


class SupplierSearchParams(BaseModel):
    """
    Search parameters for filtering supplier records.
    """
    status: Optional[str] = Field(None, description="Filter by supplier status")
    category: Optional[str] = Field(None, description="Filter by supplier category")
    material_category: Optional[str] = Field(None, description="Filter by material category")
    search: Optional[str] = Field(None, description="Search term for name or contact")
    min_rating: Optional[int] = Field(None, description="Minimum supplier rating", ge=1, le=5)
    max_rating: Optional[int] = Field(None, description="Maximum supplier rating", ge=1, le=5)


class StorageSearchParams(BaseModel):
    """
    Search parameters for filtering storage location records.
    """
    type: Optional[str] = Field(None, description="Filter by location type")
    section: Optional[str] = Field(None, description="Filter by section")
    status: Optional[str] = Field(None, description="Filter by location status")
    search: Optional[str] = Field(None, description="Search term for name")
    min_capacity: Optional[int] = Field(None, description="Minimum capacity")
    max_capacity: Optional[int] = Field(None, description="Maximum capacity")
    occupancy_rate_min: Optional[float] = Field(None, description="Minimum occupancy rate (0-100)")
    occupancy_rate_max: Optional[float] = Field(None, description="Maximum occupancy rate (0-100)")


class DocumentationSearchParams(BaseModel):
    """
    Search parameters for filtering documentation resources.
    """
    category: Optional[str] = Field(None, description="Filter by category")
    type: Optional[str] = Field(None, description="Filter by resource type")
    skill_level: Optional[str] = Field(None, description="Filter by skill level")
    search: Optional[str] = Field(None, description="Search term for title or content")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    author: Optional[str] = Field(None, description="Filter by author")