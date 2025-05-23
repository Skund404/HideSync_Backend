# File: app/services/workflow_execution_service.py

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.repositories.workflow_execution_repository import WorkflowExecutionRepository, WorkflowStepExecutionRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.repository_factory import RepositoryFactory
from app.db.models.workflow import (
    WorkflowExecution, WorkflowStepExecution, WorkflowStep,
    WorkflowStepConnection, WorkflowDecisionOption, WorkflowNavigationHistory
)
from app.core.exceptions import (
    EntityNotFoundException, ValidationException, BusinessRuleException
)
from app.core.events import global_event_bus, EntityCreatedEvent, EntityUpdatedEvent
from app.services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)


class WorkflowExecutionService(BaseService):
    """
    Service for managing workflow execution runtime.
    Handles execution flow, step transitions, and progress tracking.
    """

    def __init__(self, session: Session, workflow_service: Optional[WorkflowService] = None):
        """
        Initialize the workflow execution service.

        Args:
            session: Database session
            workflow_service: Optional workflow service dependency
        """
        self.db_session = session

        # Initialize repositories using RepositoryFactory
        factory = RepositoryFactory(session)
        self.execution_repo = factory.create_workflow_execution_repository()
        self.step_execution_repo = factory.create_workflow_step_execution_repository()
        self.workflow_repo = factory.create_workflow_repository()

        # Initialize workflow service
        self.workflow_service = workflow_service or WorkflowService(session)

    # ==================== Execution Management ====================

    def get_execution(self, execution_id: int, user_id: Optional[int] = None) -> WorkflowExecution:
        """
        Get execution with access control.

        Args:
            execution_id: Execution ID
            user_id: Optional user ID for access control

        Returns:
            WorkflowExecution object

        Raises:
            EntityNotFoundException: If execution not found
            BusinessRuleException: If access denied
        """
        try:
            execution = self.execution_repo.get_execution_with_details(execution_id)

            if not execution:
                raise EntityNotFoundException("WorkflowExecution", execution_id)

            # Check access permissions
            if user_id and execution.started_by != user_id:
                raise BusinessRuleException("Access denied to this execution")

            return execution

        except EntityNotFoundException:
            raise
        except BusinessRuleException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving execution {execution_id}: {str(e)}")
            raise

    def pause_execution(self, execution_id: int, user_id: int) -> WorkflowExecution:
        """
        Pause an active execution.

        Args:
            execution_id: Execution ID
            user_id: User requesting pause

        Returns:
            Updated execution
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            if execution.status != 'active':
                raise BusinessRuleException(f"Cannot pause execution with status '{execution.status}'")

            # Update execution status
            success = self.execution_repo.update_execution_status(execution_id, 'paused')

            if success:
                # Record navigation action
                if execution.current_step_id:
                    self.execution_repo.record_navigation(
                        execution_id, execution.current_step_id, 'paused'
                    )

                # Emit event
                event = EntityUpdatedEvent(
                    entity_id=execution_id,
                    entity_type="WorkflowExecution",
                    user_id=user_id
                )
                global_event_bus.publish(event)

                logger.info(f"Paused execution {execution_id} by user {user_id}")

                # Return updated execution
                return self.get_execution(execution_id, user_id)
            else:
                raise BusinessRuleException("Failed to pause execution")

        except (EntityNotFoundException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error pausing execution {execution_id}: {str(e)}")
            raise

    def resume_execution(self, execution_id: int, user_id: int) -> WorkflowExecution:
        """
        Resume a paused execution.

        Args:
            execution_id: Execution ID
            user_id: User requesting resume

        Returns:
            Updated execution
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            if execution.status != 'paused':
                raise BusinessRuleException(f"Cannot resume execution with status '{execution.status}'")

            # Update execution status
            success = self.execution_repo.update_execution_status(execution_id, 'active')

            if success:
                # Record navigation action
                if execution.current_step_id:
                    self.execution_repo.record_navigation(
                        execution_id, execution.current_step_id, 'resumed'
                    )

                logger.info(f"Resumed execution {execution_id} by user {user_id}")
                return self.get_execution(execution_id, user_id)
            else:
                raise BusinessRuleException("Failed to resume execution")

        except (EntityNotFoundException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error resuming execution {execution_id}: {str(e)}")
            raise

    def cancel_execution(self, execution_id: int, user_id: int, reason: Optional[str] = None) -> WorkflowExecution:
        """
        Cancel an execution.

        Args:
            execution_id: Execution ID
            user_id: User requesting cancellation
            reason: Optional cancellation reason

        Returns:
            Updated execution
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            if execution.status in ['completed', 'cancelled', 'failed']:
                raise BusinessRuleException(f"Cannot cancel execution with status '{execution.status}'")

            # Prepare completion data
            completion_data = {
                'completed_at': datetime.utcnow()
            }

            if reason:
                execution_data = execution.execution_data or {}
                execution_data['cancellation_reason'] = reason
                completion_data['execution_data'] = execution_data

            # Update execution status
            success = self.execution_repo.update_execution_status(
                execution_id, 'cancelled', completion_data
            )

            if success:
                # Record navigation action
                if execution.current_step_id:
                    self.execution_repo.record_navigation(
                        execution_id, execution.current_step_id, 'cancelled',
                        {'reason': reason} if reason else None
                    )

                logger.info(f"Cancelled execution {execution_id} by user {user_id}")
                return self.get_execution(execution_id, user_id)
            else:
                raise BusinessRuleException("Failed to cancel execution")

        except (EntityNotFoundException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error cancelling execution {execution_id}: {str(e)}")
            raise

    # ==================== Step Navigation ====================

    def navigate_to_step(self, execution_id: int, target_step_id: int, user_id: int) -> WorkflowExecution:
        """
        Navigate to a specific step in the execution.

        Args:
            execution_id: Execution ID
            target_step_id: Target step ID
            user_id: User performing navigation

        Returns:
            Updated execution
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            if execution.status != 'active':
                raise BusinessRuleException(f"Cannot navigate in execution with status '{execution.status}'")

            # Validate target step belongs to the workflow
            target_step = self.workflow_repo.db_session.query(WorkflowStep).filter(
                WorkflowStep.id == target_step_id,
                WorkflowStep.workflow_id == execution.workflow_id
            ).first()

            if not target_step:
                raise ValidationException("Target step not found in workflow")

            # Check if navigation is allowed (implement business rules here)
            if not self._can_navigate_to_step(execution, target_step):
                raise BusinessRuleException("Navigation to this step is not allowed")

            # Update current step
            success = self.execution_repo.update_current_step(execution_id, target_step_id)

            if success:
                # Record navigation
                self.execution_repo.record_navigation(
                    execution_id, target_step_id, 'navigate_to'
                )

                # Create or update step execution if needed
                step_execution = self.execution_repo.get_step_execution(execution_id, target_step_id)
                if not step_execution:
                    self.execution_repo.create_step_execution(execution_id, target_step_id, 'active')
                elif step_execution.status == 'ready':
                    self.execution_repo.update_step_execution(
                        execution_id, target_step_id,
                        {'status': 'active', 'started_at': datetime.utcnow()}
                    )

                logger.info(f"Navigated execution {execution_id} to step {target_step_id}")
                return self.get_execution(execution_id, user_id)
            else:
                raise BusinessRuleException("Failed to navigate to step")

        except (EntityNotFoundException, ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error navigating to step: {str(e)}")
            raise

    def complete_step(self, execution_id: int, step_id: int, user_id: int,
                      completion_data: Optional[Dict[str, Any]] = None) -> WorkflowExecution:
        """
        Mark a step as completed and determine next steps.

        Args:
            execution_id: Execution ID
            step_id: Step ID to complete
            user_id: User completing the step
            completion_data: Optional completion data

        Returns:
            Updated execution
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            if execution.status != 'active':
                raise BusinessRuleException(f"Cannot complete step in execution with status '{execution.status}'")

            # Get step execution
            step_execution = self.execution_repo.get_step_execution(execution_id, step_id)
            if not step_execution:
                raise EntityNotFoundException("WorkflowStepExecution", f"{execution_id}/{step_id}")

            if step_execution.status == 'completed':
                raise BusinessRuleException("Step is already completed")

            # Calculate duration if step was started
            duration = None
            if step_execution.started_at:
                duration = (datetime.utcnow() - step_execution.started_at).total_seconds() / 60  # minutes

            # Update step execution
            update_data = {
                'status': 'completed',
                'completed_at': datetime.utcnow(),
                'actual_duration': duration,
                'notes': completion_data.get('notes') if completion_data else None,
                'step_data': completion_data.get('step_data') if completion_data else None
            }

            self.execution_repo.update_step_execution(execution_id, step_id, update_data)

            # Record navigation
            self.execution_repo.record_navigation(
                execution_id, step_id, 'completed',
                {'actual_duration': duration, 'completion_data': completion_data}
            )

            # Determine next steps
            next_steps = self._determine_next_steps(execution, step_id, completion_data)

            # Update execution based on next steps
            if not next_steps:
                # No next steps - check if workflow is complete
                if self._is_workflow_complete(execution):
                    self._complete_execution(execution_id, user_id)
                else:
                    # Set to outcome selection or manual navigation mode
                    execution.current_step_id = None
            else:
                # Move to first next step
                next_step_id = next_steps[0].id
                self.execution_repo.update_current_step(execution_id, next_step_id)

                # Create step executions for next steps
                for next_step in next_steps:
                    existing = self.execution_repo.get_step_execution(execution_id, next_step.id)
                    if not existing:
                        self.execution_repo.create_step_execution(execution_id, next_step.id, 'ready')

            logger.info(f"Completed step {step_id} in execution {execution_id}")
            return self.get_execution(execution_id, user_id)

        except (EntityNotFoundException, ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error completing step: {str(e)}")
            raise

    def make_decision(self, execution_id: int, step_id: int, decision_option_id: int,
                      user_id: int) -> WorkflowExecution:
        """
        Make a decision at a decision point step.

        Args:
            execution_id: Execution ID
            step_id: Decision step ID
            decision_option_id: Selected decision option ID
            user_id: User making decision

        Returns:
            Updated execution
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            # Validate decision option belongs to step
            decision_option = self.workflow_repo.db_session.query(WorkflowDecisionOption).filter(
                WorkflowDecisionOption.id == decision_option_id,
                WorkflowDecisionOption.step_id == step_id
            ).first()

            if not decision_option:
                raise ValidationException("Decision option not found for this step")

            # Record the decision
            self.execution_repo.record_navigation(
                execution_id, step_id, 'decision_made',
                {
                    'decision_option_id': decision_option_id,
                    'option_text': decision_option.option_text
                }
            )

            # Process decision result
            if decision_option.result_action:
                self._process_decision_action(execution_id, decision_option.result_action)

            # Complete the decision step
            completion_data = {
                'step_data': {
                    'decision_option_id': decision_option_id,
                    'decision_text': decision_option.option_text
                }
            }

            return self.complete_step(execution_id, step_id, user_id, completion_data)

        except (EntityNotFoundException, ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error making decision: {str(e)}")
            raise

    # ==================== Progress and Status ====================

    def get_execution_progress(self, execution_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get detailed progress information for an execution.

        Args:
            execution_id: Execution ID
            user_id: Optional user ID for access control

        Returns:
            Progress information dictionary
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            # Use repository method to calculate progress
            progress_data = self.execution_repo.calculate_execution_progress(execution_id)

            # Add additional context
            progress_data.update({
                'workflow_name': execution.workflow.name,
                'status': execution.status,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at
            })

            return progress_data

        except Exception as e:
            logger.error(f"Error getting execution progress: {str(e)}")
            raise

    def get_next_available_steps(self, execution_id: int, user_id: Optional[int] = None) -> List[WorkflowStep]:
        """
        Get steps that can be navigated to from current position.

        Args:
            execution_id: Execution ID
            user_id: Optional user ID for access control

        Returns:
            List of available next steps
        """
        try:
            execution = self.get_execution(execution_id, user_id)

            if not execution.current_step_id:
                # No current step - return initial steps or allow manual selection
                return self.workflow_repo.get_initial_steps(execution.workflow_id)

            # Get next steps based on current step connections
            next_steps = self.workflow_repo.get_next_steps(
                execution.current_step_id,
                execution.execution_data
            )

            return next_steps

        except Exception as e:
            logger.error(f"Error getting next available steps: {str(e)}")
            raise

    # ==================== Private Helper Methods ====================

    def _can_navigate_to_step(self, execution: WorkflowExecution, target_step: WorkflowStep) -> bool:
        """
        Check if navigation to a step is allowed.

        Args:
            execution: Current execution
            target_step: Target step

        Returns:
            True if navigation is allowed
        """
        # Basic validation - step belongs to workflow
        if target_step.workflow_id != execution.workflow_id:
            return False

        # Additional business rules can be implemented here
        # For example:
        # - Check if step is reachable from current position
        # - Check if prerequisites are met
        # - Check if step is locked due to conditions

        return True

    def _determine_next_steps(self, execution: WorkflowExecution, completed_step_id: int,
                              completion_data: Optional[Dict[str, Any]] = None) -> List[WorkflowStep]:
        """
        Determine which steps should be activated next.

        Args:
            execution: Current execution
            completed_step_id: ID of just completed step
            completion_data: Data from step completion

        Returns:
            List of next steps to activate
        """
        try:
            # Get outgoing connections from completed step
            next_steps = self.workflow_repo.get_next_steps(
                completed_step_id,
                execution.execution_data
            )

            # Filter based on conditions and execution state
            available_steps = []
            for step in next_steps:
                if self._evaluate_step_condition(step, execution, completion_data):
                    available_steps.append(step)

            return available_steps

        except Exception as e:
            logger.error(f"Error determining next steps: {str(e)}")
            return []

    def _evaluate_step_condition(self, step: WorkflowStep, execution: WorkflowExecution,
                                 completion_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate if a step's conditions are met.

        Args:
            step: Step to evaluate
            execution: Current execution
            completion_data: Recent completion data

        Returns:
            True if step conditions are met
        """
        # If step has no condition logic, it's always available
        if not step.condition_logic:
            return True

        # TODO: Implement condition evaluation engine
        # This would parse JSON condition logic and evaluate against:
        # - execution.execution_data
        # - completion_data
        # - step execution history

        # For now, return True (no conditions blocking)
        return True

    def _is_workflow_complete(self, execution: WorkflowExecution) -> bool:
        """
        Check if workflow execution is complete.

        Args:
            execution: Execution to check

        Returns:
            True if workflow is complete
        """
        try:
            # Get all steps in workflow
            all_steps = self.workflow_repo.get_workflow_steps(execution.workflow_id, include_resources=False)

            # Check if all required steps are completed
            step_statuses = self.execution_repo.get_execution_step_statuses(execution.id)

            for step in all_steps:
                # Skip optional steps that haven't been started
                if step.id not in step_statuses:
                    continue

                # Check if required step is not completed
                if step_statuses[step.id] != 'completed' and not self._is_step_optional(step, execution):
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking workflow completion: {str(e)}")
            return False

    def _is_step_optional(self, step: WorkflowStep, execution: WorkflowExecution) -> bool:
        """
        Check if a step is optional in the current execution context.

        Args:
            step: Step to check
            execution: Current execution

        Returns:
            True if step is optional
        """
        # TODO: Implement logic to determine if step is optional
        # This could be based on:
        # - Step configuration
        # - Execution path taken
        # - Outcome selection

        return False

    def _complete_execution(self, execution_id: int, user_id: int) -> None:
        """
        Mark execution as completed.

        Args:
            execution_id: Execution ID
            user_id: User completing execution
        """
        try:
            execution = self.get_execution(execution_id)

            # Calculate total duration
            total_duration = None
            if execution.started_at:
                total_duration = (datetime.utcnow() - execution.started_at).total_seconds() / 60

            # Prepare completion data
            completion_data = {
                'completed_at': datetime.utcnow(),
                'total_duration': total_duration
            }

            # Update execution status
            self.execution_repo.update_execution_status(execution_id, 'completed', completion_data)

            # Record completion navigation
            self.execution_repo.record_navigation(
                execution_id, execution.current_step_id or 0, 'workflow_completed',
                {'total_duration': total_duration}
            )

            # Emit completion event
            event = EntityUpdatedEvent(
                entity_id=execution_id,
                entity_type="WorkflowExecution",
                user_id=user_id
            )
            global_event_bus.publish(event)

            logger.info(f"Completed workflow execution {execution_id}")

        except Exception as e:
            logger.error(f"Error completing execution: {str(e)}")
            raise

    def _process_decision_action(self, execution_id: int, result_action: str) -> None:
        """
        Process the result action from a decision.

        Args:
            execution_id: Execution ID
            result_action: JSON result action to process
        """
        try:
            # TODO: Implement decision action processing
            # This would parse JSON actions like:
            # - Set execution variables
            # - Skip certain steps
            # - Change workflow path
            # - Set outcome

            logger.debug(f"Processing decision action for execution {execution_id}: {result_action}")

        except Exception as e:
            logger.error(f"Error processing decision action: {str(e)}")
            # Don't raise - decision actions are optional