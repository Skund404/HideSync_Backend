# app/services/recurring_project_service.py
"""
Recurring Project service for HideSync.

This module provides functionality for managing recurring projects,
recurrence patterns, and automatic project generation.
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, date, timedelta
import uuid
import calendar
import logging
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
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
from app.services.project_service import ProjectService
from app.core.events import DomainEvent
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    ValidationException,
)

logger = logging.getLogger(__name__)


class RecurringProjectCreated(DomainEvent):
    """Event emitted when a recurring project is created."""

    def __init__(
        self, project_id: str, project_name: str, user_id: Optional[str] = None
    ):
        super().__init__()
        self.project_id = project_id
        self.project_name = project_name
        self.user_id = user_id


class ProjectGenerated(DomainEvent):
    """Event emitted when a project is generated from a recurring project."""

    def __init__(
        self,
        recurring_project_id: str,
        project_id: str,
        scheduled_date: date,
        user_id: Optional[str] = None,
    ):
        super().__init__()
        self.recurring_project_id = recurring_project_id
        self.project_id = project_id
        self.scheduled_date = scheduled_date
        self.user_id = user_id


class RecurringProjectService(BaseService[RecurringProject]):
    """
    Service for managing recurring projects in the HideSync system.

    Provides functionality for:
    - Recurring project management
    - Recurrence pattern definition and calculation
    - Automatic project generation based on schedules
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        recurrence_pattern_repository=None,
        generated_project_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        project_service=None,
    ):
        """
        Initialize RecurringProjectService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for recurring projects
            recurrence_pattern_repository: Optional repository for recurrence patterns
            generated_project_repository: Optional repository for generated projects
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            project_service: Optional project service for project generation
        """
        self.session = session
        self.repository = repository or RecurringProjectRepository(session)
        self.recurrence_pattern_repository = (
            recurrence_pattern_repository or RecurrencePatternRepository(session)
        )
        self.generated_project_repository = (
            generated_project_repository or GeneratedProjectRepository(session)
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.project_service = project_service or ProjectService(session)

    def create_recurring_project(
        self, data: Dict[str, Any], user_id: str = None
    ) -> RecurringProject:
        """
        Create a new recurring project with its recurrence pattern.

        Args:
            data: Recurring project data with recurrence pattern
            user_id: ID of the user creating the project

        Returns:
            Created recurring project entity

        Raises:
            ValidationException: If data validation fails
            BusinessRuleException: If project creation violates business rules
        """
        with self.transaction():
            # Extract recurrence pattern data
            pattern_data = data.pop("recurrence_pattern", None)
            if not pattern_data:
                raise ValidationException(
                    "Recurrence pattern is required",
                    {"recurrence_pattern": ["This field is required"]},
                )

            # Create recurrence pattern
            pattern_data["id"] = str(uuid.uuid4())
            pattern = self.recurrence_pattern_repository.create(pattern_data)

            # Prepare recurring project data
            project_data = data.copy()
            project_data["id"] = str(uuid.uuid4())
            project_data["recurrence_pattern_id"] = pattern.id
            project_data["created_by"] = user_id

            # Calculate next occurrence
            next_occurrence = self._calculate_next_occurrence(pattern)
            project_data["next_occurrence"] = next_occurrence

            # Create recurring project
            recurring_project = self.repository.create(project_data)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    RecurringProjectCreated(
                        project_id=recurring_project.id,
                        project_name=recurring_project.name,
                        user_id=user_id,
                    )
                )

            return recurring_project

    def update_recurring_project(
        self, project_id: str, data: Dict[str, Any], user_id: str = None
    ) -> RecurringProject:
        """
        Update an existing recurring project and optionally its recurrence pattern.

        Args:
            project_id: ID of the recurring project to update
            data: Updated recurring project data
            user_id: ID of the user updating the project

        Returns:
            Updated recurring project entity

        Raises:
            EntityNotFoundException: If recurring project not found
            ValidationException: If data validation fails
            BusinessRuleException: If update violates business rules
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.repository.get_by_id(project_id)
            if not recurring_project:
                raise EntityNotFoundException("RecurringProject", project_id)

            # Extract recurrence pattern data if provided
            pattern_data = data.pop("recurrence_pattern", None)
            if pattern_data:
                # Update recurrence pattern
                pattern = self.recurrence_pattern_repository.update(
                    recurring_project.recurrence_pattern_id, pattern_data
                )

                # Recalculate next occurrence
                pattern = self.recurrence_pattern_repository.get_by_id(
                    recurring_project.recurrence_pattern_id
                )
                next_occurrence = self._calculate_next_occurrence(pattern)
                data["next_occurrence"] = next_occurrence

            # Update recurring project
            updated_project = self.repository.update(project_id, data)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"RecurringProject:{project_id}")

            return updated_project

    def delete_recurring_project(self, project_id: str, user_id: str = None) -> bool:
        """
        Delete a recurring project.

        Args:
            project_id: ID of the recurring project to delete
            user_id: ID of the user deleting the project

        Returns:
            True if project was deleted

        Raises:
            EntityNotFoundException: If recurring project not found
            BusinessRuleException: If deletion violates business rules
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.repository.get_by_id(project_id)
            if not recurring_project:
                raise EntityNotFoundException("RecurringProject", project_id)

            # Delete associated generated projects (or mark them as orphaned)
            generated_projects = self.generated_project_repository.list(
                recurring_project_id=project_id
            )
            for gen_project in generated_projects:
                self.generated_project_repository.update(
                    gen_project.id, {"status": "orphaned"}
                )

            # Store pattern ID for later deletion
            pattern_id = recurring_project.recurrence_pattern_id

            # Delete recurring project
            result = self.repository.delete(project_id)

            # Delete recurrence pattern
            self.recurrence_pattern_repository.delete(pattern_id)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"RecurringProject:{project_id}")

            return result

    def get_recurring_project_with_details(self, project_id: str) -> Dict[str, Any]:
        """
        Get a recurring project with additional details.

        Args:
            project_id: ID of the recurring project

        Returns:
            Recurring project with details including recurrence pattern and upcoming occurrences

        Raises:
            EntityNotFoundException: If recurring project not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"RecurringProject:detail:{project_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get recurring project
        recurring_project = self.repository.get_by_id(project_id)
        if not recurring_project:
            raise EntityNotFoundException("RecurringProject", project_id)

        # Get recurrence pattern
        pattern = self.recurrence_pattern_repository.get_by_id(
            recurring_project.recurrence_pattern_id
        )
        if not pattern:
            raise EntityNotFoundException(
                "RecurrencePattern", recurring_project.recurrence_pattern_id
            )

        # Calculate upcoming occurrences
        upcoming_occurrences = self._calculate_upcoming_occurrences(pattern, limit=10)

        # Get generated projects
        generated_projects = self.generated_project_repository.list(
            recurring_project_id=project_id, limit=100
        )

        # Prepare result
        result = {
            **recurring_project.__dict__,
            "recurrence_pattern": pattern.__dict__,
            "upcoming_occurrences": upcoming_occurrences,
            "generated_projects": [gp.__dict__ for gp in generated_projects],
        }

        # Remove SQLAlchemy internal attributes
        if "_sa_instance_state" in result:
            result.pop("_sa_instance_state")
        if "_sa_instance_state" in result["recurrence_pattern"]:
            result["recurrence_pattern"].pop("_sa_instance_state")
        for gp in result["generated_projects"]:
            if "_sa_instance_state" in gp:
                gp.pop("_sa_instance_state")

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def list_recurring_projects(
        self, skip: int = 0, limit: int = 100, **filters
    ) -> List[RecurringProject]:
        """
        List recurring projects with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filters (is_active, project_type, etc.)

        Returns:
            List of recurring projects
        """
        return self.repository.list(skip=skip, limit=limit, **filters)

    def generate_project_instance(
        self,
        project_id: str,
        scheduled_date_str: Optional[str] = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """
        Generate a project instance from a recurring project.

        Args:
            project_id: ID of the recurring project
            scheduled_date_str: Optional specific date for generation (YYYY-MM-DD)
            user_id: ID of the user generating the project

        Returns:
            Generated project instance

        Raises:
            EntityNotFoundException: If recurring project not found
            ValidationException: If data validation fails
            BusinessRuleException: If generation violates business rules
        """
        with self.transaction():
            # Check if recurring project exists
            recurring_project = self.repository.get_by_id(project_id)
            if not recurring_project:
                raise EntityNotFoundException("RecurringProject", project_id)

            # Check if recurring project is active
            if not recurring_project.is_active:
                raise BusinessRuleException(
                    "Cannot generate project from inactive recurring project"
                )

            # Get recurrence pattern
            pattern = self.recurrence_pattern_repository.get_by_id(
                recurring_project.recurrence_pattern_id
            )
            if not pattern:
                raise EntityNotFoundException(
                    "RecurrencePattern", recurring_project.recurrence_pattern_id
                )

            # Determine scheduled date
            if scheduled_date_str:
                try:
                    scheduled_date = datetime.strptime(
                        scheduled_date_str, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    raise ValidationException(
                        "Invalid date format",
                        {"scheduled_date": ["Must be in YYYY-MM-DD format"]},
                    )
            else:
                # Use next occurrence
                scheduled_date = recurring_project.next_occurrence
                if not scheduled_date:
                    # Calculate next occurrence
                    scheduled_date = self._calculate_next_occurrence(pattern)
                    if not scheduled_date:
                        raise BusinessRuleException(
                            "No upcoming occurrences available for this recurring project"
                        )

            # Check if a project was already generated for this date
            existing_generated = self.generated_project_repository.find_by_date(
                recurring_project_id=project_id, scheduled_date=scheduled_date
            )
            if existing_generated:
                raise BusinessRuleException(
                    f"A project was already generated for {scheduled_date} (ID: {existing_generated.project_id})"
                )

            # Get occurrence number
            occurrence_number = recurring_project.total_occurrences + 1

            # Generate project name with occurrence information
            project_name = f"{recurring_project.name} #{occurrence_number}"
            if recurring_project.project_suffix:
                project_name = f"{project_name} {recurring_project.project_suffix}"

            # Create project data
            project_data = {
                "name": project_name,
                "description": recurring_project.description,
                "type": recurring_project.project_type,
                "status": "PLANNING",  # Start in planning status
                "start_date": scheduled_date,
                "due_date": scheduled_date
                + timedelta(days=7),  # Default to 7 days duration
                "template_id": recurring_project.template_id,
            }

            # Add client/customer if available
            if recurring_project.client_id:
                project_data["customer_id"] = recurring_project.client_id

            # Create the actual project
            project = self.project_service.create_project(project_data, user_id)

            # Record the generated project
            generated_project_data = {
                "id": str(uuid.uuid4()),
                "recurring_project_id": recurring_project.id,
                "project_id": project.id,
                "occurrence_number": occurrence_number,
                "scheduled_date": scheduled_date,
                "actual_generation_date": datetime.now(),
                "status": "generated",
            }
            generated_project = self.generated_project_repository.create(
                generated_project_data
            )

            # Update recurring project with new total and last/next occurrence
            update_data = {
                "total_occurrences": occurrence_number,
                "last_occurrence": scheduled_date,
            }

            # Calculate next occurrence after this one
            next_occurrence = self._calculate_next_occurrence(
                pattern, after_date=scheduled_date
            )
            if next_occurrence:
                update_data["next_occurrence"] = next_occurrence

            self.repository.update(project_id, update_data)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    ProjectGenerated(
                        recurring_project_id=recurring_project.id,
                        project_id=project.id,
                        scheduled_date=scheduled_date,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"RecurringProject:{project_id}")

            return generated_project

    def get_upcoming_recurring_projects(
        self, days: int = 7, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming recurring projects scheduled within the specified time frame.

        Args:
            days: Number of days to look ahead
            limit: Maximum number of projects to return

        Returns:
            List of upcoming recurring projects with details
        """
        # Get active recurring projects
        active_projects = self.repository.list(is_active=True, limit=100)

        # Filter those with upcoming occurrences in the specified period
        end_date = datetime.now().date() + timedelta(days=days)

        upcoming_projects = []
        for project in active_projects:
            # Only consider projects with a valid next occurrence
            if not project.next_occurrence or project.next_occurrence > end_date:
                continue

            # Get pattern
            pattern = self.recurrence_pattern_repository.get_by_id(
                project.recurrence_pattern_id
            )
            if not pattern:
                continue

            # Calculate upcoming occurrences in the period
            occurrences = self._calculate_upcoming_occurrences(
                pattern, start_date=datetime.now().date(), end_date=end_date, limit=5
            )

            if occurrences:
                upcoming_projects.append(
                    {
                        **project.__dict__,
                        "recurrence_pattern": pattern.__dict__,
                        "upcoming_occurrences": occurrences,
                    }
                )

                # Remove SQLAlchemy internal attributes
                if "_sa_instance_state" in upcoming_projects[-1]:
                    upcoming_projects[-1].pop("_sa_instance_state")
                if "_sa_instance_state" in upcoming_projects[-1]["recurrence_pattern"]:
                    upcoming_projects[-1]["recurrence_pattern"].pop(
                        "_sa_instance_state"
                    )

        # Sort by next occurrence date
        upcoming_projects.sort(key=lambda p: p["next_occurrence"])

        return upcoming_projects[:limit]

    def get_projects_due_this_week(self) -> List[RecurringProject]:
        """
        Get recurring projects with occurrences due this week.

        Returns:
            List of recurring projects with occurrences due this week
        """
        # Calculate this week's date range
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # Get active projects with next occurrence in this week
        filters = {
            "is_active": True,
            "next_occurrence_gte": start_of_week,
            "next_occurrence_lte": end_of_week,
        }

        return self.repository.list(**filters)

    def get_recurring_project_count(self) -> Dict[str, int]:
        """
        Get count of recurring projects by status.

        Returns:
            Dictionary with counts by status
        """
        total = self.repository.count()
        active = self.repository.count(is_active=True)
        inactive = self.repository.count(is_active=False)

        # Get projects with upcoming occurrences in the next week
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        upcoming = self.repository.count(
            is_active=True,
            next_occurrence_lte=next_week,
        )

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "upcoming_week": upcoming,
        }

    # app/services/recurring_project_service.py (continued)

    def _calculate_next_occurrence(
        self, pattern: RecurrencePattern, after_date: Optional[date] = None
    ) -> Optional[date]:
        """
        Calculate the next occurrence date for a recurrence pattern.

        Args:
            pattern: Recurrence pattern
            after_date: Optional date to calculate next occurrence after

        Returns:
            Next occurrence date or None if no future occurrences
        """
        # Use today if no after_date is provided
        today = after_date or datetime.now().date()

        # Check pattern end conditions
        if pattern.end_date and today > pattern.end_date:
            return None

        # Start from pattern start date or the day after after_date
        start_from = max(pattern.start_date, today + timedelta(days=1))

        if pattern.frequency == "daily":
            next_date = self._calculate_daily_occurrence(pattern, start_from)
        elif pattern.frequency == "weekly":
            next_date = self._calculate_weekly_occurrence(pattern, start_from)
        elif pattern.frequency == "monthly":
            next_date = self._calculate_monthly_occurrence(pattern, start_from)
        elif pattern.frequency == "quarterly":
            next_date = self._calculate_quarterly_occurrence(pattern, start_from)
        elif pattern.frequency == "yearly":
            next_date = self._calculate_yearly_occurrence(pattern, start_from)
        elif pattern.frequency == "custom":
            next_date = self._calculate_custom_occurrence(pattern, start_from)
        else:
            # Default to daily if unknown frequency
            next_date = self._calculate_daily_occurrence(pattern, start_from)

        # Apply weekend/holiday skipping if configured
        if next_date and (pattern.skip_weekends or pattern.skip_holidays):
            next_date = self._apply_skipping_rules(pattern, next_date)

        # Check end conditions
        if pattern.end_date and next_date > pattern.end_date:
            return None

        return next_date

    def _calculate_daily_occurrence(
        self, pattern: RecurrencePattern, start_from: date
    ) -> date:
        """Calculate next daily occurrence."""
        # For daily frequency, simply add interval days
        return start_from + timedelta(days=pattern.interval)

    def _calculate_weekly_occurrence(
        self, pattern: RecurrencePattern, start_from: date
    ) -> date:
        """Calculate next weekly occurrence."""
        # If no specific days of week, use the same day of week as start date
        if not pattern.days_of_week:
            # Add interval weeks
            return start_from + timedelta(days=7 * pattern.interval)

        # Convert Python's weekday (0-6, Monday=0) to pattern's days_of_week (often 0-6, Sunday=0)
        # Adjust as needed based on your system's conventions
        current_weekday = start_from.weekday()
        # Convert to Sunday=0 format if that's what's used in days_of_week
        current_day_of_week = (current_weekday + 1) % 7

        # Find the next allowed day of week
        allowed_days = sorted([day % 7 for day in pattern.days_of_week])

        # Find the next day in the current week
        next_day = None
        for day in allowed_days:
            if day > current_day_of_week:
                next_day = day
                break

        # If no next day found in current week, go to next week
        if next_day is None:
            next_day = allowed_days[0]
            weeks_to_add = pattern.interval
        else:
            weeks_to_add = 0

        # Calculate days to add
        days_to_add = (next_day - current_day_of_week) % 7
        days_to_add += 7 * weeks_to_add

        return start_from + timedelta(days=days_to_add)

    def _calculate_monthly_occurrence(
        self, pattern: RecurrencePattern, start_from: date
    ) -> date:
        """Calculate next monthly occurrence."""
        # If day of month is specified
        if pattern.day_of_month:
            # Get the next occurrence date by adding months and setting the day
            month = start_from.month + pattern.interval
            year = start_from.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1  # Adjust month to be 1-12

            # Calculate the actual day considering month length
            _, last_day = calendar.monthrange(year, month)
            day = min(pattern.day_of_month, last_day)

            return date(year, month, day)

        # If week of month and day of week are specified
        elif pattern.week_of_month is not None and pattern.days_of_week:
            # Currently handling only the first day in days_of_week
            day_of_week = pattern.days_of_week[0] % 7

            # Add interval months to start_from
            month = start_from.month + pattern.interval
            year = start_from.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1  # Adjust month to be 1-12

            # Find the first day of the specified day of week in the month
            first_day = date(year, month, 1)
            days_to_add = (day_of_week - first_day.weekday()) % 7
            first_occurrence = first_day + timedelta(days=days_to_add)

            # Add weeks based on week_of_month (0-based)
            result = first_occurrence + timedelta(days=7 * pattern.week_of_month)

            # Check if the result is still in the same month
            if result.month != month:
                # If not, go back to the last occurrence in the month
                result = result - timedelta(days=7)

            return result

        # Default: same day of month as start_from
        else:
            month = start_from.month + pattern.interval
            year = start_from.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1  # Adjust month to be 1-12

            # Calculate the actual day considering month length
            _, last_day = calendar.monthrange(year, month)
            day = min(start_from.day, last_day)

            return date(year, month, day)

    def _calculate_quarterly_occurrence(
        self, pattern: RecurrencePattern, start_from: date
    ) -> date:
        """Calculate next quarterly occurrence."""
        # Quarterly is just a special case of monthly with interval = 3
        monthly_pattern = RecurrencePattern(
            id=pattern.id,
            name=pattern.name,
            frequency="monthly",
            interval=3 * pattern.interval,
            start_date=pattern.start_date,
            end_date=pattern.end_date,
            end_after_occurrences=pattern.end_after_occurrences,
            days_of_week=pattern.days_of_week,
            day_of_month=pattern.day_of_month,
            week_of_month=pattern.week_of_month,
            month=pattern.month,
            custom_dates=pattern.custom_dates,
            skip_weekends=pattern.skip_weekends,
            skip_holidays=pattern.skip_holidays,
        )
        return self._calculate_monthly_occurrence(monthly_pattern, start_from)

    def _calculate_yearly_occurrence(
        self, pattern: RecurrencePattern, start_from: date
    ) -> date:
        """Calculate next yearly occurrence."""
        # If month and day are specified
        if pattern.month:
            month = pattern.month

            # Use day_of_month if specified, otherwise use the same day as start_date
            if pattern.day_of_month:
                day = pattern.day_of_month
            else:
                day = pattern.start_date.day

            # Calculate next yearly occurrence
            year = start_from.year

            # If this year's date has passed, move to next interval
            if (month, day) < (start_from.month, start_from.day):
                year += pattern.interval
            else:
                year += pattern.interval - 1

            # Adjust for leap year
            if month == 2 and day == 29 and not calendar.isleap(year):
                day = 28

            return date(year, month, day)

        # Default: same month and day as start_date
        else:
            year = start_from.year + pattern.interval
            month = pattern.start_date.month
            day = pattern.start_date.day

            # Adjust for leap year
            if month == 2 and day == 29 and not calendar.isleap(year):
                day = 28

            return date(year, month, day)

    def _calculate_custom_occurrence(
        self, pattern: RecurrencePattern, start_from: date
    ) -> Optional[date]:
        """Calculate next custom occurrence."""
        # Custom patterns use explicit dates
        if not pattern.custom_dates:
            return None

        # Find the next date after start_from
        future_dates = [d for d in pattern.custom_dates if d > start_from]
        if not future_dates:
            return None

        return min(future_dates)

    def _apply_skipping_rules(
        self, pattern: RecurrencePattern, occurrence_date: date
    ) -> date:
        """
        Apply weekend and holiday skipping rules to an occurrence date.

        Args:
            pattern: Recurrence pattern
            occurrence_date: Date to check

        Returns:
            Adjusted date that respects skipping rules
        """
        result_date = occurrence_date

        # Skip weekends if configured
        if pattern.skip_weekends:
            # Check if the date falls on a weekend
            weekday = result_date.weekday()
            if weekday >= 5:  # 5 = Saturday, 6 = Sunday
                # Skip to Monday
                days_to_add = 7 - weekday
                result_date = result_date + timedelta(days=days_to_add)

        # Skip holidays if configured
        if pattern.skip_holidays:
            # In a real implementation, this would check a holiday calendar
            # For now, we'll just check a hardcoded list of common US holidays
            is_holiday = self._is_holiday(result_date)
            while is_holiday:
                result_date = result_date + timedelta(days=1)
                is_holiday = self._is_holiday(result_date)

        return result_date

    def _is_holiday(self, check_date: date) -> bool:
        """
        Check if a date is a holiday.

        Args:
            check_date: Date to check

        Returns:
            True if the date is a holiday
        """
        # In a real implementation, this would check a holiday database
        # For demonstration, we'll check a few common US holidays

        year = check_date.year

        # New Year's Day
        if check_date == date(year, 1, 1):
            return True

        # Independence Day
        if check_date == date(year, 7, 4):
            return True

        # Christmas
        if check_date == date(year, 12, 25):
            return True

        # Add more holiday checks as needed

        return False

    def _calculate_upcoming_occurrences(
        self,
        pattern: RecurrencePattern,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 5,
    ) -> List[date]:
        """
        Calculate a list of upcoming occurrences based on a recurrence pattern.

        Args:
            pattern: Recurrence pattern
            start_date: Optional start date (defaults to today)
            end_date: Optional end date
            limit: Maximum number of occurrences to return

        Returns:
            List of upcoming occurrence dates
        """
        occurrences = []
        current_date = start_date or datetime.now().date()

        # Loop until we have enough occurrences or reach end conditions
        while len(occurrences) < limit:
            next_date = self._calculate_next_occurrence(pattern, current_date)

            # Stop if no more occurrences
            if not next_date:
                break

            # Stop if we've reached the end date
            if end_date and next_date > end_date:
                break

            occurrences.append(next_date)
            current_date = next_date

        return occurrences
