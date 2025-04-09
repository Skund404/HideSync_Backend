# File: app/schemas/tool.py
"""
Tool schemas for the HideSync API.

This module contains Pydantic models for tool management, including tools,
maintenance, and checkouts. Date/time fields align with database types.
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator

from app.db.models.enums import ToolCategory


class ToolSearchParams(BaseModel):
    category: Optional[str] = Field(None, description="Filter by tool category")
    status: Optional[str] = Field(None, description="Filter by tool status")
    location: Optional[str] = Field(None, description="Filter by storage location")
    search: Optional[str] = Field(None, description="Search term for name or description")
    maintenance_due: Optional[bool] = Field(None, description="Filter by maintenance due status")
    checked_out: Optional[bool] = Field(None, description="Filter by checked out status")
    supplier_id: Optional[int] = Field(None, description="Filter by supplier ID")


class SupplierSummary(BaseModel):
    """
    Summary schema for supplier information when related to a tool.
    """
    id: int = Field(..., description="Supplier ID")
    name: str = Field(..., description="Supplier name")
    category: Optional[str] = Field(None, description="Supplier category")

    class Config:
        from_attributes = True


class ToolMaintenanceBase(BaseModel):
    tool_id: int = Field(..., description="ID of the tool")
    tool_name: Optional[str] = Field(None, description="Name of the tool (denormalized)")
    maintenance_type: str = Field(..., description="Type of maintenance")

    # Keep the type as Any but use Field() with description
    date: Any = Field(None, description="Maintenance date")

    performed_by: Optional[str] = Field(None, description="Person who performed the maintenance")
    cost: Optional[float] = Field(None, ge=0, description="Cost of maintenance")
    internal_service: Optional[bool] = Field(True, description="Whether service was done internally")
    details: Optional[str] = Field(None, description="Maintenance details")
    parts: Optional[str] = Field(None, description="Parts used in maintenance")
    condition_before: Optional[str] = Field(None, description="Tool condition before maintenance")
    condition_after: Optional[str] = Field(None, description="Tool condition after maintenance")
    status: str = Field("SCHEDULED", description="Maintenance status")

    # Keep the type as Any but add description
    next_date: Any = Field(None, description="Next scheduled maintenance date")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Date must be a valid date type")
        return v

    @field_validator("next_date")
    @classmethod
    def validate_next_date(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Next date must be a valid date type")
        return v


class ToolMaintenanceCreate(ToolMaintenanceBase):
    # Require date for creation
    date: Any = Field(..., description="Maintenance date")

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v):
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v


class ToolMaintenanceUpdate(BaseModel):
    maintenance_type: Optional[str] = Field(None, description="Type of maintenance")
    date: Any = Field(None, description="Maintenance date")
    performed_by: Optional[str] = Field(None, description="Person who performed the maintenance")
    cost: Optional[float] = Field(None, ge=0, description="Cost of maintenance")
    internal_service: Optional[bool] = Field(None, description="Whether service was done internally")
    details: Optional[str] = Field(None, description="Maintenance details")
    parts: Optional[str] = Field(None, description="Parts used in maintenance")
    condition_before: Optional[str] = Field(None, description="Tool condition before maintenance")
    condition_after: Optional[str] = Field(None, description="Tool condition after maintenance")
    status: Optional[str] = Field(None, description="Maintenance status")
    next_date: Any = Field(None, description="Next scheduled maintenance date")

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v):
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Date must be a valid date type")
        return v

    @field_validator("next_date")
    @classmethod
    def validate_next_date(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Next date must be a valid date type")
        return v


class ToolMaintenance(ToolMaintenanceBase):
    id: int = Field(..., description="Unique identifier")
    created_at: Any = Field(None, description="Creation timestamp")
    updated_at: Any = Field(None, description="Last update timestamp")

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, v, info):
        if v is not None and not isinstance(v, datetime):
            raise ValueError(f"{info.field_name} must be a valid datetime")
        return v

    class Config:
        from_attributes = True


class ToolCheckoutBase(BaseModel):
    tool_id: int = Field(..., description="ID of the tool")
    tool_name: Optional[str] = Field(None, description="Name of the tool (denormalized)")
    checked_out_by: str = Field(..., description="Person checking out the tool")
    checked_out_date: Any = Field(..., description="Date and time when the tool was checked out")
    due_date: Any = Field(..., description="Date when the tool is due to be returned")
    project_id: Optional[int] = Field(None, description="ID of associated project")
    project_name: Optional[str] = Field(None, description="Name of the project (denormalized)")
    notes: Optional[str] = Field(None, description="Additional notes")
    status: str = Field("CHECKED_OUT", description="Checkout status")
    condition_before: Optional[str] = Field(None, description="Tool condition at checkout")

    @field_validator("checked_out_date")
    @classmethod
    def validate_checked_out_date(cls, v):
        if not isinstance(v, datetime):
            raise ValueError("Checked out date must be a valid datetime")
        return v

    @field_validator("due_date")
    @classmethod
    def validate_due_date_type(cls, v):
        if not isinstance(v, date):
            raise ValueError("Due date must be a valid date")
        return v


class ToolCheckoutCreate(ToolCheckoutBase):
    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v, info):
        values = info.data
        if "checked_out_date" in values and isinstance(values["checked_out_date"], datetime):
            checkout_dt = values["checked_out_date"]
            if isinstance(v, date) and v < checkout_dt.date():
                raise ValueError("Due date cannot be before checkout date")
        return v


class ToolCheckoutUpdate(BaseModel):
    due_date: Any = Field(None, description="Updated due date")
    returned_date: Any = Field(None, description="Date and time when the tool was returned")
    condition_after: Optional[str] = Field(None, description="Tool condition after return")
    notes: Optional[str] = Field(None, description="Updated notes")
    status: Optional[str] = Field(None, description="Updated status")
    issue_description: Optional[str] = Field(None, description="Description of any issues")

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Due date must be a valid date")
        return v

    @field_validator("returned_date")
    @classmethod
    def validate_returned_date(cls, v):
        if v is not None and not isinstance(v, datetime):
            raise ValueError("Returned date must be a valid datetime")
        return v


class ToolCheckout(ToolCheckoutBase):
    id: int = Field(..., description="Unique identifier")
    returned_date: Any = Field(None, description="Date and time when the tool was returned")
    condition_after: Optional[str] = Field(None, description="Tool condition after return")
    issue_description: Optional[str] = Field(None, description="Description of any issues")
    created_at: Any = Field(None, description="Creation timestamp")
    updated_at: Any = Field(None, description="Last update timestamp")

    # Add hybrid properties from the model
    is_overdue: Optional[bool] = Field(None, description="Whether the checkout is overdue")
    days_overdue: Optional[int] = Field(None, description="Number of days overdue")

    @field_validator("returned_date", "created_at", "updated_at")
    @classmethod
    def validate_datetimes(cls, v, info):
        if v is not None and not isinstance(v, datetime):
            raise ValueError(f"{info.field_name} must be a valid datetime")
        return v

    class Config:
        from_attributes = True


class ToolBase(BaseModel):
    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    category: ToolCategory = Field(..., description="Tool category")
    brand: Optional[str] = Field(None, description="Tool brand/manufacturer")
    model: Optional[str] = Field(None, description="Model number/name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    purchase_price: Optional[float] = Field(None, ge=0, description="Purchase price")
    purchase_date: Any = Field(None, description="Purchase date")
    specifications: Optional[str] = Field(None, description="Technical specifications")
    status: str = Field("IN_STOCK", description="Current status")
    location: Optional[str] = Field(None, description="Storage location")
    image: Optional[str] = Field(None, description="Image URL/path")
    maintenance_interval: Optional[int] = Field(None, gt=0, description="Maintenance interval in days")
    supplier: Optional[str] = Field(None, description="Supplier name (denormalized)")
    supplier_id: Optional[int] = Field(None, description="Supplier ID")

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Purchase date must be a valid date")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError("Tool name must be at least 3 characters")
        return v.strip()


class ToolCreate(ToolBase):
    next_maintenance: Any = Field(None, description="Next maintenance date")
    name: str = Field(..., description="Tool name")
    category: ToolCategory = Field(..., description="Tool category")
    status: str = Field("IN_STOCK", description="Current status")
    location: str = Field(..., description="Storage location")

    @field_validator("next_maintenance")
    @classmethod
    def validate_next_maintenance(cls, v):
        if v is not None and not isinstance(v, date):
            raise ValueError("Next maintenance date must be a valid date")
        return v


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    category: Optional[ToolCategory] = Field(None, description="Tool category")
    brand: Optional[str] = Field(None, description="Tool brand/manufacturer")
    model: Optional[str] = Field(None, description="Model number/name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    purchase_price: Optional[float] = Field(None, ge=0, description="Purchase price")
    purchase_date: Any = Field(None, description="Purchase date")
    specifications: Optional[str] = Field(None, description="Technical specifications")
    status: Optional[str] = Field(None, description="Current status")
    location: Optional[str] = Field(None, description="Storage location")
    image: Optional[str] = Field(None, description="Image URL/path")
    last_maintenance: Any = Field(None, description="Last maintenance date")
    next_maintenance: Any = Field(None, description="Next maintenance date")
    maintenance_interval: Optional[int] = Field(None, gt=0, description="Maintenance interval in days")
    supplier: Optional[str] = Field(None, description="Supplier name")
    supplier_id: Optional[int] = Field(None, description="Supplier ID")

    @field_validator("purchase_price")
    @classmethod
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("Purchase price cannot be negative")
        return v

    @field_validator("maintenance_interval")
    @classmethod
    def validate_maintenance_interval(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Maintenance interval must be positive")
        return v

    @field_validator("purchase_date", "last_maintenance", "next_maintenance")
    @classmethod
    def validate_dates(cls, v, info):
        field_name = info.field_name
        if v is not None and not isinstance(v, date):
            raise ValueError(f"{field_name} must be a valid date")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and (not v or len(v.strip()) < 3):
            raise ValueError("Tool name must be at least 3 characters")
        return v.strip() if v is not None else v


class Tool(ToolBase):
    id: int = Field(..., description="Unique identifier")
    last_maintenance: Any = Field(None, description="Last maintenance date")
    next_maintenance: Any = Field(None, description="Next maintenance date")
    checked_out_to: Optional[str] = Field(None, description="Person who has the tool checked out")
    checked_out_date: Any = Field(None, description="Date and time when the tool was checked out")
    due_date: Any = Field(None, description="Date when the tool is due to be returned")
    created_at: Any = Field(None, description="Creation timestamp")
    updated_at: Any = Field(None, description="Last update timestamp")

    # Add hybrid properties from the model
    is_checked_out: bool = Field(False, description="Whether the tool is currently checked out")
    maintenance_due: bool = Field(False, description="Whether maintenance is due")
    days_since_purchase: Optional[int] = Field(None, description="Days since purchase")

    # Add relationship to supplier
    supplier_rel: Optional[SupplierSummary] = Field(None, description="Related supplier")

    @field_validator("last_maintenance", "next_maintenance")
    @classmethod
    def validate_dates(cls, v, info):
        field_name = info.field_name
        if v is not None and not isinstance(v, date):
            raise ValueError(f"{field_name} must be a valid date")
        return v

    @field_validator("checked_out_date", "created_at", "updated_at")
    @classmethod
    def validate_datetimes(cls, v, info):
        field_name = info.field_name
        if v is not None and not isinstance(v, datetime):
            raise ValueError(f"{field_name} must be a valid datetime")
        return v

    class Config:
        from_attributes = True


class ToolWithHistory(Tool):
    maintenance_history: List["ToolMaintenance"] = Field([], description="Maintenance history")
    checkout_history: List["ToolCheckout"] = Field([], description="Checkout history")

    class Config:
        from_attributes = True


class MaintenanceScheduleItem(BaseModel):
    tool_id: int = Field(..., description="Tool ID")
    tool_name: str = Field(..., description="Tool name")
    maintenance_type: str = Field(..., description="Maintenance type")
    scheduled_date: Any = Field(..., description="Scheduled date")
    category: ToolCategory = Field(..., description="Tool category")
    status: str = Field(..., description="Maintenance status (e.g., SCHEDULED)")
    location: Optional[str] = Field(None, description="Tool location")
    is_overdue: bool = Field(False, description="Whether maintenance is overdue")
    days_until_due: Optional[int] = Field(None, description="Days until maintenance is due")

    @field_validator("scheduled_date")
    @classmethod
    def validate_scheduled_date(cls, v):
        if not isinstance(v, date):
            raise ValueError("Scheduled date must be a valid date")
        return v


class MaintenanceSchedule(BaseModel):
    schedule: List[MaintenanceScheduleItem] = Field(..., description="Maintenance schedule items")
    total_items: int = Field(..., description="Total number of scheduled maintenance items")
    overdue_items: int = Field(..., description="Number of overdue maintenance items")
    upcoming_items: int = Field(..., description="Number of upcoming maintenance items")
    start_date: Any = Field(..., description="Start date of the schedule")
    end_date: Any = Field(..., description="End date of the schedule")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v, info):
        field_name = info.field_name
        if not isinstance(v, date):
            raise ValueError(f"{field_name} must be a valid date")
        return v