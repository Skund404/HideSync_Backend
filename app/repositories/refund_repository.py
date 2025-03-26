# File: app/repositories/refund_repository.py
"""
Repository for Refund entity operations.

This module provides data access functionality for refunds, including
creating, retrieving, and updating refund records.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.db.models.refund import Refund
from app.repositories.base_repository import BaseRepository


class RefundRepository(BaseRepository[Refund]):
    """
    Repository for Refund entity operations.

    Provides methods for retrieving, creating, and updating refund records.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RefundRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Refund

    def get_refunds_by_sale(self, sale_id: int) -> List[Refund]:
        """
        Get all refunds for a specific sale.

        Args:
            sale_id: ID of the sale

        Returns:
            List of refunds for the specified sale
        """
        query = self.session.query(self.model).filter(self.model.sale_id == sale_id)
        return self._decrypt_sensitive_fields_in_list(query.all())

    def get_pending_refunds(self) -> List[Refund]:
        """
        Get all pending refunds.

        Returns:
            List of pending refunds
        """
        query = self.session.query(self.model).filter(self.model.status == "PENDING")
        return self._decrypt_sensitive_fields_in_list(query.all())

    def get_refunds_by_status(self, status: str) -> List[Refund]:
        """
        Get all refunds with a specific status.

        Args:
            status: Refund status to filter by

        Returns:
            List of refunds with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)
        return self._decrypt_sensitive_fields_in_list(query.all())

    def update_refund_status(self, refund_id: int, status: str) -> Optional[Refund]:
        """
        Update a refund's status.

        Args:
            refund_id: ID of the refund
            status: New status to set

        Returns:
            Updated refund if found, None otherwise
        """
        refund = self.get_by_id(refund_id)
        if not refund:
            return None

        refund.status = status
        self.session.commit()
        self.session.refresh(refund)
        return self._decrypt_sensitive_fields(refund)

    def process_refund(
        self,
        refund_id: int,
        transaction_id: str,
        payment_method: str,
        processor_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[Refund]:
        """
        Process a refund by updating its details.

        Args:
            refund_id: ID of the refund
            transaction_id: Transaction ID from payment processor
            payment_method: Method used for the refund
            processor_id: ID of the user processing the refund
            notes: Additional notes about the refund

        Returns:
            Updated refund if found, None otherwise
        """
        refund = self.get_by_id(refund_id)
        if not refund:
            return None

        refund.process_refund(
            transaction_id=transaction_id,
            payment_method=payment_method,
            processor_id=processor_id,
            notes=notes,
        )

        self.session.commit()
        self.session.refresh(refund)
        return self._decrypt_sensitive_fields(refund)