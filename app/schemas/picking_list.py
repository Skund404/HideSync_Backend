# File: app/schemas/picking_list.py
"""
Pydantic schemas for the picking list feature of the HideSync system.

This module defines the request and response models for picking list operations,
including list creation, item management, and status updates. These schemas
are used for validating API requests and formatting responses.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enum definitions
class PickingListStatus(str, Enum):
    """Status options for picking lists."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PARTIALLY_PICKED = "PARTIALLY_PICKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ItemStatus(str, Enum):
    """Status options for picking list items."""

    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETE = "complete"


# Base schemas
class PickingListItemBase(BaseModel):
    """Base schema for picking list items."""

    material_id: Optional[int] = None
    component_id: Optional[int] = None
    quantity_ordered: int = Field(
        ..., gt=0, description="Quantity needed, must be greater than 0"
    )
    notes: Optional[str] = None

    @validator("material_id", "component_id")
    def validate_item_reference(cls, v, values):
        """Validate that either material_id or component_id is provided."""
        if (
            "material_id" in values
            and not values["material_id"]
            and "component_id" in values
            and not values["component_id"]
        ):
            raise ValueError("Either material_id or component_id must be provided")
        return v


class PickingListBase(BaseModel):
    """Base schema for picking lists."""

    project_id: int = Field(..., description="ID of the project this list is for")
    sale_id: Optional[int] = None
    status: Optional[PickingListStatus] = PickingListStatus.PENDING
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


# Create schemas
class PickingListItemCreate(PickingListItemBase):
    """Schema for creating a new picking list item."""

    pass


class PickingListCreate(PickingListBase):
    """Schema for creating a new picking list."""

    items: Optional[List[PickingListItemCreate]] = []


# Update schemas
class PickingListItemUpdate(BaseModel):
    """Schema for updating a picking list item."""

    quantity_picked: Optional[int] = Field(None, ge=0)
    status: Optional[ItemStatus] = None
    notes: Optional[str] = None


class PickingListStatusUpdate(BaseModel):
    """Schema for updating a picking list's status."""

    status: PickingListStatus
    notes: Optional[str] = None
    completed_by: Optional[str] = None


class PickingListUpdate(BaseModel):
    """Schema for updating a picking list."""

    status: Optional[PickingListStatus] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class PickItemRequest(BaseModel):
    """Schema for recording picked items."""

    quantity_picked: int = Field(..., gt=0)
    location: Optional[str] = None
    notes: Optional[str] = None


class CancelPickingListRequest(BaseModel):
    """Schema for cancelling a picking list."""

    reason: str = Field(..., min_length=2)


# Response schemas
class MaterialInfo(BaseModel):
    """Material information included in responses."""

    id: int
    name: Optional[str] = None
    material_type: Optional[str] = None
    unit: Optional[str] = None
    status: Optional[str] = None
    storage_location: Optional[str] = None


class ComponentInfo(BaseModel):
    """Component information included in responses."""

    id: int
    name: Optional[str] = None
    component_type: Optional[str] = None


class ProjectInfo(BaseModel):
    """Project information included in responses."""

    id: int
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None


class PickingListItemResponse(BaseModel):
    """Response schema for picking list items."""

    id: str
    picking_list_id: str
    material_id: Optional[int] = None
    component_id: Optional[int] = None
    quantity_ordered: int
    quantity_picked: int
    status: str
    notes: Optional[str] = None
    material: Optional[MaterialInfo] = None
    component: Optional[ComponentInfo] = None
    completion_percentage: float = 0

    class Config:
        orm_mode = True


class PickingListResponse(BaseModel):
    """Response schema for picking lists."""

    id: str
    project_id: int
    sale_id: Optional[int] = None
    status: PickingListStatus
    assigned_to: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_complete: bool
    progress_percentage: float

    class Config:
        orm_mode = True


class CompletionStats(BaseModel):
    """Statistics about picking list completion."""

    total_items: int
    completed_items: int
    partial_items: int
    pending_items: int
    completion_percentage: float
    total_ordered: Optional[float] = None
    total_picked: Optional[float] = None
    picking_percentage: Optional[float] = None


class PickingListDetailResponse(PickingListResponse):
    """Detailed response schema for picking lists including items and statistics."""

    project: Optional[ProjectInfo] = None
    items: List[PickingListItemResponse] = []
    completion_stats: CompletionStats

    class Config:
        orm_mode = True


class PickingListReportResponse(BaseModel):
    """Response schema for picking list reports."""

    picking_list_id: str
    project_id: int
    project_name: Optional[str] = None
    status: PickingListStatus
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    statistics: CompletionStats
    by_material_type: Dict[str, Any] = {}
    by_location: Dict[str, Any] = {}
    items: List[PickingListItemResponse] = []

    class Config:
        orm_mode = True
