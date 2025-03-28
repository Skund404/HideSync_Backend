# File: app/repositories/supplier_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime
# Add this import at the top of supplier_repository.py
from sqlalchemy import func
from app.db.models.supplier import Supplier
from app.db.models.enums import SupplierStatus
from app.repositories.base_repository import BaseRepository
import time


class SupplierRepository(BaseRepository[Supplier]):
    """
    Repository for Supplier entity operations.

    Handles data access for suppliers, providing methods for
    searching, filtering, and retrieving supplier information.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SupplierRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Supplier

    def get_suppliers_by_status(
        self, status: SupplierStatus, skip: int = 0, limit: int = 100
    ) -> List[Supplier]:
        """
        Get suppliers by their status.

        Args:
            status (SupplierStatus): The supplier status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of suppliers with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    # In supplier_repository.py
    def list(self, **filters) -> List[Supplier]:
        """
        List suppliers with optional filtering.

        Args:
            **filters: Filters to apply including:
                - skip: Number of records to skip
                - limit: Maximum number of records to return
                - status: Filter by supplier status
                - category: Filter by supplier category
                - search: Search term for name/contact/email

        Returns:
            List of suppliers matching the filters
        """
        query = self.session.query(self.model)

        # Apply status filter
        if "status" in filters and filters["status"]:
            query = query.filter(self.model.status == filters["status"])

        # Apply category filter
        if "category" in filters and filters["category"]:
            query = query.filter(self.model.category == filters["category"])

        # Apply material_category filter (if present in model)
        if "material_category" in filters and filters["material_category"]:
            # This assumes material_categories is a JSON array and contains the specified category
            query = query.filter(self.model.material_categories.contains(filters["material_category"]))

        # Apply search term
        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    self.model.name.ilike(search_term),
                    self.model.contact_name.ilike(search_term),  # Fixed column name
                    self.model.email.ilike(search_term)
                )
            )

        # Apply pagination
        skip = filters.get("skip", 0)
        limit = filters.get("limit", 100)

        # Order by id to ensure consistent results
        query = query.order_by(self.model.id)

        # Execute query
        entities = query.offset(skip).limit(limit).all()

        # Decrypt sensitive fields if needed
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_suppliers_by_category(
        self, category: str, skip: int = 0, limit: int = 100
    ) -> List[Supplier]:
        """
        Get suppliers by their category.

        Args:
            category (str): The supplier category to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of suppliers in the specified category
        """
        query = self.session.query(self.model).filter(self.model.category == category)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_preferred_suppliers(
        self, skip: int = 0, limit: int = 100
    ) -> List[Supplier]:
        """
        Get preferred suppliers.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of preferred suppliers
        """
        query = self.session.query(self.model).filter(
            self.model.status == SupplierStatus.PREFERRED
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create(self, data: Dict[str, Any]) -> Supplier:
        """
        Create a new supplier with timestamp-based ID.
        """
        # Set timestamps
        now = datetime.now()
        data['created_at'] = now
        data['updated_at'] = now

        # Generate a timestamp-based ID
        if 'id' not in data:
            # Use current time in milliseconds as ID
            data['id'] = int(time.time() * 1000)

        # Create entity
        encrypted_data = self._encrypt_sensitive_fields(data)
        entity = self.model(**encrypted_data)

        try:
            # Add to session and commit
            self.session.add(entity)
            self.session.commit()
        except Exception as e:
            print(f"Error during supplier creation: {e}")
            # Try direct SQL insert as fallback
            # (This would require more work in a real implementation)

        # Return the entity
        return self._decrypt_sensitive_fields(entity)

    def get_all_suppliers(self, skip: int = 0, limit: int = 100) -> List[Supplier]:
        """
        Get all suppliers with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of suppliers
        """
        query = self.session.query(self.model)

        # Fetch all entities
        entities = query.all()

        # Apply pagination after fetch (not ideal but works with SQLCipherQuery)
        if skip or limit:
            entities = entities[skip:skip + limit]

        # Decrypt sensitive fields
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def exists_by_name(self, name: str) -> bool:
        """
        Check if a supplier with the exact name exists.

        Args:
            name: Name to check

        Returns:
            True if a supplier with this name exists, False otherwise
        """
        query = self.session.query(self.model).filter(self.model.name == name)
        # Just check if any record exists - more efficient than fetching all records
        return query.first() is not None

    def get_active_suppliers(self, skip: int = 0, limit: int = 100) -> List[Supplier]:
        """
        Get active suppliers.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of active suppliers
        """
        query = self.session.query(self.model).filter(
            or_(
                self.model.status == SupplierStatus.ACTIVE,
                self.model.status == SupplierStatus.PREFERRED,
                self.model.status == SupplierStatus.STRATEGIC,
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_suppliers_by_material_category(
        self, material_category: str, skip: int = 0, limit: int = 100
    ) -> List[Supplier]:
        """
        Get suppliers that provide a specific material category.

        Args:
            material_category (str): Material category to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of suppliers providing the specified material category
        """
        # This assumes materialCategories is stored as a JSON array or similar
        query = self.session.query(self.model).filter(
            self.model.materialCategories.contains(material_category)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_suppliers_by_rating(
        self, min_rating: int, skip: int = 0, limit: int = 100
    ) -> List[Supplier]:
        """
        Get suppliers with a rating at or above the specified minimum.

        Args:
            min_rating (int): Minimum rating to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of suppliers with ratings at or above the minimum
        """
        query = self.session.query(self.model).filter(self.model.rating >= min_rating)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_supplier_status(
        self, supplier_id: int, status: SupplierStatus
    ) -> Optional[Supplier]:
        """
        Update a supplier's status.

        Args:
            supplier_id (int): ID of the supplier
            status (SupplierStatus): New status to set

        Returns:
            Optional[Supplier]: Updated supplier if found, None otherwise
        """
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            return None

        supplier.status = status

        self.session.commit()
        self.session.refresh(supplier)
        return self._decrypt_sensitive_fields(supplier)

    def update_supplier_rating(
        self, supplier_id: int, rating: int
    ) -> Optional[Supplier]:
        """
        Update a supplier's rating.

        Args:
            supplier_id (int): ID of the supplier
            rating (int): New rating value

        Returns:
            Optional[Supplier]: Updated supplier if found, None otherwise
        """
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            return None

        supplier.rating = max(min(rating, 5), 1)  # Ensure rating is between 1 and 5

        self.session.commit()
        self.session.refresh(supplier)
        return self._decrypt_sensitive_fields(supplier)

    def search_suppliers(
            self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Supplier]:
        """
        Search for suppliers by name, contact name, or email.
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.contact_name.ilike(f"%{query}%"),  # Fixed column name
                self.model.email.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_supplier_by_email(self, email: str) -> Optional[Supplier]:
        """
        Get a supplier by email address.

        Args:
            email (str): Email address to search for

        Returns:
            Optional[Supplier]: The supplier if found, None otherwise
        """
        entity = (
            self.session.query(self.model).filter(self.model.email == email).first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None
