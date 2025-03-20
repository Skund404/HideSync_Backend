# File: app/schemas/project.py
"""
Project schemas for the HideSync API.

This module contains Pydantic models for project management, including projects,
project components, and timeline tasks.
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, root_validator

from app.db.models.enums import ProjectType, ProjectStatus, ComponentType


class TimelineTaskBase(BaseModel):
    """
    Base schema for timeline task data.
    """
    name: str = Field(..., description="Name of the task")
    start_date: datetime = Field(..., description="Start date and time for the task")
    end_date: datetime = Field(..., description="End date and time for the task")
    progress: Optional[int] = Field(0, description="Percentage of completion (0-100)", ge=0, le=100)
    status: Optional[str] = Field(None, description="Status of the task")
    dependencies: Optional[List[str]] = Field(None, description="IDs of tasks this task depends on")
    is_critical_path: Optional[bool] = Field(False, description="Whether this task is on the critical path")


class TimelineTaskCreate(TimelineTaskBase):
    """
    Schema for creating a new timeline task.
    """
    project_id: str = Field(..., description="ID of the project this task belongs to")

    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v


class TimelineTaskUpdate(BaseModel):
    """
    Schema for updating timeline task information.
    """
    name: Optional[str] = Field(None, description="Name of the task")
    start_date: Optional[datetime] = Field(None, description="Start date and time for the task")
    end_date: Optional[datetime] = Field(None, description="End date and time for the task")
    progress: Optional[int] = Field(None, description="Percentage of completion (0-100)", ge=0, le=100)
    status: Optional[str] = Field(None, description="Status of the task")
    dependencies: Optional[List[str]] = Field(None, description="IDs of tasks this task depends on")
    is_critical_path: Optional[bool] = Field(None, description="Whether this task is on the critical path")

    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v


class TimelineTaskInDB(TimelineTaskBase):
    """
    Schema for timeline task information as stored in the database.
    """
    id: str = Field(..., description="Unique identifier for the task")
    project_id: str = Field(..., description="ID of the project this task belongs to")
    created_at: datetime = Field(..., description="Timestamp when the task was created")
    updated_at: datetime = Field(..., description="Timestamp when the task was last updated")

    class Config:
        orm_mode = True


class TimelineTaskResponse(TimelineTaskInDB):
    """
    Schema for timeline task responses in the API.
    """
    days_remaining: Optional[int] = Field(None, description="Days remaining until the task is due")
    is_overdue: Optional[bool] = Field(None, description="Whether the task is overdue")

    class Config:
        orm_mode = True


class ProjectComponentBase(BaseModel):
    """
    Base schema for project component data.
    """
    component_id: int = Field(..., description="ID of the component")
    quantity: int = Field(..., description="Quantity of this component needed", gt=0)


class ProjectComponentCreate(ProjectComponentBase):
    """
    Schema for adding a component to a project.
    """
    pass


class ProjectComponentUpdate(BaseModel):
    """
    Schema for updating a project component.
    """
    quantity: Optional[int] = Field(None, description="Quantity of this component needed", gt=0)


class ProjectComponentInDB(ProjectComponentBase):
    """
    Schema for project component information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the project component relation")
    project_id: int = Field(..., description="ID of the project")

    class Config:
        orm_mode = True


class ProjectComponentResponse(ProjectComponentInDB):
    """
    Schema for project component responses in the API.
    """
    component_name: Optional[str] = Field(None, description="Name of the component")
    component_type: Optional[ComponentType] = Field(None, description="Type of the component")

    class Config:
        orm_mode = True


class ProjectBase(BaseModel):
    """
    Base schema for project data.
    """
    name: str = Field(..., description="Name of the project", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Detailed description of the project")
    type: ProjectType = Field(..., description="Type of the project")
    status: ProjectStatus = Field(ProjectStatus.CONCEPT, description="Current status of the project")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    due_date: Optional[datetime] = Field(None, description="Project due date")
    progress: Optional[float] = Field(0, description="Progress percentage", ge=0, le=100)
    completion_percentage: Optional[int] = Field(0, description="Completion percentage", ge=0, le=100)
    sale_id: Optional[int] = Field(None, description="ID of the associated sale if applicable")
    template_id: Optional[int] = Field(None, description="ID of the project template if used")
    customer: Optional[str] = Field(None, description="Customer name if not linked to a sale")
    notes: Optional[str] = Field(None, description="Additional project notes")


class ProjectCreate(ProjectBase):
    """
    Schema for creating a new project.
    """
    components: Optional[List[ProjectComponentCreate]] = Field(None, description="Components to include in the project")
    timeline_tasks: Optional[List[TimelineTaskCreate]] = Field(None, description="Timeline tasks for the project")

    @validator('due_date')
    def due_date_after_start_date(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None and v < values['start_date']:
            raise ValueError('Due date must be after start date')
        return v


class ProjectUpdate(BaseModel):
    """
    Schema for updating project information.
    """
    name: Optional[str] = Field(None, description="Name of the project", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Detailed description of the project")
    type: Optional[ProjectType] = Field(None, description="Type of the project")
    status: Optional[ProjectStatus] = Field(None, description="Current status of the project")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    due_date: Optional[datetime] = Field(None, description="Project due date")
    completed_date: Optional[datetime] = Field(None, description="Date when the project was completed")
    progress: Optional[float] = Field(None, description="Progress percentage", ge=0, le=100)
    completion_percentage: Optional[int] = Field(None, description="Completion percentage", ge=0, le=100)
    sale_id: Optional[int] = Field(None, description="ID of the associated sale if applicable")
    template_id: Optional[int] = Field(None, description="ID of the project template if used")
    customer: Optional[str] = Field(None, description="Customer name if not linked to a sale")
    notes: Optional[str] = Field(None, description="Additional project notes")

    @validator('due_date')
    def due_date_after_start_date(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None and v < values['start_date']:
            raise ValueError('Due date must be after start date')
        return v

    @validator('completed_date')
    def validate_completed_date(cls, v, values):
        if v is not None and values.get('status') != ProjectStatus.COMPLETED:
            raise ValueError('Completed date can only be set when status is COMPLETED')
        return v


class ProjectInDB(ProjectBase):
    """
    Schema for project information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the project")
    created_at: datetime = Field(..., description="Timestamp when the project was created")
    updated_at: datetime = Field(..., description="Timestamp when the project was last updated")
    completed_date: Optional[datetime] = Field(None, description="Date when the project was completed")

    class Config:
        orm_mode = True


class ProjectResponse(ProjectInDB):
    """
    Schema for project responses in the API.
    """
    components: List[ProjectComponentResponse] = Field(..., description="Components included in the project")
    timeline_tasks: List[TimelineTaskResponse] = Field(..., description="Timeline tasks for the project")
    days_until_due: Optional[int] = Field(None, description="Days remaining until the project is due")
    is_overdue: Optional[bool] = Field(None, description="Whether the project is overdue")
    customer_name: Optional[str] = Field(None, description="Full name of the associated customer")

    class Config:
        orm_mode = True


class ProjectList(BaseModel):
    """
    Schema for paginated project list responses.
    """
    items: List[ProjectResponse]
    total: int = Field(..., description="Total number of projects matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


# Project Template Schemas

class ProjectTemplateBase(BaseModel):
    """
    Base schema for project template data.
    """
    name: str = Field(..., description="Name of the template", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Detailed description of the template")
    project_type: ProjectType = Field(..., description="Type of projects this template is for")
    skill_level: Optional[str] = Field(None, description="Required skill level for this project")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in hours", gt=0)
    estimated_cost: Optional[float] = Field(None, description="Estimated cost of materials", ge=0)
    version: Optional[str] = Field(None, description="Version of this template")
    is_public: Optional[bool] = Field(False, description="Whether this template is publicly available")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the template")
    notes: Optional[str] = Field(None, description="Additional template notes")


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


class ProjectTemplateCreate(ProjectTemplateBase):
    """
    Schema for creating a new project template.
    """
    components: Optional[List[ProjectTemplateComponentCreate]] = Field(None, description="Components for this template")


class ProjectTemplateUpdate(BaseModel):
    """
    Schema for updating project template information.
    """
    name: Optional[str] = Field(None, description="Name of the template", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Detailed description of the template")
    project_type: Optional[ProjectType] = Field(None, description="Type of projects this template is for")
    skill_level: Optional[str] = Field(None, description="Required skill level for this project")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in hours", gt=0)
    estimated_cost: Optional[float] = Field(None, description="Estimated cost of materials", ge=0)
    version: Optional[str] = Field(None, description="Version of this template")
    is_public: Optional[bool] = Field(None, description="Whether this template is publicly available")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the template")
    notes: Optional[str] = Field(None, description="Additional template notes")


class ProjectTemplateComponentInDB(ProjectTemplateComponentBase):
    """
    Schema for project template component information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the template component relation")
    template_id: int = Field(..., description="ID of the template")

    class Config:
        orm_mode = True


class ProjectTemplateComponentResponse(ProjectTemplateComponentInDB):
    """
    Schema for project template component responses in the API.
    """
    component_name: Optional[str] = Field(None, description="Name of the component")
    component_type: Optional[ComponentType] = Field(None, description="Type of the component")

    class Config:
        orm_mode = True


class ProjectTemplateInDB(ProjectTemplateBase):
    """
    Schema for project template information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the template")
    created_at: datetime = Field(..., description="Timestamp when the template was created")
    updated_at: datetime = Field(..., description="Timestamp when the template was last updated")

    class Config:
        orm_mode = True


class ProjectTemplateResponse(ProjectTemplateInDB):
    """
    Schema for project template responses in the API.
    """
    components: List[ProjectTemplateComponentResponse] = Field(..., description="Components included in the template")
    usage_count: Optional[int] = Field(None, description="Number of projects created from this template")

    class Config:
        orm_mode = True


class ProjectTemplateList(BaseModel):
    """
    Schema for paginated project template list responses.
    """
    items: List[ProjectTemplateResponse]
    total: int = Field(..., description="Total number of templates matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")