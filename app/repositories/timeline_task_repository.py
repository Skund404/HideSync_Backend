# File: app/repositories/timeline_task_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc
from datetime import datetime, timedelta

from app.db.models.timeline_task import TimelineTask
from app.repositories.base_repository import BaseRepository


class TimelineTaskRepository(BaseRepository[TimelineTask]):
    """
    Repository for TimelineTask entity operations.

    Handles data access for timeline tasks, which represent scheduled activities
    within projects, including dependencies and critical path calculations.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the TimelineTaskRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = TimelineTask

    def get_tasks_by_project(self, project_id: str) -> List[TimelineTask]:
        """
        Get timeline tasks for a specific project.

        Args:
            project_id (str): ID of the project

        Returns:
            List[TimelineTask]: List of timeline tasks for the project
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.project_id == project_id)
            .order_by(asc(self.model.startDate))
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tasks_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[TimelineTask]:
        """
        Get timeline tasks by status.

        Args:
            status (str): The status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[TimelineTask]: List of timeline tasks with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_critical_path_tasks(self, project_id: str) -> List[TimelineTask]:
        """
        Get tasks on the critical path for a specific project.

        Args:
            project_id (str): ID of the project

        Returns:
            List[TimelineTask]: List of tasks on the critical path
        """
        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.project_id == project_id,
                    self.model.isCriticalPath == True,
                )
            )
            .order_by(asc(self.model.startDate))
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tasks_in_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[TimelineTask]:
        """
        Get timeline tasks within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[TimelineTask]: List of timeline tasks within the date range
        """
        query = self.session.query(self.model).filter(
            or_(
                # Tasks that start within the range
                and_(
                    self.model.startDate >= start_date, self.model.startDate <= end_date
                ),
                # Tasks that end within the range
                and_(self.model.endDate >= start_date, self.model.endDate <= end_date),
                # Tasks that span the entire range
                and_(
                    self.model.startDate <= start_date, self.model.endDate >= end_date
                ),
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_upcoming_tasks(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[TimelineTask]:
        """
        Get upcoming timeline tasks starting within the specified number of days.

        Args:
            days (int): Number of days to look ahead
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[TimelineTask]: List of upcoming timeline tasks
        """
        now = datetime.now()
        future = now + timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(and_(self.model.startDate >= now, self.model.startDate <= future))
            .order_by(asc(self.model.startDate))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_overdue_tasks(self, skip: int = 0, limit: int = 100) -> List[TimelineTask]:
        """
        Get overdue timeline tasks.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[TimelineTask]: List of overdue timeline tasks
        """
        now = datetime.now()

        query = (
            self.session.query(self.model)
            .filter(and_(self.model.endDate < now, self.model.progress < 100))
            .order_by(asc(self.model.endDate))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_task_progress(
        self, task_id: str, progress: int
    ) -> Optional[TimelineTask]:
        """
        Update a timeline task's progress.

        Args:
            task_id (str): ID of the timeline task
            progress (int): New progress value (0-100)

        Returns:
            Optional[TimelineTask]: Updated timeline task if found, None otherwise
        """
        task = self.get_by_id(task_id)
        if not task:
            return None

        task.progress = max(
            0, min(100, progress)
        )  # Ensure progress is between 0 and 100

        self.session.commit()
        self.session.refresh(task)
        return self._decrypt_sensitive_fields(task)

    def update_task_dates(
        self, task_id: str, start_date: datetime, end_date: datetime
    ) -> Optional[TimelineTask]:
        """
        Update a timeline task's start and end dates.

        Args:
            task_id (str): ID of the timeline task
            start_date (datetime): New start date
            end_date (datetime): New end date

        Returns:
            Optional[TimelineTask]: Updated timeline task if found, None otherwise
        """
        task = self.get_by_id(task_id)
        if not task:
            return None

        task.startDate = start_date
        task.endDate = end_date

        self.session.commit()
        self.session.refresh(task)
        return self._decrypt_sensitive_fields(task)

    def update_task_dependencies(
        self, task_id: str, dependencies: List[str]
    ) -> Optional[TimelineTask]:
        """
        Update a timeline task's dependencies.

        Args:
            task_id (str): ID of the timeline task
            dependencies (List[str]): New list of dependency task IDs

        Returns:
            Optional[TimelineTask]: Updated timeline task if found, None otherwise
        """
        task = self.get_by_id(task_id)
        if not task:
            return None

        task.dependencies = dependencies

        self.session.commit()
        self.session.refresh(task)
        return self._decrypt_sensitive_fields(task)

    def set_critical_path(
        self, task_id: str, is_critical_path: bool
    ) -> Optional[TimelineTask]:
        """
        Set whether a task is on the critical path.

        Args:
            task_id (str): ID of the timeline task
            is_critical_path (bool): Whether the task is on the critical path

        Returns:
            Optional[TimelineTask]: Updated timeline task if found, None otherwise
        """
        task = self.get_by_id(task_id)
        if not task:
            return None

        task.isCriticalPath = is_critical_path

        self.session.commit()
        self.session.refresh(task)
        return self._decrypt_sensitive_fields(task)

    def get_project_timeline_summary(self, project_id: str) -> Dict[str, Any]:
        """
        Get a summary of the timeline for a specific project.

        Args:
            project_id (str): ID of the project

        Returns:
            Dict[str, Any]: Dictionary with timeline summary information
        """
        # Get all tasks for the project
        tasks = self.get_tasks_by_project(project_id)

        # Calculate overall progress
        if tasks:
            total_progress = sum(task.progress for task in tasks)
            overall_progress = total_progress / len(tasks)
        else:
            overall_progress = 0

        # Find earliest start date and latest end date
        if tasks:
            earliest_start = min(task.startDate for task in tasks)
            latest_end = max(task.endDate for task in tasks)

            # Calculate project duration
            duration_days = (latest_end - earliest_start).days
        else:
            earliest_start = None
            latest_end = None
            duration_days = 0

        # Count tasks by status
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1

        # Get critical path tasks
        critical_path_tasks = [task for task in tasks if task.isCriticalPath]

        # Calculate days remaining
        now = datetime.now()
        if latest_end and now < latest_end:
            days_remaining = (latest_end - now).days
        else:
            days_remaining = 0

        return {
            "total_tasks": len(tasks),
            "overall_progress": overall_progress,
            "start_date": earliest_start,
            "end_date": latest_end,
            "duration_days": duration_days,
            "days_remaining": days_remaining,
            "status_breakdown": status_counts,
            "critical_path_tasks": len(critical_path_tasks),
            "overdue_tasks": sum(
                1 for task in tasks if task.endDate < now and task.progress < 100
            ),
        }
