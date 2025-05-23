# File: app/core/events.py

from typing import (
    Dict,
    Any,
    Callable,
    List,
    Optional,
    Set,
    Union,
    TypeVar,
    Generic,
    Type,
    Coroutine,
)
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
import uuid
import asyncio
import logging
import json
from fastapi import FastAPI
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Type definitions
T_event = TypeVar("T_event", bound="DomainEvent")
EventHandler = Callable[[T_event], None]
AsyncEventHandler = Callable[[T_event], Coroutine[Any, Any, None]]


# --- Base DomainEvent ---
@dataclass(eq=False)  # Using eq=False is generally safer for mutable objects like events
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Ensure timestamp is ISO string
        if isinstance(self.timestamp, datetime):
            result["timestamp"] = self.timestamp.isoformat()
        elif isinstance(self.timestamp, str):
            pass  # Assume already ISO
        else:
            result["timestamp"] = str(self.timestamp)  # Fallback

        result["event_type"] = self.__class__.__name__

        # Convert other date/datetime fields if they exist in subclasses
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, date):
                result[key] = value.isoformat()
        return result


# --- Core Entity Event Definitions ---
@dataclass(eq=False)
class EntityCreatedEvent(DomainEvent):
    entity_id: Any = None;
    entity_type: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class EntityUpdatedEvent(DomainEvent):
    entity_id: Any = None;
    entity_type: str = "";
    changes: Dict[str, Any] = field(default_factory=dict);
    user_id: Optional[int] = None


@dataclass(eq=False)
class EntityDeletedEvent(DomainEvent):
    entity_id: Any = None;
    entity_type: str = "";
    user_id: Optional[int] = None


# --- Tool Management Event Definitions ---
@dataclass(eq=False)
class ToolCreated(DomainEvent):
    tool_id: int = 0;
    name: str = "";
    category: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class ToolStatusChanged(DomainEvent):
    tool_id: int = 0;
    previous_status: str = "";
    new_status: str = "";
    reason: Optional[str] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class ToolMaintenanceScheduled(DomainEvent):
    maintenance_id: int = 0;
    tool_id: int = 0;
    maintenance_type: str = "";
    date: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class ToolMaintenanceCompleted(DomainEvent):
    maintenance_id: int = 0;
    tool_id: int = 0;
    completion_date: str = "";
    performed_by: Optional[str] = None;
    next_date: Optional[str] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class ToolCheckedOut(DomainEvent):
    checkout_id: int = 0;
    tool_id: int = 0;
    checked_out_by: str = "";
    project_id: Optional[int] = None;
    due_date: str = "";
    user_id: Optional[int] = None  # due_date is required in model


@dataclass(eq=False)
class ToolReturned(DomainEvent):
    checkout_id: int = 0;
    tool_id: int = 0;
    has_issues: bool = False;
    condition_after: Optional[str] = None;
    user_id: Optional[int] = None


# --- Workflow Management Event Definitions ---
@dataclass(eq=False)
class WorkflowCreatedEvent(DomainEvent):
    """Event fired when a workflow is created."""
    workflow_id: int = 0;
    workflow_name: str = "";
    is_template: bool = False;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowUpdatedEvent(DomainEvent):
    """Event fired when a workflow is updated."""
    workflow_id: int = 0;
    workflow_name: str = "";
    changes: Dict[str, Any] = field(default_factory=dict);
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowDeletedEvent(DomainEvent):
    """Event fired when a workflow is deleted."""
    workflow_id: int = 0;
    workflow_name: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowPublishedEvent(DomainEvent):
    """Event fired when a workflow is published as a template."""
    workflow_id: int = 0;
    workflow_name: str = "";
    visibility: str = "public";
    user_id: Optional[int] = None


# --- Workflow Execution Event Definitions ---
@dataclass(eq=False)
class WorkflowStartedEvent(DomainEvent):
    """Event fired when a workflow execution is started."""
    workflow_id: int = 0;
    execution_id: int = 0;
    workflow_name: str = "";
    selected_outcome_id: Optional[int] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowCompletedEvent(DomainEvent):
    """Event fired when a workflow execution is completed."""
    workflow_id: int = 0;
    execution_id: int = 0;
    workflow_name: str = "";
    outcome_id: Optional[int] = None;
    total_duration: Optional[float] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowPausedEvent(DomainEvent):
    """Event fired when a workflow execution is paused."""
    workflow_id: int = 0;
    execution_id: int = 0;
    workflow_name: str = "";
    reason: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowResumedEvent(DomainEvent):
    """Event fired when a workflow execution is resumed."""
    workflow_id: int = 0;
    execution_id: int = 0;
    workflow_name: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowCancelledEvent(DomainEvent):
    """Event fired when a workflow execution is cancelled."""
    workflow_id: int = 0;
    execution_id: int = 0;
    workflow_name: str = "";
    reason: str = "";
    user_id: Optional[int] = None


# --- Workflow Step Event Definitions ---
@dataclass(eq=False)
class WorkflowStepStartedEvent(DomainEvent):
    """Event fired when a workflow step is started."""
    workflow_id: int = 0;
    execution_id: int = 0;
    step_id: int = 0;
    step_name: str = "";
    step_type: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowStepCompletedEvent(DomainEvent):
    """Event fired when a workflow step is completed."""
    workflow_id: int = 0;
    execution_id: int = 0;
    step_id: int = 0;
    step_name: str = "";
    step_type: str = "";
    actual_duration: Optional[float] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowDecisionMadeEvent(DomainEvent):
    """Event fired when a decision is made at a decision point."""
    workflow_id: int = 0;
    execution_id: int = 0;
    step_id: int = 0;
    step_name: str = "";
    decision_option_id: int = 0;
    decision_text: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowNavigationEvent(DomainEvent):
    """Event fired when user navigates to a specific step."""
    workflow_id: int = 0;
    execution_id: int = 0;
    from_step_id: Optional[int] = None;
    to_step_id: int = 0;
    navigation_type: str = "manual";
    user_id: Optional[int] = None


# --- Workflow Resource Event Definitions ---
@dataclass(eq=False)
class WorkflowResourceReservedEvent(DomainEvent):
    """Event fired when resources are reserved for a workflow execution."""
    workflow_id: int = 0;
    execution_id: int = 0;
    resource_type: str = "";
    resource_id: int = 0;
    resource_name: str = "";
    quantity: Optional[float] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowResourceReleasedEvent(DomainEvent):
    """Event fired when resources are released from a workflow execution."""
    workflow_id: int = 0;
    execution_id: int = 0;
    resource_type: str = "";
    resource_id: int = 0;
    resource_name: str = "";
    quantity: Optional[float] = None;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowResourceUnavailableEvent(DomainEvent):
    """Event fired when required resources are unavailable."""
    workflow_id: int = 0;
    execution_id: int = 0;
    resource_type: str = "";
    resource_id: int = 0;
    resource_name: str = "";
    required_quantity: Optional[float] = None;
    available_quantity: Optional[float] = None;
    user_id: Optional[int] = None


# --- Workflow Import/Export Event Definitions ---
@dataclass(eq=False)
class WorkflowImportedEvent(DomainEvent):
    """Event fired when a workflow is imported from JSON."""
    workflow_id: int = 0;
    workflow_name: str = "";
    source: str = "";
    preset_name: str = "";
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowExportedEvent(DomainEvent):
    """Event fired when a workflow is exported to JSON."""
    workflow_id: int = 0;
    workflow_name: str = "";
    export_format: str = "json";
    user_id: Optional[int] = None


# --- Workflow Analytics Event Definitions ---
@dataclass(eq=False)
class WorkflowMilestoneReachedEvent(DomainEvent):
    """Event fired when a workflow milestone is reached."""
    workflow_id: int = 0;
    execution_id: int = 0;
    step_id: int = 0;
    milestone_name: str = "";
    progress_percentage: float = 0.0;
    user_id: Optional[int] = None


@dataclass(eq=False)
class WorkflowProgressUpdateEvent(DomainEvent):
    """Event fired when workflow progress is updated significantly."""
    workflow_id: int = 0;
    execution_id: int = 0;
    total_steps: int = 0;
    completed_steps: int = 0;
    progress_percentage: float = 0.0;
    estimated_remaining: Optional[float] = None;
    user_id: Optional[int] = None


# --- Event Bus Class ---
class EventBus:
    """
    Central event bus for domain events with both synchronous and asynchronous support.

    Features:
    - Thread-safe event publishing and subscription management
    - Support for both sync and async event handlers
    - Automatic error handling and logging
    - Type-safe event subscription
    - Background task management for async operations

    Usage:
        # Synchronous event handling
        global_event_bus.subscribe(WorkflowCreatedEvent, handle_workflow_created)
        global_event_bus.publish(WorkflowCreatedEvent(workflow_id=123))

        # Asynchronous event handling
        await global_event_bus.subscribe_async(WorkflowStartedEvent, handle_workflow_started_async)
        await global_event_bus.publish_async(WorkflowStartedEvent(execution_id=456))
    """

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event synchronously to all registered handlers.

        Args:
            event: The domain event to publish

        Note:
            - Async handlers will be logged as warnings when called synchronously
            - All handler exceptions are caught and logged
        """
        event_type = type(event).__name__
        logger.debug(f"Publishing sync event {event_type} ID {event.event_id}")
        subscribers_copy = list(self.subscribers.get(event_type, []))
        for handler in subscribers_copy:
            self._call_handler_sync(handler, event, event_type)

    def _call_handler_sync(self, handler: Callable, event: DomainEvent, event_type: str):
        """Handle synchronous event handler execution with error management."""
        try:
            if asyncio.iscoroutinefunction(handler):
                logger.warning(f"Sync call to async handler {handler.__name__} for {event_type}. Use publish_async.")
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Error in sync handler {handler.__name__} for {event_type} ID {event.event_id}: {e}",
                         exc_info=True)

    async def publish_async(self, event: DomainEvent) -> None:
        """
        Publish an event asynchronously to all registered handlers.

        Args:
            event: The domain event to publish

        Note:
            - Sync handlers are automatically wrapped in asyncio.to_thread()
            - All tasks are gathered with exception handling
        """
        event_type = type(event).__name__
        logger.debug(f"Publishing async event {event_type} ID {event.event_id}")
        async with self._lock:
            subscribers_copy = list(self.subscribers.get(event_type, []))
        tasks = [task for handler in subscribers_copy if
                 (task := self._create_handler_task(handler, event, event_type))]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self._log_handler_errors(results, subscribers_copy, event_type, event.event_id)

    def _create_handler_task(self, handler: Callable, event: DomainEvent, event_type: str) -> Optional[asyncio.Task]:
        """Create an asyncio task for event handler execution."""
        try:
            if asyncio.iscoroutinefunction(handler):
                return asyncio.create_task(handler(event))
            else:
                return asyncio.create_task(asyncio.to_thread(handler, event))
        except Exception as e:
            logger.error(f"Error creating task for handler {handler.__name__} for {event_type}: {e}", exc_info=True)
            return None

    def _log_handler_errors(self, results: List[Any], subscribers: List[Callable], event_type: str, event_id: str):
        """Log any errors that occurred during async handler execution."""
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler_name = subscribers[i].__name__ if i < len(subscribers) else 'unknown'
                logger.error(f"Error in handler '{handler_name}' for {event_type} ID {event_id}: {result}",
                             exc_info=result)

    async def subscribe_async(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> None:
        """
        Subscribe to an event type asynchronously.

        Args:
            event_type: Event class or event type name string
            handler: Callable to handle the event (sync or async)
        """
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        async with self._lock:
            self.subscribers[event_type_name].append(handler)
        logger.debug(f"Subscribed async handler {getattr(handler, '__name__', repr(handler))} to {event_type_name}")

    def subscribe(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> None:
        """
        Subscribe to an event type synchronously.

        Args:
            event_type: Event class or event type name string
            handler: Callable to handle the event (sync or async)
        """
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        self.subscribers[event_type_name].append(handler)
        logger.debug(f"Subscribed sync handler {getattr(handler, '__name__', repr(handler))} to {event_type_name}")

    async def unsubscribe_async(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> bool:
        """
        Unsubscribe from an event type asynchronously.

        Args:
            event_type: Event class or event type name string
            handler: Handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        unsubscribed = False
        async with self._lock:
            if event_type_name in self.subscribers:
                try:
                    self.subscribers[event_type_name].remove(handler)
                    unsubscribed = True
                except ValueError:
                    pass
        if unsubscribed:
            logger.debug(f"Unsubscribed handler {getattr(handler, '__name__', repr(handler))} from {event_type_name}")
        return unsubscribed

    def unsubscribe(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> bool:
        """
        Unsubscribe from an event type synchronously.

        Args:
            event_type: Event class or event type name string
            handler: Handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        if event_type_name in self.subscribers:
            try:
                self.subscribers[event_type_name].remove(handler)
                logger.debug(
                    f"Unsubscribed handler {getattr(handler, '__name__', repr(handler))} from {event_type_name}")
                return True
            except ValueError:
                return False
        return False

    async def clear_subscriptions_async(self) -> None:
        """Clear all event subscriptions asynchronously."""
        async with self._lock:
            self.subscribers.clear()
        logger.debug("Cleared all async event subscriptions")

    def clear_subscriptions(self) -> None:
        """Clear all event subscriptions synchronously."""
        self.subscribers.clear()
        logger.debug("Cleared all sync event subscriptions")


# Global event bus instance - use this throughout the application
global_event_bus = EventBus()


# --- FastAPI Event Handlers Setup ---
def setup_event_handlers(app: FastAPI) -> None:
    """
    Set up FastAPI lifecycle event handlers.

    Args:
        app: FastAPI application instance

    Note:
        This function should be called during application initialization
        to properly handle startup and shutdown events.
    """

    @app.on_event("startup")
    async def startup_event():
        logger.info("Application starting up")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutting down")
        # Cancel any remaining background tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if tasks:
            logger.info(f"Cancelling {len(tasks)} background tasks")
            [t.cancel() for t in tasks]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Background tasks cancelled")