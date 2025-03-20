# File: app/core/events.py

from typing import Dict, Any, Callable, List, Optional, Set, Union
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import asyncio
import logging
import json

logger = logging.getLogger(__name__)


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
        return {
            "event_id": self.event_id,
            "event_type": self.__class__.__name__,
            "timestamp": self.timestamp.isoformat(),
            **{
                k: v
                for k, v in self.__dict__.items()
                if k not in ["event_id", "timestamp"]
            },
        }


class EventBus:
    """Central event bus for domain events."""

    def __init__(self):
        """Initialize the event bus with empty subscribers."""
        self.subscribers = defaultdict(list)

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Domain event to publish
        """
        event_type = type(event).__name__
        logger.debug(f"Publishing event {event_type} with ID {event.event_id}")

        for subscriber in self.subscribers[event_type]:
            try:
                # For synchronous handlers
                subscriber(event)
            except Exception as e:
                logger.error(
                    f"Error handling event {event_type}: {str(e)}", exc_info=True
                )

    async def publish_async(self, event: DomainEvent) -> None:
        """
        Publish an event asynchronously to all subscribers.

        Args:
            event: Domain event to publish
        """
        event_type = type(event).__name__
        logger.debug(f"Publishing async event {event_type} with ID {event.event_id}")

        tasks = []
        for subscriber in self.subscribers[event_type]:
            if asyncio.iscoroutinefunction(subscriber):
                tasks.append(asyncio.create_task(subscriber(event)))
            else:
                # Run synchronous handlers in executor
                tasks.append(asyncio.to_thread(subscriber, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: Event type name to subscribe to
            handler: Callable to handle the event
        """
        self.subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to event type {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Event type name to unsubscribe from
            handler: Handler to unsubscribe

        Returns:
            True if handler was unsubscribed, False otherwise
        """
        if event_type in self.subscribers and handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed handler from event type {event_type}")
            return True
        return False

    def clear_subscriptions(self) -> None:
        """Clear all subscriptions (useful for testing)."""
        self.subscribers.clear()


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
