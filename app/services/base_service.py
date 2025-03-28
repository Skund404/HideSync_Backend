# File: app/services/base_service.py

from typing import TypeVar, Generic, List, Optional, Type, Dict, Any, Callable, Union
from contextlib import contextmanager
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.core.exceptions import HideSyncException, EntityNotFoundException, BusinessRuleException
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
    - User context management
    - Event handling
    - Cache management
    """

    def __init__(
            self,
            session: Session,
            repository_class: Optional[Type[BaseRepository]] = None,
            repository: Optional[BaseRepository] = None,
            security_context=None,
            event_bus=None,
            cache_service=None,
    ):
        """
        Initialize service with dependencies.

        Args:
            session: Database session for persistence operations
            repository_class: Repository class to instantiate (optional if repository is provided)
            repository: Repository instance (optional if repository_class is provided)
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session

        # Allow either repository instance or class to be provided
        if repository is not None:
            self.repository = repository
        elif repository_class is not None:
            self.repository = repository_class(session)
        else:
            # Subclasses may initialize repository directly
            self.repository = None

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

    @contextmanager
    def user_context(self, user_id: int):
        """
        Temporarily set a user context for an operation.

        Args:
            user_id: ID of the user to set as current

        Yields:
            None
        """
        if not self.security_context:
            # If no security context, just yield
            yield
            return

        # Store original user
        original_user = getattr(self.security_context, 'current_user', None)

        try:
            # Set temporary user
            self.security_context.current_user = type('User', (), {'id': user_id})
            yield
        finally:
            # Restore original user
            self.security_context.current_user = original_user

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

    def create(self, data: Dict[str, Any], user_id: Optional[int] = None) -> T:
        """
        Create a new entity.

        Args:
            data: Dictionary of entity data
            user_id: Optional user ID for the operation

        Returns:
            Created entity
        """
        # Use user context if user_id provided
        if user_id:
            with self.user_context(user_id):
                return self._create_internal(data)
        else:
            return self._create_internal(data)

    def _create_internal(self, data: Dict[str, Any]) -> T:
        """
        Internal implementation of create operation.

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

    def update(self, id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Optional[T]:
        """
        Update an existing entity.

        Args:
            id: Entity ID to update
            data: Dictionary of entity data to update
            user_id: Optional user ID for the operation

        Returns:
            Updated entity if found, None otherwise
        """
        # Use user context if user_id provided
        if user_id:
            with self.user_context(user_id):
                return self._update_internal(id, data)
        else:
            return self._update_internal(id, data)

    def _update_internal(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """
        Internal implementation of update operation.

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

    def delete(self, id: int, user_id: Optional[int] = None) -> bool:
        """
        Delete an entity by ID.

        Args:
            id: Entity ID to delete
            user_id: Optional user ID for the operation

        Returns:
            True if entity was deleted, False otherwise
        """
        # Use user context if user_id provided
        if user_id:
            with self.user_context(user_id):
                return self._delete_internal(id)
        else:
            return self._delete_internal(id)

    def _delete_internal(self, id: int) -> bool:
        """
        Internal implementation of delete operation.

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

    def get_entity_or_404(self, id: int, error_message: Optional[str] = None) -> T:
        """
        Get an entity by ID or raise EntityNotFoundException.

        Args:
            id: Entity ID to retrieve
            error_message: Optional custom error message

        Returns:
            Entity if found

        Raises:
            EntityNotFoundException: If entity is not found
        """
        entity = self.get_by_id(id)
        if not entity:
            entity_name = self.repository.model.__name__ if self.repository else "Entity"
            message = error_message or f"{entity_name} with ID {id} not found"
            raise EntityNotFoundException(message)
        return entity

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

    def _transform_error(self, error: Exception) -> Optional[HideSyncException]:
        """
        Transform generic exceptions to specific domain exceptions.

        Override this method in service subclasses to handle
        specific error cases.

        Args:
            error: The original exception

        Returns:
            Transformed domain exception, or None to re-raise original
        """
        return None