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
)
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid
import asyncio
import logging
import json
from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Type definitions for better type hinting
T = TypeVar("T", bound="DomainEvent")
EventHandler = Callable[[T], None]
AsyncEventHandler = Callable[[T], asyncio.coroutine]


@dataclass
class DomainEvent:
    """Base class for domain events."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary representation.

        Returns:
            Dictionary representation of the event
        """
        result = asdict(self)
        # Convert timestamp to ISO format string
        result["timestamp"] = self.timestamp.isoformat()
        # Add event_type field
        result["event_type"] = self.__class__.__name__
        return result


class EventBus:
    """Central event bus for domain events."""

    def __init__(self):
        """Initialize the event bus with empty subscribers."""
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Domain event to publish
        """
        event_type = type(event).__name__
        logger.debug(f"Publishing event {event_type} with ID {event.event_id}")

        # Make a local copy of subscribers to avoid issues if the list is modified during iteration
        subscribers = list(self.subscribers[event_type])

        for subscriber in subscribers:
            try:
                # For synchronous handlers
                subscriber(event)
            except Exception as e:
                logger.error(
                    f"Error handling event {event_type} (ID: {event.event_id}): {str(e)}",
                    exc_info=True,
                )

    async def publish_async(self, event: DomainEvent) -> None:
        """
        Publish an event asynchronously to all subscribers.

        Args:
            event: Domain event to publish
        """
        event_type = type(event).__name__
        logger.debug(f"Publishing async event {event_type} with ID {event.event_id}")

        async with self._lock:
            # Make a local copy of subscribers to avoid issues if the list is modified during iteration
            subscribers = list(self.subscribers[event_type])

        tasks = []
        for subscriber in subscribers:
            if asyncio.iscoroutinefunction(subscriber):
                tasks.append(asyncio.create_task(subscriber(event)))
            else:
                # Run synchronous handlers in executor
                tasks.append(asyncio.to_thread(subscriber, event))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error in async handler for {event_type} (ID: {event.event_id}): {str(result)}",
                        exc_info=result,
                    )

    def subscribe(
        self, event_type: Union[str, Type[DomainEvent]], handler: Callable
    ) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: Event type name or class to subscribe to
            handler: Callable to handle the event
        """
        # Allow subscribing with either event class or event name
        if isinstance(event_type, type) and issubclass(event_type, DomainEvent):
            event_type_name = event_type.__name__
        else:
            event_type_name = str(event_type)

        self.subscribers[event_type_name].append(handler)
        logger.debug(
            f"Subscribed handler {handler.__name__} to event type {event_type_name}"
        )

    def unsubscribe(
        self, event_type: Union[str, Type[DomainEvent]], handler: Callable
    ) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Event type name or class to unsubscribe from
            handler: Handler to unsubscribe

        Returns:
            True if handler was unsubscribed, False otherwise
        """
        # Allow unsubscribing with either event class or event name
        if isinstance(event_type, type) and issubclass(event_type, DomainEvent):
            event_type_name = event_type.__name__
        else:
            event_type_name = str(event_type)

        if (
            event_type_name in self.subscribers
            and handler in self.subscribers[event_type_name]
        ):
            self.subscribers[event_type_name].remove(handler)
            logger.debug(
                f"Unsubscribed handler {handler.__name__} from event type {event_type_name}"
            )
            return True
        return False

    def clear_subscriptions(self) -> None:
        """Clear all subscriptions (useful for testing)."""
        self.subscribers.clear()
        logger.debug("Cleared all event subscriptions")


# Global event bus instance
global_event_bus = EventBus()


# Common domain events
class EntityCreatedEvent(DomainEvent):
    """Base event for entity creation."""

    def __init__(self, entity_id: Any, entity_type: str, user_id: Optional[int] = None):
        """
        Initialize entity created event.

        Args:
            entity_id: ID of the created entity
            entity_type: Type of the created entity
            user_id: Optional ID of the user who created the entity
        """
        super().__init__()
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.user_id = user_id


class EntityUpdatedEvent(DomainEvent):
    """Base event for entity updates."""

    def __init__(
        self,
        entity_id: Any,
        entity_type: str,
        changes: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        """
        Initialize entity updated event.

        Args:
            entity_id: ID of the updated entity
            entity_type: Type of the updated entity
            changes: Dictionary of changed fields with old and new values
            user_id: Optional ID of the user who updated the entity
        """
        super().__init__()
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.changes = changes
        self.user_id = user_id


class EntityDeletedEvent(DomainEvent):
    """Base event for entity deletion."""

    def __init__(self, entity_id: Any, entity_type: str, user_id: Optional[int] = None):
        """
        Initialize entity deleted event.

        Args:
            entity_id: ID of the deleted entity
            entity_type: Type of the deleted entity
            user_id: Optional ID of the user who deleted the entity
        """
        super().__init__()
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.user_id = user_id


def setup_event_handlers(app: FastAPI) -> None:
    """
    Set up FastAPI application event handlers.

    This function registers startup and shutdown event handlers
    for the application to initialize and clean up resources.

    Args:
        app: The FastAPI application instance
    """

    @app.on_event("startup")
    async def startup_event():
        """
        Handle application startup events.

        Initializes necessary resources and connections.
        """
        logger.info("Application starting up")
        # Initialize resources here (database connections, caches, etc.)

    @app.on_event("shutdown")
    async def shutdown_event():
        """
        Handle application shutdown events.

        Cleanly closes connections and resources.
        """
        logger.info("Application shutting down")
        # Clean up resources here (close connections, flush caches, etc.)

        # Cancel any pending async tasks
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        ]

        if tasks:
            logger.info(f"Cancelling {len(tasks)} pending tasks")
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("All pending tasks cancelled")
