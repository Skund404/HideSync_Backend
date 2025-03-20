# File: services/recurring_project_service.py

"""
Recurring project management service for the HideSync system.

This module provides functionality for managing recurring projects, which allow craftspeople
to create repeating production schedules based on templates. It handles the creation of
recurring project definitions, recurrence pattern management, and the automatic generation
of project instances at scheduled intervals.

Recurring projects are essential for businesses with regular production cycles, subscription-based
offerings, or repeated custom orders. This service enables efficient management of these
cyclical workflows while maintaining consistency across project instances.

Key features:
- Recurring project template creation and management
- Recurrence pattern configuration (daily, weekly, monthly, etc.)
- Automatic project generation based on schedules
- Schedule management and adjustments
- Holiday and business hour awareness
- Integration with project management

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with the
project service to create concrete project instances.
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime, timedelta, date
import logging
import uuid
import calendar
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import ProjectType, SkillLevel
from app.db.models.recurring_project import (
    RecurringProject,
    RecurrencePattern,
    GeneratedProject,
)
from app.repositories.recurring_project_repository import (
    RecurringProjectRepository,
    RecurrencePatternRepository,
    GeneratedProjectRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class RecurringProjectCreated(DomainEvent):
    """Event emitted when a recurring project is created."""

    def __init__(
        self,
        recurring_project_id: str,
        template_id: str,
        name: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize recurring project created event.

        Args:
            recurring_project_id: ID of the created recurring project
            template_id: ID of the project template
            name: Name of the recurring project
            user_id: Optional ID of the user who created the recurring project
        """
        super().__init__()
        self.recurring_project_id = recurring_project_id
        self.template_id = template_id
        self.name = name
        self.user_id = user_id


class RecurringProjectUpdated(DomainEvent):
    """Event emitted when a recurring project is updated."""

    def __init__(
        self,
        recurring_project_id: str,
        changes: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        """
        Initialize recurring project updated event.

        Args:
            recurring_project_id: ID of the updated recurring project
            changes: Dictionary of changed fields
            user_id: Optional ID of the user who updated the recurring project
        """
        super().__init__()
        self.recurring_project_id = recurring_project_id
        self.changes = changes
        self.user_id = user_id


class RecurringProjectDeleted(DomainEvent):
    """Event emitted when a recurring project is deleted."""

    def __init__(
        self, recurring_project_id: str, name: str, user_id: Optional[int] = None
    ):
        """
        Initialize recurring project deleted event.

        Args:
            recurring_project_id: ID of the deleted recurring project
            name: Name of the recurring project
            user_id: Optional ID of the user who deleted the recurring project
        """
        super().__init__()
        self.recurring_project_id = recurring_project_id
        self.name = name
        self.user_id = user_id


class RecurrencePatternCreated(DomainEvent):
    """Event emitted when a recurrence pattern is created."""

    def __init__(
        self,
        pattern_id: str,
        recurring_project_id: str,
        frequency: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize recurrence pattern created event.

        Args:
            pattern_id: ID of the created recurrence pattern
            recurring_project_id: ID of the associated recurring project
            frequency: Frequency type of the pattern
            user_id: Optional ID of the user who created the pattern
        """
        super().__init__()
        self.pattern_id = pattern_id
        self.recurring_project_id = recurring_project_id
        self.frequency = frequency
        self.user_id = user_id


class RecurrencePatternUpdated(DomainEvent):
    """Event emitted when a recurrence pattern is updated."""

    def __init__(
        self,
        pattern_id: str,
        recurring_project_id: str,
        changes: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        """
        Initialize recurrence pattern updated event.

        Args:
            pattern_id: ID of the updated recurrence pattern
            recurring_project_id: ID of the associated recurring project
            changes: Dictionary of changed fields
            user_id: Optional ID of the user who updated the pattern
        """
        super().__init__()
        self.pattern_id = pattern_id
        self.recurring_project_id = recurring_project_id
        self.changes = changes
        self.user_id = user_id


class ProjectGenerated(DomainEvent):
    """Event emitted when a project is generated from a recurring project."""

    def __init__(
        self,
        generated_project_id: str,
        recurring_project_id: str,
        project_id: str,
        scheduled_date: datetime,
        occurrence_number: int,
    ):
        """
        Initialize project generated event.

        Args:
            generated_project_id: ID of the generated project record
            recurring_project_id: ID of the recurring project
            project_id: ID of the new project instance
            scheduled_date: Scheduled date for the project
            occurrence_number: Occurrence number in the sequence
        """
        super().__init__()
        self.generated_project_id = generated_project_id
        self.recurring_project_id = recurring_project_id
        self.project_id = project_id
        self.scheduled_date = scheduled_date
        self.occurrence_number = occurrence_number


class GenerationFailed(DomainEvent):
    """Event emitted when project generation fails."""

    def __init__(
        self,
        recurring_project_id: str,
        scheduled_date: datetime,
        occurrence_number: int,
        error: str,
    ):
        """
        Initialize generation failed event.

        Args:
            recurring_project_id: ID of the recurring project
            scheduled_date: Scheduled date for the project
            occurrence_number: Occurrence number in the sequence
            error: Error message explaining the failure
        """
        super().__init__()
        self.recurring_project_id = recurring_project_id
        self.scheduled_date = scheduled_date
        self.occurrence_number = occurrence_number
        self.error = error


# Validation functions
validate_recurring_project = validate_entity(RecurringProject)
validate_recurrence_pattern = validate_entity(RecurrencePattern)
validate_generated_project = validate_entity(GeneratedProject)


class RecurringProjectService(BaseService[RecurringProject]):
    """
    Service for managing recurring projects in the HideSync system.

    Provides functionality for:
    - Recurring project creation and management
    - Recurrence pattern configuration
    - Automatic project generation
    - Schedule management
    - Integration with project management
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        pattern_repository=None,
        generated_project_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        project_service=None,
        template_service=None,
        notification_service=None,
    ):
        """
        Initialize RecurringProjectService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for recurring projects
            pattern_repository: Optional repository for recurrence patterns
            generated_project_repository: Optional repository for generated projects
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            project_service: Optional service for project operations
            template_service: Optional service for template operations
            notification_service: Optional service for sending notifications
        """
        self.session = session
        self.repository = repository or RecurringProjectRepository(session)
        self.pattern_repository = pattern_repository or RecurrencePatternRepository(
            session
        )
        self.generated_project_repository = (
            generated_project_repository or GeneratedProjectRepository(session)
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.project_service = project_service
        self.template_service = template_service
        self.notification_service = notification_service

    @validate_input(validate_recurring_project)
    def create_recurring_project(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new recurring project with a recurrence pattern.

        Args:
            data: Recurring project data with required fields
                Required fields:
                - templateId: ID of the project template to use
                - name: Name of the recurring project
                - projectType: Type of project
                - skillLevel: Required skill level
                - recurrence_pattern: Dictionary with pattern configuration
                  Required sub-fields:
                  - frequency: Pattern frequency (daily, weekly, monthly, etc.)
                  - interval: Interval between occurrences
                  - startDate: Date to start generating projects
                  Optional sub-fields:
                  - endDate: Date to stop generating projects (if any)
                  - endAfterOccurrences: Number of occurrences after which to end
                  - daysOfWeek: List of day indices (0-6) for weekly patterns
                  - dayOfMonth: Day of month for monthly patterns
                  - weekOfMonth: Week of month for monthly patterns
                  - month: Month number for yearly patterns
                  - customDates: Array of specific dates for custom patterns
                  - skipWeekends: Whether to skip weekend occurrences
                  - skipHolidays: Whether to skip holiday occurrences
                Optional fields:
                - duration: Estimated project duration in days
                - isActive: Whether the recurring project is active
                - autoGenerate: Whether to automatically generate projects
                - advanceNoticeDays: Days in advance to generate projects
                - projectSuffix: Suffix to add to generated project names
                - clientId: ID of the client this project is for

        Returns:
            Created recurring project with pattern

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If template not found
        """
        with self.transaction():
            # Check if template exists if template service is available
            template_id = data.get("templateId")
            if template_id and self.template_service:
                template = self.template_service.get_by_id(template_id)
                if not template:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("ProjectTemplate", template_id)

            # Generate ID if not provided
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # Set default values if not provided
            if "isActive" not in data:
                data["isActive"] = True

            if "autoGenerate" not in data:
                data["autoGenerate"] = True

            if "advanceNoticeDays" not in data:
                data["advanceNoticeDays"] = 7

            if "createdAt" not in data:
                data["createdAt"] = datetime.now()

            if "modifiedAt" not in data:
                data["modifiedAt"] = datetime.now()

            # Extract recurrence pattern for later creation
            recurrence_pattern_data = data.pop("recurrence_pattern", {})

            # Create recurring project
            recurring_project = self.repository.create(data)

            # Create recurrence pattern
            recurrence_pattern = None
            if recurrence_pattern_data:
                # Generate ID if not provided
                if "id" not in recurrence_pattern_data:
                    recurrence_pattern_data["id"] = str(uuid.uuid4())

                # Add reference to recurring project
                recurrence_pattern_data["recurring_project_id"] = recurring_project.id

                # Set name if not provided
                if "name" not in recurrence_pattern_data:
                    frequency = recurrence_pattern_data.get("frequency", "custom")
                    interval = recurrence_pattern_data.get("interval", 1)
                    recurrence_pattern_data["name"] = (
                        f"{frequency.capitalize()} (every {interval})"
                    )

                # Create pattern
                recurrence_pattern = self.pattern_repository.create(
                    recurrence_pattern_data
                )

                # Publish event if event bus exists
                if self.event_bus:
                    user_id = (
                        self.security_context.current_user.id
                        if self.security_context
                        else None
                    )
                    self.event_bus.publish(
                        RecurrencePatternCreated(
                            pattern_id=recurrence_pattern.id,
                            recurring_project_id=recurring_project.id,
                            frequency=recurrence_pattern_data.get(
                                "frequency", "custom"
                            ),
                            user_id=user_id,
                        )
                    )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    RecurringProjectCreated(
                        recurring_project_id=recurring_project.id,
                        template_id=template_id,
                        name=recurring_project.name,
                        user_id=user_id,
                    )
                )

            # Return combined result
            result = recurring_project.to_dict()
            if recurrence_pattern:
                result["recurrence_pattern"] = recurrence_pattern.to_dict()

                # Calculate next occurrence
                next_occurrence = self._calculate_next_occurrence(recurrence_pattern)
                if next_occurrence:
                    # Update recurring project with next occurrence
                    self.repository.update(
                        recurring_project.id, {"nextOccurrence": next_occurrence}
                    )
                    result["nextOccurrence"] = next_occurrence

            return result

    def update_recurring_project(
        self, recurring_project_id: str, data: Dict[str, Any]
    ) -> RecurringProject:
        """
        Update an existing recurring project.

        Args:
            recurring_project_id: ID of the recurring project to update
            data: Updated recurring project data

        Returns:
            Updated recurring project entity

        Raises:
            EntityNotFoundException: If recurring project not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.get_by_id(recurring_project_id)
            if not recurring_project:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("RecurringProject", recurring_project_id)

            # Track changes for events
            changes = {}
            for key, value in data.items():
                if (
                    hasattr(recurring_project, key)
                    and getattr(recurring_project, key) != value
                ):
                    changes[key] = {
                        "old": getattr(recurring_project, key),
                        "new": value,
                    }

            # Update modified timestamp
            data["modifiedAt"] = datetime.now()

            # Update recurring project
            updated_project = self.repository.update(recurring_project_id, data)

            # Publish event if event bus exists and there are changes
            if changes and self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    RecurringProjectUpdated(
                        recurring_project_id=recurring_project_id,
                        changes=changes,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(
                    f"RecurringProject:{recurring_project_id}"
                )

            return updated_project

    def update_recurrence_pattern(
        self, pattern_id: str, data: Dict[str, Any]
    ) -> RecurrencePattern:
        """
        Update an existing recurrence pattern.

        Args:
            pattern_id: ID of the recurrence pattern to update
            data: Updated recurrence pattern data

        Returns:
            Updated recurrence pattern entity

        Raises:
            EntityNotFoundException: If pattern not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if pattern exists
            pattern = self.pattern_repository.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("RecurrencePattern", pattern_id)

            # Track changes for events
            changes = {}
            for key, value in data.items():
                if hasattr(pattern, key) and getattr(pattern, key) != value:
                    changes[key] = {"old": getattr(pattern, key), "new": value}

            # Update pattern
            updated_pattern = self.pattern_repository.update(pattern_id, data)

            # Calculate next occurrence if frequency-related fields changed
            frequency_fields = [
                "frequency",
                "interval",
                "startDate",
                "endDate",
                "daysOfWeek",
                "dayOfMonth",
                "weekOfMonth",
                "month",
                "customDates",
            ]

            if any(field in changes for field in frequency_fields):
                next_occurrence = self._calculate_next_occurrence(updated_pattern)

                # Update recurring project with next occurrence
                if next_occurrence and hasattr(pattern, "recurring_project_id"):
                    self.repository.update(
                        pattern.recurring_project_id,
                        {
                            "nextOccurrence": next_occurrence,
                            "modifiedAt": datetime.now(),
                        },
                    )

            # Publish event if event bus exists and there are changes
            if changes and self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    RecurrencePatternUpdated(
                        pattern_id=pattern_id,
                        recurring_project_id=(
                            updated_pattern.recurring_project_id
                            if hasattr(updated_pattern, "recurring_project_id")
                            else None
                        ),
                        changes=changes,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service and hasattr(pattern, "recurring_project_id"):
                self.cache_service.invalidate(
                    f"RecurringProject:{pattern.recurring_project_id}"
                )
                self.cache_service.invalidate(f"RecurrencePattern:{pattern_id}")

            return updated_pattern

    def delete_recurring_project(
        self, recurring_project_id: str, delete_generated: bool = False
    ) -> bool:
        """
        Delete a recurring project.

        Args:
            recurring_project_id: ID of the recurring project to delete
            delete_generated: Whether to delete already generated projects

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.get_by_id(recurring_project_id)
            if not recurring_project:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("RecurringProject", recurring_project_id)

            # Store name for event
            name = (
                recurring_project.name
                if hasattr(recurring_project, "name")
                else f"Project {recurring_project_id}"
            )

            # Delete associated pattern(s)
            patterns = self.pattern_repository.list(
                recurring_project_id=recurring_project_id
            )
            for pattern in patterns:
                self.pattern_repository.delete(pattern.id)

            # Delete generated projects if requested
            if delete_generated:
                generated_projects = self.generated_project_repository.list(
                    recurring_project_id=recurring_project_id
                )

                for generated in generated_projects:
                    # Delete the actual project if project service is available
                    if (
                        hasattr(generated, "project_id")
                        and generated.project_id
                        and self.project_service
                    ):
                        try:
                            self.project_service.delete_project(generated.project_id)
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete generated project {generated.project_id}: {str(e)}"
                            )

                    # Delete the generated project record
                    self.generated_project_repository.delete(generated.id)

            # Delete recurring project
            result = self.repository.delete(recurring_project_id)

            # Publish event if event bus exists and deletion was successful
            if result and self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    RecurringProjectDeleted(
                        recurring_project_id=recurring_project_id,
                        name=name,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(
                    f"RecurringProject:{recurring_project_id}"
                )
                self.cache_service.invalidate("RecurringProjects:all")

            return result

    def get_recurring_project_with_details(
        self, recurring_project_id: str
    ) -> Dict[str, Any]:
        """
        Get a recurring project with its pattern and generated projects.

        Args:
            recurring_project_id: ID of the recurring project

        Returns:
            Recurring project with pattern and generated projects

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"RecurringProject:{recurring_project_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get recurring project
        recurring_project = self.get_by_id(recurring_project_id)
        if not recurring_project:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("RecurringProject", recurring_project_id)

        # Convert to dict
        result = recurring_project.to_dict()

        # Get recurrence pattern
        patterns = self.pattern_repository.list(
            recurring_project_id=recurring_project_id
        )
        if patterns:
            # Typically, there's only one pattern per recurring project
            result["recurrence_pattern"] = patterns[0].to_dict()

        # Get generated projects
        generated_projects = self.generated_project_repository.list(
            recurring_project_id=recurring_project_id,
            sort_by="occurrenceNumber",
            sort_dir="asc",
        )

        # Organize generated projects by status
        result["generated_projects"] = {
            "scheduled": [],
            "generated": [],
            "skipped": [],
            "failed": [],
        }

        for generated in generated_projects:
            gen_dict = generated.to_dict()

            # Get project details if available
            if (
                hasattr(generated, "project_id")
                and generated.project_id
                and self.project_service
            ):
                try:
                    project = self.project_service.get_by_id(generated.project_id)
                    if project:
                        gen_dict["project"] = {
                            "id": project.id,
                            "name": project.name if hasattr(project, "name") else None,
                            "status": (
                                project.status if hasattr(project, "status") else None
                            ),
                            "completionPercentage": (
                                project.completionPercentage
                                if hasattr(project, "completionPercentage")
                                else None
                            ),
                        }
                except Exception as e:
                    logger.warning(f"Failed to get project details: {str(e)}")

            # Add to appropriate status category
            status = generated.status if hasattr(generated, "status") else "scheduled"
            if status in result["generated_projects"]:
                result["generated_projects"][status].append(gen_dict)

        # Add generation statistics
        total_count = len(generated_projects)
        generated_count = sum(
            1
            for g in generated_projects
            if hasattr(g, "status") and g.status == "generated"
        )
        skipped_count = sum(
            1
            for g in generated_projects
            if hasattr(g, "status") and g.status == "skipped"
        )
        failed_count = sum(
            1
            for g in generated_projects
            if hasattr(g, "status") and g.status == "failed"
        )

        result["statistics"] = {
            "total_count": total_count,
            "generated_count": generated_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "success_rate": (
                (generated_count / total_count * 100) if total_count > 0 else 0
            ),
            "next_occurrence": (
                recurring_project.nextOccurrence
                if hasattr(recurring_project, "nextOccurrence")
                else None
            ),
            "last_occurrence": (
                recurring_project.lastOccurrence
                if hasattr(recurring_project, "lastOccurrence")
                else None
            ),
        }

        # Get template details if available
        if (
            hasattr(recurring_project, "templateId")
            and recurring_project.templateId
            and self.template_service
        ):
            try:
                template = self.template_service.get_by_id(recurring_project.templateId)
                if template:
                    result["template"] = {
                        "id": template.id,
                        "name": template.name if hasattr(template, "name") else None,
                        "projectType": (
                            template.projectType
                            if hasattr(template, "projectType")
                            else None
                        ),
                        "skillLevel": (
                            template.skillLevel
                            if hasattr(template, "skillLevel")
                            else None
                        ),
                        "estimatedDuration": (
                            template.estimatedDuration
                            if hasattr(template, "estimatedDuration")
                            else None
                        ),
                    }
            except Exception as e:
                logger.warning(f"Failed to get template details: {str(e)}")

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def get_active_recurring_projects(self) -> List[RecurringProject]:
        """
        Get all active recurring projects.

        Returns:
            List of active recurring projects
        """
        return self.repository.list(isActive=True)

    def get_projects_due_for_generation(
        self, days_ahead: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get recurring projects that are due for generation.

        Args:
            days_ahead: Optional days ahead to look for projects to generate

        Returns:
            List of recurring projects due for generation
        """
        # Get active recurring projects
        projects = self.get_active_recurring_projects()

        # Filter for projects with auto-generate enabled
        projects = [
            p for p in projects if hasattr(p, "autoGenerate") and p.autoGenerate
        ]

        # Filter for projects with upcoming occurrences
        today = datetime.now().date()

        result = []
        for project in projects:
            # Skip if no next occurrence
            if not hasattr(project, "nextOccurrence") or not project.nextOccurrence:
                continue

            next_occurrence = project.nextOccurrence
            if isinstance(next_occurrence, str):
                next_occurrence = datetime.fromisoformat(next_occurrence).date()
            elif isinstance(next_occurrence, datetime):
                next_occurrence = next_occurrence.date()

            # Get advance notice days
            advance_notice = (
                project.advanceNoticeDays
                if hasattr(project, "advanceNoticeDays")
                else 7
            )
            if days_ahead is not None:
                advance_notice = days_ahead

            # Check if next occurrence is within advance notice period
            if next_occurrence <= today + timedelta(days=advance_notice):
                project_dict = project.to_dict()
                project_dict["days_until_occurrence"] = (next_occurrence - today).days
                result.append(project_dict)

        return result

    def generate_project(
        self, recurring_project_id: str, scheduled_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a project instance from a recurring project.

        Args:
            recurring_project_id: ID of the recurring project
            scheduled_date: Optional specific date to generate for

        Returns:
            Dictionary with generation result

        Raises:
            EntityNotFoundException: If recurring project not found
            BusinessRuleException: If project cannot be generated
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.get_by_id(recurring_project_id)
            if not recurring_project:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("RecurringProject", recurring_project_id)

            # Check if project is active
            if (
                not hasattr(recurring_project, "isActive")
                or not recurring_project.isActive
            ):
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Cannot generate project from inactive recurring project",
                    "RECURRING_PROJECT_001",
                )

            # Get recurrence pattern
            patterns = self.pattern_repository.list(
                recurring_project_id=recurring_project_id
            )
            if not patterns:
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Recurring project has no recurrence pattern",
                    "RECURRING_PROJECT_002",
                )

            pattern = patterns[0]

            # Determine scheduled date if not provided
            if not scheduled_date:
                if (
                    hasattr(recurring_project, "nextOccurrence")
                    and recurring_project.nextOccurrence
                ):
                    scheduled_date = recurring_project.nextOccurrence
                    if isinstance(scheduled_date, str):
                        scheduled_date = datetime.fromisoformat(scheduled_date)
                    elif isinstance(scheduled_date, date):
                        scheduled_date = datetime.combine(
                            scheduled_date, datetime.min.time()
                        )
                else:
                    # Calculate next occurrence
                    scheduled_date = self._calculate_next_occurrence(pattern)
                    if not scheduled_date:
                        from app.core.exceptions import BusinessRuleException

                        raise BusinessRuleException(
                            "No valid next occurrence found for recurring project",
                            "RECURRING_PROJECT_003",
                        )

                    if isinstance(scheduled_date, date):
                        scheduled_date = datetime.combine(
                            scheduled_date, datetime.min.time()
                        )

            # Get occurrence number
            generated_projects = self.generated_project_repository.list(
                recurring_project_id=recurring_project_id,
                sort_by="occurrenceNumber",
                sort_dir="desc",
                limit=1,
            )

            occurrence_number = 1
            if generated_projects:
                last_occurrence = generated_projects[0]
                occurrence_number = (
                    last_occurrence.occurrenceNumber
                    if hasattr(last_occurrence, "occurrenceNumber")
                    else 0
                ) + 1

            # Check if we've reached the maximum occurrences
            if (
                hasattr(pattern, "endAfterOccurrences")
                and pattern.endAfterOccurrences
                and occurrence_number > pattern.endAfterOccurrences
            ):
                # Update recurring project to inactive
                self.repository.update(
                    recurring_project_id,
                    {"isActive": False, "modifiedAt": datetime.now()},
                )

                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    f"Maximum number of occurrences ({pattern.endAfterOccurrences}) reached",
                    "RECURRING_PROJECT_004",
                )

            # Check if date is within pattern bounds
            if (
                hasattr(pattern, "endDate")
                and pattern.endDate
                and scheduled_date.date() > pattern.endDate
            ):
                # Update recurring project to inactive
                self.repository.update(
                    recurring_project_id,
                    {"isActive": False, "modifiedAt": datetime.now()},
                )

                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    f"Scheduled date {scheduled_date.date()} is after pattern end date {pattern.endDate}",
                    "RECURRING_PROJECT_005",
                )

            # Check if we should skip this occurrence (weekend/holiday)
            skip_reason = None
            if hasattr(pattern, "skipWeekends") and pattern.skipWeekends:
                if scheduled_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                    skip_reason = (
                        f"Skipped weekend occurrence on {scheduled_date.date()}"
                    )

            # TODO: Add holiday check if holiday calendar is available

            # Create GeneratedProject record
            generated_project_data = {
                "id": str(uuid.uuid4()),
                "recurringProjectId": recurring_project_id,
                "occurrenceNumber": occurrence_number,
                "scheduledDate": scheduled_date,
                "actualGenerationDate": datetime.now() if not skip_reason else None,
                "status": "skipped" if skip_reason else "scheduled",
                "notes": skip_reason,
            }

            generated_project = self.generated_project_repository.create(
                generated_project_data
            )

            # Generate the actual project if not skipped and project service is available
            if not skip_reason and self.project_service:
                try:
                    # Get project data from template if template service is available
                    project_data = {}

                    if (
                        hasattr(recurring_project, "templateId")
                        and recurring_project.templateId
                        and self.template_service
                    ):
                        try:
                            template_data = (
                                self.template_service.get_template_with_components(
                                    recurring_project.templateId
                                )
                            )
                            if template_data:
                                # Copy relevant template fields
                                for field in [
                                    "name",
                                    "description",
                                    "projectType",
                                    "skillLevel",
                                    "estimatedDuration",
                                    "estimatedCost",
                                ]:
                                    if field in template_data:
                                        project_data[field] = template_data[field]

                                # Copy components if available
                                if "components" in template_data:
                                    project_data["components"] = template_data[
                                        "components"
                                    ]
                        except Exception as e:
                            logger.warning(f"Failed to get template data: {str(e)}")

                    # Add required project fields
                    project_data["name"] = self._generate_project_name(
                        recurring_project, occurrence_number
                    )
                    project_data["type"] = (
                        recurring_project.projectType
                        if hasattr(recurring_project, "projectType")
                        else None
                    )
                    project_data["startDate"] = scheduled_date.date()

                    # Calculate due date based on duration
                    duration = (
                        recurring_project.duration
                        if hasattr(recurring_project, "duration")
                        else 7
                    )
                    project_data["dueDate"] = (
                        scheduled_date + timedelta(days=duration)
                    ).date()

                    # Add client if specified
                    if (
                        hasattr(recurring_project, "clientId")
                        and recurring_project.clientId
                    ):
                        project_data["customerId"] = recurring_project.clientId

                    # Create project
                    project = self.project_service.create_project(project_data)

                    # Update generated project with project ID
                    self.generated_project_repository.update(
                        generated_project.id,
                        {"projectId": project.id, "status": "generated"},
                    )

                    # Update generated project with project reference
                    generated_project = self.generated_project_repository.get_by_id(
                        generated_project.id
                    )

                    # Publish event if event bus exists
                    if self.event_bus:
                        self.event_bus.publish(
                            ProjectGenerated(
                                generated_project_id=generated_project.id,
                                recurring_project_id=recurring_project_id,
                                project_id=project.id,
                                scheduled_date=scheduled_date,
                                occurrence_number=occurrence_number,
                            )
                        )
                except Exception as e:
                    logger.error(f"Failed to generate project: {str(e)}", exc_info=True)

                    # Update generated project to reflect failure
                    self.generated_project_repository.update(
                        generated_project.id,
                        {"status": "failed", "notes": f"Generation failed: {str(e)}"},
                    )

                    # Publish failure event if event bus exists
                    if self.event_bus:
                        self.event_bus.publish(
                            GenerationFailed(
                                recurring_project_id=recurring_project_id,
                                scheduled_date=scheduled_date,
                                occurrence_number=occurrence_number,
                                error=str(e),
                            )
                        )

                    # Don't raise exception, just return failure result
                    return {
                        "success": False,
                        "recurring_project_id": recurring_project_id,
                        "generated_project_id": generated_project.id,
                        "scheduled_date": scheduled_date,
                        "occurrence_number": occurrence_number,
                        "status": "failed",
                        "error": str(e),
                    }

            # Update recurring project with last/next occurrence
            updates = {"lastOccurrence": scheduled_date, "modifiedAt": datetime.now()}

            # Calculate next occurrence if necessary
            if recurring_project.isActive:
                next_occurrence = self._calculate_next_occurrence(
                    pattern, start_from=scheduled_date + timedelta(days=1)
                )
                if next_occurrence:
                    updates["nextOccurrence"] = next_occurrence

            self.repository.update(recurring_project_id, updates)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(
                    f"RecurringProject:{recurring_project_id}"
                )

            # Return success result
            return {
                "success": True,
                "recurring_project_id": recurring_project_id,
                "generated_project_id": generated_project.id,
                "project_id": (
                    generated_project.projectId
                    if hasattr(generated_project, "projectId")
                    else None
                ),
                "scheduled_date": scheduled_date,
                "occurrence_number": occurrence_number,
                "status": (
                    generated_project.status
                    if hasattr(generated_project, "status")
                    else None
                ),
                "skipped": skip_reason is not None,
                "skip_reason": skip_reason,
                "next_occurrence": updates.get("nextOccurrence"),
            }

    def run_scheduled_generation(self, days_ahead: int = None) -> Dict[str, Any]:
        """
        Run scheduled generation for all active recurring projects.

        This is typically called by a scheduled job.

        Args:
            days_ahead: Optional days ahead to look for projects to generate

        Returns:
            Dictionary with generation results
        """
        # Get projects due for generation
        due_projects = self.get_projects_due_for_generation(days_ahead)

        results = {
            "total": len(due_projects),
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        }

        # Generate projects
        for project in due_projects:
            try:
                result = self.generate_project(project["id"])
                results["details"].append(result)

                if result.get("success"):
                    if result.get("skipped"):
                        results["skipped"] += 1
                    else:
                        results["succeeded"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to generate project {project['id']}: {str(e)}",
                    exc_info=True,
                )
                results["failed"] += 1
                results["details"].append(
                    {
                        "success": False,
                        "recurring_project_id": project["id"],
                        "error": str(e),
                    }
                )

        return results

    def skip_occurrence(self, recurring_project_id: str, reason: str) -> Dict[str, Any]:
        """
        Skip the next occurrence of a recurring project.

        Args:
            recurring_project_id: ID of the recurring project
            reason: Reason for skipping

        Returns:
            Dictionary with skip result

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.get_by_id(recurring_project_id)
            if not recurring_project:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("RecurringProject", recurring_project_id)

            # Get next occurrence date
            if (
                not hasattr(recurring_project, "nextOccurrence")
                or not recurring_project.nextOccurrence
            ):
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "No next occurrence found for recurring project",
                    "RECURRING_PROJECT_006",
                )

            next_occurrence = recurring_project.nextOccurrence
            if isinstance(next_occurrence, str):
                next_occurrence = datetime.fromisoformat(next_occurrence)
            elif isinstance(next_occurrence, date):
                next_occurrence = datetime.combine(next_occurrence, datetime.min.time())

            # Get occurrence number
            generated_projects = self.generated_project_repository.list(
                recurring_project_id=recurring_project_id,
                sort_by="occurrenceNumber",
                sort_dir="desc",
                limit=1,
            )

            occurrence_number = 1
            if generated_projects:
                last_occurrence = generated_projects[0]
                occurrence_number = (
                    last_occurrence.occurrenceNumber
                    if hasattr(last_occurrence, "occurrenceNumber")
                    else 0
                ) + 1

            # Create skipped GeneratedProject record
            generated_project_data = {
                "id": str(uuid.uuid4()),
                "recurringProjectId": recurring_project_id,
                "occurrenceNumber": occurrence_number,
                "scheduledDate": next_occurrence,
                "actualGenerationDate": datetime.now(),
                "status": "skipped",
                "notes": f"Manually skipped: {reason}",
            }

            generated_project = self.generated_project_repository.create(
                generated_project_data
            )

            # Get recurrence pattern
            patterns = self.pattern_repository.list(
                recurring_project_id=recurring_project_id
            )
            if not patterns:
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Recurring project has no recurrence pattern",
                    "RECURRING_PROJECT_002",
                )

            pattern = patterns[0]

            # Calculate next occurrence after the skipped one
            next_occurrence = self._calculate_next_occurrence(
                pattern, start_from=next_occurrence + timedelta(days=1)
            )

            # Update recurring project with last/next occurrence
            updates = {
                "lastOccurrence": recurring_project.nextOccurrence,
                "nextOccurrence": next_occurrence,
                "modifiedAt": datetime.now(),
            }

            self.repository.update(recurring_project_id, updates)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(
                    f"RecurringProject:{recurring_project_id}"
                )

            return {
                "recurring_project_id": recurring_project_id,
                "generated_project_id": generated_project.id,
                "skipped_date": next_occurrence,
                "occurrence_number": occurrence_number,
                "reason": reason,
                "next_occurrence": next_occurrence,
            }

    def activate_recurring_project(self, recurring_project_id: str) -> RecurringProject:
        """
        Activate a recurring project.

        Args:
            recurring_project_id: ID of the recurring project

        Returns:
            Activated recurring project entity

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.get_by_id(recurring_project_id)
            if not recurring_project:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("RecurringProject", recurring_project_id)

            # If already active, return as is
            if hasattr(recurring_project, "isActive") and recurring_project.isActive:
                return recurring_project

            # Get recurrence pattern
            patterns = self.pattern_repository.list(
                recurring_project_id=recurring_project_id
            )
            if not patterns:
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Recurring project has no recurrence pattern",
                    "RECURRING_PROJECT_002",
                )

            pattern = patterns[0]

            # Calculate next occurrence
            next_occurrence = self._calculate_next_occurrence(pattern)

            # Update recurring project
            return self.update_recurring_project(
                recurring_project_id,
                {"isActive": True, "nextOccurrence": next_occurrence},
            )

    def deactivate_recurring_project(
        self, recurring_project_id: str
    ) -> RecurringProject:
        """
        Deactivate a recurring project.

        Args:
            recurring_project_id: ID of the recurring project

        Returns:
            Deactivated recurring project entity

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        # Just update isActive flag
        return self.update_recurring_project(recurring_project_id, {"isActive": False})

    def get_occurrences_calendar(
        self, recurring_project_id: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get a calendar of occurrences for a recurring project.

        Args:
            recurring_project_id: ID of the recurring project
            start_date: Start date of the calendar range
            end_date: End date of the calendar range

        Returns:
            List of occurrence dates with details

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        # Check if recurring project exists
        recurring_project = self.get_by_id(recurring_project_id)
        if not recurring_project:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("RecurringProject", recurring_project_id)

        # Get recurrence pattern
        patterns = self.pattern_repository.list(
            recurring_project_id=recurring_project_id
        )
        if not patterns:
            return []

        pattern = patterns[0]

        # Get already generated projects in the date range
        generated_projects = self.generated_project_repository.list(
            recurring_project_id=recurring_project_id,
            scheduledDate_gte=start_date,
            scheduledDate_lte=end_date,
            sort_by="scheduledDate",
            sort_dir="asc",
        )

        # Map existing projects by date
        existing_by_date = {}
        for gen in generated_projects:
            scheduled_date = gen.scheduledDate
            if isinstance(scheduled_date, datetime):
                scheduled_date = scheduled_date.date()
            elif isinstance(scheduled_date, str):
                scheduled_date = datetime.fromisoformat(scheduled_date).date()

            date_str = scheduled_date.isoformat()
            existing_by_date[date_str] = gen

        # Calculate occurrences in the date range
        occurrences = []
        current_date = start_date.date()
        end_date = end_date.date()

        while current_date <= end_date:
            date_str = current_date.isoformat()

            # If occurrence already exists on this date, use it
            if date_str in existing_by_date:
                gen = existing_by_date[date_str]

                occurrence = {
                    "date": date_str,
                    "generated_project_id": gen.id,
                    "occurrence_number": (
                        gen.occurrenceNumber
                        if hasattr(gen, "occurrenceNumber")
                        else None
                    ),
                    "status": gen.status if hasattr(gen, "status") else None,
                    "generated": hasattr(gen, "status") and gen.status == "generated",
                    "skipped": hasattr(gen, "status") and gen.status == "skipped",
                    "project_id": gen.projectId if hasattr(gen, "projectId") else None,
                    "notes": gen.notes if hasattr(gen, "notes") else None,
                }

                # Add project status if available
                if hasattr(gen, "projectId") and gen.projectId and self.project_service:
                    try:
                        project = self.project_service.get_by_id(gen.projectId)
                        if project:
                            occurrence["project_status"] = (
                                project.status if hasattr(project, "status") else None
                            )
                            occurrence["project_completion"] = (
                                project.completionPercentage
                                if hasattr(project, "completionPercentage")
                                else None
                            )
                    except Exception as e:
                        logger.warning(f"Failed to get project status: {str(e)}")

                occurrences.append(occurrence)

            # Otherwise, check if this date is an occurrence according to pattern
            elif self._is_occurrence_date(pattern, current_date):
                # Check if this would be skipped due to weekend/holiday
                skip_reason = None
                if hasattr(pattern, "skipWeekends") and pattern.skipWeekends:
                    if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                        skip_reason = f"Weekend occurrence on {current_date}"

                # TODO: Add holiday check

                occurrences.append(
                    {
                        "date": date_str,
                        "generated": False,
                        "skipped": skip_reason is not None,
                        "skip_reason": skip_reason,
                        "scheduled": True,
                        "status": "scheduled",
                    }
                )

            current_date += timedelta(days=1)

        return occurrences

    def _calculate_next_occurrence(
        self, pattern: RecurrencePattern, start_from: Optional[datetime] = None
    ) -> Optional[date]:
        """
        Calculate the next occurrence date based on recurrence pattern.

        Args:
            pattern: Recurrence pattern to use
            start_from: Optional start date (defaults to today)

        Returns:
            Next occurrence date or None if no more occurrences
        """
        # Get frequency and interval
        frequency = pattern.frequency if hasattr(pattern, "frequency") else "daily"
        interval = pattern.interval if hasattr(pattern, "interval") else 1

        # Get start and end dates
        start_date = pattern.startDate if hasattr(pattern, "startDate") else None
        end_date = pattern.endDate if hasattr(pattern, "endDate") else None

        # If no start date, can't calculate occurrences
        if not start_date:
            return None

        # Use provided start date or today
        if not start_from:
            start_from = datetime.now()

        current_date = start_from.date()

        # End date check
        if end_date and current_date > end_date:
            return None

        # Make sure we don't start before the pattern start date
        if current_date < start_date:
            current_date = start_date

        # Custom dates pattern
        if frequency == "custom":
            custom_dates = (
                pattern.customDates
                if hasattr(pattern, "customDates") and pattern.customDates
                else []
            )
            if not custom_dates:
                return None

            # Convert to date objects if they're strings
            parsed_dates = []
            for d in custom_dates:
                if isinstance(d, str):
                    parsed_dates.append(datetime.fromisoformat(d).date())
                elif isinstance(d, datetime):
                    parsed_dates.append(d.date())
                else:
                    parsed_dates.append(d)

            # Sort dates
            parsed_dates.sort()

            # Find next date after current_date
            for d in parsed_dates:
                if d >= current_date:
                    return d

            # No more dates
            return None

        # Daily pattern
        elif frequency == "daily":
            # Start with current date
            result_date = current_date

            # If not already an occurrence date, advance to the next one
            if not self._is_occurrence_date(pattern, result_date):
                days_to_add = 1
                while days_to_add < 366:  # Safety limit
                    result_date = current_date + timedelta(days=days_to_add)

                    # Check if valid occurrence
                    if self._is_occurrence_date(pattern, result_date):
                        break

                    days_to_add += 1
                else:
                    # No valid occurrence found within limit
                    return None

            return result_date

        # Weekly pattern
        elif frequency == "weekly":
            days_of_week = (
                pattern.daysOfWeek
                if hasattr(pattern, "daysOfWeek") and pattern.daysOfWeek
                else [0]
            )  # Default to Monday

            # Find next matching day of week
            days_checked = 0
            result_date = current_date

            while days_checked < 7 * interval:
                # Check if current day is in days_of_week
                if result_date.weekday() in days_of_week:
                    # Check other conditions (skip weekends, etc.)
                    if self._is_occurrence_date(pattern, result_date):
                        return result_date

                # Advance to next day
                result_date += timedelta(days=1)
                days_checked += 1

            # If we get here, no valid occurrence was found
            return None

        # Monthly pattern
        elif frequency == "monthly":
            day_of_month = (
                pattern.dayOfMonth if hasattr(pattern, "dayOfMonth") else None
            )
            week_of_month = (
                pattern.weekOfMonth if hasattr(pattern, "weekOfMonth") else None
            )

            # Current month
            current_month = current_date.month
            current_year = current_date.year

            # Try for up to 12 months
            for month_offset in range(12):
                # Calculate target month and year
                target_month = (current_month - 1 + interval * month_offset) % 12 + 1
                target_year = (
                    current_year + (current_month - 1 + interval * month_offset) // 12
                )

                # Get last day of month
                last_day = calendar.monthrange(target_year, target_month)[1]

                # Specific day of month
                if day_of_month:
                    # Handle "last day of month" case (-1)
                    if day_of_month == -1:
                        result_day = last_day
                    else:
                        result_day = min(day_of_month, last_day)

                    result_date = date(target_year, target_month, result_day)

                    # Skip if before current date
                    if result_date < current_date:
                        continue

                    # Check other conditions
                    if self._is_occurrence_date(pattern, result_date):
                        return result_date

                # Specific week of month
                elif week_of_month:
                    # Find first day of month
                    first_day = date(target_year, target_month, 1)

                    # Find first occurrence of each day of week
                    first_occurrences = {}
                    for dow in range(7):
                        days_to_add = (dow - first_day.weekday()) % 7
                        first_occurrences[dow] = date(
                            target_year, target_month, 1 + days_to_add
                        )

                    # Find target day based on week_of_month
                    # week_of_month: 1-4 = specific week, -1 = last occurrence
                    days_of_week = (
                        pattern.daysOfWeek
                        if hasattr(pattern, "daysOfWeek") and pattern.daysOfWeek
                        else [0]
                    )  # Default to Monday

                    for dow in days_of_week:
                        if week_of_month == -1:
                            # Last occurrence of this day in month
                            last_occurrence = first_occurrences[dow]
                            while last_occurrence.month == target_month:
                                candidate = last_occurrence + timedelta(days=7)
                                if candidate.month != target_month:
                                    break
                                last_occurrence = candidate

                            result_date = last_occurrence
                        else:
                            # Specific week
                            result_date = first_occurrences[dow] + timedelta(
                                days=7 * (week_of_month - 1)
                            )

                        # Skip if before current date
                        if result_date < current_date:
                            continue

                        # Skip if not in target month
                        if result_date.month != target_month:
                            continue

                        # Check other conditions
                        if self._is_occurrence_date(pattern, result_date):
                            return result_date

                # Default to the same day of month
                else:
                    day = min(current_date.day, last_day)
                    result_date = date(target_year, target_month, day)

                    # Skip if before current date
                    if result_date < current_date:
                        continue

                    # Check other conditions
                    if self._is_occurrence_date(pattern, result_date):
                        return result_date

            # No valid occurrence found within limit
            return None

        # Yearly pattern
        elif frequency == "yearly":
            month = pattern.month if hasattr(pattern, "month") else current_date.month
            day_of_month = (
                pattern.dayOfMonth
                if hasattr(pattern, "dayOfMonth")
                else current_date.day
            )

            # Try for up to 5 years
            for year_offset in range(5):
                target_year = current_date.year + year_offset * interval

                # Get last day of target month
                last_day = calendar.monthrange(target_year, month)[1]
                day = min(day_of_month, last_day)

                result_date = date(target_year, month, day)

                # Skip if before current date
                if result_date < current_date:
                    continue

                # Check other conditions
                if self._is_occurrence_date(pattern, result_date):
                    return result_date

            # No valid occurrence found within limit
            return None

        # Quarterly pattern
        elif frequency == "quarterly":
            day_of_month = pattern.dayOfMonth if hasattr(pattern, "dayOfMonth") else 1

            # Current quarter
            current_quarter = (current_date.month - 1) // 3 + 1

            # Try for up to 4 quarters
            for quarter_offset in range(4):
                # Calculate target quarter
                target_quarter = (
                    current_quarter - 1 + interval * quarter_offset
                ) % 4 + 1
                target_year = (
                    current_date.year
                    + (current_quarter - 1 + interval * quarter_offset) // 4
                )

                # Calculate month for target quarter (1=Jan, 4=Apr, 7=Jul, 10=Oct)
                target_month = (target_quarter - 1) * 3 + 1

                # Get last day of month
                last_day = calendar.monthrange(target_year, target_month)[1]

                # Handle "last day of month" case (-1)
                if day_of_month == -1:
                    day = last_day
                else:
                    day = min(day_of_month, last_day)

                result_date = date(target_year, target_month, day)

                # Skip if before current date
                if result_date < current_date:
                    continue

                # Check other conditions
                if self._is_occurrence_date(pattern, result_date):
                    return result_date

            # No valid occurrence found within limit
            return None

        # Unknown frequency
        return None

    def _is_occurrence_date(self, pattern: RecurrencePattern, check_date: date) -> bool:
        """
        Check if a date is a valid occurrence according to pattern.

        Args:
            pattern: Recurrence pattern to use
            check_date: Date to check

        Returns:
            True if the date is a valid occurrence
        """
        # Check pattern bounds
        start_date = pattern.startDate if hasattr(pattern, "startDate") else None
        end_date = pattern.endDate if hasattr(pattern, "endDate") else None

        if start_date and check_date < start_date:
            return False

        if end_date and check_date > end_date:
            return False

        # Check frequency-specific rules
        frequency = pattern.frequency if hasattr(pattern, "frequency") else "daily"
        interval = pattern.interval if hasattr(pattern, "interval") else 1

        # Custom dates pattern
        if frequency == "custom":
            custom_dates = (
                pattern.customDates
                if hasattr(pattern, "customDates") and pattern.customDates
                else []
            )

            # Convert any string or datetime to date
            parsed_dates = []
            for d in custom_dates:
                if isinstance(d, str):
                    parsed_dates.append(datetime.fromisoformat(d).date())
                elif isinstance(d, datetime):
                    parsed_dates.append(d.date())
                else:
                    parsed_dates.append(d)

            return check_date in parsed_dates

        # Daily pattern
        elif frequency == "daily":
            # Check interval
            if start_date:
                days_since_start = (check_date - start_date).days
                if days_since_start % interval != 0:
                    return False

        # Weekly pattern
        elif frequency == "weekly":
            # Check day of week
            days_of_week = (
                pattern.daysOfWeek
                if hasattr(pattern, "daysOfWeek") and pattern.daysOfWeek
                else [0]
            )  # Default to Monday
            if check_date.weekday() not in days_of_week:
                return False

            # Check interval
            if start_date:
                days_since_start = (check_date - start_date).days
                weeks_since_start = days_since_start // 7
                if weeks_since_start % interval != 0:
                    return False

        # Monthly pattern
        elif frequency == "monthly":
            # Check if we have a day_of_month specification
            day_of_month = (
                pattern.dayOfMonth if hasattr(pattern, "dayOfMonth") else None
            )
            week_of_month = (
                pattern.weekOfMonth if hasattr(pattern, "weekOfMonth") else None
            )

            # Get month information
            last_day = calendar.monthrange(check_date.year, check_date.month)[1]

            # Check day of month
            if day_of_month:
                # Handle "last day of month" case (-1)
                if day_of_month == -1:
                    if check_date.day != last_day:
                        return False
                elif check_date.day != day_of_month:
                    return False

            # Check week of month
            elif week_of_month:
                # Find first day of month
                first_day = date(check_date.year, check_date.month, 1)

                # Calculate week of month for the check date
                days_of_week = (
                    pattern.daysOfWeek
                    if hasattr(pattern, "daysOfWeek") and pattern.daysOfWeek
                    else [0]
                )

                # Check if day of week matches
                if check_date.weekday() not in days_of_week:
                    return False

                # Calculate the week of month
                first_occurrence = first_day
                while first_occurrence.weekday() != check_date.weekday():
                    first_occurrence += timedelta(days=1)

                # Calculate which occurrence of this weekday it is
                occurrence_number = (check_date.day - first_occurrence.day) // 7 + 1

                # Last occurrence is special case
                if week_of_month == -1:
                    # Check if this is the last occurrence of this weekday in the month
                    next_occurrence = check_date + timedelta(days=7)
                    if next_occurrence.month == check_date.month:
                        return False
                elif occurrence_number != week_of_month:
                    return False

            # Check interval
            if start_date:
                months_since_start = (
                    (check_date.year - start_date.year) * 12
                    + check_date.month
                    - start_date.month
                )
                if months_since_start % interval != 0:
                    return False

        # Yearly pattern
        elif frequency == "yearly":
            month = (
                pattern.month
                if hasattr(pattern, "month")
                else start_date.month if start_date else 1
            )
            day_of_month = (
                pattern.dayOfMonth
                if hasattr(pattern, "dayOfMonth")
                else start_date.day if start_date else 1
            )

            # Check month
            if check_date.month != month:
                return False

            # Check day
            if day_of_month != -1 and check_date.day != day_of_month:
                return False
            elif day_of_month == -1:
                # Last day of month
                last_day = calendar.monthrange(check_date.year, check_date.month)[1]
                if check_date.day != last_day:
                    return False

            # Check interval
            if start_date:
                years_since_start = check_date.year - start_date.year
                if years_since_start % interval != 0:
                    return False

        # Quarterly pattern
        elif frequency == "quarterly":
            # Check if it's the first month of a quarter (Jan, Apr, Jul, Oct)
            if check_date.month not in [1, 4, 7, 10]:
                return False

            # Check day of month
            day_of_month = pattern.dayOfMonth if hasattr(pattern, "dayOfMonth") else 1

            if day_of_month == -1:
                # Last day of month
                last_day = calendar.monthrange(check_date.year, check_date.month)[1]
                if check_date.day != last_day:
                    return False
            elif check_date.day != day_of_month:
                return False

            # Check interval
            if start_date:
                start_quarter = (start_date.month - 1) // 3 + 1
                check_quarter = (check_date.month - 1) // 3 + 1

                quarters_since_start = (
                    (check_date.year - start_date.year) * 4
                    + check_quarter
                    - start_quarter
                )
                if quarters_since_start % interval != 0:
                    return False

        # Check weekend skipping
        if hasattr(pattern, "skipWeekends") and pattern.skipWeekends:
            if check_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                return False

        # TODO: Add holiday checking

        # All checks passed
        return True

    def _generate_project_name(
        self, recurring_project: RecurringProject, occurrence_number: int
    ) -> str:
        """
        Generate a name for a project instance.

        Args:
            recurring_project: Recurring project
            occurrence_number: Occurrence number

        Returns:
            Generated project name
        """
        base_name = (
            recurring_project.name
            if hasattr(recurring_project, "name")
            else "Recurring Project"
        )
        suffix = (
            recurring_project.projectSuffix
            if hasattr(recurring_project, "projectSuffix")
            else None
        )

        if suffix:
            # Replace placeholders in suffix
            suffix = suffix.replace("{number}", str(occurrence_number))
            suffix = suffix.replace("{date}", datetime.now().strftime("%Y-%m-%d"))

            return f"{base_name} {suffix}"
        else:
            return f"{base_name} (#{occurrence_number})"
