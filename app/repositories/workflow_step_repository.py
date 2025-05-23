# File: app/repositories/workflow_step_repository.py

import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, asc

from app.repositories.base_repository import BaseRepository
from app.db.models.workflow import (
    WorkflowStep, WorkflowStepConnection, WorkflowStepResource,
    WorkflowDecisionOption, WorkflowStepTranslation, Workflow
)
from app.core.exceptions import EntityNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class WorkflowStepRepository(BaseRepository):
    """
    Repository for workflow step-related database operations.
    Handles step management, connections, and resources.
    """

    def __init__(self, db_session: Session, encryption_service=None):
        """Initialize step repository with session and encryption service."""
        super().__init__(db_session, WorkflowStep)
        self.encryption_service = encryption_service

    # ==================== Core Step Operations ====================

    def get_step_with_details(self, step_id: int) -> Optional[WorkflowStep]:
        """
        Get step with all related data loaded.

        Args:
            step_id: Step ID

        Returns:
            WorkflowStep with full details or None
        """
        try:
            step = self.db_session.query(WorkflowStep).options(
                joinedload(WorkflowStep.workflow),
                selectinload(WorkflowStep.outgoing_connections).joinedload(WorkflowStepConnection.target_step),
                selectinload(WorkflowStep.incoming_connections).joinedload(WorkflowStepConnection.source_step),
                selectinload(WorkflowStep.resources),
                selectinload(WorkflowStep.decision_options),
                selectinload(WorkflowStep.translations),
                joinedload(WorkflowStep.parent_step),
                selectinload(WorkflowStep.child_steps)
            ).filter(WorkflowStep.id == step_id).first()

            if step:
                logger.debug(f"Retrieved step {step_id} with {len(step.resources)} resources")

            return step

        except Exception as e:
            logger.error(f"Error retrieving step {step_id}: {str(e)}")
            raise

    def get_workflow_steps_ordered(self, workflow_id: int) -> List[WorkflowStep]:
        """
        Get all steps for a workflow ordered by display_order.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of workflow steps ordered by display_order
        """
        try:
            steps = self.db_session.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id
            ).options(
                selectinload(WorkflowStep.resources),
                selectinload(WorkflowStep.decision_options),
                selectinload(WorkflowStep.outgoing_connections)
            ).order_by(WorkflowStep.display_order).all()

            logger.debug(f"Retrieved {len(steps)} steps for workflow {workflow_id}")
            return steps

        except Exception as e:
            logger.error(f"Error retrieving workflow steps: {str(e)}")
            raise

    def create_step_with_resources(self, step_data: Dict[str, Any],
                                   resources: Optional[List[Dict[str, Any]]] = None,
                                   decision_options: Optional[List[Dict[str, Any]]] = None) -> WorkflowStep:
        """
        Create a step with associated resources and decision options.

        Args:
            step_data: Step creation data
            resources: Optional list of resource data
            decision_options: Optional list of decision option data

        Returns:
            Created workflow step
        """
        try:
            # Create the step
            step = WorkflowStep(**step_data)
            self.db_session.add(step)
            self.db_session.flush()  # Get the step ID

            # Add resources if provided
            if resources:
                for resource_data in resources:
                    resource_data['step_id'] = step.id
                    resource = WorkflowStepResource(**resource_data)
                    self.db_session.add(resource)

            # Add decision options if provided
            if decision_options:
                for option_data in decision_options:
                    option_data['step_id'] = step.id
                    option = WorkflowDecisionOption(**option_data)
                    self.db_session.add(option)

            self.db_session.commit()

            logger.info(
                f"Created step {step.id} with {len(resources or [])} resources and {len(decision_options or [])} decision options")
            return step

        except Exception as e:
            logger.error(f"Error creating step with resources: {str(e)}")
            self.db_session.rollback()
            raise

    def update_step_order(self, workflow_id: int, step_orders: List[Tuple[int, int]]) -> bool:
        """
        Update the display order of multiple steps.

        Args:
            workflow_id: Workflow ID
            step_orders: List of (step_id, new_order) tuples

        Returns:
            True if updated successfully
        """
        try:
            for step_id, new_order in step_orders:
                self.db_session.query(WorkflowStep).filter(
                    WorkflowStep.id == step_id,
                    WorkflowStep.workflow_id == workflow_id
                ).update({'display_order': new_order})

            self.db_session.commit()
            logger.info(f"Updated order for {len(step_orders)} steps in workflow {workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating step orders: {str(e)}")
            self.db_session.rollback()
            raise

    def get_steps_by_type(self, workflow_id: int, step_type: str) -> List[WorkflowStep]:
        """
        Get steps by type within a workflow.

        Args:
            workflow_id: Workflow ID
            step_type: Step type to filter by

        Returns:
            List of steps matching the type
        """
        try:
            steps = self.db_session.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id,
                WorkflowStep.step_type == step_type
            ).options(
                selectinload(WorkflowStep.resources)
            ).order_by(WorkflowStep.display_order).all()

            return steps

        except Exception as e:
            logger.error(f"Error retrieving steps by type: {str(e)}")
            raise

    # ==================== Step Connection Operations ====================

    def create_step_connection(self, source_step_id: int, target_step_id: int,
                               connection_type: str = 'sequential',
                               condition: Optional[str] = None,
                               is_default: bool = False) -> WorkflowStepConnection:
        """
        Create a connection between two steps.

        Args:
            source_step_id: Source step ID
            target_step_id: Target step ID
            connection_type: Type of connection
            condition: Optional condition for the connection
            is_default: Whether this is the default connection

        Returns:
            Created connection
        """
        try:
            # Verify steps exist and are in the same workflow
            source_step = self.get_by_id(source_step_id)
            target_step = self.get_by_id(target_step_id)

            if not source_step or not target_step:
                raise EntityNotFoundException("WorkflowStep", source_step_id if not source_step else target_step_id)

            if source_step.workflow_id != target_step.workflow_id:
                raise ValidationException("Steps must be in the same workflow")

            # Check for existing connection
            existing = self.db_session.query(WorkflowStepConnection).filter(
                WorkflowStepConnection.source_step_id == source_step_id,
                WorkflowStepConnection.target_step_id == target_step_id,
                WorkflowStepConnection.connection_type == connection_type
            ).first()

            if existing:
                raise ValidationException("Connection already exists between these steps")

            # Create connection
            connection_data = {
                'source_step_id': source_step_id,
                'target_step_id': target_step_id,
                'connection_type': connection_type,
                'condition': condition,
                'is_default': is_default
            }

            connection = WorkflowStepConnection(**connection_data)
            self.db_session.add(connection)
            self.db_session.commit()

            logger.info(f"Created {connection_type} connection from step {source_step_id} to {target_step_id}")
            return connection

        except Exception as e:
            logger.error(f"Error creating step connection: {str(e)}")
            self.db_session.rollback()
            raise

    def get_step_connections(self, step_id: int, direction: str = 'outgoing') -> List[WorkflowStepConnection]:
        """
        Get connections for a step.

        Args:
            step_id: Step ID
            direction: 'outgoing', 'incoming', or 'both'

        Returns:
            List of connections
        """
        try:
            if direction == 'outgoing':
                connections = self.db_session.query(WorkflowStepConnection).filter(
                    WorkflowStepConnection.source_step_id == step_id
                ).options(joinedload(WorkflowStepConnection.target_step)).all()
            elif direction == 'incoming':
                connections = self.db_session.query(WorkflowStepConnection).filter(
                    WorkflowStepConnection.target_step_id == step_id
                ).options(joinedload(WorkflowStepConnection.source_step)).all()
            else:  # both
                outgoing = self.db_session.query(WorkflowStepConnection).filter(
                    WorkflowStepConnection.source_step_id == step_id
                ).options(joinedload(WorkflowStepConnection.target_step)).all()
                incoming = self.db_session.query(WorkflowStepConnection).filter(
                    WorkflowStepConnection.target_step_id == step_id
                ).options(joinedload(WorkflowStepConnection.source_step)).all()
                connections = outgoing + incoming

            return connections

        except Exception as e:
            logger.error(f"Error retrieving step connections: {str(e)}")
            raise

    def delete_step_connection(self, connection_id: int) -> bool:
        """
        Delete a step connection.

        Args:
            connection_id: Connection ID

        Returns:
            True if deleted successfully
        """
        try:
            deleted_rows = self.db_session.query(WorkflowStepConnection).filter(
                WorkflowStepConnection.id == connection_id
            ).delete()

            if deleted_rows > 0:
                self.db_session.commit()
                logger.info(f"Deleted step connection {connection_id}")
                return True
            else:
                logger.warning(f"No connection found with ID {connection_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting step connection: {str(e)}")
            self.db_session.rollback()
            raise

    # ==================== Resource Operations ====================

    def add_step_resource(self, step_id: int, resource_data: Dict[str, Any]) -> WorkflowStepResource:
        """
        Add a resource to a step.

        Args:
            step_id: Step ID
            resource_data: Resource data

        Returns:
            Created resource
        """
        try:
            resource_data['step_id'] = step_id
            resource = WorkflowStepResource(**resource_data)
            self.db_session.add(resource)
            self.db_session.commit()

            logger.info(f"Added {resource_data['resource_type']} resource to step {step_id}")
            return resource

        except Exception as e:
            logger.error(f"Error adding step resource: {str(e)}")
            self.db_session.rollback()
            raise

    def get_step_resources(self, step_id: int, resource_type: Optional[str] = None) -> List[WorkflowStepResource]:
        """
        Get resources for a step.

        Args:
            step_id: Step ID
            resource_type: Optional resource type filter

        Returns:
            List of step resources
        """
        try:
            query = self.db_session.query(WorkflowStepResource).filter(
                WorkflowStepResource.step_id == step_id
            )

            if resource_type:
                query = query.filter(WorkflowStepResource.resource_type == resource_type)

            resources = query.all()
            return resources

        except Exception as e:
            logger.error(f"Error retrieving step resources: {str(e)}")
            raise

    def update_step_resource(self, resource_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Update a step resource.

        Args:
            resource_id: Resource ID
            update_data: Update data

        Returns:
            True if updated successfully
        """
        try:
            updated_rows = self.db_session.query(WorkflowStepResource).filter(
                WorkflowStepResource.id == resource_id
            ).update(update_data)

            if updated_rows > 0:
                self.db_session.commit()
                logger.info(f"Updated step resource {resource_id}")
                return True
            else:
                logger.warning(f"No resource found with ID {resource_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating step resource: {str(e)}")
            self.db_session.rollback()
            raise

    def delete_step_resource(self, resource_id: int) -> bool:
        """
        Delete a step resource.

        Args:
            resource_id: Resource ID

        Returns:
            True if deleted successfully
        """
        try:
            deleted_rows = self.db_session.query(WorkflowStepResource).filter(
                WorkflowStepResource.id == resource_id
            ).delete()

            if deleted_rows > 0:
                self.db_session.commit()
                logger.info(f"Deleted step resource {resource_id}")
                return True
            else:
                logger.warning(f"No resource found with ID {resource_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting step resource: {str(e)}")
            self.db_session.rollback()
            raise

    # ==================== Decision Option Operations ====================

    def add_decision_option(self, step_id: int, option_data: Dict[str, Any]) -> WorkflowDecisionOption:
        """
        Add a decision option to a step.

        Args:
            step_id: Step ID
            option_data: Option data

        Returns:
            Created decision option
        """
        try:
            option_data['step_id'] = step_id
            option = WorkflowDecisionOption(**option_data)
            self.db_session.add(option)
            self.db_session.commit()

            logger.info(f"Added decision option to step {step_id}")
            return option

        except Exception as e:
            logger.error(f"Error adding decision option: {str(e)}")
            self.db_session.rollback()
            raise

    def get_decision_options(self, step_id: int) -> List[WorkflowDecisionOption]:
        """
        Get decision options for a step.

        Args:
            step_id: Step ID

        Returns:
            List of decision options ordered by display_order
        """
        try:
            options = self.db_session.query(WorkflowDecisionOption).filter(
                WorkflowDecisionOption.step_id == step_id
            ).order_by(WorkflowDecisionOption.display_order).all()

            return options

        except Exception as e:
            logger.error(f"Error retrieving decision options: {str(e)}")
            raise

    # ==================== Step Analysis and Validation ====================

    def find_orphaned_steps(self, workflow_id: int) -> List[WorkflowStep]:
        """
        Find steps that are not connected to the workflow flow.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of orphaned steps
        """
        try:
            # Get all steps in workflow
            all_steps = self.get_workflow_steps_ordered(workflow_id)

            # Get steps that have incoming connections
            connected_step_ids = set()

            # Add initial steps (no incoming connections, no parent)
            for step in all_steps:
                incoming_connections = self.db_session.query(WorkflowStepConnection).filter(
                    WorkflowStepConnection.target_step_id == step.id
                ).count()

                if incoming_connections == 0 and step.parent_step_id is None:
                    connected_step_ids.add(step.id)

            # Traverse from initial steps to find all reachable steps
            visited = set()
            to_visit = list(connected_step_ids)

            while to_visit:
                current_step_id = to_visit.pop()
                if current_step_id in visited:
                    continue

                visited.add(current_step_id)

                # Add connected steps
                outgoing = self.db_session.query(WorkflowStepConnection).filter(
                    WorkflowStepConnection.source_step_id == current_step_id
                ).all()

                for connection in outgoing:
                    if connection.target_step_id not in visited:
                        to_visit.append(connection.target_step_id)

            # Find orphaned steps
            all_step_ids = {step.id for step in all_steps}
            orphaned_ids = all_step_ids - visited

            orphaned_steps = [step for step in all_steps if step.id in orphaned_ids]

            if orphaned_steps:
                logger.warning(f"Found {len(orphaned_steps)} orphaned steps in workflow {workflow_id}")

            return orphaned_steps

        except Exception as e:
            logger.error(f"Error finding orphaned steps: {str(e)}")
            raise

    def validate_step_connections(self, workflow_id: int) -> List[Dict[str, Any]]:
        """
        Validate step connections for circular references and other issues.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of validation issues
        """
        try:
            issues = []

            # Check for circular references
            circular_refs = self._find_circular_references(workflow_id)
            if circular_refs:
                issues.extend(circular_refs)

            # Check for missing connections
            missing_connections = self._find_missing_connections(workflow_id)
            if missing_connections:
                issues.extend(missing_connections)

            return issues

        except Exception as e:
            logger.error(f"Error validating step connections: {str(e)}")
            raise

    # ==================== Helper Methods ====================

    def _find_circular_references(self, workflow_id: int) -> List[Dict[str, Any]]:
        """Find circular references in step connections."""
        issues = []

        # Get all connections in workflow
        connections = self.db_session.query(WorkflowStepConnection).join(
            WorkflowStep, WorkflowStepConnection.source_step_id == WorkflowStep.id
        ).filter(WorkflowStep.workflow_id == workflow_id).all()

        # Build adjacency list
        graph = {}
        for connection in connections:
            if connection.source_step_id not in graph:
                graph[connection.source_step_id] = []
            graph[connection.source_step_id].append(connection.target_step_id)

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node, path):
            if node in rec_stack:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                issues.append({
                    'type': 'circular_reference',
                    'description': f'Circular reference detected in steps: {" -> ".join(map(str, cycle))}',
                    'step_ids': cycle
                })
                return True

            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if has_cycle(neighbor, path.copy()):
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                has_cycle(node, [])

        return issues

    def _find_missing_connections(self, workflow_id: int) -> List[Dict[str, Any]]:
        """Find steps that might be missing connections."""
        issues = []

        # Get steps without outgoing connections (except outcome steps)
        steps_without_outgoing = self.db_session.query(WorkflowStep).filter(
            WorkflowStep.workflow_id == workflow_id,
            WorkflowStep.is_outcome == False
        ).filter(
            ~WorkflowStep.id.in_(
                self.db_session.query(WorkflowStepConnection.source_step_id).distinct()
            )
        ).all()

        for step in steps_without_outgoing:
            issues.append({
                'type': 'missing_outgoing_connection',
                'description': f'Step "{step.name}" has no outgoing connections',
                'step_id': step.id
            })

        return issues