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

logger = logging.getLogger(__name__)

# Type definitions
T_event = TypeVar("T_event", bound="DomainEvent")
EventHandler = Callable[[T_event], None]
AsyncEventHandler = Callable[[T_event], Coroutine[Any, Any, None]]


# --- Base DomainEvent with init=False to avoid parameter order problems ---
@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if isinstance(self.timestamp, datetime):
            result["timestamp"] = self.timestamp.isoformat()
        result["event_type"] = self.__class__.__name__
        return result


# --- Corrected Event Definitions ---
@dataclass
class EntityCreatedEvent(DomainEvent):
    entity_id: Any = None
    entity_type: str = ""
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.entity_id is None or self.entity_type == "":
            raise ValueError("entity_id and entity_type are required")


@dataclass
class EntityUpdatedEvent(DomainEvent):
    entity_id: Any = None
    entity_type: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.entity_id is None or self.entity_type == "":
            raise ValueError("entity_id and entity_type are required")


@dataclass
class EntityDeletedEvent(DomainEvent):
    entity_id: Any = None
    entity_type: str = ""
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.entity_id is None or self.entity_type == "":
            raise ValueError("entity_id and entity_type are required")


@dataclass
class ToolCreated(DomainEvent):
    tool_id: int = 0
    name: str = ""
    category: str = ""
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.tool_id == 0 or self.name == "" or self.category == "":
            raise ValueError("tool_id, name, and category are required")


@dataclass
class ToolStatusChanged(DomainEvent):
    tool_id: int = 0
    previous_status: str = ""
    new_status: str = ""
    reason: Optional[str] = None
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.tool_id == 0 or self.previous_status == "" or self.new_status == "":
            raise ValueError("tool_id, previous_status, and new_status are required")


@dataclass
class ToolMaintenanceScheduled(DomainEvent):
    maintenance_id: int = 0
    tool_id: int = 0
    maintenance_type: str = ""
    date: str = ""
    user_id: Optional[int] = None

    def __post_init__(self):
        if (
            self.maintenance_id == 0
            or self.tool_id == 0
            or self.maintenance_type == ""
            or self.date == ""
        ):
            raise ValueError(
                "maintenance_id, tool_id, maintenance_type, and date are required"
            )


@dataclass
class ToolMaintenanceCompleted(DomainEvent):
    maintenance_id: int = 0
    tool_id: int = 0
    completion_date: str = ""
    performed_by: Optional[str] = None
    next_date: Optional[str] = None
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.maintenance_id == 0 or self.tool_id == 0 or self.completion_date == "":
            raise ValueError(
                "maintenance_id, tool_id, and completion_date are required"
            )


@dataclass
class ToolCheckedOut(DomainEvent):
    checkout_id: int = 0
    tool_id: int = 0
    checked_out_by: str = ""
    project_id: Optional[int] = None
    due_date: Optional[str] = None
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.checkout_id == 0 or self.tool_id == 0 or self.checked_out_by == "":
            raise ValueError("checkout_id, tool_id, and checked_out_by are required")


@dataclass
class ToolReturned(DomainEvent):
    checkout_id: int = 0
    tool_id: int = 0
    has_issues: bool = False
    condition_after: Optional[str] = None
    user_id: Optional[int] = None

    def __post_init__(self):
        if self.checkout_id == 0 or self.tool_id == 0:
            raise ValueError("checkout_id and tool_id are required")


# --- Event Bus Class (Expanded Methods) ---
class EventBus:
    """Central event bus for domain events."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def publish(self, event: DomainEvent) -> None:
        event_type = type(event).__name__
        logger.debug(f"Publishing sync event {event_type} ID {event.event_id}")
        # Get handlers safely
        subscribers_copy = list(self.subscribers.get(event_type, []))
        for handler in subscribers_copy:
            self._call_handler_sync(handler, event, event_type)

    def _call_handler_sync(
        self, handler: Callable, event: DomainEvent, event_type: str
    ):
        try:
            if asyncio.iscoroutinefunction(handler):
                logger.warning(
                    f"Sync call to async handler {handler.__name__} for {event_type}. Consider publish_async."
                )
                # Best effort, might block or fail if loop is running
                try:
                    loop = asyncio.get_running_loop()
                    logger.error(
                        "Cannot reliably run async handler synchronously inside running loop."
                    )
                    # Option: loop.create_task(handler(event)) # Fire and forget? Risky
                except RuntimeError:  # No running loop
                    asyncio.run(handler(event))
            else:
                handler(event)
        except Exception as e:
            logger.error(
                f"Error in sync handler {handler.__name__} for {event_type} (ID: {event.event_id}): {e}",
                exc_info=True,
            )

    async def publish_async(self, event: DomainEvent) -> None:
        event_type = type(event).__name__
        logger.debug(f"Publishing async event {event_type} ID {event.event_id}")
        async with self._lock:
            subscribers_copy = list(self.subscribers.get(event_type, []))

        tasks = []
        for handler in subscribers_copy:
            task = self._create_handler_task(handler, event, event_type)
            if task:
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self._log_handler_errors(
                results, subscribers_copy, event_type, event.event_id
            )

    def _create_handler_task(
        self, handler: Callable, event: DomainEvent, event_type: str
    ) -> Optional[asyncio.Task]:
        try:
            if asyncio.iscoroutinefunction(handler):
                return asyncio.create_task(handler(event))
            else:
                return asyncio.to_thread(handler, event)
        except Exception as e:
            logger.error(
                f"Error creating task for handler {handler.__name__} for {event_type}: {e}",
                exc_info=True,
            )
            return None

    def _log_handler_errors(
        self,
        results: List[Any],
        subscribers: List[Callable],
        event_type: str,
        event_id: str,
    ):
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler_name = "?"
                if i < len(subscribers):
                    try:
                        handler_name = subscribers[i].__name__
                    except AttributeError:
                        pass
                logger.error(
                    f"Error in handler '{handler_name}' for {event_type} ID {event_id}: {result}",
                    exc_info=result,
                )

    async def subscribe_async(
        self, event_type: Union[str, Type[DomainEvent]], handler: Callable
    ) -> None:
        """Asynchronously subscribe a handler to an event type."""
        event_type_name = (
            event_type.__name__ if isinstance(event_type, type) else str(event_type)
        )
        async with self._lock:
            self.subscribers[event_type_name].append(handler)
        logger.debug(
            f"Subscribed handler {handler.__name__} to event type {event_type_name}"
        )

    def subscribe(
        self, event_type: Union[str, Type[DomainEvent]], handler: Callable
    ) -> None:
        """Subscribe a handler to an event type."""
        event_type_name = (
            event_type.__name__ if isinstance(event_type, type) else str(event_type)
        )
        # If thread safety needed for sync subscribe, add appropriate lock
        self.subscribers[event_type_name].append(handler)
        logger.debug(
            f"Subscribed handler {handler.__name__} to event type {event_type_name}"
        )

    async def unsubscribe_async(
        self, event_type: Union[str, Type[DomainEvent]], handler: Callable
    ) -> bool:
        """Asynchronously unsubscribe a handler from an event type."""
        event_type_name = (
            event_type.__name__ if isinstance(event_type, type) else str(event_type)
        )
        unsubscribed = False
        async with self._lock:
            if (
                event_type_name in self.subscribers
                and handler in self.subscribers[event_type_name]
            ):
                try:
                    self.subscribers[event_type_name].remove(handler)
                    unsubscribed = True
                except ValueError:  # Handler might have been removed concurrently
                    pass
        if unsubscribed:
            logger.debug(
                f"Unsubscribed handler {handler.__name__} from event type {event_type_name}"
            )
        return unsubscribed

    def unsubscribe(
        self, event_type: Union[str, Type[DomainEvent]], handler: Callable
    ) -> bool:
        """Unsubscribe a handler from an event type."""
        event_type_name = (
            event_type.__name__ if isinstance(event_type, type) else str(event_type)
        )
        # If thread safety needed for sync unsubscribe, add appropriate lock
        if (
            event_type_name in self.subscribers
            and handler in self.subscribers[event_type_name]
        ):
            try:
                self.subscribers[event_type_name].remove(handler)
                logger.debug(
                    f"Unsubscribed handler {handler.__name__} from event type {event_type_name}"
                )
                return True
            except ValueError:
                return False  # Handler already removed
        return False

    async def clear_subscriptions_async(self) -> None:
        """Asynchronously clear all subscriptions."""
        async with self._lock:
            self.subscribers.clear()
        logger.debug("Cleared all event subscriptions")

    def clear_subscriptions(self) -> None:
        """Clear all subscriptions."""
        # If thread safety needed, add appropriate lock
        self.subscribers.clear()
        logger.debug("Cleared all event subscriptions")


global_event_bus = EventBus()


# --- FastAPI Event Handlers Setup (Keep as is) ---
def setup_event_handlers(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_event():
        logger.info("Application starting up")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutting down")
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        ]
        if tasks:
            logger.info(f"Cancelling {len(tasks)} tasks")
            [t.cancel() for t in tasks]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Tasks cancelled")
