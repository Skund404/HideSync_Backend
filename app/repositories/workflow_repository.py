# File: app/repositories/workflow_repository.py

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.exc import IntegrityError

from app.repositories.base_repository import BaseRepository
from app.db.models.workflow import (
    Workflow, WorkflowStep, WorkflowExecution, WorkflowOutcome,
    WorkflowStepConnection, WorkflowStepResource, WorkflowDecisionOption,
    WorkflowNavigationHistory, WorkflowPath, WorkflowPathStep, WorkflowTheme
)
from app.core.exceptions import EntityNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class WorkflowRepository(BaseRepository):
    """
    Repository for workflow-related database operations.
    Follows existing HideSync repository patterns with RepositoryFactory integration.
    """

    def __init__(self, db_session: Session, encryption_service=None):
        """Initialize workflow repository with session and encryption service."""
        super().__init__(db_session, Workflow)
        self.encryption_service = encryption_service

    # ==================== Core Workflow Operations ====================

    def get_workflow_with_steps(self, workflow_id: int, include_resources: bool = True) -> Optional[Workflow]:
        """
        Get a workflow with all its steps and connections loaded.

        Args:
            workflow_id: ID of the workflow to retrieve
            include_resources: Whether to include step resources

        Returns:
            Workflow with steps loaded, or None if not found

        Raises:
            EntityNotFoundException: If workflow not found
        """
        try:
            query = self.db_session.query(Workflow).options(
                selectinload(Workflow.steps).options(
                    selectinload(WorkflowStep.outgoing_connections),
                    selectinload(WorkflowStep.decision_options),
                    selectinload(WorkflowStep.resources) if include_resources else selectinload(
                        WorkflowStep.resources).selectinload(None),
                ),
                selectinload(Workflow.outcomes),
                joinedload(Workflow.theme)
            ).filter(Workflow.id == workflow_id)

            workflow = query.first()

            if not workflow:
                logger.warning(f"Workflow with ID {workflow_id} not found")
                raise EntityNotFoundException("Workflow", workflow_id)

            logger.debug(f"Retrieved workflow {workflow_id} with {len(workflow.steps)} steps")
            return workflow

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving workflow {workflow_id}: {str(e)}")
            raise

    def get_workflow_templates(self, user_id: Optional[int] = None,
                               include_system: bool = True) -> List[Workflow]:
        """
        Get all workflow templates available to a user.

        Args:
            user_id: Optional user ID for filtering private templates
            include_system: Whether to include system templates

        Returns:
            List of workflow templates
        """
        try:
            query = self.db_session.query(Workflow).filter(
                Workflow.is_template == True,
                Workflow.status.in_(['active', 'published'])
            )

            # Filter by visibility and ownership
            if user_id:
                visibility_filter = or_(
                    Workflow.visibility == 'public',
                    Workflow.created_by == user_id
                )
                if include_system:
                    visibility_filter = or_(visibility_filter, Workflow.visibility == 'system')
                query = query.filter(visibility_filter)
            else:
                query = query.filter(Workflow.visibility == 'public')
                if include_system:
                    query = query.filter(or_(Workflow.visibility == 'public', Workflow.visibility == 'system'))

            templates = query.order_by(Workflow.name).all()
            logger.debug(f"Retrieved {len(templates)} workflow templates for user {user_id}")
            return templates

        except Exception as e:
            logger.error(f"Error retrieving workflow templates: {str(e)}")
            raise

    def search_workflows(self,
                         search_term: Optional[str] = None,
                         status: Optional[str] = None,
                         is_template: Optional[bool] = None,
                         created_by: Optional[int] = None,
                         project_id: Optional[int] = None,
                         difficulty_level: Optional[str] = None,
                         limit: int = 50,
                         offset: int = 0,
                         order_by: str = 'updated_at',
                         order_dir: str = 'desc') -> Dict[str, Any]:
        """
        Search workflows with filtering and pagination.

        Args:
            search_term: Optional search term for name/description
            status: Optional status filter
            is_template: Optional template filter
            created_by: Optional creator filter
            project_id: Optional project filter
            difficulty_level: Optional difficulty filter
            limit: Maximum number of results
            offset: Pagination offset
            order_by: Field to order by
            order_dir: Order direction (asc/desc)

        Returns:
            Dictionary with 'items', 'total', 'limit', 'offset' keys
        """
        try:
            query = self.db_session.query(Workflow)

            # Apply search filter
            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Workflow.name.ilike(search_pattern),
                        Workflow.description.ilike(search_pattern)
                    )
                )

            # Apply filters
            if status:
                query = query.filter(Workflow.status == status)

            if is_template is not None:
                query = query.filter(Workflow.is_template == is_template)

            if created_by:
                query = query.filter(Workflow.created_by == created_by)

            if project_id:
                query = query.filter(Workflow.project_id == project_id)

            if difficulty_level:
                query = query.filter(Workflow.difficulty_level == difficulty_level)

            # Get total count before pagination
            total = query.count()

            # Apply ordering
            order_column = getattr(Workflow, order_by, Workflow.updated_at)
            if order_dir.lower() == 'desc':
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))

            # Apply pagination
            workflows = query.offset(offset).limit(limit).all()

            logger.debug(f"Search returned {len(workflows)} workflows out of {total} total")

            return {
                'items': workflows,
                'total': total,
                'limit': limit,
                'offset': offset
            }

        except Exception as e:
            logger.error(f"Error searching workflows: {str(e)}")
            raise

    def get_user_workflows(self, user_id: int, include_templates: bool = False) -> List[Workflow]:
        """
        Get all workflows created by a specific user.

        Args:
            user_id: User ID
            include_templates: Whether to include templates

        Returns:
            List of user's workflows
        """
        try:
            query = self.db_session.query(Workflow).filter(Workflow.created_by == user_id)

            if not include_templates:
                query = query.filter(Workflow.is_template == False)

            workflows = query.order_by(desc(Workflow.updated_at)).all()
            logger.debug(f"Retrieved {len(workflows)} workflows for user {user_id}")
            return workflows

        except Exception as e:
            logger.error(f"Error retrieving user workflows: {str(e)}")
            raise

    def duplicate_workflow(self, workflow_id: int, new_name: str,
                           created_by: int, as_template: bool = False) -> Workflow:
        """
        Create a duplicate of an existing workflow.

        Args:
            workflow_id: ID of workflow to duplicate
            new_name: Name for the new workflow
            created_by: User creating the duplicate
            as_template: Whether to create as template

        Returns:
            Newly created workflow duplicate
        """
        try:
            # Get source workflow with all steps
            source_workflow = self.get_workflow_with_steps(workflow_id)

            # Create new workflow
            workflow_data = {
                'name': new_name,
                'description': source_workflow.description,
                'status': 'draft',
                'created_by': created_by,
                'is_template': as_template,
                'visibility': 'private',
                'version': '1.0',
                'default_locale': source_workflow.default_locale,
                'has_multiple_outcomes': source_workflow.has_multiple_outcomes,
                'estimated_duration': source_workflow.estimated_duration,
                'difficulty_level': source_workflow.difficulty_level,
                'theme_id': source_workflow.theme_id
            }

            new_workflow = self.create(workflow_data)

            # Duplicate steps and maintain ID mapping
            step_id_mapping = {}
            for step in source_workflow.steps:
                step_data = {
                    'workflow_id': new_workflow.id,
                    'name': step.name,
                    'description': step.description,
                    'instructions': step.instructions,
                    'display_order': step.display_order,
                    'step_type': step.step_type,
                    'estimated_duration': step.estimated_duration,
                    'is_milestone': step.is_milestone,
                    'ui_position_x': step.ui_position_x,
                    'ui_position_y': step.ui_position_y,
                    'is_decision_point': step.is_decision_point,
                    'is_outcome': step.is_outcome,
                    'condition_logic': step.condition_logic
                }

                new_step = WorkflowStep(**step_data)
                self.db_session.add(new_step)
                self.db_session.flush()

                step_id_mapping[step.id] = new_step.id

                # Duplicate resources
                for resource in step.resources:
                    resource_data = {
                        'step_id': new_step.id,
                        'resource_type': resource.resource_type,
                        'dynamic_material_id': resource.dynamic_material_id,
                        'tool_id': resource.tool_id,
                        'documentation_id': resource.documentation_id,
                        'quantity': resource.quantity,
                        'unit': resource.unit,
                        'notes': resource.notes,
                        'is_optional': resource.is_optional
                    }
                    self.db_session.add(WorkflowStepResource(**resource_data))

                # Duplicate decision options
                for option in step.decision_options:
                    option_data = {
                        'step_id': new_step.id,
                        'option_text': option.option_text,
                        'result_action': option.result_action,
                        'display_order': option.display_order,
                        'is_default': option.is_default
                    }
                    self.db_session.add(WorkflowDecisionOption(**option_data))

            # Update parent step relationships
            for step in source_workflow.steps:
                if step.parent_step_id:
                    new_step_id = step_id_mapping[step.id]
                    new_parent_id = step_id_mapping[step.parent_step_id]
                    self.db_session.query(WorkflowStep).filter(
                        WorkflowStep.id == new_step_id
                    ).update({'parent_step_id': new_parent_id})

            # Duplicate step connections
            for step in source_workflow.steps:
                for connection in step.outgoing_connections:
                    if connection.target_step_id in step_id_mapping:
                        connection_data = {
                            'source_step_id': step_id_mapping[step.id],
                            'target_step_id': step_id_mapping[connection.target_step_id],
                            'connection_type': connection.connection_type,
                            'condition': connection.condition,
                            'display_order': connection.display_order,
                            'is_default': connection.is_default
                        }
                        self.db_session.add(WorkflowStepConnection(**connection_data))

            # Duplicate outcomes
            for outcome in source_workflow.outcomes:
                outcome_data = {
                    'workflow_id': new_workflow.id,
                    'name': outcome.name,
                    'description': outcome.description,
                    'display_order': outcome.display_order,
                    'is_default': outcome.is_default,
                    'success_criteria': outcome.success_criteria
                }
                self.db_session.add(WorkflowOutcome(**outcome_data))

            self.db_session.commit()

            logger.info(f"Duplicated workflow {workflow_id} as {new_workflow.id} for user {created_by}")
            return new_workflow

        except Exception as e:
            logger.error(f"Error duplicating workflow {workflow_id}: {str(e)}")
            self.db_session.rollback()
            raise

    # ==================== Step Operations ====================

    def get_workflow_steps(self, workflow_id: int, include_resources: bool = True) -> List[WorkflowStep]:
        """Get all steps for a workflow."""
        try:
            query = self.db_session.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id
            ).options(
                selectinload(WorkflowStep.outgoing_connections),
                selectinload(WorkflowStep.decision_options)
            )

            if include_resources:
                query = query.options(selectinload(WorkflowStep.resources))

            steps = query.order_by(WorkflowStep.display_order).all()
            return steps

        except Exception as e:
            logger.error(f"Error retrieving workflow steps: {str(e)}")
            raise

    def get_initial_steps(self, workflow_id: int) -> List[WorkflowStep]:
        """
        Get initial steps for a workflow (steps with no incoming connections).

        Args:
            workflow_id: Workflow ID

        Returns:
            List of initial workflow steps
        """
        try:
            # Find steps that have no incoming connections and no parent step
            subquery = self.db_session.query(WorkflowStepConnection.target_step_id).filter(
                WorkflowStepConnection.target_step_id == WorkflowStep.id
            ).exists()

            initial_steps = self.db_session.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id,
                WorkflowStep.parent_step_id.is_(None),
                ~subquery
            ).order_by(WorkflowStep.display_order).all()

            # If no initial steps found, return the first step by display order
            if not initial_steps:
                first_step = self.db_session.query(WorkflowStep).filter(
                    WorkflowStep.workflow_id == workflow_id
                ).order_by(WorkflowStep.display_order).first()

                if first_step:
                    initial_steps = [first_step]

            logger.debug(f"Found {len(initial_steps)} initial steps for workflow {workflow_id}")
            return initial_steps

        except Exception as e:
            logger.error(f"Error getting initial steps for workflow {workflow_id}: {str(e)}")
            raise

    def get_next_steps(self, current_step_id: int,
                       execution_data: Optional[Dict[str, Any]] = None) -> List[WorkflowStep]:
        """
        Get next possible steps from a current step.

        Args:
            current_step_id: Current step ID
            execution_data: Optional execution data for conditional logic

        Returns:
            List of next possible steps
        """
        try:
            # Get outgoing connections from current step
            connections = self.db_session.query(WorkflowStepConnection).filter(
                WorkflowStepConnection.source_step_id == current_step_id
            ).options(joinedload(WorkflowStepConnection.target_step)).all()

            next_steps = []
            for connection in connections:
                # TODO: Implement condition evaluation if needed
                if connection.condition and execution_data:
                    # Placeholder for condition evaluation logic
                    # This would evaluate JSON conditions against execution_data
                    continue

                next_steps.append(connection.target_step)

            logger.debug(f"Found {len(next_steps)} next steps from step {current_step_id}")
            return next_steps

        except Exception as e:
            logger.error(f"Error getting next steps from {current_step_id}: {str(e)}")
            raise

    # ==================== Execution Operations ====================

    def get_active_executions(self, user_id: Optional[int] = None,
                              workflow_id: Optional[int] = None) -> List[WorkflowExecution]:
        """Get active workflow executions."""
        try:
            query = self.db_session.query(WorkflowExecution).filter(
                WorkflowExecution.status.in_(['active', 'paused'])
            ).options(joinedload(WorkflowExecution.workflow))

            if user_id:
                query = query.filter(WorkflowExecution.started_by == user_id)

            if workflow_id:
                query = query.filter(WorkflowExecution.workflow_id == workflow_id)

            executions = query.order_by(desc(WorkflowExecution.started_at)).all()
            return executions

        except Exception as e:
            logger.error(f"Error retrieving active executions: {str(e)}")
            raise

    # ==================== Statistics and Analytics ====================

    def get_workflow_statistics(self, workflow_id: int) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Dictionary with workflow statistics
        """
        try:
            # Basic execution counts
            total_executions = self.db_session.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id == workflow_id
            ).count()

            completed_executions = self.db_session.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.status == 'completed'
            ).count()

            # Average completion time
            avg_duration = self.db_session.query(func.avg(WorkflowExecution.total_duration)).filter(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.status == 'completed',
                WorkflowExecution.total_duration.is_not(None)
            ).scalar()

            # Most common outcome
            most_common_outcome = self.db_session.query(
                WorkflowOutcome.name,
                func.count(WorkflowExecution.id).label('count')
            ).join(
                WorkflowExecution, WorkflowExecution.selected_outcome_id == WorkflowOutcome.id
            ).filter(
                WorkflowOutcome.workflow_id == workflow_id,
                WorkflowExecution.status == 'completed'
            ).group_by(WorkflowOutcome.name).order_by(desc('count')).first()

            success_rate = (completed_executions / total_executions * 100) if total_executions > 0 else 0

            statistics = {
                'workflow_id': workflow_id,
                'total_executions': total_executions,
                'completed_executions': completed_executions,
                'average_completion_time': float(avg_duration) if avg_duration else None,
                'success_rate': success_rate,
                'most_common_outcome': most_common_outcome[0] if most_common_outcome else None
            }

            logger.debug(f"Generated statistics for workflow {workflow_id}")
            return statistics

        except Exception as e:
            logger.error(f"Error generating workflow statistics: {str(e)}")
            raise

    # ==================== Utility Methods ====================

    def workflow_exists(self, workflow_id: int) -> bool:
        """Check if workflow exists."""
        try:
            exists = self.db_session.query(Workflow.id).filter(
                Workflow.id == workflow_id
            ).first() is not None
            return exists
        except Exception as e:
            logger.error(f"Error checking workflow existence: {str(e)}")
            return False

    def get_workflow_by_name(self, name: str, created_by: Optional[int] = None) -> Optional[Workflow]:
        """Get workflow by name, optionally filtered by creator."""
        try:
            query = self.db_session.query(Workflow).filter(Workflow.name == name)

            if created_by:
                query = query.filter(Workflow.created_by == created_by)

            return query.first()

        except Exception as e:
            logger.error(f"Error retrieving workflow by name: {str(e)}")
            raise

    def update_workflow_status(self, workflow_id: int, new_status: str) -> bool:
        """Update workflow status."""
        try:
            updated_rows = self.db_session.query(Workflow).filter(
                Workflow.id == workflow_id
            ).update({
                'status': new_status,
                'updated_at': datetime.utcnow()
            })

            if updated_rows > 0:
                self.db_session.commit()
                logger.info(f"Updated workflow {workflow_id} status to {new_status}")
                return True
            else:
                logger.warning(f"No workflow found with ID {workflow_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating workflow status: {str(e)}")
            self.db_session.rollback()
            raise

    def delete_workflow_cascade(self, workflow_id: int) -> bool:
        """
        Delete workflow and all related data.

        Args:
            workflow_id: Workflow ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            workflow = self.get_by_id(workflow_id)
            if not workflow:
                raise EntityNotFoundException("Workflow", workflow_id)

            # Delete workflow (cascade will handle related entities)
            self.db_session.delete(workflow)
            self.db_session.commit()

            logger.info(f"Deleted workflow {workflow_id} and all related data")
            return True

        except Exception as e:
            logger.error(f"Error deleting workflow {workflow_id}: {str(e)}")
            self.db_session.rollback()
            raise