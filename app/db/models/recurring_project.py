# app/db/models/recurring_project.py
"""
Database models for recurring projects in HideSync.

This module defines the SQLAlchemy models for recurring projects,
recurrence patterns, and generated projects.
"""

from datetime import datetime, date, timedelta
import json
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
    Date,
    Text,
    JSON,
    Float,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import Base, AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ProjectType, ProjectStatus, SkillLevel


class RecurrencePattern(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Model for recurrence patterns.

    Defines when a recurring project should generate new instances.
    """

    __tablename__ = "recurrence_patterns"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly, etc.
    interval = Column(Integer, default=1, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    end_after_occurrences = Column(Integer, nullable=True)
    days_of_week = Column(JSON, nullable=True)  # [0, 1, 5] for Sun, Mon, Fri
    day_of_month = Column(Integer, nullable=True)
    week_of_month = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    custom_dates = Column(JSON, nullable=True)  # List of specific dates as strings
    skip_weekends = Column(Boolean, default=False)
    skip_holidays = Column(Boolean, default=False)

    # Relationships
    recurring_projects = relationship(
        "RecurringProject", back_populates="recurrence_pattern"
    )

    @validates("frequency")
    def validate_frequency(self, key, value):
        """Validate frequency value."""
        valid_frequencies = [
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
            "custom",
        ]
        if value.lower() not in valid_frequencies:
            raise ValueError(
                f"Invalid frequency: {value}. Must be one of {valid_frequencies}"
            )
        return value.lower()

    @validates("interval")
    def validate_interval(self, key, value):
        """Validate interval value."""
        if value < 1:
            raise ValueError("Interval must be at least 1")
        return value

    @validates("days_of_week")
    def validate_days_of_week(self, key, value):
        """Validate and convert days_of_week."""
        if value is None:
            return None

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid days_of_week format")

        if not isinstance(value, list):
            raise ValueError("days_of_week must be a list of integers")

        # Validate each day is 0-6
        for day in value:
            if not isinstance(day, int) or day < 0 or day > 6:
                raise ValueError("Each day in days_of_week must be an integer from 0-6")

        return value

    @validates("custom_dates")
    def validate_custom_dates(self, key, value):
        """Validate and convert custom_dates."""
        if value is None:
            return None

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid custom_dates format")

        if not isinstance(value, list):
            raise ValueError("custom_dates must be a list of date strings")

        # Convert strings to date objects
        result = []
        for date_str in value:
            try:
                if isinstance(date_str, str):
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    result.append(date_obj)
                elif (
                    isinstance(date_str, dict)
                    and "year" in date_str
                    and "month" in date_str
                    and "day" in date_str
                ):
                    date_obj = date(
                        date_str["year"], date_str["month"], date_str["day"]
                    )
                    result.append(date_obj)
                else:
                    raise ValueError("Invalid date format")
            except ValueError:
                raise ValueError(f"Invalid date format: {date_str}")

        return result


class RecurringProject(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Model for recurring projects.

    Defines a project template that generates new project instances
    according to a recurrence pattern.
    """

    __tablename__ = "recurring_projects"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String(50), nullable=False)
    skill_level = Column(String(50), nullable=True)
    duration = Column(Integer, nullable=True)  # In hours
    is_active = Column(Boolean, default=True)
    auto_generate = Column(Boolean, default=True)
    advance_notice_days = Column(Integer, nullable=True)
    project_suffix = Column(String(50), nullable=True)

    recurrence_pattern_id = Column(
        String, ForeignKey("recurrence_patterns.id"), nullable=False
    )
    template_id = Column(String, ForeignKey("project_templates.id"), nullable=True)
    client_id = Column(String, ForeignKey("customers.id"), nullable=True)

    next_occurrence = Column(Date, nullable=True)
    last_occurrence = Column(Date, nullable=True)
    total_occurrences = Column(Integer, default=0)

    created_by = Column(String, nullable=True)

    # Relationships
    recurrence_pattern = relationship(
        "RecurrencePattern", back_populates="recurring_projects"
    )
    generated_projects = relationship(
        "GeneratedProject", back_populates="recurring_project"
    )

    @validates("project_type")
    def validate_project_type(self, key, value):
        """Validate project type."""
        try:
            ProjectType(value)
        except ValueError:
            raise ValueError(f"Invalid project_type: {value}")
        return value

    @validates("skill_level")
    def validate_skill_level(self, key, value):
        """Validate skill level if provided."""
        if value is not None:
            try:
                SkillLevel(value)
            except ValueError:
                raise ValueError(f"Invalid skill_level: {value}")
        return value


class GeneratedProject(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Model for tracking projects generated from recurring projects.

    Links recurring projects to their generated instances.
    """

    __tablename__ = "generated_projects"

    id = Column(String, primary_key=True)
    recurring_project_id = Column(
        String, ForeignKey("recurring_projects.id"), nullable=False
    )
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    occurrence_number = Column(Integer, nullable=False)
    scheduled_date = Column(Date, nullable=False)
    actual_generation_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="generated")
    notes = Column(Text, nullable=True)

    # Relationships
    recurring_project = relationship(
        "RecurringProject", back_populates="generated_projects"
    )
    project = relationship("Project")

    @validates("status")
    def validate_status(self, key, value):
        """Validate status value."""
        valid_statuses = ["scheduled", "generated", "skipped", "failed", "orphaned"]
        if value.lower() not in valid_statuses:
            raise ValueError(
                f"Invalid status: {value}. Must be one of {valid_statuses}"
            )
        return value.lower()
