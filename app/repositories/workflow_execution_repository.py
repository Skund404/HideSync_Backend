# File: app/repositories/workflow_execution_repository.py

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, asc, case

from app.repositories.base_repository import BaseRepository
from app.db.models.workflow import (
    WorkflowExecution, WorkflowStepExecution, WorkflowNavigationHistory,
    Workflow, WorkflowStep, WorkflowOutcome
)
from app.core.exceptions import EntityNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class WorkflowExecutionRepository(BaseRepository):
    """
    Repository for workflow execution-related database operations.
    Handles runtime workflow execution tracking and navigation.
    """

    def __init__(self, db_session: Session, encryption_service=None):
        """Initialize execution repository with session and encryption service."""
        super().__init__(db_session, WorkflowExecution)
        self.encryption_service = encryption_service

    # ==================== Core Execution Operations ====================

    def get_execution_with_details(self, execution_id: int) -> Optional[WorkflowExecution]:
        """
        Get execution with all related data loaded.

        Args:
            execution_id: Execution ID

        Returns:
            WorkflowExecution with full details or None
        """
        try:
            execution = self.db_session.query(WorkflowExecution).options(
                joinedload(WorkflowExecution.workflow).selectinload(Workflow.steps),
                joinedload(WorkflowExecution.selected_outcome),
                joinedload(WorkflowExecution.current_step),
                selectinload(WorkflowExecution.step_executions).joinedload(WorkflowStepExecution.step),
                selectinload(WorkflowExecution.navigation_history)
            ).filter(WorkflowExecution.id == execution_id).first()

            if execution:
                logger.debug(
                    f"Retrieved execution {execution_id} with {len(execution.step_executions)} step executions")

            return execution

        except Exception as e:
            logger.error(f"Error retrieving execution {execution_id}: {str(e)}")
            raise

    def get_active_executions(self, user_id: Optional[int] = None,
                              workflow_id: Optional[int] = None) -> List[WorkflowExecution]:
        """
        Get active workflow executions with optional filtering.

        Args:
            user_id: Optional user filter
            workflow_id: Optional workflow filter

        Returns:
            List of active executions
        """
        try:
            query = self.db_session.query(WorkflowExecution).filter(
                WorkflowExecution.status.in_(['active', 'paused'])
            ).options(
                joinedload(WorkflowExecution.workflow),
                joinedload(WorkflowExecution.current_step)
            )

            if user_id:
                query = query.filter(WorkflowExecution.started_by == user_id)

            if workflow_id:
                query = query.filter(WorkflowExecution.workflow_id == workflow_id)

            executions = query.order_by(desc(WorkflowExecution.started_at)).all()

            logger.debug(f"Found {len(executions)} active executions")
            return executions

        except Exception as e:
            logger.error(f"Error retrieving active executions: {str(e)}")
            raise

    def update_execution_status(self, execution_id: int, new_status: str,
                                completion_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update execution status and completion data.

        Args:
            execution_id: Execution ID
            new_status: New status
            completion_data: Optional completion data

        Returns:
            True if updated successfully
        """
        try:
            update_data = {
                'status': new_status,
                'updated_at': datetime.utcnow()
            }

            # Add completion data if provided
            if completion_data:
                if new_status == 'completed':
                    update_data['completed_at'] = completion_data.get('completed_at', datetime.utcnow())
                    update_data['total_duration'] = completion_data.get('total_duration')

                if 'execution_data' in completion_data:
                    update_data['execution_data'] = completion_data['execution_data']

            updated_rows = self.db_session.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).update(update_data)

            if updated_rows > 0:
                self.db_session.commit()
                logger.info(f"Updated execution {execution_id} status to {new_status}")
                return True
            else:
                logger.warning(f"No execution found with ID {execution_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating execution status: {str(e)}")
            self.db_session.rollback()
            raise

    def update_current_step(self, execution_id: int, step_id: int) -> bool:
        """
        Update the current step for an execution.

        Args:
            execution_id: Execution ID
            step_id: New current step ID

        Returns:
            True if updated successfully
        """
        try:
            updated_rows = self.db_session.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).update({
                'current_step_id': step_id,
                'updated_at': datetime.utcnow()
            })

            if updated_rows > 0:
                self.db_session.commit()
                logger.debug(f"Updated current step for execution {execution_id} to step {step_id}")
                return True
            else:
                logger.warning(f"No execution found with ID {execution_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating current step: {str(e)}")
            self.db_session.rollback()
            raise

    # ==================== Step Execution Operations ====================

    def create_step_execution(self, execution_id: int, step_id: int,
                              initial_status: str = 'ready') -> WorkflowStepExecution:
        """
        Create a new step execution record.

        Args:
            execution_id: Parent execution ID
            step_id: Step ID
            initial_status: Initial status

        Returns:
            Created step execution
        """
        try:
            step_execution_data = {
                'execution_id': execution_id,
                'step_id': step_id,
                'status': initial_status
            }

            step_execution = WorkflowStepExecution(**step_execution_data)
            self.db_session.add(step_execution)
            self.db_session.flush()

            logger.debug(f"Created step execution for execution {execution_id}, step {step_id}")
            return step_execution

        except Exception as e:
            logger.error(f"Error creating step execution: {str(e)}")
            raise

    def get_step_execution(self, execution_id: int, step_id: int) -> Optional[WorkflowStepExecution]:
        """
        Get step execution by execution and step ID.

        Args:
            execution_id: Execution ID
            step_id: Step ID

        Returns:
            Step execution or None
        """
        try:
            step_execution = self.db_session.query(WorkflowStepExecution).filter(
                WorkflowStepExecution.execution_id == execution_id,
                WorkflowStepExecution.step_id == step_id
            ).options(joinedload(WorkflowStepExecution.step)).first()

            return step_execution

        except Exception as e:
            logger.error(f"Error retrieving step execution: {str(e)}")
            raise

    def update_step_execution(self, execution_id: int, step_id: int,
                              update_data: Dict[str, Any]) -> bool:
        """
        Update step execution data.

        Args:
            execution_id: Execution ID
            step_id: Step ID
            update_data: Update data

        Returns:
            True if updated successfully
        """
        try:
            updated_rows = self.db_session.query(WorkflowStepExecution).filter(
                WorkflowStepExecution.execution_id == execution_id,
                WorkflowStepExecution.step_id == step_id
            ).update(update_data)

            if updated_rows > 0:
                self.db_session.commit()
                logger.debug(f"Updated step execution for execution {execution_id}, step {step_id}")
                return True
            else:
                logger.warning(f"No step execution found for execution {execution_id}, step {step_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating step execution: {str(e)}")
            self.db_session.rollback()
            raise

    def get_execution_step_statuses(self, execution_id: int) -> Dict[int, str]:
        """
        Get status of all steps in an execution.

        Args:
            execution_id: Execution ID

        Returns:
            Dictionary mapping step_id to status
        """
        try:
            step_executions = self.db_session.query(
                WorkflowStepExecution.step_id,
                WorkflowStepExecution.status
            ).filter(
                WorkflowStepExecution.execution_id == execution_id
            ).all()

            return {step_id: status for step_id, status in step_executions}

        except Exception as e:
            logger.error(f"Error retrieving step statuses: {str(e)}")
            raise

    # ==================== Navigation Operations ====================

    def record_navigation(self, execution_id: int, step_id: int, action_type: str,
                          action_data: Optional[Dict[str, Any]] = None) -> WorkflowNavigationHistory:
        """
        Record a navigation action in the history.

        Args:
            execution_id: Execution ID
            step_id: Step ID
            action_type: Type of action
            action_data: Optional action data

        Returns:
            Created navigation history record
        """
        try:
            navigation_data = {
                'execution_id': execution_id,
                'step_id': step_id,
                'action_type': action_type,
                'action_data': action_data,
                'timestamp': datetime.utcnow()
            }

            navigation = WorkflowNavigationHistory(**navigation_data)
            self.db_session.add(navigation)
            self.db_session.flush()

            logger.debug(f"Recorded navigation: {action_type} for execution {execution_id}, step {step_id}")
            return navigation

        except Exception as e:
            logger.error(f"Error recording navigation: {str(e)}")
            raise

    def get_navigation_history(self, execution_id: int, limit: int = 50) -> List[WorkflowNavigationHistory]:
        """
        Get navigation history for an execution.

        Args:
            execution_id: Execution ID
            limit: Maximum number of records

        Returns:
            List of navigation history records
        """
        try:
            history = self.db_session.query(WorkflowNavigationHistory).filter(
                WorkflowNavigationHistory.execution_id == execution_id
            ).options(
                joinedload(WorkflowNavigationHistory.step)
            ).order_by(desc(WorkflowNavigationHistory.timestamp)).limit(limit).all()

            return history

        except Exception as e:
            logger.error(f"Error retrieving navigation history: {str(e)}")
            raise

    # ==================== Progress and Analytics ====================

    def calculate_execution_progress(self, execution_id: int) -> Dict[str, Any]:
        """
        Calculate execution progress statistics.

        Args:
            execution_id: Execution ID

        Returns:
            Progress statistics dictionary
        """
        try:
            # Get execution with workflow
            execution = self.get_execution_with_details(execution_id)
            if not execution:
                raise EntityNotFoundException("WorkflowExecution", execution_id)

            # Count total steps in workflow
            total_steps = len(execution.workflow.steps)

            # Count completed steps
            completed_steps = len([
                se for se in execution.step_executions
                if se.status == 'completed'
            ])

            # Calculate progress percentage
            progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0

            # Calculate time statistics
            time_elapsed = None
            estimated_remaining = None

            if execution.started_at:
                time_elapsed = (datetime.utcnow() - execution.started_at).total_seconds() / 60  # minutes

                # Estimate remaining time based on workflow duration and progress
                if execution.workflow.estimated_duration and progress_percentage > 0:
                    estimated_total = execution.workflow.estimated_duration
                    estimated_remaining = estimated_total - (estimated_total * progress_percentage / 100)

            progress_data = {
                'execution_id': execution_id,
                'total_steps': total_steps,
                'completed_steps': completed_steps,
                'current_step_id': execution.current_step_id,
                'current_step_name': execution.current_step.name if execution.current_step else None,
                'progress_percentage': round(progress_percentage, 2),
                'time_elapsed': round(time_elapsed, 2) if time_elapsed else None,
                'estimated_remaining_time': round(estimated_remaining, 2) if estimated_remaining else None
            }

            return progress_data

        except Exception as e:
            logger.error(f"Error calculating execution progress: {str(e)}")
            raise

    def get_execution_statistics(self, execution_id: int) -> Dict[str, Any]:
        """
        Get comprehensive statistics for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            Execution statistics
        """
        try:
            execution = self.get_execution_with_details(execution_id)
            if not execution:
                raise EntityNotFoundException("WorkflowExecution", execution_id)

            # Basic statistics
            stats = {
                'execution_id': execution_id,
                'workflow_id': execution.workflow_id,
                'workflow_name': execution.workflow.name,
                'status': execution.status,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'total_duration': execution.total_duration
            }

            # Step statistics
            step_stats = self._calculate_step_statistics(execution.step_executions)
            stats.update(step_stats)

            # Navigation statistics
            nav_stats = self._calculate_navigation_statistics(execution.navigation_history)
            stats.update(nav_stats)

            return stats

        except Exception as e:
            logger.error(f"Error getting execution statistics: {str(e)}")
            raise

    # ==================== Query and Search Operations ====================

    def search_executions(self, user_id: Optional[int] = None,
                          workflow_id: Optional[int] = None,
                          status: Optional[str] = None,
                          date_from: Optional[datetime] = None,
                          date_to: Optional[datetime] = None,
                          limit: int = 50,
                          offset: int = 0) -> Dict[str, Any]:
        """
        Search executions with filtering and pagination.

        Args:
            user_id: Optional user filter
            workflow_id: Optional workflow filter
            status: Optional status filter
            date_from: Optional start date filter
            date_to: Optional end date filter
            limit: Page size
            offset: Page offset

        Returns:
            Paginated search results
        """
        try:
            query = self.db_session.query(WorkflowExecution).options(
                joinedload(WorkflowExecution.workflow),
                joinedload(WorkflowExecution.current_step)
            )

            # Apply filters
            if user_id:
                query = query.filter(WorkflowExecution.started_by == user_id)

            if workflow_id:
                query = query.filter(WorkflowExecution.workflow_id == workflow_id)

            if status:
                query = query.filter(WorkflowExecution.status == status)

            if date_from:
                query = query.filter(WorkflowExecution.started_at >= date_from)

            if date_to:
                query = query.filter(WorkflowExecution.started_at <= date_to)

            # Get total count
            total = query.count()

            # Apply pagination and ordering
            executions = query.order_by(desc(WorkflowExecution.started_at)).offset(offset).limit(limit).all()

            return {
                'items': executions,
                'total': total,
                'limit': limit,
                'offset': offset
            }

        except Exception as e:
            logger.error(f"Error searching executions: {str(e)}")
            raise

    # ==================== Helper Methods ====================

    def _calculate_step_statistics(self, step_executions: List[WorkflowStepExecution]) -> Dict[str, Any]:
        """Calculate statistics for step executions."""
        if not step_executions:
            return {
                'total_steps': 0,
                'completed_steps': 0,
                'average_step_duration': None
            }

        completed_steps = [se for se in step_executions if se.status == 'completed']

        # Calculate average duration for completed steps
        durations = [se.actual_duration for se in completed_steps if se.actual_duration]
        avg_duration = sum(durations) / len(durations) if durations else None

        return {
            'total_steps': len(step_executions),
            'completed_steps': len(completed_steps),
            'average_step_duration': round(avg_duration, 2) if avg_duration else None
        }

    def _calculate_navigation_statistics(self, navigation_history: List[WorkflowNavigationHistory]) -> Dict[str, Any]:
        """Calculate navigation-related statistics."""
        if not navigation_history:
            return {
                'total_navigation_actions': 0,
                'unique_steps_visited': 0
            }

        unique_steps = set(nav.step_id for nav in navigation_history)

        return {
            'total_navigation_actions': len(navigation_history),
            'unique_steps_visited': len(unique_steps)
        }


class WorkflowStepExecutionRepository(BaseRepository):
    """
    Repository specifically for workflow step executions.
    Handles individual step tracking within executions.
    """

    def __init__(self, db_session: Session, encryption_service=None):
        """Initialize step execution repository."""
        super().__init__(db_session, WorkflowStepExecution)
        self.encryption_service = encryption_service

    def get_pending_steps(self, execution_id: int) -> List[WorkflowStepExecution]:
        """Get all pending steps for an execution."""
        try:
            return self.db_session.query(WorkflowStepExecution).filter(
                WorkflowStepExecution.execution_id == execution_id,
                WorkflowStepExecution.status.in_(['ready', 'active'])
            ).options(joinedload(WorkflowStepExecution.step)).all()

        except Exception as e:
            logger.error(f"Error retrieving pending steps: {str(e)}")
            raise

    def mark_step_completed(self, execution_id: int, step_id: int,
                            duration: Optional[float] = None,
                            notes: Optional[str] = None) -> bool:
        """Mark a step as completed."""
        try:
            update_data = {
                'status': 'completed',
                'completed_at': datetime.utcnow()
            }

            if duration:
                update_data['actual_duration'] = duration

            if notes:
                update_data['notes'] = notes

            updated = self.db_session.query(WorkflowStepExecution).filter(
                WorkflowStepExecution.execution_id == execution_id,
                WorkflowStepExecution.step_id == step_id
            ).update(update_data)

            if updated > 0:
                self.db_session.commit()
                return True
            return False

        except Exception as e:
            logger.error(f"Error marking step completed: {str(e)}")
            self.db_session.rollback()
            raise