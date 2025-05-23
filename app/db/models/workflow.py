# File: app/db/models/workflow.py

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Float, JSON, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.models.base import Base


class WorkflowTheme(Base):
    """
    Themes for workflow UI customization.
    """
    __tablename__ = "workflow_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color_scheme: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # JSON object with colors
    icon_set: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    workflows: Mapped[List["Workflow"]] = relationship("Workflow", back_populates="theme")


class Workflow(Base):
    """
    Main workflow definition table.
    Stores workflow templates and active workflows.
    """
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    theme_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_themes.id"), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    default_locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    has_multiple_outcomes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in minutes
    difficulty_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Relationships
    steps: Mapped[List["WorkflowStep"]] = relationship("WorkflowStep", back_populates="workflow",
                                                       cascade="all, delete-orphan")
    executions: Mapped[List["WorkflowExecution"]] = relationship("WorkflowExecution", back_populates="workflow",
                                                                 cascade="all, delete-orphan")
    outcomes: Mapped[List["WorkflowOutcome"]] = relationship("WorkflowOutcome", back_populates="workflow",
                                                             cascade="all, delete-orphan")
    translations: Mapped[List["WorkflowTranslation"]] = relationship("WorkflowTranslation", back_populates="workflow",
                                                                     cascade="all, delete-orphan")
    theme: Mapped[Optional["WorkflowTheme"]] = relationship("WorkflowTheme", back_populates="workflows")

    # Indexes for performance
    __table_args__ = (
        Index('idx_workflow_status_template', 'status', 'is_template'),
        Index('idx_workflow_created_by', 'created_by'),
        Index('idx_workflow_project', 'project_id'),
        CheckConstraint("visibility IN ('private', 'public', 'shared')", name='check_workflow_visibility'),
    )


class WorkflowStep(Base):
    """
    Individual steps within a workflow.
    """
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    estimated_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in minutes
    parent_step_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_steps.id"), nullable=True)
    is_milestone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ui_position_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ui_position_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    theme_override_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_themes.id"), nullable=True)
    is_decision_point: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_outcome: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    condition_logic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON for complex conditions

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="steps")
    parent_step: Mapped[Optional["WorkflowStep"]] = relationship("WorkflowStep", remote_side=[id],
                                                                 back_populates="child_steps")
    child_steps: Mapped[List["WorkflowStep"]] = relationship("WorkflowStep", back_populates="parent_step")
    outgoing_connections: Mapped[List["WorkflowStepConnection"]] = relationship("WorkflowStepConnection",
                                                                                foreign_keys="WorkflowStepConnection.source_step_id",
                                                                                back_populates="source_step",
                                                                                cascade="all, delete-orphan")
    incoming_connections: Mapped[List["WorkflowStepConnection"]] = relationship("WorkflowStepConnection",
                                                                                foreign_keys="WorkflowStepConnection.target_step_id",
                                                                                back_populates="target_step")
    resources: Mapped[List["WorkflowStepResource"]] = relationship("WorkflowStepResource", back_populates="step",
                                                                   cascade="all, delete-orphan")
    decision_options: Mapped[List["WorkflowDecisionOption"]] = relationship("WorkflowDecisionOption",
                                                                            back_populates="step",
                                                                            cascade="all, delete-orphan")
    translations: Mapped[List["WorkflowStepTranslation"]] = relationship("WorkflowStepTranslation",
                                                                         back_populates="step",
                                                                         cascade="all, delete-orphan")
    theme_override: Mapped[Optional["WorkflowTheme"]] = relationship("WorkflowTheme")

    __table_args__ = (
        Index('idx_workflow_step_workflow_order', 'workflow_id', 'display_order'),
        Index('idx_workflow_step_type', 'step_type'),
        Index('idx_workflow_step_parent', 'parent_step_id'),
    )


class WorkflowStepConnection(Base):
    """
    Connections between workflow steps defining flow.
    """
    __tablename__ = "workflow_step_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id", ondelete="CASCADE"),
                                                nullable=False)
    target_step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id", ondelete="CASCADE"),
                                                nullable=False)
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False, default="sequential")
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON condition for conditional flows
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    source_step: Mapped["WorkflowStep"] = relationship("WorkflowStep", foreign_keys=[source_step_id],
                                                       back_populates="outgoing_connections")
    target_step: Mapped["WorkflowStep"] = relationship("WorkflowStep", foreign_keys=[target_step_id],
                                                       back_populates="incoming_connections")

    __table_args__ = (
        Index('idx_workflow_connection_source', 'source_step_id'),
        Index('idx_workflow_connection_target', 'target_step_id'),
        UniqueConstraint('source_step_id', 'target_step_id', 'connection_type', name='uq_step_connection'),
        CheckConstraint('source_step_id != target_step_id', name='check_no_self_connection'),
    )


class WorkflowStepResource(Base):
    """
    Resources required for workflow steps.
    CRITICAL: References DynamicMaterial instead of generic Material.
    """
    __tablename__ = "workflow_step_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                               index=True)  # 'material', 'tool', 'documentation'

    # FOR MATERIALS - Reference DynamicMaterial (following addendum corrections)
    dynamic_material_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dynamic_materials.id"),
                                                               nullable=True)

    # FOR TOOLS - Reference Tool
    tool_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tools.id"), nullable=True)

    # FOR DOCUMENTATION - Reference Documentation
    documentation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("documentation.id"), nullable=True)

    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    step: Mapped["WorkflowStep"] = relationship("WorkflowStep", back_populates="resources")
    dynamic_material: Mapped[Optional["DynamicMaterial"]] = relationship("DynamicMaterial")
    tool: Mapped[Optional["Tool"]] = relationship("Tool")

    __table_args__ = (
        Index('idx_workflow_resource_step', 'step_id'),
        Index('idx_workflow_resource_type', 'resource_type'),
        CheckConstraint("resource_type IN ('material', 'tool', 'documentation')", name='check_resource_type'),
    )


class WorkflowOutcome(Base):
    """
    Possible outcomes for workflows with multiple end results.
    """
    __tablename__ = "workflow_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    success_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON criteria

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="outcomes")

    __table_args__ = (
        Index('idx_workflow_outcome_workflow', 'workflow_id'),
        UniqueConstraint('workflow_id', 'name', name='uq_workflow_outcome_name'),
    )


class WorkflowDecisionOption(Base):
    """
    Options available at decision points in workflows.
    """
    __tablename__ = "workflow_decision_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False)
    option_text: Mapped[str] = mapped_column(String(500), nullable=False)
    result_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON action definition
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    step: Mapped["WorkflowStep"] = relationship("WorkflowStep", back_populates="decision_options")

    __table_args__ = (
        Index('idx_workflow_decision_step', 'step_id'),
    )


class WorkflowExecution(Base):
    """
    Runtime instances of workflow execution.
    """
    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id"), nullable=False)
    started_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    selected_outcome_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_outcomes.id"),
                                                               nullable=True)
    current_step_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_steps.id"), nullable=True)
    execution_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Runtime data and variables
    total_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in minutes

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")
    selected_outcome: Mapped[Optional["WorkflowOutcome"]] = relationship("WorkflowOutcome")
    current_step: Mapped[Optional["WorkflowStep"]] = relationship("WorkflowStep")
    step_executions: Mapped[List["WorkflowStepExecution"]] = relationship("WorkflowStepExecution",
                                                                          back_populates="execution",
                                                                          cascade="all, delete-orphan")
    navigation_history: Mapped[List["WorkflowNavigationHistory"]] = relationship("WorkflowNavigationHistory",
                                                                                 back_populates="execution",
                                                                                 cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_workflow_execution_workflow', 'workflow_id'),
        Index('idx_workflow_execution_user', 'started_by'),
        Index('idx_workflow_execution_status', 'status'),
        Index('idx_workflow_execution_current_step', 'current_step_id'),
    )


class WorkflowStepExecution(Base):
    """
    Execution tracking for individual workflow steps.
    """
    __tablename__ = "workflow_step_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    execution_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_executions.id", ondelete="CASCADE"),
                                              nullable=False)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ready", index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in minutes
    step_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Step-specific data
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship("WorkflowExecution", back_populates="step_executions")
    step: Mapped["WorkflowStep"] = relationship("WorkflowStep")

    __table_args__ = (
        Index('idx_workflow_step_execution_execution', 'execution_id'),
        Index('idx_workflow_step_execution_step', 'step_id'),
        Index('idx_workflow_step_execution_status', 'status'),
        UniqueConstraint('execution_id', 'step_id', name='uq_execution_step'),
    )


class WorkflowNavigationHistory(Base):
    """
    History of user navigation through workflow execution.
    """
    __tablename__ = "workflow_navigation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    execution_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_executions.id", ondelete="CASCADE"),
                                              nullable=False)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'navigate_to', 'complete', 'decision_made'
    action_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Action-specific data
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship("WorkflowExecution", back_populates="navigation_history")
    step: Mapped["WorkflowStep"] = relationship("WorkflowStep")

    __table_args__ = (
        Index('idx_workflow_navigation_execution', 'execution_id'),
        Index('idx_workflow_navigation_step', 'step_id'),
        Index('idx_workflow_navigation_timestamp', 'timestamp'),
    )


class WorkflowTranslation(Base):
    """
    Internationalization support for workflow content.
    """
    __tablename__ = "workflow_translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    translated_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="translations")

    __table_args__ = (
        Index('idx_workflow_translation_workflow_locale', 'workflow_id', 'locale'),
        UniqueConstraint('workflow_id', 'locale', 'field_name', name='uq_workflow_translation'),
    )


class WorkflowStepTranslation(Base):
    """
    Internationalization support for workflow step content.
    """
    __tablename__ = "workflow_step_translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    translated_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    step: Mapped["WorkflowStep"] = relationship("WorkflowStep", back_populates="translations")

    __table_args__ = (
        Index('idx_workflow_step_translation_step_locale', 'step_id', 'locale'),
        UniqueConstraint('step_id', 'locale', 'field_name', name='uq_workflow_step_translation'),
    )


class WorkflowPath(Base):
    """
    Predefined paths through workflows for guided navigation.
    """
    __tablename__ = "workflow_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    difficulty_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in minutes

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow")
    path_steps: Mapped[List["WorkflowPathStep"]] = relationship("WorkflowPathStep", back_populates="path",
                                                                cascade="all, delete-orphan",
                                                                order_by="WorkflowPathStep.step_order")

    __table_args__ = (
        Index('idx_workflow_path_workflow', 'workflow_id'),
        UniqueConstraint('workflow_id', 'name', name='uq_workflow_path_name'),
    )


class WorkflowPathStep(Base):
    """
    Steps within a predefined workflow path.
    """
    __tablename__ = "workflow_path_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_paths.id", ondelete="CASCADE"), nullable=False)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_steps.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skip_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON condition for skipping

    # Relationships
    path: Mapped["WorkflowPath"] = relationship("WorkflowPath", back_populates="path_steps")
    step: Mapped["WorkflowStep"] = relationship("WorkflowStep")

    __table_args__ = (
        Index('idx_workflow_path_step_path_order', 'path_id', 'step_order'),
        UniqueConstraint('path_id', 'step_id', name='uq_path_step'),
        UniqueConstraint('path_id', 'step_order', name='uq_path_step_order'),
    )