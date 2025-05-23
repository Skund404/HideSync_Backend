# File: app/schemas/workflow.py

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum


# ==================== Base Schemas ====================

class WorkflowThemeBase(BaseModel):
    """Base schema for workflow themes."""
    name: str = Field(..., max_length=100, description="Theme name")
    description: Optional[str] = Field(None, description="Theme description")
    color_scheme: Optional[Dict[str, Any]] = Field(None, description="JSON color scheme configuration")
    icon_set: Optional[str] = Field(None, max_length=50, description="Icon set identifier")


class WorkflowThemeCreate(WorkflowThemeBase):
    """Schema for creating workflow themes."""
    pass


class WorkflowThemeUpdate(BaseModel):
    """Schema for updating workflow themes."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    color_scheme: Optional[Dict[str, Any]] = None
    icon_set: Optional[str] = Field(None, max_length=50)


class WorkflowThemeResponse(WorkflowThemeBase):
    """Schema for workflow theme responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_system: bool
    created_at: datetime


# ==================== Workflow Schemas ====================

class WorkflowBase(BaseModel):
    """Base schema for workflows."""
    name: str = Field(..., max_length=200, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    is_template: bool = Field(False, description="Whether this is a template workflow")
    visibility: str = Field("private", description="Workflow visibility")
    version: str = Field("1.0", max_length=20, description="Workflow version")
    default_locale: str = Field("en", max_length=10, description="Default locale")
    has_multiple_outcomes: bool = Field(False, description="Whether workflow has multiple possible outcomes")
    estimated_duration: Optional[float] = Field(None, ge=0, description="Estimated duration in minutes")
    difficulty_level: Optional[str] = Field(None, max_length=20, description="Difficulty level")

    @field_validator('visibility')
    @classmethod
    def validate_visibility(cls, v):
        if v not in ['private', 'public', 'shared']:
            raise ValueError('Visibility must be private, public, or shared')
        return v

    @field_validator('estimated_duration')
    @classmethod
    def validate_duration(cls, v):
        if v is not None and v < 0:
            raise ValueError('Estimated duration cannot be negative')
        return v


class WorkflowCreate(WorkflowBase):
    """Schema for creating workflows."""
    project_id: Optional[int] = Field(None, description="Associated project ID")
    theme_id: Optional[int] = Field(None, description="Theme ID")


class WorkflowUpdate(BaseModel):
    """Schema for updating workflows."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)
    visibility: Optional[str] = None
    version: Optional[str] = Field(None, max_length=20)
    has_multiple_outcomes: Optional[bool] = None
    estimated_duration: Optional[float] = Field(None, ge=0)
    difficulty_level: Optional[str] = Field(None, max_length=20)
    theme_id: Optional[int] = None

    @field_validator('visibility')
    @classmethod
    def validate_visibility(cls, v):
        if v is not None and v not in ['private', 'public', 'shared']:
            raise ValueError('Visibility must be private, public, or shared')
        return v


class WorkflowResponse(WorkflowBase):
    """Schema for workflow responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    project_id: Optional[int]
    theme_id: Optional[int]

    # Optional nested relationships
    steps: Optional[List["WorkflowStepResponse"]] = None
    outcomes: Optional[List["WorkflowOutcomeResponse"]] = None
    theme: Optional[WorkflowThemeResponse] = None


class WorkflowListResponse(BaseModel):
    """Schema for paginated workflow list responses."""
    items: List[WorkflowResponse]
    total: int
    limit: int
    offset: int


# ==================== Workflow Step Schemas ====================

class WorkflowStepResourceBase(BaseModel):
    """Base schema for workflow step resources."""
    resource_type: str = Field(..., description="Type of resource: material, tool, or documentation")
    dynamic_material_id: Optional[int] = Field(None, description="Dynamic material ID")
    tool_id: Optional[int] = Field(None, description="Tool ID")
    documentation_id: Optional[int] = Field(None, description="Documentation ID")
    quantity: Optional[float] = Field(None, ge=0, description="Required quantity")
    unit: Optional[str] = Field(None, max_length=20, description="Unit of measurement")
    notes: Optional[str] = Field(None, description="Additional notes")
    is_optional: bool = Field(False, description="Whether resource is optional")

    @field_validator('resource_type')
    @classmethod
    def validate_resource_type(cls, v):
        if v not in ['material', 'tool', 'documentation']:
            raise ValueError('Resource type must be material, tool, or documentation')
        return v


class WorkflowStepResourceCreate(WorkflowStepResourceBase):
    """Schema for creating workflow step resources."""
    pass


class WorkflowStepResourceResponse(WorkflowStepResourceBase):
    """Schema for workflow step resource responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_id: int


class WorkflowDecisionOptionBase(BaseModel):
    """Base schema for workflow decision options."""
    option_text: str = Field(..., max_length=500, description="Decision option text")
    result_action: Optional[str] = Field(None, description="JSON action definition")
    display_order: int = Field(1, ge=1, description="Display order")
    is_default: bool = Field(False, description="Whether this is the default option")


class WorkflowDecisionOptionCreate(WorkflowDecisionOptionBase):
    """Schema for creating workflow decision options."""
    pass


class WorkflowDecisionOptionResponse(WorkflowDecisionOptionBase):
    """Schema for workflow decision option responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_id: int


class WorkflowStepBase(BaseModel):
    """Base schema for workflow steps."""
    name: str = Field(..., max_length=200, description="Step name")
    description: Optional[str] = Field(None, description="Step description")
    instructions: Optional[str] = Field(None, description="Detailed instructions")
    display_order: int = Field(1, ge=1, description="Display order in workflow")
    step_type: str = Field(..., description="Type of workflow step")
    estimated_duration: Optional[float] = Field(None, ge=0, description="Estimated duration in minutes")
    parent_step_id: Optional[int] = Field(None, description="Parent step ID")
    is_milestone: bool = Field(False, description="Whether this is a milestone step")
    ui_position_x: Optional[float] = Field(None, description="UI X position")
    ui_position_y: Optional[float] = Field(None, description="UI Y position")
    theme_override_id: Optional[int] = Field(None, description="Theme override ID")
    is_decision_point: bool = Field(False, description="Whether this is a decision point")
    is_outcome: bool = Field(False, description="Whether this is an outcome step")
    condition_logic: Optional[str] = Field(None, description="JSON condition logic")


class WorkflowStepCreate(WorkflowStepBase):
    """Schema for creating workflow steps."""
    workflow_id: int = Field(..., description="Workflow ID")
    resources: Optional[List[WorkflowStepResourceCreate]] = Field(default_factory=list)
    decision_options: Optional[List[WorkflowDecisionOptionCreate]] = Field(default_factory=list)


class WorkflowStepUpdate(BaseModel):
    """Schema for updating workflow steps."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    display_order: Optional[int] = Field(None, ge=1)
    step_type: Optional[str] = None
    estimated_duration: Optional[float] = Field(None, ge=0)
    parent_step_id: Optional[int] = None
    is_milestone: Optional[bool] = None
    ui_position_x: Optional[float] = None
    ui_position_y: Optional[float] = None
    theme_override_id: Optional[int] = None
    is_decision_point: Optional[bool] = None
    is_outcome: Optional[bool] = None
    condition_logic: Optional[str] = None


class WorkflowStepResponse(WorkflowStepBase):
    """Schema for workflow step responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int

    # Optional nested relationships
    resources: Optional[List[WorkflowStepResourceResponse]] = None
    decision_options: Optional[List[WorkflowDecisionOptionResponse]] = None
    outgoing_connections: Optional[List["WorkflowStepConnectionResponse"]] = None


# ==================== Workflow Step Connection Schemas ====================

class WorkflowStepConnectionBase(BaseModel):
    """Base schema for workflow step connections."""
    connection_type: str = Field("sequential", description="Type of connection")
    condition: Optional[str] = Field(None, description="JSON condition for conditional flows")
    display_order: int = Field(1, ge=1, description="Display order")
    is_default: bool = Field(False, description="Whether this is the default connection")


class WorkflowStepConnectionCreate(WorkflowStepConnectionBase):
    """Schema for creating workflow step connections."""
    source_step_id: int = Field(..., description="Source step ID")
    target_step_id: int = Field(..., description="Target step ID")

    @field_validator('target_step_id')
    @classmethod
    def validate_no_self_connection(cls, v, info):
        if 'source_step_id' in info.data and v == info.data['source_step_id']:
            raise ValueError('Source and target steps cannot be the same')
        return v


class WorkflowStepConnectionResponse(WorkflowStepConnectionBase):
    """Schema for workflow step connection responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_step_id: int
    target_step_id: int


# ==================== Workflow Outcome Schemas ====================

class WorkflowOutcomeBase(BaseModel):
    """Base schema for workflow outcomes."""
    name: str = Field(..., max_length=200, description="Outcome name")
    description: Optional[str] = Field(None, description="Outcome description")
    display_order: int = Field(1, ge=1, description="Display order")
    is_default: bool = Field(False, description="Whether this is the default outcome")
    success_criteria: Optional[str] = Field(None, description="JSON success criteria")


class WorkflowOutcomeCreate(WorkflowOutcomeBase):
    """Schema for creating workflow outcomes."""
    workflow_id: int = Field(..., description="Workflow ID")


class WorkflowOutcomeUpdate(BaseModel):
    """Schema for updating workflow outcomes."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    display_order: Optional[int] = Field(None, ge=1)
    is_default: Optional[bool] = None
    success_criteria: Optional[str] = None


class WorkflowOutcomeResponse(WorkflowOutcomeBase):
    """Schema for workflow outcome responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int


# ==================== Workflow Execution Schemas ====================

class WorkflowExecutionBase(BaseModel):
    """Base schema for workflow executions."""
    selected_outcome_id: Optional[int] = Field(None, description="Selected outcome ID")
    execution_data: Optional[Dict[str, Any]] = Field(None, description="Runtime execution data")


class WorkflowExecutionCreate(WorkflowExecutionBase):
    """Schema for creating workflow executions."""
    pass


class WorkflowExecutionUpdate(BaseModel):
    """Schema for updating workflow executions."""
    status: Optional[str] = Field(None, max_length=50)
    current_step_id: Optional[int] = None
    execution_data: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None
    total_duration: Optional[float] = Field(None, ge=0)


class WorkflowExecutionResponse(WorkflowExecutionBase):
    """Schema for workflow execution responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    started_by: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    current_step_id: Optional[int]
    total_duration: Optional[float]

    # Optional nested relationships
    workflow: Optional[WorkflowResponse] = None
    step_executions: Optional[List["WorkflowStepExecutionResponse"]] = None


# ==================== Workflow Step Execution Schemas ====================

class WorkflowStepExecutionBase(BaseModel):
    """Base schema for workflow step executions."""
    step_data: Optional[Dict[str, Any]] = Field(None, description="Step-specific execution data")
    notes: Optional[str] = Field(None, description="Execution notes")


class WorkflowStepExecutionCreate(WorkflowStepExecutionBase):
    """Schema for creating workflow step executions."""
    execution_id: int = Field(..., description="Workflow execution ID")
    step_id: int = Field(..., description="Workflow step ID")


class WorkflowStepExecutionUpdate(BaseModel):
    """Schema for updating workflow step executions."""
    status: Optional[str] = Field(None, max_length=50)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_duration: Optional[float] = Field(None, ge=0)
    step_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class WorkflowStepExecutionResponse(WorkflowStepExecutionBase):
    """Schema for workflow step execution responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    step_id: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    actual_duration: Optional[float]

    # Optional nested relationships
    step: Optional[WorkflowStepResponse] = None


# ==================== Workflow Navigation Schemas ====================

class WorkflowNavigationHistoryBase(BaseModel):
    """Base schema for workflow navigation history."""
    action_type: str = Field(..., max_length=50, description="Type of navigation action")
    action_data: Optional[Dict[str, Any]] = Field(None, description="Action-specific data")


class WorkflowNavigationHistoryCreate(WorkflowNavigationHistoryBase):
    """Schema for creating workflow navigation history."""
    execution_id: int = Field(..., description="Workflow execution ID")
    step_id: int = Field(..., description="Workflow step ID")


class WorkflowNavigationHistoryResponse(WorkflowNavigationHistoryBase):
    """Schema for workflow navigation history responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    step_id: int
    timestamp: datetime


# ==================== Workflow Path Schemas ====================

class WorkflowPathStepBase(BaseModel):
    """Base schema for workflow path steps."""
    step_order: int = Field(..., ge=1, description="Order of step in path")
    is_optional: bool = Field(False, description="Whether step is optional")
    skip_condition: Optional[str] = Field(None, description="JSON condition for skipping")


class WorkflowPathStepCreate(WorkflowPathStepBase):
    """Schema for creating workflow path steps."""
    step_id: int = Field(..., description="Workflow step ID")


class WorkflowPathStepResponse(WorkflowPathStepBase):
    """Schema for workflow path step responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    path_id: int
    step_id: int

    # Optional nested relationship
    step: Optional[WorkflowStepResponse] = None


class WorkflowPathBase(BaseModel):
    """Base schema for workflow paths."""
    name: str = Field(..., max_length=200, description="Path name")
    description: Optional[str] = Field(None, description="Path description")
    is_default: bool = Field(False, description="Whether this is the default path")
    difficulty_level: Optional[str] = Field(None, max_length=20, description="Difficulty level")
    estimated_duration: Optional[float] = Field(None, ge=0, description="Estimated duration in minutes")


class WorkflowPathCreate(WorkflowPathBase):
    """Schema for creating workflow paths."""
    workflow_id: int = Field(..., description="Workflow ID")
    path_steps: Optional[List[WorkflowPathStepCreate]] = Field(default_factory=list)


class WorkflowPathUpdate(BaseModel):
    """Schema for updating workflow paths."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    difficulty_level: Optional[str] = Field(None, max_length=20)
    estimated_duration: Optional[float] = Field(None, ge=0)


class WorkflowPathResponse(WorkflowPathBase):
    """Schema for workflow path responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int

    # Optional nested relationships
    path_steps: Optional[List[WorkflowPathStepResponse]] = None


# ==================== Import/Export Schemas ====================

class WorkflowImportData(BaseModel):
    """Schema for workflow import data."""
    preset_info: Dict[str, Any] = Field(..., description="Preset information")
    workflow: Dict[str, Any] = Field(..., description="Workflow definition")
    required_resources: Optional[Dict[str, Any]] = Field(None, description="Required resources")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Import metadata")

    @field_validator('preset_info')
    @classmethod
    def validate_preset_info(cls, v):
        required_fields = ['name']
        for field in required_fields:
            if field not in v:
                raise ValueError(f'Preset info missing required field: {field}')
        return v

    @field_validator('workflow')
    @classmethod
    def validate_workflow_data(cls, v):
        required_fields = ['name']
        for field in required_fields:
            if field not in v:
                raise ValueError(f'Workflow data missing required field: {field}')
        return v


class WorkflowExportResponse(BaseModel):
    """Schema for workflow export response."""
    preset_info: Dict[str, Any]
    workflow: Dict[str, Any]
    required_resources: Dict[str, Any]
    metadata: Dict[str, Any]


# ==================== Search and Filter Schemas ====================

class WorkflowSearchParams(BaseModel):
    """Schema for workflow search parameters."""
    search: Optional[str] = Field(None, description="Search term")
    status: Optional[str] = Field(None, description="Status filter")
    is_template: Optional[bool] = Field(None, description="Template filter")
    difficulty_level: Optional[str] = Field(None, description="Difficulty filter")
    created_by: Optional[int] = Field(None, description="Creator filter")
    project_id: Optional[int] = Field(None, description="Project filter")
    limit: int = Field(50, ge=1, le=100, description="Page size")
    offset: int = Field(0, ge=0, description="Page offset")


# ==================== Navigation and Interaction Schemas ====================

class WorkflowDecisionRequest(BaseModel):
    """Schema for making decisions in workflow execution."""
    decision_option_id: int = Field(..., description="Selected decision option ID")
    notes: Optional[str] = Field(None, description="Decision notes")


class WorkflowNavigationRequest(BaseModel):
    """Schema for navigation requests."""
    target_step_id: int = Field(..., description="Target step ID")
    action_type: str = Field("navigate_to", description="Navigation action type")
    action_data: Optional[Dict[str, Any]] = Field(None, description="Additional action data")


class WorkflowStepCompletionRequest(BaseModel):
    """Schema for completing workflow steps."""
    notes: Optional[str] = Field(None, description="Completion notes")
    step_data: Optional[Dict[str, Any]] = Field(None, description="Step completion data")
    actual_duration: Optional[float] = Field(None, ge=0, description="Actual duration in minutes")


# ==================== Status and Progress Schemas ====================

class WorkflowProgressSummary(BaseModel):
    """Schema for workflow execution progress summary."""
    execution_id: int
    total_steps: int
    completed_steps: int
    current_step_id: Optional[int]
    current_step_name: Optional[str]
    progress_percentage: float = Field(..., ge=0, le=100)
    estimated_remaining_time: Optional[float]
    time_elapsed: Optional[float]


class WorkflowStatistics(BaseModel):
    """Schema for workflow statistics."""
    workflow_id: int
    total_executions: int
    completed_executions: int
    average_completion_time: Optional[float]
    success_rate: float = Field(..., ge=0, le=100)
    most_common_outcome: Optional[str]


# Update forward references
WorkflowResponse.model_rebuild()
WorkflowStepResponse.model_rebuild()
WorkflowExecutionResponse.model_rebuild()
WorkflowStepExecutionResponse.model_rebuild()