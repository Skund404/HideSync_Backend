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


# --- Base DomainEvent ---
@dataclass(eq=False) # Using eq=False is generally safer for mutable objects like events
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Ensure timestamp is ISO string
        if isinstance(self.timestamp, datetime):
            result["timestamp"] = self.timestamp.isoformat()
        elif isinstance(self.timestamp, str): pass # Assume already ISO
        else: result["timestamp"] = str(self.timestamp) # Fallback

        result["event_type"] = self.__class__.__name__

        # Convert other date/datetime fields if they exist in subclasses
        for key, value in result.items():
            if isinstance(value, datetime): result[key] = value.isoformat()
            elif isinstance(value, date): result[key] = value.isoformat()
        return result

# --- Specific Event Definitions ---
# Removed __post_init__ for brevity, can be added back if needed
@dataclass(eq=False)
class EntityCreatedEvent(DomainEvent):
    entity_id: Any = None; entity_type: str = ""; user_id: Optional[int] = None

@dataclass(eq=False)
class EntityUpdatedEvent(DomainEvent):
    entity_id: Any = None; entity_type: str = ""; changes: Dict[str, Any] = field(default_factory=dict); user_id: Optional[int] = None

@dataclass(eq=False)
class EntityDeletedEvent(DomainEvent):
    entity_id: Any = None; entity_type: str = ""; user_id: Optional[int] = None

@dataclass(eq=False)
class ToolCreated(DomainEvent):
    tool_id: int = 0; name: str = ""; category: str = ""; user_id: Optional[int] = None

@dataclass(eq=False)
class ToolStatusChanged(DomainEvent):
    tool_id: int = 0; previous_status: str = ""; new_status: str = ""; reason: Optional[str] = None; user_id: Optional[int] = None

@dataclass(eq=False)
class ToolMaintenanceScheduled(DomainEvent):
    maintenance_id: int = 0; tool_id: int = 0; maintenance_type: str = ""; date: str = ""; user_id: Optional[int] = None

@dataclass(eq=False)
class ToolMaintenanceCompleted(DomainEvent):
    maintenance_id: int = 0; tool_id: int = 0; completion_date: str = ""; performed_by: Optional[str] = None; next_date: Optional[str] = None; user_id: Optional[int] = None

@dataclass(eq=False)
class ToolCheckedOut(DomainEvent):
    checkout_id: int = 0; tool_id: int = 0; checked_out_by: str = ""; project_id: Optional[int] = None; due_date: str = ""; user_id: Optional[int] = None # due_date is required in model

@dataclass(eq=False)
class ToolReturned(DomainEvent):
    checkout_id: int = 0; tool_id: int = 0; has_issues: bool = False; condition_after: Optional[str] = None; user_id: Optional[int] = None


# --- Event Bus Class (Keep as previously corrected) ---
class EventBus:
    """Central event bus for domain events."""
    def __init__(self): self.subscribers: Dict[str, List[Callable]] = defaultdict(list); self._lock = asyncio.Lock()
    def publish(self, event: DomainEvent) -> None:
        event_type = type(event).__name__; logger.debug(f"Publishing sync event {event_type} ID {event.event_id}")
        subscribers_copy = list(self.subscribers.get(event_type, []))
        for handler in subscribers_copy: self._call_handler_sync(handler, event, event_type)
    def _call_handler_sync(self, handler: Callable, event: DomainEvent, event_type: str):
        try:
            if asyncio.iscoroutinefunction(handler): logger.warning(f"Sync call to async handler {handler.__name__} for {event_type}. Use publish_async.")
            else: handler(event)
        except Exception as e: logger.error(f"Error in sync handler {handler.__name__} for {event_type} ID {event.event_id}: {e}", exc_info=True)
    async def publish_async(self, event: DomainEvent) -> None:
        event_type = type(event).__name__; logger.debug(f"Publishing async event {event_type} ID {event.event_id}")
        async with self._lock: subscribers_copy = list(self.subscribers.get(event_type, []))
        tasks = [task for handler in subscribers_copy if (task := self._create_handler_task(handler, event, event_type))]
        if tasks: results = await asyncio.gather(*tasks, return_exceptions=True); self._log_handler_errors(results, subscribers_copy, event_type, event.event_id)
    def _create_handler_task(self, handler: Callable, event: DomainEvent, event_type: str) -> Optional[asyncio.Task]:
        try:
            if asyncio.iscoroutinefunction(handler): return asyncio.create_task(handler(event))
            else: return asyncio.create_task(asyncio.to_thread(handler, event))
        except Exception as e: logger.error(f"Error creating task for handler {handler.__name__} for {event_type}: {e}", exc_info=True); return None
    def _log_handler_errors(self, results: List[Any], subscribers: List[Callable], event_type: str, event_id: str):
        for i, result in enumerate(results):
            if isinstance(result, Exception): handler_name = subscribers[i].__name__ if i < len(subscribers) else 'unknown'; logger.error(f"Error in handler '{handler_name}' for {event_type} ID {event_id}: {result}", exc_info=result)
    async def subscribe_async(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> None:
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        async with self._lock: self.subscribers[event_type_name].append(handler)
        logger.debug(f"Subscribed async handler {getattr(handler, '__name__', repr(handler))} to {event_type_name}")
    def subscribe(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> None:
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        self.subscribers[event_type_name].append(handler)
        logger.debug(f"Subscribed sync handler {getattr(handler, '__name__', repr(handler))} to {event_type_name}")
    async def unsubscribe_async(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> bool:
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type); unsubscribed = False
        async with self._lock:
            if event_type_name in self.subscribers:
                try: self.subscribers[event_type_name].remove(handler); unsubscribed = True
                except ValueError: pass
        if unsubscribed: logger.debug(f"Unsubscribed handler {getattr(handler, '__name__', repr(handler))} from {event_type_name}")
        return unsubscribed
    def unsubscribe(self, event_type: Union[str, Type[DomainEvent]], handler: Callable) -> bool:
        event_type_name = event_type.__name__ if isinstance(event_type, type) else str(event_type)
        if event_type_name in self.subscribers:
            try: self.subscribers[event_type_name].remove(handler); logger.debug(f"Unsubscribed handler {getattr(handler, '__name__', repr(handler))} from {event_type_name}"); return True
            except ValueError: return False
        return False
    async def clear_subscriptions_async(self) -> None:
        async with self._lock: self.subscribers.clear(); logger.debug("Cleared all async event subscriptions")
    def clear_subscriptions(self) -> None:
        self.subscribers.clear(); logger.debug("Cleared all sync event subscriptions")

global_event_bus = EventBus()

# --- FastAPI Event Handlers Setup ---
def setup_event_handlers(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_event(): logger.info("Application starting up")
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutting down")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if tasks: logger.info(f"Cancelling {len(tasks)} background tasks"); [t.cancel() for t in tasks]; await asyncio.gather(*tasks, return_exceptions=True); logger.info("Background tasks cancelled")