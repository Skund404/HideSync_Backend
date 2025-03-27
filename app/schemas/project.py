# File: app/schemas/project.py
"""
Project schemas for the HideSync API.

This module contains Pydantic models for project management, including projects,
project components, project templates, and timeline tasks.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator, root_validator

from app.db.models.enums import ProjectType, ProjectStatus, ComponentType


# Existing schemas can remain the same
class TimelineTaskBase(BaseModel):
    """Base schema for timeline task data."""

    name: str = Field(..., description="Name of the task")
    start_date: datetime = Field(..., description="Start date and time for the task")
    end_date: datetime = Field(..., description="End date and time for the task")
    progress: Optional[int] = Field(
        0, description="Percentage of completion (0-100)", ge=0, le=100
    )
    status: Optional[str] = Field(None, description="Status of the task")
    dependencies: Optional[List[str]] = Field(
        None, description="IDs of tasks this task depends on"
    )
    is_critical_path: Optional[bool] = Field(
        False, description="Whether this task is on the critical path"
    )


# Project Template Schemas
class ProjectTemplateComponentBase(BaseModel):
    """
    Base schema for project template component data.
    """

    component_id: int = Field(..., description="ID of the component")
    quantity: int = Field(..., description="Quantity of this component needed", gt=0)


class ProjectTemplateComponentCreate(ProjectTemplateComponentBase):
    """
    Schema for adding a component to a project template.
    """

    pass


class ProjectTemplateComponentInDB(ProjectTemplateComponentBase):
    """
    Schema for project template component information as stored in the database.
    """

    id: int = Field(
        ..., description="Unique identifier for the template component relation"
    )
    template_id: int = Field(..., description="ID of the template")

    class Config:
        from_attributes = True


class ProjectTemplateComponentResponse(ProjectTemplateComponentInDB):
    """
    Schema for project template component responses in the API.
    """

    component_name: Optional[str] = Field(None, description="Name of the component")
    component_type: Optional[ComponentType] = Field(
        None, description="Type of the component"
    )

    class Config:
        from_attributes = True


class ProjectTemplateBase(BaseModel):
    """
    Base schema for project template data.
    """

    name: str = Field(
        ..., description="Name of the template", min_length=1, max_length=100
    )
    description: Optional[str] = Field(
        None, description="Detailed description of the template"
    )
    project_type: ProjectType = Field(
        ..., description="Type of projects this template is for"
    )
    skill_level: Optional[str] = Field(
        None, description="Required skill level for this project"
    )
    estimated_duration: Optional[int] = Field(
        None, description="Estimated duration in hours", gt=0
    )
    estimated_cost: Optional[float] = Field(
        None, description="Estimated cost of materials", ge=0
    )
    version: Optional[str] = Field(None, description="Version of this template")
    is_public: Optional[bool] = Field(
        False, description="Whether this template is publicly available"
    )
    tags: Optional[List[str]] = Field(
        None, description="Tags for categorizing the template"
    )
    notes: Optional[str] = Field(None, description="Additional template notes")


class ProjectTemplateCreate(ProjectTemplateBase):
    """
    Schema for creating a new project template.
    """

    components: Optional[List[ProjectTemplateComponentCreate]] = Field(
        None, description="Components for this template"
    )


class ProjectTemplateUpdate(BaseModel):
    """
    Schema for updating project template information.
    """

    name: Optional[str] = Field(
        None, description="Name of the template", min_length=1, max_length=100
    )
    description: Optional[str] = Field(
        None, description="Detailed description of the template"
    )
    project_type: Optional[ProjectType] = Field(
        None, description="Type of projects this template is for"
    )
    skill_level: Optional[str] = Field(
        None, description="Required skill level for this project"
    )
    estimated_duration: Optional[int] = Field(
        None, description="Estimated duration in hours", gt=0
    )
    estimated_cost: Optional[float] = Field(
        None, description="Estimated cost of materials", ge=0
    )
    version: Optional[str] = Field(None, description="Version of this template")
    is_public: Optional[bool] = Field(
        None, description="Whether this template is publicly available"
    )
    tags: Optional[List[str]] = Field(
        None, description="Tags for categorizing the template"
    )
    notes: Optional[str] = Field(None, description="Additional template notes")
    components: Optional[List[ProjectTemplateComponentCreate]] = Field(
        None, description="Components for this template"
    )


class ProjectTemplateInDB(ProjectTemplateBase):
    """
    Schema for project template information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the template")
    created_at: datetime = Field(
        ..., description="Timestamp when the template was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the template was last updated"
    )

    class Config:
        from_attributes = True


class ProjectTemplateResponse(ProjectTemplateInDB):
    """
    Schema for project template responses in the API.
    """

    components: List[ProjectTemplateComponentResponse] = Field(
        ..., description="Components included in the template"
    )
    usage_count: Optional[int] = Field(
        None, description="Number of projects created from this template"
    )

    class Config:
        from_attributes = True


class ProjectTemplateList(BaseModel):
    """
    Schema for paginated project template list responses.
    """

    items: List[ProjectTemplateResponse]
    total: int = Field(..., description="Total number of templates matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")
