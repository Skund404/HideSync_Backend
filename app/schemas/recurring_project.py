# app/schemas/recurring_project.py
"""
Recurring Project schemas for the HideSync API.

This module contains Pydantic models for recurring project management,
including recurrence patterns, recurring projects, and generated projects.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from app.db.models.enums import ProjectType, ProjectStatus


class RecurrencePatternBase(BaseModel):
    """Base schema for recurrence pattern data."""

    name: str = Field(..., description="Pattern name")
    frequency: str = Field(
        ..., description="Frequency: daily, weekly, monthly, quarterly, yearly, custom"
    )
    interval: int = Field(1, description="Interval between occurrences", gt=0)
    start_date: date = Field(..., description="Start date for the pattern")
    end_date: Optional[date] = Field(
        None, description="End date for the pattern (if any)"
    )
    end_after_occurrences: Optional[int] = Field(
        None, description="End after n occurrences"
    )
    days_of_week: Optional[List[int]] = Field(
        None, description="Days of week (for weekly patterns)"
    )
    day_of_month: Optional[int] = Field(
        None, description="Day of month (for monthly patterns)"
    )
    week_of_month: Optional[int] = Field(
        None, description="Week of month (for monthly patterns)"
    )
    month: Optional[int] = Field(None, description="Month (for yearly patterns)")
    custom_dates: Optional[List[date]] = Field(None, description="Custom dates")
    skip_weekends: Optional[bool] = Field(False, description="Whether to skip weekends")
    skip_holidays: Optional[bool] = Field(False, description="Whether to skip holidays")


class RecurrencePatternCreate(RecurrencePatternBase):
    """Schema for creating a new recurrence pattern."""

    pass


class RecurrencePatternUpdate(BaseModel):
    """Schema for updating recurrence pattern information."""

    name: Optional[str] = Field(None, description="Pattern name")
    frequency: Optional[str] = Field(None, description="Frequency")
    interval: Optional[int] = Field(
        None, description="Interval between occurrences", gt=0
    )
    start_date: Optional[date] = Field(None, description="Start date for the pattern")
    end_date: Optional[date] = Field(None, description="End date for the pattern")
    end_after_occurrences: Optional[int] = Field(
        None, description="End after n occurrences"
    )
    days_of_week: Optional[List[int]] = Field(None, description="Days of week")
    day_of_month: Optional[int] = Field(None, description="Day of month")
    week_of_month: Optional[int] = Field(None, description="Week of month")
    month: Optional[int] = Field(None, description="Month")
    custom_dates: Optional[List[date]] = Field(None, description="Custom dates")
    skip_weekends: Optional[bool] = Field(None, description="Whether to skip weekends")
    skip_holidays: Optional[bool] = Field(None, description="Whether to skip holidays")


class RecurrencePattern(RecurrencePatternBase):
    """Schema for recurrence pattern information."""

    id: str = Field(..., description="Unique pattern ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class RecurringProjectBase(BaseModel):
    """Base schema for recurring project data."""

    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    project_type: ProjectType = Field(..., description="Type of project")
    skill_level: Optional[str] = Field(None, description="Required skill level")
    duration: Optional[int] = Field(None, description="Estimated duration in hours")
    is_active: bool = Field(True, description="Whether the recurring project is active")
    auto_generate: bool = Field(
        True, description="Whether to automatically generate projects"
    )
    advance_notice_days: Optional[int] = Field(
        None, description="Days in advance to generate projects"
    )
    project_suffix: Optional[str] = Field(
        None, description="Suffix to add to generated project names"
    )
    client_id: Optional[str] = Field(
        None, description="Client ID for generated projects"
    )
    template_id: Optional[str] = Field(None, description="Project template ID")


class RecurringProjectCreate(RecurringProjectBase):
    """Schema for creating a new recurring project."""

    recurrence_pattern: RecurrencePatternCreate = Field(
        ..., description="Recurrence pattern"
    )


class RecurringProjectUpdate(BaseModel):
    """Schema for updating recurring project information."""

    name: Optional[str] = Field(None, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    project_type: Optional[ProjectType] = Field(None, description="Type of project")
    skill_level: Optional[str] = Field(None, description="Required skill level")
    duration: Optional[int] = Field(None, description="Estimated duration in hours")
    is_active: Optional[bool] = Field(
        None, description="Whether the recurring project is active"
    )
    auto_generate: Optional[bool] = Field(
        None, description="Whether to automatically generate projects"
    )
    advance_notice_days: Optional[int] = Field(
        None, description="Days in advance to generate projects"
    )
    project_suffix: Optional[str] = Field(
        None, description="Suffix to add to generated project names"
    )
    client_id: Optional[str] = Field(
        None, description="Client ID for generated projects"
    )
    template_id: Optional[str] = Field(None, description="Project template ID")
    recurrence_pattern: Optional[RecurrencePatternUpdate] = Field(
        None, description="Recurrence pattern updates"
    )


class RecurringProject(RecurringProjectBase):
    """Schema for recurring project information."""

    id: str = Field(..., description="Unique project ID")
    recurrence_pattern_id: str = Field(..., description="Recurrence pattern ID")
    next_occurrence: Optional[date] = Field(
        None, description="Next scheduled occurrence"
    )
    last_occurrence: Optional[date] = Field(None, description="Last occurrence date")
    total_occurrences: int = Field(
        0, description="Total number of occurrences generated"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(
        None, description="User ID who created this recurring project"
    )

    class Config:
        from_attributes = True


class RecurringProjectWithDetails(RecurringProject):
    """Schema for recurring project with additional details."""

    recurrence_pattern: RecurrencePattern = Field(..., description="Recurrence pattern")
    upcoming_occurrences: List[date] = Field([], description="Upcoming occurrences")
    generated_projects: List[Dict[str, Any]] = Field(
        [], description="Generated projects"
    )

    class Config:
        from_attributes = True


class GeneratedProjectCreate(BaseModel):
    """Schema for creating a new generated project instance."""

    recurring_project_id: str = Field(..., description="Recurring project ID")
    scheduled_date: date = Field(..., description="Scheduled date")
    occurrence_number: int = Field(..., description="Occurrence number")


class GeneratedProject(BaseModel):
    """Schema for a generated project instance."""

    id: str = Field(..., description="Generated project ID")
    recurring_project_id: str = Field(..., description="Recurring project ID")
    project_id: str = Field(..., description="Created project ID")
    occurrence_number: int = Field(..., description="Occurrence number")
    scheduled_date: date = Field(..., description="Scheduled date")
    actual_generation_date: datetime = Field(
        ..., description="Actual generation timestamp"
    )
    status: str = Field(..., description="Generation status")
    notes: Optional[str] = Field(None, description="Generation notes")

    class Config:
        from_attributes = True
