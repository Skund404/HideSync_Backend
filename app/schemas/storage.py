# File: app/schemas/storage.py
"""
Storage schemas for the HideSync API.

This module contains Pydantic models for storage management, including storage locations,
storage cells, storage assignments, and storage moves.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, root_validator

from app.db.models.enums import StorageLocationType


class StorageCellBase(BaseModel):
    """
    Base schema for storage cell data.
    """

    position: Dict[str, Any] = Field(
        ..., description="Position coordinates within the storage location"
    )
    item_id: Optional[int] = Field(
        None, description="ID of the item stored in this cell if any"
    )
    item_type: Optional[str] = Field(
        None, description="Type of the item stored (material, tool, etc.)"
    )
    occupied: bool = Field(False, description="Whether this cell is currently occupied")
    notes: Optional[str] = Field(None, description="Additional notes about this cell")


class StorageCellCreate(StorageCellBase):
    """
    Schema for creating a new storage cell.
    """

    storage_id: str = Field(
        ..., description="ID of the storage location this cell belongs to"
    )


class StorageCellUpdate(BaseModel):
    """
    Schema for updating storage cell information.
    """

    position: Optional[Dict[str, Any]] = Field(
        None, description="Position coordinates within the storage location"
    )
    item_id: Optional[int] = Field(
        None, description="ID of the item stored in this cell if any"
    )
    item_type: Optional[str] = Field(
        None, description="Type of the item stored (material, tool, etc.)"
    )
    occupied: Optional[bool] = Field(
        None, description="Whether this cell is currently occupied"
    )
    notes: Optional[str] = Field(None, description="Additional notes about this cell")


class StorageCellInDB(StorageCellBase):
    """
    Schema for storage cell information as stored in the database.
    """

    id: str = Field(
        ..., description="Unique identifier for the storage cell"
    )  # Added ID
    storage_id: str = Field(
        ..., description="ID of the storage location this cell belongs to"
    )

    class Config:
        from_attributes = True


class StorageCellResponse(StorageCellInDB):
    """
    Schema for storage cell responses in the API.
    """

    item_name: Optional[str] = Field(
        None, description="Name of the item stored in this cell"
    )

    class Config:
        from_attributes = True


class StorageLocationBase(BaseModel):
    """
    Base schema for storage location data.
    """

    name: str = Field(
        ..., description="Name of the storage location", min_length=1, max_length=100
    )
    type: StorageLocationType = Field(
        ..., description="Type of storage (CABINET, SHELF, DRAWER, etc.)"
    )
    section: Optional[str] = Field(
        None, description="Section or area within the workshop"
    )
    description: Optional[str] = Field(
        None, description="Detailed description of the storage location"
    )
    dimensions: Optional[Dict[str, Any]] = Field(
        None, description="Physical dimensions"
    )
    capacity: Optional[int] = Field(None, description="Maximum capacity", gt=0)
    utilized: Optional[int] = Field(
        0, description="Amount of capacity currently utilized", ge=0
    )
    status: Optional[str] = Field(None, description="Status of the storage location")
    notes: Optional[str] = Field(None, description="Additional notes")
    parent_storage: Optional[str] = Field(
        None, description="ID of the parent storage location if nested"
    )


class StorageLocationCreate(StorageLocationBase):
    """
    Schema for creating a new storage location.
    """

    cells: Optional[List[StorageCellCreate]] = Field(
        None, description="Cells within this storage location"
    )

    @validator("utilized")
    def validate_utilized(cls, v, values):
        if (
            v is not None
            and "capacity" in values
            and values["capacity"] is not None
            and v > values["capacity"]
        ):
            raise ValueError("Utilized space cannot exceed capacity")
        return v


class StorageLocationUpdate(BaseModel):
    """
    Schema for updating storage location information.
    """

    name: Optional[str] = Field(
        None, description="Name of the storage location", min_length=1, max_length=100
    )
    type: Optional[StorageLocationType] = Field(
        None, description="Type of storage (CABINET, SHELF, DRAWER, etc.)"
    )
    section: Optional[str] = Field(
        None, description="Section or area within the workshop"
    )
    description: Optional[str] = Field(
        None, description="Detailed description of the storage location"
    )
    dimensions: Optional[Dict[str, Any]] = Field(
        None, description="Physical dimensions"
    )
    capacity: Optional[int] = Field(None, description="Maximum capacity", gt=0)
    utilized: Optional[int] = Field(
        None, description="Amount of capacity currently utilized", ge=0
    )
    status: Optional[str] = Field(None, description="Status of the storage location")
    notes: Optional[str] = Field(None, description="Additional notes")
    parent_storage: Optional[str] = Field(
        None, description="ID of the parent storage location if nested"
    )

    @validator("utilized")
    def validate_utilized(cls, v, values):
        # Ensure capacity is present and a number before comparison
        capacity = values.get("capacity")
        if (
            v is not None
            and capacity is not None
            and isinstance(capacity, (int, float))
        ):
            if v > capacity:
                raise ValueError("Utilized space cannot exceed capacity")
        return v


class StorageLocationInDB(StorageLocationBase):
    """
    Schema for storage location information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the storage location")
    last_modified: Optional[str] = Field(
        None, description="Last modification timestamp"
    )

    class Config:
        from_attributes = True


class StorageLocationResponse(StorageLocationInDB):
    """
    Schema for storage location responses in the API.
    """

    cells: List[StorageCellResponse] = Field(
        [], description="Cells within this storage location"
    )
    usage_percentage: Optional[float] = Field(
        None, description="Percentage of capacity utilized"
    )
    item_count: Optional[int] = Field(
        None, description="Number of items stored in this location"
    )
    child_locations: Optional[List[str]] = Field(
        None, description="IDs of child storage locations"
    )

    class Config:
        from_attributes = True


class StorageLocationList(BaseModel):
    """
    Schema for paginated storage location list responses.
    """

    items: List[StorageLocationResponse]
    total: int = Field(
        ..., description="Total number of storage locations matching the query"
    )
    page: int = Field(..., description="Current page number")
    size: int = Field(
        ..., description="Number of items per page"
    )  # Use 'size' to match frontend
    pages: int = Field(..., description="Total number of pages")


class StorageAssignmentBase(BaseModel):
    """
    Base schema for storage assignment data.
    """

    material_id: int = Field(..., description="ID of the material being stored")
    material_type: str = Field(..., description="Type of material")
    storage_id: str = Field(..., description="ID of the storage location")
    position: Optional[Dict[str, Any]] = Field(
        None, description="Position within the storage location"
    )
    quantity: float = Field(..., description="Quantity being stored", gt=0)
    notes: Optional[str] = Field(
        None, description="Additional notes about this assignment"
    )


class StorageAssignmentCreate(StorageAssignmentBase):
    """
    Schema for creating a new storage assignment.
    """

    assigned_by: Optional[str] = Field(None, description="User who made the assignment")


class StorageAssignmentUpdate(BaseModel):
    """
    Schema for updating storage assignment information.
    """

    material_id: Optional[int] = Field(
        None, description="ID of the material being stored"
    )
    material_type: Optional[str] = Field(None, description="Type of material")
    storage_id: Optional[str] = Field(None, description="ID of the storage location")
    position: Optional[Dict[str, Any]] = Field(
        None, description="Position within the storage location"
    )
    quantity: Optional[float] = Field(None, description="Quantity being stored", gt=0)
    notes: Optional[str] = Field(
        None, description="Additional notes about this assignment"
    )
    assigned_by: Optional[str] = Field(
        None, description="User who updated the assignment"
    )


class StorageAssignmentInDB(StorageAssignmentBase):
    """
    Schema for storage assignment information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the storage assignment")
    assigned_date: str = Field(..., description="Date when the assignment was made")
    assigned_by: Optional[str] = Field(None, description="User who made the assignment")

    class Config:
        from_attributes = True


class StorageAssignmentResponse(StorageAssignmentInDB):
    """
    Schema for storage assignment responses in the API.
    """

    material_name: Optional[str] = Field(
        None, description="Name of the assigned material"
    )
    storage_name: Optional[str] = Field(
        None, description="Name of the storage location"
    )

    class Config:
        from_attributes = True


class StorageMoveBase(BaseModel):
    """
    Base schema for storage move data.
    """

    material_id: int = Field(..., description="ID of the material being moved")
    material_type: str = Field(..., description="Type of material")
    from_storage_id: str = Field(..., description="ID of the source storage location")
    to_storage_id: str = Field(
        ..., description="ID of the destination storage location"
    )
    quantity: float = Field(..., description="Quantity being moved", gt=0)
    reason: Optional[str] = Field(None, description="Reason for the move")
    notes: Optional[str] = Field(None, description="Additional notes about this move")


class StorageMoveCreate(StorageMoveBase):
    """
    Schema for creating a new storage move.
    """

    moved_by: Optional[str] = Field(None, description="User who performed the move")


class StorageMoveUpdate(BaseModel):
    """
    Schema for updating storage move information.
    """

    quantity: Optional[float] = Field(None, description="Quantity being moved", gt=0)
    reason: Optional[str] = Field(None, description="Reason for the move")
    notes: Optional[str] = Field(None, description="Additional notes about this move")
    moved_by: Optional[str] = Field(None, description="User who updated the move")


class StorageMoveInDB(StorageMoveBase):
    """
    Schema for storage move information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the storage move")
    move_date: str = Field(..., description="Date when the move was performed")
    moved_by: Optional[str] = Field(None, description="User who performed the move")

    class Config:
        from_attributes = True


class StorageMoveResponse(StorageMoveInDB):
    """
    Schema for storage move responses in the API.
    """

    material_name: Optional[str] = Field(None, description="Name of the moved material")
    from_storage_name: Optional[str] = Field(
        None, description="Name of the source storage location"
    )
    to_storage_name: Optional[str] = Field(
        None, description="Name of the destination storage location"
    )

    class Config:
        from_attributes = True


class StorageMoveList(BaseModel):
    """
    Schema for paginated storage move list responses.
    """

    items: List[StorageMoveResponse]
    total: int = Field(
        ..., description="Total number of storage moves matching the query"
    )
    page: int = Field(..., description="Current page number")
    size: int = Field(
        ..., description="Number of items per page"
    )  # Use 'size' to match frontend
    pages: int = Field(..., description="Total number of pages")


# --- Occupancy Report Schema ---
class OccupancyStats(BaseModel):
    """Sub-schema for capacity/utilization stats."""

    capacity: float = 0.0
    utilized: float = 0.0
    locations: int = 0
    utilization_percentage: float = 0.0


class LocationUtilizationInfo(BaseModel):
    """Sub-schema for most/least utilized locations."""

    id: str
    name: str
    capacity: int  # Keep as int for display?
    utilized: int  # Keep as int for display?
    utilization_percentage: float


class StorageOccupancyReport(BaseModel):
    """
    Schema for storage occupancy report.
    """

    total_locations: int = Field(..., description="Total number of storage locations")
    total_capacity: float = Field(..., description="Total storage capacity")
    total_utilized: float = Field(..., description="Total utilized storage")
    total_items: Optional[int] = Field(
        None, description="Total number of distinct assigned items"
    )  # Made optional
    utilization_percentage: float = Field(
        ..., description="Overall storage utilization percentage based on capacity"
    )
    overall_usage_percentage: float = Field(
        ..., description="Overall usage percentage (might be same as utilization)"
    )

    by_section: Dict[str, OccupancyStats] = Field(  # Use sub-schema
        default_factory=dict, description="Storage utilization grouped by section"
    )
    by_type: Dict[str, OccupancyStats] = Field(  # Use sub-schema
        default_factory=dict, description="Storage utilization grouped by location type"
    )

    locations_by_type: Dict[str, int] = Field(  # Just the count here
        default_factory=dict, description="Count of locations grouped by type"
    )
    locations_by_section: Dict[str, int] = Field(  # Just the count here
        default_factory=dict, description="Count of locations grouped by section"
    )

    items_by_type: Dict[str, int] = Field(  # Count of items by type
        default_factory=dict, description="Count of items grouped by material type"
    )

    locations_at_capacity: int = Field(
        ..., description="Number of locations at or near full capacity (e.g., >= 95%)"
    )
    locations_nearly_empty: int = Field(
        ..., description="Number of locations nearly empty (e.g., <= 10%)"
    )

    most_utilized_locations: List[LocationUtilizationInfo] = Field(  # Use sub-schema
        default_factory=list,
        description="List of most utilized locations (e.g., top 5)",
    )
    least_utilized_locations: List[LocationUtilizationInfo] = Field(  # Use sub-schema
        default_factory=list,
        description="List of least utilized locations (e.g., bottom 5, non-empty)",
    )

    recommendations: List[str] = Field(  # Changed to non-optional list
        default_factory=list, description="Storage optimization recommendations"
    )

    class Config:
        from_attributes = True  # Keep this if needed for ORM mapping


# --- Search Parameters ---
class StorageSearchParams(BaseModel):
    type: Optional[str] = None
    section: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None
    sort_by: Optional[str] = "name"
    sort_dir: Optional[str] = "asc"
