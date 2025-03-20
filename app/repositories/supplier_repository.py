# File: app/repositories/supplier_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime

from app.db.models.supplier import Supplier
from app.db.models.enums import SupplierStatus
from app.repositories.base_repository import BaseRepository


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

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Supplier]: List of matching suppliers
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.contactName.ilike(f"%{query}%"),
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
