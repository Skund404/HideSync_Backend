# File: app/services/base_service.py

from typing import TypeVar, Generic, List, Optional, Type, Dict, Any
from contextlib import contextmanager
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.core.exceptions import HideSyncException
from app.repositories.base_repository import BaseRepository

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BaseService(Generic[T]):
    """
    Base service for all HideSync system services.

    Provides common functionality including:
    - Transaction management
    - Error handling and standardization
    - Logging
    - Basic CRUD operations
    """

    def __init__(
        self,
        session: Session,
        repository_class: Type[BaseRepository],
        security_context=None,
        event_bus=None,
        cache_service=None,
    ):
        """
        Initialize service with dependencies.

        Args:
            session: Database session for persistence operations
            repository_class: Repository class to instantiate
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.repository = repository_class(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    @contextmanager
    def transaction(self):
        """
        Provide a transactional scope around operations.

        Yields:
            None

        Raises:
            Exception: Any exception that occurs during transaction execution
        """
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Transaction failed: {str(e)}", exc_info=True)

            # Transform database errors to domain exceptions if needed
            if hasattr(self, "_transform_error"):
                transformed = self._transform_error(e)
                if transformed:
                    raise transformed
            raise

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by ID with optional caching.

        Args:
            id: Entity ID to retrieve

        Returns:
            Entity if found, None otherwise
        """
        if self.cache_service:
            cache_key = f"{self.repository.model.__name__}:{id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        entity = self.repository.get_by_id(id)

        if entity and self.cache_service:
            self.cache_service.set(cache_key, entity, ttl=3600)

        return entity

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """
        List entities with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filters to apply

        Returns:
            List of entities matching the criteria
        """
        return self.repository.list(skip=skip, limit=limit, **filters)

    def list_paginated(
        self,
        page_size: int = 100,
        cursor: Optional[str] = None,
        sort_by: str = "id",
        sort_dir: str = "asc",
        **filters,
    ) -> Dict[str, Any]:
        """
        List entities with cursor-based pagination and filtering.

        Args:
            page_size: Number of records per page
            cursor: Opaque cursor for continued pagination
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            **filters: Additional filters to apply

        Returns:
            Dictionary with items, pagination metadata, and next cursor
        """
        # Implementation details for cursor-based pagination
        results, next_cursor = self.repository.list_paginated(
            page_size=page_size,
            cursor=cursor,
            sort_by=sort_by,
            sort_dir=sort_dir,
            **filters,
        )

        return {
            "items": results,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": next_cursor is not None,
                "page_size": page_size,
            },
        }

    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new entity.

        Args:
            data: Dictionary of entity data

        Returns:
            Created entity
        """
        with self.transaction():
            entity = self.repository.create(data)

            # Publish creation event if event bus exists
            if self.event_bus and hasattr(self, "_create_created_event"):
                event = self._create_created_event(entity)
                if event:
                    self.event_bus.publish(event)

            return entity

    def update(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.

        Args:
            id: Entity ID to update
            data: Dictionary of entity data to update

        Returns:
            Updated entity if found, None otherwise
        """
        with self.transaction():
            # Get the entity before update for event creation
            original = self.repository.get_by_id(id) if self.event_bus else None

            entity = self.repository.update(id, data)
            if not entity:
                return None

            # Invalidate cache if cache service exists
            if self.cache_service:
                cache_key = f"{self.repository.model.__name__}:{id}"
                self.cache_service.invalidate(cache_key)

            # Publish update event if event bus exists
            if self.event_bus and original and hasattr(self, "_create_updated_event"):
                event = self._create_updated_event(original, entity)
                if event:
                    self.event_bus.publish(event)

            return entity

    def delete(self, id: int) -> bool:
        """
        Delete an entity by ID.

        Args:
            id: Entity ID to delete

        Returns:
            True if entity was deleted, False otherwise
        """
        with self.transaction():
            # Get the entity before deletion for event creation
            entity = self.repository.get_by_id(id) if self.event_bus else None

            result = self.repository.delete(id)
            if not result:
                return False

            # Invalidate cache if cache service exists
            if self.cache_service:
                cache_key = f"{self.repository.model.__name__}:{id}"
                self.cache_service.invalidate(cache_key)

            # Publish deletion event if event bus exists
            if self.event_bus and entity and hasattr(self, "_create_deleted_event"):
                event = self._create_deleted_event(entity)
                if event:
                    self.event_bus.publish(event)

            return True

    def _log_operation(
        self,
        operation: str,
        entity_type: str,
        entity_id: Any = None,
        details: Dict[str, Any] = None,
    ) -> None:
        """
        Log an operation for auditing purposes.

        Args:
            operation: Operation name (create, update, delete, etc.)
            entity_type: Type of entity being operated on
            entity_id: Optional entity ID
            details: Optional operation details
        """
        user_id = None
        if self.security_context and hasattr(self.security_context, "current_user"):
            user_id = getattr(self.security_context.current_user, "id", None)

        log_data = {
            "operation": operation,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }

        logger.info(f"{operation.upper()} {entity_type} {entity_id}", extra=log_data)
