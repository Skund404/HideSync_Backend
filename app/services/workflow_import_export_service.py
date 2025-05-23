# File: app/services/workflow_import_export_service.py

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.services.workflow_service import WorkflowService
from app.repositories.repository_factory import RepositoryFactory
from app.db.models.workflow import (
    Workflow, WorkflowStep, WorkflowStepConnection, WorkflowStepResource,
    WorkflowDecisionOption, WorkflowOutcome
)
from app.core.exceptions import ValidationException, EntityNotFoundException

logger = logging.getLogger(__name__)


class WorkflowImportExportService(BaseService):
    """
    Service for importing and exporting workflows as JSON.
    Supports preset system for frontend integration and template sharing.
    """

    def __init__(self, session: Session, workflow_service: Optional[WorkflowService] = None):
        """
        Initialize the import/export service.

        Args:
            session: Database session
            workflow_service: Optional workflow service dependency
        """
        self.db_session = session
        self.workflow_service = workflow_service or WorkflowService(session)

        # Initialize repositories
        factory = RepositoryFactory(session)
        self.workflow_repo = factory.create_workflow_repository()
        self.step_repo = factory.create_workflow_step_repository()

    # ==================== Import Operations ====================

    def import_workflow(self, import_data: Dict[str, Any], user_id: int) -> Workflow:
        """
        Import a workflow from JSON data.

        Args:
            import_data: JSON data containing workflow definition
            user_id: ID of the user importing the workflow

        Returns:
            Created workflow object

        Raises:
            ValidationException: If import data is invalid
        """
        try:
            # Validate import data structure
            self._validate_import_data(import_data)

            # Extract workflow data
            workflow_data = import_data.get('workflow', {})
            preset_info = import_data.get('preset_info', {})
            metadata = import_data.get('metadata', {})

            # Prepare workflow creation data
            workflow_create_data = {
                'name': workflow_data.get('name') or preset_info.get('name', 'Imported Workflow'),
                'description': workflow_data.get('description') or preset_info.get('description', ''),
                'is_template': True,  # Imported workflows are templates by default
                'status': 'draft',
                'estimated_duration': preset_info.get('estimated_time'),
                'difficulty_level': preset_info.get('difficulty'),
                'has_multiple_outcomes': bool(workflow_data.get('outcomes', [])),
                'default_locale': 'en',
                'visibility': 'private'  # Import as private by default
            }

            # Create the workflow
            workflow = self.workflow_service.create_workflow(workflow_create_data, user_id)

            logger.info(f"Created base workflow {workflow.id} for import")

            # Import components in order
            step_id_mapping = {}

            if 'steps' in workflow_data:
                step_id_mapping = self._import_steps(workflow.id, workflow_data['steps'])
                logger.info(f"Imported {len(step_id_mapping)} steps")

            if 'outcomes' in workflow_data:
                self._import_outcomes(workflow.id, workflow_data['outcomes'])
                logger.info(f"Imported {len(workflow_data['outcomes'])} outcomes")

            if 'connections' in workflow_data:
                self._import_connections(workflow.id, workflow_data['connections'], step_id_mapping)
                logger.info(f"Imported {len(workflow_data['connections'])} connections")

            # Update workflow with final settings
            if metadata.get('original_workflow_id'):
                execution_data = workflow.execution_data or {}
                execution_data['imported_from'] = metadata['original_workflow_id']
                self.workflow_repo.update(workflow.id, {'execution_data': execution_data})

            self.db_session.commit()

            logger.info(f"Successfully imported workflow {workflow.id} '{workflow.name}' by user {user_id}")
            return workflow

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error importing workflow: {str(e)}")
            self.db_session.rollback()
            raise

    def import_workflow_from_file(self, file_path: str, user_id: int) -> Workflow:
        """
        Import workflow from a JSON file.

        Args:
            file_path: Path to JSON file
            user_id: User importing the workflow

        Returns:
            Created workflow
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            return self.import_workflow(import_data, user_id)

        except FileNotFoundError:
            raise ValidationException(f"Import file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValidationException(f"Invalid JSON in import file: {str(e)}")
        except Exception as e:
            logger.error(f"Error importing from file {file_path}: {str(e)}")
            raise

    # ==================== Export Operations ====================

    def export_workflow(self, workflow_id: int) -> Dict[str, Any]:
        """
        Export a workflow as JSON data.

        Args:
            workflow_id: ID of the workflow to export

        Returns:
            Dictionary containing complete workflow data

        Raises:
            EntityNotFoundException: If workflow not found
        """
        try:
            # Get workflow with all related data
            workflow = self.workflow_repo.get_workflow_with_steps(workflow_id, include_resources=True)

            if not workflow:
                raise EntityNotFoundException("Workflow", workflow_id)

            # Build export data structure
            export_data = {
                'preset_info': self._build_preset_info(workflow),
                'workflow': self._export_workflow_definition(workflow),
                'required_resources': self._calculate_required_resources(workflow.steps),
                'metadata': self._build_export_metadata(workflow)
            }

            logger.info(f"Successfully exported workflow {workflow_id}")
            return export_data

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error exporting workflow {workflow_id}: {str(e)}")
            raise

    def export_workflow_to_file(self, workflow_id: int, file_path: str) -> bool:
        """
        Export workflow to a JSON file.

        Args:
            workflow_id: Workflow ID to export
            file_path: Output file path

        Returns:
            True if export successful
        """
        try:
            export_data = self.export_workflow(workflow_id)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)

            logger.info(f"Exported workflow {workflow_id} to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to file {file_path}: {str(e)}")
            raise

    # ==================== Preset Management ====================

    def create_preset_from_workflow(self, workflow_id: int, preset_name: str,
                                    preset_description: str, difficulty: str = 'intermediate') -> Dict[str, Any]:
        """
        Create a preset JSON from an existing workflow.

        Args:
            workflow_id: Source workflow ID
            preset_name: Name for the preset
            preset_description: Description for the preset
            difficulty: Difficulty level

        Returns:
            Preset data
        """
        try:
            export_data = self.export_workflow(workflow_id)

            # Update preset info
            export_data['preset_info'].update({
                'name': preset_name,
                'description': preset_description,
                'difficulty': difficulty
            })

            # Update metadata
            export_data['metadata'].update({
                'created_as_preset': True,
                'preset_created_at': datetime.utcnow().isoformat()
            })

            return export_data

        except Exception as e:
            logger.error(f"Error creating preset from workflow {workflow_id}: {str(e)}")
            raise

    def validate_preset_data(self, preset_data: Dict[str, Any]) -> List[str]:
        """
        Validate preset data structure and content.

        Args:
            preset_data: Preset data to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        try:
            # Check required top-level fields
            required_fields = ['preset_info', 'workflow']
            for field in required_fields:
                if field not in preset_data:
                    errors.append(f"Missing required field: {field}")

            if errors:  # Don't continue if basic structure is wrong
                return errors

            # Validate preset_info
            preset_info = preset_data['preset_info']
            if not isinstance(preset_info, dict):
                errors.append("preset_info must be an object")
            elif not preset_info.get('name'):
                errors.append("preset_info.name is required")

            # Validate workflow structure
            workflow_errors = self._validate_workflow_structure(preset_data['workflow'])
            errors.extend(workflow_errors)

            # Validate resources if present
            if 'required_resources' in preset_data:
                resource_errors = self._validate_resources_structure(preset_data['required_resources'])
                errors.extend(resource_errors)

        except Exception as e:
            errors.append(f"Validation error: {str(e)}")

        return errors

    # ==================== Private Helper Methods ====================

    def _validate_import_data(self, data: Dict[str, Any]) -> None:
        """
        Validate the structure of import data.

        Args:
            data: Import data to validate

        Raises:
            ValidationException: If data structure is invalid
        """
        required_fields = ['workflow']
        for field in required_fields:
            if field not in data:
                raise ValidationException(f"Missing required field: {field}")

        workflow_data = data['workflow']
        if not isinstance(workflow_data, dict):
            raise ValidationException("Workflow data must be an object")

        if not workflow_data.get('name'):
            raise ValidationException("Workflow name is required")

        # Validate steps structure if present
        if 'steps' in workflow_data:
            if not isinstance(workflow_data['steps'], list):
                raise ValidationException("Workflow steps must be a list")

            for i, step in enumerate(workflow_data['steps']):
                if not isinstance(step, dict):
                    raise ValidationException(f"Step {i} must be an object")
                if not step.get('name'):
                    raise ValidationException(f"Step {i} must have a name")

    def _import_steps(self, workflow_id: int, steps_data: List[Dict[str, Any]]) -> Dict[int, int]:
        """
        Import workflow steps.

        Args:
            workflow_id: Target workflow ID
            steps_data: List of step data

        Returns:
            Mapping from original step IDs to new step IDs
        """
        step_id_mapping = {}

        for step_data in steps_data:
            # Extract original ID for mapping
            original_id = step_data.get('id', step_data.get('step_id'))

            # Prepare step creation data
            new_step_data = {
                'workflow_id': workflow_id,
                'name': step_data['name'],
                'description': step_data.get('description'),
                'instructions': step_data.get('instructions'),
                'display_order': step_data.get('display_order', 1),
                'step_type': step_data.get('step_type', 'instruction'),
                'estimated_duration': step_data.get('estimated_duration'),
                'is_milestone': step_data.get('is_milestone', False),
                'ui_position_x': step_data.get('ui_position_x'),
                'ui_position_y': step_data.get('ui_position_y'),
                'is_decision_point': step_data.get('is_decision_point', False),
                'is_outcome': step_data.get('is_outcome', False),
                'condition_logic': step_data.get('condition_logic')
            }

            # Create step
            step = WorkflowStep(**new_step_data)
            self.db_session.add(step)
            self.db_session.flush()  # Get the new ID

            if original_id:
                step_id_mapping[original_id] = step.id

            # Import step resources
            if 'resources' in step_data:
                self._import_step_resources(step.id, step_data['resources'])

            # Import decision options
            if 'decision_options' in step_data:
                self._import_decision_options(step.id, step_data['decision_options'])

        return step_id_mapping

    def _import_step_resources(self, step_id: int, resources_data: List[Dict[str, Any]]) -> None:
        """Import resources for a step."""
        for resource_data in resources_data:
            new_resource_data = {
                'step_id': step_id,
                'resource_type': resource_data.get('resource_type', 'material'),
                'quantity': resource_data.get('quantity'),
                'unit': resource_data.get('unit'),
                'notes': resource_data.get('notes'),
                'is_optional': resource_data.get('is_optional', False)
            }

            # Note: dynamic_material_id and tool_id would need to be resolved
            # based on names or external IDs in a real implementation

            resource = WorkflowStepResource(**new_resource_data)
            self.db_session.add(resource)

    def _import_decision_options(self, step_id: int, options_data: List[Dict[str, Any]]) -> None:
        """Import decision options for a step."""
        for option_data in options_data:
            new_option_data = {
                'step_id': step_id,
                'option_text': option_data['option_text'],
                'result_action': option_data.get('result_action'),
                'display_order': option_data.get('display_order', 1),
                'is_default': option_data.get('is_default', False)
            }

            option = WorkflowDecisionOption(**new_option_data)
            self.db_session.add(option)

    def _import_outcomes(self, workflow_id: int, outcomes_data: List[Dict[str, Any]]) -> None:
        """Import workflow outcomes."""
        for outcome_data in outcomes_data:
            new_outcome_data = {
                'workflow_id': workflow_id,
                'name': outcome_data['name'],
                'description': outcome_data.get('description'),
                'display_order': outcome_data.get('display_order', 1),
                'is_default': outcome_data.get('is_default', False),
                'success_criteria': outcome_data.get('success_criteria')
            }

            outcome = WorkflowOutcome(**new_outcome_data)
            self.db_session.add(outcome)

    def _import_connections(self, workflow_id: int, connections_data: List[Dict[str, Any]],
                            step_id_mapping: Dict[int, int]) -> None:
        """Import step connections."""
        for connection_data in connections_data:
            # Map original IDs to new IDs
            source_id = connection_data.get('source_step', connection_data.get('source_step_id'))
            target_id = connection_data.get('target_step', connection_data.get('target_step_id'))

            if source_id in step_id_mapping and target_id in step_id_mapping:
                new_connection_data = {
                    'source_step_id': step_id_mapping[source_id],
                    'target_step_id': step_id_mapping[target_id],
                    'connection_type': connection_data.get('connection_type', 'sequential'),
                    'condition': connection_data.get('condition'),
                    'display_order': connection_data.get('display_order', 1),
                    'is_default': connection_data.get('is_default', False)
                }

                connection = WorkflowStepConnection(**new_connection_data)
                self.db_session.add(connection)
            else:
                logger.warning(f"Skipping connection with unmapped step IDs: {source_id} -> {target_id}")

    def _build_preset_info(self, workflow: Workflow) -> Dict[str, Any]:
        """Build preset info section for export."""
        return {
            'name': workflow.name,
            'description': workflow.description or '',
            'difficulty': workflow.difficulty_level or 'intermediate',
            'estimated_time': workflow.estimated_duration,
            'tags': [],  # Could be extracted from workflow metadata
            'category': 'general'  # Could be determined from workflow type
        }

    def _export_workflow_definition(self, workflow: Workflow) -> Dict[str, Any]:
        """Export complete workflow definition."""
        return {
            'name': workflow.name,
            'description': workflow.description,
            'has_multiple_outcomes': workflow.has_multiple_outcomes,
            'estimated_duration': workflow.estimated_duration,
            'difficulty_level': workflow.difficulty_level,
            'steps': self._export_steps(workflow.steps),
            'outcomes': self._export_outcomes(workflow.outcomes),
            'connections': self._export_connections(workflow.steps)
        }

    def _export_steps(self, steps: List[WorkflowStep]) -> List[Dict[str, Any]]:
        """Export workflow steps."""
        return [{
            'id': step.id,
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
            'condition_logic': step.condition_logic,
            'resources': self._export_step_resources(step.resources),
            'decision_options': self._export_decision_options(step.decision_options)
        } for step in sorted(steps, key=lambda x: x.display_order)]

    def _export_step_resources(self, resources: List[WorkflowStepResource]) -> List[Dict[str, Any]]:
        """Export step resources."""
        return [{
            'resource_type': resource.resource_type,
            'quantity': resource.quantity,
            'unit': resource.unit,
            'notes': resource.notes,
            'is_optional': resource.is_optional,
            # Note: Would need to resolve material/tool names from IDs
            'name': self._resolve_resource_name(resource)
        } for resource in resources]

    def _export_decision_options(self, options: List[WorkflowDecisionOption]) -> List[Dict[str, Any]]:
        """Export decision options."""
        return [{
            'option_text': option.option_text,
            'result_action': option.result_action,
            'display_order': option.display_order,
            'is_default': option.is_default
        } for option in sorted(options, key=lambda x: x.display_order)]

    def _export_outcomes(self, outcomes: List[WorkflowOutcome]) -> List[Dict[str, Any]]:
        """Export workflow outcomes."""
        return [{
            'name': outcome.name,
            'description': outcome.description,
            'display_order': outcome.display_order,
            'is_default': outcome.is_default,
            'success_criteria': outcome.success_criteria
        } for outcome in sorted(outcomes, key=lambda x: x.display_order)]

    def _export_connections(self, steps: List[WorkflowStep]) -> List[Dict[str, Any]]:
        """Export step connections."""
        connections = []
        for step in steps:
            for connection in step.outgoing_connections:
                connections.append({
                    'source_step': step.id,
                    'target_step': connection.target_step_id,
                    'connection_type': connection.connection_type,
                    'condition': connection.condition,
                    'display_order': connection.display_order,
                    'is_default': connection.is_default
                })
        return connections

    def _calculate_required_resources(self, steps: List[WorkflowStep]) -> Dict[str, Any]:
        """Calculate all required resources for the workflow."""
        materials = []
        tools = []
        documentation = []

        for step in steps:
            for resource in step.resources:
                resource_info = {
                    'name': self._resolve_resource_name(resource),
                    'quantity': resource.quantity,
                    'unit': resource.unit,
                    'is_optional': resource.is_optional
                }

                if resource.resource_type == 'material':
                    materials.append(resource_info)
                elif resource.resource_type == 'tool':
                    tools.append(resource_info)
                elif resource.resource_type == 'documentation':
                    documentation.append(resource_info)

        return {
            'materials': materials,
            'tools': tools,
            'documentation': documentation
        }

    def _build_export_metadata(self, workflow: Workflow) -> Dict[str, Any]:
        """Build metadata section for export."""
        return {
            'version': workflow.version,
            'created_by': 'system',
            'exported_at': datetime.utcnow().isoformat(),
            'original_workflow_id': workflow.id,
            'export_format_version': '1.0'
        }

    def _resolve_resource_name(self, resource: WorkflowStepResource) -> str:
        """Resolve resource name from ID."""
        # In a real implementation, this would query the appropriate tables
        # to get the actual names of materials, tools, etc.
        if resource.dynamic_material_id:
            return f"Material_{resource.dynamic_material_id}"
        elif resource.tool_id:
            return f"Tool_{resource.tool_id}"
        elif resource.documentation_id:
            return f"Documentation_{resource.documentation_id}"
        else:
            return "Unknown Resource"

    def _validate_workflow_structure(self, workflow_data: Dict[str, Any]) -> List[str]:
        """Validate workflow structure."""
        errors = []

        if not workflow_data.get('name'):
            errors.append("Workflow name is required")

        if 'steps' in workflow_data:
            steps = workflow_data['steps']
            if not isinstance(steps, list):
                errors.append("Steps must be a list")
            else:
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        errors.append(f"Step {i} must be an object")
                    elif not step.get('name'):
                        errors.append(f"Step {i} must have a name")

        return errors

    def _validate_resources_structure(self, resources_data: Dict[str, Any]) -> List[str]:
        """Validate resources structure."""
        errors = []

        expected_sections = ['materials', 'tools', 'documentation']
        for section in expected_sections:
            if section in resources_data:
                if not isinstance(resources_data[section], list):
                    errors.append(f"Resources.{section} must be a list")

        return errors