# File: app/repositories/base_repository.py

from typing import Generic, TypeVar, Dict, Any, Optional, List, Type
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, and_ # Import select and func

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Base repository class providing common CRUD operations for all entities using
    modern SQLAlchemy select() syntax.

    Attributes:
        session (Session): The SQLAlchemy session for database operations
        model (Type[T]): The SQLAlchemy model class this repository manages
        encryption_service (Optional): Service for encrypting/decrypting sensitive data
    """

    def __init__(self, session: Session, model: Optional[Type[T]] = None, encryption_service=None):
        """
        Initialize the repository with a database session and the specific model.

        Args:
            session (Session): SQLAlchemy database session
            model (Type[T]): The SQLAlchemy model class this repository manages.
                             Marked Optional for init signature but should be provided by subclasses.
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        if model is None:
            # In a real scenario, you might raise an error or infer the model,
            # but for compatibility with existing MaterialRepository init, we allow None here.
            # Subclasses *must* ensure self.model is set.
            pass
        self.session = session
        self.model = model
        self.encryption_service = encryption_service

    def _get_model(self) -> Type[T]:
        """Ensures the model is set before use."""
        if self.model is None:
            raise TypeError(f"Repository model is not set for {self.__class__.__name__}")
        return self.model

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Retrieve an entity by its primary key ID using modern select().

        Args:
            id (int): The primary key ID of the entity

        Returns:
            Optional[T]: The entity if found, None otherwise
        """
        model_class = self._get_model()
        # Assuming the primary key column is always named 'id'
        stmt = select(model_class).where(getattr(model_class, 'id') == id)
        entity = self.session.execute(stmt).scalar_one_or_none()
        return self._decrypt_sensitive_fields(entity) if entity else None

    def stream(self, batch_size=100, **filters):
        """
        Stream results in batches without loading everything into memory.

        Args:
            batch_size (int): Batch size for fetching records
            **filters: Filters to apply

        Yields:
            Entity instances, one at a time
        """
        model_class = self._get_model()
        offset = 0
        while True:
            stmt = select(model_class)
            # Apply filters
            for key, value in filters.items():
                if hasattr(model_class, key):
                    stmt = stmt.where(getattr(model_class, key) == value)

            # Apply pagination
            stmt = stmt.offset(offset).limit(batch_size)

            results = self.session.execute(stmt)
            batch = results.scalars().all()

            if not batch:
                break

            for item_db in batch:
                # Process item (e.g., decrypt) before yielding
                yield self._decrypt_sensitive_fields(item_db)

            if len(batch) < batch_size: # Optimization: stop if last batch was partial
                break

            offset += batch_size


    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """
        Retrieve a list of entities with efficient pagination using modern select().

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return
            **filters: Additional filters to apply (field=value pairs)

        Returns:
            List[T]: List of entities matching the criteria
        """
        model_class = self._get_model()
        stmt = select(model_class)

        # Apply filters
        for key, value in filters.items():
            if hasattr(model_class, key):
                # Use .where() for filtering in SQLAlchemy 2.0 style
                stmt = stmt.where(getattr(model_class, key) == value)

        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)

        # Execute query
        results = self.session.execute(stmt)
        entities = results.scalars().all() # Use scalars().all() to get model instances

        # Process entities if needed (e.g., decrypt sensitive fields)
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new entity.

        Args:
            data (Dict[str, Any]): Dictionary containing entity field values

        Returns:
            T: The created entity
        """
        model_class = self._get_model()
        # Encrypt sensitive fields before saving
        encrypted_data = self._encrypt_sensitive_fields(data)
        # Ensure only columns present in the model are passed to constructor
        model_columns = {c.name for c in model_class.__table__.columns}
        filtered_data = {k: v for k, v in encrypted_data.items() if k in model_columns}

        entity = model_class(**filtered_data)
        self.session.add(entity)
        self.session.commit() # Commit persists the object and assigns PK if auto-increment
        self.session.refresh(entity) # Refresh to load any server-side defaults or triggers
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
        # Use the updated get_by_id
        entity = self.get_by_id(id)
        if not entity:
            return None

        # Encrypt sensitive fields
        encrypted_data = self._encrypt_sensitive_fields(data, entity.id)

        for key, value in encrypted_data.items():
            # Check if the attribute exists and is not a relationship or other non-column property
            if hasattr(entity, key) and key in entity.__table__.columns.keys():
                 setattr(entity, key, value)
            # Consider logging a warning for keys in data that don't map to columns

        self.session.commit() # Commit the changes
        self.session.refresh(entity) # Refresh to get the updated state
        return self._decrypt_sensitive_fields(entity)

    def delete(self, id: int) -> bool:
        """
        Delete an entity by ID.

        Args:
            id (int): The primary key ID of the entity to delete

        Returns:
            bool: True if entity was deleted, False if not found
        """
        # Use the updated get_by_id
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
        Search for entities across specified fields using modern select().

        Args:
            query (str): The search query string
            fields (List[str]): Fields to search in
            skip (int): Records to skip (pagination)
            limit (int): Max records to return

        Returns:
            List[T]: List of matching entities
        """
        model_class = self._get_model()
        stmt = select(model_class)

        if query and fields:
            search_term = f"%{query}%"
            search_criteria = []
            for field in fields:
                if hasattr(model_class, field):
                    # Assuming fields are compatible with ilike
                    search_criteria.append(
                        getattr(model_class, field).ilike(search_term)
                    )

            if search_criteria:
                stmt = stmt.where(or_(*search_criteria)) # Use where() with or_

        # Apply pagination and execute
        stmt = stmt.offset(skip).limit(limit)
        results = self.session.execute(stmt)
        entities = results.scalars().all()

        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def count(self, **filters) -> int:
        """
        Count entities matching the given filters using modern select().

        Args:
            **filters: Filters to apply (field=value pairs)

        Returns:
            int: Count of matching entities
        """
        model_class = self._get_model()
        # Correct way to count with SQLAlchemy 2.0: select(func.count()).select_from(model)
        stmt = select(func.count(getattr(model_class, 'id'))).select_from(model_class) # Count primary key

        for key, value in filters.items():
            if hasattr(model_class, key):
                stmt = stmt.where(getattr(model_class, key) == value) # Use where()

        # Execute the count query and get the scalar result
        count = self.session.execute(stmt).scalar_one()
        return count

    # --- Encryption/Decryption Methods (Assume they are correct) ---

    def _encrypt_sensitive_fields(
        self, data: Dict[str, Any], entity_id=None
    ) -> Dict[str, Any]:
        """Encrypt sensitive fields (Placeholder - assuming functional)."""
        model_class = self._get_model() # Get model safely
        if not self.encryption_service or not hasattr(model_class, "SENSITIVE_FIELDS"):
            return data
        # ... rest of the encryption logic remains the same ...
        encrypted_data = data.copy()
        for field in model_class.SENSITIVE_FIELDS:
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encryption_service.encrypt_field(
                    entity_id or "new", field, encrypted_data[field]
                )
        return encrypted_data


    def _decrypt_sensitive_fields(self, entity: T) -> T:
        """Decrypt sensitive fields (Placeholder - assuming functional)."""
        if (
            not entity
            or not self.encryption_service
            or not hasattr(entity.__class__, "SENSITIVE_FIELDS")
        ):
            return entity
        # ... rest of the decryption logic remains the same ...
        for field in entity.__class__.SENSITIVE_FIELDS:
            if hasattr(entity, field) and getattr(entity, field) is not None:
                decrypted_value = self.encryption_service.decrypt_field(
                    entity.id, field, getattr(entity, field)
                )
                setattr(entity, field, decrypted_value)
        return entity