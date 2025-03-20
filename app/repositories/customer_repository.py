# File: app/repositories/customer_repository.py

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models.customer import Customer
from app.repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """
    Repository for Customer entity operations.

    Extends the BaseRepository to provide Customer-specific data access methods.
    Handles querying, filtering, and search operations for customers.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the CustomerRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Customer

    def find_by_email(self, email: str) -> Optional[Customer]:
        """
        Find a customer by email address.

        Args:
            email (str): Email address to search for

        Returns:
            Optional[Customer]: The customer if found, None otherwise
        """
        entity = (
            self.session.query(self.model).filter(self.model.email == email).first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None

    def find_active_customers(self, skip: int = 0, limit: int = 100) -> List[Customer]:
        """
        Retrieve active customers.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Customer]: List of active customers
        """
        from app.db.models.enums import CustomerStatus

        query = self.session.query(self.model).filter(
            self.model.status == CustomerStatus.ACTIVE
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def find_by_tier(self, tier, skip: int = 0, limit: int = 100) -> List[Customer]:
        """
        Find customers by their tier.

        Args:
            tier: The customer tier to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Customer]: List of customers in the specified tier
        """
        query = self.session.query(self.model).filter(self.model.tier == tier)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def search_customers(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """
        Search for customers by name, email, or company name.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Customer]: List of matching customers
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.email.ilike(f"%{query}%"),
                self.model.company_name.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_customers_with_recent_purchases(
        self, days: int = 30, limit: int = 10
    ) -> List[Customer]:
        """
        Get customers who have made purchases within the specified number of days.

        Args:
            days (int): Number of days to look back
            limit (int): Maximum number of customers to return

        Returns:
            List[Customer]: List of customers with recent purchases
        """
        from datetime import datetime, timedelta
        from sqlalchemy import desc
        from app.db.models.sales import Sale

        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            self.session.query(self.model)
            .join(Sale, Sale.customer_id == self.model.id)
            .filter(Sale.createdAt >= cutoff_date)
            .group_by(self.model.id)
            .order_by(desc(self.model.id))
            .limit(limit)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_customers_by_source(
        self, source, skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """
        Get customers by their source (how they found your business).

        Args:
            source: The customer source to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Customer]: List of customers from the specified source
        """
        query = self.session.query(self.model).filter(self.model.source == source)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]
