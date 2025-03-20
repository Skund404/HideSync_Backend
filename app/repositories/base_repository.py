# File: app/repositories/base_repository.py

from typing import Generic, TypeVar, Dict, Any, Optional, List, Type
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Base repository class providing common CRUD operations for all entities.

    Implements the repository pattern for data access with generic typing
    to ensure type safety across all derived repositories.

    Attributes:
        session (Session): The SQLAlchemy session for database operations
        model (Type): The SQLAlchemy model class this repository manages
        encryption_service (Optional): Service for encrypting/decrypting sensitive data
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the repository with a database session.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        self.session = session
        self.encryption_service = encryption_service
        # The model attribute should be set by derived classes

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Retrieve an entity by its primary key ID.

        Args:
            id (int): The primary key ID of the entity

        Returns:
            Optional[T]: The entity if found, None otherwise
        """
        entity = self.session.query(self.model).filter(self.model.id == id).first()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """
        Retrieve a list of entities with optional filtering, pagination.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return
            **filters: Additional filters to apply (field=value pairs)

        Returns:
            List[T]: List of entities matching the criteria
        """
        query = self.session.query(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new entity.

        Args:
            data (Dict[str, Any]): Dictionary containing entity field values

        Returns:
            T: The created entity
        """
        # Encrypt sensitive fields before saving
        encrypted_data = self._encrypt_sensitive_fields(data)
        entity = self.model(**encrypted_data)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return self._decrypt_sensitive_fields(entity)

    def update(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.

        Args:
            id (int): The primary key ID of the entity to update
            data (Dict[str, Any]): Dictionary containing the fields to update

        Returns:
            Optional[T]: The updated entity if found, None otherwise
        """
        entity = self.get_by_id(id)
        if not entity:
            return None

        # Encrypt sensitive fields
        encrypted_data = self._encrypt_sensitive_fields(data, entity.id)

        for key, value in encrypted_data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        self.session.commit()
        self.session.refresh(entity)
        return self._decrypt_sensitive_fields(entity)

    def delete(self, id: int) -> bool:
        """
        Delete an entity by ID.

        Args:
            id (int): The primary key ID of the entity to delete

        Returns:
            bool: True if entity was deleted, False if not found
        """
        entity = self.get_by_id(id)
        if not entity:
            return False

        self.session.delete(entity)
        self.session.commit()
        return True

    def search(
        self, query: str, fields: List[str], skip: int = 0, limit: int = 100
    ) -> List[T]:
        """
        Search for entities across specified fields.

        Args:
            query (str): The search query string
            fields (List[str]): Fields to search in
            skip (int): Records to skip (pagination)
            limit (int): Max records to return

        Returns:
            List[T]: List of matching entities
        """
        db_query = self.session.query(self.model)

        if query and fields:
            search_criteria = []
            for field in fields:
                if hasattr(self.model, field):
                    search_criteria.append(
                        getattr(self.model, field).ilike(f"%{query}%")
                    )

            if search_criteria:
                db_query = db_query.filter(or_(*search_criteria))

        entities = db_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def count(self, **filters) -> int:
        """
        Count entities matching the given filters.

        Args:
            **filters: Filters to apply (field=value pairs)

        Returns:
            int: Count of matching entities
        """
        query = self.session.query(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        return query.count()

    def _encrypt_sensitive_fields(
        self, data: Dict[str, Any], entity_id=None
    ) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in the data dictionary.

        Args:
            data (Dict[str, Any]): Data dictionary to process
            entity_id (Optional): Entity ID for encryption context

        Returns:
            Dict[str, Any]: Data with sensitive fields encrypted
        """
        if not self.encryption_service or not hasattr(self.model, "SENSITIVE_FIELDS"):
            return data

        encrypted_data = data.copy()
        for field in self.model.SENSITIVE_FIELDS:
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encryption_service.encrypt_field(
                    entity_id or "new", field, encrypted_data[field]
                )

        return encrypted_data

    def _decrypt_sensitive_fields(self, entity: T) -> T:
        """
        Decrypt sensitive fields in an entity.

        Args:
            entity (T): Entity with potentially encrypted fields

        Returns:
            T: Entity with decrypted fields
        """
        if (
            not entity
            or not self.encryption_service
            or not hasattr(entity.__class__, "SENSITIVE_FIELDS")
        ):
            return entity

        for field in entity.__class__.SENSITIVE_FIELDS:
            if hasattr(entity, field) and getattr(entity, field) is not None:
                decrypted_value = self.encryption_service.decrypt_field(
                    entity.id, field, getattr(entity, field)
                )
                setattr(entity, field, decrypted_value)

        return entity
