# File: app/services/workflow_service.py

import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base_service import BaseService
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.repository_factory import RepositoryFactory
from app.db.models.workflow import (
    Workflow, WorkflowStep, WorkflowExecution, WorkflowOutcome,
    WorkflowStepConnection, WorkflowStepResource, WorkflowDecisionOption
)
from app.core.exceptions import (
    EntityNotFoundException, ValidationException, BusinessRuleException
)
from app.core.events import global_event_bus, EntityCreatedEvent, EntityUpdatedEvent
from app.services.enum_service import EnumService

logger = logging.getLogger(__name__)


class WorkflowService(BaseService):
    """
    Core business logic service for workflow management.
    Follows existing HideSync service patterns with corrected architecture integration.
    """

    def __init__(self, session: Session, repository: Optional[WorkflowRepository] = None,
                 security_context=None):
        """
        Initialize the workflow service.

        Args:
            session: Database session
            repository: Optional workflow repository (for dependency injection)
            security_context: Security context with current user info
        """
        self.db_session = session
        self.security_context = security_context

        # Initialize repositories using RepositoryFactory pattern
        if repository:
            self.workflow_repo = repository
        else:
            factory = RepositoryFactory(session)
            self.workflow_repo = factory.create_workflow_repository()

        # Initialize enum service for validation
        self.enum_service = EnumService(session)

    # ==================== Core Workflow Operations ====================

    def create_workflow(self, workflow_data: Dict[str, Any], user_id: int) -> Workflow:
        """
        Create a new workflow.

        Args:
            workflow_data: Workflow creation data
            user_id: ID of the user creating the workflow

        Returns:
            Created workflow

        Raises:
            ValidationException: If workflow data is invalid
            BusinessRuleException: If business rules are violated
        """
        try:
            # Validate required fields
            if not workflow_data.get('name'):
                raise ValidationException("Workflow name is required")

            # Check for duplicate names for the user
            existing_workflow = self.workflow_repo.get_workflow_by_name(
                workflow_data['name'], user_id
            )
            if existing_workflow:
                raise BusinessRuleException(f"Workflow with name '{workflow_data['name']}' already exists")

            # Sanitize and prepare data
            sanitized_data = self._sanitize_workflow_data(workflow_data)
            sanitized_data['created_by'] = user_id
            sanitized_data['status'] = sanitized_data.get('status', 'draft')

            # Create workflow
            workflow = self.workflow_repo.create(sanitized_data)

            # Emit creation event
            event = EntityCreatedEvent(
                entity_id=workflow.id,
                entity_type="Workflow",
                user_id=user_id
            )
            global_event_bus.publish(event)

            logger.info(f"Created workflow {workflow.id} '{workflow.name}' by user {user_id}")
            return workflow

        except IntegrityError as e:
            logger.error(f"Database integrity error creating workflow: {str(e)}")
            self.db_session.rollback()
            raise BusinessRuleException("Workflow with this name already exists")
        except (ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error creating workflow: {str(e)}")
            self.db_session.rollback()
            raise

    def update_workflow(self, workflow_id: int, update_data: Dict[str, Any],
                        user_id: int) -> Workflow:
        """
        Update an existing workflow.

        Args:
            workflow_id: ID of workflow to update
            update_data: Update data
            user_id: ID of user performing update

        Returns:
            Updated workflow

        Raises:
            EntityNotFoundException: If workflow not found
            ValidationException: If update data is invalid
            BusinessRuleException: If user doesn't have permission
        """
        try:
            # Get existing workflow
            workflow = self.workflow_repo.get_by_id(workflow_id)
            if not workflow:
                raise EntityNotFoundException("Workflow", workflow_id)

            # Check permissions
            if workflow.created_by != user_id and not self._is_admin_user(user_id):
                raise BusinessRuleException("Insufficient permissions to update this workflow")

            # Validate update data
            sanitized_data = self._sanitize_workflow_data(update_data, is_update=True)
            sanitized_data['updated_at'] = datetime.utcnow()

            # Update workflow
            updated_workflow = self.workflow_repo.update(workflow_id, sanitized_data)

            # Emit update event
            event = EntityUpdatedEvent(
                entity_id=workflow_id,
                entity_type="Workflow",
                user_id=user_id
            )
            global_event_bus.publish(event)

            logger.info(f"Updated workflow {workflow_id} by user {user_id}")
            return updated_workflow

        except (EntityNotFoundException, ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error updating workflow {workflow_id}: {str(e)}")
            self.db_session.rollback()
            raise

    def get_workflow(self, workflow_id: int, user_id: Optional[int] = None) -> Workflow:
        """
        Get a workflow by ID with access control.

        Args:
            workflow_id: Workflow ID
            user_id: Optional user ID for access control

        Returns:
            Workflow object

        Raises:
            EntityNotFoundException: If workflow not found
            BusinessRuleException: If access denied
        """
        try:
            workflow = self.workflow_repo.get_workflow_with_steps(workflow_id)

            # Check access permissions
            if user_id and not self._can_access_workflow(workflow, user_id):
                raise BusinessRuleException("Access denied to this workflow")

            return workflow

        except EntityNotFoundException:
            raise
        except BusinessRuleException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving workflow {workflow_id}: {str(e)}")
            raise

    def delete_workflow(self, workflow_id: int, user_id: int) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: Workflow ID
            user_id: User performing deletion

        Returns:
            True if deleted successfully

        Raises:
            EntityNotFoundException: If workflow not found
            BusinessRuleException: If user doesn't have permission or workflow has active executions
        """
        try:
            # Get workflow
            workflow = self.workflow_repo.get_by_id(workflow_id)
            if not workflow:
                raise EntityNotFoundException("Workflow", workflow_id)

            # Check permissions
            if workflow.created_by != user_id and not self._is_admin_user(user_id):
                raise BusinessRuleException("Insufficient permissions to delete this workflow")

            # Check for active executions
            active_executions = self.workflow_repo.get_active_executions(workflow_id=workflow_id)
            if active_executions:
                raise BusinessRuleException("Cannot delete workflow with active executions")

            # Delete workflow
            success = self.workflow_repo.delete_workflow_cascade(workflow_id)

            if success:
                logger.info(f"Deleted workflow {workflow_id} by user {user_id}")

            return success

        except (EntityNotFoundException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error deleting workflow {workflow_id}: {str(e)}")
            raise

    def duplicate_workflow(self, workflow_id: int, new_name: str, user_id: int,
                           as_template: bool = False) -> Workflow:
        """
        Create a duplicate of an existing workflow.

        Args:
            workflow_id: Source workflow ID
            new_name: Name for duplicate
            user_id: User creating duplicate
            as_template: Whether to create as template

        Returns:
            New duplicated workflow
        """
        try:
            # Verify source workflow exists and user has access
            source_workflow = self.get_workflow(workflow_id, user_id)

            # Check name doesn't already exist for user
            existing = self.workflow_repo.get_workflow_by_name(new_name, user_id)
            if existing:
                raise BusinessRuleException(f"Workflow with name '{new_name}' already exists")

            # Create duplicate
            duplicate = self.workflow_repo.duplicate_workflow(
                workflow_id, new_name, user_id, as_template
            )

            # Emit creation event
            event = EntityCreatedEvent(
                entity_id=duplicate.id,
                entity_type="Workflow",
                user_id=user_id
            )
            global_event_bus.publish(event)

            logger.info(f"Duplicated workflow {workflow_id} as {duplicate.id} for user {user_id}")
            return duplicate

        except (EntityNotFoundException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error duplicating workflow {workflow_id}: {str(e)}")
            raise

    # ==================== Template Management ====================

    def get_workflow_templates(self, user_id: Optional[int] = None) -> List[Workflow]:
        """
        Get available workflow templates for a user.

        Args:
            user_id: Optional user ID for filtering

        Returns:
            List of accessible workflow templates
        """
        try:
            templates = self.workflow_repo.get_workflow_templates(user_id, include_system=True)
            logger.debug(f"Retrieved {len(templates)} templates for user {user_id}")
            return templates

        except Exception as e:
            logger.error(f"Error retrieving workflow templates: {str(e)}")
            raise

    def publish_as_template(self, workflow_id: int, user_id: int,
                            visibility: str = 'public') -> Workflow:
        """
        Publish a workflow as a template.

        Args:
            workflow_id: Workflow to publish
            user_id: User performing action
            visibility: Template visibility (public, private)

        Returns:
            Updated workflow
        """
        try:
            # Get workflow
            workflow = self.get_workflow(workflow_id, user_id)

            # Check permissions
            if workflow.created_by != user_id and not self._is_admin_user(user_id):
                raise BusinessRuleException("Insufficient permissions to publish this workflow")

            # Validate workflow is ready for publication
            validation_errors = self._validate_workflow_for_publication(workflow)
            if validation_errors:
                raise ValidationException(f"Workflow validation failed: {', '.join(validation_errors)}")

            # Update workflow
            update_data = {
                'is_template': True,
                'status': 'published',
                'visibility': visibility
            }

            updated_workflow = self.workflow_repo.update(workflow_id, update_data)

            logger.info(f"Published workflow {workflow_id} as template by user {user_id}")
            return updated_workflow

        except (EntityNotFoundException, ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error publishing workflow {workflow_id} as template: {str(e)}")
            raise

    # ==================== Search and Discovery ====================

    def search_workflows(self, search_params: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Search workflows with filtering and pagination.

        Args:
            search_params: Search parameters
            user_id: Optional user ID for access filtering

        Returns:
            Paginated search results
        """
        try:
            # Add user filter if provided
            if user_id and 'created_by' not in search_params:
                search_params['created_by'] = user_id

            results = self.workflow_repo.search_workflows(**search_params)

            # Filter results based on access permissions
            if user_id:
                accessible_workflows = []
                for workflow in results['items']:
                    if self._can_access_workflow(workflow, user_id):
                        accessible_workflows.append(workflow)

                results['items'] = accessible_workflows
                results['total'] = len(accessible_workflows)

            return results

        except Exception as e:
            logger.error(f"Error searching workflows: {str(e)}")
            raise

    # ==================== Execution Management ====================

    def start_workflow_execution(self, workflow_id: int, user_id: int,
                                 selected_outcome_id: Optional[int] = None) -> WorkflowExecution:
        """
        Start a new workflow execution.

        Args:
            workflow_id: ID of the workflow to execute
            user_id: ID of the user starting the execution
            selected_outcome_id: Optional specific outcome to target

        Returns:
            Created workflow execution

        Raises:
            EntityNotFoundException: If workflow not found
            BusinessRuleException: If workflow cannot be executed
        """
        try:
            # Validate workflow exists and is executable
            workflow = self.get_workflow(workflow_id, user_id)

            if workflow.status not in ['active', 'published']:
                raise BusinessRuleException(f"Cannot execute workflow with status '{workflow.status}'")

            # Validate selected outcome if provided
            if selected_outcome_id:
                outcome = next((o for o in workflow.outcomes if o.id == selected_outcome_id), None)
                if not outcome:
                    raise ValidationException("Selected outcome not found in workflow")

            # Check resource availability
            resource_issues = self._check_resource_availability(workflow)
            if resource_issues:
                logger.warning(f"Resource issues for workflow {workflow_id}: {resource_issues}")
                # Could emit warning event or continue based on business rules

            # Create execution record
            execution_data = {
                'workflow_id': workflow_id,
                'started_by': user_id,
                'status': 'active',
                'selected_outcome_id': selected_outcome_id,
                'started_at': datetime.utcnow(),
                'execution_data': {}
            }

            # Use execution repository to create
            factory = RepositoryFactory(self.db_session)
            exec_repo = factory.create_workflow_execution_repository()
            execution = exec_repo.create(execution_data)

            # Initialize first steps
            self._initialize_workflow_execution(execution)

            # Emit start event
            event = EntityCreatedEvent(
                entity_id=execution.id,
                entity_type="WorkflowExecution",
                user_id=user_id
            )
            global_event_bus.publish(event)

            logger.info(f"Started execution {execution.id} for workflow {workflow_id} by user {user_id}")
            return execution

        except (EntityNotFoundException, ValidationException, BusinessRuleException):
            raise
        except Exception as e:
            logger.error(f"Error starting workflow execution: {str(e)}")
            self.db_session.rollback()
            raise

    # ==================== Statistics and Analytics ====================

    def get_workflow_statistics(self, workflow_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a workflow.

        Args:
            workflow_id: Workflow ID
            user_id: Optional user ID for access control

        Returns:
            Workflow statistics
        """
        try:
            # Verify access
            workflow = self.get_workflow(workflow_id, user_id)

            # Get statistics
            stats = self.workflow_repo.get_workflow_statistics(workflow_id)

            return stats

        except Exception as e:
            logger.error(f"Error getting workflow statistics: {str(e)}")
            raise

    # ==================== Private Helper Methods ====================

    def _sanitize_workflow_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """
        Sanitize and validate workflow input data.

        Args:
            data: Raw workflow data
            is_update: Whether this is an update operation

        Returns:
            Sanitized workflow data

        Raises:
            ValidationException: If data is invalid
        """
        sanitized = {}

        # String fields - strip whitespace and validate length
        string_fields = ['name', 'description', 'status', 'visibility', 'version', 'default_locale', 'difficulty_level']
        for field in string_fields:
            if field in data:
                value = str(data[field]).strip() if data[field] is not None else None
                if value:
                    if field == 'name' and len(value) > 200:
                        raise ValidationException("Workflow name must be 200 characters or less")
                    if field == 'description' and len(value) > 5000:
                        raise ValidationException("Description must be 5000 characters or less")
                    sanitized[field] = value
                elif not is_update:
                    sanitized[field] = None

        # Boolean fields
        boolean_fields = ['is_template', 'has_multiple_outcomes']
        for field in boolean_fields:
            if field in data:
                sanitized[field] = bool(data[field])

        # Numeric fields
        if 'estimated_duration' in data and data['estimated_duration'] is not None:
            duration = float(data['estimated_duration'])
            if duration < 0:
                raise ValidationException("Estimated duration cannot be negative")
            sanitized['estimated_duration'] = duration

        # Integer fields
        int_fields = ['project_id', 'theme_id']
        for field in int_fields:
            if field in data and data[field] is not None:
                sanitized[field] = int(data[field])

        # Validate enum values using enum service
        if 'status' in sanitized:
            valid_statuses = self.enum_service.get_enum_values('workflow_status', 'en')
            valid_status_codes = [status['code'] for status in valid_statuses]
            if sanitized['status'] not in valid_status_codes:
                raise ValidationException(f"Invalid status: {sanitized['status']}. Valid options: {valid_status_codes}")

        if 'visibility' in sanitized:
            if sanitized['visibility'] not in ['private', 'public', 'shared']:
                raise ValidationException("Visibility must be private, public, or shared")

        return sanitized

    def _can_access_workflow(self, workflow: Workflow, user_id: int) -> bool:
        """
        Check if user can access a workflow.

        Args:
            workflow: Workflow object
            user_id: User ID

        Returns:
            True if user has access
        """
        # Creator always has access
        if workflow.created_by == user_id:
            return True

        # Public workflows are accessible
        if workflow.visibility == 'public':
            return True

        # System admin access (if applicable)
        if self._is_admin_user(user_id):
            return True

        # TODO: Implement shared workflow access logic
        # This would check if workflow is shared with user/group

        return False

    def _is_admin_user(self, user_id: int) -> bool:
        """
        Check if user is an admin.

        Args:
            user_id: User ID

        Returns:
            True if user is admin
        """
        # TODO: Implement admin check using your user system
        # This should check user roles/permissions
        return False

    def _validate_workflow_for_publication(self, workflow: Workflow) -> List[str]:
        """
        Validate that a workflow is ready for publication as template.

        Args:
            workflow: Workflow to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Must have at least one step
        if not workflow.steps:
            errors.append("Workflow must have at least one step")

        # Must have initial steps
        initial_steps = self.workflow_repo.get_initial_steps(workflow.id)
        if not initial_steps:
            errors.append("Workflow must have at least one initial step")

        # Check for orphaned steps (steps with no path from initial)
        # TODO: Implement graph traversal validation

        # If multiple outcomes, must have outcome definitions
        if workflow.has_multiple_outcomes and not workflow.outcomes:
            errors.append("Workflow with multiple outcomes must define outcome options")

        return errors

    def _check_resource_availability(self, workflow: Workflow) -> List[str]:
        """
        Check availability of required resources for workflow execution.

        Args:
            workflow: Workflow to check

        Returns:
            List of resource availability issues
        """
        issues = []

        # Check dynamic materials
        for step in workflow.steps:
            for resource in step.resources:
                if resource.resource_type == 'material' and resource.dynamic_material_id:
                    # TODO: Check material availability using DynamicMaterialService
                    # This would integrate with your material system
                    pass
                elif resource.resource_type == 'tool' and resource.tool_id:
                    # TODO: Check tool availability
                    pass

        return issues

    def _initialize_workflow_execution(self, execution: WorkflowExecution) -> None:
        """
        Initialize a workflow execution by setting up the first steps.

        Args:
            execution: The workflow execution to initialize
        """
        try:
            # Get initial steps (steps with no incoming connections or parent steps)
            initial_steps = self.workflow_repo.get_initial_steps(execution.workflow_id)

            # Create step execution records for initial steps
            factory = RepositoryFactory(self.db_session)
            step_exec_repo = factory.create_workflow_step_execution_repository()

            for step in initial_steps:
                step_exec_data = {
                    'execution_id': execution.id,
                    'step_id': step.id,
                    'status': 'ready',
                    'created_at': datetime.utcnow()
                }
                step_exec_repo.create(step_exec_data)

            # Update execution with current step
            if initial_steps:
                execution.current_step_id = initial_steps[0].id
                self.db_session.commit()

            logger.debug(f"Initialized {len(initial_steps)} initial steps for execution {execution.id}")

        except Exception as e:
            logger.error(f"Error initializing workflow execution: {str(e)}")
            raise