# File: app/services/workflow_resource_service.py

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.repositories.repository_factory import RepositoryFactory
from app.services.dynamic_material_service import DynamicMaterialService
from app.db.models.workflow import (
    WorkflowExecution, WorkflowStep, WorkflowStepResource, WorkflowStepExecution
)
from app.core.exceptions import (
    EntityNotFoundException, ValidationException, BusinessRuleException
)

logger = logging.getLogger(__name__)


class WorkflowResourceService(BaseService):
    """
    Service for managing workflow resource integration with storage systems.
    Handles material reservations, tool availability, and resource planning.
    """

    def __init__(self, session: Session):
        """
        Initialize the workflow resource service.

        Args:
            session: Database session
        """
        self.db_session = session

        # Initialize services for resource management
        self.dynamic_material_service = DynamicMaterialService(session)

        # Initialize repositories
        factory = RepositoryFactory(session)
        self.execution_repo = factory.create_workflow_execution_repository()
        self.workflow_repo = factory.create_workflow_repository()
        self.step_repo = factory.create_workflow_step_repository()

    # ==================== Resource Planning ====================

    def analyze_workflow_resources(self, workflow_id: int) -> Dict[str, Any]:
        """
        Analyze all resource requirements for a workflow.

        Args:
            workflow_id: Workflow ID to analyze

        Returns:
            Comprehensive resource analysis
        """
        try:
            workflow = self.workflow_repo.get_workflow_with_steps(workflow_id, include_resources=True)
            if not workflow:
                raise EntityNotFoundException("Workflow", workflow_id)

            # Aggregate material requirements
            material_requirements = self._aggregate_material_requirements(workflow.steps)

            # Aggregate tool requirements
            tool_requirements = self._aggregate_tool_requirements(workflow.steps)

            # Check availability
            material_availability = self._check_material_availability(material_requirements)
            tool_availability = self._check_tool_availability(tool_requirements)

            # Calculate costs if possible
            estimated_costs = self._calculate_resource_costs(material_requirements, tool_requirements)

            analysis = {
                'workflow_id': workflow_id,
                'workflow_name': workflow.name,
                'material_requirements': material_requirements,
                'tool_requirements': tool_requirements,
                'material_availability': material_availability,
                'tool_availability': tool_availability,
                'estimated_costs': estimated_costs,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'readiness_score': self._calculate_readiness_score(material_availability, tool_availability)
            }

            logger.info(f"Completed resource analysis for workflow {workflow_id}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing workflow resources: {str(e)}")
            raise

    def check_execution_readiness(self, workflow_id: int) -> Dict[str, Any]:
        """
        Check if a workflow is ready for execution based on resource availability.

        Args:
            workflow_id: Workflow ID to check

        Returns:
            Readiness assessment
        """
        try:
            analysis = self.analyze_workflow_resources(workflow_id)

            # Determine blocking issues
            blocking_issues = []
            warnings = []

            # Check for missing materials
            for material in analysis['material_availability']:
                if not material['available']:
                    if material['required']:
                        blocking_issues.append(f"Missing required material: {material['name']}")
                    else:
                        warnings.append(f"Optional material unavailable: {material['name']}")

            # Check for missing tools
            for tool in analysis['tool_availability']:
                if not tool['available']:
                    if tool['required']:
                        blocking_issues.append(f"Missing required tool: {tool['name']}")
                    else:
                        warnings.append(f"Optional tool unavailable: {tool['name']}")

            readiness = {
                'workflow_id': workflow_id,
                'ready_for_execution': len(blocking_issues) == 0,
                'readiness_score': analysis['readiness_score'],
                'blocking_issues': blocking_issues,
                'warnings': warnings,
                'estimated_setup_time': self._estimate_setup_time(analysis),
                'recommendations': self._generate_readiness_recommendations(analysis, blocking_issues)
            }

            return readiness

        except Exception as e:
            logger.error(f"Error checking execution readiness: {str(e)}")
            raise

    # ==================== Resource Reservations ====================

    def reserve_execution_resources(self, execution_id: int) -> Dict[str, Any]:
        """
        Reserve all required resources for a workflow execution.

        Args:
            execution_id: Workflow execution ID

        Returns:
            Reservation results
        """
        try:
            execution = self.execution_repo.get_execution_with_details(execution_id)
            if not execution:
                raise EntityNotFoundException("WorkflowExecution", execution_id)

            # Reserve materials
            material_reservations = self._reserve_materials_for_execution(execution)

            # Reserve tools (schedule usage)
            tool_reservations = self._reserve_tools_for_execution(execution)

            # Create reservation record
            reservation_data = {
                'execution_id': execution_id,
                'reserved_at': datetime.utcnow().isoformat(),
                'material_reservations': material_reservations,
                'tool_reservations': tool_reservations,
                'status': 'active'
            }

            # Store reservation data in execution
            execution_data = execution.execution_data or {}
            execution_data['resource_reservations'] = reservation_data

            self.execution_repo.update_execution_status(
                execution_id, execution.status, {'execution_data': execution_data}
            )

            logger.info(f"Reserved resources for execution {execution_id}")

            return {
                'execution_id': execution_id,
                'reservation_successful': True,
                'materials_reserved': len(material_reservations),
                'tools_reserved': len(tool_reservations),
                'reservation_id': f"RES-{execution_id}-{int(datetime.utcnow().timestamp())}"
            }

        except Exception as e:
            logger.error(f"Error reserving execution resources: {str(e)}")
            raise

    def release_execution_resources(self, execution_id: int) -> bool:
        """
        Release all reserved resources for an execution.

        Args:
            execution_id: Workflow execution ID

        Returns:
            True if resources released successfully
        """
        try:
            execution = self.execution_repo.get_execution_with_details(execution_id)
            if not execution:
                raise EntityNotFoundException("WorkflowExecution", execution_id)

            execution_data = execution.execution_data or {}
            reservations = execution_data.get('resource_reservations')

            if not reservations:
                logger.warning(f"No resource reservations found for execution {execution_id}")
                return True

            # Release material reservations
            material_count = self._release_material_reservations(reservations.get('material_reservations', []))

            # Release tool reservations
            tool_count = self._release_tool_reservations(reservations.get('tool_reservations', []))

            # Update reservation status
            reservations['status'] = 'released'
            reservations['released_at'] = datetime.utcnow().isoformat()
            execution_data['resource_reservations'] = reservations

            self.execution_repo.update_execution_status(
                execution_id, execution.status, {'execution_data': execution_data}
            )

            logger.info(f"Released {material_count} materials and {tool_count} tools for execution {execution_id}")
            return True

        except Exception as e:
            logger.error(f"Error releasing execution resources: {str(e)}")
            return False

    # ==================== Step-Level Resource Management ====================

    def prepare_step_resources(self, execution_id: int, step_id: int) -> Dict[str, Any]:
        """
        Prepare resources for a specific workflow step.

        Args:
            execution_id: Workflow execution ID
            step_id: Step ID

        Returns:
            Step resource preparation results
        """
        try:
            step = self.step_repo.get_step_with_details(step_id)
            if not step:
                raise EntityNotFoundException("WorkflowStep", step_id)

            # Get step resources
            materials_needed = []
            tools_needed = []

            for resource in step.resources:
                if resource.resource_type == 'material':
                    material_info = self._prepare_material_resource(resource, execution_id)
                    if material_info:
                        materials_needed.append(material_info)

                elif resource.resource_type == 'tool':
                    tool_info = self._prepare_tool_resource(resource, execution_id)
                    if tool_info:
                        tools_needed.append(tool_info)

            preparation_result = {
                'execution_id': execution_id,
                'step_id': step_id,
                'step_name': step.name,
                'materials_needed': materials_needed,
                'tools_needed': tools_needed,
                'preparation_notes': self._generate_preparation_notes(step, materials_needed, tools_needed),
                'estimated_setup_time': self._estimate_step_setup_time(materials_needed, tools_needed)
            }

            return preparation_result

        except Exception as e:
            logger.error(f"Error preparing step resources: {str(e)}")
            raise

    def complete_step_resource_usage(self, execution_id: int, step_id: int,
                                     actual_usage: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record actual resource usage when step is completed.

        Args:
            execution_id: Workflow execution ID
            step_id: Step ID
            actual_usage: Actual resource usage data

        Returns:
            True if usage recorded successfully
        """
        try:
            step = self.step_repo.get_step_with_details(step_id)
            if not step:
                raise EntityNotFoundException("WorkflowStep", step_id)

            # Record material usage
            material_usage = self._record_material_usage(step, actual_usage)

            # Record tool usage
            tool_usage = self._record_tool_usage(step, actual_usage)

            # Update step execution with usage data
            step_execution = self.execution_repo.get_step_execution(execution_id, step_id)
            if step_execution:
                step_data = step_execution.step_data or {}
                step_data['resource_usage'] = {
                    'materials': material_usage,
                    'tools': tool_usage,
                    'recorded_at': datetime.utcnow().isoformat()
                }

                self.execution_repo.update_step_execution(
                    execution_id, step_id, {'step_data': step_data}
                )

            logger.debug(f"Recorded resource usage for step {step_id} in execution {execution_id}")
            return True

        except Exception as e:
            logger.error(f"Error recording step resource usage: {str(e)}")
            return False

    # ==================== Private Helper Methods ====================

    def _aggregate_material_requirements(self, steps: List[WorkflowStep]) -> List[Dict[str, Any]]:
        """Aggregate material requirements across all steps."""
        material_totals = {}

        for step in steps:
            for resource in step.resources:
                if resource.resource_type == 'material' and resource.dynamic_material_id:
                    material_id = resource.dynamic_material_id
                    quantity = resource.quantity or 0

                    if material_id in material_totals:
                        material_totals[material_id]['total_quantity'] += quantity
                        material_totals[material_id]['steps'].append({
                            'step_id': step.id,
                            'step_name': step.name,
                            'quantity': quantity,
                            'is_optional': resource.is_optional
                        })
                    else:
                        material_totals[material_id] = {
                            'material_id': material_id,
                            'total_quantity': quantity,
                            'unit': resource.unit,
                            'steps': [{
                                'step_id': step.id,
                                'step_name': step.name,
                                'quantity': quantity,
                                'is_optional': resource.is_optional
                            }],
                            'any_required': not resource.is_optional
                        }

        return list(material_totals.values())

    def _aggregate_tool_requirements(self, steps: List[WorkflowStep]) -> List[Dict[str, Any]]:
        """Aggregate tool requirements across all steps."""
        tool_usage = {}

        for step in steps:
            for resource in step.resources:
                if resource.resource_type == 'tool' and resource.tool_id:
                    tool_id = resource.tool_id

                    if tool_id in tool_usage:
                        tool_usage[tool_id]['steps'].append({
                            'step_id': step.id,
                            'step_name': step.name,
                            'estimated_duration': step.estimated_duration,
                            'is_optional': resource.is_optional
                        })
                        tool_usage[tool_id]['total_usage_time'] += (step.estimated_duration or 0)
                    else:
                        tool_usage[tool_id] = {
                            'tool_id': tool_id,
                            'total_usage_time': step.estimated_duration or 0,
                            'steps': [{
                                'step_id': step.id,
                                'step_name': step.name,
                                'estimated_duration': step.estimated_duration,
                                'is_optional': resource.is_optional
                            }],
                            'any_required': not resource.is_optional
                        }

        return list(tool_usage.values())

    def _check_material_availability(self, material_requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check availability of required materials."""
        availability = []

        for requirement in material_requirements:
            material_id = requirement['material_id']
            required_quantity = requirement['total_quantity']

            try:
                material = self.dynamic_material_service.get_material(material_id)
                if material:
                    available_quantity = material.quantity or 0
                    available = available_quantity >= required_quantity

                    availability.append({
                        'material_id': material_id,
                        'name': material.name,
                        'required_quantity': required_quantity,
                        'available_quantity': available_quantity,
                        'available': available,
                        'required': requirement['any_required'],
                        'unit': requirement['unit']
                    })
                else:
                    availability.append({
                        'material_id': material_id,
                        'name': f'Material_{material_id}',
                        'required_quantity': required_quantity,
                        'available_quantity': 0,
                        'available': False,
                        'required': requirement['any_required'],
                        'unit': requirement['unit']
                    })

            except Exception as e:
                logger.error(f"Error checking material {material_id}: {str(e)}")
                availability.append({
                    'material_id': material_id,
                    'name': f'Material_{material_id}',
                    'required_quantity': required_quantity,
                    'available_quantity': 0,
                    'available': False,
                    'required': requirement['any_required'],
                    'unit': requirement.get('unit', 'units'),
                    'error': str(e)
                })

        return availability

    def _check_tool_availability(self, tool_requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check availability of required tools."""
        availability = []

        for requirement in tool_requirements:
            tool_id = requirement['tool_id']

            # In a real implementation, check tool availability from tool service
            # For now, assume tools are available
            availability.append({
                'tool_id': tool_id,
                'name': f'Tool_{tool_id}',
                'total_usage_time': requirement['total_usage_time'],
                'available': True,  # Would check actual availability
                'required': requirement['any_required'],
                'availability_window': None  # Would check scheduling
            })

        return availability

    def _calculate_readiness_score(self, material_availability: List[Dict[str, Any]],
                                   tool_availability: List[Dict[str, Any]]) -> float:
        """Calculate workflow readiness score (0-100)."""
        total_items = len(material_availability) + len(tool_availability)
        if total_items == 0:
            return 100.0

        available_required = 0
        total_required = 0

        for item in material_availability + tool_availability:
            if item['required']:
                total_required += 1
                if item['available']:
                    available_required += 1

        if total_required == 0:
            return 100.0

        return (available_required / total_required) * 100

    def _reserve_materials_for_execution(self, execution: WorkflowExecution) -> List[Dict[str, Any]]:
        """Reserve materials for workflow execution."""
        reservations = []

        for step in execution.workflow.steps:
            for resource in step.resources:
                if resource.resource_type == 'material' and resource.dynamic_material_id:
                    # Create reservation record
                    reservation = {
                        'material_id': resource.dynamic_material_id,
                        'quantity': resource.quantity,
                        'step_id': step.id,
                        'reserved_at': datetime.utcnow().isoformat(),
                        'status': 'reserved'
                    }
                    reservations.append(reservation)

        return reservations

    def _reserve_tools_for_execution(self, execution: WorkflowExecution) -> List[Dict[str, Any]]:
        """Reserve tools for workflow execution."""
        reservations = []

        for step in execution.workflow.steps:
            for resource in step.resources:
                if resource.resource_type == 'tool' and resource.tool_id:
                    # Create tool usage reservation
                    reservation = {
                        'tool_id': resource.tool_id,
                        'step_id': step.id,
                        'estimated_duration': step.estimated_duration,
                        'reserved_at': datetime.utcnow().isoformat(),
                        'status': 'reserved'
                    }
                    reservations.append(reservation)

        return reservations

    def _calculate_resource_costs(self, material_requirements: List[Dict[str, Any]],
                                  tool_requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate estimated resource costs."""
        # Placeholder implementation
        return {
            'material_cost': 0.0,
            'tool_cost': 0.0,
            'total_cost': 0.0,
            'currency': 'USD',
            'estimation_note': 'Cost calculation not implemented'
        }

    def _estimate_setup_time(self, analysis: Dict[str, Any]) -> int:
        """Estimate time needed to set up resources (in minutes)."""
        material_count = len(analysis.get('material_requirements', []))
        tool_count = len(analysis.get('tool_requirements', []))

        # Simple estimation: 2 minutes per material, 3 minutes per tool
        return (material_count * 2) + (tool_count * 3)

    def _generate_readiness_recommendations(self, analysis: Dict[str, Any],
                                            blocking_issues: List[str]) -> List[str]:
        """Generate recommendations for workflow readiness."""
        recommendations = []

        if blocking_issues:
            recommendations.append("Resolve blocking issues before starting execution")

        if analysis['readiness_score'] < 80:
            recommendations.append("Consider postponing execution until more resources are available")

        recommendations.append("Gather all materials and tools before starting")
        recommendations.append("Review step instructions for any special requirements")

        return recommendations

    def _prepare_material_resource(self, resource: WorkflowStepResource, execution_id: int) -> Optional[Dict[str, Any]]:
        """Prepare information for a material resource."""
        if not resource.dynamic_material_id:
            return None

        try:
            material = self.dynamic_material_service.get_material(resource.dynamic_material_id)
            return {
                'material_id': resource.dynamic_material_id,
                'name': material.name if material else f'Material_{resource.dynamic_material_id}',
                'quantity_needed': resource.quantity,
                'unit': resource.unit,
                'notes': resource.notes,
                'is_optional': resource.is_optional
            }
        except Exception as e:
            logger.error(f"Error preparing material resource: {str(e)}")
            return None

    def _prepare_tool_resource(self, resource: WorkflowStepResource, execution_id: int) -> Optional[Dict[str, Any]]:
        """Prepare information for a tool resource."""
        if not resource.tool_id:
            return None

        return {
            'tool_id': resource.tool_id,
            'name': f'Tool_{resource.tool_id}',  # Would get actual name from tool service
            'notes': resource.notes,
            'is_optional': resource.is_optional
        }

    def _generate_preparation_notes(self, step: WorkflowStep, materials: List[Dict[str, Any]],
                                    tools: List[Dict[str, Any]]) -> List[str]:
        """Generate preparation notes for a step."""
        notes = []

        if materials:
            notes.append(f"Gather {len(materials)} material(s) for this step")

        if tools:
            notes.append(f"Prepare {len(tools)} tool(s) for this step")

        if step.estimated_duration:
            notes.append(f"Estimated duration: {step.estimated_duration} minutes")

        return notes

    def _estimate_step_setup_time(self, materials: List[Dict[str, Any]],
                                  tools: List[Dict[str, Any]]) -> int:
        """Estimate setup time for a step (in minutes)."""
        return len(materials) + len(tools)  # 1 minute per resource

    def _record_material_usage(self, step: WorkflowStep, actual_usage: Optional[Dict[str, Any]]) -> List[
        Dict[str, Any]]:
        """Record actual material usage for a step."""
        usage = []

        for resource in step.resources:
            if resource.resource_type == 'material':
                usage_record = {
                    'material_id': resource.dynamic_material_id,
                    'planned_quantity': resource.quantity,
                    'actual_quantity': resource.quantity,  # Would get from actual_usage
                    'unit': resource.unit
                }
                usage.append(usage_record)

        return usage

    def _record_tool_usage(self, step: WorkflowStep, actual_usage: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Record actual tool usage for a step."""
        usage = []

        for resource in step.resources:
            if resource.resource_type == 'tool':
                usage_record = {
                    'tool_id': resource.tool_id,
                    'planned_duration': step.estimated_duration,
                    'actual_duration': step.estimated_duration  # Would get from actual_usage
                }
                usage.append(usage_record)

        return usage

    def _release_material_reservations(self, reservations: List[Dict[str, Any]]) -> int:
        """Release material reservations."""
        count = 0
        for reservation in reservations:
            if reservation.get('status') == 'reserved':
                # In real implementation, update material availability
                count += 1
        return count

    def _release_tool_reservations(self, reservations: List[Dict[str, Any]]) -> int:
        """Release tool reservations."""
        count = 0
        for reservation in reservations:
            if reservation.get('status') == 'reserved':
                # In real implementation, update tool scheduling
                count += 1
        return count