# File: app/schemas/tool.py
"""
Tool schemas for the HideSync API.

This module contains Pydantic models for tool management, including tools,
maintenance, and checkouts. Uses Any for input date fields with 'before'
validators and specific types for response models using from_attributes.
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict # Import ConfigDict for Pydantic v2+
import logging

from app.db.models.enums import ToolCategory

logger = logging.getLogger(__name__)

# --- Helper functions for parsing (Keep as before) ---
def parse_date_string(value: Any, field_name: str) -> Optional[date]:
    """Attempts to parse various inputs (str, date, datetime) into a date object."""
    if value is None or value == "": return None
    if isinstance(value, date): return value
    if isinstance(value, datetime): return value.date()
    if isinstance(value, str):
        try: return date.fromisoformat(value)
        except ValueError:
            try:
                date_part = value.split('T')[0].split(' ')[0]
                return date.fromisoformat(date_part)
            except ValueError:
                 logger.warning(f"Pydantic validator failed date parse: '{value}' for '{field_name}'.")
                 raise ValueError(f"Invalid date format for {field_name}. Expected YYYY-MM-DD.")
    raise ValueError(f"Invalid type for {field_name}: {type(value)}. Expected date string or object.")

def parse_datetime_string(value: Any, field_name: str) -> Optional[datetime]:
    """Attempts to parse various inputs (str, date, datetime) into a datetime object."""
    if value is None or value == "": return None
    if isinstance(value, datetime): return value
    if isinstance(value, date): return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            base_value = value.split('.')[0]
            if 'Z' in base_value: clean_value = base_value.replace('Z', '+00:00')
            elif '+' in base_value or '-' in base_value[1:]: clean_value = base_value
            else: clean_value = base_value
            iso_compliant_value = clean_value.replace(' ', 'T')
            return datetime.fromisoformat(iso_compliant_value)
        except ValueError:
            try:
                 date_part = value.split('T')[0].split(' ')[0]
                 parsed_date = date.fromisoformat(date_part)
                 logger.warning(f"Pydantic validator parsed only date part: '{value}' for '{field_name}'.")
                 return datetime.combine(parsed_date, datetime.min.time())
            except ValueError:
                 logger.warning(f"Pydantic validator failed datetime parse: '{value}' for '{field_name}'.")
                 raise ValueError(f"Invalid datetime format for {field_name}. Expected ISO 8601 format.")
    raise ValueError(f"Invalid type for {field_name}: {type(value)}. Expected datetime string or object.")


# --- Schemas ---

class ToolSearchParams(BaseModel):
    category: Optional[str] = Field(None, description="Filter by tool category")
    status: Optional[str] = Field(None, description="Filter by tool status")
    location: Optional[str] = Field(None, description="Filter by storage location")
    search: Optional[str] = Field(None, description="Search term for name or description")
    maintenance_due: Optional[bool] = Field(None, description="Filter by maintenance due status")
    checked_out: Optional[bool] = Field(None, description="Filter by checked out status")
    supplier_id: Optional[int] = Field(None, description="Filter by supplier ID")


class SupplierSummary(BaseModel):
    id: int = Field(..., description="Supplier ID")
    name: str = Field(..., description="Supplier name")
    category: Optional[str] = Field(None, description="Supplier category")
    model_config = ConfigDict(from_attributes=True)


class ToolMaintenanceBase(BaseModel):
    # Use Any for input flexibility, validator handles conversion
    tool_id: int = Field(..., description="ID of the tool")
    tool_name: Optional[str] = Field(None, description="Name of the tool (denormalized)")
    maintenance_type: str = Field(..., description="Type of maintenance")
    date: Optional[Any] = Field(None, description="Maintenance date (YYYY-MM-DD)")
    performed_by: Optional[str] = Field(None, description="Person who performed the maintenance")
    cost: Optional[float] = Field(None, ge=0, description="Cost of maintenance")
    internal_service: Optional[bool] = Field(True, description="Whether service was done internally")
    details: Optional[str] = Field(None, description="Maintenance details")
    parts: Optional[str] = Field(None, description="Parts used in maintenance")
    condition_before: Optional[str] = Field(None, description="Tool condition before maintenance")
    condition_after: Optional[str] = Field(None, description="Tool condition after maintenance")
    status: str = Field("SCHEDULED", description="Maintenance status")
    next_date: Optional[Any] = Field(None, description="Next scheduled maintenance date (YYYY-MM-DD)")

    @field_validator("date", "next_date", mode='before')
    @classmethod
    def validate_maintenance_dates(cls, v: Any, info):
        return parse_date_string(v, info.field_name)


class ToolMaintenanceCreate(ToolMaintenanceBase):
    date: Any = Field(..., description="Maintenance date (YYYY-MM-DD)")
    @field_validator("cost")
    @classmethod
    def validate_cost_positive(cls, v):
        if v is not None and v < 0: raise ValueError("Cost cannot be negative")
        return v


class ToolMaintenanceUpdate(BaseModel):
    maintenance_type: Optional[str] = Field(None)
    date: Optional[Any] = Field(None)
    performed_by: Optional[str] = Field(None)
    cost: Optional[float] = Field(None, ge=0)
    internal_service: Optional[bool] = Field(None)
    details: Optional[str] = Field(None)
    parts: Optional[str] = Field(None)
    condition_before: Optional[str] = Field(None)
    condition_after: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    next_date: Optional[Any] = Field(None)

    @field_validator("date", "next_date", mode='before')
    @classmethod
    def validate_maintenance_update_dates(cls, v: Any, info):
        return parse_date_string(v, info.field_name)

    @field_validator("cost")
    @classmethod
    def validate_cost_update(cls, v):
        if v is not None and v < 0: raise ValueError("Cost cannot be negative")
        return v


# --- CORRECTED RESPONSE SCHEMA ---
class ToolMaintenance(ToolMaintenanceBase):
    # Response model - Inherits non-date fields from Base
    id: int = Field(..., description="Unique identifier")

    # --- FIX: Use specific types WITHOUT Field() for response ---
    date: Optional[date] # Field details inherited from Base, type overridden
    next_date: Optional[date] # Field details inherited from Base, type overridden
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    # --- END FIX ---

    model_config = ConfigDict(from_attributes=True)


class ToolCheckoutBase(BaseModel):
    # Use Any for input flexibility, validator handles conversion
    tool_id: int = Field(..., description="ID of the tool")
    tool_name: Optional[str] = Field(None, description="Name of the tool (denormalized)")
    checked_out_by: str = Field(..., description="Person checking out the tool")
    checked_out_date: Optional[Any] = Field(None, description="Date and time checked out (ISO Format)")
    due_date: Optional[Any] = Field(None, description="Date due back (YYYY-MM-DD)")
    project_id: Optional[int] = Field(None, description="ID of associated project")
    project_name: Optional[str] = Field(None, description="Name of the project (denormalized)")
    notes: Optional[str] = Field(None, description="Additional notes")
    status: str = Field("CHECKED_OUT", description="Checkout status")
    condition_before: Optional[str] = Field(None, description="Tool condition at checkout")

    @field_validator("checked_out_date", mode='before')
    @classmethod
    def validate_checked_out_date(cls, v: Any, info):
        if v is None: return None
        return parse_datetime_string(v, info.field_name)

    @field_validator("due_date", mode='before')
    @classmethod
    def validate_due_date_type(cls, v: Any, info):
        return parse_date_string(v, info.field_name)


class ToolCheckoutCreate(ToolCheckoutBase):
    checked_out_date: Any = Field(..., description="Date and time checked out (ISO Format)")
    due_date: Any = Field(..., description="Date due back (YYYY-MM-DD)")

    @field_validator("due_date")
    @classmethod
    def check_due_date_after_checkout(cls, v: Optional[date], info):
        if v is not None and info.data.get('checked_out_date') is not None:
            checkout_dt = info.data['checked_out_date']
            if isinstance(checkout_dt, datetime) and v < checkout_dt.date():
                 raise ValueError("Due date cannot be before checkout date")
        return v


class ToolCheckoutUpdate(BaseModel):
    due_date: Optional[Any] = Field(None, description="Updated due date (YYYY-MM-DD)")
    returned_date: Optional[Any] = Field(None, description="Date and time returned (ISO Format)")
    condition_after: Optional[str] = Field(None, description="Tool condition after return")
    notes: Optional[str] = Field(None, description="Updated notes")
    status: Optional[str] = Field(None, description="Updated status")
    issue_description: Optional[str] = Field(None, description="Description of any issues")

    @field_validator("due_date", mode='before')
    @classmethod
    def validate_update_due_date(cls, v: Any, info):
        return parse_date_string(v, info.field_name)

    @field_validator("returned_date", mode='before')
    @classmethod
    def validate_update_returned_date(cls, v: Any, info):
        return parse_datetime_string(v, info.field_name)


# --- CORRECTED RESPONSE SCHEMA ---
class ToolCheckout(ToolCheckoutBase):
    id: int = Field(..., description="Unique identifier")

    # --- FIX: Use specific types WITHOUT Field() for response ---
    checked_out_date: Optional[datetime]
    due_date: Optional[date]
    returned_date: Optional[datetime] = None # Still optional
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    # --- END FIX ---

    # Inherited fields like condition_after, issue_description are already Optional[str]
    is_overdue: Optional[bool] = None # Keep defaults as None or False as appropriate
    days_overdue: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ToolBase(BaseModel):
    # Use Any for input flexibility, validator handles conversion
    name: str = Field(..., min_length=3, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    category: ToolCategory = Field(..., description="Tool category")
    brand: Optional[str] = Field(None, description="Tool brand/manufacturer")
    model: Optional[str] = Field(None, description="Model number/name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    purchase_price: Optional[float] = Field(None, ge=0, description="Purchase price")
    purchase_date: Optional[Any] = Field(None, description="Purchase date (YYYY-MM-DD)")
    specifications: Optional[str] = Field(None, description="Technical specifications")
    status: str = Field("IN_STOCK", description="Current status")
    location: Optional[str] = Field(None, description="Storage location")
    image: Optional[str] = Field(None, description="Image URL/path")
    maintenance_interval: Optional[int] = Field(None, gt=0, description="Maintenance interval in days")
    supplier: Optional[str] = Field(None, description="Supplier name (denormalized)")
    supplier_id: Optional[int] = Field(None, description="Supplier ID")

    @field_validator("purchase_date", mode='before')
    @classmethod
    def validate_base_purchase_date(cls, v: Any, info):
        return parse_date_string(v, info.field_name)

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str):
        if len(v.strip()) < 3: raise ValueError("Tool name must be at least 3 characters")
        return v.strip()


class ToolCreate(ToolBase):
    name: str = Field(..., min_length=3, description="Tool name")
    category: ToolCategory = Field(..., description="Tool category")
    location: str = Field(..., description="Storage location")
    status: str = Field("IN_STOCK", description="Current status")
    next_maintenance: Optional[Any] = Field(None, description="Next maintenance date (YYYY-MM-DD)")

    @field_validator("next_maintenance", mode='before')
    @classmethod
    def validate_create_next_maintenance(cls, v: Any, info):
        return parse_date_string(v, info.field_name)


class ToolUpdate(BaseModel):
    # Use Any for input flexibility, validator handles conversion
    name: Optional[str] = Field(None, min_length=3, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    category: Optional[ToolCategory] = Field(None, description="Tool category")
    brand: Optional[str] = Field(None, description="Tool brand/manufacturer")
    model: Optional[str] = Field(None, description="Model number/name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    purchase_price: Optional[float] = Field(None, ge=0, description="Purchase price")
    purchase_date: Optional[Any] = Field(None, description="Purchase date (YYYY-MM-DD)")
    specifications: Optional[str] = Field(None, description="Technical specifications")
    status: Optional[str] = Field(None, description="Current status")
    location: Optional[str] = Field(None, description="Storage location")
    image: Optional[str] = Field(None, description="Image URL/path")
    last_maintenance: Optional[Any] = Field(None, description="Last maintenance date (YYYY-MM-DD)")
    next_maintenance: Optional[Any] = Field(None, description="Next maintenance date (YYYY-MM-DD)")
    maintenance_interval: Optional[int] = Field(None, gt=0, description="Maintenance interval in days")
    supplier: Optional[str] = Field(None, description="Supplier name")
    supplier_id: Optional[int] = Field(None, description="Supplier ID")
    status_change_reason: Optional[str] = Field(None, description="Reason for status change")

    @field_validator("purchase_date", "last_maintenance", "next_maintenance", mode='before')
    @classmethod
    def validate_update_dates(cls, v: Any, info):
        return parse_date_string(v, info.field_name)

    @field_validator("purchase_price")
    @classmethod
    def validate_price(cls, v):
        if v is not None and v < 0: raise ValueError("Purchase price cannot be negative")
        return v

    @field_validator("maintenance_interval")
    @classmethod
    def validate_maintenance_interval(cls, v):
        if v is not None and v <= 0: raise ValueError("Maintenance interval must be positive")
        return v

    @field_validator("name")
    @classmethod
    def validate_update_name(cls, v):
        if v is not None:
            if len(v.strip()) < 3: raise ValueError("Tool name must be at least 3 characters")
            return v.strip()
        return v


# --- CORRECTED RESPONSE SCHEMA ---
class Tool(ToolBase):
    id: int = Field(..., description="Unique identifier")

    # --- FIX: Use specific types WITHOUT Field() for response ---
    purchase_date: Optional[date]
    last_maintenance: Optional[date]
    next_maintenance: Optional[date]
    checked_out_date: Optional[datetime]
    due_date: Optional[date]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    # --- END FIX ---

    # Other fields inherited or explicitly defined
    checked_out_to: Optional[str] = None # Explicitly None default

    is_checked_out: Optional[bool] = False # Explicitly False default
    maintenance_due: Optional[bool] = False # Explicitly False default
    days_since_purchase: Optional[int] = None # Explicitly None default
    supplier_rel: Optional[SupplierSummary] = None # Explicitly None default

    model_config = ConfigDict(from_attributes=True)


class ToolWithHistory(Tool):
    maintenance_history: List[ToolMaintenance] = Field([], description="Maintenance history")
    checkout_history: List[ToolCheckout] = Field([], description="Checkout history")
    model_config = ConfigDict(from_attributes=True)


class MaintenanceScheduleItem(BaseModel):
    tool_id: int = Field(..., description="Tool ID")
    tool_name: str = Field(..., description="Tool name")
    maintenance_type: str = Field(..., description="Maintenance type")
    scheduled_date: date = Field(..., description="Scheduled date")
    category: ToolCategory = Field(..., description="Tool category")
    status: str = Field(..., description="Maintenance status (e.g., SCHEDULED)")
    location: Optional[str] = Field(None, description="Tool location")
    is_overdue: bool = Field(False, description="Whether maintenance is overdue")
    days_until_due: Optional[int] = Field(None, description="Days until maintenance is due")
    model_config = ConfigDict(from_attributes=True)


class MaintenanceSchedule(BaseModel):
    schedule: List[MaintenanceScheduleItem] = Field(..., description="Maintenance schedule items")
    total_items: int = Field(..., description="Total number of scheduled maintenance items")
    overdue_items: int = Field(..., description="Number of overdue maintenance items")
    upcoming_items: int = Field(..., description="Number of upcoming maintenance items")
    start_date: date = Field(..., description="Start date of the schedule")
    end_date: date = Field(..., description="End date of the schedule")
    model_config = ConfigDict(from_attributes=True)