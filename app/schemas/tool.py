# File: app/schemas/tool.py
"""
Tool schemas for the HideSync API.

This module contains Pydantic models for tool management, including tools,
maintenance, and checkouts.
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator

from app.db.models.enums import ToolCategory


class ToolSearchParams(BaseModel):
    """
    Search parameters for filtering tool records.
    """
    category: Optional[str] = Field(None, description="Filter by tool category")
    status: Optional[str] = Field(None, description="Filter by tool status")
    location: Optional[str] = Field(None, description="Filter by storage location")
    search: Optional[str] = Field(None, description="Search term for name or description")
    maintenance_due: Optional[bool] = Field(None, description="Filter by maintenance due status")
    checked_out: Optional[bool] = Field(None, description="Filter by checked out status")
    supplier_id: Optional[int] = Field(None, description="Filter by supplier ID")


class ToolMaintenanceBase(BaseModel):
    """
    Base schema for tool maintenance data.
    """
    tool_id: int = Field(..., description="ID of the tool")
    tool_name: Optional[str] = Field(None, description="Name of the tool")
    maintenance_type: str = Field(..., description="Type of maintenance")
    date: str = Field(..., description="Date of maintenance")
    performed_by: Optional[str] = Field(None, description="Person who performed the maintenance")
    cost: Optional[float] = Field(None, description="Cost of maintenance", ge=0)
    internal_service: Optional[bool] = Field(True, description="Whether service was done internally")
    details: Optional[str] = Field(None, description="Maintenance details")
    parts: Optional[str] = Field(None, description="Parts used in maintenance")
    condition_before: Optional[str] = Field(None, description="Tool condition before maintenance")
    condition_after: Optional[str] = Field(None, description="Tool condition after maintenance")
    status: Optional[str] = Field(None, description="Maintenance status")
    next_date: Optional[str] = Field(None, description="Next scheduled maintenance date")


class ToolMaintenanceCreate(ToolMaintenanceBase):
    """
    Schema for creating a new tool maintenance record.
    """

    @validator('cost')
    def validate_cost(cls, v):
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v


class ToolMaintenanceUpdate(BaseModel):
    """
    Schema for updating a tool maintenance record.
    """
    maintenance_type: Optional[str] = Field(None, description="Type of maintenance")
    date: Optional[str] = Field(None, description="Date of maintenance")
    performed_by: Optional[str] = Field(None, description="Person who performed the maintenance")
    cost: Optional[float] = Field(None, description="Cost of maintenance", ge=0)
    internal_service: Optional[bool] = Field(None, description="Whether service was done internally")
    details: Optional[str] = Field(None, description="Maintenance details")
    parts: Optional[str] = Field(None, description="Parts used in maintenance")
    condition_before: Optional[str] = Field(None, description="Tool condition before maintenance")
    condition_after: Optional[str] = Field(None, description="Tool condition after maintenance")
    status: Optional[str] = Field(None, description="Maintenance status")
    next_date: Optional[str] = Field(None, description="Next scheduled maintenance date")

    @validator('cost')
    def validate_cost(cls, v):
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v


class ToolMaintenance(ToolMaintenanceBase):
    """
    Schema for tool maintenance record as stored in the database.
    """
    id: int = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True

class ToolCheckoutBase(BaseModel):
    """
    Base schema for tool checkout data.
    """
    tool_id: int = Field(..., description="ID of the tool")
    tool_name: Optional[str] = Field(None, description="Name of the tool")
    checked_out_by: str = Field(..., description="Person checking out the tool")
    checked_out_date: str = Field(..., description="Date when the tool was checked out")
    due_date: str = Field(..., description="Date when the tool is due to be returned")
    project_id: Optional[int] = Field(None, description="ID of associated project")
    project_name: Optional[str] = Field(None, description="Name of the project")
    notes: Optional[str] = Field(None, description="Additional notes")
    status: Optional[str] = Field("CHECKED_OUT", description="Checkout status")
    condition_before: Optional[str] = Field(None, description="Tool condition at checkout")


class ToolCheckoutCreate(ToolCheckoutBase):
    """
    Schema for creating a new tool checkout.
    """

    @validator('due_date')
    def validate_due_date(cls, v, values):
        # Simple validation - we might want to add more complex date validation
        if v and 'checked_out_date' in values and v < values['checked_out_date']:
            raise ValueError("Due date cannot be before checkout date")
        return v


class ToolCheckoutUpdate(BaseModel):
    """
    Schema for updating a tool checkout.
    """
    due_date: Optional[str] = Field(None, description="Updated due date")
    returned_date: Optional[str] = Field(None, description="Date when the tool was returned")
    condition_after: Optional[str] = Field(None, description="Tool condition after return")
    notes: Optional[str] = Field(None, description="Updated notes")
    status: Optional[str] = Field(None, description="Updated status")
    issue_description: Optional[str] = Field(None, description="Description of any issues")


class ToolCheckout(ToolCheckoutBase):
    """
    Schema for tool checkout as stored in the database.
    """
    id: int = Field(..., description="Unique identifier")
    returned_date: Optional[str] = Field(None, description="Date when the tool was returned")
    condition_after: Optional[str] = Field(None, description="Tool condition after return")
    issue_description: Optional[str] = Field(None, description="Description of any issues")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class ToolBase(BaseModel):
    """
    Base schema for tool data.
    """
    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    category: ToolCategory = Field(..., description="Tool category")
    brand: Optional[str] = Field(None, description="Tool brand/manufacturer")
    model: Optional[str] = Field(None, description="Model number/name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    purchase_price: Optional[float] = Field(None, description="Purchase price", ge=0)
    purchase_date: Optional[str] = Field(None, description="Purchase date")
    specifications: Optional[str] = Field(None, description="Technical specifications")
    status: Optional[str] = Field("IN_STOCK", description="Current status")
    location: Optional[str] = Field(None, description="Storage location")
    image: Optional[str] = Field(None, description="Image URL/path")
    maintenance_interval: Optional[int] = Field(None, description="Maintenance interval in days")
    supplier: Optional[str] = Field(None, description="Supplier name")
    supplier_id: Optional[int] = Field(None, description="Supplier ID")


class ToolCreate(ToolBase):
    """
    Schema for creating a new tool.
    """
    next_maintenance: Optional[str] = Field(None, description="Next maintenance date")

    @validator('purchase_price')
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("Purchase price cannot be negative")
        return v

    @validator('maintenance_interval')
    def validate_maintenance_interval(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Maintenance interval must be positive")
        return v


class ToolUpdate(BaseModel):
    """
    Schema for updating tool information.
    """
    name: Optional[str] = Field(None, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    category: Optional[ToolCategory] = Field(None, description="Tool category")
    brand: Optional[str] = Field(None, description="Tool brand/manufacturer")
    model: Optional[str] = Field(None, description="Model number/name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    purchase_price: Optional[float] = Field(None, description="Purchase price", ge=0)
    purchase_date: Optional[str] = Field(None, description="Purchase date")
    specifications: Optional[str] = Field(None, description="Technical specifications")
    status: Optional[str] = Field(None, description="Current status")
    location: Optional[str] = Field(None, description="Storage location")
    image: Optional[str] = Field(None, description="Image URL/path")
    last_maintenance: Optional[str] = Field(None, description="Last maintenance date")
    next_maintenance: Optional[str] = Field(None, description="Next maintenance date")
    maintenance_interval: Optional[int] = Field(None, description="Maintenance interval in days")
    supplier: Optional[str] = Field(None, description="Supplier name")
    supplier_id: Optional[int] = Field(None, description="Supplier ID")

    @validator('purchase_price')
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("Purchase price cannot be negative")
        return v

    @validator('maintenance_interval')
    def validate_maintenance_interval(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Maintenance interval must be positive")
        return v


class Tool(ToolBase):
    """
    Schema for tool information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier")
    last_maintenance: Optional[str] = Field(None, description="Last maintenance date")
    next_maintenance: Optional[str] = Field(None, description="Next maintenance date")
    checked_out_to: Optional[str] = Field(None, description="Person who has the tool checked out")
    checked_out_date: Optional[str] = Field(None, description="Date when the tool was checked out")
    due_date: Optional[str] = Field(None, description="Date when the tool is due to be returned")

    class Config:
        from_attributes = True


class ToolWithHistory(Tool):
    """
    Schema for tool information with maintenance and checkout history.
    """
    maintenance_history: List[ToolMaintenance] = Field([], description="Maintenance history")
    checkout_history: List[ToolCheckout] = Field([], description="Checkout history")

    class Config:
        from_attributes = True


class MaintenanceScheduleItem(BaseModel):
    """
    Schema for a maintenance schedule item.
    """
    tool_id: int = Field(..., description="Tool ID")
    tool_name: str = Field(..., description="Tool name")
    maintenance_type: str = Field(..., description="Maintenance type")
    scheduled_date: str = Field(..., description="Scheduled date")
    category: ToolCategory = Field(..., description="Tool category")
    status: str = Field(..., description="Maintenance status")
    location: Optional[str] = Field(None, description="Tool location")
    is_overdue: bool = Field(False, description="Whether maintenance is overdue")
    days_until_due: Optional[int] = Field(None, description="Days until maintenance is due")


class MaintenanceSchedule(BaseModel):
    """
    Schema for maintenance schedule report.
    """
    schedule: List[MaintenanceScheduleItem] = Field(..., description="Maintenance schedule items")
    total_items: int = Field(..., description="Total number of scheduled maintenance items")
    overdue_items: int = Field(..., description="Number of overdue maintenance items")
    upcoming_items: int = Field(..., description="Number of upcoming maintenance items")
    start_date: str = Field(..., description="Start date of the schedule")
    end_date: str = Field(..., description="End date of the schedule")