# File: app/services/workflow_navigation_service.py

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.services.workflow_execution_service import WorkflowExecutionService
from app.repositories.repository_factory import RepositoryFactory
from app.db.models.workflow import (
    WorkflowExecution, WorkflowStep, WorkflowStepConnection,
    WorkflowDecisionOption, WorkflowNavigationHistory
)
from app.core.exceptions import (
    EntityNotFoundException, ValidationException, BusinessRuleException
)

logger = logging.getLogger(__name__)


class WorkflowNavigationService(BaseService):
    """
    Service for interactive workflow navigation.
    Provides text-adventure style guidance and context-aware navigation.
    """

    def __init__(self, session: Session, execution_service: Optional[WorkflowExecutionService] = None):
        """
        Initialize the workflow navigation service.

        Args:
            session: Database session
            execution_service: Optional execution service dependency
        """
        self.db_session = session
        self.execution_service = execution_service or WorkflowExecutionService(session)

        # Initialize repositories
        factory = RepositoryFactory(session)
        self.execution_repo = factory.create_workflow_execution_repository()
        self.workflow_repo = factory.create_workflow_repository()

    # ==================== Interactive Navigation ====================

    def get_navigation_context(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """
        Get complete navigation context for an execution.

        Args:
            execution_id: Execution ID
            user_id: User ID for access control

        Returns:
            Navigation context with current state, options, and guidance
        """
        try:
            execution = self.execution_service.get_execution(execution_id, user_id)

            # Get current step details
            current_step_info = self._get_current_step_info(execution)

            # Get available navigation options
            navigation_options = self._get_navigation_options(execution)

            # Get progress information
            progress = self.execution_service.get_execution_progress(execution_id, user_id)

            # Get recent history for context
            recent_history = self._get_recent_navigation_history(execution_id)

            # Generate contextual guidance
            guidance = self._generate_contextual_guidance(execution, current_step_info, navigation_options)

            context = {
                'execution_id': execution_id,
                'workflow_name': execution.workflow.name,
                'status': execution.status,
                'current_step': current_step_info,
                'navigation_options': navigation_options,
                'progress': progress,
                'recent_history': recent_history,
                'guidance': guidance,
                'timestamp': datetime.utcnow().isoformat()
            }

            logger.debug(f"Generated navigation context for execution {execution_id}")
            return context

        except Exception as e:
            logger.error(f"Error getting navigation context: {str(e)}")
            raise

    def get_step_guidance(self, execution_id: int, step_id: int, user_id: int) -> Dict[str, Any]:
        """
        Get detailed guidance for a specific step.

        Args:
            execution_id: Execution ID
            step_id: Step ID
            user_id: User ID for access control

        Returns:
            Detailed step guidance and instructions
        """
        try:
            execution = self.execution_service.get_execution(execution_id, user_id)

            # Get step details
            step = self.workflow_repo.db_session.query(WorkflowStep).filter(
                WorkflowStep.id == step_id,
                WorkflowStep.workflow_id == execution.workflow_id
            ).first()

            if not step:
                raise EntityNotFoundException("WorkflowStep", step_id)

            # Get step execution status
            step_execution = self.execution_repo.get_step_execution(execution_id, step_id)

            # Get step resources
            resources = self._format_step_resources(step.resources)

            # Get decision options if applicable
            decision_options = self._format_decision_options(step.decision_options)

            # Generate step-specific guidance
            instructions = self._generate_step_instructions(step, step_execution, execution)

            guidance = {
                'step_id': step_id,
                'step_name': step.name,
                'step_type': step.step_type,
                'description': step.description,
                'instructions': instructions,
                'detailed_instructions': step.instructions,
                'estimated_duration': step.estimated_duration,
                'is_milestone': step.is_milestone,
                'is_decision_point': step.is_decision_point,
                'status': step_execution.status if step_execution else 'not_started',
                'resources': resources,
                'decision_options': decision_options,
                'tips': self._generate_step_tips(step),
                'warnings': self._generate_step_warnings(step, execution)
            }

            return guidance

        except Exception as e:
            logger.error(f"Error getting step guidance: {str(e)}")
            raise

    def suggest_next_action(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """
        Suggest the next best action for the user.

        Args:
            execution_id: Execution ID
            user_id: User ID

        Returns:
            Suggested action with reasoning
        """
        try:
            execution = self.execution_service.get_execution(execution_id, user_id)

            if execution.status != 'active':
                return {
                    'action': 'none',
                    'reason': f'Execution is {execution.status}',
                    'message': f'This workflow execution is currently {execution.status}.'
                }

            # Analyze current state
            current_step = execution.current_step
            if not current_step:
                # No current step - suggest starting or selecting next step
                initial_steps = self.workflow_repo.get_initial_steps(execution.workflow_id)
                if initial_steps:
                    return {
                        'action': 'navigate_to_step',
                        'step_id': initial_steps[0].id,
                        'step_name': initial_steps[0].name,
                        'reason': 'Start workflow execution',
                        'message': f'Ready to begin! Start with "{initial_steps[0].name}".'
                    }
                else:
                    return {
                        'action': 'manual_selection',
                        'reason': 'No initial steps found',
                        'message': 'Please select a step to begin with.'
                    }

            # Check current step status
            step_execution = self.execution_repo.get_step_execution(execution_id, current_step.id)

            if not step_execution or step_execution.status == 'ready':
                return {
                    'action': 'start_step',
                    'step_id': current_step.id,
                    'step_name': current_step.name,
                    'reason': 'Step is ready to begin',
                    'message': f'Begin working on "{current_step.name}".'
                }

            if step_execution.status == 'active':
                if current_step.is_decision_point:
                    return {
                        'action': 'make_decision',
                        'step_id': current_step.id,
                        'step_name': current_step.name,
                        'reason': 'Decision required',
                        'message': f'A decision is needed for "{current_step.name}".'
                    }
                else:
                    return {
                        'action': 'complete_step',
                        'step_id': current_step.id,
                        'step_name': current_step.name,
                        'reason': 'Step in progress',
                        'message': f'Continue working on "{current_step.name}" and mark complete when finished.'
                    }

            if step_execution.status == 'completed':
                # Look for next steps
                next_steps = self.execution_service.get_next_available_steps(execution_id, user_id)
                if next_steps:
                    return {
                        'action': 'navigate_to_step',
                        'step_id': next_steps[0].id,
                        'step_name': next_steps[0].name,
                        'reason': 'Next step available',
                        'message': f'Great! Now move on to "{next_steps[0].name}".'
                    }
                else:
                    return {
                        'action': 'workflow_complete',
                        'reason': 'No more steps',
                        'message': 'Congratulations! This workflow appears to be complete.'
                    }

            return {
                'action': 'none',
                'reason': 'Unknown state',
                'message': 'Current state is unclear. Please review the workflow.'
            }

        except Exception as e:
            logger.error(f"Error suggesting next action: {str(e)}")
            raise

    # ==================== Interactive Commands ====================

    def process_natural_language_command(self, execution_id: int, command: str, user_id: int) -> Dict[str, Any]:
        """
        Process a natural language navigation command.

        Args:
            execution_id: Execution ID
            command: Natural language command
            user_id: User ID

        Returns:
            Command processing result
        """
        try:
            command = command.lower().strip()

            # Simple command parsing (could be enhanced with NLP)
            if any(word in command for word in ['help', 'what', 'how', 'guide']):
                return self._handle_help_command(execution_id, user_id)

            elif any(word in command for word in ['status', 'progress', 'where']):
                return self._handle_status_command(execution_id, user_id)

            elif any(word in command for word in ['next', 'continue', 'proceed']):
                return self._handle_next_command(execution_id, user_id)

            elif any(word in command for word in ['back', 'previous', 'return']):
                return self._handle_back_command(execution_id, user_id)

            elif any(word in command for word in ['complete', 'done', 'finished']):
                return self._handle_complete_command(execution_id, user_id)

            elif any(word in command for word in ['skip', 'bypass']):
                return self._handle_skip_command(execution_id, command, user_id)

            elif any(word in command for word in ['show', 'list', 'display']):
                return self._handle_show_command(execution_id, command, user_id)

            else:
                return {
                    'success': False,
                    'message': f'I didn\'t understand "{command}". Try "help" for available commands.',
                    'suggestions': ['help', 'status', 'next', 'complete']
                }

        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            return {
                'success': False,
                'message': 'Sorry, there was an error processing your command.',
                'error': str(e)
            }

    # ==================== Path Finding and Optimization ====================

    def find_optimal_path(self, execution_id: int, target_outcome_id: Optional[int] = None,
                          user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Find the optimal path through the workflow.

        Args:
            execution_id: Execution ID
            target_outcome_id: Optional target outcome
            user_id: Optional user ID for access control

        Returns:
            Optimal path information
        """
        try:
            execution = self.execution_service.get_execution(execution_id, user_id)

            # Get all steps in workflow
            all_steps = self.workflow_repo.get_workflow_steps(execution.workflow_id)

            # Build graph of step connections
            graph = self._build_step_graph(all_steps)

            # Find current position
            current_step_id = execution.current_step_id
            if not current_step_id:
                # Start from initial steps
                initial_steps = self.workflow_repo.get_initial_steps(execution.workflow_id)
                current_step_id = initial_steps[0].id if initial_steps else None

            if not current_step_id:
                raise ValidationException("Cannot determine starting position")

            # Determine target steps
            target_step_ids = []
            if target_outcome_id:
                # Find steps that lead to specific outcome
                target_step_ids = self._find_outcome_steps(execution.workflow_id, target_outcome_id)
            else:
                # Find all outcome steps
                target_step_ids = [step.id for step in all_steps if step.is_outcome]

            if not target_step_ids:
                raise ValidationException("No target steps found")

            # Find shortest paths to each target
            paths = []
            for target_id in target_step_ids:
                path = self._find_shortest_path(graph, current_step_id, target_id, all_steps)
                if path:
                    paths.append(path)

            # Select optimal path based on criteria
            optimal_path = self._select_optimal_path(paths, execution)

            return {
                'current_step_id': current_step_id,
                'target_outcome_id': target_outcome_id,
                'optimal_path': optimal_path,
                'alternative_paths': paths[:3],  # Top 3 alternatives
                'estimated_time': self._calculate_path_time(optimal_path),
                'difficulty_score': self._calculate_path_difficulty(optimal_path)
            }

        except Exception as e:
            logger.error(f"Error finding optimal path: {str(e)}")
            raise

    # ==================== Private Helper Methods ====================

    def _get_current_step_info(self, execution: WorkflowExecution) -> Optional[Dict[str, Any]]:
        """Get detailed information about the current step."""
        if not execution.current_step:
            return None

        step = execution.current_step
        step_execution = self.execution_repo.get_step_execution(execution.id, step.id)

        return {
            'id': step.id,
            'name': step.name,
            'type': step.step_type,
            'description': step.description,
            'status': step_execution.status if step_execution else 'not_started',
            'is_milestone': step.is_milestone,
            'is_decision_point': step.is_decision_point,
            'estimated_duration': step.estimated_duration
        }

    def _get_navigation_options(self, execution: WorkflowExecution) -> List[Dict[str, Any]]:
        """Get available navigation options."""
        options = []

        # If execution is not active, limited options
        if execution.status != 'active':
            if execution.status == 'paused':
                options.append({
                    'action': 'resume',
                    'label': 'Resume Workflow',
                    'description': 'Continue with the paused workflow'
                })
            return options

        # Current step options
        if execution.current_step:
            step_execution = self.execution_repo.get_step_execution(execution.id, execution.current_step.id)

            if not step_execution or step_execution.status in ['ready', 'active']:
                if execution.current_step.is_decision_point:
                    options.append({
                        'action': 'make_decision',
                        'step_id': execution.current_step.id,
                        'label': f'Make Decision: {execution.current_step.name}',
                        'description': 'Choose from available options'
                    })
                else:
                    options.append({
                        'action': 'complete_step',
                        'step_id': execution.current_step.id,
                        'label': f'Complete: {execution.current_step.name}',
                        'description': 'Mark this step as completed'
                    })

        # Next step options
        next_steps = self.execution_service.get_next_available_steps(execution.id)
        for step in next_steps[:3]:  # Limit to top 3
            options.append({
                'action': 'navigate_to_step',
                'step_id': step.id,
                'label': f'Go to: {step.name}',
                'description': step.description or f'Navigate to {step.step_type} step'
            })

        # General options
        options.extend([
            {
                'action': 'pause',
                'label': 'Pause Workflow',
                'description': 'Pause execution to continue later'
            },
            {
                'action': 'view_progress',
                'label': 'View Progress',
                'description': 'See detailed progress information'
            }
        ])

        return options

    def _get_recent_navigation_history(self, execution_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent navigation history."""
        history = self.execution_repo.get_navigation_history(execution_id, limit)

        return [{
            'timestamp': nav.timestamp.isoformat(),
            'action_type': nav.action_type,
            'step_name': nav.step.name if nav.step else 'Unknown',
            'action_data': nav.action_data
        } for nav in history]

    def _generate_contextual_guidance(self, execution: WorkflowExecution,
                                      current_step_info: Optional[Dict[str, Any]],
                                      navigation_options: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate contextual guidance messages."""
        if execution.status != 'active':
            return {
                'primary': f'This workflow is currently {execution.status}.',
                'secondary': 'Resume to continue working on it.',
                'tone': 'neutral'
            }

        if not current_step_info:
            return {
                'primary': 'Ready to start your workflow!',
                'secondary': 'Choose a step to begin with or follow the suggested path.',
                'tone': 'encouraging'
            }

        step_status = current_step_info.get('status', 'not_started')
        step_name = current_step_info.get('name', 'this step')

        if step_status == 'ready':
            return {
                'primary': f'Time to begin "{step_name}"!',
                'secondary': 'Read the instructions and gather any required materials.',
                'tone': 'encouraging'
            }

        elif step_status == 'active':
            if current_step_info.get('is_decision_point'):
                return {
                    'primary': f'Decision needed for "{step_name}".',
                    'secondary': 'Review your options and choose the best path forward.',
                    'tone': 'thoughtful'
                }
            else:
                return {
                    'primary': f'Working on "{step_name}"...',
                    'secondary': 'Take your time and mark complete when finished.',
                    'tone': 'supportive'
                }

        elif step_status == 'completed':
            return {
                'primary': f'Great work completing "{step_name}"!',
                'secondary': 'Ready to move on to the next step.',
                'tone': 'congratulatory'
            }

        return {
            'primary': 'Continue with your workflow.',
            'secondary': 'Use the navigation options to proceed.',
            'tone': 'neutral'
        }

    def _generate_step_instructions(self, step: WorkflowStep, step_execution, execution: WorkflowExecution) -> str:
        """Generate dynamic step instructions based on context."""
        base_instructions = step.instructions or f"Complete the {step.step_type} step: {step.name}"

        # Add context based on step type
        if step.step_type == 'material':
            return f"{base_instructions}\n\nGather the required materials before proceeding to the next step."

        elif step.step_type == 'tool':
            return f"{base_instructions}\n\nEnsure you have the necessary tools ready and understand their proper use."

        elif step.step_type == 'time':
            duration = step.estimated_duration
            if duration:
                return f"{base_instructions}\n\nThis step requires waiting approximately {duration} minutes."

        elif step.step_type == 'decision':
            return f"{base_instructions}\n\nCarefully consider your options as this choice will affect the workflow path."

        return base_instructions

    def _format_step_resources(self, resources) -> List[Dict[str, Any]]:
        """Format step resources for display."""
        formatted = []
        for resource in resources:
            formatted.append({
                'type': resource.resource_type,
                'quantity': resource.quantity,
                'unit': resource.unit,
                'notes': resource.notes,
                'is_optional': resource.is_optional
            })
        return formatted

    def _format_decision_options(self, decision_options) -> List[Dict[str, Any]]:
        """Format decision options for display."""
        return [{
            'id': option.id,
            'text': option.option_text,
            'is_default': option.is_default,
            'order': option.display_order
        } for option in sorted(decision_options, key=lambda x: x.display_order)]

    def _generate_step_tips(self, step: WorkflowStep) -> List[str]:
        """Generate helpful tips for a step."""
        tips = []

        if step.step_type == 'material':
            tips.append("Double-check quantities before starting the next step")
            tips.append("Organize materials in the order you'll use them")

        elif step.step_type == 'tool':
            tips.append("Ensure tools are clean and in good working condition")
            tips.append("Have safety equipment ready if needed")

        elif step.is_milestone:
            tips.append("This is a good checkpoint to review your progress")
            tips.append("Take photos to document your milestone achievement")

        return tips

    def _generate_step_warnings(self, step: WorkflowStep, execution: WorkflowExecution) -> List[str]:
        """Generate warnings for a step."""
        warnings = []

        if step.step_type == 'tool':
            warnings.append("Always follow safety guidelines when using tools")

        if step.is_decision_point:
            warnings.append("This decision cannot be easily undone - choose carefully")

        return warnings

    # Command handlers
    def _handle_help_command(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle help command."""
        return {
            'success': True,
            'message': 'Available commands:',
            'commands': [
                'help - Show this help',
                'status - Show current progress',
                'next - Move to next step',
                'complete - Mark current step as complete',
                'back - Go to previous step',
                'show steps - List all steps',
                'show resources - Show required resources'
            ]
        }

    def _handle_status_command(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle status command."""
        context = self.get_navigation_context(execution_id, user_id)
        return {
            'success': True,
            'message': f"Workflow: {context['workflow_name']}",
            'status': context['status'],
            'progress': context['progress'],
            'current_step': context['current_step']
        }

    def _handle_next_command(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle next command."""
        suggestion = self.suggest_next_action(execution_id, user_id)
        return {
            'success': True,
            'message': suggestion['message'],
            'suggested_action': suggestion
        }

    def _handle_complete_command(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle complete command."""
        execution = self.execution_service.get_execution(execution_id, user_id)

        if not execution.current_step_id:
            return {
                'success': False,
                'message': 'No current step to complete'
            }

        try:
            updated_execution = self.execution_service.complete_step(
                execution_id, execution.current_step_id, user_id
            )
            return {
                'success': True,
                'message': f'Completed step: {execution.current_step.name}',
                'next_suggestion': self.suggest_next_action(execution_id, user_id)
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Could not complete step: {str(e)}'
            }

    def _handle_back_command(self, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle back command."""
        # This would implement going back to previous step
        return {
            'success': False,
            'message': 'Going back is not yet implemented'
        }

    def _handle_skip_command(self, execution_id: int, command: str, user_id: int) -> Dict[str, Any]:
        """Handle skip command."""
        return {
            'success': False,
            'message': 'Skipping steps is not yet implemented'
        }

    def _handle_show_command(self, execution_id: int, command: str, user_id: int) -> Dict[str, Any]:
        """Handle show/list commands."""
        if 'steps' in command:
            context = self.get_navigation_context(execution_id, user_id)
            return {
                'success': True,
                'message': 'Available navigation options:',
                'options': context['navigation_options']
            }
        elif 'resources' in command:
            execution = self.execution_service.get_execution(execution_id, user_id)
            if execution.current_step:
                guidance = self.get_step_guidance(execution_id, execution.current_step.id, user_id)
                return {
                    'success': True,
                    'message': f'Resources for {execution.current_step.name}:',
                    'resources': guidance['resources']
                }
            else:
                return {
                    'success': False,
                    'message': 'No current step to show resources for'
                }

        return {
            'success': False,
            'message': 'Show what? Try "show steps" or "show resources"'
        }

    # Path finding helpers
    def _build_step_graph(self, steps: List[WorkflowStep]) -> Dict[int, List[int]]:
        """Build a graph representation of step connections."""
        graph = {}
        for step in steps:
            graph[step.id] = []
            for connection in step.outgoing_connections:
                graph[step.id].append(connection.target_step_id)
        return graph

    def _find_shortest_path(self, graph: Dict[int, List[int]], start: int, end: int,
                            steps: List[WorkflowStep]) -> Optional[List[Dict[str, Any]]]:
        """Find shortest path between two steps using BFS."""
        from collections import deque

        if start == end:
            return []

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            for neighbor in graph.get(current, []):
                if neighbor == end:
                    full_path = path + [neighbor]
                    # Convert to step info
                    step_map = {step.id: step for step in steps}
                    return [{
                        'step_id': step_id,
                        'step_name': step_map[step_id].name,
                        'step_type': step_map[step_id].step_type,
                        'estimated_duration': step_map[step_id].estimated_duration
                    } for step_id in full_path]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def _select_optimal_path(self, paths: List[List[Dict[str, Any]]],
                             execution: WorkflowExecution) -> Optional[List[Dict[str, Any]]]:
        """Select the optimal path from available options."""
        if not paths:
            return None

        # For now, select shortest path
        # Could be enhanced with more sophisticated criteria
        return min(paths, key=len)

    def _calculate_path_time(self, path: Optional[List[Dict[str, Any]]]) -> Optional[float]:
        """Calculate estimated time for a path."""
        if not path:
            return None

        total_time = 0
        for step in path:
            if step.get('estimated_duration'):
                total_time += step['estimated_duration']

        return total_time if total_time > 0 else None

    def _calculate_path_difficulty(self, path: Optional[List[Dict[str, Any]]]) -> int:
        """Calculate difficulty score for a path (1-10)."""
        if not path:
            return 0

        # Simple difficulty calculation based on path length and step types
        base_difficulty = min(len(path), 10)

        # Add complexity for decision points
        decision_steps = sum(1 for step in path if step.get('step_type') == 'decision')
        complexity_bonus = min(decision_steps * 2, 5)

        return min(base_difficulty + complexity_bonus, 10)

    def _find_outcome_steps(self, workflow_id: int, outcome_id: int) -> List[int]:
        """Find steps that lead to a specific outcome."""
        # This would implement logic to find steps associated with an outcome
        # For now, return empty list
        return []