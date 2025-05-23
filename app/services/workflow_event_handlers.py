# File: app/services/workflow_event_handlers.py

import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.core.events import global_event_bus, DomainEvent
from app.repositories.repository_factory import RepositoryFactory
from app.services.dynamic_material_service import DynamicMaterialService
from app.services.tool_service import ToolService
from app.db.models.workflow import WorkflowExecution, WorkflowStepExecution

logger = logging.getLogger(__name__)


class WorkflowEventHandlers:
    """
    Event handlers for workflow-related events.
    Integrates workflow system with inventory, tools, and other systems.
    """

    def __init__(self, session: Session):
        """
        Initialize event handlers.

        Args:
            session: Database session
        """
        self.db_session = session

        # Initialize services for integration
        self.dynamic_material_service = DynamicMaterialService(session)
        # Note: ToolService would be initialized here if available
        # self.tool_service = ToolService(session)

        # Initialize repositories
        factory = RepositoryFactory(session)
        self.execution_repo = factory.create_workflow_execution_repository()
        self.workflow_repo = factory.create_workflow_repository()

    # ==================== Workflow Lifecycle Events ====================

    def handle_workflow_created(self, event: DomainEvent) -> None:
        """
        Handle workflow creation events.

        Args:
            event: Workflow created event
        """
        try:
            if event.event_type != "EntityCreatedEvent" or event.entity_type != "Workflow":
                return

            workflow_id = event.entity_id
            user_id = getattr(event, 'user_id', None)

            logger.info(f"Handling workflow creation for workflow {workflow_id} by user {user_id}")

            # Get workflow details
            workflow = self.workflow_repo.get_by_id(workflow_id)
            if not workflow:
                logger.warning(f"Workflow {workflow_id} not found for event handling")
                return

            # Analyze workflow for resource requirements
            self._analyze_workflow_resources(workflow)

            # Log workflow creation for audit
            self._log_workflow_activity(workflow_id, "created", user_id, {
                'workflow_name': workflow.name,
                'is_template': workflow.is_template,
                'estimated_duration': workflow.estimated_duration
            })

        except Exception as e:
            logger.error(f"Error handling workflow created event: {str(e)}")

    def handle_workflow_execution_started(self, event: DomainEvent) -> None:
        """
        Handle workflow execution started events.

        Args:
            event: Workflow execution started event
        """
        try:
            if event.event_type != "EntityCreatedEvent" or event.entity_type != "WorkflowExecution":
                return

            execution_id = event.entity_id
            user_id = getattr(event, 'user_id', None)

            logger.info(f"Handling workflow execution start for execution {execution_id}")

            # Get execution details
            execution = self.execution_repo.get_execution_with_details(execution_id)
            if not execution:
                logger.warning(f"Execution {execution_id} not found for event handling")
                return

            # Reserve required resources
            self._reserve_workflow_resources(execution)

            # Check tool availability
            self._check_tool_availability(execution)

            # Initialize progress tracking
            self._initialize_progress_tracking(execution)

            # Send notifications if configured
            self._send_execution_started_notifications(execution, user_id)

        except Exception as e:
            logger.error(f"Error handling workflow execution started event: {str(e)}")

    # ==================== Step Execution Events ====================

    def handle_step_started(self, event: DomainEvent) -> None:
        """
        Handle step started events for resource management.

        Args:
            event: Step started event
        """
        try:
            # This would be called when a step starts
            # For now, we'll implement basic logging
            logger.info(f"Step started event received: {event}")

            # In a real implementation, this would:
            # - Reserve step-specific resources
            # - Update tool usage tracking
            # - Send reminders for time-based steps
            # - Update progress metrics

        except Exception as e:
            logger.error(f"Error handling step started event: {str(e)}")

    def handle_step_completed(self, event: DomainEvent) -> None:
        """
        Handle step completed events.

        Args:
            event: Step completed event
        """
        try:
            logger.info(f"Step completed event received: {event}")

            # In a real implementation, this would:
            # - Release step resources
            # - Update progress tracking
            # - Trigger next step preparations
            # - Update completion statistics

        except Exception as e:
            logger.error(f"Error handling step completed event: {str(e)}")

    def handle_decision_made(self, event: DomainEvent) -> None:
        """
        Handle decision point events.

        Args:
            event: Decision made event
        """
        try:
            logger.info(f"Decision made event received: {event}")

            # In a real implementation, this would:
            # - Log decision for analytics
            # - Update workflow path tracking
            # - Adjust resource requirements based on path
            # - Update estimated completion time

        except Exception as e:
            logger.error(f"Error handling decision made event: {str(e)}")

    # ==================== Resource Management ====================

    def _analyze_workflow_resources(self, workflow) -> None:
        """
        Analyze workflow resource requirements.

        Args:
            workflow: Workflow to analyze
        """
        try:
            material_requirements = {}
            tool_requirements = set()

            for step in workflow.steps:
                for resource in step.resources:
                    if resource.resource_type == 'material' and resource.dynamic_material_id:
                        material_id = resource.dynamic_material_id
                        quantity = resource.quantity or 0

                        if material_id in material_requirements:
                            material_requirements[material_id] += quantity
                        else:
                            material_requirements[material_id] = quantity

                    elif resource.resource_type == 'tool' and resource.tool_id:
                        tool_requirements.add(resource.tool_id)

            # Log resource analysis
            logger.info(
                f"Workflow {workflow.id} requires {len(material_requirements)} materials and {len(tool_requirements)} tools")

            # Could store this analysis for later use
            self._store_resource_analysis(workflow.id, material_requirements, tool_requirements)

        except Exception as e:
            logger.error(f"Error analyzing workflow resources: {str(e)}")

    def _reserve_workflow_resources(self, execution: WorkflowExecution) -> None:
        """
        Reserve resources for workflow execution.

        Args:
            execution: Workflow execution
        """
        try:
            reserved_materials = []

            for step in execution.workflow.steps:
                for resource in step.resources:
                    if resource.resource_type == 'material' and resource.dynamic_material_id:
                        # Check material availability
                        material = self.dynamic_material_service.get_material(resource.dynamic_material_id)
                        if material and material.quantity >= (resource.quantity or 0):
                            # In a real implementation, create a reservation record
                            reservation_info = {
                                'material_id': resource.dynamic_material_id,
                                'quantity_reserved': resource.quantity,
                                'execution_id': execution.id,
                                'step_id': step.id
                            }
                            reserved_materials.append(reservation_info)
                            logger.debug(
                                f"Reserved {resource.quantity} units of material {resource.dynamic_material_id}")
                        else:
                            logger.warning(
                                f"Insufficient material {resource.dynamic_material_id} for execution {execution.id}")

            # Store reservation information
            if reserved_materials:
                execution_data = execution.execution_data or {}
                execution_data['reserved_materials'] = reserved_materials
                self.execution_repo.update_execution_status(
                    execution.id, execution.status, {'execution_data': execution_data}
                )

        except Exception as e:
            logger.error(f"Error reserving workflow resources: {str(e)}")

    def _check_tool_availability(self, execution: WorkflowExecution) -> None:
        """
        Check tool availability for workflow execution.

        Args:
            execution: Workflow execution
        """
        try:
            required_tools = set()

            for step in execution.workflow.steps:
                for resource in step.resources:
                    if resource.resource_type == 'tool' and resource.tool_id:
                        required_tools.add(resource.tool_id)

            if required_tools:
                logger.info(f"Execution {execution.id} requires {len(required_tools)} different tools")

                # In a real implementation, check tool availability
                # and create tool usage schedules
                unavailable_tools = []

                # Store tool requirements
                execution_data = execution.execution_data or {}
                execution_data['required_tools'] = list(required_tools)
                execution_data['unavailable_tools'] = unavailable_tools

                self.execution_repo.update_execution_status(
                    execution.id, execution.status, {'execution_data': execution_data}
                )

        except Exception as e:
            logger.error(f"Error checking tool availability: {str(e)}")

    # ==================== Progress Tracking ====================

    def _initialize_progress_tracking(self, execution: WorkflowExecution) -> None:
        """
        Initialize progress tracking for execution.

        Args:
            execution: Workflow execution
        """
        try:
            progress_data = {
                'started_at': execution.started_at.isoformat(),
                'total_steps': len(execution.workflow.steps),
                'completed_steps': 0,
                'estimated_completion': None,
                'milestones': []
            }

            # Identify milestone steps
            milestones = [
                {
                    'step_id': step.id,
                    'step_name': step.name,
                    'order': step.display_order
                }
                for step in execution.workflow.steps if step.is_milestone
            ]
            progress_data['milestones'] = milestones

            # Store progress tracking data
            execution_data = execution.execution_data or {}
            execution_data['progress_tracking'] = progress_data

            self.execution_repo.update_execution_status(
                execution.id, execution.status, {'execution_data': execution_data}
            )

            logger.debug(f"Initialized progress tracking for execution {execution.id}")

        except Exception as e:
            logger.error(f"Error initializing progress tracking: {str(e)}")

    # ==================== Notifications ====================

    def _send_execution_started_notifications(self, execution: WorkflowExecution, user_id: Optional[int]) -> None:
        """
        Send notifications when execution starts.

        Args:
            execution: Started execution
            user_id: User who started execution
        """
        try:
            # In a real implementation, this would integrate with notification service
            notification_data = {
                'type': 'workflow_started',
                'execution_id': execution.id,
                'workflow_name': execution.workflow.name,
                'user_id': user_id,
                'estimated_duration': execution.workflow.estimated_duration
            }

            logger.info(f"Would send notification: {notification_data}")

            # Could integrate with email, SMS, or push notification services

        except Exception as e:
            logger.error(f"Error sending execution started notifications: {str(e)}")

    # ==================== Activity Logging ====================

    def _log_workflow_activity(self, workflow_id: int, activity_type: str,
                               user_id: Optional[int], metadata: Dict[str, Any]) -> None:
        """
        Log workflow activity for audit and analytics.

        Args:
            workflow_id: Workflow ID
            activity_type: Type of activity
            user_id: User performing activity
            metadata: Additional metadata
        """
        try:
            activity_record = {
                'workflow_id': workflow_id,
                'activity_type': activity_type,
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': metadata
            }

            logger.info(f"Workflow activity: {activity_record}")

            # In a real implementation, store in activity log table
            # or send to analytics service

        except Exception as e:
            logger.error(f"Error logging workflow activity: {str(e)}")

    def _store_resource_analysis(self, workflow_id: int,
                                 material_requirements: Dict[int, float],
                                 tool_requirements: set) -> None:
        """
        Store resource analysis results.

        Args:
            workflow_id: Workflow ID
            material_requirements: Material requirements mapping
            tool_requirements: Set of required tool IDs
        """
        try:
            analysis_data = {
                'workflow_id': workflow_id,
                'material_requirements': material_requirements,
                'tool_requirements': list(tool_requirements),
                'analyzed_at': datetime.utcnow().isoformat()
            }

            # In a real implementation, store in workflow metadata
            # or dedicated analysis table
            logger.debug(f"Stored resource analysis for workflow {workflow_id}")

        except Exception as e:
            logger.error(f"Error storing resource analysis: {str(e)}")


def setup_workflow_event_handlers(session: Session) -> None:
    """
    Set up event handlers for workflow events.
    Call this during application startup.

    Args:
        session: Database session
    """
    try:
        handlers = WorkflowEventHandlers(session)

        # Subscribe to workflow events
        global_event_bus.subscribe(handlers.handle_workflow_created)
        global_event_bus.subscribe(handlers.handle_workflow_execution_started)
        global_event_bus.subscribe(handlers.handle_step_started)
        global_event_bus.subscribe(handlers.handle_step_completed)
        global_event_bus.subscribe(handlers.handle_decision_made)

        logger.info("Workflow event handlers setup completed")

    except Exception as e:
        logger.error(f"Error setting up workflow event handlers: {str(e)}")
        raise


# ==================== Event Handler Decorators ====================

def workflow_event_handler(event_type: str):
    """
    Decorator for workflow event handlers.

    Args:
        event_type: Type of event to handle
    """

    def decorator(func):
        def wrapper(event: DomainEvent):
            if event.event_type == event_type:
                return func(event)

        return wrapper

    return decorator

# Example usage with decorator:
# @workflow_event_handler("WorkflowStepStartedEvent")
# def handle_step_started_custom(event):
#     # Custom handling logic
#     pass