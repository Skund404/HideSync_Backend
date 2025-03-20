# File: services/timeline_task_service.py

"""
Timeline task management service for the HideSync system.

This module provides functionality for managing timeline tasks associated with projects.
It handles task creation, scheduling, dependencies, status management, and notifications
to enable effective project timeline management and progress tracking.

Timeline tasks represent individual work items that need to be completed within a project,
with specific start and end dates, potential dependencies, and progression tracking.
The service enables craftspeople to plan their work, track progress, and meet deadlines.

Key features:
- Task creation and assignment
- Scheduling with start and end dates
- Task dependency management
- Progress tracking and status updates
- Critical path identification and management
- Timeline visualization data preparation
- Notifications for upcoming and overdue tasks
- Integration with project management

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with the
project service and notification service.
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime, timedelta
import logging
import uuid
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException
)
from app.core.validation import validate_input, validate_entity
from app.db.models.timeline_task import TimelineTask
from app.repositories.timeline_task_repository import TimelineTaskRepository
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class TaskCreated(DomainEvent):
    """Event emitted when a timeline task is created."""

    def __init__(self, task_id: str, project_id: str,
                 task_name: str, user_id: Optional[int] = None):
        """
        Initialize task created event.

        Args:
            task_id: ID of the created task
            project_id: ID of the associated project
            task_name: Name of the task
            user_id: Optional ID of the user who created the task
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.task_name = task_name
        self.user_id = user_id


class TaskUpdated(DomainEvent):
    """Event emitted when a timeline task is updated."""

    def __init__(self, task_id: str, project_id: str,
                 changes: Dict[str, Any], user_id: Optional[int] = None):
        """
        Initialize task updated event.

        Args:
            task_id: ID of the updated task
            project_id: ID of the associated project
            changes: Dictionary of changed fields
            user_id: Optional ID of the user who updated the task
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.changes = changes
        self.user_id = user_id


class TaskDeleted(DomainEvent):
    """Event emitted when a timeline task is deleted."""

    def __init__(self, task_id: str, project_id: str,
                 task_name: str, user_id: Optional[int] = None):
        """
        Initialize task deleted event.

        Args:
            task_id: ID of the deleted task
            project_id: ID of the associated project
            task_name: Name of the task
            user_id: Optional ID of the user who deleted the task
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.task_name = task_name
        self.user_id = user_id


class TaskStatusChanged(DomainEvent):
    """Event emitted when a task's status changes."""

    def __init__(self, task_id: str, project_id: str,
                 previous_status: str, new_status: str,
                 task_name: str, user_id: Optional[int] = None):
        """
        Initialize task status changed event.

        Args:
            task_id: ID of the task
            project_id: ID of the associated project
            previous_status: Previous status value
            new_status: New status value
            task_name: Name of the task
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.task_name = task_name
        self.user_id = user_id


class TaskProgressUpdated(DomainEvent):
    """Event emitted when a task's progress is updated."""

    def __init__(self, task_id: str, project_id: str,
                 previous_progress: int, new_progress: int,
                 task_name: str, user_id: Optional[int] = None):
        """
        Initialize task progress updated event.

        Args:
            task_id: ID of the task
            project_id: ID of the associated project
            previous_progress: Previous progress percentage
            new_progress: New progress percentage
            task_name: Name of the task
            user_id: Optional ID of the user who updated the progress
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.previous_progress = previous_progress
        self.new_progress = new_progress
        self.task_name = task_name
        self.user_id = user_id


class TaskDueSoon(DomainEvent):
    """Event emitted when a task is due soon."""

    def __init__(self, task_id: str, project_id: str,
                 task_name: str, due_date: datetime, days_remaining: int):
        """
        Initialize task due soon event.

        Args:
            task_id: ID of the task
            project_id: ID of the associated project
            task_name: Name of the task
            due_date: Due date of the task
            days_remaining: Number of days remaining until the task is due
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.task_name = task_name
        self.due_date = due_date
        self.days_remaining = days_remaining


class TaskOverdue(DomainEvent):
    """Event emitted when a task becomes overdue."""

    def __init__(self, task_id: str, project_id: str,
                 task_name: str, due_date: datetime, days_overdue: int):
        """
        Initialize task overdue event.

        Args:
            task_id: ID of the task
            project_id: ID of the associated project
            task_name: Name of the task
            due_date: Due date of the task
            days_overdue: Number of days the task is overdue
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.task_name = task_name
        self.due_date = due_date
        self.days_overdue = days_overdue


# Validation functions
validate_timeline_task = validate_entity(TimelineTask)


class TimelineTaskService(BaseService[TimelineTask]):
    """
    Service for managing timeline tasks in the HideSync system.

    Provides functionality for:
    - Task creation and management
    - Scheduling and dependencies
    - Progress tracking
    - Timeline visualization
    - Due date monitoring
    - Critical path management
    """

    def __init__(self, session: Session, repository=None,
                 security_context=None, event_bus=None, cache_service=None,
                 project_service=None, notification_service=None):
        """
        Initialize TimelineTaskService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for timeline tasks
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            project_service: Optional service for project operations
            notification_service: Optional service for sending notifications
        """
        self.session = session
        self.repository = repository or TimelineTaskRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.project_service = project_service
        self.notification_service = notification_service

    @validate_input(validate_timeline_task)
    def create_task(self, data: Dict[str, Any]) -> TimelineTask:
        """
        Create a new timeline task.

        Args:
            data: Task data with required fields
                Required fields:
                - project_id: ID of the project this task belongs to
                - name: Name of the task
                - startDate: Start date of the task
                - endDate: End date of the task
                Optional fields:
                - status: Task status (defaults to "NOT_STARTED")
                - progress: Progress percentage (defaults to 0)
                - dependencies: List of task IDs this task depends on
                - isCriticalPath: Whether this task is on the critical path
                - assignedTo: Person assigned to the task

        Returns:
            Created timeline task entity

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If referenced project not found
        """
        with self.transaction():
            # Check if project exists if project service is available
            project_id = data.get('project_id')
            if project_id and self.project_service:
                project = self.project_service.get_by_id(project_id)
                if not project:
                    from app.core.exceptions import EntityNotFoundException
                    raise EntityNotFoundException("Project", project_id)

            # Generate ID if not provided
            if 'id' not in data:
                data['id'] = str(uuid.uuid4())

            # Set default values if not provided
            if 'status' not in data:
                data['status'] = "NOT_STARTED"

            if 'progress' not in data:
                data['progress'] = 0

            # Validate start and end dates
            start_date = data.get('startDate')
            end_date = data.get('endDate')

            if start_date and end_date and start_date > end_date:
                raise ValidationException(
                    "End date must be after start date",
                    {"endDate": ["End date must be after start date"]}
                )

            # Validate dependencies if provided
            dependencies = data.get('dependencies', [])
            if dependencies:
                self._validate_dependencies(dependencies, project_id)

            # Create task
            task = self.repository.create(data)

            # Update critical path if needed
            if data.get('isCriticalPath'):
                self._update_project_critical_path(project_id, task.id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = self.security_context.current_user.id if self.security_context else None
                self.event_bus.publish(TaskCreated(
                    task_id=task.id,
                    project_id=project_id,
                    task_name=task.name,
                    user_id=user_id
                ))

            # Send notification if notification service exists
            if self.notification_service:
                self._send_task_assigned_notification(task)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:timeline:{project_id}")

            return task

    def update_task(self, task_id: str, data: Dict[str, Any]) -> TimelineTask:
        """
        Update an existing timeline task.

        Args:
            task_id: ID of the task to update
            data: Updated task data

        Returns:
            Updated timeline task entity

        Raises:
            EntityNotFoundException: If task not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if task exists
            task = self.get_by_id(task_id)
            if not task:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("TimelineTask", task_id)

            # Store original values for events
            original_status = task.status if hasattr(task, 'status') else None
            original_progress = task.progress if hasattr(task, 'progress') else 0
            project_id = task.project_id
            task_name = task.name if hasattr(task, 'name') else f"Task {task_id}"

            # Validate start and end dates if both are provided
            start_date = data.get('startDate')
            end_date = data.get('endDate')

            if start_date and end_date and start_date > end_date:
                raise ValidationException(
                    "End date must be after start date",
                    {"endDate": ["End date must be after start date"]}
                )

            # Validate dependencies if provided
            dependencies = data.get('dependencies')
            if dependencies:
                self._validate_dependencies(dependencies, project_id, exclude_task_id=task_id)

            # Track changes for events
            changes = {}
            for key, value in data.items():
                if hasattr(task, key) and getattr(task, key) != value:
                    changes[key] = {
                        'old': getattr(task, key),
                        'new': value
                    }

            # Update task
            updated_task = self.repository.update(task_id, data)

            # Emit events based on changes
            if self.event_bus:
                user_id = self.security_context.current_user.id if self.security_context else None

                # General update event
                if changes:
                    self.event_bus.publish(TaskUpdated(
                        task_id=task_id,
                        project_id=project_id,
                        changes=changes,
                        user_id=user_id
                    ))

                # Status change event
                new_status = data.get('status')
                if new_status and new_status != original_status:
                    self.event_bus.publish(TaskStatusChanged(
                        task_id=task_id,
                        project_id=project_id,
                        previous_status=original_status,
                        new_status=new_status,
                        task_name=task_name,
                        user_id=user_id
                    ))

                # Progress change event
                new_progress = data.get('progress')
                if new_progress is not None and new_progress != original_progress:
                    self.event_bus.publish(TaskProgressUpdated(
                        task_id=task_id,
                        project_id=project_id,
                        previous_progress=original_progress,
                        new_progress=new_progress,
                        task_name=task_name,
                        user_id=user_id
                    ))

            # Send notifications if assignment changed
            if 'assignedTo' in data and self.notification_service:
                self._send_task_assigned_notification(updated_task)

            # If status changed to completed, update dependent tasks
            if data.get('status') == "COMPLETED" and original_status != "COMPLETED":
                self._update_dependent_tasks(task_id)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:timeline:{project_id}")
                self.cache_service.invalidate(f"TimelineTask:{task_id}")

            return updated_task

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a timeline task.

        Args:
            task_id: ID of the task to delete

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If task not found
            BusinessRuleException: If task is on the critical path
        """
        with self.transaction():
            # Check if task exists
            task = self.get_by_id(task_id)
            if not task:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("TimelineTask", task_id)

            # Check if task is on critical path
            if hasattr(task, 'isCriticalPath') and task.isCriticalPath:
                from app.core.exceptions import BusinessRuleException
                raise BusinessRuleException(
                    "Cannot delete a task on the critical path",
                    "TIMELINE_TASK_001"
                )

            # Check if other tasks depend on this one
            dependent_tasks = self._get_dependent_tasks(task_id)
            if dependent_tasks:
                task_names = [t.name if hasattr(t, 'name') else f"Task {t.id}" for t in dependent_tasks]
                from app.core.exceptions import BusinessRuleException
                raise BusinessRuleException(
                    f"Cannot delete a task that others depend on. Dependent tasks: {', '.join(task_names)}",
                    "TIMELINE_TASK_002"
                )

            # Store values for event
            project_id = task.project_id
            task_name = task.name if hasattr(task, 'name') else f"Task {task_id}"

            # Delete task
            result = self.repository.delete(task_id)

            # Publish event if event bus exists
            if result and self.event_bus:
                user_id = self.security_context.current_user.id if self.security_context else None
                self.event_bus.publish(TaskDeleted(
                    task_id=task_id,
                    project_id=project_id,
                    task_name=task_name,
                    user_id=user_id
                ))

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:timeline:{project_id}")
                self.cache_service.invalidate(f"TimelineTask:{task_id}")

            return result

    def update_task_progress(self, task_id: str, progress: int) -> TimelineTask:
        """
        Update the progress of a task.

        Args:
            task_id: ID of the task
            progress: New progress percentage (0-100)

        Returns:
            Updated timeline task entity

        Raises:
            EntityNotFoundException: If task not found
            ValidationException: If progress is invalid
        """
        # Validate progress
        if progress < 0 or progress > 100:
            raise ValidationException(
                "Progress must be between 0 and 100",
                {"progress": ["Progress must be between 0 and 100"]}
            )

        # Determine status based on progress
        status = None
        if progress == 0:
            status = "NOT_STARTED"
        elif progress == 100:
            status = "COMPLETED"
        elif progress > 0:
            status = "IN_PROGRESS"

        # Update task with progress and potentially status
        update_data = {"progress": progress}
        if status:
            update_data["status"] = status

        return self.update_task(task_id, update_data)

    def update_task_status(self, task_id: str, status: str) -> TimelineTask:
        """
        Update the status of a task.

        Args:
            task_id: ID of the task
            status: New status value

        Returns:
            Updated timeline task entity

        Raises:
            EntityNotFoundException: If task not found
        """
        # Determine progress based on status
        progress = None
        if status == "NOT_STARTED":
            progress = 0
        elif status == "COMPLETED":
            progress = 100

        # Update task with status and potentially progress
        update_data = {"status": status}
        if progress is not None:
            update_data["progress"] = progress

        return self.update_task(task_id, update_data)

    def add_dependency(self, task_id: str, dependency_id: str) -> TimelineTask:
        """
        Add a dependency to a task.

        Args:
            task_id: ID of the task
            dependency_id: ID of the task to depend on

        Returns:
            Updated timeline task entity

        Raises:
            EntityNotFoundException: If either task not found
            ValidationException: If dependency would create a cycle
        """
        with self.transaction():
            # Check if both tasks exist
            task = self.get_by_id(task_id)
            if not task:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("TimelineTask", task_id)

            dependency = self.get_by_id(dependency_id)
            if not dependency:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("TimelineTask", dependency_id)

            # Check if they're in the same project
            if task.project_id != dependency.project_id:
                raise ValidationException(
                    "Cannot add a dependency to a task in a different project",
                    {"dependency_id": ["Dependency must be in the same project"]}
                )

            # Check if dependency already exists
            current_dependencies = task.dependencies if hasattr(task, 'dependencies') and task.dependencies else []
            if dependency_id in current_dependencies:
                return task  # Already exists, no need to update

            # Check for circular dependencies
            if self._would_create_cycle(task_id, dependency_id):
                raise ValidationException(
                    "Adding this dependency would create a circular reference",
                    {"dependency_id": ["Would create a circular dependency"]}
                )

            # Add dependency
            new_dependencies = current_dependencies + [dependency_id]

            # Update task
            return self.update_task(task_id, {"dependencies": new_dependencies})

    def remove_dependency(self, task_id: str, dependency_id: str) -> TimelineTask:
        """
        Remove a dependency from a task.

        Args:
            task_id: ID of the task
            dependency_id: ID of the dependency to remove

        Returns:
            Updated timeline task entity

        Raises:
            EntityNotFoundException: If task not found
        """
        with self.transaction():
            # Check if task exists
            task = self.get_by_id(task_id)
            if not task:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("TimelineTask", task_id)

            # Check if dependency exists
            current_dependencies = task.dependencies if hasattr(task, 'dependencies') and task.dependencies else []
            if dependency_id not in current_dependencies:
                return task  # Doesn't exist, no need to update

            # Remove dependency
            new_dependencies = [d for d in current_dependencies if d != dependency_id]

            # Update task
            return self.update_task(task_id, {"dependencies": new_dependencies})

    def get_tasks_by_project(self, project_id: str) -> List[TimelineTask]:
        """
        Get all timeline tasks for a specific project.

        Args:
            project_id: ID of the project

        Returns:
            List of timeline tasks for the project
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Project:timeline:{project_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get tasks from repository
        tasks = self.repository.list(project_id=project_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, tasks, ttl=3600)  # 1 hour TTL

        return tasks

    def get_task_with_dependencies(self, task_id: str) -> Dict[str, Any]:
        """
        Get a task with its dependencies and dependent tasks.

        Args:
            task_id: ID of the task

        Returns:
            Task with dependencies and dependent tasks

        Raises:
            EntityNotFoundException: If task not found
        """
        # Check if task exists
        task = self.get_by_id(task_id)
        if not task:
            from app.core.exceptions import EntityNotFoundException
            raise EntityNotFoundException("TimelineTask", task_id)

        # Convert to dict
        result = task.to_dict()

        # Get dependencies
        dependencies = []
        if hasattr(task, 'dependencies') and task.dependencies:
            for dep_id in task.dependencies:
                dep = self.get_by_id(dep_id)
                if dep:
                    dependencies.append({
                        "id": dep.id,
                        "name": dep.name if hasattr(dep, 'name') else None,
                        "status": dep.status if hasattr(dep, 'status') else None,
                        "progress": dep.progress if hasattr(dep, 'progress') else 0,
                        "endDate": dep.endDate if hasattr(dep, 'endDate') else None
                    })

        result['dependencies_details'] = dependencies

        # Get dependent tasks
        dependent_tasks = self._get_dependent_tasks(task_id)
        result['dependent_tasks'] = [
            {
                "id": t.id,
                "name": t.name if hasattr(t, 'name') else None,
                "status": t.status if hasattr(t, 'status') else None,
                "progress": t.progress if hasattr(t, 'progress') else 0,
                "startDate": t.startDate if hasattr(t, 'startDate') else None
            }
            for t in dependent_tasks
        ]

        return result

    def update_project_timeline(self, project_id: str) -> Dict[str, Any]:
        """
        Recalculate and update the project timeline.

        This includes:
        - Recalculating the critical path
        - Adjusting task dates based on dependencies
        - Updating project start and end dates

        Args:
            project_id: ID of the project

        Returns:
            Dictionary with timeline statistics

        Raises:
            EntityNotFoundException: If project not found
        """
        with self.transaction():
            # Check if project exists if project service is available
            if self.project_service:
                project = self.project_service.get_by_id(project_id)
                if not project:
                    from app.core.exceptions import EntityNotFoundException
                    raise EntityNotFoundException("Project", project_id)

            # Get all tasks for the project
            tasks = self.get_tasks_by_project(project_id)
            if not tasks:
                return {
                    "project_id": project_id,
                    "total_tasks": 0,
                    "critical_path_tasks": 0,
                    "earliest_start": None,
                    "latest_end": None,
                    "timeline_updated": False
                }

            # Calculate critical path
            critical_path = self._calculate_critical_path(tasks)

            # Update critical path tasks
            for task in tasks:
                is_critical = task.id in critical_path
                if (not hasattr(task, 'isCriticalPath') or task.isCriticalPath != is_critical):
                    self.repository.update(task.id, {"isCriticalPath": is_critical})

            # Calculate project dates
            earliest_start = min((t.startDate for t in tasks if hasattr(t, 'startDate') and t.startDate), default=None)
            latest_end = max((t.endDate for t in tasks if hasattr(t, 'endDate') and t.endDate), default=None)

            # Update project dates if project service is available
            if self.project_service and earliest_start and latest_end:
                try:
                    self.project_service.update_project(project_id, {
                        "startDate": earliest_start,
                        "dueDate": latest_end
                    })
                except Exception as e:
                    logger.warning(f"Failed to update project dates: {str(e)}")

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:timeline:{project_id}")

            return {
                "project_id": project_id,
                "total_tasks": len(tasks),
                "critical_path_tasks": len(critical_path),
                "earliest_start": earliest_start,
                "latest_end": latest_end,
                "timeline_updated": True
            }

    def get_tasks_by_status(self, project_id: str, status: str) -> List[TimelineTask]:
        """
        Get all tasks for a project with a specific status.

        Args:
            project_id: ID of the project
            status: Status to filter by

        Returns:
            List of tasks with the specified status
        """
        return self.repository.list(project_id=project_id, status=status)

    def get_overdue_tasks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all overdue tasks.

        Args:
            project_id: Optional project ID to filter by

        Returns:
            List of overdue tasks with days overdue
        """
        today = datetime.now().date()

        # Get tasks that aren't completed and have an end date in the past
        filters = {
            "status_not": "COMPLETED",
            "endDate_lt": today
        }

        if project_id:
            filters["project_id"] = project_id

        tasks = self.repository.list(**filters)

        # Add days overdue information
        result = []
        for task in tasks:
            end_date = task.endDate if hasattr(task, 'endDate') else None
            if end_date:
                days_overdue = (today - end_date).days

                task_dict = task.to_dict()
                task_dict['days_overdue'] = days_overdue

                result.append(task_dict)

        return result

    def get_upcoming_tasks(self, days: int = 7, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get tasks due in the next specified number of days.

        Args:
            days: Number of days to look ahead
            project_id: Optional project ID to filter by

        Returns:
            List of upcoming tasks with days remaining
        """
        today = datetime.now().date()
        due_date = today + timedelta(days=days)

        # Get tasks that aren't completed and have an end date in the specified range
        filters = {
            "status_not": "COMPLETED",
            "endDate_gte": today,
            "endDate_lte": due_date
        }

        if project_id:
            filters["project_id"] = project_id

        tasks = self.repository.list(**filters)

        # Add days remaining information
        result = []
        for task in tasks:
            end_date = task.endDate if hasattr(task, 'endDate') else None
            if end_date:
                days_remaining = (end_date - today).days

                task_dict = task.to_dict()
                task_dict['days_remaining'] = days_remaining

                result.append(task_dict)

        return result

    def generate_timeline_visualization_data(self, project_id: str) -> Dict[str, Any]:
        """
        Generate data for timeline visualization.

        Args:
            project_id: ID of the project

        Returns:
            Dictionary with timeline visualization data

        Raises:
            EntityNotFoundException: If project not found
        """
        # Check if project exists if project service is available
        if self.project_service:
            project = self.project_service.get_by_id(project_id)
            if not project:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException("Project", project_id)

        # Get all tasks for the project
        tasks = self.get_tasks_by_project(project_id)

        # Transform tasks for visualization
        visualization_data = []

        for task in tasks:
            if hasattr(task, 'startDate') and hasattr(task, 'endDate'):
                task_data = {
                    "id": task.id,
                    "name": task.name if hasattr(task, 'name') else f"Task {task.id}",
                    "start": task.startDate.isoformat() if task.startDate else None,
                    "end": task.endDate.isoformat() if task.endDate else None,
                    "progress": task.progress if hasattr(task, 'progress') else 0,
                    "status": task.status if hasattr(task, 'status') else None,
                    "isCriticalPath": task.isCriticalPath if hasattr(task, 'isCriticalPath') else False,
                    "dependencies": task.dependencies if hasattr(task, 'dependencies') and task.dependencies else [],
                    "assignedTo": task.assignedTo if hasattr(task, 'assignedTo') else None
                }

                visualization_data.append(task_data)

        # Calculate project dates
        earliest_start = min((t.startDate for t in tasks if hasattr(t, 'startDate') and t.startDate), default=None)
        latest_end = max((t.endDate for t in tasks if hasattr(t, 'endDate') and t.endDate), default=None)

        return {
            "project_id": project_id,
            "project_name": project.name if hasattr(project, 'name') else None,
            "start_date": earliest_start.isoformat() if earliest_start else None,
            "end_date": latest_end.isoformat() if latest_end else None,
            "tasks": visualization_data
        }

    def check_due_tasks(self, days_threshold: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check for tasks that are due soon or overdue and generate notifications.

        This is typically called by a scheduled job.

        Args:
            days_threshold: Number of days to consider as "due soon"

        Returns:
            Dictionary with overdue and due soon tasks
        """
        today = datetime.now().date()

        # Get overdue tasks
        overdue_tasks = self.get_overdue_tasks()

        # Get tasks due soon
        due_soon_tasks = self.get_upcoming_tasks(days=days_threshold)

        # Generate notifications if notification service exists
        if self.notification_service:
            # Notifications for overdue tasks
            for task in overdue_tasks:
                days_overdue = task.get('days_overdue', 0)
                end_date = task.get('endDate')

                # Only publish event if not already notified recently
                self.event_bus.publish(TaskOverdue(
                    task_id=task.get('id'),
                    project_id=task.get('project_id'),
                    task_name=task.get('name', f"Task {task.get('id')}"),
                    due_date=end_date,
                    days_overdue=days_overdue
                ))

                # Create notification
                fallback_name = f"Task {task.get('id')}"
                self.notification_service.create_notification({
                    "user_id": task.get('assignedTo'),
                    "type": "TASK_OVERDUE",
                    "title": f"Task Overdue: {task.get('name', fallback_name)}",
                    "message": f"Task is overdue by {days_overdue} day(s). Due date was {end_date.strftime('%Y-%m-%d')}.",
                    "link": f"/projects/{task.get('project_id')}/tasks/{task.get('id')}",
                    "priority": "HIGH"
                })

            # Notifications for tasks due soon
            for task in due_soon_tasks:
                days_remaining = task.get('days_remaining', 0)
                end_date = task.get('endDate')

                # Only publish event if not already notified
                self.event_bus.publish(TaskDueSoon(
                    task_id=task.get('id'),
                    project_id=task.get('project_id'),
                    task_name=task.get('name', f"Task {task.get('id')}"),
                    due_date=end_date,
                    days_remaining=days_remaining
                ))

                # Create notification
                fallback_name = f"Task {task.get('id')}"
                self.notification_service.create_notification({
                    "user_id": task.get('assignedTo'),
                    "type": "TASK_DUE_SOON",
                    "title": f"Task Due Soon: {task.get('name', fallback_name)}",
                    "message": f"Task is due in {days_remaining} day(s). Due date is {end_date.strftime('%Y-%m-%d')}.",
                    "link": f"/projects/{task.get('project_id')}/tasks/{task.get('id')}",
                    "priority": "MEDIUM"
                })
        return {
            "overdue_tasks": overdue_tasks,
            "due_soon_tasks": due_soon_tasks
        }

    def _validate_dependencies(self, dependencies: List[str], project_id: str,
                               exclude_task_id: Optional[str] = None) -> None:
        """
        Validate that dependencies exist and are in the same project.

        Args:
            dependencies: List of task IDs
            project_id: Project ID to validate against
            exclude_task_id: Optional task ID to exclude (for updates)

        Raises:
            ValidationException: If validation fails
        """
        invalid_dependencies = []

        for dep_id in dependencies:
            # Skip self-reference for updates
            if dep_id == exclude_task_id:
                invalid_dependencies.append(dep_id)
                continue

            # Check if dependency exists
            dep = self.get_by_id(dep_id)
            if not dep:
                invalid_dependencies.append(dep_id)
                continue

            # Check if dependency is in the same project
            if dep.project_id != project_id:
                invalid_dependencies.append(dep_id)

        if invalid_dependencies:
            raise ValidationException(
                "Invalid dependencies",
                {"dependencies": [f"Invalid dependency IDs: {', '.join(invalid_dependencies)}"]}
            )

    def _would_create_cycle(self, task_id: str, dependency_id: str) -> bool:
        """
        Check if adding a dependency would create a circular reference.

        Args:
            task_id: ID of the task
            dependency_id: ID of the dependency to add

        Returns:
            True if it would create a cycle, False otherwise
        """
        # If dependency depends on task, it would create a cycle
        return self._is_dependent_on(dependency_id, task_id, set())

    def _is_dependent_on(self, task_id: str, target_id: str, visited: set) -> bool:
        """
        Recursively check if a task depends on a target task.

        Args:
            task_id: ID of the task to check
            target_id: ID of the target dependency
            visited: Set of already visited task IDs

        Returns:
            True if task depends on target, False otherwise
        """
        # Avoid infinite recursion
        if task_id in visited:
            return False

        visited.add(task_id)

        # Get task
        task = self.get_by_id(task_id)
        if not task:
            return False

        # Check dependencies
        dependencies = task.dependencies if hasattr(task, 'dependencies') and task.dependencies else []

        # Direct dependency
        if target_id in dependencies:
            return True

        # Check indirect dependencies
        for dep_id in dependencies:
            if self._is_dependent_on(dep_id, target_id, visited):
                return True

        return False

    def _get_dependent_tasks(self, task_id: str) -> List[TimelineTask]:
        """
        Get all tasks that depend on a specific task.

        Args:
            task_id: ID of the task

        Returns:
            List of tasks that depend on the specified task
        """
        # Get task to find project
        task = self.get_by_id(task_id)
        if not task:
            return []

        # Get all tasks in the same project
        project_tasks = self.get_tasks_by_project(task.project_id)

        # Filter for tasks that depend on the specified task
        dependent_tasks = []
        for t in project_tasks:
            dependencies = t.dependencies if hasattr(t, 'dependencies') and t.dependencies else []
            if task_id in dependencies:
                dependent_tasks.append(t)

        return dependent_tasks

    def _update_dependent_tasks(self, completed_task_id: str) -> None:
        """
        Update tasks that depend on a completed task.

        Args:
            completed_task_id: ID of the completed task
        """
        # Get dependent tasks
        dependent_tasks = self._get_dependent_tasks(completed_task_id)

        for task in dependent_tasks:
            # Check if all dependencies are completed
            all_dependencies_completed = True

            dependencies = task.dependencies if hasattr(task, 'dependencies') and task.dependencies else []
            for dep_id in dependencies:
                if dep_id == completed_task_id:
                    continue  # We know this one is completed

                dep = self.get_by_id(dep_id)
                if not dep or not hasattr(dep, 'status') or dep.status != "COMPLETED":
                    all_dependencies_completed = False
                    break

            # If all dependencies are completed and task hasn't started, update its status
            if all_dependencies_completed and hasattr(task, 'status') and task.status == "NOT_STARTED":
                # Update to ready status
                self.repository.update(task.id, {"status": "READY"})

                # Send notification if notification service exists
                if self.notification_service:
                    self.notification_service.create_notification({
                        "user_id": task.assignedTo if hasattr(task, 'assignedTo') else None,
                        "type": "TASK_READY",
                        "title": f"Task Ready: {task.name if hasattr(task, 'name') else f'Task {task.id}'}",
                        "message": "All dependencies are completed. This task is now ready to start.",
                        "link": f"/projects/{task.project_id}/tasks/{task.id}",
                        "priority": "LOW"
                    })

    def _calculate_critical_path(self, tasks: List[TimelineTask]) -> List[str]:
        """
        Calculate the critical path for a set of tasks.

        The critical path is the sequence of tasks that determines
        the minimum time needed to complete the project.

        Args:
            tasks: List of tasks to analyze

        Returns:
            List of task IDs on the critical path
        """
        # Build dependency graph
        graph = {}
        task_durations = {}

        for task in tasks:
            task_id = task.id

            # Skip tasks without start or end dates
            if not hasattr(task, 'startDate') or not hasattr(task, 'endDate') or not task.startDate or not task.endDate:
                continue

            # Calculate duration in days
            duration = (task.endDate - task.startDate).days + 1  # +1 to include both start and end date
            task_durations[task_id] = max(1, duration)  # Minimum duration of 1 day

            # Initialize graph entry
            if task_id not in graph:
                graph[task_id] = []

            # Add dependencies
            dependencies = task.dependencies if hasattr(task, 'dependencies') and task.dependencies else []
            for dep_id in dependencies:
                # Add task as dependent of its dependency
                if dep_id not in graph:
                    graph[dep_id] = []
                graph[dep_id].append(task_id)

        # Find start and end tasks
        start_tasks = []
        end_tasks = []

        for task_id in graph:
            # Find tasks with no dependencies
            has_dependencies = False
            for deps in graph.values():
                if task_id in deps:
                    has_dependencies = True
                    break

            if not has_dependencies:
                start_tasks.append(task_id)

            # Find tasks with no dependents
            if not graph[task_id]:
                end_tasks.append(task_id)

        # If no start or end tasks, return empty list
        if not start_tasks or not end_tasks:
            return []

        # Calculate earliest start and latest finish times
        earliest_start = {}
        latest_finish = {}

        # Forward pass - earliest start times
        for task_id in start_tasks:
            earliest_start[task_id] = 0

        # Topological sort
        visited = set()
        topo_order = []

        def dfs(node):
            visited.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
            topo_order.append(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        topo_order.reverse()

        # Calculate earliest start times
        for task_id in topo_order:
            if task_id not in earliest_start:
                earliest_start[task_id] = 0

            for dep_id in graph.get(task_id, []):
                earliest_finish = earliest_start[task_id] + task_durations.get(task_id, 0)
                if dep_id not in earliest_start or earliest_start[dep_id] < earliest_finish:
                    earliest_start[dep_id] = earliest_finish

        # Calculate project duration
        project_duration = max(
            earliest_start.get(task_id, 0) + task_durations.get(task_id, 0)
            for task_id in end_tasks
        )

        # Backward pass - latest finish times
        for task_id in end_tasks:
            latest_finish[task_id] = project_duration

        # Calculate latest finish times
        for task_id in reversed(topo_order):
            if task_id not in latest_finish:
                latest_finish[task_id] = project_duration

            latest_start = latest_finish[task_id] - task_durations.get(task_id, 0)

            for prev_id in graph:
                if task_id in graph.get(prev_id, []):
                    if prev_id not in latest_finish or latest_finish[prev_id] > latest_start:
                        latest_finish[prev_id] = latest_start

        # Find critical path (tasks with no slack)
        critical_path = []

        for task_id in graph:
            earliest_end = earliest_start.get(task_id, 0) + task_durations.get(task_id, 0)
            latest_end = latest_finish.get(task_id, 0)

            # If slack is zero, task is on critical path
            if abs(earliest_end - latest_end) < 0.01:  # Use small epsilon for floating point comparison
                critical_path.append(task_id)

        return critical_path

    def _update_project_critical_path(self, project_id: str, new_critical_task_id: str) -> None:
        """
        Update the critical path for a project when a task is explicitly marked as critical.

        Args:
            project_id: ID of the project
            new_critical_task_id: ID of the task to add to critical path
        """
        # Get all tasks for the project
        tasks = self.get_tasks_by_project(project_id)

        # Update task as critical
        self.repository.update(new_critical_task_id, {"isCriticalPath": True})

        # Recalculate critical path will be done on the next update_project_timeline call

    def _send_task_assigned_notification(self, task: TimelineTask) -> None:
        """
        Send a notification when a task is assigned to someone.

        Args:
            task: Task that was assigned
        """
        if not self.notification_service or not hasattr(task, 'assignedTo') or not task.assignedTo:
            return

        task_name = task.name if hasattr(task, 'name') else f"Task {task.id}"
        project_id = task.project_id

        # Get project name if project service is available
        project_name = None
        if self.project_service:
            try:
                project = self.project_service.get_by_id(project_id)
                if project:
                    project_name = project.name if hasattr(project, 'name') else None
            except Exception as e:
                logger.warning(f"Failed to get project for notification: {str(e)}")

        # Create notification
        self.notification_service.create_notification({
            "user_id": task.assignedTo,
            "type": "TASK_ASSIGNED",
            "title": f"Task Assigned: {task_name}",
            "message": f"You have been assigned to a task{' in ' + project_name if project_name else ''}.",
            "link": f"/projects/{project_id}/tasks/{task.id}",
            "priority": "MEDIUM"
        })